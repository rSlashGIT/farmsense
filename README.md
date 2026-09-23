# FarmSense AI

**FarmSense AI** is a full-stack crop recommendation and farm decision-support project for Indian agriculture. It combines a Random Forest classifier, live weather, soil-report extraction, market scoring, optional live mandi prices, profitability estimates, and a React dashboard.

This repository is the **complete project handoff** for students who want to run, understand, extend, or use the project as the implementation base for academic work.

> Start with [HANDOFF.md](./HANDOFF.md) if you are taking over this project.

---

## Current Project Snapshot

| Item | Current implementation |
|---|---|
| Frontend | React 18 + Vite 5 + Tailwind CSS 3 |
| Backend | Python 3.11 + FastAPI |
| ML model | scikit-learn RandomForestClassifier |
| Crop classes | **56** |
| ML dataset | **5,600 rows** (100 generated samples per crop) |
| Direct ML input features | **7**: N, P, K, temperature, humidity, pH, rainfall |
| Recommendation output | Top **5** crops |
| Mandi archive | **7,000 monthly rows**, Jan 2016-May 2026 |
| Weather | Open-Meteo + MET Norway fallback |
| Soil report extraction | PDF text parsing + Tesseract OCR for images |
| Frontend deployment | Vercel |
| Backend deployment | Render |
| API version | 2.0.0 |

---

## What the Application Does

1. Accepts soil, climate, location, farm and budget inputs.
2. Can extract common soil values from a PDF/JPG/PNG soil report.
3. Uses a trained Random Forest model to rank crop candidates.
4. Combines ML fit with market and profitability scoring.
5. Uses Open-Meteo for Indian location search/weather and falls back to MET Norway if the forecast provider is rate-limited or unavailable.
6. Uses static market baselines by default and can use the data.gov.in / AGMARKNET feed when a backend API key is configured.
7. Returns five crop recommendations with fit, market score, profit index, estimated revenue/ROI and supporting crop information.

---

## Architecture

```text
React / Vite frontend
        |
        v
FastAPI backend
   |        |         |          |
   |        |         |          +--> Soil report parser (pdfplumber / Tesseract)
   |        |         +-------------> Open-Meteo weather + geocoding
   |        +-----------------------> Market baselines + optional AGMARKNET live price
   +--------------------------------> Random Forest crop classifier
```

---

## Repository Structure

```text
farmsense/
├── backend/
│   ├── data/
│   │   ├── crop_data.csv
│   │   ├── mandi_price_history_2016_2026.csv
│   │   └── mandi_price_history_summary.json
│   ├── main.py
│   ├── model.py
│   ├── market_data.py
│   ├── ocr_parser.py
│   ├── generate_dataset.py
│   ├── build_mandi_price_archive.py
│   ├── requirements.txt
│   ├── requirements-lock.txt  # tested handoff snapshot
│   └── .env.example
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── vite.config.js
│   ├── vercel.json
│   └── .env.example
├── docs/
│   └── RESEARCH_HANDOFF.md
├── HANDOFF.md
├── FarmSense_AI_Updated_Technical_Details.docx  # May 2026 report snapshot
├── MANDI_DATA.md
├── VERCEL_DEPLOYMENT.md
├── render.yaml
├── run.sh
└── README.md
```

---

## Local Setup

### Prerequisites

- Python **3.11** recommended
- Node.js **18+**
- npm
- Git
- Optional: Tesseract OCR installed on the system for image-based soil reports

### 1. Clone

```bash
git clone https://github.com/rSlashGIT/farmsense.git
cd farmsense
```

### 2. Backend

#### Windows PowerShell

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload --port 8001
```

#### macOS / Linux

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8001
```

Backend:
- API: `http://localhost:8001`
- Swagger: `http://localhost:8001/docs`
- Health: `http://localhost:8001/health`

The dataset is already committed. If model artifacts are absent, the backend trains automatically on startup.

For an exact snapshot of the Python package versions verified during the September 2026 handoff, use `backend/requirements-lock.txt`. The normal deployment continues to use `requirements.txt`.

### 3. Frontend

Open a second terminal:

```bash
cd frontend
npm ci
```

Create `frontend/.env` from `.env.example`, then run:

```bash
npm run dev
```

Open `http://localhost:5173`.

Default local API setting:

```text
VITE_API_BASE_URL=http://localhost:8001
```

---

## Backend Environment Variables

```text
DATA_GOV_API_KEY=your_data_gov_api_key_here
MANDI_CACHE_TTL_SECONDS=21600
MANDI_API_TIMEOUT_SECONDS=6
MET_NORWAY_USER_AGENT=FarmSense-AI/2.0 https://github.com/rSlashGIT/farmsense
```

`DATA_GOV_API_KEY` is optional for local operation. Without it, the project still works with static market data and the local mandi archive.

Never commit a real API key.

---

## Main API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Backend/model/data health |
| POST | `/predict` | Top-5 crop recommendations |
| POST | `/upload-report` | Extract soil values from PDF/JPG/PNG |
| GET | `/locations?query=...` | Indian location suggestions |
| GET | `/weather?location=...` | Weather auto-fill values |
| GET | `/market-prices` | Market reference data |
| GET | `/market-history` | Local mandi archive |

Interactive schemas are available at `/docs`.

---

## Scoring

```text
overall_score =
    (fit_score × 0.45)
  + (market_score × 0.35)
  + (profit_index × 0.20)
```

**Important:** `fit_score` is not the raw Random Forest probability. Read [docs/RESEARCH_HANDOFF.md](./docs/RESEARCH_HANDOFF.md) before using these values in academic work.

---

## Dataset and Reproducibility

`backend/data/crop_data.csv` currently contains:

- 5,600 rows
- 56 crop classes
- 100 rows per crop
- columns: `N, P, K, temperature, humidity, ph, rainfall, label`

Regenerate deterministically with:

```bash
cd backend
python generate_dataset.py
```

The generator uses `numpy.random.seed(42)`.

---

## Deployment

Current hosted endpoints:

- Frontend: https://farmsense-ai-nine.vercel.app
- Backend: https://farmsense-ai-backend-dhoy.onrender.com
- Backend health: https://farmsense-ai-backend-dhoy.onrender.com/health

Configuration:
- Frontend: [VERCEL_DEPLOYMENT.md](./VERCEL_DEPLOYMENT.md)
- Backend: [render.yaml](./render.yaml)
- Mandi data: [MANDI_DATA.md](./MANDI_DATA.md)

For a new Vercel deployment:

```text
VITE_API_BASE_URL=https://<your-render-backend>
```

Keep `DATA_GOV_API_KEY` only on the backend.

---

## Legacy Technical Document

`FarmSense_AI_Updated_Technical_Details.docx` is a **May 18, 2026 report snapshot**. It contains some planned/report-oriented wording (including a React Native iOS direction) that is not the current web implementation. For current behavior, treat the source code, this README, `HANDOFF.md`, and `docs/RESEARCH_HANDOFF.md` as authoritative.

---

## Student Continuation Checklist

1. Read [HANDOFF.md](./HANDOFF.md).
2. Verify `/health`.
3. Confirm the frontend says **System Online**.
4. Test one prediction.
5. Test weather auto-fill.
6. Test `/market-history`.
7. Read [docs/RESEARCH_HANDOFF.md](./docs/RESEARCH_HANDOFF.md) before writing a paper, report or methodology section.

---

## Important Limitation

FarmSense is an academic decision-support project. Crop suitability, weather-derived rainfall, mandi prices, yield, revenue and ROI values should be independently validated before real-world farming decisions or publication-quality claims.
