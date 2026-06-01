# Deploy on Vercel (Naukri every 30 minutes)

Vercel runs **Naukri** auto-apply on a **Cron schedule every 30 minutes**.  
**LinkedIn** still runs on your PC (Brave + Selenium) — Vercel cannot run a browser.

## Architecture

| Where | What |
|--------|------|
| **Vercel Cron** | `GET /api/cron/apply` every 30 min → search & apply on Naukri |
| **Vercel Blob** | Stores `job_applications.xlsx` between runs |
| **Your PC** | `python react_devops_auto_apply.py` for LinkedIn + optional local Naukri |

> **Warning:** Naukri often blocks **datacenter IPs** (including Vercel). If you get 403/auth errors, run Naukri locally and use Vercel only for monitoring, or use a residential proxy.

## 1. Prerequisites

- [Vercel account](https://vercel.com)
- [Vercel Blob](https://vercel.com/docs/storage/vercel-blob) store linked to the project
- Naukri cookies from `python google_login.py`

## 2. Prepare cookies for Vercel

```bash
python scripts/cookies_to_env.py
```

Copy the printed line → you will paste it as `NAUKRI_COOKIES_JSON`.

## 3. Deploy

### Option A — Vercel CLI

```bash
npm i -g vercel
vercel login
vercel
```

### Option B — GitHub

1. Push this repo to GitHub  
2. [vercel.com/new](https://vercel.com/new) → Import repository  
3. Framework: **Other** (Python serverless + static `public/`)

## 4. Environment variables (Vercel → Settings → Environment Variables)

| Variable | Required | Description |
|----------|----------|-------------|
| `CRON_SECRET` | Yes | Random string, e.g. `openssl rand -hex 32` |
| `NAUKRI_COOKIES_JSON` | Yes | One-line JSON from `cookies_to_env.py` |
| `BLOB_READ_WRITE_TOKEN` | Yes | From Vercel → Storage → Blob → token |
| `OPENROUTER_API_KEY` | Optional | For questionnaires |
| `OPENROUTER_MODEL` | Optional | `openai/gpt-oss-120b:free` |
| `EXCEL_BLOB_URL` | Optional | Set after first run if upload returns a URL |

Enable for **Production** (and Preview if you want).

## 5. Cron schedule

Defined in `vercel.json`:

```json
"schedule": "0/30 * * * *"
```

Runs at **:00** and **:30** every hour (UTC). Change the cron expression if you need IST-aligned times.

## 6. Verify

- Open your deployment URL → status page  
- `https://YOUR_PROJECT.vercel.app/api/health`  
- Manually trigger cron (with secret):

```bash
curl -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://YOUR_PROJECT.vercel.app/api/cron/apply
```

Response JSON includes `naukri.stats` (applied / skipped / failed).

## 7. Local vs Vercel

| Task | Command |
|------|---------|
| LinkedIn + Naukri locally, loop 30 min | `python react_devops_auto_apply.py` |
| One local cycle | `python react_devops_auto_apply.py --once` |
| Naukri on Vercel only | Automatic via Cron |

## 8. Pro plan note

Cron + long runs may need **Vercel Pro** for `maxDuration: 300` (5 minutes). On Hobby, function timeout may be shorter — reduce `PAGES_PER_QUERY` in `config.py` if runs time out.

## 9. Refresh cookies

When Naukri session expires:

1. `python google_login.py` on your PC  
2. `python scripts/cookies_to_env.py`  
3. Update `NAUKRI_COOKIES_JSON` in Vercel and redeploy (or save env without redeploy)
