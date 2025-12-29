"""
⚠️ PRESERVATION ZONE - LLM Service

This module contains all LLM-related functionality including:
- Gemini3Client (exact copy from api.py)
- All prompt functions (g0, g1, g2, g3, g4, generate_snapshot_reading, etc.)
- Helper functions for chart serialization and formatting

CRITICAL: All prompts in this file are PRESERVED EXACTLY as they were in api.py.
DO NOT modify prompt text, structure, or formatting.
Only allowed changes: moving code to different files (exact copy), adding comments around prompts.

Original source: api.py
Last verified: 2025-01-21
"""

import os
import json
import logging
import re
import time
from typing import Dict, Any, Optional, List

# Try to import the correct genai package
try:
    import google.generativeai as genai
    GEMINI_PACKAGE_TYPE = "generativeai"
except ImportError:
    try:
        import google.genai as genai
        GEMINI_PACKAGE_TYPE = "genai"
    except ImportError:
        genai = None
        GEMINI_PACKAGE_TYPE = None

from llm_schemas import (
    serialize_chart_for_llm,
    format_serialized_chart_for_prompt,
    parse_json_response,
    GlobalReadingBlueprint,
    SNAPSHOT_PROMPT
)

logger = logging.getLogger(__name__)

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI3_MODEL = os.getenv("GEMINI3_MODEL", "gemini-3-pro-preview")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101")
AI_MODE = os.getenv("AI_MODE", "real").lower()  # "real" or "stub" for local testing

# Import anthropic for Claude client
try:
    import anthropic
except ImportError:
    anthropic = None

# --- Cost Calculation (exact copy) ---
def calculate_gemini3_cost(prompt_tokens: int, completion_tokens: int,
                           input_price_per_million: float = 2.00,
                           output_price_per_million: float = 12.00) -> dict:
    """
    Calculate Gemini 3 Pro API cost based on token usage.
    
    Default pricing (per 1M tokens):
    - Input: $2.00
    - Output: $12.00
    """
    try:
        prompt_tokens = int(prompt_tokens) if prompt_tokens is not None else 0
        completion_tokens = int(completion_tokens) if completion_tokens is not None else 0
        prompt_tokens = max(0, prompt_tokens)
        completion_tokens = max(0, completion_tokens)
        
        input_cost = (prompt_tokens / 1_000_000) * input_price_per_million
        output_cost = (completion_tokens / 1_000_000) * output_price_per_million
        total_cost = input_cost + output_cost
        
        return {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
            'input_cost_usd': round(input_cost, 6),
            'output_cost_usd': round(output_cost, 6),
            'total_cost_usd': round(total_cost, 6)
        }
    except (TypeError, ValueError) as e:
        logger.error(f"Error calculating Gemini cost: {e}. Tokens: prompt={prompt_tokens}, completion={completion_tokens}")
        return {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'input_cost_usd': 0.0,
            'output_cost_usd': 0.0,
            'total_cost_usd': 0.0
        }


