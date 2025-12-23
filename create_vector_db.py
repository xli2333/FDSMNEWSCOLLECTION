import sqlite3
import os
import shutil
import time
from tqdm import tqdm
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

import os

# Configuration
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Database Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, 'fudan_knowledge_base.db')
CHROMA_DB_DIR = os.path.join(BASE_DIR, 'chroma_db')

# Configuration
BATCH_SIZE = 100  # Number of chunks to process per API call/db insertion

def get_articles_from_db():
    """Reads all articles from the SQLite database."""
    print("Reading data from SQLite...")
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, publish_date, link, content, source FROM articles")
    rows = cursor.fetchall()
    conn.close()
    
    documents = []
    print(f"Converting {len(rows)} database rows to documents...")
    for row in tqdm(rows, desc="Loading Articles", unit="article"):
        # Construct metadata
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
    """Splits documents into chunks."""
    print("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Total chunks created: {len(chunks)}")
    return chunks

def create_vector_store(chunks):
    """Generates embeddings and stores them in ChromaDB with batch processing."""
    
    # 1. Setup Embedding Model
    print("Initializing Embedding Model (gemini-embedding-exp-03-07) with task_type='retrieval_document'...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-exp-03-07",
        task_type="retrieval_document"
    )
    
    # 2. Clean existing DB
    if os.path.exists(CHROMA_DB_DIR):
        print(f"Removing existing ChromaDB at {CHROMA_DB_DIR}...")
        for _ in range(3):
            try:
                shutil.rmtree(CHROMA_DB_DIR)
                time.sleep(2) # Wait for FS
                break
            except Exception as e:
                print(f"Retry deleting DB: {e}")
                time.sleep(2)


    # 3. Initialize Chroma (persist_directory creates the folder)
    print("Initializing Vector Store...")
    vectorstore = Chroma(
        persist_directory=CHROMA_DB_DIR, 
        embedding_function=embeddings
    )
    
    # 4. Process in Batches
    total_chunks = len(chunks)
    print(f"Starting embedding and insertion for {total_chunks} chunks...")
    print(f"Batch size: {BATCH_SIZE}")

    for i in tqdm(range(0, total_chunks, BATCH_SIZE), desc="Vectorizing", unit="batch"):
        batch = chunks[i : i + BATCH_SIZE]
        try:
            vectorstore.add_documents(documents=batch)
            # Optional: commit/persist often isn't needed for Chroma v0.4+ as it auto-persists, 
            # but used to be required. The context manager handles it usually.
        except Exception as e:
            print(f"\nError processing batch starting at index {i}: {e}")
            # Continue to next batch or break? Let's try to continue.
            continue
            
    print(f"✅ Vector store created and persisted at {CHROMA_DB_DIR}")
    return vectorstore

if __name__ == "__main__":
    docs = get_articles_from_db()
    if docs:
        chunks = split_documents(docs)
        create_vector_store(chunks)
        print("All operations completed successfully!")
    else:
        print("No documents found in SQLite database.")