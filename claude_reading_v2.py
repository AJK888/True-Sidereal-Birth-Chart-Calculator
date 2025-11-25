"""
V2 Premium Reading Pipeline

This module implements a comprehensive 10-section reading structure using many smaller
Claude API calls to avoid truncation. Each section is generated separately and then
polished individually for maximum quality and coherence.
"""

import logging
import json
import os
from typing import Dict, Any

# Import shared components from api.py
from api import LLMClient, calculate_claude_cost, AI_MODE, CLAUDE_API_KEY

# Import chart serialization and schema utilities
from llm_schemas import (
    GlobalReadingBlueprint,
    serialize_chart_for_llm,
    format_serialized_chart_for_prompt,
    parse_json_response
)

# Setup logger
logger = logging.getLogger(__name__)


# ============================================================================
# Call 0: Global Blueprint
# ============================================================================

async def call0_global_blueprint(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    unknown_time: bool
) -> Dict[str, Any]:
    """
    Call 0: Produce a structured JSON blueprint for the entire reading.
    Includes life thesis, 3 core life axes, and top 5 themes.
    """
    logger.info("="*60)
    logger.info("CALL 0: Global Blueprint")
    logger.info("="*60)
    
    system_prompt = """You are a master astrological planner. Your ONLY job is to analyze the chart and produce a structured JSON blueprint.

You must output ONLY valid JSON matching this exact structure:
{
  "life_thesis": "One paragraph summarizing the soul's core journey...",
  "axes": [
    {
      "name": "Axis name",
      "description": "One paragraph description...",
      "chart_factors": ["placement1", "placement2"],
      "immature_expression": "How it shows when unresolved...",
      "mature_expression": "How it shows when integrated..."
    }
  ],
  "top_themes": [
    {
      "label": "emotional",
      "text": "Theme description..."
    },
    {
      "label": "relationship",
      "text": "Theme description..."
    },
    {
      "label": "work",
      "text": "Theme description..."
    },
    {
      "label": "spiritual",
      "text": "Theme description..."
    },
    {
      "label": "shadow",
      "text": "Theme description..."
    }
  ]
}

You must output exactly 3 axes and exactly 5 top themes (emotional, relationship, work, spiritual, shadow).
Your response must start with { and end with }. No markdown, no explanations outside the JSON."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Note:** {"Birth time is unknown, so house placements and Ascendant/MC are unavailable." if unknown_time else "Full chart data including houses and angles is available."}

**Your Task:**
Analyze this chart and produce a global blueprint JSON with:
1. **life_thesis**: One paragraph that captures the soul's core journey and purpose
2. **axes**: Exactly 3 fundamental life axes (tensions/dynamics) that shape this person's experience
3. **top_themes**: Exactly 5 theme bullets covering: emotional patterns, relationship dynamics, work/vocation, spiritual/meaning, shadow/growth areas

Each axis must be grounded in specific chart placements. Each theme must be specific to this chart, not generic.

Output ONLY the JSON object. Start with {{ and end with }}."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.5,
        max_output_tokens=4096,
        call_label="call0_global_blueprint"
    )
    
    # Parse JSON response
    blueprint_parsed = parse_json_response(response_text, GlobalReadingBlueprint)
    
    if blueprint_parsed:
        logger.info("Call 0 completed successfully - parsed JSON blueprint")
        return {"parsed": blueprint_parsed, "raw_text": response_text}
    else:
        logger.warning("Call 0 JSON parsing failed, using raw text")
        return {"parsed": None, "raw_text": response_text}


# ============================================================================
# Section Generation Calls
# ============================================================================

async def call1_cover_and_orientation(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 1: Cover & Orientation
    Generates title block, orientation paragraphs, and disclaimer.
    """
    logger.info("="*60)
    logger.info("CALL 1: Cover and Orientation")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert astrological consultant. Your job is to create an inviting, clear introduction to the reading.

Explain what this reading is, how to use it, and include a clear disclaimer. Do NOT interpret placements yet; just frame the experience.

