"""
Chart Results API Routes

Combined endpoints for getting complete chart results including:
- Chart data
- Famous matches
- Chat session creation
"""

import logging
import hashlib
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.exceptions import NotFoundError
from database import get_db, User, SavedChart, ChatConversation, ChatMessage
from auth import get_current_user_optional
from app.services.chart_service import generate_chart_hash
from services.similarity_service import find_similar_famous_people_internal

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["chart-results"])


class FullResultsRequest(BaseModel):
    """Request model for full chart results."""
    chart_hash: str = Field(..., description="Chart hash to get results for")
    include_matches: bool = Field(True, description="Include famous people matches")
    include_chat_session: bool = Field(True, description="Create anonymous chat session")


@router.post(
    "/charts/full-results",
    summary="Get Complete Chart Results",
    description="""
    Get complete chart results including chart data, famous matches, and chat session.
    
    This endpoint provides everything needed for a single-page results experience.
    
    **Rate Limit**: 100 requests per day per IP address
    """,
    response_description="Complete chart results",
    tags=["chart-results"]
)
async def get_full_results_endpoint(
    request: Request,
    data: FullResultsRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get complete chart results for a single-page experience.
    """
    try:
        # Find chart by hash (could be in saved_charts or need to reconstruct)
        # For now, we'll need the chart data - this endpoint assumes chart was already calculated
        # In a real implementation, you might cache chart data by hash
        
        # Try to find saved chart
        saved_chart = db.query(SavedChart).filter(
            SavedChart.chart_data_json.contains(f'"chart_hash":"{data.chart_hash}"')
        ).first()
        
        if not saved_chart:
            raise NotFoundError(
                detail="Chart not found",
                resource_type="chart",
                resource_id=data.chart_hash
            )
        
        # Parse chart data
        chart_data = json.loads(saved_chart.chart_data_json)
        
        results = {
            "status": "success",
            "chart_hash": data.chart_hash,
            "chart_data": chart_data
        }
        
        # Include famous matches if requested
        if data.include_matches:
            try:
                # Get famous matches
                matches_result = await find_similar_famous_people_internal(chart_data, limit=10, db=db)
                results["famous_matches"] = matches_result.get("matches", [])
            except Exception as e:
                logger.warning(f"Failed to get famous matches: {e}")
                results["famous_matches"] = []
        
        # Create anonymous chat session if requested
        if data.include_chat_session:
            try:
                # Create or get chat session for chart hash
                chat_session = await create_anonymous_chat_session(
                    data.chart_hash,
                    saved_chart.id if saved_chart else None,
                    current_user,
                    db
                )
                results["chat_session"] = chat_session
            except Exception as e:
                logger.warning(f"Failed to create chat session: {e}")
                results["chat_session"] = None
        
        return results
    
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error getting full results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get full results: {str(e)}")


async def create_anonymous_chat_session(
    chart_hash: str,
    chart_id: Optional[int],
    current_user: Optional[User],
    db: Session
) -> Dict[str, Any]:
    """
    Create an anonymous chat session for a chart hash.
    
    Note: Full anonymous support requires database migration to make user_id and chart_id nullable.
    For now, this works for logged-in users. Anonymous users get a session ID that can be
    used with a future implementation.
    
    Args:
        chart_hash: Chart hash identifier
        chart_id: Optional saved chart ID
        current_user: Optional current user
        db: Database session
    
    Returns:
        Chat session information
    """
    # If user is logged in and has a saved chart, create conversation
    if current_user and chart_id:
        # Check if conversation already exists
        existing = db.query(ChatConversation).filter(
            ChatConversation.user_id == current_user.id,
            ChatConversation.chart_id == chart_id
        ).first()
        
        if existing:
            return {
                "conversation_id": existing.id,
                "is_anonymous": False,
                "message_limit": None,
                "requires_signup": False
            }
        
        # Create new conversation for logged-in user
        conversation = ChatConversation(
            user_id=current_user.id,
            chart_id=chart_id,
            title="New Conversation"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        return {
            "conversation_id": conversation.id,
            "is_anonymous": False,
            "message_limit": None,
            "requires_signup": False
        }
    
    # For anonymous users, return session info
    # TODO: Full anonymous support requires:
    # 1. Database migration to make user_id and chart_id nullable in ChatConversation
    # 2. Add chart_hash column to ChatConversation
    # 3. Store chart_data_json for anonymous sessions
    # For now, return a session identifier that frontend can use
    session_id = f"anon_{chart_hash}"
    
    return {
        "session_id": session_id,
        "is_anonymous": True,
        "message_limit": 10,  # 10 free messages for anonymous users
        "messages_used": 0,
        "requires_signup": True,  # Prompt user to sign up for full chat access
        "note": "Anonymous chat sessions require database migration for full support"
    }