# --- Gemini3Client (exact copy) ---
class Gemini3Client:
    """Gemini 3 client with token + cost tracking."""
    
    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        self.model_name = GEMINI3_MODEL or "gemini-3-pro-preview"
        self.default_max_tokens = int(os.getenv("GEMINI3_MAX_OUTPUT_TOKENS", "81920"))
        self.client = None
        self.model = None
        if GEMINI_API_KEY and AI_MODE != "stub" and genai:
            try:
                if GEMINI_PACKAGE_TYPE == "generativeai":
                    # Old google-generativeai package
                    self.model = genai.GenerativeModel(self.model_name)
                elif GEMINI_PACKAGE_TYPE == "genai":
                    # New google.genai package uses Client API
                    try:
                        from google.genai import Client
                        self.client = Client(api_key=GEMINI_API_KEY)
                        # Model will be accessed via client.models.generate_content
                    except ImportError:
                        logger.error("Could not import Client from google.genai")
                        self.client = None
                else:
                    logger.warning("Unknown genai package type, cannot initialize model")
            except Exception as e:
                logger.error(f"Error initializing Gemini model '{self.model_name}': {e}")
                self.model = None
                self.client = None
    
    async def generate(self, system: str, user: str, max_output_tokens: int, temperature: float, call_label: str) -> str:
        self.call_count += 1
        logger.info(f"[{call_label}] Starting Gemini call #{self.call_count}")
        logger.info(f"[{call_label}] System prompt length: {len(system)} chars")
        logger.info(f"[{call_label}] User content length: {len(user)} chars")
        max_tokens = max_output_tokens or self.default_max_tokens
        logger.info(f"[{call_label}] max_output_tokens set to {max_tokens}")
        
        if AI_MODE == "stub":
            logger.info(f"[{call_label}] AI_MODE=stub: Returning stub response")
            stub_response = f"[STUB GEMINI RESPONSE for {call_label}] System: {system[:120]}... User: {user[:120]}..."
            self.total_prompt_tokens += len(system.split()) + len(user.split())
            self.total_completion_tokens += len(stub_response.split())
            return stub_response
        
        if not GEMINI_API_KEY:
            logger.error(f"[{call_label}] GEMINI_API_KEY not configured - cannot call Gemini 3")
            raise Exception("Gemini API key not configured")
        
        if self.model is None and (GEMINI_PACKAGE_TYPE == "generativeai" or self.client is None):
            try:
                if GEMINI_PACKAGE_TYPE == "generativeai":
                    # Old API
                    self.model = genai.GenerativeModel(self.model_name)
                elif GEMINI_PACKAGE_TYPE == "genai":
                    # New Client API - initialize client if needed
                    if self.client is None:
                        from google.genai import Client
                        self.client = Client(api_key=GEMINI_API_KEY)
                        logger.info(f"[{call_label}] Initialized google.genai Client")
            except Exception as e:
                logger.error(f"[{call_label}] Failed to initialize Gemini client: {e}", exc_info=True)
                raise
        
        prompt_sections = []
        if system:
            prompt_sections.append(f"[SYSTEM INSTRUCTIONS]\n{system.strip()}")
        prompt_sections.append(f"[USER INPUT]\n{user.strip()}")
        combined_prompt = "\n\n".join(prompt_sections)
        
        try:
            logger.info(f"[{call_label}] Calling Gemini model '{self.model_name}'...")
            generation_config = {
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": max_tokens,
            }
            
            # Use appropriate API based on which package is available
            if GEMINI_PACKAGE_TYPE == "genai" and self.client is not None:
                # New google.genai Client API - use client.models.generate_content() (synchronous, not async)
                try:
                    from google.genai import types
                    logger.info(f"[{call_label}] Using google.genai Client API with GenerateContentConfig")
                    # Create config object using types.GenerateContentConfig
                    config = types.GenerateContentConfig(
                        temperature=generation_config["temperature"],
                        top_p=generation_config["top_p"],
                        top_k=generation_config["top_k"],
                        max_output_tokens=generation_config["max_output_tokens"]
                    )
                    # Note: generate_content is synchronous, not async
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=combined_prompt,
                        config=config
                    )
                except ImportError:
                    # Fallback if types module not available
                    logger.warning(f"[{call_label}] types module not available, trying without config")
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=combined_prompt
                    )
                except Exception as e:
                    logger.error(f"[{call_label}] Error calling google.genai API: {e}", exc_info=True)
                    # Last resort: try simple call without config
                    try:
                        response = self.client.models.generate_content(
                            model=self.model_name,
                            contents=combined_prompt
                        )
                    except Exception as e2:
                        logger.error(f"[{call_label}] Simple call also failed: {e2}")
                        raise
            elif GEMINI_PACKAGE_TYPE == "generativeai" and self.model is not None:
                # Old google-generativeai API
                response = await self.model.generate_content_async(
                    combined_prompt,
                    generation_config=generation_config
                )
            else:
                raise Exception(f"Cannot generate content - not properly initialized (package_type={GEMINI_PACKAGE_TYPE}, model={self.model is not None}, client={self.client is not None})")
            logger.info(f"[{call_label}] Gemini API call completed successfully")
        except Exception as e:
            logger.error(f"[{call_label}] Gemini API error: {e}", exc_info=True)
            raise
        
        usage_metadata = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0
        }
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            try:
                usage_metadata = {
                    'prompt_tokens': int(getattr(response.usage_metadata, 'prompt_token_count', 0) or 0),
                    'completion_tokens': int(getattr(response.usage_metadata, 'candidates_token_count',
                                                     getattr(response.usage_metadata, 'completion_token_count', 0)) or 0),
                    'total_tokens': int(getattr(response.usage_metadata, 'total_token_count', 0) or 0)
                }
                logger.info(f"[{call_label}] Token usage - Input: {usage_metadata['prompt_tokens']}, Output: {usage_metadata['completion_tokens']}, Total: {usage_metadata['total_tokens']}")
            except Exception as meta_error:
                logger.warning(f"[{call_label}] Failed to parse Gemini usage metadata: {meta_error}")
                usage_metadata = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        
        self.total_prompt_tokens += usage_metadata['prompt_tokens']
        self.total_completion_tokens += usage_metadata['completion_tokens']
        call_cost = calculate_gemini3_cost(usage_metadata['prompt_tokens'], usage_metadata['completion_tokens'])
        self.total_cost_usd += call_cost['total_cost_usd']
        logger.info(f"[{call_label}] Call cost: ${call_cost['total_cost_usd']:.6f} (Input: ${call_cost['input_cost_usd']:.6f}, Output: ${call_cost['output_cost_usd']:.6f})")
        
        response_text = ""
        if hasattr(response, 'text') and response.text:
            response_text = response.text.strip()
        elif hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                    part_texts = [getattr(part, "text", "") for part in candidate.content.parts]
                    response_text = " ".join(part_texts).strip()
                    if response_text:
                        break
        if not response_text:
            logger.error(f"[{call_label}] Gemini response empty or blocked")
            raise Exception("Gemini response was empty or blocked")
        
        logger.info(f"[{call_label}] Response length: {len(response_text)} characters")
        return response_text
    
    def get_summary(self) -> dict:
        return {
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_prompt_tokens + self.total_completion_tokens,
            'total_cost_usd': self.total_cost_usd,
            'call_count': self.call_count
        }


