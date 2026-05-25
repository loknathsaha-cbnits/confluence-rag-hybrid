import sqlite3
import os
from datetime import datetime
from typing import Optional, List
from pathlib import Path
import threading
from contextlib import contextmanager
import json

from .models import UserRecord, SessionRecord, InteractionRecord, SourceRecord


class DatabaseManager:
    """Thread-safe SQLite database manager for storing interactions."""

    def __init__(self, db_path: str = "data/ops_engine.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.RLock()

        # Create data directory if it doesn't exist
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema on first run
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _initialize_database(self):
        """Create database tables if they don't exist."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    engine_mode TEXT DEFAULT 'Confluence-Hybrid-RAG',
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # Interactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    confidence_score REAL,
                    router_decision TEXT,
                    execution_status TEXT,
                    processing_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error_message TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # Sources table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interaction_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    chunk_id TEXT,
                    relevance_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interaction_id) REFERENCES interactions(interaction_id)
                )
            """)

            # Create indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interactions_user_id
                ON interactions(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interactions_session_id
                ON interactions(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_interaction_id
                ON sources(interaction_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id
                ON sessions(user_id)
            """)

            conn.commit()

    def create_or_update_user(self, user_id: str) -> UserRecord:
        """Create a new user or update last_active timestamp."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = datetime.now()

            # Try to update if exists, otherwise insert
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, created_at, last_active)
                VALUES (?, ?, ?)
            """, (user_id, now, now))

            # Update last_active
            cursor.execute("""
                UPDATE users SET last_active = ? WHERE user_id = ?
            """, (now, user_id))

            conn.commit()

            # Fetch and return the user record
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            return UserRecord(
                user_id=row['user_id'],
                created_at=datetime.fromisoformat(row['created_at']),
                last_active=datetime.fromisoformat(row['last_active'])
            )

    def create_session(self, session_id: str, user_id: str, engine_mode: str = "Confluence-Hybrid-RAG") -> SessionRecord:
        """Create a new session for a user."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Ensure user exists
            self.create_or_update_user(user_id)

            now = datetime.now()

            cursor.execute("""
                INSERT OR IGNORE INTO sessions
                (session_id, user_id, created_at, engine_mode, status)
                VALUES (?, ?, ?, ?, 'active')
            """, (session_id, user_id, now, engine_mode))

            conn.commit()

            # Fetch and return the session record
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()

            return SessionRecord(
                session_id=row['session_id'],
                user_id=row['user_id'],
                created_at=datetime.fromisoformat(row['created_at']),
                engine_mode=row['engine_mode'],
                status=row['status']
            )

    def save_interaction(
        self,
        session_id: str,
        user_id: str,
        query: str,
        answer: str,
        confidence_score: float,
        sources: List[dict],
        router_decision: Optional[str] = None,
        execution_status: str = "success",
        processing_time_ms: int = 0,
        error_message: Optional[str] = None
    ) -> InteractionRecord:
        """Save an interaction (query-answer pair) with its sources."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Ensure user and session exist
            self.create_or_update_user(user_id)
            self.create_session(session_id, user_id)

            now = datetime.now()

            # Insert interaction
            cursor.execute("""
                INSERT INTO interactions
                (session_id, user_id, query, answer, confidence_score,
                 router_decision, execution_status, processing_time_ms,
                 created_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, user_id, query, answer, confidence_score,
                router_decision, execution_status, processing_time_ms,
                now, error_message
            ))

            interaction_id = cursor.lastrowid

            # Insert sources
            for source in sources:
                cursor.execute("""
                    INSERT INTO sources
                    (interaction_id, url, title, chunk_id, relevance_score, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    interaction_id,
                    source.get('url', ''),
                    source.get('title', ''),
                    source.get('chunk_id'),
                    source.get('score'),
                    now
                ))

            conn.commit()

            # Fetch and return the interaction record
            cursor.execute("SELECT * FROM interactions WHERE interaction_id = ?", (interaction_id,))
            row = cursor.fetchone()

            return InteractionRecord(
                interaction_id=row['interaction_id'],
                session_id=row['session_id'],
                user_id=row['user_id'],
                query=row['query'],
                answer=row['answer'],
                confidence_score=row['confidence_score'],
                router_decision=row['router_decision'],
                execution_status=row['execution_status'],
                processing_time_ms=row['processing_time_ms'],
                created_at=datetime.fromisoformat(row['created_at']),
                error_message=row['error_message']
            )

    def get_interaction_history(self, user_id: str, limit: int = 50) -> List[dict]:
        """Retrieve interaction history for a user."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT i.*,
                       GROUP_CONCAT(s.url, '|') as source_urls,
                       GROUP_CONCAT(s.title, '|') as source_titles
                FROM interactions i
                LEFT JOIN sources s ON i.interaction_id = s.interaction_id
                WHERE i.user_id = ?
                GROUP BY i.interaction_id
                ORDER BY i.created_at DESC
                LIMIT ?
            """, (user_id, limit))

            rows = cursor.fetchall()
            results = []

            for row in rows:
                results.append({
                    'interaction_id': row['interaction_id'],
                    'query': row['query'],
                    'answer': row['answer'],
                    'confidence_score': row['confidence_score'],
                    'created_at': row['created_at'],
                    'sources': [
                        {'url': url, 'title': title}
                        for url, title in zip(
                            (row['source_urls'] or '').split('|'),
                            (row['source_titles'] or '').split('|')
                        )
                        if url
                    ]
                })

            return results

    def get_session_interactions(self, session_id: str) -> List[dict]:
        """Retrieve all interactions in a session."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT i.*,
                       GROUP_CONCAT(s.url, '|') as source_urls,
                       GROUP_CONCAT(s.title, '|') as source_titles
                FROM interactions i
                LEFT JOIN sources s ON i.interaction_id = s.interaction_id
                WHERE i.session_id = ?
                GROUP BY i.interaction_id
                ORDER BY i.created_at ASC
            """, (session_id,))

            rows = cursor.fetchall()
            results = []

            for row in rows:
                results.append({
                    'interaction_id': row['interaction_id'],
                    'query': row['query'],
                    'answer': row['answer'],
                    'confidence_score': row['confidence_score'],
                    'created_at': row['created_at'],
                    'processing_time_ms': row['processing_time_ms'],
                    'sources': [
                        {'url': url, 'title': title}
                        for url, title in zip(
                            (row['source_urls'] or '').split('|'),
                            (row['source_titles'] or '').split('|')
                        )
                        if url
                    ]
                })

            return results

    def get_analytics(self, user_id: Optional[str] = None) -> dict:
        """Get analytics about interactions."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            where_clause = "WHERE user_id = ?" if user_id else ""
            params = (user_id,) if user_id else ()

            # Total interactions
            cursor.execute(f"SELECT COUNT(*) as count FROM interactions {where_clause}", params)
            total_interactions = cursor.fetchone()['count']

            # Average confidence
            cursor.execute(f"SELECT AVG(confidence_score) as avg_conf FROM interactions {where_clause}", params)
            avg_confidence = cursor.fetchone()['avg_conf'] or 0

            # Average processing time
            cursor.execute(f"SELECT AVG(processing_time_ms) as avg_time FROM interactions {where_clause}", params)
            avg_processing_time = cursor.fetchone()['avg_time'] or 0

            # Success rate
            cursor.execute(f"""
                SELECT
                    SUM(CASE WHEN execution_status = 'success' THEN 1 ELSE 0 END) as success_count
                FROM interactions {where_clause}
            """, params)
            success_count = cursor.fetchone()['success_count'] or 0

            return {
                'total_interactions': total_interactions,
                'average_confidence': round(avg_confidence, 3),
                'average_processing_time_ms': round(avg_processing_time, 2),
                'success_rate': round((success_count / total_interactions * 100) if total_interactions > 0 else 0, 2),
                'user_id': user_id if user_id else 'all_users'
            }

    def close(self):
        """Close the database connection."""
        with self._lock:
            if hasattr(self._local, 'connection') and self._local.connection:
                self._local.connection.close()
                self._local.connection = None


# Global database instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get or create the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def init_database(db_path: str = "data/ops_engine.db"):
    """Initialize the database manager."""
    global _db_manager
    _db_manager = DatabaseManager(db_path)
