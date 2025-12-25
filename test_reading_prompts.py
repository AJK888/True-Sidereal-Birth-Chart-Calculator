"""
Test script to validate reading prompt improvements.

This script checks that:
1. All critical prompt requirements are present
2. PDF generator recognizes new sections
3. Prompt structure is correct
"""

import re
from pathlib import Path

def test_prompt_requirements():
    """Test that all critical requirements are in the prompts."""
    prompts_file = Path(__file__).parent / "app" / "services" / "llm_prompts.py"
    
    if not prompts_file.exists():
        print(f"[ERROR] Could not find {prompts_file}")
        return False
    
    content = prompts_file.read_text(encoding='utf-8')
    
    checks = {
        "Stellium explicit listing requirement": [
            r"CRITICAL.*stellium.*explicitly list ALL planets",
            r"NEVER say.*stellium.*without.*listing",
        ],
        "Planetary Dignities section": [
            r"PLANETARY DIGNITIES.*CONDITIONS",
            r"exaltation.*fall.*detriment",
        ],
        "Aspects coverage (5-7)": [
            r"TOP 5-7.*TIGHTEST ASPECTS",
            r"MUST cover.*TOP 5-7",
            r"Do NOT cover fewer than 5",
        ],
        "Aspect mechanism explanations": [
            r"aspect mechanism.*WHY",
            r"explain.*geometric.*astrological reason",
        ],
        "Houses detailed analysis": [
            r"ALL 12 houses",
            r"10-15 paragraphs.*per house",
        ],
        "Spiritual Path separate": [
            r"SEPARATE from.*Famous People",
            r"Do NOT mix famous people.*spiritual path",
        ],
        "Concrete examples global": [
            r"CONCRETE EXAMPLES",
            r"3-4.*concrete examples",
            r"MULTIPLE concrete examples",
        ],
        "Shadow interactions": [
            r"HOW SHADOWS INTERACT",
            r"how.*shadow patterns interact",
        ],
        "Emotional Life depth": [
            r"SUBSTANTIAL.*10-12 paragraphs",
            r"Family Dynamics Analysis",
            r"Childhood Patterns",
            r"Healing Modalities",
        ],
        "Work/Money depth": [
            r"Specific Career Paths",
            r"Detailed Money Patterns",
            r"Mars Analysis",
        ],
        "Operating System expanded": [
            r"6-8 paragraphs.*EXPANDED",
            r"default mode.*high expression mode",
        ],
    }
    
    results = {}
    all_passed = True
    
    for check_name, patterns in checks.items():
        found = False
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                found = True
                break
        results[check_name] = found
        if not found:
            all_passed = False
            print(f"[FAIL] {check_name}")
        else:
            print(f"[PASS] {check_name}")
    
    return all_passed, results


def test_pdf_generator_sections():
    """Test that PDF generator recognizes new sections."""
    pdf_file = Path(__file__).parent / "pdf_generator.py"
    
    if not pdf_file.exists():
        print(f"[ERROR] Could not find {pdf_file}")
        return False
    
    content = pdf_file.read_text(encoding='utf-8')
    
    checks = {
        "Planetary Dignities section": [
            r'"planetary_dignities"',
            r"planetary dignities.*conditions",
        ],
        "Shadow subsections": [
            r"how shadows interact",
            r"the gift first",
            r"the pattern",
            r"the protective function",
        ],
        "Growth edges subsections": [
            r"the opportunity",
            r"the chart evidence",
            r"why they resist",
            r"the practice",
        ],
        "Emotional Life subsections": [
            r"family dynamics.*analysis",
            r"childhood patterns",
            r"healing modalities",
        ],
        "Work/Money subsections": [
            r"specific career paths",
            r"detailed money patterns",
            r"mars.*analysis",
        ],
    }
    
    results = {}
    all_passed = True
    
    for check_name, patterns in checks.items():
        found = False
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                found = True
                break
        results[check_name] = found
        if not found:
            all_passed = False
            print(f"[FAIL] {check_name}")
        else:
            print(f"[PASS] {check_name}")
    
    return all_passed, results


def main():
    """Run all tests."""
    print("=" * 80)
    print("TESTING READING PROMPT IMPROVEMENTS")
    print("=" * 80)
    print()
    
    print("Testing Prompt Requirements...")
    print("-" * 80)
    prompts_ok, prompts_results = test_prompt_requirements()
    print()
    
    print("Testing PDF Generator Sections...")
    print("-" * 80)
    pdf_ok, pdf_results = test_pdf_generator_sections()
    print()
    
    print("=" * 80)
    if prompts_ok and pdf_ok:
        print("[SUCCESS] ALL TESTS PASSED")
        print()
        print("Next steps:")
        print("1. Generate a test reading via the API endpoint")
        print("2. Verify all requirements are met in the generated reading")
        print("3. Check the PDF output formats correctly")
        print()
        print("To test via API:")
        print("  POST /api/v1/charts/generate_reading")
        print("  with chart_data, unknown_time, and user_inputs")
    else:
        print("[FAILURE] SOME TESTS FAILED")
        print()
        if not prompts_ok:
            print("Prompt requirements need fixing:")
            for check, passed in prompts_results.items():
                if not passed:
                    print(f"  - {check}")
        if not pdf_ok:
            print("PDF generator needs fixing:")
            for check, passed in pdf_results.items():
                if not passed:
                    print(f"  - {check}")
    print("=" * 80)


if __name__ == "__main__":
    main()

