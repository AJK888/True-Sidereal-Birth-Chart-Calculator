"""
Query Optimizer

Utilities for optimizing database queries and preventing N+1 problems.
"""

import logging
from typing import List, Any, Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select

from database import User, SavedChart, ChatConversation, ChatMessage
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class QueryOptimizer:
    """Utilities for query optimization."""
    
    @staticmethod
    def get_user_with_charts(
        db: Session,
        user_id: int,
        include_conversations: bool = False
    ) -> Optional[User]:
        """Get user with charts using eager loading to prevent N+1."""
        query = db.query(User).options(
            joinedload(User.charts)
        )
        
        if include_conversations:
            query = query.options(
                joinedload(User.conversations).joinedload(ChatConversation.messages)
            )
        
        return query.filter(User.id == user_id).first()
    
    @staticmethod
    def get_users_with_charts(
        db: Session,
        user_ids: List[int],
        limit: Optional[int] = None
    ) -> List[User]:
        """Get multiple users with their charts using eager loading."""
        query = db.query(User).options(
            selectinload(User.charts)
        ).filter(User.id.in_(user_ids))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_chart_with_conversations(
        db: Session,
        chart_id: int,
        include_messages: bool = False
    ) -> Optional[SavedChart]:
        """Get chart with conversations using eager loading."""
        query = db.query(SavedChart).options(
            joinedload(SavedChart.conversations)
        )
        
        if include_messages:
            query = query.options(
                joinedload(SavedChart.conversations).joinedload(ChatConversation.messages)
            )
        
        return query.filter(SavedChart.id == chart_id).first()
    
    @staticmethod
    def get_conversation_with_messages(
        db: Session,
        conversation_id: int
    ) -> Optional[ChatConversation]:
        """Get conversation with messages using eager loading."""
        return db.query(ChatConversation).options(
            joinedload(ChatConversation.messages)
        ).filter(ChatConversation.id == conversation_id).first()
    
    @staticmethod
    def get_user_charts_optimized(
        db: Session,
        user_id: int,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SavedChart]:
        """Get user's charts with optimized query."""
        query = db.query(SavedChart).filter(
            SavedChart.user_id == user_id
        ).order_by(SavedChart.created_at.desc())
        
        if offset:
            query = query.offset(offset)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_conversation_messages_optimized(
        db: Session,
        conversation_id: int,
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get conversation messages with optimized query."""
        query = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id
        ).order_by(ChatMessage.sequence_number)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def batch_load_users(
        db: Session,
        user_ids: List[int]
    ) -> List[User]:
        """Batch load users to avoid N+1 queries."""
        if not user_ids:
            return []
        
        return db.query(User).filter(User.id.in_(user_ids)).all()
    
    @staticmethod
    def batch_load_charts(
        db: Session,
        chart_ids: List[int]
    ) -> List[SavedChart]:
        """Batch load charts to avoid N+1 queries."""
        if not chart_ids:
            return []
        
        return db.query(SavedChart).filter(SavedChart.id.in_(chart_ids)).all()

