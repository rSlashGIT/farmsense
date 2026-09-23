# FarmSense AI — Junior Handoff Guide

This is the shortest path for anyone taking over the project.

## What you already have

The repository already contains:

- React frontend source
- FastAPI backend source
- 56-class crop dataset
- model training and inference code
- soil-report parser
- weather and Indian location integration
- market scoring data
- local mandi archive
- Render and Vercel deployment configuration

You do **not** need to rebuild the project from scratch.

## First 15 minutes

1. Clone the repository.
2. Follow the Local Setup section in `README.md`.
3. Start the backend on port `8001`.
4. Open `http://localhost:8001/health`.
5. Open `http://localhost:8001/docs`.
6. Start the frontend on port `5173`.
7. Confirm the frontend shows **System Online**.
8. Run one crop recommendation.

A healthy backend response should include `"status": "ok"`, model accuracy, `"total_crops": 56`, and mandi archive availability.

## Minimum functional verification

Before changing code, verify:

- `GET /health`
- `GET /locations?query=Bengaluru`
- `GET /weather?location=Bengaluru`
- `GET /market-history?crop=tomato&limit=5`
- one `POST /predict` through Swagger or the frontend
- PDF soil report upload
- JPG/PNG upload if Tesseract is installed

## Where to change what

| Goal | Main file(s) |
|---|---|
| API routes / validation | `backend/main.py` |
| ML model / training / inference | `backend/model.py` |
| Crop market assumptions | `backend/market_data.py` |
| Soil report parsing | `backend/ocr_parser.py` |
| Regenerate crop dataset | `backend/generate_dataset.py` |
| Rebuild mandi archive | `backend/build_mandi_price_archive.py` |
| Frontend shell | `frontend/src/App.jsx` |
| Input form | `frontend/src/components/InputForm.jsx` |
| Results UI | `frontend/src/components/ResultsPanel.jsx` |
| API client | `frontend/src/api.js` |
| Styling | `frontend/src/index.css` |

## Environment variables

Frontend:

```text
VITE_API_BASE_URL=http://localhost:8001
```

Backend:

```text
DATA_GOV_API_KEY=...
MANDI_CACHE_TTL_SECONDS=21600
MANDI_API_TIMEOUT_SECONDS=6
MET_NORWAY_USER_AGENT=FarmSense-AI/2.0 https://github.com/rSlashGIT/farmsense
```

The live mandi key is optional. Never commit a real key.

## OCR note

PDF reports use `pdfplumber`.

Image reports use `pytesseract`, which also requires the **Tesseract OCR application** installed on the computer and available on PATH. Installing only the Python package is not enough.

## Research / paper work

Read `docs/RESEARCH_HANDOFF.md` before writing a paper, methodology section, results section, presentation or dataset description.

The root `FarmSense_AI_Updated_Technical_Details.docx` is a May 18, 2026 report snapshot and includes some planned/report wording. Use the current source + handoff docs as the authority when they differ.

Several project values are generated or derived rather than direct real-world observations. The research handoff explains which ones.

## Safe workflow

- Create your own branch before major changes.
- Do not commit `.env`, API keys, `.venv`, `node_modules`, build folders or generated model pickle files.
- Keep frontend and backend API schemas synchronized.
- If changing model inputs, update the dataset, Pydantic schema, frontend form and docs together.
- Re-test health, prediction, weather, market and report upload after backend changes.

## Common problems

**Frontend says System Offline**

Check that the backend is on port 8001 and `frontend/.env` points to it.

**Model does not load**

Delete local `model.pkl`, `label_encoder.pkl` and `model_meta.pkl`, then restart the backend to retrain.

**Image OCR fails**

Install Tesseract and ensure the executable is on PATH.

**Live mandi prices are not used**

Configure a valid backend `DATA_GOV_API_KEY`. Without it the fallback is intentional.

**Weather/location fails**

Internet access is required. Forecasts use Open-Meteo first and automatically fall back to MET Norway. If you fork the project, update `MET_NORWAY_USER_AGENT` to identify your own project/contact URL.

## Before submitting academic work

Record the exact:

- Git commit SHA
- dataset rows/classes
- train/test split
- random seed
- model hyperparameters
- evaluation metrics
- whether live mandi data was enabled
- code or dataset changes made

That keeps the work reproducible.
