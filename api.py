# api.py (MANUAL LOGGING TEST)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from natal_chart import (
    NatalChart, get_sign_and_ruler, format_true_sidereal_placement, PLANETS_CONFIG, 
    calculate_numerology, get_chinese_zodiac
)
import swisseph as swe
import traceback
import requests
import pendulum
import os
import json
from datetime import datetime

app = FastAPI(title="True Sidereal API - Test Mode", version="1.0")

# --- SETUP ---
origins = ["https://true-sidereal-birth-chart.onrender.com"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["POST", "GET", "HEAD"], allow_headers=["*"])

class ChartRequest(BaseModel):
    name: str; year: int; month: int; day: int; hour: int; minute: int; location: str

@app.get("/ping")
def ping():
    return {"message": "ok"}

@app.post("/calculate_chart")
def calculate_chart_endpoint(data: ChartRequest):
    # --- MANUAL LOGGING TEST ---
    logtail_token = os.getenv("LOGTAIL_SOURCE_TOKEN")
    print(f"--- DEBUG: Attempting manual log. Token found: {'Yes' if logtail_token else 'No'} ---")
    
    if logtail_token:
        try:
            headers = {
                "Authorization": f"Bearer {logtail_token}",
                "Content-Type": "application/json"
            }
            log_payload = [{
                "dt": datetime.utcnow().isoformat() + "Z",
                "message": "Manual log test successful.",
                "level": "info",
                "context": { "chart_name": data.name, "location": data.location }
            }]
            
            print("--- DEBUG: Sending manual log to Better Stack... ---")
            log_response = requests.post("https://in.logtail.com", headers=headers, data=json.dumps(log_payload), timeout=10)
            
            print(f"--- DEBUG: Manual log response received. Status Code: {log_response.status_code} ---")
            if log_response.status_code != 202:
                print(f"--- DEBUG: Better Stack Response Text: {log_response.text} ---")

        except Exception as e:
            print(f"--- DEBUG: CRITICAL ERROR during manual log attempt: {e} ---")

    # The rest of the function will now run normally.
    try:
        swe.set_ephe_path(r".")
        
        # ... (Full calculation logic remains here, but is omitted for brevity)
        # ... The code below is a placeholder for your real calculation logic.
        
        # This part is just to ensure the function returns something.
        # Your actual, full calculation logic should be here.
        chart = {"name": data.name, "utc_datetime": "Calculated", "location": "Calculated", "day_night_status": "Calculated", "chart_analysis": {}, "major_positions": [], "aspects": [], "aspect_patterns": [], "additional_points": [], "house_rulers": {}, "house_sign_distributions": {}}


        return chart # Returning a simplified version for the test
    
    except Exception as e:
        print("\n--- AN EXCEPTION WAS CAUGHT IN MAIN LOGIC ---"); traceback.print_exc(); print("-----------------------------\n")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")
