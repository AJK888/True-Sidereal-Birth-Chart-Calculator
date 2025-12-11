# Credit Tracking System - How 10 Free Chats Are Tracked

## Overview
Free users get **10 free chats** tracked via a credit system. Each chat message costs 1 credit.

## Database Schema

### User Table
- `credits` column (Integer, default=10) - Stores remaining credits
- New users automatically get 10 credits when created (via database default)

### CreditTransaction Table
- Logs all credit changes (deductions and additions)
- Fields: `user_id`, `amount` (negative for deductions), `transaction_type`, `description`, `created_at`
- Used for audit trail and debugging

## Credit Flow

### 1. User Registration
When a new user registers (`/auth/register`):
- User record is created with `credits = 10` (database default)
- No explicit credit assignment needed - handled by database schema

### 2. Chat Message Request
When user sends a chat message (`/api/chat/conversations/{id}/messages`):

**Step 1: Check Access**
```python
has_subscription, reason = check_subscription_access(current_user, db, admin_secret)
has_credits = check_credits(current_user, CHAT_CREDIT_COST)  # Checks if credits >= 1
```

**Step 2: Allow or Deny**
- If `has_subscription` OR `has_credits` → Allow
- If neither → Return 402 error with upgrade message

**Step 3: Deduct Credits (if free user)**
```python
if not has_subscription:
    credits_remaining = deduct_credits(db, current_user, CHAT_CREDIT_COST, description)
    credits_charged = CHAT_CREDIT_COST
```

### 3. Credit Deduction Process
The `deduct_credits()` function:
1. Checks if user has enough credits (`user.credits >= amount`)
2. If insufficient → Raises HTTPException 402
3. Deducts credits: `user.credits -= amount`
4. Creates `CreditTransaction` record for audit trail
5. Commits transaction to database
6. Returns remaining credits

## Important Notes

### Credit Check Timing
- Credits are checked **before** processing the message
- Credits are deducted **after** generating the AI response (but before saving)
- This ensures users can't send messages if they don't have credits

### Subscription Users
- Users with active subscription (`has_active_subscription() == True`) don't use credits
- Credits are only deducted for free users
- Subscription check happens first, so subscription users bypass credit system entirely

### Credit Refresh
- After `deduct_credits()` commits, the `current_user` object in memory still has the old credit value
- The returned `credits_remaining` value is fresh from the database
- Frontend should use `credits_remaining` from the API response, not cached values

## Tracking Methods

### Method 1: Database Column (Primary)
- `users.credits` column is the source of truth
- Updated atomically via `deduct_credits()` function
- Default value ensures new users get 10 credits

### Method 2: Transaction Log (Audit Trail)
- `credit_transactions` table logs every credit change
- Can calculate total credits used: `SUM(amount WHERE amount < 0)`
- Useful for debugging and analytics

### Method 3: API Endpoint
- `/api/chat/credits` endpoint returns current credit balance
- Frontend can check credits before sending messages

## Potential Issues & Solutions

### Issue: Stale Credit Values
**Problem**: If user object isn't refreshed, `current_user.credits` might be stale.

**Solution**: Always use the value returned from `deduct_credits()` or refresh the user object:
```python
db.refresh(current_user)  # Refresh from database
```

### Issue: Race Conditions
**Problem**: Multiple simultaneous requests could deduct credits incorrectly.

**Solution**: Database transactions ensure atomicity. The `deduct_credits()` function:
- Checks credits
- Deducts credits
- Commits transaction
All in one atomic operation.

### Issue: Migration Scripts
**Problem**: Old migration scripts might have `DEFAULT 3` instead of `DEFAULT 10`.

**Solution**: Update migration scripts to use `DEFAULT 10` for new users.

## Testing Credit Tracking

To verify credits are working:
1. Create a new user → Should have 10 credits
2. Send 10 chat messages → Should work
3. Send 11th chat message → Should get 402 error
4. Check `credit_transactions` table → Should have 10 records with `amount = -1`
5. Check `users.credits` → Should be 0

## Frontend Integration

The frontend receives:
- `credits_remaining` in chat response (if free user)
- `credits_remaining: null` for subscription users
- Can call `/api/chat/credits` to check balance anytime

