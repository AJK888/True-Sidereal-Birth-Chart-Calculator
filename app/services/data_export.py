"""
Data Export Service

Provides data export functionality in various formats (CSV, JSON, PDF).
"""

import logging
import csv
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from io import StringIO, BytesIO
from sqlalchemy.orm import Session

from database import User, SavedChart, ChatConversation, ChatMessage, CreditTransaction
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class DataExportService:
    """Service for exporting data in various formats."""
    
    @staticmethod
    def export_user_data_json(
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """Export all user data as JSON."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get user charts
        charts = db.query(SavedChart).filter(
            SavedChart.user_id == user_id
        ).all()
        
        # Get conversations
        conversations = db.query(ChatConversation).filter(
            ChatConversation.user_id == user_id
        ).all()
        
        # Get messages for each conversation
        conversation_ids = [c.id for c in conversations]
        messages = []
        if conversation_ids:
            messages = db.query(ChatMessage).filter(
                ChatMessage.conversation_id.in_(conversation_ids)
            ).order_by(ChatMessage.sequence_number).all()
        
        # Get credit transactions
        credit_transactions = db.query(CreditTransaction).filter(
            CreditTransaction.user_id == user_id
        ).order_by(CreditTransaction.created_at).all()
        
        # Build export data
        export_data = {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "is_active": user.is_active,
                "credits": user.credits,
                "subscription_status": user.subscription_status,
            },
            "charts": [
                {
                    "id": chart.id,
                    "chart_name": chart.chart_name,
                    "created_at": chart.created_at.isoformat() if chart.created_at else None,
                    "birth_data": {
                        "year": chart.birth_year,
                        "month": chart.birth_month,
                        "day": chart.birth_day,
                        "hour": chart.birth_hour,
                        "minute": chart.birth_minute,
                        "location": chart.birth_location,
                    },
                    "has_reading": bool(chart.ai_reading),
                }
                for chart in charts
            ],
            "conversations": [
                {
                    "id": conv.id,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "chart_id": conv.chart_id,
                }
                for conv in conversations
            ],
            "messages": [
                {
                    "id": msg.id,
                    "conversation_id": msg.conversation_id,
                    "role": msg.role,
                    "content": msg.content,
                    "sequence_number": msg.sequence_number,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ],
            "credit_transactions": [
                {
                    "id": tx.id,
                    "transaction_type": tx.transaction_type,
                    "amount": tx.amount,
                    "description": tx.description,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                }
                for tx in credit_transactions
            ],
            "export_date": datetime.utcnow().isoformat()
        }
        
        return export_data
    
    @staticmethod
    def export_user_data_csv(
        db: Session,
        user_id: int
    ) -> str:
        """Export user data as CSV."""
        export_data = DataExportService.export_user_data_json(db, user_id)
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write user info
        writer.writerow(["Section", "Field", "Value"])
        writer.writerow(["User", "ID", export_data["user"]["id"]])
        writer.writerow(["User", "Email", export_data["user"]["email"]])
        writer.writerow(["User", "Full Name", export_data["user"]["full_name"]])
        writer.writerow(["User", "Created At", export_data["user"]["created_at"]])
        writer.writerow(["User", "Is Active", export_data["user"]["is_active"]])
        writer.writerow(["User", "Credits", export_data["user"]["credits"]])
        
        # Write charts
        writer.writerow([])
        writer.writerow(["Charts"])
        writer.writerow(["ID", "Name", "Created At", "Birth Year", "Birth Month", "Birth Day", "Location"])
        for chart in export_data["charts"]:
            writer.writerow([
                chart["id"],
                chart["chart_name"],
                chart["created_at"],
                chart["birth_data"]["year"],
                chart["birth_data"]["month"],
                chart["birth_data"]["day"],
                chart["birth_data"]["location"],
            ])
        
        # Write credit transactions
        writer.writerow([])
        writer.writerow(["Credit Transactions"])
        writer.writerow(["ID", "Type", "Amount", "Description", "Created At"])
        for tx in export_data["credit_transactions"]:
            writer.writerow([
                tx["id"],
                tx["transaction_type"],
                tx["amount"],
                tx["description"],
                tx["created_at"],
            ])
        
        return output.getvalue()
    
    @staticmethod
    def export_all_users_csv(
        db: Session,
        include_inactive: bool = False
    ) -> str:
        """Export all users as CSV."""
        query = db.query(User)
        if not include_inactive:
            query = query.filter(User.is_active == True)
        
        users = query.all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "ID", "Email", "Full Name", "Created At", "Is Active",
            "Is Admin", "Credits", "Subscription Status"
        ])
        
        # Write user data
        for user in users:
            writer.writerow([
                user.id,
                user.email,
                user.full_name,
                user.created_at.isoformat() if user.created_at else "",
                user.is_active,
                user.is_admin,
                user.credits,
                user.subscription_status,
            ])
        
        return output.getvalue()
    
    @staticmethod
    def export_charts_csv(
        db: Session,
        user_id: Optional[int] = None
    ) -> str:
        """Export charts as CSV."""
        query = db.query(SavedChart)
        if user_id:
            query = query.filter(SavedChart.user_id == user_id)
        
        charts = query.all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "ID", "User ID", "Chart Name", "Created At",
            "Birth Year", "Birth Month", "Birth Day",
            "Birth Hour", "Birth Minute", "Location", "Has Reading"
        ])
        
        # Write chart data
        for chart in charts:
            writer.writerow([
                chart.id,
                chart.user_id,
                chart.chart_name,
                chart.created_at.isoformat() if chart.created_at else "",
                chart.birth_year,
                chart.birth_month,
                chart.birth_day,
                chart.birth_hour,
                chart.birth_minute,
                chart.birth_location,
                bool(chart.ai_reading),
            ])
        
        return output.getvalue()

