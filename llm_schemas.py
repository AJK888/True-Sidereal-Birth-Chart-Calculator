"""
LLM Schema Definitions and Chart Serialization

This module defines:
1. JSON schemas for structured LLM outputs (especially Chart Overview & Core Themes)
2. Chart serialization functions to convert raw chart_data into LLM-friendly JSON
3. Pydantic models for validation and type safety

Example JSON Schema Output (Chart Overview):
{
    "themes": [
        {
            "title": "The Bridge Between Solitude and Expression",
            "headline_sentences": [
                "You carry a deep need for privacy and introspection that often conflicts with your drive to communicate and connect.",
                "This tension shapes how you process emotions and express your authentic self in relationships."
            ],
            "why_in_chart": {
                "text": "This comes from your Sidereal Sun in Scorpio vs Tropical Sun in Sagittarius, together with your Moon–Saturn square, and your Life Path 7 pattern of seeking deeper meaning.",
                "supporting_placements": ["Sidereal Sun in Scorpio", "Tropical Sun in Sagittarius", "Moon–Saturn square", "Life Path 7"]
            },
            "how_it_plays_out": {
                "text": "In relationships, this can look like withdrawing when you feel overwhelmed, then re-engaging with intense curiosity. At work, you might prefer deep, meaningful projects over surface-level collaboration.",
                "examples": [
                    "Withdrawing when overwhelmed, then re-engaging with curiosity",
                    "Preferring deep projects over surface-level collaboration"
                ]
            }
        }
    ],
    "synthesis": {
        "text": "These five themes interact to create a life path centered on...",
        "key_tension": "between security and risk",
        "growth_direction": "learning to trust your intuitive insights while taking calculated risks"
    }
}
"""

from typing import Dict, List, Optional, Any, TypedDict, Type
from pydantic import BaseModel, Field, field_validator, ConfigDict
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# JSON Schema for LLM Outputs
# ============================================================================

class WhyInChartSection(BaseModel):
    """Subsection explaining why a theme appears in the chart."""
    text: str = Field(..., description="2-4 sentences explicitly referencing key placements/aspects")
    supporting_placements: Optional[List[str]] = Field(
        default=None,
        description="List of specific placements/aspects mentioned (for validation)"
    )


class HowItPlaysOutSection(BaseModel):
    """Subsection with concrete real-life examples."""
    text: str = Field(..., description="1-2 concrete real-life examples")
    examples: Optional[List[str]] = Field(
        default=None,
        description="Extracted examples for validation"
    )


class CoreTheme(BaseModel):
    """A single core psychological or life theme."""
    title: str = Field(..., description="Short title in plain language (e.g., 'The Bridge Between Solitude and Expression')")
    headline_sentences: List[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Exactly 2 short headline sentences in everyday language"
    )
    why_in_chart: WhyInChartSection = Field(..., description="Why this theme shows up in the chart")
    how_it_plays_out: HowItPlaysOutSection = Field(..., description="How it tends to feel and play out")
    
    @field_validator('headline_sentences')
    @classmethod
    def validate_headline_count(cls, v):
        if len(v) != 2:
            raise ValueError(f"Must have exactly 2 headline sentences, got {len(v)}")
        return v


class SynthesisParagraph(BaseModel):
    """Synthesis paragraph tying all themes together."""
    text: str = Field(..., description="Paragraph showing how themes interact")
    key_tension: str = Field(..., description="One key inner tension (e.g., 'between security and risk')")
    growth_direction: str = Field(..., description="Key long-term growth direction from resolving the tension")


class ChartOverviewOutput(BaseModel):
    """Structured output for Chart Overview & Core Themes section."""
    themes: List[CoreTheme] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Exactly 5 core psychological or life themes"
    )
    synthesis: SynthesisParagraph = Field(..., description="Synthesis paragraph at the end")
    
    @field_validator('themes')
    @classmethod
    def validate_theme_count(cls, v):
        if len(v) != 5:
            raise ValueError(f"Must have exactly 5 themes, got {len(v)}")
        return v


# ============================================================================
# Global Reading Blueprint (Call 0)
# ============================================================================

