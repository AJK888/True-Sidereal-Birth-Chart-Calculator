"""
Search Service

Provides advanced search and filtering functionality.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, ilike

from database import User, SavedChart, ChatConversation, ChatMessage
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class SearchService:
    """Service for advanced search and filtering."""
    
    @staticmethod
    def search_users(
        db: Session,
        query: str,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
        has_subscription: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search users by email, name, or other criteria."""
        search_query = db.query(User)
        
        # Text search
        if query:
            search_query = search_query.filter(
                or_(
                    User.email.ilike(f"%{query}%"),
                    User.full_name.ilike(f"%{query}%")
                )
            )
        
        # Filters
        if is_active is not None:
            search_query = search_query.filter(User.is_active == is_active)
        
        if is_admin is not None:
            search_query = search_query.filter(User.is_admin == is_admin)
        
        if has_subscription is not None:
            if has_subscription:
                search_query = search_query.filter(User.subscription_status == "active")
            else:
                search_query = search_query.filter(User.subscription_status != "active")
        
        users = search_query.limit(limit).all()
        
        return [
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "subscription_status": user.subscription_status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ]
    
    @staticmethod
    def search_charts(
        db: Session,
        query: Optional[str] = None,
        user_id: Optional[int] = None,
        has_reading: Optional[bool] = None,
        birth_year: Optional[int] = None,
        birth_month: Optional[int] = None,
        location: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search charts with advanced filtering."""
        search_query = db.query(SavedChart)
        
        # Text search
        if query:
            search_query = search_query.filter(
                or_(
                    SavedChart.chart_name.ilike(f"%{query}%"),
                    SavedChart.birth_location.ilike(f"%{query}%")
                )
            )
        
        # Filters
        if user_id:
            search_query = search_query.filter(SavedChart.user_id == user_id)
        
        if has_reading is not None:
            if has_reading:
                search_query = search_query.filter(SavedChart.ai_reading.isnot(None))
            else:
                search_query = search_query.filter(SavedChart.ai_reading.is_(None))
        
        if birth_year:
            search_query = search_query.filter(SavedChart.birth_year == birth_year)
        
        if birth_month:
            search_query = search_query.filter(SavedChart.birth_month == birth_month)
        
        if location:
            search_query = search_query.filter(
                SavedChart.birth_location.ilike(f"%{location}%")
            )
        
        if created_after:
            search_query = search_query.filter(SavedChart.created_at >= created_after)
        
        if created_before:
            search_query = search_query.filter(SavedChart.created_at <= created_before)
        
        charts = search_query.order_by(SavedChart.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": chart.id,
                "user_id": chart.user_id,
                "chart_name": chart.chart_name,
                "birth_year": chart.birth_year,
                "birth_month": chart.birth_month,
                "birth_day": chart.birth_day,
                "birth_location": chart.birth_location,
                "has_reading": bool(chart.ai_reading),
                "created_at": chart.created_at.isoformat() if chart.created_at else None,
            }
            for chart in charts
        ]
    
    @staticmethod
    def search_conversations(
        db: Session,
        query: Optional[str] = None,
        user_id: Optional[int] = None,
        chart_id: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search conversations with filtering."""
        search_query = db.query(ChatConversation)
        
        # Text search
        if query:
            search_query = search_query.filter(
                ChatConversation.title.ilike(f"%{query}%")
            )
        
        # Filters
        if user_id:
            search_query = search_query.filter(ChatConversation.user_id == user_id)
        
        if chart_id:
            search_query = search_query.filter(ChatConversation.chart_id == chart_id)
        
        if created_after:
            search_query = search_query.filter(ChatConversation.created_at >= created_after)
        
        if created_before:
            search_query = search_query.filter(ChatConversation.created_at <= created_before)
        
        conversations = search_query.order_by(ChatConversation.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": conv.id,
                "user_id": conv.user_id,
                "chart_id": conv.chart_id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
            for conv in conversations
        ]
    
    @staticmethod
    def search_messages(
        db: Session,
        query: str,
        conversation_id: Optional[int] = None,
        role: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search messages by content."""
        search_query = db.query(ChatMessage)
        
        # Text search
        if query:
            search_query = search_query.filter(
                ChatMessage.content.ilike(f"%{query}%")
            )
        
        # Filters
        if conversation_id:
            search_query = search_query.filter(
                ChatMessage.conversation_id == conversation_id
            )
        
        if role:
            search_query = search_query.filter(ChatMessage.role == role)
        
        messages = search_query.order_by(ChatMessage.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "role": msg.role,
                "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,  # Truncate for preview
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]
    
    @staticmethod
    def get_search_suggestions(
        db: Session,
        query: str,
        search_type: str = "all"
    ) -> Dict[str, List[str]]:
        """Get search suggestions based on partial query."""
        suggestions = {
            "users": [],
            "charts": [],
            "conversations": []
        }
        
        if not query or len(query) < 2:
            return suggestions
        
        # User suggestions
        if search_type in ["all", "users"]:
            users = db.query(User).filter(
                or_(
                    User.email.ilike(f"{query}%"),
                    User.full_name.ilike(f"{query}%")
                )
            ).limit(5).all()
            suggestions["users"] = [
                user.email for user in users
            ]
        
        # Chart suggestions
        if search_type in ["all", "charts"]:
            charts = db.query(SavedChart).filter(
                SavedChart.chart_name.ilike(f"{query}%")
            ).limit(5).all()
            suggestions["charts"] = [
                chart.chart_name for chart in charts
            ]
        
        # Conversation suggestions
        if search_type in ["all", "conversations"]:
            conversations = db.query(ChatConversation).filter(
                ChatConversation.title.ilike(f"{query}%")
            ).limit(5).all()
            suggestions["conversations"] = [
                conv.title for conv in conversations
            ]
        
        return suggestions