Tone: Professional, warm, psychologically literate. Use second person ("you")."""
    
    blueprint_context = ""
    if blueprint.get("parsed"):
        blueprint_context = f"\n**Life Thesis (for context):**\n{blueprint['parsed'].life_thesis}\n"
    elif blueprint.get("raw_text"):
        blueprint_context = f"\n**Blueprint Context:**\n{blueprint['raw_text'][:500]}\n"
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}
{blueprint_context}

**Your Task:**
Write the Cover & Orientation section with these subsections:

**Title:**
[Create a personalized title for this reading, e.g., "True Sidereal Birth Chart Report for [Name]"]

**Orientation:**
Write 2-3 paragraphs explaining:
- What this reading is (a comprehensive astrological synthesis)
- How to use it (read through, reflect, return to specific sections)
- What makes it unique (true sidereal + tropical comparison, deep psychological focus)

**Disclaimer:**
Write 1 paragraph with a clear disclaimer about astrology being for self-reflection and not deterministic prediction.

Use plain text headings (no markdown). Do not interpret specific placements yet."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=2000,
        call_label="call1_cover_and_orientation"
    )
    
    logger.info("Call 1 completed successfully")
    return response_text


async def call2_chart_overview_and_core_themes(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 2: Chart Overview & Core Themes
    Uses the GlobalReadingBlueprint to write life thesis, 3 axes, and top 5 themes.
    """
    logger.info("="*60)
    logger.info("CALL 2: Chart Overview and Core Themes")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer. Follow the blueprint exactly to create a coherent overview.

Tone Guidelines:
- Sound like a psychologically literate consultant speaking to an intelligent client
- Favor clear, concrete language over mystical phrasing
- Use second person ("you") throughout
- Avoid hedging; prefer confident but non-absolute phrases like "you tend to" or "you are likely to"

**CRITICAL RULE:** Base your reading *only* on the analysis provided. Do not invent placements."""
    
    blueprint_json = ""
    if blueprint.get("parsed"):
        blueprint_json = json.dumps(blueprint['parsed'].model_dump(), indent=2)
    elif blueprint.get("raw_text"):
        blueprint_json = blueprint['raw_text']
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Global Blueprint (follow this exactly):**
{blueprint_json}

**Your Task:**
Write the "Chart Overview and Core Themes" section using the blueprint:

1. **Life Thesis**
Use the life_thesis from the blueprint as the opening paragraph.

2. **Three Life Axes**
For each of the 3 axes in the blueprint, write:
- The axis name as a heading
- 1-2 paragraphs explaining:
  - Which placements create this axis (reference chart_factors)
  - How it feels in daily life
  - Immature vs mature expression (use the blueprint's immature_expression and mature_expression)

3. **Top 5 Themes**
Create a bullet list based on the top_themes from the blueprint. Each bullet should expand on the theme text provided.

{"**Note:** Do not mention houses, Ascendant, MC, or Chart Ruler as birth time is unknown." if unknown_time else ""}

Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=6000,
        call_label="call2_chart_overview_and_core_themes"
    )
    
    logger.info("Call 2 completed successfully")
    return response_text


async def call3_foundational_pillars(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 3: Foundational Pillars (Sun, Moon, Ascendant)
    """
    logger.info("="*60)
    logger.info("CALL 3: Foundational Pillars")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing detailed planetary interpretations.

Tone: Psychologically literate, concrete, second person. Emphasize behavioral examples.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    blueprint_context = ""
    if blueprint.get("parsed"):
        blueprint_context = f"\n**Life Thesis (for coherence):**\n{blueprint['parsed'].life_thesis}\n"
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}
{blueprint_context}

**Your Task:**
Write the "Foundational Pillars" section with these subsections:

**Sun**
- Sidereal Interpretation (1 paragraph)
- Tropical Interpretation (1 paragraph)
- Integration (1 paragraph connecting both)

**Moon**
- Sidereal Interpretation (1 paragraph)
- Tropical Interpretation (1 paragraph)
- Integration (1 paragraph connecting both)

