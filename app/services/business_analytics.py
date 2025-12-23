"""
Business Analytics Service

Provides business intelligence and analytics for the application.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract

from database import (
    User, SavedChart, ChatConversation, ChatMessage,
    CreditTransaction, SubscriptionPayment
)
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class BusinessAnalyticsService:
    """Service for business analytics and insights."""
    
    @staticmethod
    def get_user_growth_metrics(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user growth metrics over time."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Total users
        total_users = db.query(func.count(User.id)).scalar()
        
        # New users in period
        new_users = db.query(func.count(User.id)).filter(
            User.created_at >= start_date
        ).scalar()
        
        # Active users (users with activity in period)
        active_users = db.query(func.count(func.distinct(SavedChart.user_id))).filter(
            SavedChart.created_at >= start_date
        ).scalar()
        
        # Daily signups
        daily_signups = db.query(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('count')
        ).filter(
            User.created_at >= start_date
        ).group_by(func.date(User.created_at)).all()
        
        signups_by_day = [
            {"date": str(date), "count": count}
            for date, count in daily_signups
        ]
        
        # Growth rate
        previous_period_start = start_date - timedelta(days=days)
        previous_period_users = db.query(func.count(User.id)).filter(
            and_(
                User.created_at >= previous_period_start,
                User.created_at < start_date
            )
        ).scalar()
        
        growth_rate = 0.0
        if previous_period_users > 0:
            growth_rate = ((new_users - previous_period_users) / previous_period_users) * 100
        
        return {
            "period_days": days,
            "total_users": total_users,
            "new_users": new_users,
            "active_users": active_users,
            "growth_rate_percent": round(growth_rate, 2),
            "daily_signups": signups_by_day,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    
    @staticmethod
    def get_engagement_metrics(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user engagement metrics."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Charts created
        charts_created = db.query(func.count(SavedChart.id)).filter(
            SavedChart.created_at >= start_date
        ).scalar()
        
        # Conversations started
        conversations_started = db.query(func.count(ChatConversation.id)).filter(
            ChatConversation.created_at >= start_date
        ).scalar()
        
        # Messages sent
        messages_sent = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.created_at >= start_date
        ).scalar()
        
        # Average charts per user
        users_with_charts = db.query(func.count(func.distinct(SavedChart.user_id))).filter(
            SavedChart.created_at >= start_date
        ).scalar()
        avg_charts_per_user = round(charts_created / users_with_charts, 2) if users_with_charts > 0 else 0
        
        # Average messages per conversation
        avg_messages_per_conversation = round(
            messages_sent / conversations_started, 2
        ) if conversations_started > 0 else 0
        
        # Active users (users with any activity)
        active_users = db.query(func.count(func.distinct(
            func.coalesce(SavedChart.user_id, ChatConversation.user_id)
        ))).filter(
            or_(
                SavedChart.created_at >= start_date,
                ChatConversation.created_at >= start_date
            )
        ).scalar()
        
        return {
            "period_days": days,
            "charts_created": charts_created,
            "conversations_started": conversations_started,
            "messages_sent": messages_sent,
            "active_users": active_users,
            "avg_charts_per_user": avg_charts_per_user,
            "avg_messages_per_conversation": avg_messages_per_conversation,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    
    @staticmethod
    def get_feature_usage_metrics(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get feature usage metrics."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Charts with readings
        charts_with_readings = db.query(func.count(SavedChart.id)).filter(
            and_(
                SavedChart.created_at >= start_date,
                SavedChart.ai_reading.isnot(None)
            )
        ).scalar()
        
        # Total charts
        total_charts = db.query(func.count(SavedChart.id)).filter(
            SavedChart.created_at >= start_date
        ).scalar()
        
        # Reading generation rate
        reading_rate = round(
            (charts_with_readings / total_charts * 100), 2
        ) if total_charts > 0 else 0
        
        # Users with saved charts
        users_with_saved_charts = db.query(
            func.count(func.distinct(SavedChart.user_id))
        ).filter(
            SavedChart.created_at >= start_date
        ).scalar()
        
        # Users with conversations
        users_with_conversations = db.query(
            func.count(func.distinct(ChatConversation.user_id))
        ).filter(
            ChatConversation.created_at >= start_date
        ).scalar()
        
        return {
            "period_days": days,
            "charts_with_readings": charts_with_readings,
            "total_charts": total_charts,
            "reading_generation_rate_percent": reading_rate,
            "users_with_saved_charts": users_with_saved_charts,
            "users_with_conversations": users_with_conversations,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    
    @staticmethod
    def get_business_overview(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get comprehensive business overview."""
        user_growth = BusinessAnalyticsService.get_user_growth_metrics(db, days)
        engagement = BusinessAnalyticsService.get_engagement_metrics(db, days)
        feature_usage = BusinessAnalyticsService.get_feature_usage_metrics(db, days)
        
        return {
            "user_growth": user_growth,
            "engagement": engagement,
            "feature_usage": feature_usage,
            "timestamp": datetime.utcnow().isoformat()
        }

