# Refined Celebrity Similarity Matching Logic

## Overview

The similarity matching system has been significantly enhanced to incorporate multiple matching strategies, comprehensive scoring, and detailed match reasons.

## Matching Criteria

The system now returns famous people who match **any** of the following criteria:

### 1. Strict Matching Criteria

#### A. Sun AND Moon in Sidereal
- Both Sun and Moon signs must match in the sidereal system
- Example: User has Sun in Aries and Moon in Cancer → Returns people with Sun in Aries AND Moon in Cancer (sidereal)

#### B. Sun AND Moon in Tropical
- Both Sun and Moon signs must match in the tropical system
- Example: User has Sun in Taurus and Moon in Leo → Returns people with Sun in Taurus AND Moon in Leo (tropical)

#### C. Numerology Day AND Life Path Number
- Both Day Number and Life Path Number must match
- Handles master numbers (e.g., "33/6" matches both "33/6" and "6")
- Example: User has Day Number 5 and Life Path 7 → Returns people with Day Number 5 AND Life Path 7

#### D. Chinese Zodiac AND (Day Number OR Life Path Number)
- Chinese Zodiac animal must match
- AND at least one numerology number (Day Number OR Life Path Number) must match
- Example: User is a Dragon with Day Number 3 → Returns Dragons with Day Number 3 OR Dragons with Life Path 3

### 2. Aspect Matching

- Returns people who share **2 or more** of the top 3 aspects
- Compares both sidereal and tropical aspects
- Aspects are matched by planet pairs and aspect type (e.g., "Sun Conjunction Moon")
- Example: User's top 3 aspects include "Sun Square Saturn" and "Moon Trine Jupiter" → Returns people with at least 2 of these same aspects

### 3. Stellium Matching

- Returns people with the same stelliums (3+ planets in the same sign or house)
- Compares both sidereal and tropical stelliums
- Matches by sign name or house number
- Example: User has a 4-planet stellium in Aquarius → Returns people with stelliums in Aquarius

## Comprehensive Similarity Score

All matches receive a **comprehensive similarity score (0-100)** that incorporates:

### Planetary Placements (All Planets)
- **Sun**: 8 points per system (16 total)
- **Moon**: 8 points per system (16 total)
- **Mercury**: 3 points per system (6 total)
- **Venus**: 3 points per system (6 total)
- **Mars**: 3 points per system (6 total)
- **Jupiter**: 2 points per system (4 total)
- **Saturn**: 2 points per system (4 total)
- **Uranus**: 1.5 points per system (3 total)
- **Neptune**: 1.5 points per system (3 total)
- **Pluto**: 1.5 points per system (3 total)
- **Rising/Ascendant**: 4 points per system (8 total) - only if birth time known

**Total Planetary Points**: ~60-68 points (depending on birth time)

### Aspects (Top 10 from Both Systems)
- **2 points per matching aspect**
- Compares top 10 aspects from both sidereal and tropical systems
- Maximum: ~40 points (if all 10 aspects match)

### Numerology
- **Life Path Number**: 5 points
- **Day Number**: 3 points
- Handles master numbers

**Total Numerology Points**: 8 points

### Chinese Zodiac
- **Chinese Zodiac Animal**: 4 points

### Other Factors
- **Dominant Element**: 2 points

**Maximum Possible Score**: ~114-122 points (normalized to 0-100)

## Match Reasons

Each match includes a `match_reasons` array explaining why the person was included:

### Example Reasons:
- `"Matching Sun (Aries) and Moon (Cancer) in Sidereal"`
- `"Matching Day Number (5) and Life Path Number (7)"`
- `"Matching Chinese Zodiac (Dragon) and Day Number (3)"`
- `"Sharing 2 top aspect(s) in Sidereal: Sun Conjunction Moon, Venus Square Mars"`
- `"Shared stellium: Sidereal: 4 bodies in Aquarius (Air, Fixed Sign Stellium)"`

## Response Format

```json
{
  "matches": [
    {
      "name": "Albert Einstein",
      "wikipedia_url": "https://en.wikipedia.org/wiki/Albert_Einstein",
      "occupation": "Theoretical Physicist",
      "similarity_score": 87.5,
      "match_reasons": [
        "Matching Sun (Pisces) and Moon (Cancer) in Sidereal",
        "Sharing 2 top aspect(s) in Tropical: Sun Trine Jupiter, Moon Square Saturn"
      ],
      "match_type": "strict",
      "birth_date": "3/14/1879",
      "birth_location": "Ulm, Germany",
      "sun_sign_sidereal": "Pisces",
      "sun_sign_tropical": "Pisces",
      "moon_sign_sidereal": "Cancer",
      "moon_sign_tropical": "Leo",
      // ... all planetary placements
    }
  ],
  "total_compared": 1247,
  "matches_found": 15
}
```

## Match Type Priority

Results are sorted by:
1. **Match Type Priority**: Strict matches > Aspect matches > Stellium matches
2. **Similarity Score**: Higher scores first (within same match type)

## Database Optimization

The system uses optimized database queries:
- Filters candidates by strict criteria first (Sun/Moon signs, numerology, Chinese zodiac)
- Includes people with `top_aspects_json` or `chart_data_json` for aspect/stellium matching
- Limits initial query to 2000 candidates
- Applies strict matching, aspect matching, and stellium matching in Python
- Returns top N matches sorted by priority and score

## Future Enhancements

When you add columns for additional placements and aspects to the database:
- The system will automatically use them in the comprehensive score
- No code changes needed - it reads from `planetary_placements_json` and `top_aspects_json`
- Consider adding indexes on new columns for faster filtering

## Notes

- The system handles missing data gracefully (e.g., if birth time is unknown, Rising sign is skipped)
- Master numbers in numerology are handled flexibly (e.g., "33/6" matches both "33" and "6")
- All matching is case-insensitive where applicable
- The comprehensive score provides a general similarity metric even if strict criteria aren't met
