"""
Search Endpoints

Endpoints for advanced search and filtering.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.services.search_service import SearchService
from database import get_db, User
from auth import get_current_user, get_current_user_optional

logger = setup_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# Pydantic Models
class SearchRequest(BaseModel):
    """Schema for search request."""
    query: str
    search_type: Optional[str] = "all"  # all, users, charts, conversations, messages
    filters: Optional[Dict[str, Any]] = None


@router.get("/users", response_model=Dict[str, Any])
async def search_users(
    q: str = Query(..., description="Search query"),
    is_active: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    has_subscription: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Search users with advanced filtering.
    
    Requires admin access.
    """
    try:
        results = SearchService.search_users(
            db=db,
            query=q,
            is_active=is_active,
            is_admin=is_admin,
            has_subscription=has_subscription,
            limit=limit
        )
        
        return {
            "query": q,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error searching users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search users: {str(e)}"
        )


@router.get("/charts", response_model=Dict[str, Any])
async def search_charts(
    q: Optional[str] = Query(None, description="Search query"),
    user_id: Optional[int] = None,
    has_reading: Optional[bool] = None,
    birth_year: Optional[int] = None,
    birth_month: Optional[int] = None,
    location: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Search charts with advanced filtering.
    
    Users can search their own charts, admins can search all charts.
    """
    try:
        # Parse date strings
        created_after_dt = None
        created_before_dt = None
        
        if created_after:
            try:
                created_after_dt = datetime.fromisoformat(created_after.replace('Z', '+00:00'))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid created_after date format")
        
        if created_before:
            try:
                created_before_dt = datetime.fromisoformat(created_before.replace('Z', '+00:00'))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid created_before date format")
        
        # If user is not admin, restrict to their own charts
        if current_user and not current_user.is_admin:
            user_id = current_user.id
        
        results = SearchService.search_charts(
            db=db,
            query=q,
            user_id=user_id,
            has_reading=has_reading,
            birth_year=birth_year,
            birth_month=birth_month,
            location=location,
            created_after=created_after_dt,
            created_before=created_before_dt,
            limit=limit
        )
        
        return {
            "query": q or "",
            "results": results,
            "count": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching charts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search charts: {str(e)}"
        )


@router.get("/conversations", response_model=Dict[str, Any])
async def search_conversations(
    q: Optional[str] = Query(None, description="Search query"),
    user_id: Optional[int] = None,
    chart_id: Optional[int] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Search conversations with filtering.
    
    Users can search their own conversations, admins can search all conversations.
    """
    try:
        # Parse date strings
        created_after_dt = None
        created_before_dt = None
        
        if created_after:
            try:
                created_after_dt = datetime.fromisoformat(created_after.replace('Z', '+00:00'))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid created_after date format")
        
        if created_before:
            try:
                created_before_dt = datetime.fromisoformat(created_before.replace('Z', '+00:00'))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid created_before date format")
        
        # If user is not admin, restrict to their own conversations
        if current_user and not current_user.is_admin:
            user_id = current_user.id
        
        results = SearchService.search_conversations(
            db=db,
            query=q,
            user_id=user_id,
            chart_id=chart_id,
            created_after=created_after_dt,
            created_before=created_before_dt,
            limit=limit
        )
        
        return {
            "query": q or "",
            "results": results,
            "count": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching conversations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search conversations: {str(e)}"
        )


@router.get("/messages", response_model=Dict[str, Any])
async def search_messages(
    q: str = Query(..., description="Search query"),
    conversation_id: Optional[int] = None,
    role: Optional[str] = Query(None, regex="^(user|assistant)$"),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Search messages by content.
    
    Requires admin access.
    """
    try:
        results = SearchService.search_messages(
            db=db,
            query=q,
            conversation_id=conversation_id,
            role=role,
            limit=limit
        )
        
        return {
            "query": q,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error searching messages: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search messages: {str(e)}"
        )


@router.get("/suggestions", response_model=Dict[str, Any])
async def get_search_suggestions(
    q: str = Query(..., min_length=2, description="Search query (minimum 2 characters)"),
    search_type: str = Query("all", regex="^(all|users|charts|conversations)$"),
    current_user: Optional[User] = Depends(get_current_user_optional()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get search suggestions based on partial query.
    
    Public endpoint (no authentication required).
    """
    try:
        suggestions = SearchService.get_search_suggestions(
            db=db,
            query=q,
            search_type=search_type
        )
        
        return {
            "query": q,
            "suggestions": suggestions
        }
    except Exception as e:
        logger.error(f"Error getting search suggestions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get suggestions: {str(e)}"
        )


@router.post("/advanced", response_model=Dict[str, Any])
async def advanced_search(
    request: SearchRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Advanced search with multiple criteria.
    
    Requires admin access.
    """
    try:
        results = {}
        
        if request.search_type in ["all", "users"]:
            filters = request.filters or {}
            results["users"] = SearchService.search_users(
                db=db,
                query=request.query,
                is_active=filters.get("is_active"),
                is_admin=filters.get("is_admin"),
                has_subscription=filters.get("has_subscription"),
                limit=50
            )
        
        if request.search_type in ["all", "charts"]:
            filters = request.filters or {}
            results["charts"] = SearchService.search_charts(
                db=db,
                query=request.query,
                user_id=filters.get("user_id"),
                has_reading=filters.get("has_reading"),
                limit=50
            )
        
        if request.search_type in ["all", "conversations"]:
            filters = request.filters or {}
            results["conversations"] = SearchService.search_conversations(
                db=db,
                query=request.query,
                user_id=filters.get("user_id"),
                chart_id=filters.get("chart_id"),
                limit=50
            )
        
        return {
            "query": request.query,
            "search_type": request.search_type,
            "results": results,
            "total_count": sum(len(v) if isinstance(v, list) else 0 for v in results.values())
        }
    except Exception as e:
        logger.error(f"Error performing advanced search: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to perform search: {str(e)}"
        )