class LifeAxis(BaseModel):
    """A core life axis representing a fundamental tension or dynamic."""
    name: str = Field(..., description="Short name for the axis (e.g., 'Self vs Other', 'Security vs Adventure')")
    description: str = Field(..., description="One-paragraph description of what this axis represents")
    chart_factors: List[str] = Field(..., description="List of specific chart placements/aspects that create this axis")
    immature_expression: str = Field(..., description="How this axis manifests when unresolved or immature")
    mature_expression: str = Field(..., description="How this axis manifests when integrated and mature")


class CoreThemeBullet(BaseModel):
    """A single theme bullet point for the top themes list."""
    label: str = Field(..., description="Category label (e.g., 'emotional', 'relationship', 'work', 'spiritual', 'shadow')")
    text: str = Field(..., description="The theme description text")


class SunMoonAscendantPlan(BaseModel):
    """Integration plan for Sun, Moon, and Ascendant."""
    body: str = Field(..., description="One of: Sun, Moon, Ascendant")
    sidereal_expression: str = Field(..., description="Short note on sidereal expression")
    tropical_expression: str = Field(..., description="Short note on tropical expression")
    integration_notes: str = Field(..., description="How to reconcile the two expressions in practice")


class PlanetaryClusterPlan(BaseModel):
    """Describes stelliums or functional clusters."""
    name: str = Field(..., description="Cluster name (e.g., 'Aquarius Stellium')")
    members: List[str] = Field(..., description="Bodies/points involved")
    description: str = Field(..., description="What the cluster means psychologically")
    implications: str = Field(..., description="Life areas impacted by this cluster")


class HouseDomainPlan(BaseModel):
    """Summaries for life domains or house groupings."""
    domain: str = Field(..., description="Life domain label (e.g., 'Relationships', 'Career')")
    summary: str = Field(..., description="Key insights for this domain")
    indicators: List[str] = Field(..., description="Relevant houses/planets/aspects supporting this summary")


class AspectHighlightPlan(BaseModel):
    """Key aspect highlights for later expansion."""
    title: str = Field(..., description="Short friendly label for the aspect dynamic")
    aspect: str = Field(..., description="Exact aspect description (e.g., 'Sun square Saturn')")
    meaning: str = Field(..., description="Core tension or talent described plainly")
    life_applications: List[str] = Field(..., description="Concrete scenarios or arenas where it shows up")


class PatternPlan(BaseModel):
    """Major aspect pattern descriptions."""
    name: str = Field(..., description="Pattern name (e.g., 'Grand Trine in Earth')")
    description: str = Field(..., description="Summary of why this matters")
    involved_points: List[str] = Field(..., description="Planets/points in the pattern")


class ThemedChapterPlan(BaseModel):
    """Outline for deep-dive thematic chapters."""
    chapter: str = Field(..., description="Chapter name (love, work, emotional life, spirituality, etc.)")
    thesis: str = Field(..., description="Core statement this chapter should argue")
    subtopics: List[str] = Field(..., description="Specific angles or questions to cover")
    supporting_factors: List[str] = Field(..., description="Chart factors that justify the thesis/subtopics")


class ShadowContradictionPlan(BaseModel):
    """Contradictions the reading must explore."""
    tension: str = Field(..., description="Name or describe the contradiction/tension")
    drivers: List[str] = Field(..., description="Chart factors driving this tension")
    integration_strategy: str = Field(..., description="How to work with or alchemize the contradiction")


class GrowthEdgePlan(BaseModel):
    """Concrete growth edges or practices."""
    focus: str = Field(..., description="What area the growth edge targets")
    description: str = Field(..., description="Why this is important now")
    practices: List[str] = Field(..., description="Actionable experiments or practices")


class FinalPrinciplesPlan(BaseModel):
    """Owner's manual principles and prompts."""
    principles: List[str] = Field(..., description="Guiding statements distilled from the chart")
    prompts: List[str] = Field(..., description="Reflection or action prompts tied to those principles")


