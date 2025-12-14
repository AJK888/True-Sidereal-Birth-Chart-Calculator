# Backend Implementation Guide - Single Page Results Experience

## Overview

This guide outlines the backend changes needed to support the new single-page results experience where users see their chart, free reading, famous matches, and chatbot all on one page after clicking "Generate Chart".

---

## Required Backend Changes

### 1. Enhance `/calculate_chart` Endpoint

**Current Behavior:**
- Returns chart data + snapshot reading
- User must separately call famous matches API
- Chat requires saved chart + user account

**Proposed Enhancement:**

Add optional parameter to include famous matches automatically:

```python
@app.post("/calculate_chart")
@limiter.limit("50/day")
async def calculate_chart_endpoint(
    request: Request, 
    data: ChartRequest,
    include_matches: bool = Query(default=False)  # New parameter
):
    # ... existing chart calculation code ...
    
    full_response = chart.get_full_chart_data(...)
    
    # Optionally auto-fetch famous matches
    if include_matches:
        try:
            # Call internal function to find matches
            matches = await find_similar_famous_people_internal(
                chart_data=full_response,
                limit=10,
                db=db  # Need to pass db session
            )
            full_response["famous_matches"] = matches
            logger.info(f"Included {len(matches)} famous matches in chart response")
        except Exception as e:
            logger.warning(f"Could not fetch famous matches: {e}")
            full_response["famous_matches"] = []
    
    return full_response
```

**Note:** This requires extracting the matching logic into a reusable function.

---

### 2. Create Internal Famous Matches Function

Extract the matching logic from `/api/find-similar-famous-people` into a reusable function:

```python
async def find_similar_famous_people_internal(
    chart_data: Dict[str, Any],
    limit: int = 10,
    db: Session = None
) -> List[Dict[str, Any]]:
    """
    Internal function to find similar famous people.
    Can be called from other endpoints.
    """
    # Extract the logic from find_similar_famous_people_endpoint
    # Return list of matches in same format
    pass
```

---

### 3. Chart Hash-Based Chat Sessions

**Current Issue:** Chat requires:
- User must be logged in
- Chart must be saved first
- User creates conversation manually

**Solution:** Support temporary chat sessions using `chart_hash`

#### Option A: Modify Chat API to Accept Chart Hash

```python
# In chat_api.py

class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""
    chart_id: Optional[int] = None  # Make optional
    chart_hash: Optional[str] = None  # New: for temporary sessions
    title: Optional[str] = "New Conversation"

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),  # Make optional
    db: Session = Depends(get_db)
):
    """Create a new conversation for a chart or chart_hash."""
    
    # If chart_hash provided, create temporary session
    if data.chart_hash:
        # Check if temporary session already exists
        existing = db.query(ChatConversation).filter(
            ChatConversation.chart_hash == data.chart_hash,
            ChatConversation.user_id == None  # Anonymous session
        ).first()
        
        if existing:
            return ConversationResponse(...)
        
        # Create new temporary session
        conversation = ChatConversation(
            user_id=None,  # Anonymous
            chart_id=None,
            chart_hash=data.chart_hash,
            chart_data_json=json.dumps(chart_data),  # Store chart data
            title=data.title or "Chat about your chart"
        )
        db.add(conversation)
        db.commit()
        return ConversationResponse(...)
    
    # Existing logic for chart_id...
```

**Database Schema Change Needed:**

```python
# In database.py, modify ChatConversation model:

class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Make nullable
    chart_id = Column(Integer, ForeignKey("saved_charts.id"), nullable=True)  # Make nullable
    chart_hash = Column(String, nullable=True, index=True)  # New field
    chart_data_json = Column(JSON, nullable=True)  # Store chart data for temp sessions
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### Option B: Session-Based Temporary Conversations

Store temporary conversations in session/cookie instead of database:

```python
# Use FastAPI sessions or Redis
from fastapi_sessions import SessionMiddleware, SessionStorage

