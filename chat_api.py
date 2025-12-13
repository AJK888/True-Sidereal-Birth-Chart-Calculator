"""
Chat API for Synthesis Astrology

Handles:
- Chat conversations about saved charts
- Message history retrieval
- Admin access to all conversations
- Credit deduction for chat usage
"""

import os
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db, User, SavedChart, ChatConversation, ChatMessage, CreditTransaction, AdminBypassLog
from auth import get_current_user, get_current_user_optional
from subscription import check_subscription_access
from fastapi import Request

logger = logging.getLogger(__name__)

# Create router for chat endpoints
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Admin email (use existing ADMIN_EMAIL env var)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

# Credit cost per chat message
CHAT_CREDIT_COST = 1


# ============================================================================
# Pydantic Models
# ============================================================================

class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    content: str


class MessageResponse(BaseModel):
    """Schema for message response."""
    id: int
    role: str
    content: str
    created_at: datetime
    tokens_used: Optional[int] = None
    credits_charged: Optional[int] = None

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""
    chart_id: int
    title: Optional[str] = "New Conversation"


class ConversationResponse(BaseModel):
    """Schema for conversation response."""
    id: int
    chart_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    """Schema for conversation with messages."""
    id: int
    chart_id: int
    chart_name: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True


class AdminConversationResponse(BaseModel):
    """Schema for admin view of conversations."""
    id: int
    user_id: int
    user_email: str
    user_name: Optional[str]
    chart_id: int
    chart_name: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    messages: Optional[List[MessageResponse]] = None

    class Config:
        from_attributes = True


class ChatSendRequest(BaseModel):
    """Schema for sending a chat message."""
    message: str


class ChatSendResponse(BaseModel):
    """Schema for chat response."""
    user_message: MessageResponse
    assistant_message: MessageResponse
    credits_remaining: Optional[int] = None  # None for subscription users


# ============================================================================
# Helper Functions
# ============================================================================

def is_admin(user: User) -> bool:
    """Check if user is an admin."""
    return user.is_admin or (ADMIN_EMAIL and user.email == ADMIN_EMAIL)


def check_credits(user: User, required: int = CHAT_CREDIT_COST) -> bool:
    """Check if user has enough credits."""
    return user.credits >= required


def deduct_credits(db: Session, user: User, amount: int, description: str) -> int:
    """Deduct credits from user and log transaction."""
    if user.credits < amount:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Insufficient credits",
                "required": amount,
                "available": user.credits
            }
        )
    
    user.credits -= amount
    
    transaction = CreditTransaction(
        user_id=user.id,
        amount=-amount,
        transaction_type="chat",
        description=description
    )
    db.add(transaction)
    db.commit()
    
    return user.credits