class GlobalReadingBlueprint(BaseModel):
    """Global blueprint for the entire reading - provides coherence across all sections."""
    model_config = ConfigDict(populate_by_name=True, extra='ignore')  # Ignore extra fields from Gemini

    life_thesis: str = Field(..., description="One-paragraph life thesis summarizing the soul's core journey")
    central_paradox: Optional[str] = Field(None, description="The core paradox or tension that defines this chart")
    core_axes: List[LifeAxis] = Field(..., min_length=3, max_length=4, alias="core_axes", description="3-4 core life axes to prioritize")
    top_themes: List[CoreThemeBullet] = Field(..., min_length=5, max_length=5, description="Exactly 5 top themes (emotional, relationship, work, spiritual, shadow)")
    sun_moon_ascendant_plan: List[SunMoonAscendantPlan] = Field(..., description="Integration plan for Sun, Moon, Ascendant")
    planetary_clusters: List[PlanetaryClusterPlan] = Field(..., description="List of stelliums or functional planet clusters")
    houses_by_domain: List[HouseDomainPlan] = Field(..., description="House/domain summaries to reference later")
    aspect_highlights: List[AspectHighlightPlan] = Field(..., description="Top aspects to expand later")
    patterns: List[PatternPlan] = Field(..., description="Major aspect patterns that must be referenced")
    themed_chapters: List[ThemedChapterPlan] = Field(..., description="Plans for themed deep-dive chapters")
    shadow_contradictions: List[ShadowContradictionPlan] = Field(..., description="Key contradictions that need exploration")
    growth_edges: List[GrowthEdgePlan] = Field(..., description="Specific growth edges / experiments to include")
    final_principles_and_prompts: FinalPrinciplesPlan = Field(..., description="Owner's manual summary with actionable prompts")
    snapshot: Any = Field(..., description="Planning notes for the Snapshot section (key contradictions, drives, relational and shadow patterns to feature)")
    
    @field_validator('snapshot')
    @classmethod
    def validate_snapshot(cls, v):
        """Accept snapshot as string or list, convert list to string."""
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return str(v)
    
    @field_validator('core_axes')
    @classmethod
    def validate_axes_count(cls, v):
        if len(v) < 3 or len(v) > 4:
            raise ValueError(f"Must have 3-4 axes, got {len(v)}")
        return v
    
    @field_validator('top_themes')
    @classmethod
    def validate_themes_count(cls, v):
        if len(v) != 5:
            raise ValueError(f"Must have exactly 5 top themes, got {len(v)}")
        return v
    
    @property
    def axes(self) -> List[LifeAxis]:
        """Backward-compatible accessor for legacy code."""
        return self.core_axes


SNAPSHOT_PROMPT = """
EXACT OUTPUT FORMAT REQUIRED:

- [Your first insight about their behavior/pattern here]
- [Your second insight about their behavior/pattern here]
- [Your third insight about their behavior/pattern here]
- [Your fourth insight about their behavior/pattern here]
- [Your fifth insight about their behavior/pattern here]
- [Your sixth insight about their behavior/pattern here]
- [Your seventh insight about their behavior/pattern here]

CRITICAL FORMATTING RULES:
1. Start IMMEDIATELY with the first bullet "- " (no heading, no intro)
2. Each line MUST begin with "- " (dash followed by space)
3. Exactly 7 bullets total
4. NO paragraphs before or after the bullets
5. NO astrological terms (no planets, signs, houses, aspects, numerology)

WHAT MAKES A GOOD BULLET:
Good: "- You rehearse conversations in your head for hours, then say something completely different in the moment—and immediately regret it."
Bad: "You are a deep thinker who values communication." (no dash, too generic)

Good: "- When someone disappoints you, you don't get angry—you get quiet. And that quiet is louder than any argument."
Bad: "Your Moon in Scorpio makes you emotional." (uses astrology jargon)

Good: "- You've ended relationships not because you stopped loving them, but because you couldn't stop imagining how they'd eventually leave you first."
Bad: "You have trust issues in relationships." (too generic, not specific behavior)

CONTENT PRIORITIES:
1. The central paradox—the split between what they want and what they do
2. The repeating pattern they've promised themselves to stop
3. The thing they do in relationships that pushes people away while trying to keep them close
4. The fear that drives their ambition (or their avoidance)
5. The way they sabotage themselves when things are going well
6. What they're really thinking when they smile and say "I'm fine"
7. The version of themselves they show no one

TONE: Forensic intimacy. Like a therapist who's known them for years finally saying the thing out loud.
"""


# ============================================================================
# Chart Serialization for LLM Input
# ============================================================================

