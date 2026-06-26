# Air Sense - Flask Backend

A Flask backend service for the "Air Sense" air quality application. It integrates with the OpenWeatherMap Air Pollution API to provide live air quality details and forecasts, dynamic AQI mapping, and personalized risk wording for specific health conditions.

## Project Structure

* `app.py`: Main Flask application with routing, mapping logic, and validations.
* `test_app.py`: Unit test suite testing all endpoints, validations, mapping logic, and error handlers using mocks.
* `.env`: Environment variables configuration file (contains your `OWM_API_KEY`).
* `.gitignore`: Specifies files to be ignored by Git (including `.env` containing your API key).
* `requirements.txt`: Python package dependencies.
* `venv/`: Local Python virtual environment directory.

---

## Setup & Installation

### 1. Prerequisites
Ensure you have Python 3.13+ installed on your system.

### 2. Configure Environment Variables
A `.env` file has been created with a placeholder API key. For live data, modify this key with your actual OpenWeatherMap API key:
```ini
OWM_API_KEY=YOUR_ACTUAL_API_KEY
```

### 3. Run Unit Tests
To run the mock-based unit tests and ensure the application mapping logic behaves as expected:
```powershell
.\venv\Scripts\python.exe -m unittest test_app.py
```

### 4. Running the Development Server
To start the backend locally on `http://localhost:5000`:
```powershell
.\venv\Scripts\python.exe app.py
```

---

## API Documentation

### 1. Health Check
* **Endpoint**: `GET /`
* **Response**:
  ```json
  {
    "status": "running"
  }
  ```

### 2. Live Air Quality
* **Endpoint**: `GET /live`
* **Query Parameters**:
  * `lat` (required, float): Latitude (e.g. `40.7128`)
  * `lon` (required, float): Longitude (e.g. `-74.0060`)
  * `condition` (optional, string): One of `asthma`, `allergies`, `copd`, `none`. Default is `none`.
* **Example Request**:
  `GET http://localhost:5000/live?lat=40.7128&lon=-74.0060&condition=asthma`
* **Response**:
  ```json
  {
    "coord": {
      "lat": 40.7128,
      "lon": -74.006
    },
    "aqi": 3,
    "aqi_display": 130,
    "label": "Moderate",
    "color": "orange",
    "condition": "asthma",
    "personalized_risk": "Moderate risk. Keep your quick-relief inhaler handy; consider reducing outdoor activities.",
    "pollutants": {
      "co": 350.0,
      "no2": 15.3,
      "o3": 65.2,
      "pm10": 24.1,
      "pm2_5": 12.5,
      "so2": 1.2
    }
  }
  ```

### 3. 24-Hour Air Quality Forecast & Best Window
* **Endpoint**: `GET /forecast`
* **Query Parameters**:
  * `lat` (required, float): Latitude (e.g. `40.7128`)
  * `lon` (required, float): Longitude (e.g. `-74.0060`)
* **Example Request**:
  `GET http://localhost:5000/forecast?lat=40.7128&lon=-74.0060`
* **Response**:
  ```json
  {
    "coord": {
      "lat": 40.7128,
      "lon": -74.006
    },
    "forecast": [
      {
        "dt": 1605182400,
        "time_formatted": "2020-11-12 12:00:00 UTC",
        "aqi": 1,
        "aqi_display": 40,
        "label": "Good",
        "color": "green",
        "pollutants": { ... }
      },
      ...
    ],
    "best_time_window": {
      "aqi": 1,
      "label": "Good",
      "color": "green",
      "display_aqi": 40,
      "start_time": 1605182400,
      "end_time": 1605186000,
      "start_time_formatted": "2020-11-12 12:00:00 UTC",
      "end_time_formatted": "2020-11-12 13:00:00 UTC",
      "duration_hours": 1
    }
  }
  ```
