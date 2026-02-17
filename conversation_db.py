"""SQLite persistence layer for conversations.

Provides database storage and retrieval of conversations and messages.
Allows conversations to survive server restarts.
"""
from __future__ import annotations
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


DB_PATH = Path(__file__).parent.parent / "data" / "conversations.db"


def init_db():
    """Initialize the database schema if it doesn't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                context TEXT DEFAULT '{}'
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        
        # Create index for faster queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation 
            ON messages(conversation_id)
        """)
        
        conn.commit()


def save_conversation(conversation_id: str, title: str, context: Dict[str, Any] = None):
    """Save or update a conversation in the database."""
    if context is None:
        context = {}
    
    init_db()
    now = datetime.now().isoformat()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO conversations 
            (id, title, created_at, updated_at, context)
            VALUES (?, ?, 
                COALESCE((SELECT created_at FROM conversations WHERE id = ?), ?),
                ?, ?)
        """, (conversation_id, title, conversation_id, now, now, json.dumps(context)))
        conn.commit()


def save_message(message_id: str, conversation_id: str, role: str, content: str, timestamp: str):
    """Save a message to the database."""
    init_db()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO messages 
            (id, conversation_id, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (message_id, conversation_id, role, content, timestamp))
        conn.commit()


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a conversation by ID."""
    init_db()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return dict(row)


def get_conversation_messages(conversation_id: str) -> List[Dict[str, str]]:
    """Retrieve all messages for a conversation, ordered by timestamp."""
    init_db()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT id, role, content, timestamp FROM messages 
               WHERE conversation_id = ? 
               ORDER BY timestamp ASC""",
            (conversation_id,)
        )
        messages = []
        for row in cursor.fetchall():
            messages.append(dict(row))
        
        return messages


def list_all_conversations() -> List[Dict[str, Any]]:
    """List all conversations, ordered by most recent first."""
    init_db()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT id, title, created_at, updated_at FROM conversations 
               ORDER BY updated_at DESC"""
        )
        conversations = []
        
        for row in cursor.fetchall():
            conv_dict = dict(row)
            # Count messages for this conversation
            msg_cursor = conn.execute(
                "SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?",
                (conv_dict['id'],)
            )
            msg_count = msg_cursor.fetchone()[0]
            conv_dict['message_count'] = msg_count
            conversations.append(conv_dict)
        
        return conversations


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and all its messages."""
    init_db()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()
        
        return cursor.rowcount > 0


def update_conversation_title(conversation_id: str, new_title: str) -> bool:
    """Update the title of a conversation."""
    init_db()
    now = datetime.now().isoformat()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (new_title, now, conversation_id)
        )
        conn.commit()
        
        return cursor.rowcount > 0


def export_conversation(conversation_id: str, format: str = "markdown") -> str:
    """Export a conversation as text or markdown."""
    init_db()
    
    conv = get_conversation(conversation_id)
    if not conv:
        return ""
    
    messages = get_conversation_messages(conversation_id)
    
    if format == "markdown":
        output = f"# {conv['title']}\n\n"
        output += f"*Created: {conv['created_at']}*\n\n"
        
        for msg in messages:
            role_title = "User" if msg['role'] == 'user' else "Agent"
            output += f"## {role_title}\n\n{msg['content']}\n\n"
        
        return output
    
    else:  # Plain text
        output = f"=== {conv['title']} ===\n"
        output += f"Created: {conv['created_at']}\n\n"
        
        for msg in messages:
            role_title = "USER" if msg['role'] == 'user' else "AGENT"
            output += f"[{role_title}] {msg['timestamp']}\n{msg['content']}\n\n"
        
        return output


def search_conversations(query: str) -> List[Dict[str, Any]]:
    """Search conversations by title."""
    init_db()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT id, title, created_at, updated_at FROM conversations 
               WHERE title LIKE ? 
               ORDER BY updated_at DESC""",
            (f"%{query}%",)
        )
        conversations = []
        
        for row in cursor.fetchall():
            conv_dict = dict(row)
            msg_cursor = conn.execute(
                "SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?",
                (conv_dict['id'],)
            )
            msg_count = msg_cursor.fetchone()[0]
            conv_dict['message_count'] = msg_count
            conversations.append(conv_dict)
        
        return conversations
