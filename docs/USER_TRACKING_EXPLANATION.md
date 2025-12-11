# User Tracking System - How Users Are Identified

## Overview
Users are tracked by their **User ID** (database primary key), not by email. Email is used for login/registration, but the actual tracking uses the numeric user ID.

## Authentication Flow

### 1. Registration/Login
When a user registers or logs in:
```python
# User provides email + password
POST /auth/register or /auth/login
{
    "email": "user@example.com",
    "password": "password123"
}
```

### 2. User Lookup by Email
The system looks up the user by email:
```python
user = get_user_by_email(db, email)  # Finds user by email
```

### 3. JWT Token Creation
A JWT token is created containing:
- `sub` (subject) = **user.id** (the numeric ID, converted to string)
- `email` = user.email (for convenience, but not used for lookup)

```python
access_token = create_access_token(
    data={
        "sub": str(user.id),  # User ID is the primary identifier
        "email": user.email   # Email included but not primary
    }
)
```

### 4. Token Storage
- Frontend stores the JWT token (usually in localStorage or sessionStorage)
- Token is sent with every API request in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

### 5. API Request Authentication
When user makes an API request (e.g., send chat message):

**Step 1: Extract Token**
```python
# FastAPI extracts token from Authorization header
credentials = Depends(security)  # Gets "Bearer <token>"
```

**Step 2: Decode Token**
```python
token_data = decode_token(credentials.credentials)
# Returns: TokenData(user_id=123, email="user@example.com")
```

**Step 3: Lookup User by ID**
```python
user = get_user_by_id(db, token_data.user_id)  # Looks up by ID, not email!
```

**Step 4: Return User Object**
```python
# current_user now has full user object with:
# - id: 123
# - email: "user@example.com"
# - credits: 10
# - subscription_status: "inactive"
# - etc.
```

## Why User ID, Not Email?

### Advantages of Using ID:
1. **Performance**: Integer lookups are faster than string lookups
2. **Stability**: User ID never changes (email can change)
3. **Database Design**: Primary keys are optimized for lookups
4. **Security**: Less sensitive than email in tokens

### Email Usage:
- **Login/Registration**: Email is used to find the user initially
- **Display**: Email is shown in UI and included in JWT for convenience
- **Not Primary Key**: Email is unique but not the primary identifier

## Database Schema

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,           -- Primary key (used for tracking)
    email VARCHAR(255) UNIQUE,       -- Unique but not primary identifier
    hashed_password VARCHAR(255),
    credits INTEGER DEFAULT 10,
    -- ... other fields
);
```

## Credit Tracking by User ID

When tracking credits:
```python
# In chat_api.py
current_user: User = Depends(get_current_user)  # Gets user by ID from token
db.refresh(current_user)  # Refresh to get latest credits
has_credits = check_credits(current_user, 1)  # Check credits for this user ID

# Credits are stored per user ID
user.credits -= 1  # Deducts from user with this ID
```

## Example Flow

1. **User registers**: `email: "alice@example.com"`
   - Database creates user with `id: 42`
   - JWT token created: `{"sub": "42", "email": "alice@example.com"}`

2. **User sends chat message**:
   - Frontend sends: `Authorization: Bearer <token>`
   - Backend decodes token → gets `user_id: 42`
   - Backend queries: `SELECT * FROM users WHERE id = 42`
   - Gets user with `credits: 10`

3. **Credit deduction**:
   - `UPDATE users SET credits = credits - 1 WHERE id = 42`
   - User 42 now has 9 credits

## Security Notes

- **JWT Tokens**: Expire after 7 days (configurable)
- **Token Validation**: Every request validates the token signature
- **User Lookup**: Always by ID from token, never trust email from client
- **Database**: User ID is immutable (never changes)

## Summary

- **Primary Identifier**: User ID (numeric, database primary key)
- **Login Identifier**: Email (used to find user initially)
- **Token Contains**: User ID + Email (ID is what's used)
- **API Requests**: User identified by ID from JWT token
- **Credit Tracking**: Credits stored per user ID, not email

The system uses **User ID** for all tracking and operations. Email is only used for the initial login lookup.