def serialize_chart_for_llm(chart_data: Dict[str, Any], unknown_time: bool) -> Dict[str, Any]:
    """
    Serialize chart data into a clean, LLM-friendly JSON structure.
    
    This function creates a stable, human-readable representation of the chart
    that's optimized for LLM consumption, removing redundant or low-value fields.
    
    Args:
        chart_data: Raw chart data from get_full_chart_data()
        unknown_time: Whether birth time is unknown (affects available data)
    
    Returns:
        A clean dict structure ready for JSON serialization
        
    Example output structure:
    {
        "metadata": {
            "unknown_time": false,
            "day_night_status": "day"
        },
        "core_identity": {
            "sidereal": {
                "sun": {"sign": "Capricorn", "degree": 25.5, "house": 10, "retrograde": false},
                "moon": {"sign": "Aries", "degree": 12.3, "house": 1, "retrograde": false},
                "ascendant": {"sign": "Aries", "degree": 0.0}
            },
            "tropical": {
                "sun": {"sign": "Aquarius", "degree": 5.2, "house": 11, "retrograde": false},
                "moon": {"sign": "Pisces", "degree": 18.7, "house": 2, "retrograde": false},
                "ascendant": {"sign": "Aries", "degree": 0.0}
            }
        },
        "planetary_placements": {
            "sidereal": [...],
            "tropical": [...]
        },
        "major_aspects": [...],
        "aspect_patterns": [...],
        "chart_analysis": {
            "sidereal": {"dominant_element": "Fire", "dominant_planet": "Mars"},
            "tropical": {"dominant_element": "Water", "dominant_planet": "Neptune"}
        },
        "numerology": {...},
        "nodes": {
            "sidereal": {"north_node": {"sign": "Leo", "degree": 15.2}, "south_node": {...}},
            "tropical": {...}
        }
    }
    """
    s_positions = {p['name']: p for p in chart_data.get('sidereal_major_positions', [])}
    t_positions = {p['name']: p for p in chart_data.get('tropical_major_positions', [])}
    s_extra = {p['name']: p for p in chart_data.get('sidereal_additional_points', [])}
    t_extra = {p['name']: p for p in chart_data.get('tropical_additional_points', [])}
    
    def extract_placement_info(pos_dict: Dict, body_name: str) -> Optional[Dict]:
        """Extract clean placement info from position dict."""
        body = pos_dict.get(body_name)
        if not body or not body.get('position') or body.get('position') == 'N/A':
            return None
        
        # Parse position string like "25°30' Capricorn" or "12°34' Aries"
        position_str = body.get('position', '')
        parts = position_str.split()
        sign = parts[-1] if parts else None
        
        # Extract degree (first number before °)
        degree = None
        if '°' in position_str:
            try:
                degree = float(position_str.split('°')[0])
            except (ValueError, IndexError):
                pass
        
        result = {
            "sign": sign,
            "degree": degree,
            "retrograde": body.get('retrograde', False)
        }
        
        # Add house if available and not unknown_time
        if not unknown_time and body.get('house') is not None:
            result["house"] = body.get('house')
        
        return result
    
    # Build serialized structure
    # NOTE: Personal identifiers (name, birth_date, birth_time, location) are excluded
    # to protect user privacy when sending data to AI models
    serialized = {
        "metadata": {
            "unknown_time": unknown_time,
            "day_night_status": chart_data.get('day_night_status', 'unknown')
        },
        "core_identity": {
            "sidereal": {},
            "tropical": {}
        },
        "planetary_placements": {
            "sidereal": [],
            "tropical": []
        },
        "major_aspects": [],
        "aspect_patterns": [],
        "chart_analysis": {
            "sidereal": {},
            "tropical": {}
        },
        "numerology": {},
        "nodes": {
            "sidereal": {},
            "tropical": {}
        }
    }
    
    # Core identity (Sun, Moon, Ascendant)
    for system in ['sidereal', 'tropical']:
        pos_dict = s_positions if system == 'sidereal' else t_positions
        extra_dict = s_extra if system == 'sidereal' else t_extra
        
        core = serialized["core_identity"][system]
        
        # Sun and Moon
        for body in ['Sun', 'Moon']:
            info = extract_placement_info(pos_dict, body)
            if info:
                core[body.lower()] = info
        
        # Ascendant (if known time)
        if not unknown_time:
            asc_info = extract_placement_info(extra_dict, 'Ascendant')
            if asc_info:
                core["ascendant"] = asc_info
    
    # All planetary placements
    major_bodies = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 
                    'Uranus', 'Neptune', 'Pluto', 'Chiron']
    additional_bodies = ['True Node', 'South Node', 'Lilith', 'Ceres', 'Pallas', 'Juno', 'Vesta']
    
    for system in ['sidereal', 'tropical']:
        pos_dict = s_positions if system == 'sidereal' else t_positions
        extra_dict = s_extra if system == 'sidereal' else t_extra
        
        placements = []
        for body in major_bodies + additional_bodies:
            info = extract_placement_info(pos_dict if body in major_bodies else extra_dict, body)
            if info:
                placements.append({
                    "body": body,
                    **info
                })
        
        serialized["planetary_placements"][system] = placements
    
    # Major aspects (top 20, sorted by score)
    aspects = chart_data.get('sidereal_aspects', [])
    if aspects:
        # Sort by score (descending), then orb (ascending)
        def parse_score(score_val):
            try:
                if isinstance(score_val, str):
                    return float(score_val)
                return float(score_val)
            except (ValueError, TypeError):
                return 0.0
        
        def parse_orb(orb_val):
            try:
                if isinstance(orb_val, str):
                    return abs(float(orb_val.replace('°', '').strip()))
                return abs(float(orb_val))
            except (ValueError, TypeError):
                return 999.0
        
        sorted_aspects = sorted(
            aspects,
            key=lambda a: (-parse_score(a.get('score', 0)), parse_orb(a.get('orb', 999)))
        )[:20]
        
        serialized["major_aspects"] = [
            {
                "p1": a.get('p1_name', ''),
                "p2": a.get('p2_name', ''),
                "type": a.get('type', ''),
                "orb": a.get('orb', ''),
                "score": a.get('score', '')
            }
            for a in sorted_aspects
        ]
    
    # Aspect patterns
    patterns = chart_data.get('sidereal_aspect_patterns', [])
    serialized["aspect_patterns"] = [
        p.get('description', '') for p in patterns
    ]
    
    # Chart analysis (dominant element, planet, etc.)
    s_analysis = chart_data.get('sidereal_chart_analysis', {})
    t_analysis = chart_data.get('tropical_chart_analysis', {})
    
    serialized["chart_analysis"]["sidereal"] = {
        "dominant_element": s_analysis.get('dominant_element'),
        "dominant_planet": s_analysis.get('dominant_planet'),
        "element_distribution": s_analysis.get('element_distribution', {}),
        "modality_distribution": s_analysis.get('modality_distribution', {})
    }
    
    serialized["chart_analysis"]["tropical"] = {
        "dominant_element": t_analysis.get('dominant_element'),
        "dominant_planet": t_analysis.get('dominant_planet'),
        "element_distribution": t_analysis.get('element_distribution', {}),
        "modality_distribution": t_analysis.get('modality_distribution', {})
    }
    
    # Numerology
    numerology = chart_data.get('numerology_analysis') or {}
    name_numerology = numerology.get('name_numerology') or {}
    serialized["numerology"] = {
        "life_path_number": numerology.get('life_path_number'),
        "day_number": numerology.get('day_number'),
        "lucky_number": numerology.get('lucky_number'),
        "expression_number": name_numerology.get('expression_number'),
        "soul_urge_number": name_numerology.get('soul_urge_number'),
        "personality_number": name_numerology.get('personality_number')
    }
    
    # Nodes
    for system in ['sidereal', 'tropical']:
        pos_dict = s_positions if system == 'sidereal' else t_positions
        
        nn_info = extract_placement_info(pos_dict, 'True Node')
        sn_info = extract_placement_info(pos_dict, 'South Node')
        
        if nn_info:
            serialized["nodes"][system]["north_node"] = nn_info
        if sn_info:
            serialized["nodes"][system]["south_node"] = sn_info
    
    # Chinese Zodiac
    if chart_data.get('chinese_zodiac'):
        serialized["chinese_zodiac"] = chart_data.get('chinese_zodiac')
    
    return serialized