{"**Ascendant**\nSince birth time is unknown, write a short note explaining why Ascendant analysis is omitted and how the reading focuses on sign-level patterns instead." if unknown_time else "**Ascendant**\n- Sidereal Interpretation (1 paragraph)\n- Tropical Interpretation (1 paragraph)\n- Integration (1 paragraph connecting both)"}

For each planet, include concrete behavioral examples. Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=6000,
        call_label="call3_foundational_pillars"
    )
    
    logger.info("Call 3 completed successfully")
    return response_text


async def call4_personal_planets(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 4.1: Personal Planets (Mercury, Venus, Mars)
    """
    logger.info("="*60)
    logger.info("CALL 4: Personal Planets")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing detailed planetary interpretations.

Tone: Psychologically literate, concrete, second person.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Your Task:**
Write the "Personal Planets" section covering Mercury, Venus, and Mars.

For each planet:
- Sidereal Interpretation (1 paragraph)
- Tropical Interpretation (1 paragraph)
- Integration (1 paragraph connecting both)

Also include 1-2 paragraphs on any stellium or cluster if present (3+ planets in same sign).

Emphasize concrete behavioral examples. Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=6000,
        call_label="call4_personal_planets"
    )
    
    logger.info("Call 4 completed successfully")
    return response_text


async def call5_social_planets(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 4.2: Social Planets (Jupiter, Saturn)
    """
    logger.info("="*60)
    logger.info("CALL 5: Social Planets")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing detailed planetary interpretations.

Tone: Psychologically literate, concrete, second person. Emphasize expansion vs discipline in both soul and real-world terms.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Your Task:**
Write the "Social Planets" section covering Jupiter and Saturn.

For each planet:
- Sidereal Interpretation (1 paragraph)
- Tropical Interpretation (1 paragraph)
- Integration (1 paragraph connecting both)

Emphasize how expansion (Jupiter) and discipline (Saturn) interact in both soul-level and real-world terms. Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=6000,
        call_label="call5_social_planets"
    )
    
    logger.info("Call 5 completed successfully")
    return response_text


async def call6_outer_and_nodes(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 4.3: Outer Planets & Nodes (Uranus, Neptune, Pluto, Chiron, Nodes, key asteroids)
    """
    logger.info("="*60)
    logger.info("CALL 6: Outer Planets and Nodes")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing detailed planetary interpretations.

Tone: More mythic and psychological for outer planets. For Nodes, emphasize the 'From X to Y' life arc.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Your Task:**
Write the "Outer Planets and Nodes" section covering:
- Uranus, Neptune, Pluto, Chiron
- Nodes (True Node, South Node) - provide a detailed 'From X to Y' life arc
- Key asteroids if present (Ceres, Pallas, Juno, Vesta, Lilith)

For each planet/point:
- Sidereal Interpretation (1 paragraph)
- Tropical Interpretation (1 paragraph)
- Integration (1 paragraph connecting both)

For Nodes specifically, write a detailed narrative of the soul's journey from South Node patterns to North Node growth.

Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=6000,
        call_label="call6_outer_and_nodes"
    )
    
    logger.info("Call 6 completed successfully")
    return response_text


async def call7_houses_and_domains(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 5: Houses & Life Domains
    """
    logger.info("="*60)
    logger.info("CALL 7: Houses and Life Domains")
    logger.info("="*60)
    
    if unknown_time:
        # Return a short explanation instead
        return """**Houses and Life Domains**

Since your birth time is unknown, we cannot calculate precise house placements. House analysis requires the exact moment of birth to determine which signs occupy each of the 12 life domains.

However, the sign-level and aspect-level patterns in your chart still reveal important themes across life areas. The planetary placements and aspects discussed throughout this reading apply to all areas of life, regardless of house emphasis."""
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing about life domains.

Tone: Psychologically literate, concrete, second person.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Your Task:**
Write the "Houses and Life Domains" section, grouped by life domains:

- Self & Identity (1st house)
- Home & Family (4th house)
- Creative Expression & Pleasure (5th house)
- Work & Health (6th house)
- Relationships & Intimacy (7th house)
- Beliefs & Purpose (9th house)
- Career & Reputation (10th house)
- Community & Friends (11th house)
- Spirituality & Endings (12th house)

For each domain, write 1-2 paragraphs focusing on:
- The most active houses, angles, and rulers
- How planetary energy manifests in that life area

Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=6000,
        call_label="call7_houses_and_domains"
    )
    
    logger.info("Call 7 completed successfully")
    return response_text


