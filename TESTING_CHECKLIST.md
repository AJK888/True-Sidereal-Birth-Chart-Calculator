# Testing Checklist for Reading Improvements

This document outlines what to verify when testing the improved reading generation.

## Critical Requirements to Verify

### 1. Stellium Details ✅
**Check:** Every stellium mention must explicitly list ALL planets with signs and degrees.

**Example of CORRECT format:**
```
Your 12th House Stellium includes:
- Sun in Aries (Sidereal 3°34') / Taurus (Tropical 5°01')
- Venus in Aries (Sidereal 10°00') / Taurus (Tropical 11°27')
- True Node in Pisces (Sidereal 33°20') / Aries (Tropical 22°48')
- Vertex in Aries (Sidereal 10°00') / Taurus (Tropical 11°27')
```

**Example of INCORRECT format:**
```
Your 12th House Stellium creates...
```
(No planets listed - this is WRONG)

---

### 2. Planetary Dignities Section ✅
**Check:** Must have a section titled "PLANETARY DIGNITIES & CONDITIONS" that covers:
- All planets with exaltation (e.g., Mars in Capricorn)
- All planets in fall (e.g., Moon in Scorpio)
- All planets in detriment
- All planets in domicile
- All retrograde planets
- Explanation of what each condition means and WHY
- Concrete examples of how it shows up in life

**Verify:**
- Section exists in reading
- Each planet's dignity/debility is explained
- Both sidereal and tropical dignities are covered if they differ
- Examples are provided for each condition

---

### 3. Aspects Coverage ✅
**Check:** Must cover TOP 5-7 tightest aspects (minimum 5).

**Verify:**
- At least 5 aspects are covered
- Aspects are ordered by orb (tightest first)
- Each aspect has 3 paragraphs:
  1. Aspect mechanism explanation (WHAT and WHY)
  2. Why this matters (with 3-4 concrete examples)
  3. The growth edge (integrated expression)

**Example of aspect mechanism:**
```
Quincunx/Inconjunct (150°): Creates irritation/incompatibility, requires adjustment. 
WHY: The planets are 150° apart, creating an awkward angle where their energies 
don't naturally align, requiring constant adjustment.
```

---

### 4. Houses Analysis ✅
**Check:** All 12 houses must be covered with detailed analysis (10-15 paragraphs each).

**Verify:**
- All 12 houses are present
- Each house includes:
  - House cusp & ruler (3-4 paragraphs)
  - All planets in house (3-5 paragraphs)
  - All zodiac signs in house (2-3 paragraphs)
  - Synthesis & integration (4-6 paragraphs)
  - Stelliums (if applicable, 4-6 paragraphs with ALL planets listed)
  - Real-life expression (2-3 paragraphs)

---

### 5. Structural Issues ✅
**Check:** Spiritual Path must be SEPARATE from Famous People.

**Verify:**
- "Spiritual Path & Meaning" section exists and is separate
- It focuses on spirituality (Nodes, Neptune, 12th house, practices)
- "Famous People & Chart Similarities" is a separate section
- No mixing of famous people analysis into spiritual path

---

### 6. Concrete Examples ✅
**Check:** Every section must have 3-4 concrete examples.

**Verify:**
- Themes have examples across different life areas
- Aspects have examples in relationships, work, daily life
- Shadow patterns have concrete scenarios
- Work/Money section has specific career paths and money patterns
- Emotional Life has family dynamics and healing examples

**Example of GOOD concrete example:**
```
When your partner criticizes you, you freeze for a moment, then respond with 
logical explanations because your Moon in Libra (Sidereal 1.0°) needs to 
maintain harmony, while your Tropical Moon in Scorpio (13.0°) feels the 
attack deeply but suppresses it.
```

**Example of BAD abstract description:**
```
You tend to be emotional in relationships.
```

---

### 7. Shadow Section - How Shadows Interact ✅
**Check:** After all shadow patterns, there must be a subsection "HOW SHADOWS INTERACT".

**Verify:**
- Subsection exists
- Explains how shadows reinforce or conflict with each other
- Shows hierarchy (which shadow is most dominant)
- Provides examples of multiple shadows activating simultaneously
- Connects to overall chart themes

---

### 8. Emotional Life, Family & Healing ✅
**Check:** Must be SUBSTANTIAL (10-12 paragraphs minimum).

**Verify:**
- Section has required subsections:
  - Family Dynamics Analysis (3-4 paragraphs)
  - Childhood Patterns (2-3 paragraphs)
  - Healing Modalities (3-4 paragraphs)
- Multiple concrete examples across different life areas
- References to Moon, 4th/8th/12th houses, Chiron

---

### 9. Work, Money & Vocation ✅
**Check:** Must be SUBSTANTIAL (10-12 paragraphs minimum).

**Verify:**
- Section has required subsections:
  - Specific Career Paths (3-4 paragraphs)
  - Detailed Money Patterns (3-4 paragraphs)
  - Mars Analysis (2-3 paragraphs)
- Specific career guidance (not generic)
- Detailed money patterns with examples
- Mars placement analysis

---

### 10. Owner's Manual - Operating System ✅
**Check:** Must be EXPANDED (6-8 paragraphs minimum).

**Verify:**
- Detailed comparison between default mode and high expression mode
- Concrete examples of both modes
- Explanation of what triggers the shift between modes
- Practices/awareness that help access high expression mode
- How high expression mode transforms the central paradox

---

## PDF Formatting Verification

### Check PDF Output:
1. **Planetary Dignities section** appears correctly formatted
2. **All new subsections** are properly formatted:
   - "How Shadows Interact"
   - "Family Dynamics Analysis"
   - "Childhood Patterns"
   - "Healing Modalities"
   - "Specific Career Paths"
   - "Detailed Money Patterns"
   - "Mars Analysis"
3. **Stellium listings** are formatted correctly (not broken across pages awkwardly)
4. **Aspect mechanism explanations** are readable
5. **Concrete examples** are clearly formatted (not run together)

---

## Testing Steps

1. **Generate a new reading** with a chart that has:
   - A stellium (preferably 12th house)
   - Planets in dignities/debilities (exaltation, fall, etc.)
   - At least 5 tight aspects
   - Known birth time (for houses analysis)

2. **Review the reading text** for all critical requirements above

3. **Generate the PDF** and verify formatting

4. **Check for:**
   - Missing stellium planet listings
   - Missing planetary dignities section
   - Less than 5 aspects covered
   - Missing houses (should be all 12)
   - Mixed spiritual path and famous people
   - Abstract descriptions without concrete examples
   - Missing "How Shadows Interact" subsection
   - Brief Emotional Life or Work/Money sections
   - Brief Operating System section

---

## Expected Improvements

After these changes, readings should:
- **Grade: A** (instead of B)
- Have explicit stellium listings
- Include planetary dignities explanations
- Cover 5-7 aspects with mechanism explanations
- Have detailed 12-house analysis
- Show clear separation of spiritual path and famous people
- Include abundant concrete examples throughout
- Show how shadows interact
- Have substantial depth in all sections

---

## Notes

- If any requirement is missing, the prompts may need further refinement
- The PDF generator should handle all new sections automatically
- Test with multiple charts to ensure consistency

