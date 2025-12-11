# Migration: Placement and Aspect Data

## Overview

This migration adds structured placement and aspect data columns to the database and populates them for all existing records.

## What This Migration Does

1. **Adds new columns** to `saved_charts` table:
   - `planetary_placements_json` - Structured planetary placements (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Ascendant)
   - `top_aspects_json` - Top 3 aspects for both sidereal and tropical systems

2. **Populates data** for:
   - All `saved_charts` records that have `chart_data_json`
   - All `famous_people` records that have `chart_data_json` but are missing placement/aspect data

## Data Structure

### Planetary Placements JSON Format

```json
{
  "sidereal": {
    "Sun": {
      "sign": "Capricorn",
      "degree": 25.5,
      "retrograde": false,
      "house": 10
    },
    "Moon": {
      "sign": "Aries",
      "degree": 12.3,
      "retrograde": false,
      "house": 1
    },
    "Ascendant": {
      "sign": "Aries",
      "degree": 0.0,
      "retrograde": false
    }
    // ... other planets
  },
  "tropical": {
    // Same structure for tropical placements
  }
}
```

### Top Aspects JSON Format

```json
{
  "sidereal": [
    {
      "p1": "Sun",
      "p2": "Moon",
      "type": "Conjunction",
      "orb": "2.5°",
      "strength": "4.5"
    },
    {
      "p1": "Venus",
      "p2": "Mars",
      "type": "Square",
      "orb": "3.2°",
      "strength": "3.0"
    },
    {
      "p1": "Jupiter",
      "p2": "Saturn",
      "type": "Trine",
      "orb": "1.8°",
      "strength": "3.5"
    }
  ],
  "tropical": [
    // Same structure for tropical aspects
  ]
}
```

## Usage

### Basic Migration (Only Missing Data)

```bash
python scripts/migration/migrate_placements_aspects.py
```

This will:
- Add columns to `saved_charts` if they don't exist
- Populate data only for records that are missing it

### Update All Records

```bash
python scripts/migration/migrate_placements_aspects.py --update-all
```

This will:
- Add columns to `saved_charts` if they don't exist
- Re-populate data for ALL records (even if they already have data)

### Migrate Only Saved Charts

```bash
python scripts/migration/migrate_placements_aspects.py --saved-charts-only
```

### Migrate Only Famous People

```bash
python scripts/migration/migrate_placements_aspects.py --famous-people-only
```

### Add Columns Only (No Data Population)

```bash
python scripts/migration/migrate_placements_aspects.py --columns-only
```

## What Gets Extracted

### Planetary Placements

Extracted from `chart_data_json`:
- **Major Planets**: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron
- **Ascendant**: Only if `unknown_time = False`
- **For each planet**:
  - Sign (sidereal and tropical)
  - Degree
  - Retrograde status
  - House number (if time is known)

### Top Aspects

Extracted from `chart_data_json`:
- Top 3 aspects by strength (score) for both sidereal and tropical
- Sorted by:
  1. Strength (score) descending
  2. Orb (closer = better) ascending
- **For each aspect**:
  - Planet 1 name
  - Planet 2 name
  - Aspect type (Conjunction, Square, Trine, etc.)
  - Orb (degrees)
  - Strength (score)

## Database Schema Changes

### Before Migration

```python
class SavedChart(Base):
    chart_data_json = Column(Text, nullable=True)
    # No structured placement/aspect data
```

### After Migration

```python
class SavedChart(Base):
    chart_data_json = Column(Text, nullable=True)
    planetary_placements_json = Column(Text, nullable=True)  # NEW
    top_aspects_json = Column(Text, nullable=True)  # NEW
```

## Benefits

1. **Faster Queries**: Can query placements/aspects without parsing full `chart_data_json`
2. **Better Performance**: Structured data is easier to index and search
3. **Consistency**: Same structure as `famous_people` table
4. **API Efficiency**: Can return placement/aspect data without full chart calculation

## Notes

- The migration extracts data from existing `chart_data_json` - it does NOT recalculate charts
- If `chart_data_json` is missing or invalid, the record will be skipped
- The migration is safe to run multiple times (idempotent)
- Uses batch commits (every 10 records) for performance
- Progress is logged every 100 records

## Troubleshooting

### "Column already exists" errors

This is normal if you've run the migration before. The script checks for existing columns before adding them.

### Records not being updated

Check that:
1. Records have `chart_data_json` populated
2. `chart_data_json` contains valid JSON
3. JSON contains `sidereal_major_positions` and `tropical_major_positions` arrays

### Missing Ascendant data

Ascendant is only extracted if `unknown_time = False`. Records with unknown birth times won't have Ascendant in placements.

## Related Scripts

- `scripts/maintenance/calculate_all_placements.py` - Similar script for famous_people only
- `scripts/maintenance/calculate_famous_people_charts.py` - Recalculates full charts
