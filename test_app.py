import unittest
import time
from unittest.mock import patch, MagicMock
from app import app, AQI_LEVEL_MAP as AQI_MAPPING

class TestAirSenseBackend(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Ensure Gemini is disabled in tests to test rule-based fallback
        import app as app_module
        app_module._gemini_available = False

    def test_health_check(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "Air Sense backend is running"})

    def test_validation_errors(self):
        # Missing lat/lon
        response = self.app.get("/live")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required parameters", response.json["error"])

        # Invalid lat/lon
        response = self.app.get("/live?lat=abc&lon=12.3")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid parameters", response.json["error"])

        # Missing lat/lon forecast
        response = self.app.get("/forecast")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required parameters", response.json["error"])

    @patch("app.requests.get")
    def test_live_endpoint_success(self, mock_get):
        # Mock OpenWeatherMap response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "coord": {"lat": 40.7128, "lon": -74.006},
            "list": [
                {
                    "main": {"aqi": 3},
                    "components": {
                        "pm2_5": 12.5,
                        "pm10": 24.1,
                        "no2": 15.3,
                        "o3": 65.2,
                        "so2": 1.2,
                        "co": 350.0
                    },
                    "dt": 1605182400
                }
            ]
        }
        mock_get.return_value = mock_response

        # Test live endpoint for COPD condition
        response = self.app.get("/live?lat=40.7128&lon=-74.0060&condition=copd")
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["aqi_level"], 3)
        self.assertEqual(data["display_aqi"], AQI_MAPPING[3]["display_aqi"])
        self.assertEqual(data["aqi_label"], "Moderate")
        self.assertEqual(data["aqi_color"], "orange")
        self.assertEqual(data["conditions_used"], ["copd"])
        self.assertEqual(data["ai_generated"], False)
        self.assertEqual(
            data["personalized_risk"],
            "Moderate risk — consider limiting prolonged outdoor activity (COPD)"
        )
        self.assertEqual(data["pollutants"]["pm2_5"], 12.5)

    @patch("app.requests.get")
    def test_forecast_endpoint_success(self, mock_get):
        # Mock OpenWeatherMap forecast response with 26 hours of data (to verify 24h filter)
        now = int(time.time())
        
        mock_list = []
        for i in range(26):
            # Create Hourly items with varying AQI values
            # Let's make index 5 to 7 have AQI 1 (Good), rest have AQI 3
            aqi_val = 1 if 5 <= i <= 7 else 3
            mock_list.append({
                "main": {"aqi": aqi_val},
                "components": {
                    "pm2_5": 10.0,
                    "pm10": 20.0,
                    "no2": 10.0,
                    "o3": 40.0,
                    "so2": 1.0,
                    "co": 300.0
                },
                "dt": now + i * 3600
            })
            
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "coord": {"lat": 40.7128, "lon": -74.006},
            "list": mock_list
        }
        mock_get.return_value = mock_response

        response = self.app.get("/forecast?lat=40.7128&lon=-74.0060")
        self.assertEqual(response.status_code, 200)
        data = response.json
        
        # Verify it filters correctly
        self.assertTrue(len(data["hourly"]) <= 24)
        
        # Verify best time window contains correct information
        self.assertEqual(data["best_window_aqi"], AQI_MAPPING[1]["display_aqi"])
        self.assertEqual(data["best_window_start"], now + 5 * 3600)

    @patch("app.requests.get")
    def test_external_api_error(self, mock_get):
        # Mock failure from OpenWeatherMap API
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized - invalid appid"
        mock_response.json.return_value = {"message": "Invalid API key"}
        mock_get.return_value = mock_response

        response = self.app.get("/live?lat=40.7128&lon=-74.0060")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json["error"], "Failed to fetch air quality data")

if __name__ == "__main__":
    unittest.main()
