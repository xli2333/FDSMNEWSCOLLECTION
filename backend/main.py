from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os
import base64
import io
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()

from google import genai
from google.genai import types

import shutil

from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS # Changed from Chroma
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. Configuration & Initialization
# API Key from Environment Variable (Security Best Practice)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("⚠️ WARNING: GOOGLE_API_KEY not found in environment variables.")

# Paths & Persistent Storage Logic for Render
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define where data SHOULD be (Persistent Disk on Render, or local folder)
# On Render, mount your disk to /etc/fdsm_data
RENDER_DISK_PATH = "/etc/fdsm_data" 

if os.path.exists(RENDER_DISK_PATH) and os.environ.get("RENDER"):
    print(f"☁️ Detected Render Cloud Environment. Using Persistent Disk at {RENDER_DISK_PATH}")
    DATA_DIR = RENDER_DISK_PATH
else:
    print(f"💻 Detected Local Environment. Using local directory: {BASE_DIR}")
    DATA_DIR = BASE_DIR

# Define File Paths
SQLITE_DB_PATH = os.path.join(DATA_DIR, 'fudan_knowledge_base.db')
FAISS_DB_DIR = os.path.join(DATA_DIR, 'faiss_index') 

# --- DATA MIGRATION LOGIC (For First Deploy) ---
# If running on Cloud and data is missing in persistent disk, copy from repo source
if DATA_DIR != BASE_DIR:
    # 1. Check Database
    if not os.path.exists(SQLITE_DB_PATH):
        print("📦 Initializing Database on Persistent Disk...")
        src_db = os.path.join(BASE_DIR, 'fudan_knowledge_base.db')
        if os.path.exists(src_db):
            shutil.copy2(src_db, SQLITE_DB_PATH)
            print("✅ Database copied successfully.")
        else:
            print("⚠️ Source database not found in repo!")
    
    # 2. Check FAISS Index
    if not os.path.exists(FAISS_DB_DIR):
        print("📦 Initializing FAISS Index on Persistent Disk...")
        src_faiss = os.path.join(BASE_DIR, 'faiss_index')
        if os.path.exists(src_faiss):
            shutil.copytree(src_faiss, FAISS_DB_DIR)
            print("✅ FAISS Index copied successfully.")
        else:
            print("⚠️ Source FAISS index not found in repo!")
# -----------------------------------------------

app = FastAPI(title="Fudan Knowledge Base API")

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Models
# Embedding Model for Vector Search (Task Type: retrieval_query)
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-exp-03-07",
    task_type="retrieval_query" 
)

# Chat Model for Query Expansion
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro", 
    temperature=0.3,
    convert_system_message_to_human=True
)

# Connect to VectorDB (FAISS)
vectorstore = None
try:
    if os.path.exists(FAISS_DB_DIR):
        print(f"🔌 Loading FAISS Index from: {FAISS_DB_DIR}")
        vectorstore = FAISS.load_local(
            FAISS_DB_DIR, 
            embeddings, 
            allow_dangerous_deserialization=True, # Required for local pickle files
            distance_strategy=DistanceStrategy.COSINE
        )
        print(f"✅ Successfully loaded FAISS Index")
    else:
        print(f"❌ FAISS Index not found at {FAISS_DB_DIR}")
except Exception as e:
    print(f"❌ Failed to load FAISS Index: {e}")

# 2. Data Models (Pydantic)
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    source: Optional[str] = None

class SearchResult(BaseModel):
    id: int
    title: str
    publish_date: str
    source: str
    snippet: str
    score: float

class ArticleDetail(BaseModel):
    id: int
    title: str
    publish_date: str
    source: str
    link: str
    content: str

class ConditionalSearchRequest(BaseModel):
    keyword: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    source: Optional[str] = None
    limit: int = 10

# 3. Helper Functions
def extract_core_query(user_input: str) -> str:
    """
    Extracts the core search intent/keywords from the user's natural language input.
    """
    prompt = PromptTemplate.from_template(
        "You are a search query extractor. "
        "Your task is to extract the MAIN topic, entity, or concept from the user's input. "
        "Remove conversational filler, stopwords, and generic descriptors like 'article', 'paper', 'news', 'info', 'introduction', 'about'.\n\n"
        "Constraint: Do NOT add new words. Do NOT expand. Do NOT change the meaning. "
        "Output ONLY the extracted core subject.\n\n"
        "Example 1:\nUser: 'Show me articles about supply chain management'\nOutput: supply chain management\n\n"
        "Example 2:\nUser: 'Any news on artificial intelligence?'\nOutput: artificial intelligence\n\n"
        "Example 3:\nUser: '我想找一下那个机器人的文章'\nOutput: 机器人\n\n"
        "User Input: {input}\n\n"
        "Output:"
    )
    chain = prompt | llm | StrOutputParser()
    try:
        core_query = chain.invoke({"input": user_input})
        core_query = core_query.strip()
        print(f"🎯 Input: '{user_input}' -> Core: '{core_query}'")
        return core_query
    except Exception as e:
        print(f"⚠️ Core query extraction failed: {e}")
        return user_input

