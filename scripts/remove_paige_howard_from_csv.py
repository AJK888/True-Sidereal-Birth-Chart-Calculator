"""
Script to remove Paige Howard from the famous_people_export.csv file.
"""
import csv
import os
import sys

def remove_paige_howard_from_csv():
    """Remove Paige Howard from the CSV export file."""
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "famous_people_export.csv"
    )
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
    
    # Read all lines
    lines = []
    removed = False
    
    with open(csv_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            # Check if this is Paige Howard (name is in column 1, index 1)
            if len(row) > 1 and row[1] == "Paige Howard":
                print(f"Found and removing: {row[1]} (ID: {row[0]})")
                removed = True
                continue
            lines.append(row)
    
    if not removed:
        print("Paige Howard not found in CSV file")
        return
    
    # Write back to file
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(lines)
    
    print(f"Successfully removed Paige Howard from {csv_path}")

if __name__ == "__main__":
    print("=" * 60)
    print("Removing Paige Howard from famous_people_export.csv")
    print("=" * 60)
    remove_paige_howard_from_csv()
    print("=" * 60)
    print("Done!")

