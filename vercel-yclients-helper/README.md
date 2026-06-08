# YClients Credentials Helper (Vercel)

Standalone web form that lets a barbershop owner enter their YClients
login/password and receive their personal **`user_token`** and **`company_id`**(s),
using your partner integrator token.

No DB, no Redis — single Python serverless function.

## What gets deployed

- `GET  /`                — HTML form
- `POST /api/credentials` — proxies `POST /auth` + `GET /companies?my=1` to YClients
- `GET  /api/health`      — liveness check

## Deploy in 3 steps

### 1. Install Vercel CLI (one-time)

```bash
npm i -g vercel
vercel login
```

### 2. Deploy

```bash
cd vercel-yclients-helper
vercel                # first run: links project, asks a few questions
vercel --prod         # deploy to production
```

When asked "In which directory is your code located?" — press Enter (current dir).

### 3. Set env vars

Either via dashboard (`Project Settings → Environment Variables`) or CLI:

```bash
vercel env add YCLIENTS_PARTNER_TOKEN production
# paste your partner token, hit Enter

# Optional: protect the form with a shared key (see below)
vercel env add YCLIENTS_HELPER_ACCESS_KEY production
```

Then redeploy so the new env vars take effect:

```bash
vercel --prod
```

## Sharing with your friend

Vercel will give you a URL like `https://yc-helper-abc123.vercel.app`.

- **Without access key**: just send the URL. Anyone who hits it can try
  YClients credentials (against your partner token).
- **With access key set**: send the URL with the key as query param:
  `https://yc-helper-abc123.vercel.app/?key=YOUR_SECRET`. Without `?key=...`
  the form returns 403.

## Security notes

- The partner token lives only in Vercel env vars. Never sent to the browser.
- Login/password are **not** persisted anywhere — they live in memory for one
  HTTP round-trip and are dropped.
- For extra safety: deploy → use → run `vercel remove yc-helper` when done.
- Vercel logs request metadata (IP, path, status). Don't log request bodies.

## Local testing

```bash
cd vercel-yclients-helper
pip install -r requirements.txt
YCLIENTS_PARTNER_TOKEN=your_token uvicorn api.index:app --port 8001
# open http://localhost:8001
```
