"""
main.py — FarmSense AI Backend
FastAPI application exposing:
  POST /predict        — Crop recommendation with ML + market scoring
  POST /upload-report  — Soil report OCR extraction (PDF / JPG / PNG)
  GET  /weather        — Live weather from Open-Meteo for a given city
  GET  /market-prices  — Static market price reference data
  GET  /health         — Health check

Run with: uvicorn main:app --reload --port 8001
"""

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import csv
import os
import requests
import time
from pathlib import Path

from model import load_or_train, predict_top_n, get_model_accuracy, generate_reason
from market_data import get_market_score, MARKET_SCORES, DEMAND_SCORES

INDIA_COUNTRY_CODE = "IN"


def _load_local_env() -> None:
    """Load backend/.env in local development without adding another dependency."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()

DATA_GOV_API_URL = "https://api.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi"
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY") or os.getenv("AGMARKNET_API_KEY")
MANDI_CACHE_TTL_SECONDS = int(os.getenv("MANDI_CACHE_TTL_SECONDS", "21600"))
MANDI_API_TIMEOUT_SECONDS = float(os.getenv("MANDI_API_TIMEOUT_SECONDS", "6"))
MET_NORWAY_API_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
MET_NORWAY_USER_AGENT = os.getenv(
    "MET_NORWAY_USER_AGENT",
    "FarmSense-AI/2.0 https://github.com/rSlashGIT/farmsense",
)
BASE_DIR = Path(__file__).parent
MANDI_ARCHIVE_PATH = BASE_DIR / "data" / "mandi_price_history_2016_2026.csv"
MANDI_ARCHIVE_SUMMARY_PATH = BASE_DIR / "data" / "mandi_price_history_summary.json"

_mandi_price_cache: dict[tuple[str, str, str, str], tuple[float, dict | None]] = {}
_data_gov_disabled_until = 0.0

COMMODITY_ALIASES: dict[str, list[str]] = {
    "rice": ["Paddy(Dhan)(Common)", "Rice", "Paddy"],
    "chickpea": ["Bengal Gram(Gram)(Whole)", "Gram", "Chana"],
    "kidneybeans": ["Rajgir", "Beans"],
    "pigeonpeas": ["Arhar (Tur/Red Gram)(Whole)", "Red Gram", "Arhar"],
    "mothbeans": ["Moth Beans", "Moth"],
    "mungbean": ["Green Gram (Moong)(Whole)", "Green Gram", "Moong"],
    "blackgram": ["Black Gram (Urd Beans)(Whole)", "Black Gram", "Urd"],
    "lentil": ["Lentil (Masur)(Whole)", "Masur"],
    "watermelon": ["Water Melon", "Watermelon"],
    "muskmelon": ["Karbuja(Musk Melon)", "Musk Melon", "Muskmelon"],
    "cotton": ["Cotton", "Cotton Seed"],
    "chilli": ["Dry Chillies", "Chilli", "Green Chilli"],
    "capsicum": ["Chilly Capsicum", "Capsicum"],
    "sweet_potato": ["Sweet Potato"],
    "sugarcane": ["Sugarcane"],
    "soybean": ["Soyabean", "Soybean"],
    "groundnut": ["Groundnut", "Ground Nut Seed"],
    "sesame": ["Sesamum(Sesame,Gingelly,Til)", "Sesame"],
    "cumin": ["Cummin Seed(Jeera)", "Cumin"],
    "pepper": ["Black pepper", "Pepper"],
    "ginger": ["Ginger(Green)", "Ginger"],
    "coriander": ["Corriander seed", "Coriander"],
}

INDIAN_LOCATION_ALIASES = {
    "bangalore": "Bengaluru",
    "banglore": "Bengaluru",
    "mysore": "Mysuru",
    "mangalore": "Mangaluru",
    "bellary": "Ballari",
    "bellari": "Ballari",
    "bellaria": "Ballari",
    "baroda": "Vadodara",
    "calcutta": "Kolkata",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "gurgaon": "Gurugram",
}

POPULAR_INDIAN_LOCATIONS = [
    {"name": "Bengaluru", "admin1": "Karnataka", "admin2": "Bengaluru Urban", "latitude": 12.97194, "longitude": 77.59369, "population": 8495492, "priority": 0, "aliases": ["bangalore", "banglore", "bengaluru"]},
    {"name": "Bengaluru Rural", "admin1": "Karnataka", "admin2": "Bengaluru Rural", "latitude": 13.22567, "longitude": 77.57501, "population": 990923, "priority": 5, "aliases": ["bangalore rural", "bengaluru rural"]},
    {"name": "Bengaluru Urban", "admin1": "Karnataka", "admin2": "Bengaluru Urban", "latitude": 12.97056, "longitude": 77.59456, "population": 9621551, "priority": 5, "aliases": ["bangalore urban", "bengaluru urban"]},
    {"name": "Bangarapet", "admin1": "Karnataka", "admin2": "Kolar", "latitude": 12.99116, "longitude": 78.17804, "population": 43500, "priority": 10, "aliases": ["bangarapet"]},
    {"name": "Ballari", "admin1": "Karnataka", "admin2": "Ballari", "latitude": 15.14205, "longitude": 76.92398, "population": 410445, "aliases": ["bellary", "bellari", "bellaria", "ballari"]},
    {"name": "Belagavi", "admin1": "Karnataka", "admin2": "Belagavi", "latitude": 15.85212, "longitude": 74.50447, "population": 488157, "aliases": ["belgaum", "belagavi"]},
    {"name": "Belur", "admin1": "Karnataka", "admin2": "Hassan", "latitude": 13.16231, "longitude": 75.86754, "population": 20319, "aliases": ["belur"]},
    {"name": "Bellampalli", "admin1": "Telangana", "admin2": "Mancherial", "latitude": 19.05577, "longitude": 79.49300, "population": 55841, "aliases": ["bellampalli"]},
    {"name": "Beldanga", "admin1": "West Bengal", "admin2": "Murshidabad", "latitude": 23.93428, "longitude": 88.26018, "population": 29634, "aliases": ["beldanga"]},
    {"name": "Mumbai", "admin1": "Maharashtra", "admin2": "Mumbai", "latitude": 19.07283, "longitude": 72.88261, "population": 12691836, "aliases": ["bombay", "mumbai"]},
    {"name": "Delhi", "admin1": "National Capital Territory of Delhi", "admin2": "Delhi", "latitude": 28.65195, "longitude": 77.23149, "population": 10927986, "aliases": ["delhi", "new delhi"]},
    {"name": "Pune", "admin1": "Maharashtra", "admin2": "Pune", "latitude": 18.51957, "longitude": 73.85535, "population": 3124458, "aliases": ["pune"]},
    {"name": "Hyderabad", "admin1": "Telangana", "admin2": "Hyderabad", "latitude": 17.38405, "longitude": 78.45636, "population": 6809970, "aliases": ["hyderabad"]},
    {"name": "Chennai", "admin1": "Tamil Nadu", "admin2": "Chennai", "latitude": 13.08784, "longitude": 80.27847, "population": 4328063, "aliases": ["madras", "chennai"]},
    {"name": "Kolkata", "admin1": "West Bengal", "admin2": "Kolkata", "latitude": 22.56263, "longitude": 88.36304, "population": 4631392, "aliases": ["calcutta", "kolkata"]},
    {"name": "Ahmedabad", "admin1": "Gujarat", "admin2": "Ahmedabad", "latitude": 23.02579, "longitude": 72.58727, "population": 6357693, "aliases": ["ahmedabad"]},
    {"name": "Jaipur", "admin1": "Rajasthan", "admin2": "Jaipur", "latitude": 26.91962, "longitude": 75.78781, "population": 2711758, "aliases": ["jaipur"]},
    {"name": "Lucknow", "admin1": "Uttar Pradesh", "admin2": "Lucknow", "latitude": 26.83928, "longitude": 80.92313, "population": 2472011, "aliases": ["lucknow"]},
    {"name": "Kanpur", "admin1": "Uttar Pradesh", "admin2": "Kanpur Nagar", "latitude": 26.46523, "longitude": 80.34975, "population": 2823249, "aliases": ["kanpur"]},
    {"name": "Nagpur", "admin1": "Maharashtra", "admin2": "Nagpur", "latitude": 21.14631, "longitude": 79.08491, "population": 2228018, "aliases": ["nagpur"]},
    {"name": "Indore", "admin1": "Madhya Pradesh", "admin2": "Indore", "latitude": 22.71792, "longitude": 75.83330, "population": 1837041, "aliases": ["indore"]},
    {"name": "Bhopal", "admin1": "Madhya Pradesh", "admin2": "Bhopal", "latitude": 23.25469, "longitude": 77.40289, "population": 1599914, "aliases": ["bhopal"]},
    {"name": "Patna", "admin1": "Bihar", "admin2": "Patna", "latitude": 25.59408, "longitude": 85.13563, "population": 1599920, "aliases": ["patna"]},
    {"name": "Ludhiana", "admin1": "Punjab", "admin2": "Ludhiana", "latitude": 30.91204, "longitude": 75.85379, "population": 1545368, "aliases": ["ludhiana"]},
    {"name": "Nashik", "admin1": "Maharashtra", "admin2": "Nashik", "latitude": 19.99745, "longitude": 73.78980, "population": 1289497, "aliases": ["nashik", "nasik"]},
    {"name": "Surat", "admin1": "Gujarat", "admin2": "Surat", "latitude": 21.19594, "longitude": 72.83023, "population": 4467797, "aliases": ["surat"]},
    {"name": "Vadodara", "admin1": "Gujarat", "admin2": "Vadodara", "latitude": 22.29941, "longitude": 73.20812, "population": 1409476, "aliases": ["vadodara", "baroda"]},
    {"name": "Chandigarh", "admin1": "Chandigarh", "admin2": "Chandigarh", "latitude": 30.73629, "longitude": 76.78840, "population": 960787, "aliases": ["chandigarh"]},
    {"name": "Mysuru", "admin1": "Karnataka", "admin2": "Mysuru", "latitude": 12.29791, "longitude": 76.63925, "population": 868313, "aliases": ["mysore", "mysuru"]},
    {"name": "Mangaluru", "admin1": "Karnataka", "admin2": "Dakshina Kannada", "latitude": 12.91723, "longitude": 74.85603, "population": 417387, "aliases": ["mangalore", "mangaluru"]},
    {"name": "Coimbatore", "admin1": "Tamil Nadu", "admin2": "Coimbatore", "latitude": 11.00555, "longitude": 76.96612, "population": 959823, "aliases": ["coimbatore"]},
    {"name": "Kochi", "admin1": "Kerala", "admin2": "Ernakulam", "latitude": 9.93988, "longitude": 76.26022, "population": 604696, "aliases": ["kochi", "cochin"]},
    {"name": "Guwahati", "admin1": "Assam", "admin2": "Kamrup Metropolitan", "latitude": 26.18440, "longitude": 91.74580, "population": 899094, "aliases": ["guwahati"]},
    {"name": "Bhubaneswar", "admin1": "Odisha", "admin2": "Khordha", "latitude": 20.27241, "longitude": 85.83385, "population": 762243, "aliases": ["bhubaneswar"]},
    {"name": "Ranchi", "admin1": "Jharkhand", "admin2": "Ranchi", "latitude": 23.34316, "longitude": 85.30940, "population": 846454, "aliases": ["ranchi"]},
    {"name": "Banda", "admin1": "Uttar Pradesh", "admin2": "Banda", "latitude": 25.47534, "longitude": 80.33580, "population": 160473, "aliases": ["banda"]},
    {"name": "Bankura", "admin1": "West Bengal", "admin2": "Bankura", "latitude": 23.23241, "longitude": 87.07160, "population": 137386, "aliases": ["bankura"]},
    {"name": "Banswara", "admin1": "Rajasthan", "admin2": "Banswara", "latitude": 23.54614, "longitude": 74.43490, "population": 99969, "aliases": ["banswara"]},
    {"name": "Banaskantha", "admin1": "Gujarat", "admin2": "Banaskantha", "latitude": 24.17243, "longitude": 72.43458, "population": 3120506, "aliases": ["banaskantha", "palanpur"]},
]

# ─── App Initialization ───────────────────────────────────────────────────────
app = FastAPI(
    title="FarmSense AI API",
    description="Intelligent crop recommendation system powered by ML + market data",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Load / Train the ML model at startup ─────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    load_or_train()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    nitrogen: float = Field(..., ge=0, le=140, description="Soil Nitrogen (mg/kg)")
    phosphorus: float = Field(..., ge=0, le=145, description="Soil Phosphorus (mg/kg)")
    potassium: float = Field(..., ge=0, le=205, description="Soil Potassium (mg/kg)")
    temperature: float = Field(..., ge=0, le=55, description="Temperature (°C)")
    humidity: float = Field(..., ge=0, le=100, description="Humidity (%)")
    ph: float = Field(..., ge=3.0, le=10.0, description="Soil pH")
    rainfall: float = Field(..., ge=0, le=300, description="Annual Rainfall (cm)")
    organic_carbon: float = Field(0.5, ge=0.0, le=5.0, description="Organic Carbon (%)")
    electrical_conductivity: float = Field(0.3, ge=0.0, le=8.0, description="Electrical Conductivity (dS/m)")
    season: str = Field("Kharif", description="Farming season")
    irrigation: str = Field("Available", description="Irrigation availability")
    previous_crop: str = Field("None", description="Previous crop grown")
    location: str = Field("", description="City/district name")
    land_area: float = Field(1.0, ge=0.1, le=10000, description="Land area in acres")
    budget_per_acre: float = Field(20000, ge=0, description="Budget per acre in INR")


class GovtScheme(BaseModel):
    name: str
    body: str
    benefit: str


class CropRecommendation(BaseModel):
    rank: int
    crop: str
    fit_score: float
    market_score: float
    profit_index: float
    overall_score: float
    season: str
    water_need: str
    reason: str
    tags: list[str]
    govt_schemes: list[GovtScheme]
    ai_insights: str
    cost_per_acre: float
    yield_per_acre: float
    price_per_quintal: float
    cycle_days: int
    potential_revenue: float
    potential_profit: float
    roi_percent: float
    market_source: str = "Static estimate"
    market_location: str = ""
    market_name: str = ""
    market_price_date: str = ""
    market_commodity: str = ""
    live_price_used: bool = False


class PredictResponse(BaseModel):
    recommendations: list[CropRecommendation]
    model_accuracy: float
    parameters_analyzed: int
    total_crops_evaluated: int
    land_area: float
    budget_per_acre: float


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _compute_revenue(mkt: dict, land_area: float) -> tuple[float, float, float]:
    """Calculate potential revenue, profit, ROI for given land area."""
    cost_total = mkt["cost_per_acre"] * land_area
    gross_revenue = mkt["yield_per_acre"] * mkt["price_per_quintal"] * land_area
    net_profit = gross_revenue - cost_total
    roi = round((net_profit / cost_total) * 100, 1) if cost_total > 0 else 0.0
    return round(gross_revenue, 0), round(net_profit, 0), roi


def _to_float(value) -> float | None:
    """Parse numeric API values that may arrive as strings with commas."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _date_rank(value: str | None) -> float:
    if not value:
        return 0.0
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return time.mktime(time.strptime(text, fmt))
        except ValueError:
            continue
    return 0.0


