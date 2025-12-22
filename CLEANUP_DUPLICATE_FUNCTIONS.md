# Cleanup: Remove Duplicate Function Definitions

This document provides a systematic approach to removing duplicate function definitions from `api.py`.

## Status

✅ **ALL FUNCTIONS REMOVED - Cleanup Complete!**

### Small functions removed:
- `calculate_gemini3_cost()` - ✅ Removed
- `Gemini3Client` class - ✅ Removed  
- `_blueprint_to_json()` - ✅ Removed (including leftover fragment)

### Large functions removed (100+ lines each):
- `g0_global_blueprint()` - ✅ Removed (moved to `app.services.llm_prompts`)
- `g1_natal_foundation()` - ✅ Removed (moved to `app.services.llm_prompts`)
- `g2_deep_dive_chapters()` - ✅ Removed (moved to `app.services.llm_prompts`)
- `g3_polish_full_reading()` - ✅ Removed (moved to `app.services.llm_prompts`)
- `g4_famous_people_section()` - ✅ Removed (moved to `app.services.llm_prompts`)
- `serialize_snapshot_data()` - ✅ Removed (moved to `app.services.llm_service`)
- `format_snapshot_for_prompt()` - ✅ Removed (moved to `app.services.llm_service`)
- `generate_snapshot_reading()` - ✅ Removed (moved to `app.services.llm_prompts`)
- `get_gemini3_reading()` - ✅ Removed (moved to `app.services.llm_prompts`)
- `sanitize_reading_text()` - ✅ Removed (moved to `app.services.llm_service`)
- `get_quick_highlights()` - ✅ Removed (moved to `app.services.chart_service`)
- `send_snapshot_email_via_sendgrid()` - ✅ Removed (moved to `app.services.email_service`)
- `send_chart_email_via_sendgrid()` - ✅ Removed (moved to `app.services.email_service`)
- `parse_pasted_chart_data()` - ✅ Removed (moved to `app.services.chart_service`)
- `generate_comprehensive_synastry()` - ✅ Removed (moved to `app.services.llm_prompts`)
- `send_synastry_email()` - ✅ Removed (moved to `app.services.email_service`)

## Removal Strategy

Since these functions are now imported from service modules, they can be safely removed. However, given their size, removal should be done carefully:

1. **Test after each removal** - Verify the code still works
2. **Remove in batches** - Group related functions together
3. **Keep backups** - Git commit after each successful removal

## Verification

✅ **Verification Complete:**
- ✅ All imports work correctly (functions imported from service modules)
- ✅ No syntax errors (linter check passed)
- ✅ All duplicate function definitions removed
- ✅ Functions replaced with comments noting their new location

## Summary

All duplicate function definitions have been successfully removed from `api.py`. The functions are now exclusively imported from their respective service modules:
- LLM functions: `app.services.llm_service`, `app.services.llm_prompts`
- Email functions: `app.services.email_service`
- Chart functions: `app.services.chart_service`

The code now uses the imported versions from service modules, eliminating code duplication and improving maintainability.

