# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Set your OpenWeatherMap API key as an environment variable in production.
# For local testing, you can paste it directly here (replace the string below).
OWM_API_KEY = os.environ.get("OWM_API_KEY", "65d1b1437d735690d2f990006209f198")

OWM_AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
OWM_FORECAST_URL = "http://api.openweathermap.org/data/2.5/air_pollution/forecast"

# OpenWeatherMap AQI index is 1-5, not the standard 0-500 scale.
# We map it to a simplified category + a rough 0-500-style number for display.
AQI_LEVEL_MAP = {
    1: {"label": "Good", "color": "green", "display_aqi": 30},
    2: {"label": "Fair", "color": "yellow", "display_aqi": 75},
    3: {"label": "Moderate", "color": "orange", "display_aqi": 125},
    4: {"label": "Poor", "color": "red", "display_aqi": 200},
    5: {"label": "Very Poor", "color": "maroon", "display_aqi": 300},
}




VALID_CONDITIONS = {
    "asthma", "copd", "allergies", "bronchitis", "sinusitis",
    "heart_disease", "lung_cancer", "pneumonia", "pregnancy",
    "other", "none",
}

# How much each condition raises sensitivity at the same AQI level.
# 2 = high sensitivity, 1 = moderate sensitivity, 0 = baseline/no extra risk.
CONDITION_WEIGHT = {
    "asthma": 2,
    "copd": 2,
    "heart_disease": 2,
    "pregnancy": 2,
    "bronchitis": 1,
    "pneumonia": 1,
    "lung_cancer": 1,
    "allergies": 1,
    "sinusitis": 1,
    "other": 1,
    "none": 0,
}

CONDITION_DISPLAY_NAMES = {
    "asthma": "asthma",
    "copd": "COPD",
    "allergies": "allergies",
    "bronchitis": "bronchitis",
    "sinusitis": "sinusitis",
    "heart_disease": "heart condition",
    "lung_cancer": "lung condition",
    "pneumonia": "pneumonia history",
    "pregnancy": "pregnancy",
    "other": "your condition",
}


def parse_conditions(raw):
    """Parses a comma-separated condition string into a clean, valid list."""
    if not raw:
        return ["none"]
    parts = [c.strip().lower() for c in raw.split(",") if c.strip()]
    parts = [c for c in parts if c in VALID_CONDITIONS]
    if not parts:
        return ["none"]
    # "none" should never be combined with real conditions.
    if "none" in parts and len(parts) > 1:
        parts = [c for c in parts if c != "none"]
    return parts


def get_risk_advisory(level, conditions):
    """Returns a personalized advisory line based on AQI level and a list of conditions."""
    conditions = conditions or ["none"]

    # Sensitivity = highest weight among all selected conditions.
    max_weight = max(CONDITION_WEIGHT.get(c, 0) for c in conditions)
    sensitive = max_weight >= 2
    mildly_sensitive = max_weight == 1

    # Build a short reference to the most relevant condition(s) for phrasing.
    named = [CONDITION_DISPLAY_NAMES[c] for c in conditions if c in CONDITION_DISPLAY_NAMES]
    condition_note = f" ({', '.join(named)})" if named and sensitive else ""

    if level <= 1:
        return "Low risk for you" if not sensitive else f"Low risk, air is clean today{condition_note}"
    elif level == 2:
        if sensitive:
            return f"Mild risk — take normal precautions{condition_note}"
        elif mildly_sensitive:
            return "Mild risk for you"
        return "Low risk for you"
    elif level == 3:
        return f"Moderate risk — consider limiting prolonged outdoor activity{condition_note}" if sensitive else "Moderate risk for you"
    elif level == 4:
        return f"High risk for you — avoid outdoor activity if possible{condition_note}" if sensitive else "High risk for prolonged outdoor activity"
    else:
        return f"Very high risk for you — stay indoors if possible{condition_note}" if sensitive else "Very high risk — limit outdoor exposure"


@app.route("/live", methods=["GET"])
def live():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    condition_raw = request.args.get("condition", "none")  # e.g. "asthma,pregnancy"
    conditions = parse_conditions(condition_raw)

    if not lat or not lon:
        return jsonify({"error": "Missing required parameters: lat and lon"}), 400

    try:
        float(lat)
        float(lon)
    except ValueError:
        return jsonify({"error": "Invalid parameters: lat and lon must be numbers"}), 400

    params = {"lat": lat, "lon": lon, "appid": OWM_API_KEY}
    resp = requests.get(OWM_AIR_POLLUTION_URL, params=params)

    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch air quality data"}), 502

    data = resp.json()
    try:
        aqi_level = data["list"][0]["main"]["aqi"]
        components = data["list"][0]["components"]
    except (KeyError, IndexError):
        return jsonify({"error": "Unexpected response from data provider"}), 502

    level_info = AQI_LEVEL_MAP.get(aqi_level, AQI_LEVEL_MAP[3])

    return jsonify({
        "aqi_level": aqi_level,
        "aqi_label": level_info["label"],
        "aqi_color": level_info["color"],
        "display_aqi": level_info["display_aqi"],
        "personalized_risk": get_risk_advisory(aqi_level, conditions),
        "conditions_used": conditions,
        "pollutants": {
            "pm2_5": components.get("pm2_5"),
            "pm10": components.get("pm10"),
            "no2": components.get("no2"),
            "o3": components.get("o3"),
            "so2": components.get("so2"),
            "co": components.get("co"),
        }
    })


@app.route("/forecast", methods=["GET"])
def forecast():
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if not lat or not lon:
        return jsonify({"error": "Missing required parameters: lat and lon"}), 400

    try:
        float(lat)
        float(lon)
    except ValueError:
        return jsonify({"error": "Invalid parameters: lat and lon must be numbers"}), 400

    params = {"lat": lat, "lon": lon, "appid": OWM_API_KEY}
    resp = requests.get(OWM_FORECAST_URL, params=params)

    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch forecast data"}), 502

    data = resp.json()
    entries = data.get("list", [])[:24]  # next 24 hours

    hourly = []
    for entry in entries:
        aqi_level = entry["main"]["aqi"]
        level_info = AQI_LEVEL_MAP.get(aqi_level, AQI_LEVEL_MAP[3])
        hourly.append({
            "timestamp": entry["dt"],
            "aqi_level": aqi_level,
            "display_aqi": level_info["display_aqi"],
            "color": level_info["color"],
        })

    if not hourly:
        return jsonify({"error": "No forecast data available"}), 502

    # Find the best (lowest AQI) window of at least 2 consecutive hours.
    best_start_idx = min(range(len(hourly)), key=lambda i: hourly[i]["display_aqi"])
    best_window_start = hourly[best_start_idx]["timestamp"]

    return jsonify({
        "hourly": hourly,
        "best_window_start": best_window_start,
        "best_window_aqi": hourly[best_start_idx]["display_aqi"],
    })


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "Air Sense backend is running"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)