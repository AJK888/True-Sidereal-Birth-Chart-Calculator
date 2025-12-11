# DATABASE_URL Setup Guide

## Your Connection String

```
postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres
```

## Format Breakdown

- **Protocol**: `postgresql://` ✅ (correct)
- **User**: `postgres.nfglgzrfpmtsowwacmwz` ✅ (Supabase user)
- **Password**: `%23SynthesisAstrology1` ✅ (URL-encoded `#SynthesisAstrology1`)
- **Host**: `aws-1-us-east-1.pooler.supabase.com` ✅ (Supabase pooler)
- **Port**: `6543` ✅ (Pooler port)
- **Database**: `postgres` ✅ (Default database)

## Setting the Environment Variable

### Windows (PowerShell)
```powershell
$env:DATABASE_URL="postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
```

### Windows (Command Prompt)
```cmd
set DATABASE_URL=postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres
```

### Linux/Mac (Bash)
```bash
export DATABASE_URL="postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
```

### Render/Production
In your Render dashboard:
1. Go to your service → Environment
2. Add/Update `DATABASE_URL` variable
3. Use the exact string above

## Important Notes

### Password Encoding
- `%23` is URL-encoded `#` character
- This is **correct** for connection strings
- Your password is: `#SynthesisAstrology1`
- The `%23` ensures the `#` doesn't get interpreted as a URL fragment

### Alternative (If URL encoding causes issues)
If you have problems, you can also use:
```
postgresql://postgres.nfglgzrfpmtsowwacmwz:#SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres
```

But `%23` is the safer, more standard approach.

### Verification

Your `database.py` will automatically:
1. ✅ Handle `postgres://` → `postgresql://` conversion (if needed)
2. ✅ Use connection pooling settings
3. ✅ Work with SQLAlchemy

## Testing the Connection

You can test if it works by running:

```python
from database import SessionLocal, FamousPerson, User

db = SessionLocal()
try:
    # Test famous_people table
    count = db.query(FamousPerson).count()
    print(f"Famous people: {count}")
    
    # Test users table
    user_count = db.query(User).count()
    print(f"Users: {user_count}")
    
    print("✅ Connection successful!")
except Exception as e:
    print(f"❌ Connection failed: {e}")
finally:
    db.close()
```

## Summary

**Your connection string is correct!** ✅

Just set it as an environment variable using one of the methods above, and your application will connect to Supabase automatically.

