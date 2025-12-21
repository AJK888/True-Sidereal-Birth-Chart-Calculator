# Synastry Prompt Guide: Best Practices for LLM-Based Chart Comparison

## Recommendation: **Paste Everything in Chat** (Not PDFs)

**Why pasting is better:**
- LLMs process structured text more reliably than PDFs
- You can use clear section headers (=== SECTION ===) that LLMs parse well
- Easier to verify the data was received correctly
- Better token efficiency (no OCR/parsing overhead)
- More reliable formatting control

**When PDFs might be acceptable:**
- If the LLM has excellent PDF parsing (Claude 3.5 Sonnet, GPT-4o)
- If you're hitting token limits (though this is rare for modern models)
- If you need to share the prompt with others who prefer PDFs

---

## Prompt Structure (Based on Your Full Reading Format)

### System Prompt (Role Definition)

```
You are an expert true sidereal astrologer specializing in synastry (relationship chart comparison). You analyze the compatibility, dynamics, and karmic connections between two people using both tropical and sidereal astrology, numerology, and Chinese zodiac.

Your approach:
- Synthesize insights from BOTH sidereal and tropical systems
- Identify both harmonious and challenging aspects
- Explain how numerology and Chinese zodiac add depth to the astrological picture
- Use clear, psychologically literate language
- Be specific and concrete, not generic
- Acknowledge both strengths and growth areas in the relationship

CRITICAL RULES:
- Base your analysis ONLY on the chart data provided
- Do not invent placements, aspects, or interpretations not in the data
- Compare placements between Person 1 and Person 2 systematically
- Consider both individual chart patterns AND their interaction
```

### User Prompt Structure

```
=== SYNANSTRY ANALYSIS REQUEST ===

I need a comprehensive synastry analysis comparing two people's complete astrological profiles. Please analyze their compatibility, relationship dynamics, and karmic connections using all available data: tropical placements, sidereal placements, aspects, numerology, and Chinese zodiac.

=== PERSON 1: [Name or Identifier] ===

[Paste Person 1's complete chart data in the format below]

=== CHART METADATA ===
Unknown Time: [true/false]

=== CORE IDENTITY ===

SIDEREAL:
  Sun: [Sign] [Degree]°, House [Number]
  Moon: [Sign] [Degree]°, House [Number]
  Ascendant: [Sign] [Degree]°

TROPICAL:
  Sun: [Sign] [Degree]°, House [Number]
  Moon: [Sign] [Degree]°, House [Number]
  Ascendant: [Sign] [Degree]°

=== CHART ANALYSIS ===
SIDEREAL Dominant Element: [Element]
SIDEREAL Dominant Planet: [Planet]
TROPICAL Dominant Element: [Element]
TROPICAL Dominant Planet: [Planet]

=== PLANETARY PLACEMENTS ===
[Include all major planets in both systems - Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Nodes, etc.]

=== MAJOR ASPECTS (Top 10) ===
  [Planet 1] [Aspect Type] [Planet 2] (orb: [X]°, score: [Y])
  [Continue for top 10 aspects]

=== ASPECT PATTERNS ===
  - [Pattern 1]
  - [Pattern 2]

=== NUMEROLOGY ===
  Life Path: [Number]
  Day Number: [Number]
  Expression: [Number]
  [Include any other numerology data]

=== NODES ===
SIDEREAL North Node: [Sign] [Degree]°
TROPICAL North Node: [Sign] [Degree]°

=== CHINESE ZODIAC ===
[Sign and element, e.g., "Dragon (Earth)"]

=== PERSON 1'S FULL READING (if available) ===
[Paste the complete personalized reading text here - this provides deep context about Person 1's patterns, themes, and psychological makeup]

=== END PERSON 1 ===


=== PERSON 2: [Name or Identifier] ===

[Repeat the exact same structure for Person 2]

=== END PERSON 2 ===


=== SYNANSTRY ANALYSIS TASK ===

Please provide a comprehensive synastry analysis structured as follows:

**1. Executive Summary: The Core Connection**
Write 3-4 paragraphs that synthesize the overall relationship dynamic. What is the fundamental nature of this connection? What brings them together? What are the primary themes?

**2. Sidereal Synastry: The True Zodiac Connection**
- Compare Person 1's sidereal placements with Person 2's sidereal placements
- Analyze sidereal-to-sidereal aspects (Person 1's planets aspecting Person 2's planets)
- Identify the most significant sidereal connections
- Explain what these reveal about their karmic and soul-level connection

**3. Tropical Synastry: The Personality-Level Interaction**
- Compare Person 1's tropical placements with Person 2's tropical placements
- Analyze tropical-to-tropical aspects
- Identify how their personalities interact in day-to-day life
- Explain compatibility at the personality level

**4. Cross-System Analysis: Where Systems Align or Diverge**
- Compare Person 1's sidereal placements with Person 2's tropical placements (and vice versa)
- Identify where the two systems tell the same story vs. where they diverge
- Explain what this means for the relationship

**5. Numerology Compatibility**
- Compare Life Path numbers, Expression numbers, Day numbers
- Analyze how their numerological energies interact
- Identify numerological themes in the relationship

**6. Chinese Zodiac Compatibility**
- Compare their Chinese zodiac signs and elements
- Explain traditional compatibility and how it relates to the Western astrological picture
- Identify any interesting cross-cultural patterns

**7. Major Synastry Aspects (Most Important)**
Analyze the top 10-15 most significant synastry aspects between the two charts. For each:
- Which person's planet aspects which person's planet
- The aspect type and orb
- What this means for their relationship dynamic
- Concrete examples of how this might show up

**8. Relationship Strengths**
- What works well between them?
- Where do they naturally support each other?
- What gifts do they bring to each other?

**9. Relationship Challenges & Growth Areas**
- Where might they trigger each other?
- What patterns might create friction?
- How can they work with these challenges for mutual growth?

**10. Synthesis: The Complete Picture**
- Weave together insights from sidereal, tropical, numerology, and Chinese zodiac
- Provide a holistic view of the relationship
- Offer practical guidance for navigating the relationship

**11. Karmic & Evolutionary Themes**
- What might they be learning together?
- What past-life or soul-level themes are present?
- How can this relationship support their individual and mutual evolution?

Please be thorough, specific, and reference the actual chart data throughout your analysis.
```