def format_serialized_chart_for_prompt(serialized_chart: Dict[str, Any]) -> str:
    """
    Format the serialized chart as a human-readable string for LLM prompts.
    
    This creates a clean text representation that's easier for LLMs to parse
    than raw JSON, while maintaining structure.
    """
    lines = []
    
    # Metadata
    # NOTE: Personal identifiers (name, birth_date, birth_time, location) are excluded
    # to protect user privacy when sending data to AI models
    meta = serialized_chart.get('metadata', {})
    lines.append("=== CHART METADATA ===")
    lines.append(f"Unknown Time: {meta.get('unknown_time', False)}")
    lines.append("")
    
    # Core Identity
    lines.append("=== CORE IDENTITY ===")
    for system in ['sidereal', 'tropical']:
        lines.append(f"\n{system.upper()}:")
        core = serialized_chart.get('core_identity', {}).get(system, {})
        for body in ['sun', 'moon', 'ascendant']:
            if body in core:
                info = core[body]
                house_str = f", House {info['house']}" if 'house' in info else ""
                retro_str = " (Rx)" if info.get('retrograde') else ""
                lines.append(f"  {body.capitalize()}: {info.get('sign')} {info.get('degree', '')}°{house_str}{retro_str}")
    lines.append("")
    
    # Chart Analysis
    lines.append("=== CHART ANALYSIS ===")
    for system in ['sidereal', 'tropical']:
        analysis = serialized_chart.get('chart_analysis', {}).get(system, {})
        if analysis.get('dominant_element'):
            lines.append(f"{system.upper()} Dominant Element: {analysis['dominant_element']}")
        if analysis.get('dominant_planet'):
            lines.append(f"{system.upper()} Dominant Planet: {analysis['dominant_planet']}")
    lines.append("")
    
    # Major Aspects (top 10)
    aspects = serialized_chart.get('major_aspects', [])[:10]
    if aspects:
        lines.append("=== MAJOR ASPECTS (Top 10) ===")
        for a in aspects:
            lines.append(f"  {a.get('p1')} {a.get('type')} {a.get('p2')} (orb: {a.get('orb')}, score: {a.get('score')})")
        lines.append("")
    
    # Aspect Patterns
    patterns = serialized_chart.get('aspect_patterns', [])
    if patterns:
        lines.append("=== ASPECT PATTERNS ===")
        for p in patterns:
            lines.append(f"  - {p}")
        lines.append("")
    
    # Numerology
    numerology = serialized_chart.get('numerology', {})
    if any(numerology.values()):
        lines.append("=== NUMEROLOGY ===")
        if numerology.get('life_path_number'):
            lines.append(f"  Life Path: {numerology['life_path_number']}")
        if numerology.get('day_number'):
            lines.append(f"  Day Number: {numerology['day_number']}")
        if numerology.get('expression_number'):
            lines.append(f"  Expression: {numerology['expression_number']}")
        lines.append("")
    
    # Nodes
    lines.append("=== NODES ===")
    for system in ['sidereal', 'tropical']:
        nodes = serialized_chart.get('nodes', {}).get(system, {})
        if nodes.get('north_node'):
            nn = nodes['north_node']
            lines.append(f"{system.upper()} North Node: {nn.get('sign')} {nn.get('degree', '')}°")
    lines.append("")
    
    return "\n".join(lines)