# ============================================================================
# User Endpoints
# ============================================================================

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_user_conversations(
    chart_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for the current user, optionally filtered by chart."""
    query = db.query(ChatConversation).filter(ChatConversation.user_id == current_user.id)
    
    if chart_id:
        query = query.filter(ChatConversation.chart_id == chart_id)
    
    conversations = query.order_by(desc(ChatConversation.updated_at)).all()
    
    result = []
    for conv in conversations:
        result.append(ConversationResponse(
            id=conv.id,
            chart_id=conv.chart_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages)
        ))
    
    return result


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new conversation for a chart."""
    # Verify user owns the chart
    chart = db.query(SavedChart).filter(
        SavedChart.id == data.chart_id,
        SavedChart.user_id == current_user.id
    ).first()
    
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    
    conversation = ChatConversation(
        user_id=current_user.id,
        chart_id=data.chart_id,
        title=data.title or f"Chat about {chart.chart_name}"
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return ConversationResponse(
        id=conversation.id,
        chart_id=conversation.chart_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a conversation with all its messages."""
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = [MessageResponse(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at,
        tokens_used=msg.tokens_used,
        credits_charged=msg.credits_charged
    ) for msg in sorted(conversation.messages, key=lambda m: m.created_at)]
    
    return ConversationDetailResponse(
        id=conversation.id,
        chart_id=conversation.chart_id,
        chart_name=conversation.chart.chart_name,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=messages
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ChatSendResponse)
async def send_message(
    conversation_id: int,
    data: ChatSendRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message in a conversation and get AI response. Requires subscription OR credits (10 free chats)."""
    # Get conversation
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check access: subscription OR credits (with admin bypass support)
    # Refresh user to ensure we have latest credit balance
    db.refresh(current_user)
    
    # Check both query params and headers (case-insensitive)
    friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
    if not friends_and_family_key:
        # Check headers (case-insensitive)
        for header_name, header_value in request.headers.items():
            if header_name.lower() == "x-friends-and-family-key":
                friends_and_family_key = header_value
                break
    has_subscription, reason = check_subscription_access(current_user, db, friends_and_family_key)
    has_credits = check_credits(current_user, CHAT_CREDIT_COST)
    
    # Allow if user has subscription OR has credits
    if not has_subscription and not has_credits:
        # Log admin bypass attempt if secret was provided but invalid
        if friends_and_family_key:
            try:
                log_entry = AdminBypassLog(
                    user_email=current_user.email,
                    endpoint="/api/chat/conversations/{conversation_id}/messages",
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    details=f"Invalid admin secret attempt for chat"
                )
                db.add(log_entry)
                db.commit()
            except Exception as log_error:
                # Handle sequence sync issues gracefully
                error_str = str(log_error)
                if "UniqueViolation" in error_str and "admin_bypass_logs_pkey" in error_str:
                    logger.warning(f"Admin bypass log sequence out of sync. Run fix_admin_logs_sequence.py to resolve. Error: {log_error}")
                    try:
                        db.rollback()
                    except:
                        pass
                else:
                    logger.warning(f"Could not log admin bypass attempt: {log_error}")
        
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Chat access required",
                "message": f"You've used all {current_user.credits} free chats. Purchase a full reading for $28 to get unlimited chats for a month, or subscribe for $8/month.",
                "credits_remaining": current_user.credits,
                "reason": reason
            }
        )
    
    # Log successful admin bypass if used
    if reason == "admin_bypass":
        try:
            log_entry = AdminBypassLog(
                user_email=current_user.email,
                endpoint="/api/chat/conversations/{conversation_id}/messages",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                details=f"Admin bypass used for chat"
            )
            db.add(log_entry)
            db.commit()
        except Exception as log_error:
            # Handle sequence sync issues gracefully
            error_str = str(log_error)
            if "UniqueViolation" in error_str and "admin_bypass_logs_pkey" in error_str:
                logger.warning(f"Admin bypass log sequence out of sync. Run fix_admin_logs_sequence.py to resolve. Error: {log_error}")
                try:
                    db.rollback()
                except:
                    pass
            else:
                logger.warning(f"Could not log admin bypass: {log_error}")
    
    # Save user message
    user_message = ChatMessage(
        conversation_id=conversation_id,
        role="user",
        content=data.message,
        credits_charged=0  # User messages don't cost credits
    )
    db.add(user_message)
    
    # TODO: Generate AI response using chart context
    # For now, placeholder response
    ai_response_content = await generate_chat_response(
        conversation=conversation,
        user_message=data.message,
        db=db
    )
    
    # Deduct credits if user doesn't have subscription (free users use credits)
    # Skip credit deduction for FRIENDS_AND_FAMILY_KEY users
    credits_charged = 0
    credits_remaining = None
    
    if not has_subscription and reason != "admin_bypass":
        # Free user - deduct credits (but not for FRIENDS_AND_FAMILY_KEY users)
        credits_remaining = deduct_credits(db, current_user, CHAT_CREDIT_COST, f"Chat message in conversation {conversation_id}")
        credits_charged = CHAT_CREDIT_COST
    
    # Save assistant message
    assistant_message = ChatMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=ai_response_content,
        credits_charged=credits_charged
    )
    db.add(assistant_message)
    
    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    
    logger.info(f"User {current_user.id} sent message in conversation {conversation_id} (credits charged: {credits_charged})")
    
    return ChatSendResponse(
        user_message=MessageResponse(
            id=user_message.id,
            role=user_message.role,
            content=user_message.content,
            created_at=user_message.created_at,
            tokens_used=user_message.tokens_used,
            credits_charged=0  # User messages don't cost credits
        ),
        assistant_message=MessageResponse(
            id=assistant_message.id,
            role=assistant_message.role,
            content=assistant_message.content,
            created_at=assistant_message.created_at,
            tokens_used=assistant_message.tokens_used,
            credits_charged=credits_charged
        ),
        credits_remaining=credits_remaining
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation."""
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)
    db.commit()
    
    return {"message": "Conversation deleted"}


@router.patch("/conversations/{conversation_id}")
async def update_conversation_title(
    conversation_id: int,
    title: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update conversation title."""
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation.title = title
    db.commit()
    
    return {"message": "Title updated", "title": title}


# ============================================================================
# Admin Endpoints
# ============================================================================

@router.get("/admin/conversations", response_model=List[AdminConversationResponse])
async def admin_get_all_conversations(
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    include_messages: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [ADMIN ONLY] Get all conversations across all users.
    Can filter by user_id or user_email.
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = db.query(ChatConversation).join(User).join(SavedChart)
    
    if user_id:
        query = query.filter(ChatConversation.user_id == user_id)
    if user_email:
        query = query.filter(User.email.ilike(f"%{user_email}%"))
    
    total = query.count()
    conversations = query.order_by(desc(ChatConversation.updated_at)).offset(offset).limit(limit).all()
    
    result = []
    for conv in conversations:
        messages = None
        if include_messages:
            messages = [MessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                tokens_used=msg.tokens_used,
                credits_charged=msg.credits_charged
            ) for msg in sorted(conv.messages, key=lambda m: m.created_at)]
        
        result.append(AdminConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            user_email=conv.owner.email,
            user_name=conv.owner.full_name,
            chart_id=conv.chart_id,
            chart_name=conv.chart.chart_name,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages),
            messages=messages
        ))
    
    logger.info(f"Admin {current_user.email} accessed conversations (total: {total})")
    
    return result


