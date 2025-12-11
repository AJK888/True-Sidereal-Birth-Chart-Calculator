# Environment Variables for Migration

## Current Setup

You have:
- `DATABASE_URL` - Currently set to Render (for your user data)
- This is fine! The migration script uses a different variable.

## During Migration

The migration script uses:
- `RENDER_DATABASE_URL` - To read from Render (if not set, you can provide it directly in the script)

**Your current `DATABASE_URL` won't interfere** - the migration script uses `RENDER_DATABASE_URL` specifically.

## After Migration

Once you've migrated users to Supabase, you'll update:

### Option 1: Update DATABASE_URL to Supabase (Recommended)

```bash
# Set DATABASE_URL to Supabase (replaces Render)
export DATABASE_URL="postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
```

This way:
- ✅ Your app uses Supabase for everything
- ✅ Single connection string
- ✅ Both `users` and `famous_people` in one database

### Option 2: Keep Both (If you want to keep Render as backup)

You can keep both:
- `DATABASE_URL` - Set to Supabase (for your app)
- `RENDER_DATABASE_URL` - Keep as backup reference

## Migration Steps

1. **Run migration** (uses `RENDER_DATABASE_URL` or you can set it):
   ```bash
   # If RENDER_DATABASE_URL is not set, the script will use DATABASE_URL
   # Or set it explicitly:
   export RENDER_DATABASE_URL="$DATABASE_URL"  # Copy from Render
   python scripts/migrate_users_to_supabase.py
   ```

2. **After migration, update DATABASE_URL**:
   ```bash
   export DATABASE_URL="postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
   ```

3. **Test your app** - It should now use Supabase for both tables

## Quick Check

To see what your current `DATABASE_URL` is:
```bash
echo $DATABASE_URL
```

The migration script will work with your current setup - no changes needed before running it!

