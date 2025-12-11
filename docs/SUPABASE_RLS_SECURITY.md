# Supabase Row Level Security (RLS) Guide

## Current Setup

Your application uses **SQLAlchemy with direct PostgreSQL connections** (not Supabase client SDK). This means:

- ✅ **RLS policies don't affect your backend API** - Your FastAPI app connects directly with the database password
- ✅ **You can keep tables unrestricted** - Since all access goes through your backend API
- ⚠️ **But you should still secure them** - For defense in depth and future-proofing

## Recommendation: Enable RLS but Keep Backend Access

### Option 1: Keep Unrestricted (Current - Works Fine)

**When to use:**
- You're only accessing the database through your backend API
- You're not using Supabase client SDK in your frontend
- You want the simplest setup

**Security:**
- Your backend API handles all authentication/authorization
- Database password is kept secret in environment variables
- Users can't directly access the database

**Action:** Keep tables unrestricted ✅

### Option 2: Enable RLS with Service Role Bypass (Recommended for Production)

**When to use:**
- You want defense in depth
- You might add Supabase client SDK later
- You want to follow security best practices

**How it works:**
- Enable RLS on all tables
- Your backend uses the **service_role** key (bypasses RLS)
- Frontend/client access would be restricted by RLS policies

**Action:** Enable RLS, but your backend will still work because it uses service_role

## Table-by-Table Security Recommendations

### 🔒 **Sensitive Tables (Enable RLS)**

#### `users`
- **Sensitive data:** Passwords, emails, Stripe IDs, subscription info
- **RLS Policy:** Only service_role can access
- **Action:** Enable RLS, create policy for service_role

#### `saved_charts`
- **Sensitive data:** User birth data, personal charts
- **RLS Policy:** Users can only access their own charts (if using Supabase client)
- **Action:** Enable RLS, but backend uses service_role so it still works

#### `chat_conversations` & `chat_messages`
- **Sensitive data:** Private conversations
- **RLS Policy:** Users can only access their own conversations
- **Action:** Enable RLS

#### `credit_transactions` & `subscription_payments`
- **Sensitive data:** Payment information
- **RLS Policy:** Only service_role can access
- **Action:** Enable RLS

#### `admin_bypass_logs`
- **Sensitive data:** Admin access logs
- **RLS Policy:** Only service_role can access
- **Action:** Enable RLS

### 🌐 **Public Tables (Can Stay Unrestricted)**

#### `famous_people`
- **Data:** Public information (Wikipedia data)
- **Access:** Read-only for matching
- **Action:** Can stay unrestricted, or enable RLS with public read access

## Implementation Steps

### Step 1: Enable RLS on Sensitive Tables

Run this SQL in Supabase SQL Editor:

```sql
-- Enable RLS on all user-related tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_charts ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_bypass_logs ENABLE ROW LEVEL SECURITY;

-- Optional: Enable RLS on famous_people (public read)
ALTER TABLE famous_people ENABLE ROW LEVEL SECURITY;
```

### Step 2: Create Policies for Service Role

Since your backend uses the service_role (via connection string), create policies that allow service_role access:

```sql
-- Policy: Service role can do everything
CREATE POLICY "Service role full access" ON users
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access" ON saved_charts
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access" ON chat_conversations
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access" ON chat_messages
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access" ON credit_transactions
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access" ON subscription_payments
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access" ON admin_bypass_logs
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Famous people: Public read access
CREATE POLICY "Public read access" ON famous_people
    FOR SELECT
    USING (true);
```

### Step 3: Verify Your Connection String

Make sure your `DATABASE_URL` uses the **service_role** key (not anon key):

```bash
# Service role (bypasses RLS) - ✅ Use this
postgresql://postgres.nfglgzrfpmtsowwacmwz:[PASSWORD]@aws-1-us-east-1.pooler.supabase.com:6543/postgres

# Anon key (subject to RLS) - ❌ Don't use this for backend
postgresql://postgres.nfglgzrfpmtsowwacmwz:[ANON_KEY]@...
```

## Important Notes

### ✅ Your Backend Will Still Work

- Your FastAPI app uses SQLAlchemy with direct PostgreSQL connection
- Connection string uses service_role (bypasses RLS)
- All your `db.query()`, `db.add()`, `db.commit()` calls work the same
- **No code changes needed!**

### 🔒 Security Benefits

1. **Defense in depth:** Even if someone gets database credentials, RLS provides an extra layer
2. **Future-proof:** If you add Supabase client SDK later, RLS is already configured
3. **Compliance:** Shows you're following security best practices
4. **Audit trail:** RLS policies are logged and auditable

### ⚠️ What RLS Doesn't Protect Against

- Direct database password leaks (use environment variables!)
- SQL injection (use parameterized queries - SQLAlchemy does this)
- Backend API vulnerabilities (secure your API endpoints)

## Recommendation for Your Use Case

**For now:** Keep tables **unrestricted** if:
- ✅ You're comfortable with backend-only access
- ✅ You want the simplest setup
- ✅ You're not planning to use Supabase client SDK

**For production:** Enable RLS if:
- ✅ You want defense in depth
- ✅ You might add frontend direct access later
- ✅ You want to follow security best practices
- ✅ You're handling sensitive payment data (Stripe)

## Quick Decision Guide

```
Do you use Supabase client SDK in frontend?
├─ YES → Enable RLS with user-specific policies
└─ NO → Do you want extra security layer?
    ├─ YES → Enable RLS with service_role policies
    └─ NO → Keep unrestricted (current setup)
```

## Testing After Enabling RLS

1. **Test your backend API** - Should work exactly the same
2. **Test database scripts** - Migration/maintenance scripts should still work
3. **Check Supabase dashboard** - You should still be able to view data (using service_role)

## Summary

**Current Status:** Unrestricted tables work fine for your setup ✅

**Recommendation:** 
- **Keep unrestricted** for now if you want simplicity
- **Enable RLS** if you want extra security and best practices

Either way, your backend API will work the same because it uses service_role connection!