async def call8_aspects_and_patterns(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any]
) -> str:
    """
    Section 6: Aspects & Patterns
    """
    logger.info("="*60)
    logger.info("CALL 8: Aspects and Patterns")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing about aspects and patterns.

Tone: Psychologically literate, concrete, second person. Explicitly connect back to axes/themes from blueprint where relevant.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    blueprint_context = ""
    if blueprint.get("parsed"):
        axes_summary = "\n".join([f"- {axis.name}: {axis.description[:100]}..." for axis in blueprint['parsed'].axes])
        blueprint_context = f"\n**Life Axes (for coherence):**\n{axes_summary}\n"
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}
{blueprint_context}

**Your Task:**
Write the "Aspects and Patterns" section:

1. **Most Influential Aspects**
Analyze the 5-10 tightest aspects from the chart. For each aspect, write 1-2 paragraphs explaining:
- The core tension, strength, or pattern
- How it shows up in real life
- Connection to life axes/themes where relevant

2. **Aspect Patterns**
For each major pattern (T-squares, Grand Trines, Stelliums, Yods, Grand Crosses):
- Shadow paragraph (how it manifests when unresolved)
- Gift paragraph (the positive potential)
- Integration paragraph (how to work with it)

Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=8000,
        call_label="call8_aspects_and_patterns"
    )
    
    logger.info("Call 8 completed successfully")
    return response_text


async def call9_themes_love_and_relationships(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 7.1: Themed Chapter - Love and Relationships
    """
    logger.info("="*60)
    logger.info("CALL 9: Themes - Love and Relationships")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing a themed chapter.

Use everything (chart_summary + blueprint) to synthesize a comprehensive chapter on love and relationships.

Tone: Psychologically literate, concrete, second person.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Your Task:**
Write a comprehensive "Love and Relationships" themed chapter.

Focus on:
- Venus, Mars, Moon placements
- {"5th and 7th house themes (if relevant)" if not unknown_time else "relationship-oriented aspects and patterns"}
- Juno, Nodes, major relationship aspects

Synthesize how these elements work together to create relationship patterns, needs, challenges, and gifts.

Write several pages of detailed analysis. Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=8000,
        call_label="call9_themes_love_and_relationships"
    )
    
    logger.info("Call 9 completed successfully")
    return response_text


async def call10_themes_work_money_vocation(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 7.2: Themed Chapter - Work, Money, Vocation
    """
    logger.info("="*60)
    logger.info("CALL 10: Themes - Work, Money, Vocation")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing a themed chapter.

Use everything (chart_summary + blueprint) to synthesize a comprehensive chapter on work, money, and vocation.

Tone: Psychologically literate, concrete, second person.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Your Task:**
Write a comprehensive "Work, Money, and Vocation" themed chapter.

Focus on:
- {"10th house (career), 2nd house (money), 6th house (work)" if not unknown_time else "Saturn, Jupiter, and work-oriented aspects"}
- Saturn, Jupiter placements
- Mercury, Mars (communication and drive in work)
- Major aspects affecting career/money themes

Synthesize how these elements work together to create work patterns, money relationship, vocational calling, and career challenges/gifts.

Write several pages of detailed analysis. Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=8000,
        call_label="call10_themes_work_money_vocation"
    )
    
    logger.info("Call 10 completed successfully")
    return response_text


