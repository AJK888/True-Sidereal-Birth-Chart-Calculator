# api.py (TESTING VERSION)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# Note: Other imports are not needed for this simple test
import os
import time

app = FastAPI(title="True Sidereal API - Test Mode", version="1.0")

origins = [
    "https://true-sidereal-birth-chart.onrender.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "HEAD"],
    allow_headers=["*"],
)

class ChartRequest(BaseModel):
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    location: str

@app.get("/ping")
def ping():
    return {"message": "ok"}

@app.post("/calculate_chart")
def calculate_chart_endpoint(data: ChartRequest):
    # This function now only prints to the log and returns dummy data instantly.
    print(f"--- TEST SUCCESSFUL: Request received for {data.name} at {time.time()} ---")
    
    return {
        "name": data.name,
        "utc_datetime": "TEST MODE",
        "location": "TEST MODE",
        "day_night_status": "TEST MODE",
        "chart_analysis": {
            "chart_ruler": "TEST", "dominant_sign": "TEST", "dominant_element": "TEST",
            "dominant_modality": "TEST", "dominant_planet": "TEST", "life_path_number": "TEST",
            "day_number": "TEST", "chinese_zodiac": "TEST"
        },
        "major_positions": [],
        "aspects": [],
        "aspect_patterns": [],
        "additional_points": [],
        "house_rulers": {},
        "house_sign_distributions": {}
    }
