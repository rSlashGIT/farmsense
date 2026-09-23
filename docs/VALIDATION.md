# FarmSense AI Validation Record

Last verified: **23 September 2026**

This file records checks performed against the current handoff so the next team can distinguish verified behavior from documentation-only claims.

## Production checks

The following deployed endpoints returned HTTP 200:

- Frontend: https://farmsense-ai-nine.vercel.app
- Backend health: https://farmsense-ai-backend-dhoy.onrender.com/health
- Swagger docs: https://farmsense-ai-backend-dhoy.onrender.com/docs
- Mandi history sample: /market-history?crop=tomato&limit=2
- Bengaluru weather: /weather?location=Bengaluru

Observed production health response:

```json
{
  "status": "ok",
  "model_accuracy": 78.12,
  "version": "2.0.0",
  "total_crops": 56,
  "live_mandi_prices": false,
  "mandi_archive_available": true
}
```
## Weather check

The Bengaluru weather endpoint resolved the location to Bengaluru, Karnataka, India and returned live values successfully.

During this verification the backend used the **MET Norway fallback**, confirming the fallback path is working when Open-Meteo forecast data is unavailable or rate-limited.

## Frontend build check

From `frontend/`:

```bash
npm ci
npm run build
```

Result: **production Vite build passed**.

The build transformed 38 modules and produced the `dist/` bundle successfully.

## Dependency advisory note

`npm ci` reported two npm audit advisories at validation time:

- 1 moderate
- 1 high

The application still builds successfully. These were not automatically force-upgraded because `npm audit fix --force` can introduce breaking dependency changes. Review advisories before making dependency upgrades.
## Recommended re-check after future changes

After modifying the project, repeat at minimum:

1. `npm ci && npm run build`
2. Start the backend and verify `GET /health`
3. Run one `POST /predict`
4. Verify `GET /locations`
5. Verify `GET /weather`
6. Verify `GET /market-history`
7. Load the frontend and confirm **System Online**
8. Test one recommendation through the UI

For research-facing claims, also follow `docs/RESEARCH_HANDOFF.md`.

## Scope

This validation confirms deployment reachability, backend health/data availability, selected API routes and frontend buildability. It is not a substitute for a full agronomic validation, security audit or publication-quality model evaluation.
