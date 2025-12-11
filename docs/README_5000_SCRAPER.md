# Full Process Script: Scrape 5000 Wikipedia People & Calculate Charts

This script performs the complete end-to-end process:
1. Gets a list of 5000 famous people from Wikipedia
2. Scrapes their birth dates and locations
3. Calculates their birth charts with numerology and Chinese zodiac
4. Stores everything in the database

## Requirements

```bash
pip install wikipedia-api requests sqlalchemy aiosqlite pyswisseph
```

## Environment Setup

Set your OpenCage API key (required for geocoding):

**PowerShell:**
```powershell
$env:OPENCAGE_KEY="your_opencage_key_here"
```

**Bash/Linux:**
```bash
export OPENCAGE_KEY="your_opencage_key_here"
```

## Usage

```bash
python scripts/scrape_and_calculate_5000.py
```

## What It Does

1. **Fetches People List**: Gets up to 5000 people from Wikipedia categories:
   - Category:Living people
   - Category:20th-century births
   - Category:21st-century births
   - Category:19th-century births
   - And more historical categories

2. **Scrapes Birth Data**: For each person:
   - Extracts birth date (year, month, day)
   - Extracts birth location
   - Cleans wiki markup artifacts

3. **Calculates Charts**: For each person with valid data:
   - Geocodes birth location
   - Calculates full birth chart (Sidereal & Tropical)
   - Calculates numerology (Life Path & Day Number)
   - Calculates Chinese Zodiac (Animal & Element)
   - Extracts key chart elements for matching

4. **Stores in Database**: Saves to `synthesis_astrology.db`:
   - All chart data as JSON
   - Key elements (Sun, Moon, Rising signs)
   - Numerology data
   - Chinese zodiac data

## Rate Limiting

- **Wikipedia API**: 100 requests/minute (~0.6 seconds between requests)
- **Estimated Time**: 
  - Scraping 5000 people: ~50 minutes
  - Chart calculation: ~5-10 minutes (depends on geocoding)
  - **Total: ~1 hour**

## Output

The script creates:
- `full_process_output.txt` - Detailed log of the entire process
- `synthesis_astrology.db` - SQLite database with all results

## Progress Tracking

The script shows progress every:
- 100 people during scraping
- 50 people during chart calculation
- Commits to database every 50 records (batch commits)

## Error Handling

- Skips people without birth dates
- Skips people whose locations can't be geocoded
- Retries failed Wikipedia API requests
- Continues processing even if individual people fail

## Verification

After running, verify results:

```bash
python scripts/verify_numerology.py
```

Or query directly:

```python
import sqlite3
conn = sqlite3.connect('synthesis_astrology.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM famous_people')
print(f"Total records: {c.fetchone()[0]}")
conn.close()
```

## Notes

- The script respects Wikipedia's API rate limits
- It skips people already in the database (safe to re-run)
- Historical figures (pre-1800) are included
- Most people won't have exact birth times (defaults to noon)

## Troubleshooting

**"No module named 'sqlalchemy'"**
```bash
pip install sqlalchemy aiosqlite
```

**"OPENCAGE_KEY not set"**
- Set the environment variable before running

**"SwissEph file not found"**
- These warnings are for minor asteroids (Chiron, Ceres, etc.)
- Main chart calculations still work fine
- Can be ignored

**Slow performance**
- Normal - Wikipedia rate limiting means ~1 hour for 5000 people
- Can reduce `MAX_PEOPLE` in the script for faster testing

