import sqlite3

def check_db():
    conn = sqlite3.connect('fudan_knowledge_base.db')
    cursor = conn.cursor()

    sources = ['news', 'wechat']
    
    for source in sources:
        print(f"==== 来源: {source.upper()} ====")
        
        # Oldest 2
        print("最早的两条:")
        cursor.execute(f"SELECT title, publish_date FROM articles WHERE source='{source}' ORDER BY publish_date ASC LIMIT 2")
        for row in cursor.fetchall():
            print(f"  [{row[1]}] {row[0]}")
            
        # Newest 2
        print("\n最新的两条:")
        cursor.execute(f"SELECT title, publish_date FROM articles WHERE source='{source}' ORDER BY publish_date DESC LIMIT 2")
        for row in cursor.fetchall():
            print(f"  [{row[1]}] {row[0]}")
        print("-" * 30)

    conn.close()

if __name__ == "__main__":
    check_db()
