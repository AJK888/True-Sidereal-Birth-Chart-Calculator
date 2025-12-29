"""
Generate a real reading and grade it against the requirements.

This script:
1. Calculates the chart for Sofie AlQattan
2. Generates a full reading
3. Grades it against all requirements
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pendulum

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Check for API key - try to load from .env file if not in environment
if not os.getenv("GEMINI_API_KEY"):
    # Try to load from .env file
    env_file = project_root / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print(f"Loaded environment variables from {env_file}")
        except ImportError:
            pass
    
    # Check again after loading .env
    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY not found.")
        print("The reading will use stub mode (test responses only).")
        print("\nTo generate a real reading, set GEMINI_API_KEY:")
        print("  export GEMINI_API_KEY='your-key-here'  # Linux/Mac")
        print("  $env:GEMINI_API_KEY='your-key-here'    # Windows PowerShell")
        print("  Or create a .env file with: GEMINI_API_KEY=your-key-here")
        print()
        print("Continuing with stub mode for testing...")
        os.environ["AI_MODE"] = "stub"

from natal_chart import (
    NatalChart,
    calculate_numerology,
    get_chinese_zodiac_and_element
)
from app.services.llm_prompts import get_gemini3_reading, get_claude_reading


def calculate_test_chart():
    """Calculate the chart for Sofie AlQattan."""
    # Sofie AlQattan: 2005-04-25 06:00:00 LOCAL TIME, Kuwait City, Kuwait
    # Kuwait City coordinates: 29.3797° N, 47.9734° E
    # Kuwait City timezone: Asia/Kuwait (UTC+3)
    
    # Convert local time to UTC
    local_time = pendulum.datetime(2005, 4, 25, 6, 0, tz='Asia/Kuwait')
    utc_time = local_time.in_timezone('UTC')
    
    chart = NatalChart(
        name="Sofie AlQattan",
        year=utc_time.year,
        month=utc_time.month,
        day=utc_time.day,
        hour=utc_time.hour,
        minute=utc_time.minute,
        latitude=29.3797,
        longitude=47.9734
    )
    
    chart.calculate_chart(unknown_time=False)
    
    # Calculate numerology (function signature: day, month, year)
    numerology_result = calculate_numerology(25, 4, 2005)
    numerology = {
        "life_path_number": numerology_result.get("life_path_number", 0),
        "day_number": numerology_result.get("day_number", 0)
    }
    
    # Calculate Chinese zodiac
    chinese_zodiac = get_chinese_zodiac_and_element(2005, 4, 25)
    
    # Get full chart data
    chart_data = chart.get_full_chart_data(numerology, None, chinese_zodiac, False)
    
    return chart_data


def grade_reading(reading: str) -> Dict[str, Any]:
    """Grade the reading against all requirements."""
    reading_lower = reading.lower()
    
    grades = {}
    issues = []
    strengths = []
    
    # 1. Stellium explicit listing
    stellium_keywords = [
        "stellium includes",
        "stellium contains",
        "sun in aries" in reading_lower and "venus in aries" in reading_lower and "true node" in reading_lower,
    ]
    has_stellium_listing = any(
        kw in reading_lower if isinstance(kw, str) else kw 
        for kw in stellium_keywords
    )
    if has_stellium_listing:
        grades["stellium_listing"] = "PASS"
        strengths.append("Stellium explicitly lists planets")
    else:
        grades["stellium_listing"] = "FAIL"
        issues.append("Stellium not explicitly listed with all planets, signs, and degrees")
    
    # 2. Planetary Dignities section
    has_dignities = (
        "planetary dignities" in reading_lower or 
        "dignities & conditions" in reading_lower or
        ("exaltation" in reading_lower and "fall" in reading_lower)
    )
    if has_dignities:
        grades["planetary_dignities"] = "PASS"
        strengths.append("Planetary Dignities section present")
    else:
        grades["planetary_dignities"] = "FAIL"
        issues.append("Planetary Dignities section missing")
    
    # 3. Aspects coverage (5-7)
    aspect_count = reading.count("aspect") + reading.count("Aspect")
    if aspect_count >= 5:
        grades["aspects_coverage"] = "PASS"
        strengths.append(f"Good aspect coverage ({aspect_count} mentions)")
    else:
        grades["aspects_coverage"] = "FAIL"
        issues.append(f"Only {aspect_count} aspect mentions - need at least 5 detailed aspects")
    
    # 4. Aspect mechanism explanations
    mechanism_keywords = ["why", "because", "mechanism", "creates", "geometric"]
    mechanism_count = sum(1 for kw in mechanism_keywords if kw in reading_lower)
    if mechanism_count >= 3:
        grades["aspect_mechanisms"] = "PASS"
        strengths.append("Aspect mechanisms explained")
    else:
        grades["aspect_mechanisms"] = "PARTIAL"
        issues.append("Aspect mechanism explanations could be more detailed")
    
    # 5. Houses analysis (all 12)
    house_count = sum(1 for i in range(1, 13) if f"{i}st house" in reading_lower or f"{i}nd house" in reading_lower or 
                     f"{i}rd house" in reading_lower or f"{i}th house" in reading_lower or
                     f"house {i}" in reading_lower)
    if house_count >= 12:
        grades["houses_coverage"] = "PASS"
        strengths.append(f"All {house_count} houses covered")
    else:
        grades["houses_coverage"] = "FAIL"
        issues.append(f"Only {house_count} houses mentioned - need all 12")
    
    # 6. Spiritual Path separate
    has_spiritual = "spiritual path" in reading_lower or "spiritual path & meaning" in reading_lower
    has_famous = "famous people" in reading_lower
    if has_spiritual and has_famous:
        # Check if they're in separate sections
        spiritual_idx = reading_lower.find("spiritual")
        famous_idx = reading_lower.find("famous")
        if abs(spiritual_idx - famous_idx) > 500:  # They're separated
            grades["spiritual_separate"] = "PASS"
            strengths.append("Spiritual Path and Famous People are separate")
        else:
            grades["spiritual_separate"] = "FAIL"
            issues.append("Spiritual Path and Famous People appear to be mixed")
    else:
        grades["spiritual_separate"] = "PARTIAL"
        issues.append("Missing Spiritual Path or Famous People section")
    
    # 7. Concrete examples
    example_keywords = ["when", "in relationships", "at work", "during", "this shows up as", "manifest"]
    example_count = sum(1 for kw in example_keywords if kw in reading_lower)
    if example_count >= 20:
        grades["concrete_examples"] = "PASS"
        strengths.append(f"Good use of concrete examples ({example_count} instances)")
    elif example_count >= 10:
        grades["concrete_examples"] = "PARTIAL"
        issues.append(f"Could use more concrete examples ({example_count} found)")
    else:
        grades["concrete_examples"] = "FAIL"
        issues.append(f"Insufficient concrete examples ({example_count} found)")
    
    # 8. How Shadows Interact
    has_shadow_interaction = "how shadows interact" in reading_lower or "shadows interact" in reading_lower
    if has_shadow_interaction:
        grades["shadow_interactions"] = "PASS"
        strengths.append("How Shadows Interact subsection present")
    else:
        grades["shadow_interactions"] = "FAIL"
        issues.append("How Shadows Interact subsection missing")
    
    # 9. Emotional Life depth
    has_emotional_subsections = (
        "family dynamics" in reading_lower or
        "childhood patterns" in reading_lower or
        "healing modalities" in reading_lower
    )
    emotional_length = len([p for p in reading.split("\n\n") if "emotional" in p.lower() or "family" in p.lower()])
    if has_emotional_subsections and emotional_length >= 3:
        grades["emotional_depth"] = "PASS"
        strengths.append("Emotional Life section has required subsections")
    else:
        grades["emotional_depth"] = "PARTIAL"
        issues.append("Emotional Life section could be deeper with required subsections")
    
    # 10. Work/Money depth
    has_work_subsections = (
        "career paths" in reading_lower or
        "money patterns" in reading_lower or
        "mars" in reading_lower and "capricorn" in reading_lower
    )
    if has_work_subsections:
        grades["work_depth"] = "PASS"
        strengths.append("Work/Money section has required subsections")
    else:
        grades["work_depth"] = "PARTIAL"
        issues.append("Work/Money section could include more specific subsections")
    
    # 11. Operating System expanded
    has_operating_system = "operating system" in reading_lower
    has_mode_comparison = ("default mode" in reading_lower and "high expression" in reading_lower) or \
                         ("default" in reading_lower and "integrated" in reading_lower)
    if has_operating_system and has_mode_comparison:
        grades["operating_system"] = "PASS"
        strengths.append("Operating System section expanded with mode comparison")
    else:
        grades["operating_system"] = "PARTIAL"
        issues.append("Operating System section could be more expanded")
    
    # Calculate overall grade
    pass_count = sum(1 for v in grades.values() if v == "PASS")
    partial_count = sum(1 for v in grades.values() if v == "PARTIAL")
    fail_count = sum(1 for v in grades.values() if v == "FAIL")
    
    total_checks = len(grades)
    score = (pass_count * 100 + partial_count * 70 + fail_count * 0) / total_checks
    
    if score >= 90:
        overall_grade = "A"
    elif score >= 80:
        overall_grade = "B"
    elif score >= 70:
        overall_grade = "C"
    else:
        overall_grade = "D"
    
    return {
        "overall_grade": overall_grade,
        "score": score,
        "grades": grades,
        "strengths": strengths,
        "issues": issues,
        "pass_count": pass_count,
        "partial_count": partial_count,
        "fail_count": fail_count,
        "total_checks": total_checks
    }


async def main():
    """Generate and grade a reading."""
    print("=" * 80)
    print("GENERATING AND GRADING READING")
    print("=" * 80)
    print()
    print("Chart: Sofie AlQattan")
    print("Birth: 2005-04-25 06:00:00 LOCAL TIME (Kuwait City)")
    print("Location: Kuwait City, Kuwait")
    print()
    
    # Calculate chart
    print("Step 1: Calculating chart...")
    chart_data = calculate_test_chart()
    print("[OK] Chart calculated")
    print()
    
    # Generate reading
    print("Step 2: Generating reading (this may take several minutes)...")
    print("-" * 80)
    reading = None
    
    # Use a wrapper to capture the reading even if there's a Unicode logging error
    import sys
    import io
    
    # Redirect stderr temporarily to capture Unicode errors
    old_stderr = sys.stderr
    stderr_capture = io.StringIO()
    
    try:
        # Try to get the reading using Claude
        try:
            reading = await get_claude_reading(
                chart_data=chart_data,
                unknown_time=False,
                db=None
            )
            print()
            print("[OK] Reading generated")
            print()
        except Exception as e:
            error_str = str(e)
            # Check if this is a Unicode encoding error in logging
            if ("charmap" in error_str.lower() or "unicode" in error_str.lower()) and "position 0-34" in error_str:
                # This is the Unicode box-drawing character error in logging
                # The reading was likely generated successfully before the print statement failed
                # Try to extract it from the logs or re-call without the problematic logging
                print("[WARNING] Unicode encoding error in logging detected")
                print("Attempting to recover reading...")
                
                # The reading should have been generated - check logs for length
                # We'll need to call it again but suppress the problematic print
                # Actually, let's just check if we can get it from a second attempt with error handling
                pass
            else:
                # Real error - re-raise
                raise
    
    except Exception as e:
        # Final check - if we still don't have a reading, it's a real failure
        if not reading or len(reading) < 1000:
            print(f"ERROR: Failed to generate reading: {e}")
            print("This appears to be a real error, not just a logging issue.")
            import traceback
            traceback.print_exc()
            return 1
        else:
            print("[WARNING] Exception occurred but reading was generated")
            print(f"Reading length: {len(reading):,} characters")
    
    finally:
        sys.stderr = old_stderr
    
    if not reading or len(reading) < 1000:
        print("ERROR: No valid reading was generated")
        return 1
    
    # Save reading
    output_file = project_root / "generated_reading.txt"
    output_file.write_text(reading, encoding='utf-8')
    print(f"Reading saved to: {output_file}")
    print()
    
    # Grade reading
    print("Step 3: Grading reading...")
    print("-" * 80)
    grade_results = grade_reading(reading)
    
    # Print results
    print()
    print("=" * 80)
    print("GRADING RESULTS")
    print("=" * 80)
    print()
    print(f"Overall Grade: {grade_results['overall_grade']} ({grade_results['score']:.1f}/100)")
    print()
    print(f"Pass: {grade_results['pass_count']}/{grade_results['total_checks']}")
    print(f"Partial: {grade_results['partial_count']}/{grade_results['total_checks']}")
    print(f"Fail: {grade_results['fail_count']}/{grade_results['total_checks']}")
    print()
    
    print("DETAILED GRADES:")
    print("-" * 80)
    for check_name, result in grade_results['grades'].items():
        status = "[PASS]" if result == "PASS" else "[PARTIAL]" if result == "PARTIAL" else "[FAIL]"
        print(f"{status} {check_name.replace('_', ' ').title()}")
    print()
    
    if grade_results['strengths']:
        print("STRENGTHS:")
        print("-" * 80)
        for strength in grade_results['strengths']:
            print(f"[+] {strength}")
        print()
    
    if grade_results['issues']:
        print("ISSUES TO ADDRESS:")
        print("-" * 80)
        for issue in grade_results['issues']:
            print(f"[-] {issue}")
        print()
    
    # Save grade report
    grade_file = project_root / "reading_grade_report.json"
    grade_file.write_text(json.dumps(grade_results, indent=2), encoding='utf-8')
    print(f"Grade report saved to: {grade_file}")
    print()
    
    print("=" * 80)
    print(f"Reading length: {len(reading):,} characters")
    print(f"Reading saved to: {output_file}")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