# --- ClaudeClient ---
class ClaudeClient:
    """Claude 3.5 Sonnet client with token + cost tracking."""
    
    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        self.model_name = CLAUDE_MODEL
        # Claude Opus 4.5 has max 64,000 output tokens
        self.default_max_tokens = int(os.getenv("CLAUDE_MAX_OUTPUT_TOKENS", "64000"))
        self.client = None
        
        if ANTHROPIC_API_KEY and AI_MODE != "stub":
            try:
                if anthropic is None:
                    raise ImportError("anthropic package not installed")
                self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            except ImportError:
                logger.error("anthropic package not installed. Install with: pip install anthropic")
                self.client = None
            except Exception as e:
                logger.error(f"Error initializing Claude client: {e}")
                self.client = None
    
    async def generate(self, system: str, user: str, max_output_tokens: int, temperature: float, call_label: str) -> str:
        self.call_count += 1
        logger.info(f"[{call_label}] Starting Claude call #{self.call_count}")
        logger.info(f"[{call_label}] System prompt length: {len(system)} chars")
        logger.info(f"[{call_label}] User content length: {len(user)} chars")
        max_tokens = max_output_tokens or self.default_max_tokens
        logger.info(f"[{call_label}] max_output_tokens set to {max_tokens}")
        
        if AI_MODE == "stub":
            logger.info(f"[{call_label}] AI_MODE=stub: Returning stub response")
            stub_response = f"[STUB CLAUDE RESPONSE for {call_label}] System: {system[:120]}... User: {user[:120]}..."
            self.total_prompt_tokens += len(system.split()) + len(user.split())
            self.total_completion_tokens += len(stub_response.split())
            return stub_response
        
        if not ANTHROPIC_API_KEY:
            logger.error(f"[{call_label}] ANTHROPIC_API_KEY not configured - cannot call Claude")
            raise Exception("Anthropic API key not configured")
        
        if self.client is None:
            try:
                if anthropic is None:
                    raise ImportError("anthropic package not installed")
                self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            except Exception as e:
                logger.error(f"[{call_label}] Failed to initialize Claude client: {e}", exc_info=True)
                raise
        
        try:
            logger.info(f"[{call_label}] Calling Claude model '{self.model_name}'...")
            
            # Claude API call - enable streaming for long requests (>10 min)
            # For large max_tokens, we need to use streaming
            # Also cap max_tokens at 64,000 (Claude Opus 4.5 limit)
            max_tokens = min(max_tokens, 64000)
            use_streaming = max_tokens > 20000  # Stream if expecting large output
            
            if use_streaming:
                logger.info(f"[{call_label}] Using streaming mode for large output (max_tokens={max_tokens})")
                text_parts = []
                usage_metadata = {
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0
                }
                
                with self.client.messages.stream(
                    model=self.model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[
                        {"role": "user", "content": user}
                    ]
                ) as stream:
                    chunk_count = 0
                    for event in stream:
                        if event.type == "content_block_delta" and event.delta.type == "text_delta":
                            text_parts.append(event.delta.text)
                            chunk_count += 1
                            if chunk_count % 100 == 0:  # Log progress every 100 chunks
                                logger.info(f"[{call_label}] Received {chunk_count} text chunks, {len(''.join(text_parts))} chars so far...")
                        elif event.type == "message_delta" and event.usage:
                            # Capture usage when available
                            usage_metadata = {
                                'prompt_tokens': event.usage.input_tokens or 0,
                                'completion_tokens': event.usage.output_tokens or 0,
                                'total_tokens': (event.usage.input_tokens or 0) + (event.usage.output_tokens or 0)
                            }
                        elif event.type == "message_stop":
                            # Final event - try to get usage if not already captured
                            if usage_metadata['total_tokens'] == 0:
                                # Estimate tokens if we can't get usage
                                usage_metadata = {
                                    'prompt_tokens': len(system.split()) + len(user.split()),
                                    'completion_tokens': len(''.join(text_parts).split()),
                                    'total_tokens': len(system.split()) + len(user.split()) + len(''.join(text_parts).split())
                                }
                
                response_text = "".join(text_parts).strip()
                
                if not response_text:
                    logger.error(f"[{call_label}] Claude streaming response empty")
                    raise Exception("Claude streaming response was empty")
            else:
                # Non-streaming for smaller requests
                message = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[
                        {"role": "user", "content": user}
                    ]
                )
                
                # Extract response text
                response_text = ""
                if message.content:
                    # Claude returns a list of content blocks
                    text_parts = []
                    for block in message.content:
                        if block.type == "text":
                            text_parts.append(block.text)
                    response_text = "".join(text_parts).strip()
                
                if not response_text:
                    logger.error(f"[{call_label}] Claude response empty")
                    raise Exception("Claude response was empty")
                
                # Extract token usage
                usage = message.usage
                usage_metadata = {
                    'prompt_tokens': usage.input_tokens if usage else 0,
                    'completion_tokens': usage.output_tokens if usage else 0,
                    'total_tokens': (usage.input_tokens + usage.output_tokens) if usage else 0
                }
            
                logger.info(f"[{call_label}] Claude API call completed successfully")
            
            logger.info(f"[{call_label}] Claude API call completed successfully")
        except Exception as e:
            logger.error(f"[{call_label}] Claude API error: {e}", exc_info=True)
            raise
        
        logger.info(f"[{call_label}] Token usage - Input: {usage_metadata['prompt_tokens']}, Output: {usage_metadata['completion_tokens']}, Total: {usage_metadata['total_tokens']}")
        
        self.total_prompt_tokens += usage_metadata['prompt_tokens']
        self.total_completion_tokens += usage_metadata['completion_tokens']
        
        # Claude 3.5 Sonnet pricing: $3/1M input, $15/1M output
        call_cost = calculate_claude_cost(usage_metadata['prompt_tokens'], usage_metadata['completion_tokens'])
        self.total_cost_usd += call_cost['total_cost_usd']
        logger.info(f"[{call_label}] Call cost: ${call_cost['total_cost_usd']:.6f} (Input: ${call_cost['input_cost_usd']:.6f}, Output: ${call_cost['output_cost_usd']:.6f})")
        
        logger.info(f"[{call_label}] Response length: {len(response_text)} characters")
        return response_text
    
    def get_summary(self) -> dict:
        return {
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_prompt_tokens + self.total_completion_tokens,
            'total_cost_usd': self.total_cost_usd,
            'call_count': self.call_count
        }


