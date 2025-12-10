"""Monitor the progress of the scrape_and_calculate_5000.py script."""
import sqlite3
import time
import os

db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'synthesis_astrology.db')
output_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'full_process_output.txt')

target = 5000
check_interval = 30  # Check every 30 seconds

print("=" * 70)
print("MONITORING SCRAPER PROGRESS")
print("=" * 70)
print(f"Target: {target} people")
print(f"Checking every {check_interval} seconds...")
print("=" * 70)

last_count = 0
start_time = time.time()

while True:
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM famous_people')
        count = c.fetchone()[0]
        conn.close()
        
        elapsed = time.time() - start_time
        elapsed_min = elapsed / 60
        
        if count > last_count:
            rate = (count - last_count) / (check_interval / 60) if elapsed > check_interval else 0
            remaining = (target - count) / rate if rate > 0 else 0
            print(f"[{time.strftime('%H:%M:%S')}] Count: {count}/{target} (+{count - last_count} in last {check_interval}s, ~{rate:.1f}/min, ~{remaining:.1f} min remaining)")
            last_count = count
            
            if count >= target:
                print("\n" + "=" * 70)
                print("✓ TARGET REACHED!")
                print(f"Total people: {count}")
                print(f"Total time: {elapsed_min:.1f} minutes")
                print("=" * 70)
                break
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Count: {count}/{target} (no change)")
        
        # Check output file for errors
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    if 'ERROR' in last_line.upper() or 'FAILED' in last_line.upper():
                        print(f"\n⚠ WARNING: Last output line: {last_line}")
        
        time.sleep(check_interval)
        
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        break
    except Exception as e:
        print(f"\nError checking progress: {e}")
        time.sleep(check_interval)

