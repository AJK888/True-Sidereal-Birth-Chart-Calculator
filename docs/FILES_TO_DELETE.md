# Files Recommended for Deletion

This document lists files that appear to be temporary, obsolete, duplicate, or no longer needed after the Supabase migration.

## 🗑️ RECOMMENDED FOR DELETION

### 1. **Output/Log Files** (Temporary - can be regenerated)
- `alignment_output.txt` - Script output file
- `chart_calc_output.txt` - Script output file
- `database_names.txt` - Temporary data file
- `debug_infobox.txt` - Debug output
- `famous_people_by_category_output.txt` - Script output
- `migration_output.txt` - Migration log output
- `minimize_database_output.txt` - Script output
- `output.log` - General log file
- `qc_report.txt` - Quality control report (can be regenerated)
- `scraper_run.log` - Scraper log file
- `wikidata_process_output.txt` - Process output

### 2. **Database Files** (Migrated to Supabase)
- `synthesis_astrology.db` - SQLite database (data now in Supabase)
- `famous_people_export.csv` - Temporary CSV export (data now in Supabase)
- `famous_people_data.json` - Temporary JSON export (if exists)

### 3. **Old SQL Migration Files** (No longer needed - migrations complete)
- `migrate_add_numerology_chinese.sql` - One-time migration, already applied
- `migrate_add_placements_columns.sql` - One-time migration, already applied
- `migrate_add_reading_purchase.sql` - One-time migration, already applied
- `migrate_add_subscriptions.sql` - One-time migration, already applied
- `migrate_add_user_columns.sql` - One-time migration, already applied

### 4. **Obsolete Migration Scripts** (Superseded by newer versions)
- `scripts/migrate_database.py` - Old SQLite migration script (superseded by `migrate_to_supabase.py`)
- `scripts/migrate_via_csv.py` - Alternative migration method (no longer needed)
- `scripts/migrate_users_to_supabase.py` - Superseded by `migrate_all_to_supabase.py`
- `scripts/verify_supabase_connection.py` - One-time verification script (no longer needed)

### 5. **Duplicate/Nested Directory** (Appears to be duplicate)
- `True-Sidereal-Birth-Chart/` (entire nested directory)
  - Contains duplicate `api.py`, `natal_chart.py`, `pdf_generator.py`, `render.yaml`, `requirements.txt`
  - These files exist in the parent directory

### 6. **Test/Debug Scripts** (One-time use, no longer needed)
- `scripts/test_api_direct.py` - One-time API test
- `scripts/test_chart_calc.py` - One-time chart calculation test
- `scripts/test_chunked_query.py` - One-time query test
- `scripts/test_fix.py` - One-time fix verification
- `scripts/test_geocoding.py` - One-time geocoding test
- `scripts/test_numerology_calc.py` - One-time numerology test
- `scripts/test_parsing.py` - One-time parsing test
- `scripts/test_patterns_direct.py` - One-time pattern test
- `scripts/test_regex.py` - One-time regex test
- `scripts/test_scraper_simple.py` - One-time scraper test
- `scripts/test_sparql_connection.py` - One-time SPARQL test
- `scripts/test_supabase_connection.py` - One-time connection test (connection verified)
- `scripts/test_wikipedia_format.py` - One-time format test
- `scripts/test_wikipedia_scraper.py` - One-time scraper test
- `scripts/debug_wiki.py` - Debug script
- `scripts/quick_geocode_test.py` - Quick test script
- `scripts/quick_list_names.py` - Quick utility
- `scripts/quick_list.py` - Quick utility
- `scripts/QUICK_TEST.py` - Quick test

### 7. **Verification Scripts** (One-time use, verification complete)
- `scripts/verify_and_run.py` - One-time verification
- `scripts/verify_charts.py` - One-time chart verification
- `scripts/verify_fix.py` - One-time fix verification
- `scripts/verify_numerology.py` - One-time numerology verification
- `scripts/verify_removal.py` - One-time removal verification
- `scripts/verify_supabase_connection.py` - Connection verified

### 8. **Utility Scripts** (One-time use, task complete)
- `scripts/add_missing_columns.py` - One-time column addition (complete)
- `scripts/align_database.py` - One-time alignment (complete)
- `scripts/check_na_values.py` - One-time check (complete)
- `scripts/delete_and_log.py` - One-time deletion utility
- `scripts/delete_records_direct.py` - One-time deletion utility
- `scripts/diagnose_columns.py` - One-time diagnosis (complete)
- `scripts/drop_rising_indexes.py` - One-time index removal (complete)
- `scripts/list_all_people.py` - Utility script (can be regenerated)
- `scripts/list_database_columns.py` - One-time listing (complete)
- `scripts/list_database_names.py` - Utility script
- `scripts/list_database_people.py` - Utility script
- `scripts/list_render_tables.py` - One-time listing (complete)
- `scripts/minimize_database_columns.py` - One-time minimization (complete)
- `scripts/monitor_progress.py` - One-time monitoring script
- `scripts/remove_invalid_records.py` - One-time removal (complete)
- `scripts/remove_rising_columns.py` - One-time removal (complete)
- `scripts/remove_two_records.py` - One-time removal (complete)
- `scripts/show_people.py` - Utility script
- `scripts/update_database_schema.py` - One-time schema update (complete)

