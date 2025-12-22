# Remove Duplicate Function Definitions

This document lists all duplicate function definitions in `api.py` that should be removed since they're now imported from service modules.

## Functions to Remove

### LLM Service Functions
1. `calculate_gemini3_cost()` - Line ~504 - Now in `app.services.llm_service`
2. `Gemini3Client` class - Line ~529 - Now in `app.services.llm_service`
3. `_blueprint_to_json()` - Line ~712 - Now in `app.services.llm_service`

### LLM Prompt Functions (Large - ~100+ lines each)
4. `g0_global_blueprint()` - Line ~718 - Now in `app.services.llm_prompts`
5. `g1_natal_foundation()` - Line ~819 - Now in `app.services.llm_prompts`
6. `g2_deep_dive_chapters()` - Line ~1094 - Now in `app.services.llm_prompts`
7. `g3_polish_full_reading()` - Line ~1354 - Now in `app.services.llm_prompts`
8. `g4_famous_people_section()` - Line ~1432 - Now in `app.services.llm_prompts`
9. `generate_snapshot_reading()` - Line ~1811 - Now in `app.services.llm_prompts`
10. `get_gemini3_reading()` - Line ~1917 - Now in `app.services.llm_prompts`
11. `generate_comprehensive_synastry()` - Line ~4623 - Now in `app.services.llm_prompts`

### LLM Helper Functions
12. `serialize_snapshot_data()` - Line ~1568 - Now in `app.services.llm_service`
13. `format_snapshot_for_prompt()` - Line ~1753 - Now in `app.services.llm_service`
14. `sanitize_reading_text()` - Line ~2046 - Now in `app.services.llm_service`

### Chart Service Functions
15. `get_quick_highlights()` - Line ~2076 - Now in `app.services.chart_service`
16. `parse_pasted_chart_data()` - Line ~4521 - Now in `app.services.chart_service`

### Email Service Functions
17. `send_snapshot_email_via_sendgrid()` - Line ~2428 - Now in `app.services.email_service`
18. `send_chart_email_via_sendgrid()` - Line ~2469 - Now in `app.services.email_service`
19. `send_synastry_email()` - Line ~4801 - Now in `app.services.email_service`

## Removal Strategy

1. **Small functions first** - Remove utility functions (calculate_gemini3_cost, _blueprint_to_json, etc.)
2. **Medium functions** - Remove helper functions (serialize_snapshot_data, format_snapshot_for_prompt, etc.)
3. **Large functions last** - Remove prompt functions (g0, g1, g2, g3, g4, etc.)

## Verification

After removal, verify:
- [ ] All imports work correctly
- [ ] No NameError exceptions
- [ ] All endpoints still function
- [ ] Tests pass

## Note

The functions are currently defined locally AND imported. The local definitions shadow the imports. Removing them will make the code use the imported versions from service modules.

