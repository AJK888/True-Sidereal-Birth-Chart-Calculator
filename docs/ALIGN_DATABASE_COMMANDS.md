# Database Alignment Commands

## Overview
This process minimizes the database by removing all astrological placement columns except Sun and Moon signs (sidereal and tropical). All other placements are stored in JSON columns.

## Changes Made
1. ✅ Removed rising sign columns from `database.py` model
2. ✅ Removed all individual planet columns (Mercury, Venus, Mars, Jupiter, Saturn, etc.)
3. ✅ Updated `export_to_csv.py` to exclude removed columns
4. ✅ Updated `quality_control_database.py` to not check removed columns
5. ✅ Updated `fix_database_issues.py` to not reference removed columns
6. ✅ Created `minimize_database_columns.py` script to remove unwanted columns

## Commands to Run

### Step 1: Minimize Database Columns
```bash
cd "Synthesis Astrology/True-Sidereal-Birth-Chart"
python scripts/minimize_database_columns.py
```

This script will:
- Remove `rising_sign_sidereal` and `rising_sign_tropical` columns
- Remove all individual planet columns (Mercury, Venus, Mars, Jupiter, Saturn, etc.)
- Keep only Sun and Moon signs (sidereal and tropical)
- Add `planetary_placements_json` and `top_aspects_json` if missing
- Recreate indexes on essential columns
- Verify the final schema

**Note:** This will prompt you to confirm before removing columns (requires table recreation in SQLite).

### Step 2: Populate JSON Columns (if not already done)
```bash
python scripts/calculate_all_placements.py
```

This extracts all planetary placements and top 3 aspects from `chart_data_json` and populates:
- `planetary_placements_json`
- `top_aspects_json`

### Step 3: Verify Database Status
```bash
python scripts/check_database_status.py
```

This will show:
- Current columns in the database
- Unwanted columns (should be none)
- Indexed columns
- Data population status

## Expected Final Schema

**Indexed columns (for fast matching):**
- `id` (primary key)
- `name` (unique)
- `sun_sign_sidereal`, `sun_sign_tropical`
- `moon_sign_sidereal`, `moon_sign_tropical`
- `life_path_number`
- `chinese_zodiac_animal`
- `page_views`

**JSON columns (all other astrological data):**
- `chart_data_json` - Full chart data
- `planetary_placements_json` - All planetary placements (Mercury, Venus, Mars, etc.)
- `top_aspects_json` - Top 3 aspects

**Removed columns (minimized for size):**
- ❌ `rising_sign_sidereal`, `rising_sign_tropical`
- ❌ `mercury_sign_sidereal`, `mercury_sign_tropical`
- ❌ `venus_sign_sidereal`, `venus_sign_tropical`
- ❌ `mars_sign_sidereal`, `mars_sign_tropical`
- ❌ `jupiter_sign_sidereal`, `jupiter_sign_tropical`
- ❌ `saturn_sign_sidereal`, `saturn_sign_tropical`
- ❌ All other individual planet sign columns

## Notes
- Rising sign data is still available in `chart_data_json` if needed
- All scripts have been updated to not reference rising sign columns
- The database will be smaller without these columns

