# Preservation Guidelines - Critical Components

**⚠️ CRITICAL: READ THIS BEFORE ANY REFACTORING**

This document defines what MUST be preserved exactly during any backend refactoring.

---

## Components That MUST Be Preserved Exactly

### 1. LLM Prompts

**Status:** ✅ **DO NOT MODIFY - TUNED AND VALIDATED**

**What to Preserve:**
- All prompt strings sent to Gemini/LLM
- Prompt structure and formatting
- Prompt construction logic
- Variable substitution in prompts
- Any prompt-related constants or templates

**Files Containing Prompts:**
- `api.py` - All prompt strings (search for `prompt =`, `system_prompt`, etc.)
- `llm_schemas.py` - `SNAPSHOT_PROMPT` and other prompt constants
- Any functions that build or format prompts

**Preservation Rules:**
1. ✅ **EXACT COPY ONLY** - When extracting, copy prompts character-for-character
2. ✅ **NO REFACTORING** - Do not "improve" or "clean up" prompt text
3. ✅ **NO FORMATTING CHANGES** - Preserve whitespace, line breaks, indentation
4. ✅ **NO VARIABLE RENAMING** - Keep all variable names in prompts exactly
5. ✅ **VERIFICATION REQUIRED** - Compare before/after extraction byte-for-byte

**Allowed Changes:**
- Moving prompts to separate files (exact copy)
- Adding comments around prompts (not in prompts)
- Adding logging before/after prompt usage (not modifying prompts)

**Forbidden Changes:**
- ❌ Changing prompt text
- ❌ Reformatting prompts
- ❌ "Improving" prompt wording
- ❌ Changing prompt structure
- ❌ Modifying variable substitution logic
- ❌ Any change that affects prompt content

---

### 2. Technical Calculations

**Status:** ✅ **DO NOT MODIFY - SENSITIVE AND VALIDATED**

**What to Preserve:**
- All chart calculation algorithms
- Mathematical formulas
- Swiss Ephemeris usage patterns
- Sign calculations (sidereal and tropical)
- Aspect calculations
- House calculations
- Planetary position calculations
- Any mathematical operations

**Files Containing Calculations:**
- `natal_chart.py` - All calculation logic
- `api.py` - Chart calculation calls and related logic
- Any functions that perform mathematical operations on chart data

**Preservation Rules:**
1. ✅ **EXACT COPY ONLY** - When extracting, copy calculation code exactly
2. ✅ **NO ALGORITHM CHANGES** - Do not "optimize" or "improve" calculations
3. ✅ **NO FORMULA CHANGES** - Preserve all mathematical formulas exactly
4. ✅ **NO PRECISION CHANGES** - Preserve all rounding, precision, and formatting
5. ✅ **VERIFICATION REQUIRED** - Test outputs match exactly before/after

**Allowed Changes:**
- Moving calculation code to services (exact copy)
- Adding error handling around calculations (not in calculations)
- Adding logging before/after calculations (not modifying calculations)
- Adding type hints (if they don't change behavior)

**Forbidden Changes:**
- ❌ Changing calculation algorithms
- ❌ Modifying mathematical formulas
- ❌ Changing precision or rounding
- ❌ "Optimizing" calculations
- ❌ Refactoring calculation logic
- ❌ Any change that affects calculation output

---

## Verification Process

### Before Any Extraction:

1. **Create Test Suite:**
   ```python
   # tests/preservation/test_calculations_preserved.py
   # Test with known inputs, save expected outputs
   ```

2. **Save Original Outputs:**
   - Run calculations on test data
   - Save outputs to files
   - Hash outputs for comparison

3. **Save Original Prompts:**
   - Extract all prompt strings
   - Save to files
   - Hash prompts for comparison

### During Extraction:

1. **Copy Exactly:**
   - Copy code character-for-character
   - Do not reformat
   - Do not "improve"
   - Do not refactor

2. **Add Preservation Markers:**
   ```python
   # ⚠️ DO NOT MODIFY - VALIDATED PROMPT/CALCULATION
   # Original source: api.py, line X
   # Last verified: YYYY-MM-DD
   ```

3. **Document Changes:**
   - Only document WHERE code moved
   - Do NOT document WHAT changed (nothing should change)

### After Extraction:

1. **Run Regression Tests:**
   - Run same calculations on test data
   - Compare outputs byte-for-byte
   - Verify prompts match exactly

2. **Automated Verification:**
   ```python
   # tests/preservation/verify_no_changes.py
   # Compare hashes of prompts and calculation outputs
   ```

3. **Manual Review:**
   - Review extracted code
   - Verify no changes to prompts/calculations
   - Check preservation markers

---

## Code Markers

### Use These Markers in Code:

```python
# ⚠️ PRESERVATION ZONE START - DO NOT MODIFY
# This section contains validated prompts/calculations
# Original source: api.py, lines 1000-1500
# Last verified: 2025-01-21
# Any changes to this section must be approved and verified

# [Original code here - exact copy]

# ⚠️ PRESERVATION ZONE END
```

### In Function Docstrings:

```python
def calculate_chart(...):
    """
    Calculate birth chart.
    
    ⚠️ PRESERVATION NOTE:
    This function contains validated calculation logic.
    DO NOT modify calculation algorithms, formulas, or precision.
    Only allowed changes: error handling, logging, type hints.
    
    Original source: natal_chart.py
    Last verified: 2025-01-21
    """
```

---

## Testing Requirements

### Required Tests:

1. **Calculation Regression Tests:**
   ```python
   def test_calculations_preserved():
       # Test with known inputs
       # Compare outputs to saved expected outputs
       # Fail if any difference
   ```

2. **Prompt Regression Tests:**
   ```python
   def test_prompts_preserved():
       # Extract all prompts
       # Compare to saved original prompts
       # Fail if any difference
   ```

3. **Integration Tests:**
   ```python
   def test_end_to_end_outputs_match():
       # Test full flow with same inputs
       # Compare final outputs
       # Fail if any difference
   ```

---

## Review Checklist

Before committing any changes that touch prompts or calculations:

- [ ] Original code saved/committed separately
- [ ] Test suite created with expected outputs
- [ ] Code copied exactly (no edits)
- [ ] Preservation markers added
- [ ] Regression tests pass
- [ ] Manual review completed
- [ ] Documentation updated
- [ ] Code review approved

---

## Emergency Rollback

If any changes accidentally modify prompts or calculations:

1. **Immediately:**
   - Revert the commit
   - Notify team
   - Document what happened

2. **Investigation:**
   - Compare before/after
   - Identify what changed
   - Document findings

3. **Prevention:**
   - Add additional safeguards
   - Update guidelines
   - Improve review process

---

## Contact

If you have questions about what can/cannot be changed:
- Review this document
- Check preservation markers in code
- Ask before making changes
- When in doubt, preserve exactly

---

**Last Updated:** 2025-01-21  
**Status:** Active - Must be followed for all refactoring

