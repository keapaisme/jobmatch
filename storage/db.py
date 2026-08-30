import sqlite3
import hashlib
import os
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "opportunities.db")

class DatabaseManager:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化資料庫 schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 防重去重紀錄表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_posts (
                post_id TEXT PRIMARY KEY,
                url TEXT UNIQUE,
                content_hash TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # 2. 已匹配高價值商機表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT UNIQUE,
                title TEXT,
                url TEXT,
                source TEXT,
                score INTEGER,
                x_budget_score INTEGER,
                y_urgency_score REAL,
                vector_json TEXT,
                ai_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # 3. 用戶誤判回報日誌表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT,
                title TEXT,
                content_snippet TEXT,
                reported_reason TEXT,
                meta_intent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()

    @staticmethod
    def generate_hash(content: str) -> str:
        """根據內文生成 MD5 指紋"""
        return hashlib.md5(content.strip().encode("utf-8")).hexdigest()

    def is_seen(self, post_id: str, url: str, content: str) -> bool:
        """防重去重檢查 (URL + Content Hash)"""
        c_hash = self.generate_hash(content) if content else ""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM seen_posts 
                WHERE post_id = ? OR url = ? OR (content_hash != '' AND content_hash = ?)
            """, (post_id, url, c_hash))
            return cursor.fetchone() is not None

    def mark_seen(self, post_id: str, url: str, content: str, source: str):
        """記錄已處理貼文"""
        c_hash = self.generate_hash(content) if content else ""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO seen_posts (post_id, url, content_hash, source)
                VALUES (?, ?, ?, ?)
            """, (post_id, url, c_hash, source))
            conn.commit()

    def save_opportunity(self, post_id: str, title: str, url: str, source: str, 
                         score: int, x_score: int, y_score: float, vector_json: str, ai_reason: str):
        """儲存高價值商機"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO opportunities 
                (post_id, title, url, source, score, x_budget_score, y_urgency_score, vector_json, ai_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, title, url, source, score, x_score, y_score, vector_json, ai_reason))
            conn.commit()

    def add_feedback(self, post_id: str, title: str, content_snippet: str, reason: str, meta_intent: str = "Zero-Margin Group Buy"):
        """記錄誤判案例並寫入反饋庫"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback_log (post_id, title, content_snippet, reported_reason, meta_intent)
                VALUES (?, ?, ?, ?, ?)
            """, (post_id, title, content_snippet, reason, meta_intent))
            conn.commit()

if __name__ == "__main__":
    db = DatabaseManager()
    print("Database initialized successfully at:", DB_PATH)
