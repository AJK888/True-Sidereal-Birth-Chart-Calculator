"""
Admin Service

Business logic for admin operations including user management,
chart moderation, and system administration.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_

from database import User, SavedChart, ChatConversation, CreditTransaction
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class AdminService:
    """Service for admin operations."""
    
    @staticmethod
    def get_users(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get paginated list of users with optional filtering."""
        query = db.query(User)
        
        # Apply filters
        if search:
            search_filter = or_(
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        if is_admin is not None:
            query = query.filter(User.is_admin == is_admin)
        
        # Apply sorting
        if hasattr(User, sort_by):
            sort_column = getattr(User, sort_by)
            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(sort_column)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        users = query.offset(skip).limit(limit).all()
        
        return {
            "users": users,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    @staticmethod
    def get_user_stats(db: Session, user_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a user."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Count charts
        chart_count = db.query(SavedChart).filter(
            SavedChart.user_id == user_id
        ).count()
        
        # Count conversations
        conversation_count = db.query(ChatConversation).filter(
            ChatConversation.user_id == user_id
        ).count()
        
        # Get credit transactions
        credit_transactions = []
        try:
            credit_transactions = db.query(CreditTransaction).filter(
                CreditTransaction.user_id == user_id
            ).order_by(desc(CreditTransaction.created_at)).limit(10).all()
        except Exception:
            # CreditTransaction table might not exist in all databases
            pass
        
        # Calculate total credits purchased
        total_credits_purchased = db.query(
            func.sum(CreditTransaction.credits)
        ).filter(
            and_(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == "purchase"
            )
        ).scalar() or 0
        
        return {
            "user": user,
            "stats": {
                "chart_count": chart_count,
                "conversation_count": conversation_count,
                "total_credits_purchased": total_credits_purchased,
                "current_credits": user.credits,
            },
            "recent_credit_transactions": credit_transactions
        }
    
    @staticmethod
    def update_user(
        db: Session,
        user_id: int,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
        credits: Optional[int] = None
    ) -> User:
        """Update user information."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        if email is not None:
            # Check if email is already taken
            existing = db.query(User).filter(
                and_(User.email == email, User.id != user_id)
            ).first()
            if existing:
                raise ValueError("Email already in use")
            user.email = email
        
        if full_name is not None:
            user.full_name = full_name
        
        if is_active is not None:
            user.is_active = is_active
        
        if is_admin is not None:
            user.is_admin = is_admin
        
        if credits is not None:
            user.credits = credits
        
        db.commit()
        db.refresh(user)
        
        logger.info(f"User {user_id} updated by admin")
        return user
    
    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        """Delete a user and all associated data."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Delete user (cascade will handle related records)
        db.delete(user)
        db.commit()
        
        logger.info(f"User {user_id} deleted by admin")
        return True
    
    @staticmethod
    def get_all_charts(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get paginated list of all charts."""
        query = db.query(SavedChart)
        
        # Apply filters
        if user_id:
            query = query.filter(SavedChart.user_id == user_id)
        
        if search:
            query = query.filter(
                SavedChart.chart_name.ilike(f"%{search}%")
            )
        
        # Apply sorting
        if hasattr(SavedChart, sort_by):
            sort_column = getattr(SavedChart, sort_by)
            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(sort_column)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        charts = query.offset(skip).limit(limit).all()
        
        return {
            "charts": charts,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    @staticmethod
    def get_system_stats(db: Session) -> Dict[str, Any]:
        """Get system-wide statistics."""
        # Total users
        total_users = db.query(func.count(User.id)).scalar()
        active_users = db.query(func.count(User.id)).filter(
            User.is_active == True
        ).scalar()
        admin_users = db.query(func.count(User.id)).filter(
            User.is_admin == True
        ).scalar()
        
        # Total charts
        total_charts = db.query(func.count(SavedChart.id)).scalar()
        
        # Total conversations
        total_conversations = db.query(
            func.count(ChatConversation.id)
        ).scalar()
        
        # Users with subscriptions
        subscribed_users = db.query(func.count(User.id)).filter(
            User.subscription_status == "active"
        ).scalar()
        
        # Recent signups (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_signups = db.query(func.count(User.id)).filter(
            User.created_at >= thirty_days_ago
        ).scalar()
        
        # Total credits purchased
        total_credits_purchased = db.query(
            func.sum(CreditTransaction.credits)
        ).filter(
            CreditTransaction.transaction_type == "purchase"
        ).scalar() or 0
        
        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "admin": admin_users,
                "subscribed": subscribed_users,
                "recent_signups_30d": recent_signups,
            },
            "charts": {
                "total": total_charts,
            },
            "conversations": {
                "total": total_conversations,
            },
            "credits": {
                "total_purchased": total_credits_purchased,
            },
            "timestamp": datetime.utcnow().isoformat()
        }

