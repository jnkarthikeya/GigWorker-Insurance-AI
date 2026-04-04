"""
ShieldPay – Data Sources & Environmental Simulation Engine
Simulates real-world data APIs: Weather, Demand Index, AQI, Traffic.
"""

import math
import random
import logging
from datetime import datetime
import requests
from dotenv import load_dotenv
load_dotenv()
import os
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
from typing import Dict, Any, Optional

logger = logging.getLogger("shieldpay.env")

# ──────────────────────────────────────────────
# City Profiles
# ──────────────────────────────────────────────
CITY_PROFILES = {
    "Mumbai": {"rain_base": 8.0, "rain_peak_months": [6,7,8,9], "demand_base": 72, "aqi_base": 145, "traffic_base": 0.65},
    "Delhi": {"rain_base": 3.0, "rain_peak_months": [7,8], "demand_base": 80, "aqi_base": 220, "traffic_base": 0.75},
    "Bangalore": {"rain_base": 6.0, "rain_peak_months": [5,6,9,10], "demand_base": 85, "aqi_base": 95, "traffic_base": 0.80},
    "Chennai": {"rain_base": 5.0, "rain_peak_months": [10,11,12], "demand_base": 68, "aqi_base": 85, "traffic_base": 0.60},
    "Hyderabad": {"rain_base": 4.5, "rain_peak_months": [7,8,9], "demand_base": 75, "aqi_base": 110, "traffic_base": 0.58},
}
DEFAULT_CITY = "Mumbai"

# ──────────────────────────────────────────────
# Classifiers
# ──────────────────────────────────────────────
def classify_rain(r): return "severe" if r>30 else "heavy" if r>15 else "moderate" if r>7 else "light" if r>2 else "clear"
def classify_aqi(a): return "severe" if a>400 else "very_poor" if a>300 else "poor" if a>200 else "moderate" if a>100 else "satisfactory" if a>50 else "good"
def classify_traffic(c): return "gridlock" if c>0.85 else "heavy" if c>0.7 else "moderate" if c>0.5 else "light" if c>0.3 else "free_flow"
def classify_demand(i): return "high" if i>=80 else "normal" if i>=55 else "low" if i>=35 else "very_low"

# ──────────────────────────────────────────────
# REAL API FETCH
# ──────────────────────────────────────────────
def fetch_real_weather(city: str):
    city_map= {
        "bengaluru":"bangalore",
        "delhi ncr": "delhi",
        "bombay": "mumbai",
        "hyderabad": "hyderabad",
        "chennai": "chennai",
        "mumbai":"mumbai"
    }
    city = city_map.get(city.lower(),city)
    if not OPENWEATHER_API_KEY:
        logger.warning("No OpenWeather API key")
        return None
    try:
        city = city.title()  
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        res = requests.get(url, timeout=2)
        data = res.json()

        if res.status_code != 200:
            logger.warning(f"Weather API error {data}")
            return None

        rain = data.get("rain", {}).get("1h", 0) or 0
        sev = classify_rain(rain)

        return {
            "rain_mm": rain,
            "severity": sev,
            "income_impact_pct": {"clear":0,"light":10,"moderate":25,"heavy":45,"severe":65}[sev],
            "source": "real",
            "confidence": 0.9
        }
    except Exception as e:
        logger.warning(f"Weather fail {e}")
        return None


def fetch_real_aqi(city: str):
    if not OPENWEATHER_API_KEY:
        return None
    try:
        city = city.title()
        geo = requests.get(f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}", timeout=2).json()
        if not geo: return None
        lat, lon = geo[0]["lat"], geo[0]["lon"]

        data = requests.get(f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}", timeout=2).json()
        aqi = data["list"][0]["main"]["aqi"] * 50
        cat = classify_aqi(aqi)

        return {
            "aqi": aqi,
            "category": cat,
            "income_impact_pct": {"good":0,"satisfactory":0,"moderate":5,"poor":15,"very_poor":30,"severe":50}[cat],
            "source": "real",
            "confidence": 0.9
        }
    except Exception as e:
        logger.warning(f"AQI fail {e}")
        return None


