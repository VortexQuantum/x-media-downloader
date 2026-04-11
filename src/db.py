"""SQLite database for tracking downloaded media."""

import sqlite3
import os


class DownloadDB:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                tweet_id TEXT NOT NULL,
                media_url TEXT NOT NULL,
                file_path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tweet_id, media_url)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_downloaded_at
            ON downloads(downloaded_at)
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fetch_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                fetched_up_to INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Ensure the single row exists
        self.conn.execute("""
            INSERT OR IGNORE INTO fetch_state (id, fetched_up_to)
            VALUES (1, 0)
        """)
        self.conn.commit()

    def is_downloaded(self, tweet_id: str, media_url: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM downloads WHERE tweet_id = ? AND media_url = ?",
            (tweet_id, media_url)
        ).fetchone()
        return row is not None

    def mark_downloaded(self, tweet_id: str, media_url: str,
                        file_path: str, media_type: str):
        self.conn.execute(
            """INSERT OR IGNORE INTO downloads
               (tweet_id, media_url, file_path, media_type)
               VALUES (?, ?, ?, ?)""",
            (tweet_id, media_url, file_path, media_type)
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        total = self.conn.execute(
            "SELECT COUNT(*) FROM downloads"
        ).fetchone()[0]
        by_type = {}
        for row in self.conn.execute(
            "SELECT media_type, COUNT(*) as cnt FROM downloads GROUP BY media_type"
        ):
            by_type[row[0]] = row[1]
        unique_tweets = self.conn.execute(
            "SELECT COUNT(DISTINCT tweet_id) FROM downloads"
        ).fetchone()[0]
        return {"total": total, "by_type": by_type, "unique_tweets": unique_tweets}

    def get_fetch_offset(self) -> int:
        row = self.conn.execute(
            "SELECT fetched_up_to FROM fetch_state WHERE id = 1"
        ).fetchone()
        return row[0] if row else 0

    def set_fetch_offset(self, offset: int):
        self.conn.execute(
            "UPDATE fetch_state SET fetched_up_to = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            (offset,)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
