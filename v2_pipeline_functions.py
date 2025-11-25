# V2 Pipeline Functions - to be inserted into api.py
# These functions implement the premium 10-section reading structure

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

