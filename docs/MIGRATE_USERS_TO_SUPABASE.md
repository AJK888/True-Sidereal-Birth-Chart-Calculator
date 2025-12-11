# Migrate User Data to Supabase

## Recommendation: Use Same Supabase Database ✅

**Best approach:** Use the same Supabase database for both `famous_people` and `users` tables.

### Benefits:
- ✅ Single connection string
- ✅ Lower cost (one database)
- ✅ Easier to manage
- ✅ Can add relationships between tables if needed
- ✅ Standard practice

## Migration Steps

### 1. Get Your Render Database Connection String

1. Go to your Render dashboard
2. Find your PostgreSQL database service
3. Copy the **Internal Database URL** or **Connection String**
   - Format: `postgresql://user:password@host:port/database`

### 2. Run the Migration Script

**Option A: Set environment variable**
```bash
export RENDER_DATABASE_URL="postgresql://user:password@host:port/database"
cd "Synthesis Astrology/True-Sidereal-Birth-Chart"
python scripts/migrate_users_to_supabase.py
```

**Option B: Edit the script directly**
- Open `scripts/migrate_users_to_supabase.py`
- Set `RENDER_DATABASE_URL` on line 11

### 3. What Gets Migrated

The script will:
- Create the `users` table in Supabase (if it doesn't exist)
- Copy all user records from Render to Supabase
- Preserve all user data (passwords, subscriptions, etc.)
- Create indexes for fast queries

### 4. Related Tables

If you have related tables (`saved_charts`, `chat_conversations`, `credit_transactions`), you may want to migrate those too. The script currently only migrates the `users` table.

## After Migration

### Update Your Application

Once migrated, update your `DATABASE_URL` to point to Supabase:

```bash
export DATABASE_URL="postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
```

Your application will then use Supabase for both:
- `famous_people` table
- `users` table
- All other tables

### Verify Migration

```python
from database import SessionLocal, User, FamousPerson

db = SessionLocal()
user_count = db.query(User).count()
famous_count = db.query(FamousPerson).count()
print(f"Users: {user_count}, Famous People: {famous_count}")
db.close()
```

## Alternative: Keep User Data on Render

If you prefer to keep user data on Render:

1. **Keep two database connections:**
   - Render: For user data
   - Supabase: For famous people data

2. **Update your code:**
   - Create separate database sessions for each
   - Use Render for user operations
   - Use Supabase for famous people queries

This works but is more complex to manage.

## Security Note

- User passwords are hashed, so they're safe to migrate
- Stripe customer IDs and subscription data will be preserved
- All sensitive data remains encrypted in transit

## Need Help?

If you encounter issues:
1. Check both database connection strings are correct
2. Verify table schemas match
3. Check for any foreign key constraints that might block migration