def parse_json_response(response_text: str, schema_class: Type[BaseModel]) -> Optional[BaseModel]:
    """
    Parse LLM JSON response and validate against schema.
    
    Handles common JSON formatting issues:
    - JSON wrapped in markdown code blocks
    - Trailing commas
    - Comments
    - Multiple JSON objects
    
    Args:
        response_text: Raw text response from LLM
        schema_class: Pydantic model class to validate against
    
    Returns:
        Parsed and validated model instance, or None if parsing fails
    """
    try:
        # Try to extract JSON from markdown code blocks
        if '```json' in response_text:
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            if end != -1:
                response_text = response_text[start:end].strip()
        elif '```' in response_text:
            start = response_text.find('```') + 3
            end = response_text.find('```', start)
            if end != -1:
                response_text = response_text[start:end].strip()
        
        # Try to find JSON object boundaries
        if '{' in response_text:
            start = response_text.find('{')
            # Find matching closing brace
            brace_count = 0
            end = -1
            for i, char in enumerate(response_text[start:], start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            if end != -1:
                response_text = response_text[start:end]
        
        # Clean up common issues
        response_text = response_text.strip()
        # Remove trailing commas (simple approach)
        import re
        response_text = re.sub(r',\s*}', '}', response_text)
        response_text = re.sub(r',\s*]', ']', response_text)
        
        # Parse JSON
        data = json.loads(response_text)
        
        # Validate against schema
        return schema_class(**data)
        
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parsing error: {e}. Response text: {response_text[:500]}")
        return None
    except Exception as e:
        logger.warning(f"Schema validation error: {e}. Response text: {response_text[:500]}")
        return None

