"""
Database query optimization utilities.

Provides helpers for optimizing database queries with eager loading
and query optimization patterns.
"""

from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Optional
from database import SavedChart, User, ChatConversation, ChatMessage


def get_user_charts_optimized(db: Session, user_id: int) -> List[SavedChart]:
    """
    Get user's saved charts with optimized query.
    
    Uses eager loading to avoid N+1 queries.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        List of SavedChart objects
    """
    return db.query(SavedChart)\
        .filter(SavedChart.user_id == user_id)\
        .order_by(SavedChart.created_at.desc())\
        .all()


def get_chart_with_conversations(db: Session, chart_id: int, user_id: int) -> Optional[SavedChart]:
    """
    Get chart with its conversations (eager loading).
    
    Args:
        db: Database session
        chart_id: Chart ID
        user_id: User ID (for security check)
        
    Returns:
        SavedChart with conversations loaded, or None
    """
    return db.query(SavedChart)\
        .filter(
            SavedChart.id == chart_id,
            SavedChart.user_id == user_id
        )\
        .options(selectinload(SavedChart.conversations))\
        .first()


def get_conversation_with_messages(db: Session, conversation_id: int, user_id: int) -> Optional[ChatConversation]:
    """
    Get conversation with its messages (eager loading).
    
    Args:
        db: Database session
        conversation_id: Conversation ID
        user_id: User ID (for security check)
        
    Returns:
        ChatConversation with messages loaded, or None
    """
    return db.query(ChatConversation)\
        .filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user_id
        )\
        .options(selectinload(ChatConversation.messages))\
        .first()


def get_user_conversations_optimized(db: Session, user_id: int) -> List[ChatConversation]:
    """
    Get user's conversations with optimized query.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        List of ChatConversation objects
    """
    return db.query(ChatConversation)\
        .filter(ChatConversation.user_id == user_id)\
        .order_by(ChatConversation.updated_at.desc())\
        .all()

