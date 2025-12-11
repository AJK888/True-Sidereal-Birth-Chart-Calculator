# Frontend User Identification - How the Website Identifies User ID

## Overview
The frontend doesn't directly extract the user ID from the JWT token. Instead, it stores the **full user object** (including ID) returned from the API after login/registration.

## Authentication Flow

### 1. Login/Registration Response
When user logs in or registers, the API returns:
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
        "id": 42,
        "email": "user@example.com",
        "full_name": "John Doe",
        "created_at": "2025-01-01T00:00:00",
        "is_active": true
    }
}
```

### 2. Frontend Storage
The frontend stores **both** the token and the user object:

```javascript
// In auth.js
saveAuthState(token, user) {
    this.authToken = token;
    this.currentUser = user;  // Full user object with ID
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_user', JSON.stringify(user));  // User object stored
}
```

### 3. User Object Structure
The stored user object contains:
```javascript
{
    id: 42,                    // User ID - available directly!
    email: "user@example.com",
    full_name: "John Doe",
    created_at: "2025-01-01T00:00:00",
    is_active: true
}
```

### 4. Accessing User ID
The frontend accesses the user ID directly from the stored user object:
```javascript
// User ID is available as:
AuthManager.currentUser.id  // e.g., 42

// Or from localStorage:
const user = JSON.parse(localStorage.getItem('auth_user'));
const userId = user.id;  // e.g., 42
```

## How It Works

### On Page Load
```javascript
loadAuthState() {
    const token = localStorage.getItem('auth_token');
    const user = localStorage.getItem('auth_user');  // Get stored user object
    
    if (token && user) {
        this.authToken = token;
        this.currentUser = JSON.parse(user);  // Parse user object (includes ID)
        // Now AuthManager.currentUser.id is available
    }
}
```

### Making API Requests
The frontend sends the JWT token (not the user ID) in the Authorization header:
```javascript
getAuthHeaders() {
    if (!this.authToken) return {};
    return {
        'Authorization': `Bearer ${this.authToken}`  // Token, not user ID
    };
}
```

The backend extracts the user ID from the token, not from the request body.

## Why Store User Object?

### Advantages:
1. **No Token Parsing**: Frontend doesn't need to decode JWT tokens
2. **Immediate Access**: User ID available without API call
3. **Display Info**: Can show user name, email without fetching
4. **Simple**: Direct property access (`user.id`)

### Token Still Used:
- **API Authentication**: Token sent in Authorization header
- **Backend Validation**: Backend decodes token to verify user
- **Security**: Token signature prevents tampering

## Example Usage

### Getting User ID
```javascript
// Check if logged in
if (AuthManager.isLoggedIn()) {
    const userId = AuthManager.currentUser.id;  // e.g., 42
    console.log(`User ID: ${userId}`);
}
```

### Displaying User Info
```javascript
// Show user email
const userEmail = AuthManager.currentUser.email;

// Show user name
const userName = AuthManager.currentUser.full_name || AuthManager.currentUser.email;
```

### Making Authenticated Requests
```javascript
// API automatically gets user ID from token on backend
fetch(`${API_BASE}/api/chat/conversations`, {
    headers: AuthManager.getAuthHeaders()  // Sends token, backend extracts ID
});
```

## Token Verification

The frontend verifies the token is still valid:
```javascript
async verifyToken() {
    const response = await fetch(`${this.API_BASE}/auth/me`, {
        headers: this.getAuthHeaders()  // Sends token
    });
    
    if (response.status === 401) {
        this.logout();  // Token expired, logout user
    }
}
```

The `/auth/me` endpoint returns the current user object (including ID) based on the token.

## Summary

**Frontend User ID Identification:**
1. **Stored**: User object (with ID) stored in `localStorage` as `auth_user`
2. **Accessed**: `AuthManager.currentUser.id` or `JSON.parse(localStorage.getItem('auth_user')).id`
3. **Source**: User object returned from `/auth/login` or `/auth/register` API response
4. **Not Extracted**: Frontend doesn't decode JWT token to get ID (backend does that)

**API Requests:**
- Frontend sends: JWT token in `Authorization: Bearer <token>` header
- Backend extracts: User ID from token's `sub` claim
- Backend uses: User ID to look up user and check credits/subscription

The frontend has the user ID available immediately from the stored user object, while the backend validates and extracts it from the JWT token for security.

