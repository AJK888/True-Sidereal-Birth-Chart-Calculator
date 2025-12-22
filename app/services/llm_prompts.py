"""
⚠️ PRESERVATION ZONE - LLM Prompt Functions

This module contains all LLM prompt functions with their prompts preserved EXACTLY.

CRITICAL: All prompts in this file are PRESERVED EXACTLY as they were in api.py.
DO NOT modify prompt text, structure, or formatting.
Only allowed changes: moving code to different files (exact copy), adding comments around prompts.

Original source: api.py
Last verified: 2025-01-21
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from llm_schemas import (
    serialize_chart_for_llm,
    format_serialized_chart_for_prompt,
    parse_json_response,
    GlobalReadingBlueprint,
    SNAPSHOT_PROMPT
)

# Import from llm_service for helper functions and client
# Use relative import since we're in the same package
from .llm_service import (
    Gemini3Client,
    calculate_gemini3_cost,
    _blueprint_to_json,
    serialize_snapshot_data,
    format_snapshot_for_prompt,
    sanitize_reading_text
)

# Import for famous people matching
from services.similarity_service import find_similar_famous_people_internal

logger = logging.getLogger(__name__)

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AI_MODE = os.getenv("AI_MODE", "real").lower()  # "real" or "stub" for local testing


# ⚠️ PRESERVATION ZONE START - PROMPT FUNCTION: g0_global_blueprint
async def g0_global_blueprint(llm: Gemini3Client, serialized_chart: dict, chart_summary: str, unknown_time: bool) -> Dict[str, Any]:
    """Gemini Call 0 - produce JSON planning blueprint with forensic depth."""
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 0: GLOBAL BLUEPRINT GENERATION")
    logger.info("="*80)
    logger.info(f"Starting G0_global_blueprint - Chart summary length: {len(chart_summary)} chars")
    logger.info(f"Unknown time: {unknown_time}")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    system_prompt = """You are a master astrological analyst performing FORENSIC CHART SYNTHESIS. Your job is to find the hidden architecture of this person's psyche by weighing every signal.

WEIGHTING HIERARCHY (use this to resolve conflicts):
1. ASPECTS with orb < 3° = strongest signal (especially to Sun, Moon, Ascendant)
2. SIDEREAL placements = soul-level truth, karmic patterns, what they ARE at depth
3. TROPICAL placements = personality expression, how they APPEAR and BEHAVE
4. NUMEROLOGY Life Path = meta-pattern that either confirms or creates tension with astrology
5. CHINESE ZODIAC = elemental overlay that amplifies or softens other signals
6. HOUSE placements = WHERE patterns manifest (career, relationships, etc.)

When sidereal and tropical CONTRADICT:
- The person experiences an internal split (e.g., sidereal Scorpio depth vs tropical Sagittarius optimism)
- This IS the story—don't smooth it over, make it the central tension

When sidereal and tropical ALIGN:
- The signal is amplified—this is a core, undeniable trait
- Cite this as "double confirmation"

Output ONLY JSON. No markdown or commentary outside the JSON object.
Schema (all keys required):
- life_thesis: string paragraph (the ONE sentence that captures their entire journey)
- central_paradox: string (the core contradiction that defines them—be specific)
- core_axes: list of 3-4 objects {name, description, chart_factors[], immature_expression, mature_expression, weighting_rationale}
- top_themes: list of 5 {label, text, evidence_chain} where evidence_chain shows the derivation
- sun_moon_ascendant_plan: list of {body, sidereal_expression, tropical_expression, integration_notes, conflict_or_harmony}
- planetary_clusters: list of {name, members[], description, implications, weight}
- houses_by_domain: list of {domain, summary, indicators[], ruling_planet_state}
- aspect_highlights: list of {title, aspect, orb, meaning, life_applications[], priority_rank}
- patterns: list of {name, description, involved_points[], psychological_function}
- themed_chapters: list of {chapter, thesis, subtopics[], supporting_factors[], key_contradiction}
- shadow_contradictions: list of {tension, drivers[], integration_strategy, what_they_avoid_seeing}
- growth_edges: list of {focus, description, practices[], resistance_prediction}
- final_principles_and_prompts: {principles[], prompts[]}
- snapshot: planning notes for the 7 most disarming psychological truths (specific behaviors, not traits)
- evidence_summary: brief list of the 5 strongest signals in the chart by weight

All notes must cite specific chart factors with their weights."""
    
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    time_note = "Birth time is UNKNOWN. Avoid relying on houses/angles; focus on sign-level, planetary, and aspect evidence." if unknown_time else "Birth time is known. Houses and angles are available."
    user_prompt = f"""Chart Summary:
{chart_summary}

Serialized Chart Data:
{serialized_chart_json}

Context:
- {time_note}
- You are performing FORENSIC ANALYSIS. Find the hidden architecture.
- For every claim, trace the evidence chain: which placements + aspects + numerology converge to create it?
- Identify the CENTRAL PARADOX: the one contradiction that explains most of their struggles and gifts.
- Weight signals using the hierarchy: tight aspects > sidereal > tropical > numerology > Chinese zodiac > houses.
- The snapshot field should capture 7 specific BEHAVIORS (not traits) that would make someone say "how do they know that?"
- The evidence_summary should list the 5 heaviest signals in priority order.

Return ONLY the JSON object."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=12000,
        temperature=0.2,
        call_label="G0_global_blueprint"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G0_global_blueprint completed in {step_duration:.2f} seconds")
    logger.info(f"G0 API calls made: {step_calls}")
    logger.info(f"G0 step cost: ${step_cost:.6f} USD")
    logger.info(f"G0 response length: {len(response_text)} characters")
    
    blueprint_parsed = parse_json_response(response_text, GlobalReadingBlueprint)
    if blueprint_parsed:
        logger.info("G0 parsed blueprint successfully")
        logger.info("="*80)
        return {"parsed": blueprint_parsed, "raw_text": response_text}
    
    logger.warning("G0 blueprint parsing failed - returning raw JSON text fallback")
    logger.info("="*80)
    return {"parsed": None, "raw_text": response_text}
# ⚠️ PRESERVATION ZONE END - PROMPT FUNCTION: g0_global_blueprint


