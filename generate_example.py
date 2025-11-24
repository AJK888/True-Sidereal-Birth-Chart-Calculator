#!/usr/bin/env python3
"""
Example Chart Generator Script

This script generates example JSON files for the astrology website by calling
the API endpoints. It can be used interactively or with command-line arguments.

Usage:
    python generate_example.py
    python generate_example.py --name "Elon Musk" --year 1971 --month 6 --day 28 --hour 7 --minute 30 --location "Pretoria, South Africa"
    python generate_example.py --file examples.csv
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import requests
from pathlib import Path


# API Configuration
API_BASE_URL = "https://true-sidereal-api.onrender.com"
CALCULATE_ENDPOINT = f"{API_BASE_URL}/calculate_chart"
READING_ENDPOINT = f"{API_BASE_URL}/generate_reading"


def parse_time_string(time_str: str) -> Tuple[int, int]:
    """
    Parse time string in formats like "7:30 AM", "19:30", "7:30 PM"
    Returns (hour, minute) in 24-hour format
    """
    time_str = time_str.strip().upper()
    
    # Handle 24-hour format (e.g., "19:30")
    if "AM" not in time_str and "PM" not in time_str:
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return hour, minute
        except (ValueError, IndexError):
            raise ValueError(f"Invalid time format: {time_str}")
    
    # Handle 12-hour format
    is_pm = "PM" in time_str
    time_str = time_str.replace("AM", "").replace("PM", "").strip()
    
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        
        if hour == 12:
            hour = 0 if not is_pm else 12
        elif is_pm:
            hour += 12
            
        return hour, minute
    except (ValueError, IndexError):
        raise ValueError(f"Invalid time format: {time_str}")


def parse_date_string(date_str: str) -> Tuple[int, int, int]:
    """
    Parse date string in formats like "June 28, 1971", "6/28/1971", "1971-06-28"
    Returns (year, month, day)
    """
    date_str = date_str.strip()
    
    # Try ISO format first (YYYY-MM-DD)
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.year, dt.month, dt.day
    except ValueError:
        pass
    
    # Try US format (MM/DD/YYYY or M/D/YYYY)
    try:
        parts = date_str.split("/")
        if len(parts) == 3:
            month = int(parts[0])
            day = int(parts[1])
            year = int(parts[2])
            if year < 100:
                year += 2000 if year < 50 else 1900
            return year, month, day
    except (ValueError, IndexError):
        pass
    
    # Try full date format (e.g., "June 28, 1971")
    try:
        dt = datetime.strptime(date_str, "%B %d, %Y")
        return dt.year, dt.month, dt.day
    except ValueError:
        pass
    
    try:
        dt = datetime.strptime(date_str, "%b %d, %Y")
        return dt.year, dt.month, dt.day
    except ValueError:
        pass
    
    raise ValueError(f"Could not parse date: {date_str}. Try formats like 'June 28, 1971', '6/28/1971', or '1971-06-28'")


def format_birth_date(year: int, month: int, day: int) -> str:
    """Format date as 'Month Day, Year'"""
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    return f"{month_names[month - 1]} {day}, {year}"


def format_birth_time(hour: int, minute: int) -> str:
    """Format time as 'H:MM AM/PM'"""
    if hour == 0:
        display_hour = 12
        period = "AM"
    elif hour < 12:
        display_hour = hour
        period = "AM"
    elif hour == 12:
        display_hour = 12
        period = "PM"
    else:
        display_hour = hour - 12
        period = "PM"
    
    return f"{display_hour}:{minute:02d} {period}"


def calculate_chart(name: str, year: int, month: int, day: int, hour: int, minute: int, 
                   location: str, unknown_time: bool = False) -> Dict[str, Any]:
    """
    Call the calculate_chart API endpoint and return the chart data.
    """
    print(f"Calculating chart for {name}...")
    
    payload = {
        "full_name": name,
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute,
        "location": location,
        "unknown_time": unknown_time,
        "no_full_name": False
    }
    
    try:
        response = requests.post(CALCULATE_ENDPOINT, json=payload, timeout=60)
        response.raise_for_status()
        chart_data = response.json()
        print("✓ Chart calculated successfully")
        return chart_data
    except requests.exceptions.RequestException as e:
        print(f"✗ Error calculating chart: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        raise


def generate_reading(chart_data: Dict[str, Any], unknown_time: bool, name: str) -> str:
    """
    Call the generate_reading API endpoint and return the AI reading.
    """
    print(f"Generating AI reading for {name}...")
    
    payload = {
        "chart_data": chart_data,
        "unknown_time": unknown_time,
        "user_inputs": {
            "full_name": name
        }
    }
    
    try:
        response = requests.post(READING_ENDPOINT, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        reading = result.get("gemini_reading", "")
        print("✓ AI reading generated successfully")
        return reading
    except requests.exceptions.RequestException as e:
        print(f"✗ Error generating reading: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        raise


def generate_example_json(name: str, year: int, month: int, day: int, 
                         hour: int, minute: int, location: str, 
                         unknown_time: bool = False,
                         output_dir: Optional[str] = None) -> str:
    """
    Generate a complete example JSON file by calling both API endpoints.
    Returns the path to the saved JSON file.
    """
    # Calculate chart
    chart_data = calculate_chart(name, year, month, day, hour, minute, location, unknown_time)
    
    # Generate reading
    ai_reading = generate_reading(chart_data, unknown_time, name)
    
    # Format metadata
    birth_date = format_birth_date(year, month, day)
    birth_time = format_birth_time(hour, minute) if not unknown_time else None
    
    # Create output structure
    output = {
        "metadata": {
            "name": name,
            "birth_date": birth_date,
            "birth_time": birth_time if birth_time else None,
            "location": location,
            "unknown_time": unknown_time
        },
        "ai_reading": ai_reading,
        "chart_data": chart_data
    }
    
    # Determine output filename
    if output_dir is None:
        # Default to examples/data directory in frontend repo
        script_dir = Path(__file__).parent
        frontend_dir = script_dir / "True-Sidereal-Birth-Chart-Calculator"
        if not frontend_dir.exists():
            frontend_dir = script_dir
        output_dir = frontend_dir / "examples" / "data"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create filename from name (e.g., "Elon Musk" -> "elon-musk.json")
    filename = name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    output_path = output_dir / f"{filename}.json"
    
    # Save JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Example file saved to: {output_path}")
    return str(output_path)


def interactive_mode():
    """Run the script in interactive mode, prompting for user input."""
    print("=" * 60)
    print("Example Chart Generator - Interactive Mode")
    print("=" * 60)
    print()
    
    # Get name
    name = input("Full name: ").strip()
    if not name:
        print("Error: Name is required")
        return
    
    # Get date
    date_str = input("Birth date (e.g., 'June 28, 1971' or '6/28/1971'): ").strip()
    try:
        year, month, day = parse_date_string(date_str)
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    # Get time
    unknown_time_input = input("Unknown birth time? (y/n): ").strip().lower()
    unknown_time = unknown_time_input == 'y'
    
    hour, minute = 12, 0  # Default to noon
    if not unknown_time:
        time_str = input("Birth time (e.g., '7:30 AM' or '19:30'): ").strip()
        try:
            hour, minute = parse_time_string(time_str)
        except ValueError as e:
            print(f"Error: {e}")
            return
    
    # Get location
    location = input("Birth location (e.g., 'Pretoria, South Africa'): ").strip()
    if not location:
        print("Error: Location is required")
        return
    
    # Confirm
    print()
    print("Summary:")
    print(f"  Name: {name}")
    print(f"  Date: {format_birth_date(year, month, day)}")
    if not unknown_time:
        print(f"  Time: {format_birth_time(hour, minute)}")
    else:
        print(f"  Time: Unknown")
    print(f"  Location: {location}")
    print()
    
    confirm = input("Generate example? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    # Generate
    try:
        output_path = generate_example_json(
            name, year, month, day, hour, minute, location, unknown_time
        )
        print(f"\n✓ Success! File saved to: {output_path}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate example JSON files for astrology website",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python generate_example.py
  
  # Command-line mode
  python generate_example.py --name "Elon Musk" --year 1971 --month 6 --day 28 --hour 7 --minute 30 --location "Pretoria, South Africa"
  
  # With date/time strings
  python generate_example.py --name "Barack Obama" --date "August 4, 1961" --time "7:24 PM" --location "Honolulu, Hawaii, USA"
        """
    )
    
    parser.add_argument("--name", type=str, help="Full name")
    parser.add_argument("--year", type=int, help="Birth year")
    parser.add_argument("--month", type=int, help="Birth month (1-12)")
    parser.add_argument("--day", type=int, help="Birth day")
    parser.add_argument("--hour", type=int, default=12, help="Birth hour (0-23, default: 12)")
    parser.add_argument("--minute", type=int, default=0, help="Birth minute (0-59, default: 0)")
    parser.add_argument("--date", type=str, help="Birth date as string (e.g., 'June 28, 1971' or '6/28/1971')")
    parser.add_argument("--time", type=str, help="Birth time as string (e.g., '7:30 AM' or '19:30')")
    parser.add_argument("--location", type=str, help="Birth location")
    parser.add_argument("--unknown-time", action="store_true", help="Birth time is unknown")
    parser.add_argument("--output-dir", type=str, help="Output directory (default: examples/data)")
    
    args = parser.parse_args()
    
    # If no arguments provided, run in interactive mode
    if not any(vars(args).values()):
        interactive_mode()
        return
    
    # Validate required arguments
    if not args.name:
        print("Error: --name is required")
        parser.print_help()
        sys.exit(1)
    
    if not args.location:
        print("Error: --location is required")
        parser.print_help()
        sys.exit(1)
    
    # Parse date
    if args.date:
        try:
            year, month, day = parse_date_string(args.date)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.year and args.month and args.day:
        year, month, day = args.year, args.month, args.day
    else:
        print("Error: Must provide either --date or --year --month --day")
        parser.print_help()
        sys.exit(1)
    
    # Parse time
    if args.unknown_time:
        hour, minute = 12, 0
    elif args.time:
        try:
            hour, minute = parse_time_string(args.time)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.hour is not None:
        hour, minute = args.hour, args.minute
    else:
        hour, minute = 12, 0
    
    # Generate example
    try:
        output_path = generate_example_json(
            args.name, year, month, day, hour, minute, args.location,
            args.unknown_time, args.output_dir
        )
        print(f"\n✓ Success! File saved to: {output_path}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

