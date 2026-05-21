# SkullMod Daily Words API

FastAPI backend for SkullMod daily words.

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Create `.env` from `.env.example` and set a real `SECRET_KEY`.
4. Run the API:

```bash
uvicorn app.main:app --reload
```

## Tests

```bash
python -m pytest
```

## Render PostgreSQL Setup

For production, use Render PostgreSQL instead of SQLite.

1. Create a PostgreSQL database in Render.
2. Copy the database's internal connection string.
3. In the `skullmod-daily-words-api` web service, set:

```text
DATABASE_URL=<Render PostgreSQL internal connection string>
SECRET_KEY=<random string with at least 32 characters>
ENV=production
```

The app accepts both `postgres://...` and `postgresql://...` URLs and normalizes them for SQLAlchemy.

After changing `DATABASE_URL`, trigger a manual deploy in Render. On startup, the API creates the required tables if they do not exist.

## Physical Skull NFC Artifacts

Create artifact records before writing NFC tags. The generated CSV contains the URL that should be written to each physical NFC tag.

```bash
python scripts/create_artifacts.py \
  --count 10 \
  --production-batch FOUNDER-001 \
  --artifact-type prototype \
  --artifact-series "Founder Series" \
  --material-type epoxy \
  --output exports/founder-001.csv
```

Set `PUBLIC_NFC_BASE_URL` in `.env` or pass `--base-url` to control the URL prefix. Example output URL:

```text
https://skullmod.app/nfc/<public_token>
```

The NFC tag stores only the artifact URL. Ownership is created later when a user claims the artifact through the app/backend.

## Production Notes

- Set `SECRET_KEY` in Render or the hosting provider environment.
- Use an explicit `CORS_ORIGINS` list in production instead of `*`.
- Use a persistent production database before public launch.
- Keep `.env` and local SQLite files out of git.
