"""Conversation management for multi-turn chat with the AI agent.

Tracks message history, turns, and maintains context for ongoing conversations.
Supports optional SQLite persistence for conversations to survive server restarts.
"""
from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime
import uuid
import json

# Optional persistence layer
try:
    from . import conversation_db
    _PERSISTENCE_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    _PERSISTENCE_AVAILABLE = False


class Message:
    """Represents a single message in a conversation."""

    def __init__(self, role: str, content: str, timestamp: str | None = None, message_id: str | None = None):
        """role: 'user', 'agent', or 'system'. content: message text."""
        self.id = message_id or str(uuid.uuid4())
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }


class Conversation:
    """Represents a multi-turn conversation with the AI agent."""

    def __init__(self, conversation_id: str | None = None, title: str = "New Conversation", persist: bool = True):
        self.id = conversation_id or str(uuid.uuid4())
        self.title = title
        self.messages: List[Message] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.context: Dict[str, Any] = {}  # e.g., last mission matched, etc.
        self.persist_enabled = persist and _PERSISTENCE_AVAILABLE
        
        # Save to database if persistence is enabled
        if self.persist_enabled:
            conversation_db.save_conversation(self.id, self.title, self.context)

    def add_message(self, role: str, content: str) -> Message:
        """Add a message to the conversation and return it."""
        msg = Message(role, content)
        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()
        
        # Save message to database if persistence is enabled
        if self.persist_enabled:
            conversation_db.save_message(msg.id, self.id, role, content, msg.timestamp)
            conversation_db.save_conversation(self.id, self.title, self.context)
        
        return msg

    def get_history(self, limit: int | None = None) -> List[Dict[str, Any]]:
        """Get message history (optionally limited to last N messages)."""
        msgs = self.messages if not limit else self.messages[-limit :]
        return [m.to_dict() for m in msgs]

    def get_context_for_ai(self) -> List[Dict[str, str]]:
        """Format history for AI agent input (system-compatible format)."""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def update_context(self, key: str, value: Any):
        """Store context data (e.g., mission ID, pilot info)."""
        self.context[key] = value
        self.updated_at = datetime.now().isoformat()
        
        # Save to database if persistence is enabled
        if self.persist_enabled:
            conversation_db.save_conversation(self.id, self.title, self.context)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": len(self.messages),
            "messages": self.get_history(),
            "context": self.context,
        }


class ConversationManager:
    """Manages multiple conversations with users.
    
    Supports optional SQLite persistence so conversations survive server restarts.
    Enable by ensuring conversation_db module is available.
    """

    def __init__(self, load_from_db: bool = True):
        self.conversations: Dict[str, Conversation] = {}
        self.persist_enabled = _PERSISTENCE_AVAILABLE
        
        # Load persisted conversations from database on startup
        if self.persist_enabled and load_from_db:
            self._load_from_database()

    def _load_from_database(self):
        """Load all conversations from the database."""
        if not self.persist_enabled:
            return
        
        try:
            for conv_data in conversation_db.list_all_conversations():
                conv = Conversation(
                    conversation_id=conv_data['id'],
                    title=conv_data['title'],
                    persist=True
                )
                # Load messages for this conversation
                messages = conversation_db.get_conversation_messages(conv_data['id'])
                for msg_data in messages:
                    msg = Message(
                        role=msg_data['role'],
                        content=msg_data['content'],
                        timestamp=msg_data['timestamp'],
                        message_id=msg_data['id']
                    )
                    conv.messages.append(msg)
                
                self.conversations[conv.id] = conv
        except Exception as e:
            print(f"Warning: Failed to load conversations from database: {e}")

    def create_conversation(self, title: str = "New Conversation") -> Conversation:
        """Create a new conversation and return it."""
        conv = Conversation(title=title, persist=self.persist_enabled)
        self.conversations[conv.id] = conv
        return conv

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Retrieve a conversation by ID."""
        return self.conversations.get(conversation_id)

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all conversations (summary only)."""
        return [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "message_count": len(c.messages),
            }
            for c in self.conversations.values()
        ]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation by ID."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            
            # Also delete from database if persistence is enabled
            if self.persist_enabled:
                conversation_db.delete_conversation(conversation_id)
            
            return True
        return False

    def rename_conversation(self, conversation_id: str, new_title: str) -> bool:
        """Rename a conversation."""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return False
        
        conv.title = new_title
        conv.updated_at = datetime.now().isoformat()
        
        # Update in database if persistence is enabled
        if self.persist_enabled:
            conversation_db.update_conversation_title(conversation_id, new_title)
        
        return True

    def export_conversation(self, conversation_id: str, format: str = "markdown") -> str:
        """Export a conversation as text or markdown."""
        if self.persist_enabled:
            return conversation_db.export_conversation(conversation_id, format)
        
        # Fallback: export from in-memory conversation
        conv = self.get_conversation(conversation_id)
        if not conv:
            return ""
        
        if format == "markdown":
            output = f"# {conv.title}\n\n"
            output += f"*Created: {conv.created_at}*\n\n"
            
            for msg in conv.messages:
                role_title = "User" if msg.role == 'user' else "Agent"
                output += f"## {role_title}\n\n{msg.content}\n\n"
            
            return output
        else:  # Plain text
            output = f"=== {conv.title} ===\n"
            output += f"Created: {conv.created_at}\n\n"
            
            for msg in conv.messages:
                role_title = "USER" if msg.role == 'user' else "AGENT"
                output += f"[{role_title}] {msg.timestamp}\n{msg.content}\n\n"
            
            return output

    def add_message(self, conversation_id: str, role: str, content: str) -> Message | None:
        """Add a message to a conversation."""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        return conv.add_message(role, content)
