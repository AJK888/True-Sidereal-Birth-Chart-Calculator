# In api.py, replace the whole calculate_chart_endpoint function

@app.post("/calculate_chart")
def calculate_chart_endpoint(data: ChartRequest):
    # This is a temporary test version that does no calculations
    print("DEBUG: Running in simplified test mode.")
    return {
        "name": data.name,
        "utc_datetime": "TEST DATA",
        "location": "TEST DATA",
        "day_night_status": "TEST DATA",
        "chart_analysis": {
            "chart_ruler": "TEST DATA", "dominant_sign": "TEST DATA",
            "dominant_element": "TEST DATA", "dominant_modality": "TEST DATA",
            "dominant_planet": "TEST DATA", "life_path_number": "TEST",
            "day_number": "TEST", "chinese_zodiac": "TEST"
        },
        "major_positions": [], "aspects": [], "aspect_patterns": [],
        "additional_points": [], "house_rulers": {},
        "house_sign_distributions": {}
    }
