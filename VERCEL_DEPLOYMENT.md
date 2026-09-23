# FarmSense AI Deployment Guide

FarmSense uses separate deployments:

- **Frontend:** Vercel
- **Backend:** Render

Source repository: `rSlashGIT/farmsense`.

Current production endpoints:

- Frontend: https://farmsense-ai-nine.vercel.app
- Backend: https://farmsense-ai-backend-dhoy.onrender.com
- Health endpoint: https://farmsense-ai-backend-dhoy.onrender.com/health

## Frontend — Vercel

Use:

| Setting | Value |
|---|---|
| Framework | Vite |
| Root Directory | `frontend` |
| Install Command | `npm install` or `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |

Set:

```text
VITE_API_BASE_URL=https://<your-render-backend-domain>
```

Never point a deployed frontend to `localhost`.

## Backend — Render

The repository includes `render.yaml` with:

```text
name: farmsense-ai-backend
runtime: python
rootDir: backend
buildCommand: pip install -r requirements.txt
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
healthCheckPath: /health
```

Platform Python version:

```text
3.11.11
```

Optional live-mandi configuration:

```text
DATA_GOV_API_KEY=<your data.gov.in key>
```

## Health verification

After backend deployment:

```text
https://<backend-domain>/health
```

Expected shape:

```json
{
  "status": "ok",
  "model_accuracy": 0,
  "version": "2.0.0",
  "total_crops": 56,
  "live_mandi_prices": false,
  "mandi_archive_available": true
}
```

The actual model accuracy is returned at runtime.

Then verify:

```text
https://<backend-domain>/docs
https://<backend-domain>/market-history?crop=tomato&limit=5
https://<backend-domain>/weather?location=Bengaluru
```

## Connect frontend to backend

1. Set Vercel `VITE_API_BASE_URL` to the Render base URL.
2. Redeploy the frontend.
3. Load the app.
4. Confirm **System Online**.
5. Run one prediction.

## Secrets

Keep all API keys on the backend.

Never put `DATA_GOV_API_KEY` in a `VITE_...` variable because Vite variables are exposed to client-side JavaScript.

## Free-tier note

Render free services can sleep when idle, so the first request can be slower after inactivity.
