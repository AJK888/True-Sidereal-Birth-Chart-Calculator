# api.py

import time # Add this import at the top
from fastapi import FastAPI, HTTPException
# ... (all other imports)

# ... (rest of the file is the same until the endpoint function)

@app.post("/calculate_chart")
def calculate_chart_endpoint(data: ChartRequest):
    start_time = time.time()
    print(f"[{time.time() - start_time:.2f}s] Request received for {data.location}.")
    
    try:
        swe.set_ephe_path(r".")

        # --- GEOCODING ---
        print(f"[{time.time() - start_time:.2f}s] Starting geocoding...")
        opencage_key = os.getenv("OPENCAGE_KEY")
        # ... (rest of geocoding logic)
        response = requests.get(geo_url, timeout=15)
        response.raise_for_status()
        geo_res = response.json()
        print(f"[{time.time() - start_time:.2f}s] Geocoding finished.")

        # --- TIMEZONE CONVERSION ---
        # ... (timezone logic is the same)
        utc_time = local_time.in_timezone('UTC')
        print(f"[{time.time() - start_time:.2f}s] Timezone converted.")

        # --- CHART CALCULATION ---
        chart = NatalChart(...) # Simplified for brevity
        print(f"[{time.time() - start_time:.2f}s] Starting main chart calculation...")
        chart.calculate_chart()
        print(f"[{time.time() - start_time:.2f}s] Chart calculation finished.")

        # ... (rest of the function, including the return statement, is the same)
        
    except Exception as e:
        print(f"[{time.time() - start_time:.2f}s] An error occurred.")
        # ... (rest of error handling)
