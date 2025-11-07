"""
Password-protected encrypted database for DiaryML
All data stored in an AES-256 encrypted SQLite file using SQLCipher
Provides both password verification and full database encryption

Uses pysqlcipher3 for transparent encryption (install: pip install pysqlcipher3)
Falls back to standard sqlite3 with warning if pysqlcipher3 not available
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import json
from contextlib import contextmanager
import hashlib

# Try to import SQLCipher for encrypted database
try:
    from pysqlcipher3 import dbapi2 as sqlite3
    HAS_ENCRYPTION = True
    _ENCRYPTION_STATUS_LOGGED = False
except ImportError:
    import sqlite3
    HAS_ENCRYPTION = False
    _ENCRYPTION_STATUS_LOGGED = False


class DiaryDatabase:
    """Password-protected and encrypted SQLite database for DiaryML"""

    def __init__(self, db_path: Optional[Path] = None, password: Optional[str] = None):
        """
        Initialize database with password protection and encryption

        Args:
            db_path: Path to database file (default: DiaryML/diary.db)
            password: Password for encryption and verification
        """
        global _ENCRYPTION_STATUS_LOGGED

        # Log encryption status once on first database initialization
        if not _ENCRYPTION_STATUS_LOGGED:
            if HAS_ENCRYPTION:
                print("✓ Using SQLCipher for database encryption")
            else:
                print("⚠ WARNING: pysqlcipher3 not found - database will NOT be encrypted!")
                print("  Install with: pip install pysqlcipher3")
                print("  Your data is currently human-readable in diary.db")
            _ENCRYPTION_STATUS_LOGGED = True

        if db_path is None:
            db_path = Path(__file__).parent.parent / "diary.db"

        self.db_path = db_path
        self.password = password
        self._password_hash = self._hash_password(password) if password else None
        self._connection: Optional[sqlite3.Connection] = None
        self.is_encrypted = HAS_ENCRYPTION

    def _hash_password(self, password: str) -> str:
        """Hash password for storage/verification"""
        return hashlib.sha256(password.encode()).hexdigest()

    @contextmanager
    def get_connection(self):
        """Get database connection with encryption"""
        conn = sqlite3.connect(str(self.db_path))

        # CRITICAL: Set encryption key FIRST (before any other operations)
        if HAS_ENCRYPTION and self.password:
            # Use the password directly as the encryption key
            conn.execute(f"PRAGMA key = '{self.password}'")
            # Set SQLCipher compatibility for better performance
            conn.execute("PRAGMA cipher_compatibility = 4")

        # Use WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode = WAL")

        # Return rows as dictionaries
        conn.row_factory = sqlite3.Row

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def initialize_schema(self):
        """Create database schema and store password hash"""
        with self.get_connection() as conn:
            # Password verification table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    password_hash TEXT NOT NULL
                )
            """)

            # Store password hash on first initialization
            if self._password_hash:
                existing = conn.execute("SELECT password_hash FROM auth WHERE id = 1").fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO auth (id, password_hash) VALUES (1, ?)",
                        (self._password_hash,)
                    )
            # Entries table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    content TEXT NOT NULL,
                    image_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Moods table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS moods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id INTEGER NOT NULL,
                    emotion TEXT NOT NULL,
                    score REAL NOT NULL,
                    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
                )
            """)

            # Projects table (extracted mentions)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    first_mentioned DATETIME,
                    last_mentioned DATETIME,
                    status TEXT DEFAULT 'active'
                )
            """)

            # Project mentions in entries
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    mention_type TEXT,
                    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)

            # Media mentions (movies, books, music, etc.)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS media_mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    sentiment TEXT,
                    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
                )
            """)

            # User preferences and patterns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Chat sessions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Chat messages
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_timestamp ON entries(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_moods_entry ON moods(entry_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)")

    def add_entry(
        self,
        content: str,
        image_path: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        Add new diary entry

        Returns:
            entry_id
        """
        if timestamp is None:
            timestamp = datetime.now()

        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO entries (content, image_path, timestamp) VALUES (?, ?, ?)",
                (content, image_path, timestamp)
            )
            return cursor.lastrowid

    def add_mood(self, entry_id: int, emotions: Dict[str, float]):
        """Add emotion scores for an entry"""
        with self.get_connection() as conn:
            for emotion, score in emotions.items():
                conn.execute(
                    "INSERT INTO moods (entry_id, emotion, score) VALUES (?, ?, ?)",
                    (entry_id, emotion, score)
                )

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """Get entry by ID with moods"""
        with self.get_connection() as conn:
            # Get entry
            entry = conn.execute(
                "SELECT * FROM entries WHERE id = ?",
                (entry_id,)
            ).fetchone()

            if not entry:
                return None

            entry_dict = dict(entry)

            # Get moods
            moods = conn.execute(
                "SELECT emotion, score FROM moods WHERE entry_id = ?",
                (entry_id,)
            ).fetchall()

            entry_dict["moods"] = {row["emotion"]: row["score"] for row in moods}

            return entry_dict

    def get_recent_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent entries"""
        with self.get_connection() as conn:
            entries = conn.execute(
                "SELECT * FROM entries ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()

            result = []
            for entry in entries:
                entry_dict = dict(entry)

                # Get moods
                moods = conn.execute(
                    "SELECT emotion, score FROM moods WHERE entry_id = ?",
                    (entry_dict["id"],)
                ).fetchall()

                entry_dict["moods"] = {row["emotion"]: row["score"] for row in moods}
                result.append(entry_dict)

            return result

    def delete_entry(self, entry_id: int):
        """Delete an entry (cascades to moods, projects, etc.)"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
            # Reclaim disk space
            conn.execute("VACUUM")

    def update_entry(self, entry_id: int, content: str, timestamp: Optional[datetime] = None):
        """
        Update an existing entry's content

        Args:
            entry_id: ID of the entry to update
            content: New content for the entry
            timestamp: Optional new timestamp
        """
        with self.get_connection() as conn:
            if timestamp:
                conn.execute(
                    "UPDATE entries SET content = ?, timestamp = ? WHERE id = ?",
                    (content, timestamp, entry_id)
                )
            else:
                conn.execute(
                    "UPDATE entries SET content = ? WHERE id = ?",
                    (content, entry_id)
                )

    def add_project(self, name: str, status: str = "active") -> int:
        """Add or update project"""
        now = datetime.now()

        with self.get_connection() as conn:
            # Try to insert, or update if exists
            cursor = conn.execute(
                """
                INSERT INTO projects (name, first_mentioned, last_mentioned, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    last_mentioned = ?,
                    status = ?
                """,
                (name, now, now, status, now, status)
            )
            return cursor.lastrowid

    def link_project_to_entry(self, entry_id: int, project_name: str, mention_type: str = "mention"):
        """Link a project mention to an entry"""
        project_id = self.add_project(project_name)

        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO project_mentions (entry_id, project_id, mention_type) VALUES (?, ?, ?)",
                (entry_id, project_id, mention_type)
            )

    def get_active_projects(self) -> List[Dict[str, Any]]:
        """Get active projects"""
        with self.get_connection() as conn:
            projects = conn.execute(
                """
                SELECT * FROM projects
                WHERE status = 'active'
                ORDER BY last_mentioned DESC
                """
            ).fetchall()

            return [dict(row) for row in projects]

    def add_media_mention(self, entry_id: int, media_type: str, title: str, sentiment: str = "neutral"):
        """Add media mention (movie, book, music, etc.)"""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO media_mentions (entry_id, media_type, title, sentiment) VALUES (?, ?, ?, ?)",
                (entry_id, media_type, title, sentiment)
            )

    def get_media_history(self, media_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get media history, optionally filtered by type"""
        with self.get_connection() as conn:
            if media_type:
                media = conn.execute(
                    """
                    SELECT * FROM media_mentions
                    WHERE media_type = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (media_type, limit)
                ).fetchall()
            else:
                media = conn.execute(
                    "SELECT * FROM media_mentions ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()

            return [dict(row) for row in media]

    def get_mood_timeline(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get mood trends over time"""
        with self.get_connection() as conn:
            results = conn.execute(
                """
                SELECT
                    DATE(e.timestamp) as date,
                    m.emotion,
                    AVG(m.score) as avg_score
                FROM entries e
                JOIN moods m ON e.id = m.entry_id
                WHERE e.timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY DATE(e.timestamp), m.emotion
                ORDER BY date DESC
                """,
                (days,)
            ).fetchall()

            return [dict(row) for row in results]

    def search_entries(
        self,
        query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        emotions: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search entries with various filters

        Args:
            query: Text search query
            start_date: Filter entries after this date
            end_date: Filter entries before this date
            emotions: Filter by dominant emotions
            limit: Maximum number of results

        Returns:
            List of matching entries with metadata
        """
        with self.get_connection() as conn:
            # Build the query dynamically
            sql = "SELECT DISTINCT e.* FROM entries e"
            conditions = []
            params = []

            # Join moods if filtering by emotion
            if emotions:
                sql += " JOIN moods m ON e.id = m.entry_id"

            sql += " WHERE 1=1"

            # Text search
            if query:
                conditions.append("e.content LIKE ?")
                params.append(f"%{query}%")

            # Date range filter
            if start_date:
                conditions.append("e.timestamp >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("e.timestamp <= ?")
                params.append(end_date)

            # Emotion filter
            if emotions and len(emotions) > 0:
                placeholders = ','.join('?' * len(emotions))
                conditions.append(f"m.emotion IN ({placeholders})")
                params.extend(emotions)
                # Only include entries where emotion has significant score
                conditions.append("m.score > 0.3")

            # Add conditions
            if conditions:
                sql += " AND " + " AND ".join(conditions)

            # Order and limit
            sql += " ORDER BY e.timestamp DESC LIMIT ?"
            params.append(limit)

            # Execute query
            entries = conn.execute(sql, params).fetchall()

            # Get moods for each entry
            result = []
            for entry in entries:
                entry_dict = dict(entry)

                # Get moods
                moods = conn.execute(
                    "SELECT emotion, score FROM moods WHERE entry_id = ?",
                    (entry_dict["id"],)
                ).fetchall()

                entry_dict["moods"] = {row["emotion"]: row["score"] for row in moods}
                result.append(entry_dict)

            return result

    def set_user_preference(self, key: str, value: Any):
        """Store user preference or pattern"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_data (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = ?,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, json.dumps(value), json.dumps(value))
            )

    def get_user_preference(self, key: str) -> Optional[Any]:
        """Get user preference"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM user_data WHERE key = ?",
                (key,)
            ).fetchone()

            if row:
                return json.loads(row["value"])
            return None

    def verify_password(self) -> bool:
        """Verify the password is correct by checking hash"""
        try:
            with self.get_connection() as conn:
                # Check if auth table exists
                result = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='auth'"
                ).fetchone()

                if not result:
                    # New database, password is valid
                    return True

                # Check password hash
                stored = conn.execute("SELECT password_hash FROM auth WHERE id = 1").fetchone()

                if not stored:
                    # No password set yet, accept any password
                    return True

                # Verify hash matches
                return stored["password_hash"] == self._password_hash

        except Exception as e:
            print(f"Password verification error: {e}")
            return False

    # === Chat Session Management ===

    def create_chat_session(self, title: Optional[str] = None) -> int:
        """Create a new chat session"""
        if title is None:
            title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO chat_sessions (title) VALUES (?)",
                (title,)
            )
            return cursor.lastrowid

    def get_chat_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all chat sessions"""
        with self.get_connection() as conn:
            sessions = conn.execute(
                """
                SELECT cs.*,
                       COUNT(cm.id) as message_count,
                       MAX(cm.timestamp) as last_message_at
                FROM chat_sessions cs
                LEFT JOIN chat_messages cm ON cs.id = cm.session_id
                GROUP BY cs.id
                ORDER BY cs.updated_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

            return [dict(row) for row in sessions]

    def get_chat_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific chat session"""
        with self.get_connection() as conn:
            session = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()

            if session:
                return dict(session)
            return None

    def delete_chat_session(self, session_id: int):
        """Delete a chat session (cascades to messages)"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
            # Reclaim disk space after deletion
            conn.execute("VACUUM")

    def update_chat_session_title(self, session_id: int, title: str):
        """Update chat session title"""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, session_id)
            )

    def add_chat_message(self, session_id: int, role: str, content: str) -> int:
        """Add a message to a chat session"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )

            # Update session timestamp
            conn.execute(
                "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )

            return cursor.lastrowid

    def get_chat_messages(self, session_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get messages for a chat session"""
        with self.get_connection() as conn:
            if limit:
                messages = conn.execute(
                    """
                    SELECT * FROM chat_messages
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (session_id, limit)
                ).fetchall()
            else:
                messages = conn.execute(
                    "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
                    (session_id,)
                ).fetchall()

            return [dict(row) for row in messages]

    def clear_chat_messages(self, session_id: int):
        """Clear all messages in a chat session"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            # Reclaim disk space
            conn.execute("VACUUM")


# Global instance
_db_instance: Optional[DiaryDatabase] = None


def get_database(password: Optional[str] = None) -> DiaryDatabase:
    """Get or create database singleton"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DiaryDatabase(password=password)
        _db_instance.initialize_schema()
    return _db_instance