def expand_query(original_query: str) -> List[str]:
    """
    Generates related search terms and returns them as a list of strings.
    """
    prompt = PromptTemplate.from_template(
        "You are a precise search query optimizer. "
        "Generate 3-4 strictly synonymous or highly specific keywords for the user's query "
        "to improve vector retrieval accuracy.\n\n"
        "Constraint: Do NOT generate broad topics, parent categories, or loosely related concepts. "
        "For example, if the query is 'Robot', do NOT output 'AI' or 'Technology'. Output 'Robotics', 'Automaton', 'Bot'.\n\n"
        "User Query: {query}\n\n"
        "Output ONLY a comma-separated list of keywords. "
    )
    chain = prompt | llm | StrOutputParser()
    try:
        response = chain.invoke({"query": original_query})
        # Split by comma and strip whitespace
        keywords = [k.strip() for k in response.split(',') if k.strip()]
        print(f"🔍 Original: '{original_query}' -> Keywords: {keywords}")
        return keywords
    except Exception as e:
        print(f"⚠️ Query expansion failed: {e}")
        return []

def get_db_connection():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 4. API Endpoints

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Fudan Knowledge Base Backend (FAISS)"}

@app.post("/api/rag_search", response_model=List[SearchResult])
async def rag_search(request: SearchRequest):
    if vectorstore is None:
        raise HTTPException(status_code=500, detail="Vector Database not available")

    # 1. Extract Core Intent (Remove noise from user input)
    core_query = extract_core_query(request.query)

    # 2. Multi-Query Generation (Based on the clean core query)
    expanded_keywords = expand_query(core_query)
    
    # The search queries list includes the core query (priority) and expanded keywords
    search_queries = [core_query] + expanded_keywords
    
    # Configuration for Fusion
    # Euclidean Distance to Similarity conversion: 1 / (1 + distance)
    
    # 1. Threshold: Minimum score to be considered relevant.
    MIN_RELEVANCE_THRESHOLD = 0.35 
    
    # 2. Frequency Boost: Bonus for each additional query that finds the same doc.
    FREQUENCY_BOOST = 0.05 
    
    # 3. Source Weights: Prioritize original query results.
    ORIGINAL_QUERY_WEIGHT = 1.0
    EXPANDED_QUERY_WEIGHT = 0.6 # 15% penalty for docs found ONLY by expanded terms

    # 2. Parallel/Sequential Search & Fusion
    # Map: article_id -> {doc: Document, max_similarity: float, hit_count: int, hit_by_original: bool}
    candidates = {}

    print(f"🚀 Executing Search for {len(search_queries)} queries...")

    for i, query_text in enumerate(search_queries):
        # We fetch slightly more than top_k for each sub-query to ensure diversity
        # The original query (i=0) gets significantly more candidates (3x) to maximize "Exact Match" coverage
        if i == 0:
            k_limit = max(20, request.top_k * 4) 
        else:
            k_limit = request.top_k
        
        # Prepare Filter
        search_filter = None
        if request.source and request.source != "all":
            search_filter = {"source": request.source}

        results = vectorstore.similarity_search_with_score(query_text, k=k_limit, filter=search_filter)
        
        for doc, distance in results:
            # Convert Cosine Distance to Similarity (0 to 1)
            # Cosine Distance = 1 - Cosine Similarity
            similarity = 1 - distance
            
            article_id = doc.metadata.get("article_id")
            if not article_id:
                continue

            is_original_query = (i == 0)

            if article_id in candidates:
                # Update existing candidate
                entry = candidates[article_id]
                entry["max_similarity"] = max(entry["max_similarity"], similarity)
                entry["hit_count"] += 1
                if is_original_query:
                    entry["hit_by_original"] = True
            else:
                # New candidate
                candidates[article_id] = {
                    "doc": doc,
                    "max_similarity": similarity,
                    "hit_count": 1,
                    "hit_by_original": is_original_query
                }

    # 3. Final Scoring & Ranking
    final_results = []
    
    for article_id, data in candidates.items():
        # Apply Weighting based on Source
        # If the doc was found by the user's original query, it keeps full score.
        # If it was ONLY found by expanded keywords, it gets a penalty.
        weight = ORIGINAL_QUERY_WEIGHT if data["hit_by_original"] else EXPANDED_QUERY_WEIGHT
        
        weighted_similarity = data["max_similarity"] * weight
        
        # Fusion Formula: Weighted Similarity + (Bonus for frequency)
        final_score = weighted_similarity + (FREQUENCY_BOOST * (data["hit_count"] - 1))
        
        # Threshold Check
        if final_score >= MIN_RELEVANCE_THRESHOLD:
            final_results.append({
                "data": data,
                "score": final_score
            })

    # Sort by Final Score Descending
    final_results.sort(key=lambda x: x["score"], reverse=True)

    # 4. Format Response
    response_data = []
    # Slice to top_k
    for item in final_results[:request.top_k]:
        doc = item["data"]["doc"]
        meta = doc.metadata
        
        response_data.append(SearchResult(
            id=meta.get("article_id", 0),
            title=meta.get("title", "Untitled"),
            publish_date=meta.get("publish_date", "Unknown"),
            source=meta.get("source", "unknown"),
            snippet=doc.page_content[:200] + "...",
            score=round(item["score"], 4)
        ))
    
    print(f"✅ Returning {len(response_data)} results after fusion and thresholding.")
    
    print(f"✅ Returning {len(response_data)} results after fusion and thresholding.")
    return response_data