### 9. **Obsolete Scraper Scripts** (Superseded by newer versions)
- `scripts/scrape_wikipedia_famous_people.py` - Old scraper (superseded by `scrape_famous_people_by_category.py`)
- `scripts/scrape_wikipedia_famous_people_fixed.py` - Intermediate version (superseded)

### 10. **Run/Output Scripts** (One-time use)
- `scripts/run_and_show_output.py` - One-time run script
- `scripts/run_and_show.py` - One-time run script
- `scripts/run_scraper_verbose.py` - One-time run script
- `scripts/run_with_output.py` - One-time run script
- `scripts/run_with_verbose_output.py` - One-time run script

### 11. **Redundant Documentation** (Information consolidated elsewhere)
- `UPDATE_TO_SUPABASE.md` - Redundant (info in `MIGRATE_TO_SUPABASE.md`)
- `scripts/EXPECTED_OUTPUT.md` - One-time documentation
- `scripts/GEOCODING_VERIFICATION.md` - One-time verification doc
- `scripts/REVIEW_NOTES.md` - Review notes (can be archived)

### 12. **Ephemeris Files** (If not needed for runtime)
- `swiss_ephemeris/seas_06.se1` - Old ephemeris file (if `seas_18.se1` is sufficient)
- `swiss_ephemeris/seas_12.se1` - Old ephemeris file (if `seas_18.se1` is sufficient)

## ⚠️ KEEP (Important Files)

### Core Application Files
- `api.py` - Main API
- `auth.py` - Authentication
- `chat_api.py` - Chat API
- `database.py` - Database models
- `llm_schemas.py` - LLM schemas
- `natal_chart.py` - Chart calculations
- `pdf_generator.py` - PDF generation
- `stripe_integration.py` - Stripe integration
- `subscription.py` - Subscription logic
- `v2_pipeline_functions.py` - Pipeline functions

### Active Scripts
- `scripts/calculate_all_placements.py` - Active calculation script
- `scripts/export_to_csv.py` - Active export script
- `scripts/export_to_csv_clean.py` - Active clean export
- `scripts/fix_database_issues.py` - Active fix script
- `scripts/quality_control_database.py` - Active QC script
- `scripts/scrape_and_calculate_5000.py` - Active scraper
- `scripts/scrape_famous_people_by_category.py` - Active scraper
- `scripts/scrape_wikidata_5000.py` - Active scraper
- `scripts/update_pageviews.py` - Active update script
- `scripts/view_pageview_stats.py` - Active stats viewer

### Migration Scripts (Keep for reference)
- `scripts/migrate_to_supabase.py` - Main migration script (keep for reference)
- `scripts/migrate_all_to_supabase.py` - Complete migration script (keep for reference)

### Documentation (Keep)
- `MIGRATE_TO_SUPABASE.md` - Migration guide
- `MIGRATE_USERS_TO_SUPABASE.md` - User migration guide
- `MIGRATION_ENV_VARS.md` - Environment variables guide
- `DATABASE_USAGE_ANALYSIS.md` - Database usage analysis
- `ALIGN_DATABASE_COMMANDS.md` - Database alignment commands
- `PRICING_STRATEGY.md` - Pricing strategy
- `STRIPE_SETUP_GUIDE.md` - Stripe setup guide
- `scripts/README_5000_SCRAPER.md` - Scraper documentation
- `scripts/README_FAMOUS_PEOPLE.md` - Famous people documentation
- `scripts/WIKIPEDIA_COMPLIANCE.md` - Wikipedia compliance
- `swiss_ephemeris/README_DOWNLOAD.md` - Ephemeris download guide

### Configuration Files
- `requirements.txt` - Python dependencies
- `render.yaml` - Render configuration

## 📊 Summary

**Total files recommended for deletion: ~80+ files**

**Categories:**
- Output/Log files: 11 files
- Database files: 2-3 files
- SQL migration files: 5 files
- Obsolete migration scripts: 4 files
- Duplicate directory: ~5 files
- Test scripts: 18 files
- Verification scripts: 6 files
- Utility scripts: 20 files
- Obsolete scraper scripts: 2 files
- Run scripts: 5 files
- Redundant documentation: 4 files
- Old ephemeris files: 2 files (optional)

## 🎯 Priority Deletion (Safe to Delete Immediately)

1. All `.txt` output files (11 files)
2. All `.log` files (2 files)
3. `synthesis_astrology.db` (SQLite database - data in Supabase)
4. `famous_people_export.csv` (temporary export)
5. All SQL migration files (5 files)
6. All test scripts (18 files)
7. Duplicate `True-Sidereal-Birth-Chart/` directory

## ⚠️ Review Before Deleting

- Old ephemeris files (check if `seas_18.se1` covers all needed date ranges)
- Some utility scripts (if you might need them for debugging)
- Redundant documentation (if you want to keep for reference)

