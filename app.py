import os
import time
import logging
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

# Initialize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Load env variables
load_dotenv()
OWM_API_KEY = os.getenv("OWM_API_KEY")

app = Flask(__name__)

# Add CORS headers for developer convenience
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response

# AQI Mapping config
AQI_MAPPING = {
    1: {"label": "Good", "color": "green", "display_aqi": 40},
    2: {"label": "Fair", "color": "yellow", "display_aqi": 75},
    3: {"label": "Moderate", "color": "orange", "display_aqi": 130},
    4: {"label": "Poor", "color": "red", "display_aqi": 185},
    5: {"label": "Very Poor", "color": "maroon", "display_aqi": 350}
}

# Personalized risk guidance
RISK_MAPPINGS = {
    "none": {
        1: "Air quality is satisfactory, and air pollution poses little or no risk.",
        2: "Air quality is acceptable; however, some pollutants may cause moderate health concerns for a very small number of people.",
        3: "Members of sensitive groups may experience health effects. The general public is less likely to be affected.",
        4: "Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects.",
        5: "Health alert: everyone may experience more serious health effects."
    },
    "asthma": {
        1: "Air is clean. Very low risk of asthma trigger.",
        2: "Minor risk. Asthmatics should monitor symptoms like coughing or wheezing.",
        3: "Moderate risk. Keep your quick-relief inhaler handy; consider reducing outdoor activities.",
        4: "High risk. Avoid outdoor activity, keep inhaler close, and stay indoors in clean air.",
        5: "Extreme risk. Severe asthma trigger potential. Stay indoors, run air purifiers, and follow your asthma action plan."
    },
    "allergies": {
        1: "Low allergen impact. Safe for outdoor activities.",
        2: "Mild allergen concern. Sensitive allergy sufferers might feel mild irritation.",
        3: "Moderate allergen impact. Take allergy medications if needed; limit prolonged outdoor exposure.",
        4: "High allergen impact. Stay indoors with windows closed and use air conditioning.",
        5: "Severe allergy threat. High risk of sinus irritation, itching, or respiratory distress. Stay indoors."
    },
    "copd": {
        1: "Safe conditions for COPD patients. Easy breathing.",
        2: "Generally safe, but monitor breathing. Limit heavy exertion.",
        3: "Warning. COPD symptoms may worsen. Stay indoors in well-ventilated or air-conditioned rooms.",
        4: "Dangerous. High risk of breathing difficulties. Avoid all outdoor physical activity.",
        5: "Critical threat. Severe COPD exacerbation risk. Call doctor if symptoms worsen. Stay inside with clean air filtration."
    }
}

def get_personalized_risk(condition, aqi):
    # Normalize condition key
    cond_key = str(condition).lower().strip() if condition else "none"
    if cond_key not in RISK_MAPPINGS:
        cond_key = "none"
    
    # aqi should be bounded between 1 and 5
    aqi_val = max(1, min(5, int(aqi)))
    return RISK_MAPPINGS[cond_key][aqi_val]

def find_best_time_window(hourly_items):
    if not hourly_items:
        return None
    
    min_aqi = min(item["main"]["aqi"] for item in hourly_items)
    
    # Find the longest consecutive run of min_aqi
    best_run = []
    current_run = []
    
    for item in hourly_items:
        if item["main"]["aqi"] == min_aqi:
            current_run.append(item)
        else:
            if len(current_run) > len(best_run):
                best_run = current_run
            current_run = []
            
    if len(current_run) > len(best_run):
        best_run = current_run
        
    if not best_run:
        return None
        
    start_dt = best_run[0]["dt"]
    end_dt = best_run[-1]["dt"] + 3600  # End of the last hour block
    
    return {
        "aqi": min_aqi,
        "label": AQI_MAPPING[min_aqi]["label"],
        "color": AQI_MAPPING[min_aqi]["color"],
        "display_aqi": AQI_MAPPING[min_aqi]["display_aqi"],
        "start_time": start_dt,
        "end_time": end_dt,
        "start_time_formatted": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_dt)) + " UTC",
        "end_time_formatted": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(end_dt)) + " UTC",
        "duration_hours": len(best_run)
    }

# Check for API Key configuration
if not OWM_API_KEY or OWM_API_KEY == "65d1b1437d735690d2f990006209f198":
    logger.warning("OWM_API_KEY environment variable is not configured or using default placeholder. API requests may fail.")

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "running"}), 200