# ⚠️ PRESERVATION ZONE START - PROMPT FUNCTION: g1_natal_foundation
async def g1_natal_foundation(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """Gemini Call 1 - Natal foundations + personal/social planets."""
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 1: NATAL FOUNDATION GENERATION")
    logger.info("="*80)
    logger.info(f"Starting G1_natal_foundation - Chart summary length: {len(chart_summary)} chars")
    logger.info(f"Blueprint parsed: {blueprint.get('parsed') is not None}")
    logger.info(f"Unknown time: {unknown_time}")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    blueprint_json = _blueprint_to_json(blueprint)
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    time_note = "After the Snapshot, include a short 'What We Know / What We Don't Know' paragraph clarifying birth time is unknown. Avoid houses/angles entirely." if unknown_time else "You may cite houses and angles explicitly."
    
    system_prompt = """You are The Synthesizer performing FORENSIC PSYCHOLOGICAL RECONSTRUCTION.

Your reader should finish this reading feeling like their psyche has been X-rayed. Every paragraph must show WHY you know what you know—not by explaining astrology, but by making the evidence visible through specificity.

EVIDENCE DENSITY RULE: Every paragraph must contain:
1. A specific claim about behavior/psychology
2. The phrase "because" or "this comes from" followed by 2-3 chart factors
3. A concrete example showing how it manifests

WEIGHTING (use this to resolve contradictions):
- Tight aspects (< 3° orb) override sign placements
- Sidereal = what they ARE at soul level (karmic, deep, persistent)
- Tropical = how they APPEAR and ACT (personality, behavior, first impression)
- When sidereal/tropical contradict: THIS IS THE STORY—the internal split IS the insight
- Numerology Life Path = meta-pattern confirming or challenging astrology
- Chinese Zodiac = elemental amplifier/softener

CUMULATIVE REVELATION STRUCTURE:
- Snapshot = "I see you" (specific behaviors that feel uncanny)
- Overview = "Here's why" (the architecture behind the behaviors)
- Houses = "Here's where it plays out" (life domains)

Tone: Forensic psychologist briefing a client. Clinical precision, warm delivery, zero fluff.

Scope for this call:
- Snapshot (7 bullets, no lead-in)
- Chart Overview & Core Themes
- Houses & Life Domains summary

Rules:
- Start immediately with SNAPSHOT heading. No preamble.
- NO markdown, bold/italic, emojis, or decorative separators.
- Every claim must have visible evidence (chart factors named).
- Make the reader feel the WEIGHT of the analysis through specificity, not explanation."""
    
    heading_block = "   WHAT WE KNOW / WHAT WE DON'T KNOW\n" if unknown_time else ""
    
    if unknown_time:
        houses_instruction = "SKIP THIS SECTION ENTIRELY. Since birth time is unknown, we cannot calculate houses. Do NOT write anything about houses or life domains. Do NOT mention that birth time is unknown here—that was already covered in the What We Know section. Simply omit this section completely."
    else:
        houses_instruction = """CRITICAL: You MUST cover ALL 12 houses. Do not skip any house. Each house gets its own detailed subsection.

Cover each house in this exact order with the heading format: [NUMBER]st/nd/rd/th HOUSE: [NAME]

1st HOUSE: SELF & IDENTITY
2nd HOUSE: RESOURCES & VALUES
3rd HOUSE: COMMUNICATION & LEARNING
4th HOUSE: HOME & ROOTS
5th HOUSE: CREATIVITY & PLEASURE
6th HOUSE: WORK & HEALTH
7th HOUSE: RELATIONSHIPS & PARTNERSHIPS
8th HOUSE: TRANSFORMATION & SHARED RESOURCES
9th HOUSE: PHILOSOPHY & HIGHER LEARNING
10th HOUSE: CAREER & PUBLIC STANDING
11th HOUSE: FRIENDS & ASPIRATIONS
12th HOUSE: SPIRITUALITY & UNCONSCIOUS

For EACH of the 12 houses, you MUST provide a COMPREHENSIVE, DETAILED analysis following this structure:

1. HOUSE CUSP & RULER (2-3 paragraphs):
   - The sign on the cusp in BOTH sidereal and tropical systems (note if they differ and what that means)
   - The ruling planet(s) for that sign
   - Where the ruling planet is located (sign, house, degree) in BOTH sidereal and tropical systems
   - The condition of the ruler (dignified, debilitated, retrograde, in fall, in detriment, etc.) in both systems
   - What the ruler's condition tells us about how this life domain functions
   - How the ruler's placement in another house connects this domain to that other area of life

2. ALL PLANETS IN THE HOUSE (3-5 paragraphs):
   - List EVERY planet that falls in this house in the SIDEREAL system (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Nodes, etc.)
   - List EVERY planet that falls in this house in the TROPICAL system
   - For EACH planet, provide detailed analysis:
     * Its sign placement (in both systems if different)
     * Its exact degree
     * Its house position
     * Its aspects (list all major aspects to other planets)
     * Whether it's retrograde
     * What this planet's presence in this house means for this life domain
   - Compare sidereal vs tropical placements - note where planets appear in different houses between systems and what that contradiction means
   - If a planet appears in this house in one system but not the other, explain the significance

3. ALL ZODIAC SIGNS IN THE HOUSE (2-3 paragraphs):
   - Identify ALL signs that appear within this house (houses can span multiple signs)
   - Note the exact degree ranges for each sign within the house
   - Explain how each sign's energy influences this life domain
   - Compare sidereal vs tropical sign distributions in the house
   - Show how different signs within the house create layers or phases in this domain

4. SYNTHESIS & INTEGRATION (4-6 paragraphs):
   - Show how the domain is "engineered" by multiple factors converging (house ruler + ALL planets in house + sign distributions + aspects to cusp)
   - Explain how sidereal placements reveal the SOUL-LEVEL approach to this domain
   - Explain how tropical placements reveal the PERSONALITY-LEVEL approach to this domain
   - Note any contradictions or tensions between sidereal and tropical placements and what that means
   - Give MULTIPLE concrete examples of how this shows up in real life (at least 3-4 specific scenarios)
   - Connect to numerology where relevant (Life Path, Day Number, etc.)
   - Connect to Chinese zodiac if relevant
   - If the house is empty (no planets), explain what that means - but still provide substantial analysis of the ruler and sign distributions
   - Show how this house connects to other houses through planetary rulerships

5. STELLIUMS & CONCENTRATIONS (if applicable, 2-3 paragraphs):
   - If 3+ planets are in this house, analyze the stellium energy in detail
   - Explain how it concentrates focus in this domain
   - Note if the stellium appears in sidereal, tropical, or both systems
   - Show how the stellium creates intensity, focus, or complexity in this area

6. REAL-LIFE EXPRESSION (2-3 paragraphs):
   - Provide concrete, specific examples of how this house manifests in daily life
   - Give scenarios, behaviors, or life patterns that show this house's energy
   - Connect to the overall chart themes from earlier sections

CRITICAL REQUIREMENTS:
- You MUST cover ALL 12 houses - do not skip any
- Each house should be substantial (at least 10-15 paragraphs total per house)
- Be thorough - examine every planet, every sign, and both systems
- Use specific degree references and aspect details
- Provide concrete examples, not generic descriptions
- Show the forensic analysis - make the reader feel the weight of the analysis"""
    
    snapshot_notes = ""
    if blueprint.get("parsed") and getattr(blueprint['parsed'], "snapshot", None):
        snapshot_notes = blueprint['parsed'].snapshot
    elif blueprint.get("raw_text"):
        snapshot_notes = "Snapshot planning notes were not parsed; rely on the chart summary and SNAPSHOT_PROMPT."
    
    user_prompt = f"""[CHART SUMMARY]\n{chart_summary}\n
[SERIALIZED CHART DATA]\n{serialized_chart_json}\n
[BLUEPRINT JSON]\n{blueprint_json}\n
Instructions:
1. Use uppercase headings in this order:
   SNAPSHOT: WHAT WILL FEEL MOST TRUE ABOUT YOU
   SYNTHESIS ASTROLOGY'S THESIS ON YOUR CHART (no colon in heading)
{heading_block}   CHART OVERVIEW & CORE THEMES
   HOUSES & LIFE DOMAINS SUMMARY

2. SNAPSHOT: THIS SECTION MUST BE A BULLETED LIST. FORMAT IS CRITICAL.
   
   OUTPUT FORMAT (follow exactly):
   - [First bullet point sentence here]
   - [Second bullet point sentence here]
   - [Third bullet point sentence here]
   - [Fourth bullet point sentence here]
   - [Fifth bullet point sentence here]
   - [Sixth bullet point sentence here]
   - [Seventh bullet point sentence here]
   
   RULES:
   - Exactly 7 bullets, each starting with "- " (dash space)
   - Each bullet is 1-2 sentences about a SPECIFIC BEHAVIOR or PATTERN
   - NO intro paragraph before the bullets
   - NO outro paragraph after the bullets
   - NO astrological jargon (no planets, signs, houses, aspects)
   - Every bullet should make the reader think "how do they know that?!"
   
{SNAPSHOT_PROMPT.strip()}

Blueprint notes for Snapshot (use them to prioritize chart factors):
{snapshot_notes}

3. SYNTHESIS ASTROLOGY'S THESIS ON YOUR CHART (write this heading exactly as shown, no colon after SYNTHESIS): Immediately after the Snapshot bullets, write a single powerful paragraph (4-6 sentences) that captures the CENTRAL THESIS of this person's chart. This is the "life_thesis" from the blueprint—the one core truth that everything else orbits around.
   
   FORMAT:
   - One paragraph, no bullets
   - Start with a bold, direct statement about who this person IS at their core
   - Reference the central_paradox from the blueprint
   - Name the primary tension they navigate daily
   - End with what integration/growth looks like for them
   - Use "you" language, be direct and confident
   - NO astrological jargon in this section—speak in psychological/behavioral terms
   
   This should feel like the "thesis statement" of their entire reading—if someone only read this paragraph, they'd understand the essence of the chart.

4. Chart Overview & Core Themes: This is the HEART of the reading. Structure each of the 5 themes as:
   
   THEME TITLE (plain language, no jargon)
   
   Opening: 2-3 sentences stating the pattern in everyday language. Make this vivid and specific.
   
   The Evidence (3-4 sentences): "This shows up because [Sidereal X] creates [quality], while [Tropical Y] adds [quality], and this tension is [amplified/softened] by [Aspect Z at N° orb]. Your Life Path [N] [confirms/complicates] this by [specific connection]. Additionally, [another chart factor] reinforces this pattern by [explanation]."
   
   How It Plays Out (3-4 sentences): Describe multiple specific scenarios—a relationship moment, a work situation, AND an internal experience. Be concrete: "When your partner criticizes you, you..." or "In meetings, you tend to..."
   
   The Contradiction (2-3 sentences): If sidereal and tropical pull in different directions, name the internal split explicitly: "Part of you [sidereal quality], while another part [tropical quality]. This creates an ongoing negotiation where [specific behavior]. You've probably noticed this most when [situation]."
   
   Integration Hint (1-2 sentences): What does growth look like for this specific theme?
   
   CRITICAL: Use blueprint.sun_moon_ascendant_plan extensively. At least 2 of the 5 themes MUST be anchored in Sun, Moon, or Ascendant dynamics. For each, reference:
   - The sidereal_expression and tropical_expression from the plan
   - The conflict_or_harmony field to determine if this is a tension or amplification
   - The integration_notes to inform the growth direction
   
   End with a SUBSTANTIAL SYNTHESIS PARAGRAPH (5-7 sentences) that:
   - Names the central paradox from the blueprint
   - Shows how the 5 themes interact and reinforce each other
   - Identifies the ONE thing that would shift everything if they worked on it
   - Describes what integration looks like in concrete daily terms
   - Ends with an empowering but realistic statement about their potential

5. Houses & Life Domains: {houses_instruction}

6. EVIDENCE TRAIL: Every paragraph must make the reader feel the weight of analysis by naming specific factors. Use phrases like:
   - "because your [placement] at [degree] [aspect] your [other placement]"
   - "this is amplified by"
   - "the [numerology number] confirms this pattern"
   - "your [Chinese zodiac element] adds [quality] to this dynamic"

7. No markdown, decorative characters, or horizontal rules.

8. Keep Action Checklist for later sections."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=81920,
        temperature=0.7,
        call_label="G1_natal_foundation"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G1_natal_foundation completed in {step_duration:.2f} seconds")
    logger.info(f"G1 API calls made: {step_calls}")
    logger.info(f"G1 step cost: ${step_cost:.6f} USD")
    logger.info(f"G1 response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text
# ⚠️ PRESERVATION ZONE END - PROMPT FUNCTION: g1_natal_foundation


# ⚠️ PRESERVATION ZONE START - PROMPT FUNCTION: g2_deep_dive_chapters
async def g2_deep_dive_chapters(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    natal_sections: str,
    unknown_time: bool
) -> str:
    """Gemini Call 2 - Themed chapters, aspects, shadow, owner's manual."""
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 2: DEEP DIVE CHAPTERS GENERATION")
    logger.info("="*80)
    logger.info(f"Starting G2_deep_dive_chapters - Chart summary length: {len(chart_summary)} chars")
    logger.info(f"Natal sections length: {len(natal_sections)} characters")
    logger.info(f"Unknown time: {unknown_time}")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    blueprint_json = _blueprint_to_json(blueprint)
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    
    system_prompt = """You are continuing the FORENSIC PSYCHOLOGICAL RECONSTRUCTION.

The earlier sections established the architecture. Now you're showing how it PLAYS OUT in specific life domains. Each section should feel like a case study with evidence.

CUMULATIVE REVELATION: Each section should DEEPEN what came before, not just add to it. Reference earlier themes explicitly: "The [Theme X] pattern from your overview manifests here as..."

EVIDENCE DENSITY: Every paragraph needs:
1. A specific claim about this life domain
2. The chart factors that create it (sidereal + tropical + aspects + numerology)
3. A concrete scenario or behavior

WEIGHTING REMINDER:
- Tight aspects (< 3°) are the loudest signals
- Sidereal = soul-level truth, tropical = personality expression
- When they contradict, the SPLIT is the insight
- Numerology confirms or complicates
- Chinese zodiac amplifies or softens

Scope for this call:
- LOVE, RELATIONSHIPS & ATTACHMENT
- WORK, MONEY & VOCATION
- EMOTIONAL LIFE, FAMILY & HEALING
- SPIRITUAL PATH & MEANING
- MAJOR LIFE DYNAMICS: THE TIGHTEST ASPECTS & PATTERNS
- SHADOW, CONTRADICTIONS & GROWTH EDGES
- OWNER'S MANUAL: FINAL INTEGRATION (with Action Checklist)

NO APPENDIX. Planetary details should be woven into the themed chapters where they matter most.

Guardrails:
- Read earlier sections and BUILD on them—don't repeat, deepen.
- Use blueprint data for each section.
- Every paragraph must have visible evidence (chart factors named).
- Each themed chapter must name the KEY CONTRADICTION for that life area.
- Maintain forensic precision with warm delivery.
- No markdown, decorative characters, or separators."""
    
    user_prompt = f"""[CHART SUMMARY]\n{chart_summary}\n
[SERIALIZED CHART DATA]\n{serialized_chart_json}\n
[BLUEPRINT JSON]\n{blueprint_json}\n
[PRIOR SECTIONS ALREADY WRITTEN]\n{natal_sections}\n
BLUEPRINT DATA TO USE:
- blueprint.sun_moon_ascendant_plan: Reference the sidereal/tropical expressions and integration_notes for Sun, Moon, Ascendant throughout these sections
- blueprint.themed_chapters: Use the thesis, subtopics, and key_contradiction for each chapter
- blueprint.aspect_highlights: For the Aspects section
- blueprint.patterns: For pattern summaries
- blueprint.shadow_contradictions and growth_edges: For Shadow section
- blueprint.final_principles_and_prompts: For Owner's Manual

Section instructions:
LOVE, RELATIONSHIPS & ATTACHMENT
- Use Venus, Mars, Nodes, Juno, 5th/7th houses (if time known) plus relevant aspects/patterns.
- Reference blueprint.sun_moon_ascendant_plan.Moon data—the Moon's sidereal/tropical split directly shapes emotional needs in relationships.
- Provide at least 3 concrete relational dynamics that show contradiction + lesson. Every paragraph must cite multiple signals (e.g., Venus/Mars aspect + nodal axis + numerology) and end with "so this often looks like…".

WORK, MONEY & VOCATION
- Integrate Midheaven/10th/2nd houses when available, Saturn/Jupiter signatures, dominant elements, numerology if reinforcing.
- Reference blueprint.sun_moon_ascendant_plan.Sun data—the Sun's sidereal/tropical split shapes core identity and career expression.
- Show how internal motives (from earlier sections) become strategy, and call back to Mars/Saturn themes where relevant.

EMOTIONAL LIFE, FAMILY & HEALING
- Use Moon aspects, 4th/8th/12th houses, Chiron, blueprint notes.
- Reference blueprint.sun_moon_ascendant_plan.Moon extensively—this is the Moon's primary domain.
- Reveal family imprints and healing arcs with visceral examples (e.g., "This is the moment you shut down during conflict…").

SPIRITUAL PATH & MEANING
- Nodes, Neptune, Pluto, numerology, blueprint spiritual chapter. Explain how surrender vs control repeats everywhere, and prescribe tangible practices that tie back to numerology/Life Path.

MAJOR LIFE DYNAMICS: THE TIGHTEST ASPECTS & PATTERNS

This section covers the TOP 5 TIGHTEST ASPECTS (by orb) plus any significant aspect patterns in the chart.

FORMAT FOR EACH ASPECT (cover ONLY the TOP 5 tightest aspects, ordered by orb from tightest to widest):

[PLANET 1] [ASPECT TYPE] [PLANET 2] ([orb]°)

[Paragraph 1: Core Dynamic - Name the fundamental tension or gift this creates. Explain the archetypal meaning of this aspect combination. What is the essential dynamic between these two planetary energies?]

[Paragraph 2: Why This Matters - Explain the psychological mechanism. What does this aspect create internally? How does it shape their default responses, emotional patterns, and decision-making? Reference both sidereal and tropical contexts if relevant. Show how this aspect amplifies or modifies the individual planet meanings. Provide concrete examples of how this shows up in relationships, work, or daily life.]

[Paragraph 3: The Growth Edge - What shifts when they work with this consciously? What's the integrated expression vs the reactive pattern? What does mastery of this aspect look like?]

---

[Leave a blank line and "---" separator between each aspect for readability]

AFTER THE 5 ASPECTS, ADD A SECTION ON ASPECT PATTERNS:

ASPECT PATTERNS IN YOUR CHART

For each significant pattern found in the chart (Grand Trines, T-Squares, Stelliums, Yods, Kites, Grand Crosses, Mystic Rectangles, etc.):

[PATTERN NAME]: [Planets involved - list all planets with their signs and houses]

[Paragraph 1: What This Geometry Creates - Explain the psychological function. How does this shape concentrate or distribute energy? What is the archetypal meaning of this pattern? How do the planets interact within this geometry? What are the strengths and challenges?]

[Paragraph 2: The Life Theme - Connect to earlier themes in the reading. How does this pattern reinforce or complicate themes from the Chart Overview? What life areas does this pattern most strongly influence? Provide concrete examples of how this pattern shows up in their daily life or major life decisions.]

[Paragraph 3: The Integration Path - How to work with this pattern consciously. What awareness or practices help them navigate this pattern? What does integration look like?]

---

[Use "---" between each pattern for visual separation]

CRITICAL REQUIREMENTS:
- Cover ONLY the TOP 5 tightest aspects (prioritize by orb - tightest first)
- Each aspect should be EXACTLY 3 paragraphs (not more, not less)
- Be detailed and specific - show the forensic analysis
- Provide concrete examples, not generic descriptions
- Reference both sidereal and tropical placements where relevant
- Connect aspects to the overall chart themes
- Include ALL significant aspect patterns found in the chart
- Each pattern should be EXACTLY 3 paragraphs

SHADOW, CONTRADICTIONS & GROWTH EDGES

This section should be COMPREHENSIVE and DEEP. Format with clear subsections and substantial content.

For each shadow pattern, use this detailed structure:

SHADOW: [Name of the Shadow Pattern]

The Pattern: [3-4 paragraphs describing what this looks like in behavior. Be specific and detailed. Give concrete examples of how this shadow pattern manifests. What are the observable behaviors, reactions, or patterns? How does this show up in relationships, work, or internal experience?]

The Driver: [4-5 paragraphs explaining WHY this pattern exists - what chart factors create it. Reference specific placements, aspects, and patterns from the chart. Show the forensic analysis - which planets, signs, houses, and aspects create this shadow? Explain the psychological mechanism. How do sidereal and tropical placements contribute? Connect to numerology or other factors if relevant. Show the evidence chain that creates this pattern.]

The Contradiction: [2-3 paragraphs explaining the internal contradiction or tension. What are the competing needs or energies? How does this create internal conflict? What is the person avoiding or not seeing?]

The Cost: [3-4 paragraphs on what this costs them in life/relationships. Be specific - how does this shadow pattern limit them? What opportunities does it close? What relationships does it damage? What growth does it prevent? Give concrete examples.]

The Integration: [4-5 paragraphs with concrete "pattern interrupts" and integration strategies. What can they DO differently? Provide specific practices, awareness exercises, or approaches. What does working with this shadow consciously look like? What is the integrated expression? How can they transform this pattern? Give actionable steps and concrete examples of the shift.]

Real-Life Example: [2-3 paragraphs with a concrete scenario showing this shadow pattern in action, and then showing how the integrated approach would look different.]

---

[Use "---" between each shadow pattern for visual separation]

Cover at least 4-5 shadow patterns from blueprint.shadow_contradictions. Be thorough and comprehensive.

GROWTH EDGES

After the shadow patterns, add a section called "Growth Edges" with actionable experiments and practices:

For each growth edge, provide:

[GROWTH EDGE NAME]

The Opportunity: [2-3 paragraphs explaining what this growth edge represents. What potential does this unlock? What becomes possible when they develop this?]

The Chart Evidence: [2-3 paragraphs showing which chart factors support this growth. Reference specific placements, aspects, or patterns that indicate this potential.]

The Practice: [3-4 paragraphs with specific, actionable experiments or practices. What can they do to develop this? Give concrete exercises, awareness practices, or approaches. Be detailed and specific - not vague suggestions.]

The Integration: [2-3 paragraphs on how this growth edge connects to the overall chart themes and shadow patterns. How does developing this help integrate the shadows?]

---

[Use "---" between each growth edge for visual separation]

Cover at least 4-5 growth edges from blueprint.growth_edges. Make them substantial and actionable.

CRITICAL REQUIREMENTS:
- Each shadow pattern should be substantial (at least 15-20 paragraphs per pattern)
- Each growth edge should be substantial (at least 10-12 paragraphs per edge)
- Be extremely detailed and specific - show the forensic analysis
- Provide concrete examples, practices, and actionable steps
- Reference specific chart factors throughout
- Make the reader feel the depth and weight of the analysis

- [Growth edge 1]: [Concrete experiment they can try, tied to a specific pattern]
- [Growth edge 2]: [Concrete experiment they can try, tied to a specific pattern]
- [Growth edge 3]: [Concrete experiment they can try, tied to a specific pattern]

Each growth edge bullet must start with "- " and be 1-2 sentences.

OWNER'S MANUAL: FINAL INTEGRATION
This is the "so what do I do with all this?" section. Structure it as:

YOUR OPERATING SYSTEM (2-3 paragraphs)
- Synthesize the central paradox and how it affects daily decisions
- Name the "default mode" they fall into under stress (with evidence)
- Name the "high expression" mode they access when integrated

GUIDING PRINCIPLES (3-4 principles)
Each principle must:
- Reference a specific theme or pattern from earlier
- Be actionable, not abstract
- Include the "because" (why this principle matters for THIS chart)

INTEGRATION PROMPTS (3-4 questions)
Questions they should sit with, each tied to a specific chart dynamic.

ACTION CHECKLIST (7 bullets)
Format each bullet EXACTLY like this, starting with "- " on its own line:
- [Action verb] [specific task] this week. This addresses [Theme/Section reference] which showed [specific pattern].

Each bullet must:
- Start on a new line with "- " (dash space)
- Begin with a specific action verb (Practice, Notice, Try, Schedule, Write, Ask, etc.)
- Be concrete enough to do THIS WEEK
- Reference which section/theme it addresses
- Keep each bullet to 1-2 sentences maximum

Example format:
- Practice pausing for 3 breaths before responding to criticism this week. This addresses Theme 2 (The Reactive Protector) which showed your Mars-Moon square creates defensive reactions.
- Notice when you're overexplaining yourself in conversations. This addresses the Mercury-Jupiter opposition from Major Aspects which creates a tendency to over-justify.

Unknown time handling: {'Do NOT cite houses/angles; speak in terms of domains, signs, and aspects.' if unknown_time else 'You may cite houses/angles explicitly.'}

FINAL INSTRUCTION: The reading should end with a single paragraph that returns to the life_thesis from the blueprint—the ONE sentence that captures their entire journey. This creates closure and makes the reader feel the coherence of the entire analysis."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=81920,
        temperature=0.7,
        call_label="G2_deep_dive_chapters"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G2_deep_dive_chapters completed in {step_duration:.2f} seconds")
    logger.info(f"G2 API calls made: {step_calls}")
    logger.info(f"G2 step cost: ${step_cost:.6f} USD")
    logger.info(f"G2 response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text
# ⚠️ PRESERVATION ZONE END - PROMPT FUNCTION: g2_deep_dive_chapters


# ⚠️ PRESERVATION ZONE START - PROMPT FUNCTION: g3_polish_full_reading
async def g3_polish_full_reading(
    llm: Gemini3Client,
    full_draft: str,
    chart_summary: str
) -> str:
    """Gemini Call 3 - polish entire reading for forensic coherence."""
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 3: POLISH FULL READING")
    logger.info("="*80)
    logger.info(f"Starting G3_polish_full_reading - Full draft length: {len(full_draft)} characters")
    logger.info(f"Chart summary length: {len(chart_summary)} chars")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    system_prompt = """You are the final editor ensuring this reading feels like a FORENSIC RECONSTRUCTION—coherent, weighted, and undeniably specific.

COHERENCE CHECK:
1. Does every section BUILD on previous sections? Add explicit callbacks: "As we saw in [Section]..." or "This connects to [Theme X]..."
2. Does the central paradox thread through the entire reading? It should be named in Overview, visible in each themed chapter, and resolved in Owner's Manual.
3. Are late revelations reflected earlier? If Shadow section reveals something important, ensure Overview or Snapshot hints at it.

EVIDENCE DENSITY CHECK:
1. Does every claim have visible evidence (chart factors named)?
2. Are the "because" statements specific? Not "because of your chart" but "because your Moon at 15° Scorpio squares your Sun"
3. Is the weighting clear? When factors contradict, is the resolution explained?

IMPACT CHECK:
1. Does Snapshot feel uncanny? Each bullet should make reader think "how do they know that?"
2. Does each paragraph earn its existence? Cut fluff, tighten sentences, make every word count.
3. Does the reading ESCALATE? The most powerful insight should come in Shadow or Owner's Manual, not early.

TONE CHECK:
1. Clinical precision + warm delivery
2. Second person throughout
3. Confident but non-absolute ("you tend to" not "you always")
4. Zero fluff, zero filler, zero generic statements

Preserve all section headings and bullet counts. You may rewrite any sentence to improve coherence and impact."""
    
    user_prompt = f"""Full draft to polish:
{full_draft}

Reference chart summary (for context only, do not restate):
{chart_summary}

Return the polished reading. Ensure:
1. Central paradox is visible throughout
2. Every section builds on previous ones
3. Evidence is specific and weighted
4. The reading feels like a forensic reconstruction, not a horoscope"""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=81920,
        temperature=0.4,
        call_label="G3_polish_full_reading"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G3_polish_full_reading completed in {step_duration:.2f} seconds")
    logger.info(f"G3 API calls made: {step_calls}")
    logger.info(f"G3 step cost: ${step_cost:.6f} USD")
    logger.info(f"G3 response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text
# ⚠️ PRESERVATION ZONE END - PROMPT FUNCTION: g3_polish_full_reading


# ⚠️ PRESERVATION ZONE START - PROMPT FUNCTION: g4_famous_people_section
async def g4_famous_people_section(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    famous_people_matches: list,
    unknown_time: bool
) -> str:
    """Gemini Call 4 - Generate famous people comparison section."""
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 4: FAMOUS PEOPLE SECTION GENERATION")
    logger.info("="*80)
    logger.info(f"Starting G4_famous_people_section - Number of matches: {len(famous_people_matches)}")
    logger.info(f"Chart summary length: {len(chart_summary)} chars")
    logger.info(f"Unknown time: {unknown_time}")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    
    # Format famous people data for the LLM - limit to top 5
    famous_people_data = []
    for match in famous_people_matches[:5]:  # Limit to top 5
        fp_data = {
            "name": match.get("name", "Unknown"),
            "occupation": match.get("occupation", ""),
            "similarity_score": match.get("similarity_score", 0),
            "matching_factors": match.get("matching_factors", []),
            "birth_date": match.get("birth_date", ""),
            "birth_location": match.get("birth_location", ""),
        }
        famous_people_data.append(fp_data)
    
    famous_people_json = json.dumps(famous_people_data, indent=2)
    
    system_prompt = """You are an expert astrologer analyzing chart similarities between the user and famous historical figures.

Your task is to provide DEEP, DETAILED analysis that:
1. References EACH matching placement explicitly and explains what it means
2. Shows how multiple matching placements create a coherent psychological pattern
3. Connects chart similarities to observable traits, life patterns, and archetypal energies
4. Provides substantial, insightful analysis (not brief summaries)

Be extremely specific and forensic:
- Name EVERY matching placement from the matching_factors list
- Explain what EACH placement means individually
- Show how the COMBINATION of placements creates a unique pattern
- Connect to psychological traits, life themes, strengths, and challenges
- Provide concrete examples of how these patterns manifest
- Be insightful, detailed, and comprehensive

Tone: Clinical precision with warm delivery. Second person ("you share...", "like [famous person], you...")."""
    
    user_prompt = f"""**User's Chart Summary:**
{chart_summary}

**Famous People Matches:**
{famous_people_json}

**Instructions:**
Write a section titled "Famous People & Chart Similarities" that:

1. Introduction (2-3 paragraphs): Explain that sharing chart patterns with notable figures reveals archetypal energies and life themes. Explain how these similarities work and what they mean.

2. For EACH of the top 5 highest scoring matches (process ALL 5, ordered by similarity_score from highest to lowest):

   Format each person as follows:
   
   [PERSON NAME] ([OCCUPATION/NOTABILITY])
   
   Chart Similarities:
   - Go through EACH matching factor from the matching_factors list
   - For EACH matching placement, write 2-3 sentences explaining:
     * What this specific placement means (e.g., "Sun in Aries (Sidereal) indicates...")
     * How this placement shapes personality, behavior, or life patterns
     * What this suggests about core identity, emotional needs, or life themes
   
   Psychological Patterns:
   - Write 3-4 paragraphs analyzing the COMBINATION of matching placements
   - Show how multiple placements create a coherent psychological profile
   - Explain what these shared patterns suggest about:
     * Core psychological traits and motivations
     * Life themes or archetypal energies
     * Potential strengths and how they manifest
     * Potential challenges and how they show up
   - Be specific: "The combination of [Placement 1] and [Placement 2] creates [pattern]. Like [famous person], this manifests as [concrete example from their life or work]. In your life, this might show up as [specific scenario]."
   
   What This Reveals:
   - Write 2-3 paragraphs connecting the chart similarities to observable traits
   - Reference specific examples from the famous person's life or work
   - Explain what these patterns suggest about the user's potential
   - Be detailed and insightful, not generic

3. Synthesis (3-4 paragraphs): After covering all 8 people, write a comprehensive synthesis that:
   - Identifies common themes across multiple matches
   - Explains what these collective similarities reveal about the user's archetypal patterns
   - Shows how different matches highlight different aspects of the user's chart
   - Connects to the overall reading themes
   - Provides insight into potential life themes and directions

**Critical Requirements:**
- Cover ALL 5 top matches (not just 2-3)
- Reference EACH matching placement explicitly from the matching_factors list
- Write SUBSTANTIAL content for each person (at least 5-7 paragraphs per person)
- Don't just list similarities—explain what they MEAN in depth
- Connect chart patterns to psychological/life patterns with concrete examples
- Be insightful, detailed, and comprehensive
- If birth time is unknown, don't mention house placements
- Use second person throughout
- No markdown, bold, or decorative separators"""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=32768,  # Increased for detailed famous people analysis
        temperature=0.7,
        call_label="G4_famous_people_section"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G4_famous_people_section completed in {step_duration:.2f} seconds")
    logger.info(f"G4 API calls made: {step_calls}")
    logger.info(f"G4 step cost: ${step_cost:.6f} USD")
    logger.info(f"G4 response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text
# ⚠️ PRESERVATION ZONE END - PROMPT FUNCTION: g4_famous_people_section


# ⚠️ PRESERVATION ZONE START - PROMPT FUNCTION: generate_snapshot_reading
async def generate_snapshot_reading(chart_data: dict, unknown_time: bool) -> str:
    """
    Generate a comprehensive snapshot reading using limited data:
    - 2 tightest aspects (sidereal and tropical)
    - Stelliums (sidereal and tropical)
    - Sun, Moon, Rising (sidereal and tropical)
    
    This is blinded - no name, birthdate, or location is included.
    """
    if not GEMINI_API_KEY and AI_MODE != "stub":
        logger.warning("Gemini API key not configured - snapshot reading unavailable")
        return "Snapshot reading is temporarily unavailable."
    
    try:
        # Serialize snapshot data
        logger.info("Serializing snapshot data...")
        snapshot = serialize_snapshot_data(chart_data, unknown_time)
        
        # Validate snapshot has data
        if not snapshot.get("core_identity", {}).get("sidereal") and not snapshot.get("core_identity", {}).get("tropical"):
            logger.error("Snapshot data is empty - no core identity found")
            return "Snapshot reading is temporarily unavailable - chart data incomplete."
        
        snapshot_summary = format_snapshot_for_prompt(snapshot)
        logger.info(f"Snapshot summary length: {len(snapshot_summary)} characters")
        
        llm = Gemini3Client()
        logger.info("Calling Gemini API for snapshot reading...")
        
        unknown_time_flag = snapshot.get('metadata', {}).get('unknown_time', False)
        
        time_restrictions = ""
        if unknown_time_flag:
            time_restrictions = """
CRITICAL: Birth time is UNKNOWN. You MUST:
- Do NOT mention the Ascendant (Rising sign) at all - it is not available
- Do NOT mention house placements or house numbers
- Do NOT mention the Midheaven (MC) or any angles
- Do NOT mention chart ruler or house rulers
- Focus ONLY on sign placements, planetary aspects, and stelliums in signs
- When describing stelliums, focus on the sign energy, NOT house placement
- If the data shows "Unknown Time: True", the Ascendant/Rising is NOT in the data and should not be referenced"""
        else:
            time_restrictions = """
- You may reference the Ascendant (Rising sign) if it's in the data
- You may mention house placements if they're provided in the data"""
        
        system_prompt = f"""You are a master astrological analyst providing a comprehensive snapshot reading.

Your task is to synthesize the core identity (Sun, Moon, Rising if available), the two tightest aspects, and any stelliums from BOTH sidereal and tropical systems into a detailed but focused snapshot.

GUIDELINES:
1. Compare and contrast sidereal vs tropical placements - note where they align and where they differ
2. Explain how the tightest aspects create core dynamics in the personality
3. Describe how stelliums concentrate energy in specific signs (and houses only if birth time is known)
4. Synthesize these elements into a coherent picture of the person's core nature
5. Be specific and insightful, providing meaningful depth (4-6 paragraphs)
6. Use second person ("you", "your")
7. Focus on psychological patterns and tendencies, not predictions
8. Draw connections between the different elements to create a unified narrative
{time_restrictions}

OUTPUT FORMAT:
Provide a comprehensive snapshot reading in 4-6 paragraphs that synthesizes all the provided information with depth and insight."""
        
        unknown_time_flag = snapshot.get('metadata', {}).get('unknown_time', False)
        
        rising_instruction = ""
        if unknown_time_flag:
            rising_instruction = "\nIMPORTANT: The birth time is unknown, so the Ascendant/Rising sign is NOT available. Do NOT mention it or try to interpret it. Focus only on Sun and Moon placements, aspects, and stelliums."
        else:
            rising_instruction = "\nYou may include the Ascendant/Rising sign in your analysis if it's provided in the data."
        
        user_prompt = f"""Chart Snapshot Data:
{snapshot_summary}

Generate a comprehensive snapshot reading that:
1. Synthesizes the Sun and Moon placements from both sidereal and tropical systems, noting similarities and differences{rising_instruction}
2. Explains how the two tightest aspects from each system create core dynamics and psychological patterns
3. Describes how any stelliums concentrate energy in signs and what this means for the person's focus and expression (mention houses ONLY if birth time is known)
4. Compares and contrasts sidereal vs tropical where relevant, explaining the significance of any differences
5. Creates a coherent, detailed picture of the core psychological patterns, motivations, and tendencies
6. Draws meaningful connections between all the elements to tell a unified story

{"REMINDER: Birth time is unknown. Do NOT mention Ascendant, Rising sign, houses, Midheaven, or any time-sensitive chart elements." if unknown_time_flag else ""}

Provide 4-6 paragraphs of insightful, specific analysis that gives readers a meaningful understanding while they wait for their full report."""
        
        response = await llm.generate(
            system=system_prompt,
            user=user_prompt,
            max_output_tokens=4000,  # Increased for more comprehensive reading
            temperature=0.7,  # Higher for more creative and nuanced responses
            call_label="snapshot_reading"
        )
        
        return response.strip()
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"Error generating snapshot reading: {error_type}: {error_msg}", exc_info=True)
        logger.error(f"Full error details - Type: {error_type}, Message: {error_msg}")
        return f"Snapshot reading is temporarily unavailable. Error: {error_type}"