async def call11_themes_emotional_family_healing(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 7.3: Themed Chapter - Emotional Life, Family, Healing
    """
    logger.info("="*60)
    logger.info("CALL 11: Themes - Emotional Life, Family, Healing")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing a themed chapter.

Use everything (chart_summary + blueprint) to synthesize a comprehensive chapter on emotional life, family, and healing.

Tone: Psychologically literate, concrete, second person.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Your Task:**
Write a comprehensive "Emotional Life, Family, and Healing" themed chapter.

Focus on:
- Moon, {"4th house (home/family)" if not unknown_time else "family-oriented aspects"}
- Chiron (wounds and healing)
- Emotional aspects and patterns
- Family dynamics and ancestral patterns

Synthesize how these elements work together to create emotional patterns, family dynamics, healing needs, and growth opportunities.

Write several pages of detailed analysis. Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=8000,
        call_label="call11_themes_emotional_family_healing"
    )
    
    logger.info("Call 11 completed successfully")
    return response_text


async def call12_themes_spiritual_path_meaning(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """
    Section 7.4: Themed Chapter - Spiritual Path and Meaning
    """
    logger.info("="*60)
    logger.info("CALL 12: Themes - Spiritual Path and Meaning")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing a themed chapter.

Use everything (chart_summary + blueprint) to synthesize a comprehensive chapter on spiritual path and meaning.

Tone: Psychologically literate, concrete, second person.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

**Your Task:**
Write a comprehensive "Spiritual Path and Meaning" themed chapter.

Focus on:
- {"9th house (beliefs), 12th house (spirituality)" if not unknown_time else "Neptune, Jupiter, and spiritual aspects"}
- Neptune, Jupiter placements
- Nodes (karmic direction)
- Spiritual aspects and patterns

Synthesize how these elements work together to create spiritual needs, meaning-making patterns, and the soul's deeper purpose.

Write several pages of detailed analysis. Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=8000,
        call_label="call12_themes_spiritual_path_meaning"
    )
    
    logger.info("Call 12 completed successfully")
    return response_text


async def call13_shadow_and_growth(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any]
) -> str:
    """
    Section 8: Shadow, Contradictions & Growth Edges
    """
    logger.info("="*60)
    logger.info("CALL 13: Shadow and Growth")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing about shadow and growth.

Tone: Psychologically literate, compassionate but direct, second person.

Force yourself to name exactly where each contradiction comes from in the chart (axes, aspects, planets).

Growth prescriptions must be chart-specific, not generic advice.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    blueprint_context = ""
    if blueprint.get("parsed"):
        axes_info = "\n".join([f"- {axis.name}: {axis.description}" for axis in blueprint['parsed'].axes])
        blueprint_context = f"\n**Life Axes (for contradictions):**\n{axes_info}\n"
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}
{blueprint_context}

**Your Task:**
Write the "Shadow, Contradictions & Growth Edges" section:

1. **Core Contradictions**
Identify 3-5 core contradictions in this chart. For each:
- Name exactly which placements/aspects/axes create it (1-2 paragraphs)
- Explain how it manifests as inner tension

2. **Defense Mechanisms / Default Coping Patterns**
Describe 3-5 default coping patterns that emerge from these contradictions.

3. **Growth Prescriptions**
Provide 5-10 specific growth prescriptions tied directly to this chart. Each must:
- Reference specific placements/aspects
- Be actionable and chart-specific
- Not be generic self-help advice

Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=8000,
        call_label="call13_shadow_and_growth"
    )
    
    logger.info("Call 13 completed successfully")
    return response_text


async def call14_timing_stub(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any]
) -> str:
    """
    Section 9: Timing (stub for future transit/progression logic)
    """
    logger.info("="*60)
    logger.info("CALL 14: Timing (Stub)")
    logger.info("="*60)
    
    return """**Timing and Cycles**

This reading focuses on your natal blueprint—the core patterns and potentials encoded in your birth chart. 

Future timing analysis (transits, progressions, and solar returns) would show how these patterns activate and evolve over time. For now, this reading provides the foundation: understanding who you are at the core, so you can recognize and work with these patterns as they unfold in your life.

To explore timing, consider consulting with an astrologer who can analyze current transits and progressions in relation to your natal chart."""


async def call15_final_integration(
    llm: LLMClient,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any]
) -> str:
    """
    Section 10: Final Integration / Owner's Manual
    """
    logger.info("="*60)
    logger.info("CALL 15: Final Integration")
    logger.info("="*60)
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer writing a final integration.

Tone: Psychologically literate, empowering, second person.

Explicitly reference life thesis and axes from blueprint, and main patterns from the reading.

**CRITICAL RULE:** Base your reading *only* on the analysis provided."""
    
    blueprint_context = ""
    if blueprint.get("parsed"):
        blueprint_context = f"""
**Life Thesis:**
{blueprint['parsed'].life_thesis}

**Life Axes:**
{chr(10).join([f"- {axis.name}: {axis.description}" for axis in blueprint['parsed'].axes])}
"""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}
{blueprint_context}