@router.get("/admin/conversations/{conversation_id}", response_model=AdminConversationResponse)
async def admin_get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """[ADMIN ONLY] Get a specific conversation with all messages."""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = [MessageResponse(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at,
        tokens_used=msg.tokens_used,
        credits_charged=msg.credits_charged
    ) for msg in sorted(conversation.messages, key=lambda m: m.created_at)]
    
    logger.info(f"Admin {current_user.email} viewed conversation {conversation_id}")
    
    return AdminConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        user_email=conversation.owner.email,
        user_name=conversation.owner.full_name,
        chart_id=conversation.chart_id,
        chart_name=conversation.chart.chart_name,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        messages=messages
    )


@router.get("/admin/stats")
async def admin_get_chat_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """[ADMIN ONLY] Get chat usage statistics."""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total_conversations = db.query(ChatConversation).count()
    total_messages = db.query(ChatMessage).count()
    total_users_with_chats = db.query(ChatConversation.user_id).distinct().count()
    
    # Messages in last 24 hours
    from datetime import timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    messages_24h = db.query(ChatMessage).filter(ChatMessage.created_at >= yesterday).count()
    
    # Total credits used on chat
    total_chat_credits = db.query(CreditTransaction).filter(
        CreditTransaction.transaction_type == "chat"
    ).count()
    
    return {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_users_with_chats": total_users_with_chats,
        "messages_last_24h": messages_24h,
        "total_chat_credits_used": total_chat_credits
    }


# ============================================================================
# AI Response Generation (placeholder - implement with your LLM)
# ============================================================================

async def generate_chat_response(
    conversation: ChatConversation,
    user_message: str,
    db: Session
) -> str:
    """
    Generate AI response based on chart context and conversation history.
    
    TODO: Implement with Gemini API
    """
    # Get chart data
    chart = conversation.chart
    chart_name = chart.chart_name
    
    # Get conversation history (last 10 messages for context)
    recent_messages = sorted(conversation.messages, key=lambda m: m.created_at)[-10:]
    
    # TODO: Build prompt with:
    # 1. Chart data (from chart.chart_data_json)
    # 2. AI reading (from chart.ai_reading)
    # 3. Conversation history
    # 4. User's new question
    
    # Placeholder response
    return f"""Thank you for your question about {chart_name}'s chart!

[This is a placeholder response. The actual AI integration will provide personalized insights based on the chart data and your specific question.]

Your question: "{user_message}"

To implement:
1. Parse chart_data_json for relevant placements
2. Reference the AI reading for context
3. Generate response using Gemini with chart-specific system prompt
"""


# ============================================================================
# Credits Endpoint
# ============================================================================

@router.get("/credits")
async def get_user_credits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's credit balance and transaction history."""
    transactions = db.query(CreditTransaction).filter(
        CreditTransaction.user_id == current_user.id
    ).order_by(desc(CreditTransaction.created_at)).limit(20).all()
    
    return {
        "credits": current_user.credits,
        "chat_cost": CHAT_CREDIT_COST,
        "recent_transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "type": t.transaction_type,
                "description": t.description,
                "created_at": t.created_at
            }
            for t in transactions
        ]
    }

