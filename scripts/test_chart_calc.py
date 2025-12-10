#!/usr/bin/env python3
"""Test script to verify chart calculation works."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['OPENCAGE_KEY'] = '122d238a65bc443297d6144ba105975d'

print("=" * 60)
print("Testing Chart Calculation Script")
print("=" * 60)
print(f"OPENCAGE_KEY: {os.getenv('OPENCAGE_KEY')[:20]}...")

try:
    from scripts.calculate_famous_people_charts import process_famous_people
    print("✓ Successfully imported process_famous_people")
    
    print("\nCalling process_famous_people()...")
    process_famous_people()
    print("\n✓ Script completed!")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