**Your Task:**
Write the "Final Integration / Owner's Manual" section:

1. **If You Remember Nothing Else...**
Write 1-2 paragraphs distilling the absolute essence of this chart and reading.

2. **Guiding Principles**
Provide 3-5 guiding principles for living with this chart's patterns.

3. **Reflection Questions**
Provide ~10 reflection questions that help the reader engage deeply with their chart.

4. **Closing Validation**
Write a closing paragraph that validates the reader's journey and potential.

Explicitly reference the life thesis and main axes throughout. Use plain text headings (no markdown)."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=6000,
        call_label="call15_final_integration"
    )
    
    logger.info("Call 15 completed successfully")
    return response_text


# ============================================================================
# Section Polishing
# ============================================================================

async def polish_section(
    llm: LLMClient,
    section_text: str,
    section_label: str
) -> str:
    """
    Polishes tone, flow, and clarity for ONE section.
    Does not change meaning, structure, or headings.
    """
    logger.info(f"Polishing section: {section_label}")
    
    system_prompt = """You are a careful editor polishing astrological writing.

Your job is to improve tone, flow, and clarity WITHOUT changing:
- Meaning or content
- Structure or headings
- Specific placements or interpretations

Make the writing smoother, more engaging, and clearer while preserving all astrological accuracy."""
    
    user_prompt = f"""**Section to Polish:**
{section_text}

**Your Task:**
Polish this section for tone, flow, and clarity. Keep all headings, structure, and content exactly as is. Only improve the writing quality."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.3,
        max_output_tokens=6000,
        call_label=f"polish_{section_label.lower().replace(' ', '_')}"
    )
    
    return response_text


# ============================================================================
# Main Orchestrator
# ============================================================================

async def get_claude_reading_v2(chart_data: dict, unknown_time: bool) -> str:
    """
    Generate comprehensive astrological reading using the premium 10-section structure
    with many smaller Claude API calls to avoid truncation.
    
    Pipeline:
    - Call 0: Global Blueprint (JSON planner)
    - Calls 1-15: Section generators
    - Polish each section individually
    - Combine into final reading
    """
    if not CLAUDE_API_KEY and AI_MODE != "stub":
        logger.error("Claude API key not configured - AI reading unavailable")
        raise Exception("Claude API key not configured. AI reading is unavailable.")

    logger.info("="*60)
    logger.info("Starting Claude reading generation (V2 Premium Pipeline)...")
    logger.info(f"AI_MODE: {AI_MODE}")
    logger.info(f"Unknown time: {unknown_time}")
    logger.info("="*60)
    
    # Initialize LLM client for token/cost tracking
    llm = LLMClient()
    
    try:
        # Serialize chart data for LLM consumption
        serialized_chart = serialize_chart_for_llm(chart_data, unknown_time=unknown_time)
        chart_summary = format_serialized_chart_for_prompt(serialized_chart)
        
        # Call 0: Global Blueprint
        blueprint = await call0_global_blueprint(
            llm, serialized_chart, chart_summary, unknown_time
        )
        
        # Generate all sections
        logger.info("="*60)
        logger.info("Generating all reading sections...")
        logger.info("="*60)
        
        sec1 = await call1_cover_and_orientation(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec2 = await call2_chart_overview_and_core_themes(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec3 = await call3_foundational_pillars(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec4 = await call4_personal_planets(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec5 = await call5_social_planets(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec6 = await call6_outer_and_nodes(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec7 = await call7_houses_and_domains(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec8 = await call8_aspects_and_patterns(llm, serialized_chart, chart_summary, blueprint)
        sec9 = await call9_themes_love_and_relationships(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec10 = await call10_themes_work_money_vocation(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec11 = await call11_themes_emotional_family_healing(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec12 = await call12_themes_spiritual_path_meaning(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        sec13 = await call13_shadow_and_growth(llm, serialized_chart, chart_summary, blueprint)
        sec14 = await call14_timing_stub(llm, serialized_chart, chart_summary, blueprint)
        sec15 = await call15_final_integration(llm, serialized_chart, chart_summary, blueprint)
        
        # Polish each section
        logger.info("="*60)
        logger.info("Polishing all sections...")
        logger.info("="*60)
        
        p1 = await polish_section(llm, sec1, "Cover and Orientation")
        p2 = await polish_section(llm, sec2, "Chart Overview and Core Themes")
        p3 = await polish_section(llm, sec3, "Foundational Pillars")
        p4 = await polish_section(llm, sec4, "Personal Planets")
        p5 = await polish_section(llm, sec5, "Social Planets")
        p6 = await polish_section(llm, sec6, "Outer Planets and Nodes")
        p7 = await polish_section(llm, sec7, "Houses and Life Domains")
        p8 = await polish_section(llm, sec8, "Aspects and Patterns")
        p9 = await polish_section(llm, sec9, "Themes - Love and Relationships")
        p10 = await polish_section(llm, sec10, "Themes - Work Money Vocation")
        p11 = await polish_section(llm, sec11, "Themes - Emotional Family Healing")
        p12 = await polish_section(llm, sec12, "Themes - Spiritual Path Meaning")
        p13 = await polish_section(llm, sec13, "Shadow and Growth")
        p14 = await polish_section(llm, sec14, "Timing")
        p15 = await polish_section(llm, sec15, "Final Integration")
        
        # Combine all polished sections
        final_reading = f"""{p1}

