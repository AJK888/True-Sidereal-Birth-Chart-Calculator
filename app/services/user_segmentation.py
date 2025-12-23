"""
User Segmentation Service

Provides user segmentation and cohort analysis.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, extract

from database import (
    User, SavedChart, ChatConversation, CreditTransaction
)
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class UserSegmentationService:
    """Service for user segmentation."""
    
    @staticmethod
    def get_user_segments(
        db: Session
    ) -> Dict[str, Any]:
        """Get user segments based on activity and behavior."""
        # Power users (users with 5+ charts)
        power_users = db.query(func.count(func.distinct(SavedChart.user_id))).filter(
            SavedChart.user_id.in_(
                db.query(SavedChart.user_id).group_by(SavedChart.user_id).having(
                    func.count(SavedChart.id) >= 5
                ).subquery()
            )
        ).scalar()
        
        # Active users (users with charts or conversations in last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users = db.query(func.count(func.distinct(
            func.coalesce(SavedChart.user_id, ChatConversation.user_id)
        ))).filter(
            or_(
                SavedChart.created_at >= thirty_days_ago,
                ChatConversation.created_at >= thirty_days_ago
            )
        ).scalar()
        
        # Inactive users (no activity in last 90 days)
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        inactive_users = db.query(func.count(User.id)).filter(
            and_(
                ~User.id.in_(
                    db.query(SavedChart.user_id).filter(
                        SavedChart.created_at >= ninety_days_ago
                    ).distinct()
                ),
                ~User.id.in_(
                    db.query(ChatConversation.user_id).filter(
                        ChatConversation.created_at >= ninety_days_ago
                    ).distinct()
                )
            )
        ).scalar()
        
        # New users (registered in last 30 days)
        new_users = db.query(func.count(User.id)).filter(
            User.created_at >= thirty_days_ago
        ).scalar()
        
        # Subscribed users
        subscribed_users = db.query(func.count(User.id)).filter(
            User.subscription_status == "active"
        ).scalar()
        
        # Users with credits
        users_with_credits = db.query(func.count(User.id)).filter(
            User.credits > 0
        ).scalar()
        
        # Users who purchased credits
        users_who_purchased = db.query(
            func.count(func.distinct(CreditTransaction.user_id))
        ).filter(
            CreditTransaction.transaction_type == "purchase"
        ).scalar()
        
        return {
            "power_users": power_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "new_users": new_users,
            "subscribed_users": subscribed_users,
            "users_with_credits": users_with_credits,
            "users_who_purchased": users_who_purchased,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def get_cohort_analysis(
        db: Session,
        cohort_size_days: int = 30
    ) -> Dict[str, Any]:
        """Get cohort analysis by registration date."""
        # Simplified cohort analysis that works with both PostgreSQL and SQLite
        # Get all users with their registration dates
        all_users = db.query(User).order_by(User.created_at).all()
        
        # Group by month
        cohorts_dict = {}
        for user in all_users:
            if user.created_at:
                # Create month key (YYYY-MM format)
                month_key = user.created_at.strftime("%Y-%m")
                if month_key not in cohorts_dict:
                    cohorts_dict[month_key] = {
                        "user_ids": [],
                        "user_count": 0
                    }
                cohorts_dict[month_key]["user_ids"].append(user.id)
                cohorts_dict[month_key]["user_count"] += 1
        
        cohort_data = []
        for month_key in sorted(cohorts_dict.keys()):
            cohort_info = cohorts_dict[month_key]
            user_ids = cohort_info["user_ids"]
            user_count = cohort_info["user_count"]
            
            # Calculate retention: users who created charts
            users_with_charts = db.query(
                func.count(func.distinct(SavedChart.user_id))
            ).filter(
                SavedChart.user_id.in_(user_ids)
            ).scalar()
            
            retention_rate = round(
                (users_with_charts / user_count * 100), 2
            ) if user_count > 0 else 0
            
            cohort_data.append({
                "cohort_month": month_key,
                "user_count": user_count,
                "users_with_charts": users_with_charts,
                "retention_rate_percent": retention_rate
            })
        
        return {
            "cohort_size_days": cohort_size_days,
            "cohorts": cohort_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def get_user_lifetime_value(
        db: Session
    ) -> Dict[str, Any]:
        """Calculate user lifetime value metrics."""
        # Average charts per user
        total_charts = db.query(func.count(SavedChart.id)).scalar()
        total_users = db.query(func.count(User.id)).scalar()
        avg_charts_per_user = round(total_charts / total_users, 2) if total_users > 0 else 0
        
        # Average conversations per user
        total_conversations = db.query(func.count(ChatConversation.id)).scalar()
        avg_conversations_per_user = round(
            total_conversations / total_users, 2
        ) if total_users > 0 else 0
        
        # Average credits per user
        total_credits = db.query(func.sum(User.credits)).scalar() or 0
        avg_credits_per_user = round(total_credits / total_users, 2) if total_users > 0 else 0
        
        # Users who made purchases
        users_who_purchased = db.query(
            func.count(func.distinct(CreditTransaction.user_id))
        ).filter(
            CreditTransaction.transaction_type == "purchase"
        ).scalar()
        
        purchase_rate = round(
            (users_who_purchased / total_users * 100), 2
        ) if total_users > 0 else 0
        
        return {
            "avg_charts_per_user": avg_charts_per_user,
            "avg_conversations_per_user": avg_conversations_per_user,
            "avg_credits_per_user": avg_credits_per_user,
            "purchase_rate_percent": purchase_rate,
            "timestamp": datetime.utcnow().isoformat()
        }