def calculate_claude_cost(prompt_tokens: int, completion_tokens: int,
                          input_price_per_million: float = 3.00,
                          output_price_per_million: float = 15.00) -> dict:
    """Calculate Claude 3.5 Sonnet API cost based on token usage."""
    try:
        prompt_tokens = int(prompt_tokens) if prompt_tokens is not None else 0
        completion_tokens = int(completion_tokens) if completion_tokens is not None else 0
        prompt_tokens = max(0, prompt_tokens)
        completion_tokens = max(0, completion_tokens)
        
        input_cost = (prompt_tokens / 1_000_000) * input_price_per_million
        output_cost = (completion_tokens / 1_000_000) * output_price_per_million
        total_cost = input_cost + output_cost
        
        return {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
            'input_cost_usd': round(input_cost, 6),
            'output_cost_usd': round(output_cost, 6),
            'total_cost_usd': round(total_cost, 6)
        }
    except (TypeError, ValueError) as e:
        logger.error(f"Error calculating Claude cost: {e}. Tokens: prompt={prompt_tokens}, completion={completion_tokens}")
        return {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'input_cost_usd': 0.0,
            'output_cost_usd': 0.0,
            'total_cost_usd': 0.0
        }


# --- Helper Functions (exact copy) ---
def _blueprint_to_json(blueprint: Dict[str, Any]) -> str:
    if blueprint.get("parsed"):
        return json.dumps(blueprint['parsed'].model_dump(by_alias=True), indent=2)
    return blueprint.get("raw_text", "")


