#!/usr/bin/env python3
"""Test script to verify numerology and Chinese zodiac calculations."""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['OPENCAGE_KEY'] = '122d238a65bc443297d6144ba105975d'

print("=" * 70)
print("TESTING NUMEROLOGY AND CHINESE ZODIAC CALCULATIONS")
print("=" * 70)

try:
    from scripts.calculate_famous_people_charts import calculate_person_chart
    from natal_chart import calculate_numerology, get_chinese_zodiac_and_element
    
    # Load test data
    with open('famous_people_data.json', 'r', encoding='utf-8') as f:
        people_data = json.load(f)
    
    print(f"\nLoaded {len(people_data)} people from JSON")
    
    # Test first person
    if people_data:
        person = people_data[0]
        print(f"\nTesting with: {person.get('name')}")
        
        birth_date = person.get('birth_date', {})
        year = birth_date.get('year')
        month = birth_date.get('month')
        day = birth_date.get('day')
        
        print(f"Birth date: {month}/{day}/{year}")
        
        # Test numerology calculation
        numerology = calculate_numerology(day, month, year)
        print(f"\nNumerology:")
        print(f"  Life Path: {numerology.get('life_path')}")
        print(f"  Day Number: {numerology.get('day_number')}")
        
        # Test Chinese zodiac
        chinese = get_chinese_zodiac_and_element(year, month, day)
        print(f"\nChinese Zodiac:")
        print(f"  Animal: {chinese.get('animal')}")
        print(f"  Element: {chinese.get('element')}")
        
        # Test full chart calculation
        print(f"\nCalculating full chart...")
        result = calculate_person_chart(person)
        
        if result:
            chart_data = result['chart_data']
            print(f"✓ Chart calculated successfully")
            
            # Check numerology in chart data
            num_data = chart_data.get('numerology_analysis', {})
            print(f"\nNumerology in chart data:")
            print(f"  Life Path: {num_data.get('life_path_number')}")
            print(f"  Day Number: {num_data.get('day_number')}")
            
            # Check Chinese zodiac in chart data
            cz = chart_data.get('chinese_zodiac', '')
            print(f"\nChinese Zodiac in chart data: {cz}")
            
        else:
            print("✗ Failed to calculate chart")
    
    print("\n" + "=" * 70)
    print("Now running full process...")
    print("=" * 70)
    
    from scripts.calculate_famous_people_charts import process_famous_people
    process_famous_people()
    
    print("\n" + "=" * 70)
    print("PROCESS COMPLETE")
    print("=" * 70)
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