@app.route("/live", methods=["GET"])
def get_live_air_quality():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    condition = request.args.get("condition", "none")
    
    if not lat or not lon:
        return jsonify({"error": "Missing required parameters: lat and lon"}), 400
        
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except ValueError:
        return jsonify({"error": "Invalid parameters: lat and lon must be numbers"}), 400

    if not OWM_API_KEY:
        return jsonify({"error": "API configuration error: OWM_API_KEY is not set"}), 500
        
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        "lat": lat_f,
        "lon": lon_f,
        "appid": OWM_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"OpenWeatherMap API returned status {response.status_code}: {response.text}")
            return jsonify({
                "error": "Failed to fetch data from weather service",
                "remote_status": response.status_code,
                "details": response.json().get("message", response.text)
            }), response.status_code
            
        data = response.json()
        
        # Verify the structure of the returned response
        if not data.get("list") or len(data["list"]) == 0:
            return jsonify({"error": "No air quality data returned by service"}), 502
            
        latest = data["list"][0]
        aqi = latest["main"]["aqi"]
        components = latest["components"]
        
        mapped = AQI_MAPPING.get(aqi, {"label": "Unknown", "color": "grey", "display_aqi": 0})
        risk = get_personalized_risk(condition, aqi)
        
        result = {
            "coord": data.get("coord", {"lat": lat_f, "lon": lon_f}),
            "aqi": aqi,
            "aqi_display": mapped["display_aqi"],
            "label": mapped["label"],
            "color": mapped["color"],
            "condition": condition,
            "personalized_risk": risk,
            "pollutants": {
                "pm2_5": components.get("pm2_5"),
                "pm10": components.get("pm10"),
                "no2": components.get("no2"),
                "o3": components.get("o3"),
                "so2": components.get("so2"),
                "co": components.get("co")
            }
        }
        return jsonify(result), 200
        
    except requests.RequestException as e:
        logger.exception("Error calling OpenWeatherMap API")
        return jsonify({"error": "Failed to connect to weather service", "details": str(e)}), 502

@app.route("/forecast", methods=["GET"])
def get_air_quality_forecast():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    
    if not lat or not lon:
        return jsonify({"error": "Missing required parameters: lat and lon"}), 400
        
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except ValueError:
        return jsonify({"error": "Invalid parameters: lat and lon must be numbers"}), 400

    if not OWM_API_KEY:
        return jsonify({"error": "API configuration error: OWM_API_KEY is not set"}), 500
        
    url = "http://api.openweathermap.org/data/2.5/air_pollution/forecast"
    params = {
        "lat": lat_f,
        "lon": lon_f,
        "appid": OWM_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"OpenWeatherMap API returned status {response.status_code}: {response.text}")
            return jsonify({
                "error": "Failed to fetch forecast from weather service",
                "remote_status": response.status_code,
                "details": response.json().get("message", response.text)
            }), response.status_code
            
        data = response.json()
        forecast_list = data.get("list", [])
        
        # Filter for the next 24 hours
        now = int(time.time())
        twenty_four_hours_sec = 24 * 60 * 60
        
        hourly_data = [
            item for item in forecast_list
            if now <= item.get("dt", 0) <= now + twenty_four_hours_sec
        ]
        
        # Fallback if filtered list is empty (e.g. clock mismatch)
        if not hourly_data:
            hourly_data = forecast_list[:24]
            
        formatted_forecast = []
        for item in hourly_data:
            dt = item["dt"]
            aqi = item["main"]["aqi"]
            components = item.get("components", {})
            mapped = AQI_MAPPING.get(aqi, {"label": "Unknown", "color": "grey", "display_aqi": 0})
            
            formatted_forecast.append({
                "dt": dt,
                "time_formatted": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(dt)) + " UTC",
                "aqi": aqi,
                "aqi_display": mapped["display_aqi"],
                "label": mapped["label"],
                "color": mapped["color"],
                "pollutants": {
                    "pm2_5": components.get("pm2_5"),
                    "pm10": components.get("pm10"),
                    "no2": components.get("no2"),
                    "o3": components.get("o3"),
                    "so2": components.get("so2"),
                    "co": components.get("co")
                }
            })
            
        best_window = find_best_time_window(hourly_data)
        
        result = {
            "coord": data.get("coord", {"lat": lat_f, "lon": lon_f}),
            "forecast": formatted_forecast,
            "best_time_window": best_window
        }
        return jsonify(result), 200
        
    except requests.RequestException as e:
        logger.exception("Error calling OpenWeatherMap API")
        return jsonify({"error": "Failed to connect to weather service", "details": str(e)}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