def sanitize_reading_text(text: str) -> str:
    """Remove leftover markdown markers or decorative separators from AI output."""
    if not text:
        return text
    
    patterns = [
        (r'\*\*\*(.*?)\*\*\*', r'\1'),
        (r'\*\*(.*?)\*\*', r'\1'),
        (r'\*(.*?)\*', r'\1'),
    ]
    cleaned = text
    for pattern, repl in patterns:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.DOTALL)
    
    # Remove standalone lines of asterisks or dashes
    cleaned = re.sub(r'^\s*(\*{3,}|-{3,})\s*$', '', cleaned, flags=re.MULTILINE)
    
    # Collapse multiple blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned


def _sign_from_position(pos: str | None) -> str | None:
    """Extract sign from a position string like '12°34' Virgo'."""
    if not pos or pos == "N/A":
        return None
    parts = pos.split()
    return parts[-1] if parts else None


# --- Snapshot Data Serialization (exact copy) ---
def serialize_snapshot_data(chart_data: dict, unknown_time: bool) -> dict:
    """
    Serialize only the snapshot data: 2 tightest aspects, stelliums, Sun/Moon/Rising
    from both sidereal and tropical systems. This is blinded (no name, birthdate, location).
    """
    snapshot = {
        "metadata": {
            "unknown_time": unknown_time
        },
        "core_identity": {
            "sidereal": {},
            "tropical": {}
        },
        "tightest_aspects": {
            "sidereal": [],
            "tropical": []
        },
        "stelliums": {
            "sidereal": [],
            "tropical": []
        }
    }
    
    # Extract Sun, Moon, Rising from sidereal
    s_positions = {p['name']: p for p in chart_data.get('sidereal_major_positions', [])}
    s_extra = {p['name']: p for p in chart_data.get('sidereal_additional_points', [])}
    
    def extract_sign_from_position(position_str):
        """Extract sign name from position string like '25°30' Capricorn'"""
        if not position_str:
            return 'N/A'
        parts = position_str.split()
        return parts[-1] if parts else 'N/A'
    
    for body_name in ['Sun', 'Moon']:
        if body_name in s_positions:
            body = s_positions[body_name]
            position_str = body.get('position', '')
            snapshot["core_identity"]["sidereal"][body_name.lower()] = {
                "sign": extract_sign_from_position(position_str),
                "degree": body.get('degrees', 0),
                "house": body.get('house_num') if not unknown_time else None,
                "retrograde": body.get('retrograde', False)
            }
    
    # Ascendant (if known time)
    if not unknown_time and 'Ascendant' in s_extra:
        asc = s_extra['Ascendant']
        info_str = asc.get('info', '')
        sign = extract_sign_from_position(info_str)
        # Try to extract degree from info string (format: "Sign degree°" or "Sign degree° – House X")
        degree = 0
        if info_str:
            parts = info_str.split()
            for i, part in enumerate(parts):
                if '°' in part:
                    try:
                        degree = float(part.replace('°', '').replace("'", ''))
                        break
                    except (ValueError, AttributeError):
                        pass
        snapshot["core_identity"]["sidereal"]["ascendant"] = {
            "sign": sign,
            "degree": degree
        }
    
    # Extract Sun, Moon, Rising from tropical
    t_positions = {p['name']: p for p in chart_data.get('tropical_major_positions', [])}
    t_extra = {p['name']: p for p in chart_data.get('tropical_additional_points', [])}
    
    for body_name in ['Sun', 'Moon']:
        if body_name in t_positions:
            body = t_positions[body_name]
            position_str = body.get('position', '')
            snapshot["core_identity"]["tropical"][body_name.lower()] = {
                "sign": extract_sign_from_position(position_str),
                "degree": body.get('degrees', 0),
                "house": body.get('house_num') if not unknown_time else None,
                "retrograde": body.get('retrograde', False)
            }
    
    # Ascendant (if known time)
    if not unknown_time and 'Ascendant' in t_extra:
        asc = t_extra['Ascendant']
        info_str = asc.get('info', '')
        sign = extract_sign_from_position(info_str)
        # Try to extract degree from info string (format: "Sign degree°" or "Sign degree° – House X")
        degree = 0
        if info_str:
            parts = info_str.split()
            for i, part in enumerate(parts):
                if '°' in part:
                    try:
                        degree = float(part.replace('°', '').replace("'", ''))
                        break
                    except (ValueError, AttributeError):
                        pass
        snapshot["core_identity"]["tropical"]["ascendant"] = {
            "sign": sign,
            "degree": degree
        }
    
    # Get 2 tightest aspects from sidereal (sorted by score, then orb)
    s_aspects = chart_data.get('sidereal_aspects', [])
    if s_aspects:
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
        
        sorted_s_aspects = sorted(
            s_aspects,
            key=lambda a: (-parse_score(a.get('score', 0)), parse_orb(a.get('orb', 999)))
        )[:2]
        
        snapshot["tightest_aspects"]["sidereal"] = [
            {
                "p1": a.get('p1_name', ''),
                "p2": a.get('p2_name', ''),
                "type": a.get('type', ''),
                "orb": a.get('orb', ''),
                "score": a.get('score', '')
            }
            for a in sorted_s_aspects
        ]
    
    # Get 2 tightest aspects from tropical
    t_aspects = chart_data.get('tropical_aspects', [])
    if t_aspects:
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
        
        sorted_t_aspects = sorted(
            t_aspects,
            key=lambda a: (-parse_score(a.get('score', 0)), parse_orb(a.get('orb', 999)))
        )[:2]
        
        snapshot["tightest_aspects"]["tropical"] = [
            {
                "p1": a.get('p1_name', ''),
                "p2": a.get('p2_name', ''),
                "type": a.get('type', ''),
                "orb": a.get('orb', ''),
                "score": a.get('score', '')
            }
            for a in sorted_t_aspects
        ]
    
    # Get stelliums from sidereal
    s_patterns = chart_data.get('sidereal_aspect_patterns', [])
    stelliums_s = [p for p in s_patterns if 'stellium' in p.get('description', '').lower()]
    snapshot["stelliums"]["sidereal"] = [p.get('description', '') for p in stelliums_s]
    
    # Get stelliums from tropical
    t_patterns = chart_data.get('tropical_aspect_patterns', [])
    stelliums_t = [p for p in t_patterns if 'stellium' in p.get('description', '').lower()]
    snapshot["stelliums"]["tropical"] = [p.get('description', '') for p in stelliums_t]
    
    return snapshot