@app.post("/api/sql_search", response_model=List[SearchResult])
async def sql_search(request: ConditionalSearchRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT id, title, publish_date, source, content FROM articles WHERE 1=1"
    params = []

    if request.keyword:
        # Strict Match Logic:
        # 1. Keyword appears in Title (High relevance)
        # OR
        # 2. Keyword appears AT LEAST TWICE in Content (Deep relevance)
        # using "%keyword%keyword%" pattern to simulate count >= 2
        query += " AND (title LIKE ? OR content LIKE ?)"
        params.extend([f"%{request.keyword}%", f"%{request.keyword}%{request.keyword}%"])
    
    if request.start_date:
        query += " AND publish_date >= ?"
        params.append(request.start_date)
        
    if request.end_date:
        query += " AND publish_date <= ?"
        params.append(request.end_date)

    if request.source and request.source != "all":
        query += " AND source = ?"
        params.append(request.source)

    query += " ORDER BY publish_date DESC LIMIT ?"
    params.append(request.limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append(SearchResult(
            id=row["id"],
            title=row["title"],
            publish_date=row["publish_date"],
            source=row["source"],
            snippet=row["content"][:200] + "...",
            score=1.0 
        ))
    
    return results

@app.get("/api/article/{article_id}", response_model=ArticleDetail)
async def get_article(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Article not found")

    return ArticleDetail(
        id=row["id"],
        title=row["title"],
        publish_date=row["publish_date"],
        source=row["source"],
        link=row["link"],
        content=row["content"]
    )

class SummaryResponse(BaseModel):
    id: int
    title: str
    source: str
    publish_date: str
    link: Optional[str] = None
    summary: str

@app.get("/api/summarize_article/{article_id}", response_model=SummaryResponse)
async def summarize_article(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Article not found")

    # Construct Prompt for Pure Abstractive Summarization
    prompt = PromptTemplate.from_template(
        "任务：对以下文章进行【高保真浓缩摘要】。\n\n"
        "文章标题：{title}\n"
        "文章内容：\n{content}\n\n"
        "【严格约束】：\n"
        "1. **禁止废话**：严禁出现“好的同学们”、“这篇文章讲了...”、“导读如下”等任何开场白或结束语。直接开始输出正文。\n"
        "2. **禁止分析**：不要发表评论、不要进行价值判断、不要分析其意义。只陈述原文的事实和观点。\n"
        "3. **结构还原**：严格按照原文的逻辑结构和段落顺序进行缩写。保留原文的小标题（如果有）。\n"
        "4. **段落间距**：每一段文字结束后，必须空一行，以确保阅读排版清晰。\n"
        "5. **长度与细节**：保留原文约 50%-70% 的篇幅。保留所有关键数据、具体案例、人名和核心论据。不要写成短小的提纲，要写成一篇流畅的短文章。\n"
        "6. **格式**：使用 Markdown 格式。小标题使用 ##，重点内容使用 **加粗**。\n\n"
        "输出内容："
    )
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        # Use only the first 15000 chars to avoid token limits if article is huge
        # But generally we want as much context as possible.
        content_snippet = row["content"][:20000] 
        summary = chain.invoke({"title": row["title"], "content": content_snippet})
        
        return SummaryResponse(
            id=row["id"],
            title=row["title"],
            source=row["source"],
            publish_date=row["publish_date"],
            link=row["link"],
            summary=summary
        )
    except Exception as e:
        print(f"❌ Summary generation failed: {e}")
        # Fallback: return original content if AI fails, but marked as raw
        return SummaryResponse(
            id=row["id"],
            title=row["title"],
            source=row["source"],
            publish_date=row["publish_date"],
            link=row["link"],
            summary=f"> ⚠️ AI 导读生成失败，以下为原文内容：\n\n{row['content']}"
        )

class TimeMachineResponse(BaseModel):
    id: int
    title: str
    publish_date: str
    source: str
    quote: str
    image_base64: Optional[str] = None # Base64 encoded image

# Initialize GenAI Client for Image Generation
genai_client = genai.Client(api_key=GOOGLE_API_KEY)

@app.get("/api/time_machine", response_model=TimeMachineResponse)
async def time_machine(date: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Select Article
    if date:
        # Find the article CLOSEST to the specified date
        # Uses SQLite's julianday to calculate absolute difference in days
        try:
            cursor.execute("""
                SELECT * FROM articles 
                ORDER BY ABS(JULIANDAY(publish_date) - JULIANDAY(?)) ASC 
                LIMIT 1
            """, (date,))
        except Exception as e:
            print(f"⚠️ Date query failed (likely invalid date format), falling back to random: {e}")
            cursor.execute("SELECT * FROM articles ORDER BY RANDOM() LIMIT 1")
    else:
        # Completely random if no date provided
        cursor.execute("SELECT * FROM articles ORDER BY RANDOM() LIMIT 1")
    
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No articles found in database")

    article_title = row["title"]
    article_content = row["content"][:500] # Use snippet for context

    # 2. Extract a Quote (using existing LangChain LLM for speed)
    quote_prompt = PromptTemplate.from_template(
        "从以下文章片段中提取一句最有哲理、最打动人或最核心的金句（不超过30字）。\n"
        "如果没有合适的，就基于标题创作一句富有商业洞察力的短句。\n"
        "文章：{title}\n{content}\n\n输出金句："
    )
    quote_chain = quote_prompt | llm | StrOutputParser()
    try:
        quote = quote_chain.invoke({"title": article_title, "content": article_content}).strip()
    except:
        quote = article_title

    # 3. Generate Image (STRICTLY using gemini-3-pro-image-preview as requested)
    image_base64 = None
    try:
        print(f"🎨 Generating Time Machine image using gemini-3-pro-image-preview for: {article_title}")
        prompt = (
            f"Create a cute hand-drawn illustration style, marker or colored pencil sketch. "
            f"Subject: A conceptual representation of '{article_title}'. "
            f"Scene: A warm, academic setting at Fudan University Business School. "
            f"Details: Include minimal Simplified Chinese text labels related to the theme: '{article_title}'. "
            f"Colors: Warm orange and deep blue accents. "
            f"Style: Heartwarming, artistic, simple lines, like a diary sketch. "
            f"IMPORTANT: The entire composition MUST be a perfect 1:1 square aspect ratio. Ensure the main subject is centered within a square frame."
        )
        
        # Removed aspect_ratio from config as it caused validation error
        response = genai_client.models.generate_content(
            model='gemini-3-pro-image-preview',
            contents=[prompt],
        )
        
        # Parse response following the logic provided: iterate parts, check for inline_data
        for part in response.parts:
            if part.inline_data is not None:
                # Part data is the binary image data
                image_base64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                print("✅ Image generated successfully with gemini-3-pro-image-preview")
                break
        
        if not image_base64:
             print("⚠️ No inline_data found in response parts. Check model output.")

    except Exception as e:
        print(f"❌ Image generation failed with gemini-3-pro-image-preview: {e}")

    return TimeMachineResponse(
        id=row["id"],
        title=row["title"],
        publish_date=row["publish_date"],
        source=row["source"],
        quote=quote,
        image_base64=image_base64
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
