# Migrate Database to Supabase

## Prerequisites

1. Install required package:
```bash
pip install psycopg2-binary
```

2. Get your Supabase database password:
   - Go to your Supabase dashboard
   - Settings > Database
   - Find "Database password" (or reset it if needed)

## Running the Migration

```bash
cd "Synthesis Astrology/True-Sidereal-Birth-Chart"
python scripts/migrate_to_supabase.py
```

The script will:
1. Prompt you for your Supabase database password
2. Connect to your SQLite database
3. Connect to your Supabase PostgreSQL database
4. Create the table schema in Supabase
5. Transfer all data from SQLite to Supabase
6. Create indexes for fast queries
7. Verify the migration

## What Gets Migrated

**All columns from your current model:**
- Basic info: id, name, wikipedia_url, occupation
- Birth data: birth_year, birth_month, birth_day, birth_hour, birth_minute, birth_location, unknown_time
- Chart signs: sun_sign_sidereal, sun_sign_tropical, moon_sign_sidereal, moon_sign_tropical
- Numerology: life_path_number, day_number
- Chinese Zodiac: chinese_zodiac_animal
- Metadata: page_views, created_at, updated_at
- JSON data: chart_data_json, planetary_placements_json, top_aspects_json

**Unwanted columns are excluded:**
- rising_sign_sidereal, rising_sign_tropical
- Individual planet columns (Mercury, Venus, Mars, etc.)
- chinese_zodiac_element

## Connection Details (Already Configured)

- Host: `db.nfglgzrfpmtsowwacmwz.supabase.co`
- Port: `5432`
- Database: `postgres`
- User: `postgres`
- Password: (you'll be prompted)

## After Migration

1. Update your `database.py` to use PostgreSQL instead of SQLite
2. Update your connection string in your application
3. Test the connection

## Troubleshooting

**Connection failed:**
- Check your database password in Supabase dashboard
- Verify your network can reach Supabase
- Check if your IP needs to be whitelisted (Supabase settings)

**Migration errors:**
- Check that your SQLite database is not corrupted
- Verify all required columns exist
- Check the error message for specific issues