def format_snapshot_for_prompt(snapshot: dict) -> str:
    """Format the snapshot data as a human-readable string for LLM prompts."""
    lines = []
    
    lines.append("=== SNAPSHOT CHART DATA ===")
    lines.append(f"Unknown Time: {snapshot.get('metadata', {}).get('unknown_time', False)}")
    lines.append("")
    
    # Core Identity
    lines.append("=== CORE IDENTITY ===")
    unknown_time = snapshot.get('metadata', {}).get('unknown_time', False)
    for system in ['sidereal', 'tropical']:
        lines.append(f"\n{system.upper()}:")
        core = snapshot.get('core_identity', {}).get(system, {})
        # Always include Sun and Moon
        for body in ['sun', 'moon']:
            if body in core:
                info = core[body]
                house_str = f", House {info['house']}" if info.get('house') and not unknown_time else ""
                retro_str = " (Rx)" if info.get('retrograde') else ""
                degree_str = f" {info.get('degree', 0)}°" if info.get('degree') else ""
                lines.append(f"  {body.capitalize()}: {info.get('sign', 'N/A')}{degree_str}{house_str}{retro_str}")
        # Only include Ascendant if time is known
        if not unknown_time and 'ascendant' in core:
            info = core['ascendant']
            degree_str = f" {info.get('degree', 0)}°" if info.get('degree') else ""
            lines.append(f"  Ascendant: {info.get('sign', 'N/A')}{degree_str}")
        elif unknown_time:
            lines.append("  Ascendant: Not available (birth time unknown)")
    lines.append("")
    
    # Tightest Aspects
    lines.append("=== TWO TIGHTEST ASPECTS ===")
    for system in ['sidereal', 'tropical']:
        lines.append(f"\n{system.upper()}:")
        aspects = snapshot.get('tightest_aspects', {}).get(system, [])
        if aspects:
            for a in aspects:
                lines.append(f"  {a.get('p1')} {a.get('type')} {a.get('p2')} (orb: {a.get('orb')}, score: {a.get('score')})")
        else:
            lines.append("  No aspects available")
    lines.append("")
    
    # Stelliums
    lines.append("=== STELLIUMS ===")
    for system in ['sidereal', 'tropical']:
        lines.append(f"\n{system.upper()}:")
        stelliums = snapshot.get('stelliums', {}).get(system, [])
        if stelliums:
            for s in stelliums:
                lines.append(f"  {s}")
        else:
            lines.append("  No stelliums detected")
    lines.append("")
    
    return "\n".join(lines)


# Prompt functions are in llm_prompts.py to preserve prompts exactly
# api.py should import from both llm_service.py and llm_prompts.py

# Export core functions for use in api.py and llm_prompts.py
__all__ = [
    'Gemini3Client',
    'calculate_gemini3_cost',
    '_blueprint_to_json',
    'serialize_snapshot_data',
    'format_snapshot_for_prompt',
    'sanitize_reading_text',
    '_sign_from_position'
]

