"""
Revenue Analytics Service

Provides revenue tracking and analytics.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract

from database import (
    User, CreditTransaction, SubscriptionPayment
)
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class RevenueAnalyticsService:
    """Service for revenue analytics."""
    
    @staticmethod
    def get_revenue_metrics(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get revenue metrics over time."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Total revenue from credit purchases (amount field)
        credit_purchases = db.query(
            func.sum(CreditTransaction.amount)
        ).filter(
            and_(
                CreditTransaction.transaction_type == "purchase",
                CreditTransaction.created_at >= start_date
            )
        ).scalar() or 0
        
        # Subscription revenue
        # Note: Assuming SubscriptionPayment has an amount field
        subscription_revenue = 0
        try:
            subscription_payments = db.query(
                func.sum(SubscriptionPayment.amount)
            ).filter(
                and_(
                    SubscriptionPayment.created_at >= start_date,
                    SubscriptionPayment.status == "completed"
                )
            ).scalar() or 0
            subscription_revenue = float(subscription_payments) if subscription_payments else 0
        except Exception:
            # SubscriptionPayment might not have amount field or table might not exist
            pass
        
        # Active subscriptions
        active_subscriptions = db.query(func.count(User.id)).filter(
            and_(
                User.subscription_status == "active",
                User.subscription_start_date <= end_date,
                or_(
                    User.subscription_end_date.is_(None),
                    User.subscription_end_date >= end_date
                )
            )
        ).scalar()
        
        # New subscriptions in period
        new_subscriptions = db.query(func.count(User.id)).filter(
            and_(
                User.subscription_status == "active",
                User.subscription_start_date >= start_date
            )
        ).scalar()
        
        # Daily revenue from credit purchases
        daily_credit_purchases = db.query(
            func.date(CreditTransaction.created_at).label('date'),
            func.sum(CreditTransaction.amount).label('amount')
        ).filter(
            and_(
                CreditTransaction.transaction_type == "purchase",
                CreditTransaction.created_at >= start_date
            )
        ).group_by(func.date(CreditTransaction.created_at)).all()
        
        daily_revenue = [
            {"date": str(date), "amount": float(amount) if amount else 0}
            for date, amount in daily_credit_purchases
        ]
        
        # Revenue by source
        revenue_by_source = {
            "credits": credit_purchases,
            "subscriptions": subscription_revenue,
            "total": credit_purchases + subscription_revenue
        }
        
        return {
            "period_days": days,
            "total_revenue": revenue_by_source["total"],
            "revenue_by_source": revenue_by_source,
            "active_subscriptions": active_subscriptions,
            "new_subscriptions": new_subscriptions,
            "daily_revenue": daily_revenue,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    
    @staticmethod
    def get_subscription_metrics(
        db: Session
    ) -> Dict[str, Any]:
        """Get subscription-related metrics."""
        # Total subscriptions
        total_subscriptions = db.query(func.count(User.id)).filter(
            User.subscription_status == "active"
        ).scalar()
        
        # Subscription status breakdown
        status_breakdown = {}
        for status in ["active", "inactive", "past_due", "canceled", "trialing"]:
            count = db.query(func.count(User.id)).filter(
                User.subscription_status == status
            ).scalar()
            status_breakdown[status] = count
        
        # Average subscription duration (for ended subscriptions)
        # This would require calculating from start/end dates
        
        return {
            "total_active_subscriptions": total_subscriptions,
            "status_breakdown": status_breakdown,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def get_credit_metrics(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get credit purchase and usage metrics."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Credits purchased (amount field)
        credits_purchased = db.query(
            func.sum(CreditTransaction.amount)
        ).filter(
            and_(
                CreditTransaction.transaction_type == "purchase",
                CreditTransaction.created_at >= start_date
            )
        ).scalar() or 0
        
        # Credits used (negative amounts)
        credits_used = db.query(
            func.sum(func.abs(CreditTransaction.amount))
        ).filter(
            and_(
                CreditTransaction.transaction_type == "usage",
                CreditTransaction.created_at >= start_date
            )
        ).scalar() or 0
        
        # Total credits in circulation (sum of all user credits)
        total_credits_in_circulation = db.query(
            func.sum(User.credits)
        ).scalar() or 0
        
        # Average credits per user
        total_users = db.query(func.count(User.id)).scalar()
        avg_credits_per_user = round(
            total_credits_in_circulation / total_users, 2
        ) if total_users > 0 else 0
        
        return {
            "period_days": days,
            "credits_purchased": credits_purchased,
            "credits_used": credits_used,
            "total_credits_in_circulation": total_credits_in_circulation,
            "avg_credits_per_user": avg_credits_per_user,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