# ⚠️ PRESERVATION ZONE END - PROMPT FUNCTION: generate_snapshot_reading


# ⚠️ PRESERVATION ZONE START - PROMPT FUNCTION: get_gemini3_reading
async def get_gemini3_reading(chart_data: dict, unknown_time: bool, db: Session = None) -> str:
    """Four-call Gemini 3 pipeline with optional famous people section."""
    reading_start_time = time.time()
    
    if not GEMINI_API_KEY and AI_MODE != "stub":
        logger.error("Gemini API key not configured - AI reading unavailable")
        raise Exception("Gemini API key not configured. AI reading is unavailable.")
    
    logger.info("="*80)
    logger.info("="*80)
    logger.info("FULL READING GENERATION - STARTING")
    logger.info("="*80)
    logger.info("="*80)
    logger.info(f"AI_MODE: {AI_MODE}")
    logger.info(f"Unknown time: {unknown_time}")
    logger.info(f"Database session available: {db is not None}")
    logger.info("="*80)
    
    llm = Gemini3Client()
    
    try:
        # Step 0: Serialize chart data
        logger.info("Preparing chart data for LLM...")
        serialized_chart = serialize_chart_for_llm(chart_data, unknown_time=unknown_time)
        chart_summary = format_serialized_chart_for_prompt(serialized_chart)
        logger.info(f"Chart serialized - Summary length: {len(chart_summary)} characters")
        logger.info("="*80)
        
        # Step 1: Global Blueprint
        blueprint = await g0_global_blueprint(llm, serialized_chart, chart_summary, unknown_time)
        
        # Step 2: Natal Foundation
        natal_sections = await g1_natal_foundation(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        
        # Step 3: Deep Dive Chapters
        deep_sections = await g2_deep_dive_chapters(llm, serialized_chart, chart_summary, blueprint, natal_sections, unknown_time)
        
        # Step 4: Combine and Polish
        full_draft = f"{natal_sections}\n\n{deep_sections}"
        logger.info(f"Combined draft length: {len(full_draft)} characters")
        final_reading = await g3_polish_full_reading(llm, full_draft, chart_summary)
        
        # Step 5: Generate famous people section if database session is available
        famous_people_section = ""
        if db:
            try:
                logger.info("="*80)
                logger.info("FAMOUS PEOPLE MATCHING - STARTING")
                logger.info("="*80)
                logger.info("Calling find_similar_famous_people_internal to find matches...")
                famous_start = time.time()
                famous_people_matches = await find_similar_famous_people_internal(chart_data, limit=8, db=db)
                famous_duration = time.time() - famous_start
                logger.info(f"Famous people matching completed in {famous_duration:.2f} seconds")
                logger.info(f"find_similar_famous_people_internal returned: {famous_people_matches.get('matches_found', 0)} matches out of {famous_people_matches.get('total_compared', 0)} compared")
                
                if famous_people_matches and len(famous_people_matches.get('matches', [])) > 0:
                    logger.info(f"Found {len(famous_people_matches['matches'])} famous people matches, generating section...")
                    famous_people_section = await g4_famous_people_section(
                        llm, serialized_chart, chart_summary, famous_people_matches['matches'], unknown_time
                    )
                    final_reading = f"{final_reading}\n\n{famous_people_section}"
                    logger.info(f"Famous people section added - Final reading length: {len(final_reading)} characters")
                else:
                    logger.info("No famous people matches found or empty result")
                logger.info("="*80)
            except Exception as e:
                logger.error(f"Error generating famous people section: {e}", exc_info=True)
                # Continue without famous people section
        
        # Finalize reading
        final_reading = sanitize_reading_text(final_reading).strip()
        reading_duration = time.time() - reading_start_time
        
        # Calculate final costs
        summary = llm.get_summary()
        cost_info = calculate_gemini3_cost(summary['total_prompt_tokens'], summary['total_completion_tokens'])
        
        # Comprehensive cost summary
        logger.info("="*80)
        logger.info("="*80)
        logger.info("FULL READING GENERATION - COMPLETE")
        logger.info("="*80)
        logger.info("="*80)
        logger.info(f"Total Generation Time: {reading_duration:.2f} seconds ({reading_duration/60:.2f} minutes)")
        logger.info(f"Final Reading Length: {len(final_reading):,} characters")
        logger.info("")
        logger.info("=== GEMINI 3 API USAGE SUMMARY ===")
        logger.info(f"Total API Calls: {summary['call_count']}")
        logger.info(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        logger.info(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        logger.info(f"Total Tokens: {summary['total_tokens']:,}")
        logger.info("")
        logger.info("=== GEMINI 3 API COST BREAKDOWN ===")
        logger.info(f"Input Cost:  ${cost_info['input_cost_usd']:.6f} USD")
        logger.info(f"Output Cost: ${cost_info['output_cost_usd']:.6f} USD")
        logger.info(f"───────────────────────────────────")
        logger.info(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f} USD")
        logger.info("="*80)
        logger.info("="*80)
        
        # Also print to stdout for Render visibility
        print(f"\n{'='*80}")
        print("FULL READING GENERATION - COMPLETE")
        print(f"{'='*80}")
        print(f"Total Generation Time: {reading_duration:.2f} seconds ({reading_duration/60:.2f} minutes)")
        print(f"Final Reading Length: {len(final_reading):,} characters")
        print("")
        print("=== GEMINI 3 API USAGE SUMMARY ===")
        print(f"Total API Calls: {summary['call_count']}")
        print(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        print(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        print(f"Total Tokens: {summary['total_tokens']:,}")
        print("")
        print("=== GEMINI 3 API COST BREAKDOWN ===")
        print(f"Input Cost:  ${cost_info['input_cost_usd']:.6f} USD")
        print(f"Output Cost: ${cost_info['output_cost_usd']:.6f} USD")
        print(f"───────────────────────────────────")
        print(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f} USD")
        print(f"{'='*80}\n")
        
        return final_reading
    except Exception as e:
        reading_duration = time.time() - reading_start_time
        logger.error(f"Error during Gemini 3 reading generation after {reading_duration:.2f} seconds: {e}", exc_info=True)
        raise Exception(f"An error occurred while generating the detailed AI reading: {e}")
# ⚠️ PRESERVATION ZONE END - PROMPT FUNCTION: get_gemini3_reading


# ⚠️ PRESERVATION ZONE START - PROMPT FUNCTION: generate_comprehensive_synastry
async def generate_comprehensive_synastry(
    llm: Gemini3Client,
    person1_data: Dict[str, Any],
    person2_data: Dict[str, Any]
) -> str:
    """
    Generate comprehensive synastry analysis using the prompt structure from SYNANSTRY_PROMPT_GUIDE.md
    """
    logger.info("="*80)
    logger.info("GENERATING COMPREHENSIVE SYNANSTRY ANALYSIS")
    logger.info("="*80)
    
    # Build structured prompt following the guide
    system_prompt = """You are an expert true sidereal astrologer specializing in synastry (relationship chart comparison). You analyze the compatibility, dynamics, and karmic connections between two people using both tropical and sidereal astrology, numerology, and Chinese zodiac.

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
- Consider both individual chart patterns AND their interaction"""
    
    # Format Person 1 data
    person1_text = f"""=== PERSON 1 ===

{person1_data.get('full_reading', 'Full reading not provided')}

=== CHART DATA ===
{json.dumps(person1_data.get('chart_data', {}), indent=2)}

=== PLANETARY PLACEMENTS ===
{chr(10).join(person1_data.get('planetary_placements', {}).get('sidereal', []))}

=== MAJOR ASPECTS ===
{chr(10).join(person1_data.get('major_aspects', [])[:10])}

=== NUMEROLOGY ===
{json.dumps(person1_data.get('numerology', {}), indent=2)}

=== CHINESE ZODIAC ===
{person1_data.get('chinese_zodiac', 'Not provided')}

=== END PERSON 1 ===
"""
    
    # Format Person 2 data
    person2_text = f"""=== PERSON 2 ===

{person2_data.get('full_reading', 'Full reading not provided')}

=== CHART DATA ===
{json.dumps(person2_data.get('chart_data', {}), indent=2)}

=== PLANETARY PLACEMENTS ===
{chr(10).join(person2_data.get('planetary_placements', {}).get('sidereal', []))}

=== MAJOR ASPECTS ===
{chr(10).join(person2_data.get('major_aspects', [])[:10])}

=== NUMEROLOGY ===
{json.dumps(person2_data.get('numerology', {}), indent=2)}

=== CHINESE ZODIAC ===
{person2_data.get('chinese_zodiac', 'Not provided')}

=== END PERSON 2 ===
"""
    
    user_prompt = f"""=== SYNANSTRY ANALYSIS REQUEST ===

I need a comprehensive synastry analysis comparing two people's complete astrological profiles. Please analyze their compatibility, relationship dynamics, and karmic connections using all available data: tropical placements, sidereal placements, aspects, numerology, and Chinese zodiac.

{person1_text}

{person2_text}

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

Please be thorough, specific, and reference the actual chart data throughout your analysis."""
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    
    logger.info("Calling Gemini API for comprehensive synastry analysis...")
    logger.info(f"Person 1 data length: {len(person1_text)} chars")
    logger.info(f"Person 2 data length: {len(person2_text)} chars")
    logger.info(f"Total prompt length: {len(user_prompt)} chars")
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=32768,  # Very high limit for comprehensive analysis
        temperature=0.7,
        call_label="synastry_analysis"
    )
    
    # Calculate cost
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"Synastry analysis completed")
    logger.info(f"API calls made: {step_calls}")
    logger.info(f"Cost: ${step_cost:.6f} USD")
    logger.info(f"Response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text
# ⚠️ PRESERVATION ZONE END - PROMPT FUNCTION: generate_comprehensive_synastry

