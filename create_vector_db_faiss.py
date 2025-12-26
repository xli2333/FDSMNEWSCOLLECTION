import sqlite3
import os
import time
from tqdm import tqdm
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

import os

# Configuration
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, 'fudan_knowledge_base.db')
FAISS_DB_DIR = os.path.join(BASE_DIR, 'faiss_index')

# Configuration
BATCH_SIZE = 50   # Process 50 chunks at a time
SAVE_EVERY_N_BATCHES = 5 # Save to disk every 5 batches (approx every 250 chunks)

def get_articles_from_db():
    print("Reading data from SQLite...")
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, publish_date, link, content, source FROM articles")
    rows = cursor.fetchall()
    conn.close()
    
    documents = []
    print(f"Converting {len(rows)} database rows to documents...")
    for row in tqdm(rows, desc="Loading Articles", unit="article"):
        metadata = {
            "article_id": row[0],
            "title": row[1] if row[1] else "Untitled",
            "publish_date": row[2] if row[2] else "Unknown",
            "link": row[3] if row[3] else "",
            "source": row[5]
        }
        content = row[4]
        if content:
            documents.append(Document(page_content=content, metadata=metadata))
    return documents

def split_documents(documents):
    print("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Total chunks available: {len(chunks)}")
    return chunks

def create_vector_store(chunks):
    print("Initializing Embedding Model (gemini-embedding-exp-03-07)...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-exp-03-07",
        task_type="retrieval_document"
    )
    
    vectorstore = None
    processed_count = 0

    # 1. Try to load existing index to RESUME
    if os.path.exists(FAISS_DB_DIR) and os.path.exists(os.path.join(FAISS_DB_DIR, "index.faiss")):
        try:
            print(f"🔄 Found existing index at {FAISS_DB_DIR}. Attempting to resume...")
            vectorstore = FAISS.load_local(FAISS_DB_DIR, embeddings, allow_dangerous_deserialization=True)
            processed_count = vectorstore.index.ntotal
            print(f"✅ Resuming from chunk {processed_count}/{len(chunks)}")
        except Exception as e:
            print(f"⚠️ Could not load existing index ({e}). Starting from scratch.")
    else:
        print("🆕 Starting new vector index.")

    # 2. Slice chunks to process only new ones
    if processed_count >= len(chunks):
        print("🎉 All chunks are already processed!")
        return

    remaining_chunks = chunks[processed_count:]
    total_batches = (len(remaining_chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"Processing {len(remaining_chunks)} remaining chunks in {total_batches} batches...")

    batch_idx = 0
    for i in tqdm(range(0, len(remaining_chunks), BATCH_SIZE), desc="Vectorizing", unit="batch"):
        batch = remaining_chunks[i : i + BATCH_SIZE]
        
        # Retry logic for API calls
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if vectorstore is None:
                    vectorstore = FAISS.from_documents(batch, embeddings, distance_strategy=DistanceStrategy.COSINE)
                else:
                    vectorstore.add_documents(batch)
                break # Success
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"\n❌ Error on batch {batch_idx}: {e}")
                    raise e
                time.sleep(2) # Wait before retry

        batch_idx += 1

        # Periodic Save (Checkpointing)
        if batch_idx % SAVE_EVERY_N_BATCHES == 0:
            _save_index(vectorstore)
            
    # Final Save
    _save_index(vectorstore)
    print("🎉 All operations completed successfully!")

def _save_index(vectorstore):
    """Helper to save safely"""
    if not os.path.exists(FAISS_DB_DIR):
        os.makedirs(FAISS_DB_DIR, exist_ok=True)
    
    try:
        vectorstore.save_local(FAISS_DB_DIR)
        # print(f"💾 Checkpoint saved.") # Optional: reduce spam
    except Exception as e:
        print(f"\n❌ Failed to save index: {e}")

if __name__ == "__main__":
    docs = get_articles_from_db()
    if docs:
        chunks = split_documents(docs)
        create_vector_store(chunks)
    else:
        print("No documents found in SQLite database.")