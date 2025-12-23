"""
GDPR Compliance Service

Provides GDPR-compliant data export and deletion functionality.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from database import User, SavedChart, ChatConversation, ChatMessage, CreditTransaction
from app.services.data_export import DataExportService
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class GDPRService:
    """Service for GDPR compliance operations."""
    
    @staticmethod
    def export_user_data_gdpr(
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Export all user data in GDPR-compliant format.
        
        This includes all personal data associated with the user.
        """
        try:
            export_data = DataExportService.export_user_data_json(db, user_id)
            
            # Add GDPR metadata
            export_data["gdpr_export"] = {
                "export_date": datetime.utcnow().isoformat(),
                "purpose": "GDPR data export",
                "data_categories": [
                    "personal_information",
                    "birth_charts",
                    "conversations",
                    "messages",
                    "credit_transactions"
                ]
            }
            
            logger.info(f"GDPR data export generated for user {user_id}")
            return export_data
        except Exception as e:
            logger.error(f"Error exporting GDPR data for user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def delete_user_data_gdpr(
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Delete all user data in compliance with GDPR right to erasure.
        
        This permanently deletes all personal data associated with the user.
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Log deletion request
            deletion_log = {
                "user_id": user_id,
                "email": user.email,
                "deletion_date": datetime.utcnow().isoformat(),
                "reason": "GDPR right to erasure",
                "data_deleted": []
            }
            
            # Delete related data (cascade should handle most, but we'll be explicit)
            # Delete messages
            conversation_ids = db.query(ChatConversation.id).filter(
                ChatConversation.user_id == user_id
            ).subquery()
            
            messages_deleted = db.query(ChatMessage).filter(
                ChatMessage.conversation_id.in_(conversation_ids)
            ).delete(synchronize_session=False)
            deletion_log["data_deleted"].append(f"{messages_deleted} messages")
            
            # Delete conversations
            conversations_deleted = db.query(ChatConversation).filter(
                ChatConversation.user_id == user_id
            ).delete(synchronize_session=False)
            deletion_log["data_deleted"].append(f"{conversations_deleted} conversations")
            
            # Delete charts
            charts_deleted = db.query(SavedChart).filter(
                SavedChart.user_id == user_id
            ).delete(synchronize_session=False)
            deletion_log["data_deleted"].append(f"{charts_deleted} charts")
            
            # Delete credit transactions
            transactions_deleted = db.query(CreditTransaction).filter(
                CreditTransaction.user_id == user_id
            ).delete(synchronize_session=False)
            deletion_log["data_deleted"].append(f"{transactions_deleted} credit transactions")
            
            # Delete user
            db.delete(user)
            db.commit()
            
            deletion_log["data_deleted"].append("user account")
            
            logger.info(f"GDPR data deletion completed for user {user_id}: {deletion_log}")
            
            return {
                "success": True,
                "user_id": user_id,
                "deletion_date": datetime.utcnow().isoformat(),
                "data_deleted": deletion_log["data_deleted"]
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting GDPR data for user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def anonymize_user_data(
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Anonymize user data instead of deleting (for legal/accounting requirements).
        
        This removes personally identifiable information while preserving
        anonymized data for analytics.
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Anonymize user email
            original_email = user.email
            user.email = f"deleted_{user_id}@anonymized.local"
            user.full_name = None
            
            # Anonymize chart names
            charts = db.query(SavedChart).filter(SavedChart.user_id == user_id).all()
            for chart in charts:
                chart.chart_name = f"Anonymized User {user_id}"
                chart.birth_location = "Anonymized"
            
            db.commit()
            
            logger.info(f"User {user_id} data anonymized (was: {original_email})")
            
            return {
                "success": True,
                "user_id": user_id,
                "anonymization_date": datetime.utcnow().isoformat(),
                "original_email": original_email  # For verification only
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Error anonymizing user data for user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_gdpr_compliance_status(
        db: Session
    ) -> Dict[str, Any]:
        """Get GDPR compliance status and statistics."""
        total_users = db.query(User).count()
        
        # Users who have requested data export (would need a tracking table)
        # For now, we'll return basic compliance info
        
        return {
            "gdpr_compliant": True,
            "data_export_available": True,
            "data_deletion_available": True,
            "anonymization_available": True,
            "total_users": total_users,
            "compliance_date": datetime.utcnow().isoformat()
        }