# ──────────────────────────────────────────────
# SIMULATION (UNCHANGED LOGIC)
# ──────────────────────────────────────────────
def get_weather_data(city):
    rain = random.uniform(0, 20)
    sev = classify_rain(rain)
    return {"rain_mm": rain, "severity": sev, "income_impact_pct": {"clear":0,"light":10,"moderate":25,"heavy":45,"severe":65}[sev], "source":"simulated","confidence":0.6}

def get_demand_data(city):
    idx = random.uniform(20, 100)
    cat = classify_demand(idx)
    return {"index": idx, "category": cat, "income_impact_pct": {"high":-5,"normal":0,"low":20,"very_low":40}[cat], "source":"simulated","confidence":0.6}

def get_aqi_data(city):
    aqi = random.uniform(50, 300)
    cat = classify_aqi(aqi)
    return {"aqi": aqi, "category": cat, "income_impact_pct": {"good":0,"satisfactory":0,"moderate":5,"poor":15,"very_poor":30,"severe":50}[cat], "source":"simulated","confidence":0.6}

def get_traffic_data(city):
    c = random.uniform(0,1)
    cat = classify_traffic(c)
    return {"congestion_index": c, "category": cat, "income_impact_pct": {"free_flow":0,"light":5,"moderate":15,"heavy":30,"gridlock":55}[cat], "source":"simulated","confidence":0.6}


# ──────────────────────────────────────────────
# SAFE FETCH
# ──────────────────────────────────────────────
def safe_fetch(func, city):
    try:
        return func(city)
    except Exception as e:
        logger.warning(f"Safe fetch fail {e}")
        return None


# ──────────────────────────────────────────────
# MAIN ENGINE
# ──────────────────────────────────────────────
def get_full_environment(city: str = DEFAULT_CITY):

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor() as executor:
        fw = executor.submit(safe_fetch, fetch_real_weather, city)
        fa = executor.submit(safe_fetch, fetch_real_aqi, city)

        try: real_weather = fw.result(timeout=2)
        except: real_weather = None

        try: real_aqi = fa.result(timeout=2)
        except: real_aqi = None

    weather = real_weather if real_weather else get_weather_data(city)
    aqi = real_aqi if real_aqi else get_aqi_data(city)

    demand = get_demand_data(city)
    traffic = get_traffic_data(city)

    score = (
        (100-weather["income_impact_pct"])*0.35 +
        (100-demand["income_impact_pct"])*0.30 +
        (100-aqi["income_impact_pct"])*0.20 +
        (100-traffic["income_impact_pct"])*0.15
    )

    conf = (weather["confidence"]+aqi["confidence"]+demand["confidence"]+traffic["confidence"])/4

    logger.info({
        "city": city,
        "weather_source": weather.get("source"),
        "aqi_source": aqi.get("source")
    })
    print("🌍 ENV DEBUG:", {
    "weather": weather,
    "aqi": aqi
})

    return {
        "city": city,
        "weather": weather,
        "demand": demand,
        "aqi": aqi,
        "traffic": traffic,
        "composite_env_score": round(score*conf,2),
        "confidence": round(conf,2),
        "timestamp": datetime.utcnow().isoformat()
    }
def simulate_trigger_environment(trigger_type: str, city: str = DEFAULT_CITY):
    """
    Adapter layer for trigger engine compatibility
    Uses full environment engine internally
    """

    env = get_full_environment(city)

    if trigger_type == "rainfall":
        return {
            "value": env["weather"]["rain_mm"],
            "threshold": 15,
            "category": env["weather"]["severity"]
        }

    elif trigger_type == "aqi":
        return {
            "value": env["aqi"]["aqi"],
            "threshold": 200,
            "category": env["aqi"]["category"]
        }

    elif trigger_type == "demand":
        return {
            "value": env["demand"]["index"],
            "threshold": 50,
            "category": env["demand"]["category"]
        }

    elif trigger_type == "traffic":
        return {
            "value": env["traffic"]["congestion_index"],
            "threshold": 0.7,
            "category": env["traffic"]["category"]
        }

    else:
        return {
            "value": env["composite_env_score"],
            "threshold": 50,
            "category": "composite"
        }