def _commodity_candidates(crop_name: str) -> list[str]:
    crop_key = crop_name.lower().replace(" ", "_")
    aliases = COMMODITY_ALIASES.get(crop_key, [])
    title_name = crop_key.replace("_", " ").title()
    candidates = [*aliases, title_name, crop_name]
    unique = []
    for item in candidates:
        if item and item not in unique:
            unique.append(item)
    return unique


def _resolve_mandi_location(location: str) -> dict:
    """
    Convert the user's city/district text into state/district filters for
    data.gov.in. If the lookup fails, live prices can still be fetched by
    commodity alone.
    """
    if not location.strip():
        return {}

    try:
        matches = _search_indian_locations(location, count=1)
    except requests.RequestException:
        return {}

    if not matches:
        return {}

    item = matches[0]
    return {
        "state": item.get("admin1") or "",
        "district": item.get("admin2") or item.get("name") or "",
        "display": _location_display(item),
    }


def _select_mandi_price(records: list[dict]) -> dict | None:
    valid = []
    for record in records:
        price = _to_float(record.get("modal_price"))
        if price is None or price <= 0:
            continue
        valid.append((record, price, _date_rank(record.get("arrival_date"))))

    if not valid:
        return None

    latest_date = max(date_value for _, _, date_value in valid)
    latest_records = [item for item in valid if item[2] == latest_date] if latest_date else valid[:10]
    prices = sorted(price for _, price, _ in latest_records)
    median_price = prices[len(prices) // 2]
    representative = min(latest_records, key=lambda item: abs(item[1] - median_price))[0]

    return {
        "price_per_quintal": round(median_price, 2),
        "commodity": representative.get("commodity", ""),
        "market": representative.get("market", ""),
        "district": representative.get("district", ""),
        "state": representative.get("state", ""),
        "arrival_date": representative.get("arrival_date", ""),
        "record_count": len(latest_records),
        "source": "data.gov.in AGMARKNET live mandi feed",
    }


def _fetch_live_mandi_price(
    crop_name: str,
    location: dict | None = None,
    market: str = "",
) -> dict | None:
    """Fetch the latest modal mandi price for a crop, with short in-memory caching."""
    global _data_gov_disabled_until

    if not DATA_GOV_API_KEY or time.time() < _data_gov_disabled_until:
        return None

    location = location or {}
    state = (location.get("state") or "").strip()
    district = (location.get("district") or "").strip()
    market = market.strip()
    cache_key = (crop_name.lower(), state.lower(), district.lower(), market.lower())
    cached = _mandi_price_cache.get(cache_key)
    if cached and time.time() - cached[0] < MANDI_CACHE_TTL_SECONDS:
        return cached[1]

    scopes = [(state, district)]
    if district and not market:
        scopes.append((state, ""))
    if state and not market:
        scopes.append(("", ""))

    for scope_state, scope_district in scopes:
        for commodity in _commodity_candidates(crop_name):
            params = {
                "api-key": DATA_GOV_API_KEY,
                "format": "json",
                "limit": 100,
                "filters[commodity]": commodity,
            }
            if scope_state:
                params["filters[state]"] = scope_state
            if scope_district:
                params["filters[district]"] = scope_district
            if market:
                params["filters[market]"] = market

            try:
                resp = requests.get(DATA_GOV_API_URL, params=params, timeout=MANDI_API_TIMEOUT_SECONDS)
                if resp.status_code in {401, 403}:
                    _data_gov_disabled_until = time.time() + 300
                    _mandi_price_cache[cache_key] = (time.time(), None)
                    return None
                resp.raise_for_status()
                selected = _select_mandi_price(resp.json().get("records") or [])
            except (requests.RequestException, ValueError):
                selected = None

            if selected:
                selected["requested_commodity"] = commodity
                _mandi_price_cache[cache_key] = (time.time(), selected)
                return selected

    _mandi_price_cache[cache_key] = (time.time(), None)
    return None


def _market_score_with_live_price(crop_name: str, mkt: dict, live_price: dict | None) -> dict:
    enriched = dict(mkt)
    enriched.update({
        "market_source": "Static estimate",
        "market_location": "",
        "market_name": "",
        "market_price_date": "",
        "market_commodity": "",
        "live_price_used": False,
    })

    if not live_price:
        return enriched

    crop_key = crop_name.lower()
    base = MARKET_SCORES.get(crop_key, {})
    static_price = float(base.get("price_per_quintal") or mkt["price_per_quintal"] or 1)
    live_modal_price = float(live_price["price_per_quintal"])
    base_price_score = float(base.get("price_score", 50))
    export_score = float(base.get("export", 50))
    demand_score = DEMAND_SCORES.get(mkt["demand"], 65)

    price_ratio = live_modal_price / static_price if static_price > 0 else 1.0
    live_price_score = max(35, min(100, round(base_price_score * price_ratio)))
    market_score = round(0.40 * live_price_score + 0.40 * demand_score + 0.20 * export_score)

    location_parts = [
        live_price.get("market"),
        live_price.get("district"),
        live_price.get("state"),
    ]

    enriched.update({
        "price_per_quintal": live_modal_price,
        "market_score": market_score,
        "market_source": live_price.get("source", "data.gov.in AGMARKNET live mandi feed"),
        "market_location": ", ".join([part for part in location_parts if part]),
        "market_name": live_price.get("market", ""),
        "market_price_date": live_price.get("arrival_date", ""),
        "market_commodity": live_price.get("commodity") or live_price.get("requested_commodity", ""),
        "live_price_used": True,
    })
    return enriched


def _load_mandi_archive_rows(crop: str = "", limit: int = 100) -> list[dict]:
    if not MANDI_ARCHIVE_PATH.exists():
        return []

    crop_key = crop.strip().lower().replace(" ", "_")
    rows = []
    with MANDI_ARCHIVE_PATH.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if crop_key and row.get("crop", "").lower() != crop_key:
                continue
            rows.append(row)
            if len(rows) >= limit:
                break
    return rows


def _canonical_indian_location(query: str) -> str:
    normalized = " ".join(query.strip().lower().split())
    return INDIAN_LOCATION_ALIASES.get(normalized, query.strip())


def _location_display(result: dict) -> str:
    parts = [
        result.get("name"),
        result.get("admin2"),
        result.get("admin1"),
        result.get("country"),
    ]
    seen = set()
    clean_parts = []
    for part in parts:
        if not part:
            continue
        key = str(part).strip().lower()
        if key and key not in seen:
            seen.add(key)
            clean_parts.append(str(part).strip())
    return ", ".join(clean_parts)


def _local_indian_locations(query: str) -> list[dict]:
    normalized = " ".join(query.strip().lower().split())
    if len(normalized) < 2:
        return []

    matches = []
    for item in POPULAR_INDIAN_LOCATIONS:
        names = [item["name"].lower(), *[alias.lower() for alias in item.get("aliases", [])]]
        starts = any(name.startswith(normalized) for name in names)
        contains = any(normalized in name for name in names)
        if starts or contains:
            result = {
                **item,
                "country": "India",
                "country_code": INDIA_COUNTRY_CODE,
                "id": f"local-{item['name'].lower()}",
            }
            score = 0 if starts else 1
            matches.append((score, int(item.get("priority", 50)), -int(item.get("population") or 0), result))

    return [item for _, _, _, item in sorted(matches, key=lambda row: (row[0], row[1], row[2], row[3]["name"]))[:4]]


def _search_indian_locations(query: str, count: int = 4) -> list[dict]:
    """
    Search Open-Meteo geocoding but keep only Indian locations.
    Open-Meteo uses current official names for several Indian cities, so a
    small alias map handles common older spellings such as Bangalore/Bellary.
    """
    query = query.strip()
    if len(query) < 2:
        return []

    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    search_terms = [query]
    canonical = _canonical_indian_location(query)
    if canonical.lower() != query.lower():
        search_terms.insert(0, canonical)

    matches = []
    seen_keys = set()

    for result in _local_indian_locations(query):
        key = (result.get("name", "").lower(), result.get("admin1", "").lower())
        seen_keys.add(key)
        matches.append(result)

    for term in search_terms:
        params = {
            "name": term,
            "count": max(count * 3, 10),
            "language": "en",
            "format": "json",
            "countryCode": INDIA_COUNTRY_CODE,
        }
        resp = requests.get(geo_url, params=params, timeout=10)
        resp.raise_for_status()

        for result in resp.json().get("results") or []:
            if result.get("country_code") != INDIA_COUNTRY_CODE:
                continue
            key = (result.get("name", "").lower(), result.get("admin1", "").lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            matches.append(result)

    preferred = canonical.lower()
    matches.sort(
        key=lambda item: (
            0 if str(item.get("id", "")).startswith("local-") else 1,
            0 if item.get("name", "").lower() == preferred else 1,
            int(item.get("priority", 100)),
            -int(item.get("population") or 0),
            item.get("name", ""),
        )
    )
    return matches[:count]


# ─── /predict endpoint ────────────────────────────────────────────────────────

@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """
    Accepts soil + climate parameters and returns top 5 crop recommendations.
    Score threshold: all three metrics (fit, market, profit) must be >= 50.
    If no crop meets threshold, the best available crops are returned.

    Ranking formula:
        overall_score = (fit_score × 0.45) + (market_score × 0.35) + (profit_index × 0.20)
    """
    try:
        top_candidates = predict_top_n(
            nitrogen=req.nitrogen,
            phosphorus=req.phosphorus,
            potassium=req.potassium,
            temperature=req.temperature,
            humidity=req.humidity,
            ph=req.ph,
            rainfall=req.rainfall,
            top_n=10,  # get 10 internally, filter to top 5 meeting threshold
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    qualified = []
    fallback = []
    mandi_location = _resolve_mandi_location(req.location) if req.location.strip() else {}

    for candidate in top_candidates:
        crop_name = candidate["crop"]
        fit_score = candidate["fit_score"]

        base_mkt = get_market_score(crop_name)
        live_price = _fetch_live_mandi_price(crop_name, mandi_location)
        mkt = _market_score_with_live_price(crop_name, base_mkt, live_price)
        market_score = float(mkt["market_score"])

        # profit_index: blend of fit and market (ensure it's also normalized high)
        profit_index = round((fit_score * 0.40) + (market_score * 0.60), 1)
        profit_index = min(profit_index, 100.0)

        overall_score = round(
            (fit_score * 0.45) + (market_score * 0.35) + (profit_index * 0.20), 1
        )

        reason = generate_reason(
            crop=crop_name,
            nitrogen=req.nitrogen,
            phosphorus=req.phosphorus,
            potassium=req.potassium,
            temperature=req.temperature,
            humidity=req.humidity,
            ph=req.ph,
            rainfall=req.rainfall,
            confidence=candidate["confidence"],
        )

        gross_rev, net_profit, roi = _compute_revenue(mkt, req.land_area)

        schemes = [
            GovtScheme(name=s["name"], body=s["body"], benefit=s["benefit"])
            for s in mkt.get("govt_schemes", [])
        ]

        rec = CropRecommendation(
            rank=0,
            crop=crop_name.replace("_", " ").title(),
            fit_score=fit_score,
            market_score=market_score,
            profit_index=profit_index,
            overall_score=overall_score,
            season=mkt["season"],
            water_need=mkt["water_need"],
            reason=reason,
            tags=mkt["tags"],
            govt_schemes=schemes,
            ai_insights=mkt.get("ai_insights", ""),
            cost_per_acre=mkt["cost_per_acre"],
            yield_per_acre=mkt["yield_per_acre"],
            price_per_quintal=mkt["price_per_quintal"],
            cycle_days=mkt["cycle_days"],
            potential_revenue=gross_rev,
            potential_profit=net_profit,
            roi_percent=roi,
            market_source=mkt["market_source"],
            market_location=mkt["market_location"],
            market_name=mkt["market_name"],
            market_price_date=mkt["market_price_date"],
            market_commodity=mkt["market_commodity"],
            live_price_used=mkt["live_price_used"],
        )

        # Score threshold: all 3 metrics >= 50
        if fit_score >= 50 and market_score >= 50 and profit_index >= 50:
            qualified.append(rec)
        else:
            fallback.append(rec)

    # Sort both lists by overall_score
    qualified.sort(key=lambda x: x.overall_score, reverse=True)
    fallback.sort(key=lambda x: x.overall_score, reverse=True)

    # If we have enough qualified crops, use them; otherwise fill from fallback
    if len(qualified) >= 5:
        final = qualified[:5]
    elif len(qualified) > 0:
        needed = 5 - len(qualified)
        final = qualified + fallback[:needed]
    else:
        # All crops are fallback — return best available
        final = fallback[:5]

    for i, rec in enumerate(final):
        rec.rank = i + 1

    return PredictResponse(
        recommendations=final,
        model_accuracy=round(get_model_accuracy() * 100, 2),
        parameters_analyzed=11,
        total_crops_evaluated=len(MARKET_SCORES),
        land_area=req.land_area,
        budget_per_acre=req.budget_per_acre,
    )


# ─── /upload-report endpoint ──────────────────────────────────────────────────

@app.post("/upload-report")
async def upload_report(file: UploadFile = File(...)):
    """
    Accepts a soil lab report (PDF, JPG, PNG) and extracts soil parameter values
    using OCR / text parsing. Returns extracted values for auto-filling the form.
    """
    allowed_types = {
        "application/pdf",
        "image/jpeg", "image/jpg", "image/png", "image/webp",
    }
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Upload PDF, JPG, or PNG.",
        )

    file_bytes = await file.read()
    max_size = 15 * 1024 * 1024  # 15 MB
    if len(file_bytes) > max_size:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 15 MB.")

    try:
        from ocr_parser import parse_soil_report
        result = parse_soil_report(file_bytes, content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report parsing failed: {str(e)}")

    return result


# ─── /market-prices endpoint ──────────────────────────────────────────────────

@app.get("/market-prices")
async def get_market_prices(
    crop: str = Query("", description="Optional crop/commodity to fetch from live mandi feed"),
    state: str = Query("", description="Optional mandi state filter"),
    district: str = Query("", description="Optional mandi district filter"),
    market: str = Query("", description="Optional mandi market filter"),
):
    """Returns market price reference data, with optional live data.gov.in lookup."""
    if crop:
        crop_key = crop.strip().lower().replace(" ", "_")
        base_mkt = get_market_score(crop_key)
        live_price = _fetch_live_mandi_price(
            crop_key,
            {"state": state.strip(), "district": district.strip()},
            market=market,
        )
        mkt = _market_score_with_live_price(crop_key, base_mkt, live_price)
        return {
            "crop": crop_key,
            "market_score": mkt["market_score"],
            "price_per_quintal": mkt["price_per_quintal"],
            "season": mkt["season"],
            "demand": mkt["demand"],
            "source": mkt["market_source"],
            "market_location": mkt["market_location"],
            "market_price_date": mkt["market_price_date"],
            "market_commodity": mkt["market_commodity"],
            "live_price_used": mkt["live_price_used"],
        }

    prices = {}
    for crop, data in MARKET_SCORES.items():
        demand_score = DEMAND_SCORES[data["demand"]]
        composite = round(0.40 * data["price_score"] + 0.40 * demand_score + 0.20 * data["export"])
        prices[crop] = {
            "market_score": composite,
            "price_per_quintal": data["price_per_quintal"],
            "season": data["season"],
            "demand": data["demand"],
        }
    source = "Static Agmarknet + APEDA estimates 2024-25"
    if DATA_GOV_API_KEY:
        source += "; live lookup available with crop/state/district filters"
    return {"crops": prices, "source": source}


@app.get("/market-history")
async def get_market_history(
    crop: str = Query("", description="Optional crop filter, e.g. tomato"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum rows to return"),
):
    """Returns rows from the local 10-year mandi price archive."""
    rows = _load_mandi_archive_rows(crop=crop, limit=limit)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Mandi price archive not found or no rows match the requested crop.",
        )

    summary = {}
    if MANDI_ARCHIVE_SUMMARY_PATH.exists():
        try:
            import json
            summary = json.loads(MANDI_ARCHIVE_SUMMARY_PATH.read_text(encoding="utf-8"))
        except ValueError:
            summary = {}

    return {
        "summary": summary,
        "count": len(rows),
        "rows": rows,
    }


@app.get("/locations")
async def get_location_suggestions(query: str = Query(..., min_length=2, description="Indian city or district search text")):
    """Returns up to 4 Indian location suggestions for weather auto-fill."""
    try:
        matches = _search_indian_locations(query, count=4)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Location suggestion request failed: {e}")

    return {
        "suggestions": [
            {
                "name": item.get("name", ""),
                "display_name": _location_display(item),
                "admin1": item.get("admin1", ""),
                "admin2": item.get("admin2", ""),
                "country": item.get("country", "India"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
            }
            for item in matches
        ]
    }


def _fetch_met_norway_weather(lat: float, lon: float) -> tuple[float, float, float]:
    """Fallback weather source for hosts rate-limited by Open-Meteo."""
    response = requests.get(
        MET_NORWAY_API_URL,
        params={"lat": round(lat, 4), "lon": round(lon, 4)},
        headers={"User-Agent": MET_NORWAY_USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    timeseries = response.json().get("properties", {}).get("timeseries", [])
    if not timeseries:
        raise requests.RequestException("MET Norway returned no forecast timeseries")

    current = timeseries[0].get("data", {}).get("instant", {}).get("details", {})
    temperature = float(current.get("air_temperature", 25.0))
    humidity = float(current.get("relative_humidity", 60.0))

    hourly_precip = []
    for point in timeseries:
        value = (
            point.get("data", {})
            .get("next_1_hours", {})
            .get("details", {})
            .get("precipitation_amount")
        )
        if value is not None:
            hourly_precip.append(float(value))

    if hourly_precip:
        avg_hourly_mm = sum(hourly_precip) / len(hourly_precip)
        annual_rainfall_est = round(avg_hourly_mm * 24 * 365 / 10, 1)
    else:
        annual_rainfall_est = 80.0

    annual_rainfall_est = max(20.0, min(300.0, annual_rainfall_est))
    return temperature, humidity, annual_rainfall_est


# ─── /weather endpoint ────────────────────────────────────────────────────────

@app.get("/weather")
async def get_weather(location: str = Query(..., description="City or district name")):
    """
    Fetches real-time weather from Open-Meteo with a MET Norway fallback.
    Returns values ready to auto-fill the frontend climate inputs.
    """
    try:
        results = _search_indian_locations(location, count=1)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Geocoding request failed: {e}")

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"Indian location '{location}' not found. Try a nearby Indian city or district.",
        )

    lat = results[0]["latitude"]
    lon = results[0]["longitude"]
    resolved_location = _location_display(results[0])

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,precipitation",
        "daily": "precipitation_sum",
        "timezone": "auto",
        "forecast_days": 7,
    }

    source = "Open-Meteo (open-meteo.com)"
    try:
        w_resp = requests.get(weather_url, params=weather_params, timeout=10)
        w_resp.raise_for_status()
        w_data = w_resp.json()

        current = w_data.get("current", {})
        daily = w_data.get("daily", {})
        temperature = current.get("temperature_2m", 25.0)
        humidity = current.get("relative_humidity_2m", 60.0)

        daily_precip = daily.get("precipitation_sum", [])
        if daily_precip:
            weekly_avg = sum(daily_precip) / len(daily_precip) * 7
            annual_rainfall_est = round(weekly_avg * 52 / 10, 1)
        else:
            annual_rainfall_est = 80.0
        annual_rainfall_est = max(20.0, min(300.0, annual_rainfall_est))
    except (requests.RequestException, ValueError, TypeError) as open_meteo_error:
        try:
            temperature, humidity, annual_rainfall_est = _fetch_met_norway_weather(lat, lon)
            source = "MET Norway fallback (api.met.no)"
        except (requests.RequestException, ValueError, TypeError) as fallback_error:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Weather providers unavailable. Open-Meteo: {open_meteo_error}; "
                    f"MET Norway: {fallback_error}"
                ),
            )

    return {
        "location": resolved_location,
        "latitude": lat,
        "longitude": lon,
        "temperature": round(temperature, 1),
        "humidity": round(humidity, 1),
        "rainfall": annual_rainfall_est,
        "source": source,
    }


# ─── /health endpoint ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_accuracy": round(get_model_accuracy() * 100, 2),
        "version": "2.0.0",
        "total_crops": len(MARKET_SCORES),
        "live_mandi_prices": bool(DATA_GOV_API_KEY),
        "mandi_archive_available": MANDI_ARCHIVE_PATH.exists(),
    }


# ─── Dev entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