{p2}

{p3}

{p4}

{p5}

{p6}

{p7}

{p8}

{p9}

{p10}

{p11}

{p12}

{p13}

{p14}

{p15}"""
        
        # Log final cost summary
        summary = llm.get_summary()
        logger.info(">>> ENTERED get_claude_reading_v2 AND ABOUT TO LOG COST <<<")
        cost_info = calculate_claude_cost(summary['total_prompt_tokens'], summary['total_completion_tokens'])
        logger.info(f"=== CLAUDE API COST SUMMARY (V2) ===")
        logger.info(f"Total Calls: {summary['call_count']}")
        logger.info(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        logger.info(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        logger.info(f"Total Tokens: {summary['total_tokens']:,}")
        logger.info(f"Input Cost: ${cost_info['input_cost_usd']:.6f}")
        logger.info(f"Output Cost: ${cost_info['output_cost_usd']:.6f}")
        logger.info(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f}")
        logger.info("=" * 50)
        # Also print to stdout as fallback
        print(f"\n{'='*60}")
        print(f"CLAUDE API COST SUMMARY (V2)")
        print(f"Total Calls: {summary['call_count']}")
        print(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        print(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        print(f"Total Tokens: {summary['total_tokens']:,}")
        print(f"Input Cost: ${cost_info['input_cost_usd']:.6f}")
        print(f"Output Cost: ${cost_info['output_cost_usd']:.6f}")
        print(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f}")
        print(f"{'='*60}\n")
        
        return final_reading
        
    except Exception as e:
        logger.error(f"Error during Claude reading generation (V2): {e}", exc_info=True)
        raise Exception(f"An error occurred while generating the detailed AI reading: {e}")

