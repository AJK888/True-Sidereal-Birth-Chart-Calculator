# Scripts Directory

This directory contains utility scripts organized by purpose.

## Directory Structure

### `migration/`
Database migration scripts for moving data between databases.

- **migrate_to_supabase.py** - Migrate `famous_people` table from SQLite to Supabase
- **migrate_all_to_supabase.py** - Migrate all user-related tables from Render to Supabase

### `scrapers/`
Web scraping scripts for collecting famous people data.

- **scrape_famous_people_by_category.py** - Scrape Wikipedia by category
- **scrape_wikidata_5000.py** - Scrape from Wikidata SPARQL endpoint
- **scrape_and_calculate_5000.py** - Combined scraping and chart calculation

### `maintenance/`
Database maintenance and data quality scripts.

- **quality_control_database.py** - Run comprehensive quality checks
- **fix_database_issues.py** - Automatically fix identified issues
- **calculate_all_placements.py** - Calculate planetary placements from chart data
- **update_pageviews.py** - Fetch and update Wikipedia pageview data
- **export_to_csv.py** - Export database tables to CSV
- **export_to_csv_clean.py** - Clean CSV export (minimal columns)
- **update_existing_with_asteroids.py** - Update existing records with asteroid data
- **view_pageview_stats.py** - View pageview statistics
- **calculate_famous_people_charts.py** - Calculate charts for famous people

### `utils/`
General utility scripts.

- **check_database_status.py** - Check database schema status
- **download_swiss_ephemeris.py** - Download Swiss Ephemeris files
- **copy_ephemeris_file.py** - Copy ephemeris files
- **create_all_ephemeris_files.py** - Create all ephemeris file types
- **final_test.py** - Final testing script

## Usage

All scripts should be run from the project root directory:

```bash
# From project root
python scripts/maintenance/quality_control_database.py
python scripts/migration/migrate_to_supabase.py
python scripts/scrapers/scrape_famous_people_by_category.py
```

## Notes

- Most scripts require database connection via `DATABASE_URL` environment variable
- Migration scripts may require additional connection strings (see documentation)
- Some scripts require API keys (Wikipedia, geocoding services, etc.)

