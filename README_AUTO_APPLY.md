# Naukri + LinkedIn Auto-Apply — React Developer & DevOps Engineer

Automatically search **Naukri.com** and **LinkedIn** for React and DevOps roles, apply to Easy Apply jobs, skip companies you already applied to, and log external apply URLs in Excel.

## What it does

1. Logs into Naukri (API) and LinkedIn (browser)
2. Searches React / DevOps keywords
3. **Repeats every 30 minutes** (configurable) until you stop it
4. **Skips** jobs already applied (by job ID) and **companies** already applied (by company name)
5. **Saves external redirect URLs** in Excel when apply goes to a company website
6. **Auto-answers questionnaires**: Yes where possible, **30 days** notice, **relocate Yes**, **2 years** experience

## Setup

### 1. Install Python 3.10+

```bash
pip install -r requirements.txt
```

### 2. OpenRouter API key (LinkedIn form questions)

Copy `env.example` to `.env` and add your key:

```bash
copy env.example .env
```

```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-oss-120b:free
```

The bot fills Easy Apply popups automatically (Next → Review → Submit). AI is used when a question is not covered by your profile defaults.

### 3. Naukri sign-in (Google)

```bash
python google_login.py
```

Saves `naukri_cookies.json`.

### 4. LinkedIn sign-in (one time)

```bash
python linkedin_login.py
```

Saves `linkedin_cookies.json`. **Brave** opens; complete login manually.

### 5. Run auto-apply

```bash
python react_devops_auto_apply.py
```

Runs Naukri + LinkedIn, then waits **30 minutes** and runs again. Press **Ctrl+C** to stop.

Single run (no loop):

```bash
python react_devops_auto_apply.py --once
```

## Configuration (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `LOOP_INTERVAL_MINUTES` | 30 | Minutes between full cycles |
| `ENABLE_NAUKRI` | True | Toggle Naukri |
| `ENABLE_LINKEDIN` | True | Toggle LinkedIn |
| `SKIP_IF_COMPANY_ALREADY_APPLIED` | True | Skip same company name |
| `EXCEL_FILE` | `job_applications.xlsx` | Log file |
| `APPLICANT_PROFILE` | notice 30, exp 2, relocate yes | Questionnaire answers |
| `USE_BRAVE_BROWSER` | True | Sign-in and LinkedIn use Brave |
| `BRAVE_BINARY_PATH` | (auto) | Full path to brave.exe if not detected |
| `LINKEDIN_HEADLESS` | False | Set True to hide Brave |
| `USE_OPENROUTER_FOR_LINKEDIN` | True | AI answers for unknown questions |
| `OPENROUTER_MODEL` | openai/gpt-oss-120b:free | Model on OpenRouter |
| `LINKEDIN_EASY_APPLY_MAX_STEPS` | 25 | Max Next/Submit steps per job |

## Excel output

File: **`job_applications.xlsx`** (or set `EXCEL_FILE` in `.env`)

| Column | Description |
|--------|-------------|
| Platform | Naukri or LinkedIn |
| Job URL | Listing link |
| **External Apply URL** | Company site when not Easy Apply |
| Status | Applied / Skipped / Failed |
| Company | Used to skip duplicate companies |

## Profile answers (questionnaires)

Edit `APPLICANT_PROFILE` in `config.py`:

- Experience: **2 years**
- Notice period: **30 days**
- Willing to relocate: **Yes**
- Other yes/no questions: **Yes** when unclear

## Deploy Naukri on Vercel (every 30 minutes)

See **[README_VERCEL.md](README_VERCEL.md)** for Cron + Blob setup. LinkedIn stays on your PC.

## Important notes

- **Home IP** recommended for Naukri (cloud IPs may get 403).
- **LinkedIn** uses Selenium/**Brave** — keep the window usable; re-run `linkedin_login.py` if session expires.
- **Terms of service** — use only on your own accounts.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Naukri 403 | Home IP; run `google_login.py` again |
| LinkedIn login failed | Run `python linkedin_login.py` |
| No LinkedIn jobs | Set `LINKEDIN_HEADLESS = False` and watch the browser |
| Old Excel (`naukri_jobs.xlsx`) | New runs use `job_applications.xlsx`; old file still works as reference |

## Project structure

```
├── google_login.py              # Naukri Google sign-in
├── linkedin_login.py            # LinkedIn sign-in
├── react_devops_auto_apply.py   # Main script (loop + both platforms)
├── config.py                    # Intervals, keywords, profile
├── job_applications.xlsx        # Created on first run
├── naukri_cookies.json
├── linkedin_cookies.json
└── src/client/linkedin_client.py
```