---

## Data Formatting Tips

### 1. Use Clear Section Headers
Your current format uses `=== SECTION ===` headers - keep this! It helps LLMs parse the structure.

### 2. Include Both Full Readings (If Available)
The personalized readings provide deep psychological context that raw chart data doesn't. Include them if you have them.

### 3. Organize Planetary Placements Clearly
For synastry, you might want to add a section like:

```
=== ALL PLANETARY PLACEMENTS (for Synastry Reference) ===

SIDEREAL:
  Sun: [Sign] [Degree]° in House [X]
  Moon: [Sign] [Degree]° in House [X]
  Mercury: [Sign] [Degree]° in House [X]
  [Continue for all planets]

TROPICAL:
  [Same structure]
```

### 4. Calculate Synastry Aspects
If your system calculates synastry aspects (Person 1's planets aspecting Person 2's planets), include a section:

```
=== SYNANSTRY ASPECTS ===
Person 1's [Planet] [Aspect] Person 2's [Planet] (orb: [X]°)
[Continue for all significant synastry aspects]
```

---

## Which LLM to Use?

### **Best Options (in order):**

1. **Claude 3.5 Sonnet (Anthropic)**
   - Excellent at structured analysis
   - Handles long contexts well
   - Strong at synthesis across multiple systems

2. **GPT-4o (OpenAI)**
   - Very good at following complex instructions
   - Strong reasoning capabilities
   - Good at cross-referencing data

3. **Gemini 1.5 Pro (Google)**
   - Excellent context window (up to 1M tokens)
   - Good at structured tasks
   - Free tier available

4. **GPT-4 Turbo**
   - Good alternative if GPT-4o isn't available
   - Slightly less capable but still strong

### **Avoid:**
- GPT-3.5 (not sophisticated enough for this complexity)
- Free Claude (Claude Haiku) - too limited
- Older Gemini models (Gemini 1.0)

---

## Token Management

### Estimated Token Counts:
- **One person's chart data (formatted)**: ~2,000-3,000 tokens
- **One person's full reading**: ~4,000-8,000 tokens
- **Two people's complete data**: ~12,000-22,000 tokens
- **System prompt + instructions**: ~1,500 tokens
- **Total**: ~13,500-23,500 tokens

### Tips:
- Most modern models can handle this easily (GPT-4o: 128k context, Claude 3.5: 200k context)
- If you hit limits, prioritize:
  1. Keep all chart placements
  2. Keep top 10 aspects per person
  3. Keep full readings (they're very valuable)
  4. Reduce aspect patterns if needed

---

## Example Workflow

1. **Prepare Data:**
   - Export both charts from your website
   - Copy the formatted chart data (using your `format_serialized_chart_for_prompt` format)
   - Copy both full readings if available

2. **Start New Chat:**
   - Use a fresh conversation for each synastry analysis
   - Paste the system prompt first (if the LLM supports system messages)
   - Then paste the full user prompt with both people's data

3. **Refine if Needed:**
   - Ask follow-up questions about specific aspects
   - Request deeper analysis on particular areas
   - Ask for practical relationship advice based on the analysis

---

## Advanced: Adding Synastry Calculations

If you want to enhance this further, you could:

1. **Calculate Synastry Aspects:**
   - Person 1's planets aspecting Person 2's planets
   - Include orbs and aspect scores
   - This is the most important addition for synastry

2. **Composite Chart:**
   - Midpoint calculations between the two charts
   - Adds another layer of analysis

3. **Relationship Houses:**
   - How Person 1's planets fall in Person 2's houses
   - How Person 2's planets fall in Person 1's houses
   - Very important for synastry depth

---

## Final Recommendation

**Best Practice:**
1. Use **Claude 3.5 Sonnet** or **GPT-4o**
2. **Paste everything in chat** (not PDFs)
3. Use the structured format above with clear section headers
4. Include both full readings if available
5. Calculate and include synastry aspects if possible
6. Start with a fresh conversation for each analysis

This approach will give you the most comprehensive, accurate, and useful synastry analysis.

