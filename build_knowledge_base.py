import os
import sqlite3

# Configuration
BASE_DIR = os.getcwd()
NEWS_DIR = os.path.join(BASE_DIR, 'Fudan_News_Data')   # Changed from Media to News
WECHAT_DIR = os.path.join(BASE_DIR, 'Fudan_Wechat_Data')
DB_NAME = 'fudan_knowledge_base.db'

def init_db():
    """Initialize the SQLite database with the required schema."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Drop table if exists to ensure clean state
    cursor.execute('DROP TABLE IF EXISTS articles')
    
    cursor.execute('''
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT,
            publish_date TEXT,
            link TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    return conn

def parse_content_file(file_path):
    """
    Parses a content.txt file to extract metadata and body.
    Returns a dictionary or None if parsing fails.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

    data = {
        'title': '',
        'publish_date': '',
        'link': '',
        'content': ''
    }
    
    header_parsed = False
    content_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        
        if not header_parsed:
            if line_stripped.startswith('标题:'):
                data['title'] = line_stripped.replace('标题:', '').strip()
            elif line_stripped.startswith('日期:'):
                data['publish_date'] = line_stripped.replace('日期:', '').strip()
            elif line_stripped.startswith('链接:'):
                data['link'] = line_stripped.replace('链接:', '').strip()
            elif line_stripped.startswith('---'): # Separator found
                header_parsed = True
            # Ignore other header lines
        else:
            content_lines.append(line)
            
    data['content'] = ''.join(content_lines).strip()
    
    return data

def process_directory(conn, source_name, root_dir):
    """
    Traverses the directory, finds content.txt files, and inserts them into the DB.
    """
    cursor = conn.cursor()
    count = 0
    
    print(f"Scanning {source_name} directory: {root_dir}...")
    
    for root, dirs, files in os.walk(root_dir):
        if 'content.txt' in files:
            file_path = os.path.join(root, 'content.txt')
            article_data = parse_content_file(file_path)
            
            if article_data:
                cursor.execute('''
                    INSERT INTO articles (source, title, publish_date, link, content)
                    VALUES (?, ?, ?, ?, ?)
                ''', (source_name, article_data['title'], article_data['publish_date'], article_data['link'], article_data['content']))
                count += 1
                
                if count % 100 == 0:
                    print(f"Processed {count} records for {source_name}...")

    conn.commit()
    print(f"Finished {source_name}. Total records: {count}")

def main():
    if os.path.exists(DB_NAME):
        try:
            os.remove(DB_NAME)
            print(f"Removed existing database: {DB_NAME}")
        except PermissionError:
            print(f"Warning: Could not remove {DB_NAME}. It might be in use. Appending to it (or failing if schema conflict).")

    conn = init_db()
    
    # Process News Data (Source: news)
    if os.path.exists(NEWS_DIR):
        process_directory(conn, 'news', NEWS_DIR)
    else:
        print(f"Directory not found: {NEWS_DIR}")
        
    # Process Wechat Data (Source: wechat)
    if os.path.exists(WECHAT_DIR):
        process_directory(conn, 'wechat', WECHAT_DIR)
    else:
        print(f"Directory not found: {WECHAT_DIR}")

    # Verify counts
    cursor = conn.cursor()
    cursor.execute("SELECT source, COUNT(*) FROM articles GROUP BY source")
    results = cursor.fetchall()
    print("\nDatabase Summary:")
    for row in results:
        print(f"Source: {row[0]}, Count: {row[1]}")
        
    conn.close()
    print(f"\nDatabase {DB_NAME} created successfully.")

if __name__ == "__main__":
    main()