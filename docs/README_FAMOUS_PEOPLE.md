# Famous People Similarity Feature

This feature allows users to find famous people with similar birth charts to their own.

## Setup Instructions

### 1. Install Required Packages

```bash
pip install wikipedia-api beautifulsoup4 requests
```

### 2. Scrape Wikipedia Data

**Option A: Manual Data Entry (Recommended for Start)**
Create a JSON file `famous_people_data.json` with this structure:

```json
[
  {
    "name": "Albert Einstein",
    "wikipedia_url": "https://en.wikipedia.org/wiki/Albert_Einstein",
    "birth_date": {
      "year": 1879,
      "month": 3,
      "day": 14,
      "hour": null,
      "minute": null
    },
    "birth_location": "Ulm, Kingdom of Württemberg, German Empire",
    "occupation": "Theoretical physicist"
  }
]
```

**Option B: Use Wikipedia API (Advanced)**
Run the scraper script (requires Wikipedia API setup):

```bash
python scripts/scrape_wikipedia_famous_people.py
```

### 3. Calculate Charts for Famous People

```bash
python scripts/calculate_famous_people_charts.py
```

This will:
- Read the JSON file
- Calculate birth charts for each person
- Store them in the database

### 4. Database Migration

The `FamousPerson` table will be created automatically when you run the script, or you can run:

```python
from database import init_db
init_db()
```

## API Usage

### Find Similar Famous People

**Endpoint:** `POST /api/find-similar-famous-people`

**Request Body:**
```json
{
  "chart_data": { /* chart data from /calculate_chart */ },
  "limit": 10
}
```

**Response:**
```json
{
  "matches": [
    {
      "name": "Albert Einstein",
      "wikipedia_url": "https://en.wikipedia.org/wiki/Albert_Einstein",
      "occupation": "Theoretical physicist",
      "similarity_score": 85.5,
      "birth_date": "3/14/1879",
      "birth_location": "Ulm, Kingdom of Württemberg",
      "sun_sign_sidereal": "Pisces",
      "sun_sign_tropical": "Pisces",
      "moon_sign_sidereal": "Aries",
      "moon_sign_tropical": "Aries"
    }
  ],
  "total_compared": 2000,
  "matches_found": 10
}
```

## Similarity Algorithm

The similarity score is calculated based on:
- **Sun Sign Match** (Sidereal & Tropical): 30% (15% each)
- **Moon Sign Match** (Sidereal & Tropical): 30% (15% each)
- **Rising Sign Match** (Sidereal & Tropical): 20% (10% each, if available)
- **Dominant Element Match**: 10%
- **Life Path Number Match**: 10% (if available)

Maximum score: 100 points

## Notes

- This is a **FREE feature** - no subscription required
- Most famous people won't have exact birth times, so Rising signs may not be available
- The feature works best with at least Sun and Moon sign matches
- Wikipedia URLs are provided for users to learn more about each person