# Store temporary conversations in session
# Migrate to database when user signs up
```

**Recommendation:** Option A is better for persistence and analytics.

---

### 4. Auto-Create Chat Session Endpoint

Create endpoint that frontend can call after chart generation:

```python
@router.post("/conversations/auto-create", response_model=ConversationResponse)
async def auto_create_conversation(
    data: Dict[str, Any],  # Contains chart_data and chart_hash
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Automatically create a chat conversation for a newly generated chart.
    Works for both logged-in and anonymous users.
    """
    chart_hash = data.get("chart_hash")
    chart_data = data.get("chart_data")
    
    if not chart_hash:
        raise HTTPException(status_code=400, detail="chart_hash required")
    
    # Check if conversation already exists
    query = db.query(ChatConversation).filter(
        ChatConversation.chart_hash == chart_hash
    )
    
    if current_user:
        query = query.filter(ChatConversation.user_id == current_user.id)
    else:
        query = query.filter(ChatConversation.user_id == None)
    
    existing = query.first()
    
    if existing:
        return ConversationResponse(...)
    
    # Create new conversation
    conversation = ChatConversation(
        user_id=current_user.id if current_user else None,
        chart_id=None,  # Will be set if user saves chart later
        chart_hash=chart_hash,
        chart_data_json=json.dumps(chart_data) if chart_data else None,
        title="Chat about your chart"
    )
    db.add(conversation)
    db.commit()
    
    return ConversationResponse(...)
```

---

### 5. Modify Chat Message Endpoint to Support Chart Hash

Update the send message endpoint to work with chart_hash-based conversations:

```python
@router.post("/conversations/{conversation_id}/messages", response_model=ChatSendResponse)
async def send_message(
    conversation_id: int,
    data: ChatSendRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),  # Make optional
    db: Session = Depends(get_db)
):
    """Send a message in a conversation."""
    
    # Get conversation
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check ownership: user must own it OR it must be anonymous (chart_hash based)
    if conversation.user_id:
        if not current_user or conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        # Anonymous conversation - allow access via session/chart_hash
        # Could check session or IP address
        pass
    
    # Rest of existing logic...
```

---

### 6. Migration Endpoint (When User Signs Up)

When anonymous user signs up, migrate their temporary conversations:

```python
@router.post("/conversations/migrate")
async def migrate_temporary_conversations(
    chart_hashes: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Migrate temporary (anonymous) conversations to user's account.
    Called after user signs up or logs in.
    """
    migrated = []
    
    for chart_hash in chart_hashes:
        # Find anonymous conversations with this chart_hash
        temp_conversations = db.query(ChatConversation).filter(
            ChatConversation.chart_hash == chart_hash,
            ChatConversation.user_id == None
        ).all()
        
        for conv in temp_conversations:
            conv.user_id = current_user.id
            migrated.append(conv.id)
    
    db.commit()
    
    return {
        "migrated_count": len(migrated),
        "conversation_ids": migrated
    }
```

---

## Database Migration Script

Create migration script to add new fields:

```python
# scripts/migration/add_chat_hash_support.py

"""
Migration: Add chart_hash support to chat_conversations table
"""

def upgrade():
    # Add chart_hash column
    # Add chart_data_json column
    # Make user_id nullable
    # Make chart_id nullable
    # Add index on chart_hash
    pass

def downgrade():
    # Remove chart_hash column
    # Remove chart_data_json column
    # Make user_id NOT NULL
    # Make chart_id NOT NULL
    pass
```

SQL Migration:

```sql
-- Add chart_hash support to chat_conversations

ALTER TABLE chat_conversations 
ADD COLUMN chart_hash VARCHAR(255),
ADD COLUMN chart_data_json JSONB;

-- Make user_id and chart_id nullable for anonymous sessions
ALTER TABLE chat_conversations 
ALTER COLUMN user_id DROP NOT NULL,
ALTER COLUMN chart_id DROP NOT NULL;

-- Add index for faster lookups
CREATE INDEX idx_chat_conversations_chart_hash ON chat_conversations(chart_hash);

-- Add index for anonymous sessions
CREATE INDEX idx_chat_conversations_anonymous ON chat_conversations(chart_hash, user_id) 
WHERE user_id IS NULL;
```

---

## API Response Structure

### Enhanced `/calculate_chart` Response

```json
{
  "sidereal_major_positions": [...],
  "snapshot_reading": "Your free reading...",
  "quick_highlights": "...",
  "chart_hash": "abc123...",
  "famous_matches": [  // If include_matches=true
    {
      "id": 123,
      "name": "Famous Person",
      "similarity_score": 0.85,
      "shared_placements": ["Sun in Aries", "Moon in Leo"]
    }
  ]
}
```

### New `/api/chat/conversations/auto-create` Response

```json
{
  "id": 456,
  "chart_id": null,
  "chart_hash": "abc123...",
  "title": "Chat about your chart",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "message_count": 0,
  "requires_signup": false  // true if anonymous and credits exhausted
}
```

---

## Implementation Checklist

### Phase 1: Quick Wins (No DB Changes)
- [ ] Extract famous matches logic into reusable function
- [ ] Add `include_matches` parameter to `/calculate_chart`
- [ ] Test famous matches auto-inclusion

### Phase 2: Chat Hash Support
- [ ] Create database migration script
- [ ] Run migration on database
- [ ] Update `ChatConversation` model in `database.py`
- [ ] Modify `ConversationCreate` schema
- [ ] Update `create_conversation` endpoint
- [ ] Update `send_message` endpoint to support anonymous sessions
- [ ] Create `auto_create_conversation` endpoint
- [ ] Test anonymous chat sessions

### Phase 3: Migration & Cleanup
- [ ] Create migration endpoint for user signup
- [ ] Add cleanup job for expired anonymous sessions
- [ ] Update documentation
- [ ] Test full flow

---

## Testing Strategy

### Test Cases

1. **Anonymous User Flow:**
   - Generate chart → Get chart_hash
   - Auto-create chat session with chart_hash
   - Send messages (should work with credits)
   - Sign up → Migrate conversations

2. **Logged-In User Flow:**
   - Generate chart → Auto-create chat session
   - Send messages (should work with subscription/credits)
   - Save chart → Link conversation to saved chart

3. **Famous Matches:**
   - Generate chart with `include_matches=true`
   - Verify matches included in response
   - Verify matches are relevant

4. **Edge Cases:**
   - Multiple anonymous sessions with same chart_hash
   - Expired anonymous sessions
   - User signs up with existing anonymous sessions

---

## Security Considerations

1. **Anonymous Chat Sessions:**
   - Limit by IP address?
   - Rate limit anonymous sessions more strictly
   - Expire after 24 hours
   - Require email for chat after X messages?

2. **Chart Hash Validation:**
   - Validate chart_hash format
   - Prevent hash collision attacks
   - Rate limit chart_hash creation

3. **Data Privacy:**
   - Clear anonymous sessions after expiration
   - Don't store PII in anonymous sessions
   - Migrate data properly on signup

---

## Performance Considerations

1. **Famous Matches:**
   - Cache matches by chart_hash
   - Use database indexes for faster lookups
   - Consider pagination for large result sets

2. **Chat Sessions:**
   - Index on chart_hash for fast lookups
   - Consider Redis for temporary sessions (future)
   - Cleanup old anonymous sessions regularly

3. **Combined Endpoint:**
   - Consider creating `/api/chart/full-results` endpoint
   - Reduces number of API calls
   - Can optimize database queries

---

## Next Steps

1. **Review this guide** with team
2. **Decide on approach** (chart_hash vs. session-based)
3. **Create database migration** script
4. **Implement Phase 1** (famous matches auto-inclusion)
5. **Implement Phase 2** (chat hash support)
6. **Test thoroughly** before deploying
7. **Update frontend** to use new endpoints

---

## Questions to Answer

1. **Anonymous Chat:**
   - Should anonymous users get 10 free messages?
   - Or require signup immediately?
   - How to prevent abuse?

2. **Session Expiry:**
   - How long should anonymous sessions last?
   - 24 hours? 7 days? Until browser close?

3. **Chart Data Storage:**
   - Store full chart_data_json in conversation?
   - Or just chart_hash and fetch on demand?
   - Size considerations?

4. **Migration Strategy:**
   - Auto-migrate on signup?
   - Or prompt user to migrate?
   - What if user has multiple anonymous sessions?
