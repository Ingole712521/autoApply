<p align="center">
  <img src="assests/logo2.svg" alt="naukri-api-client" width="680"/>
</p>

# Noperi

A lightweight and Selenium-free Python API client for Naukri.com, designed to help you update your profile, upload your resume, and retrieve personalized job recommendations programmatically.

---

**Status:** 🟢 Working (Last tested: April 2026)

---

## ✨ Features

| Feature | Status |
|---|---|
| Login & session management (Bearer token) | ✅ Working |
| Resume upload (PDF) | ✅ Working |
| Profile update (headline, name, summary) | ✅ Working |
| Recommended jobs feed | ✅ Working |
| `nkparam` token harvester (Selenium utility) | ✅ Working |
| Job search (`/jobapi/v3/search`) | 🚧 Under development |
| One-click job apply | 🚧 Under development |

> **No Selenium required** for features 1–4. The Selenium script is only needed as a helper to harvest fresh `nkparam` tokens for the search endpoint.

---

## 🗂️ Project Structure

```
naukri-api-client/
├── main.py                     # Entry point — demo of all features
├── nkPool.txt                  # Pool of captured nkparam tokens
├── .env                        # Credentials 
├── src/
│   ├── client/
│   │   ├── naukri_client.py    # Core auth + profile + resume client
│   │   ├── job_client.py       # Recommended jobs + search + apply
│   │   └── session.py          # requests.Session factory
│   ├── config/
│   │   └── constants.py        # URLs, regex patterns, app IDs
│   ├── exceptions/
│   │   └── exceptions.py       # Custom exception classes
│   ├── models/
│   │   └── models.py           # Dataclasses: Job, NaukriSession, etc.
│   └── utils/
│       ├── extractors.py       # HTML / JS parsing helpers
│       └── request_helper.py   # Exponential-retry decorator
        ├── get_Nkparam.py          # Selenium helper to harvest nkparam tokens
```

---

## ⚠️ IP & Hosting Advice

Naukri fingerprints IPs for every request. Many cloud providers trigger MFA or get blocked.

**Avoid:**
- Azure (all regions)
- GitHub Actions / CI
- Some Google Cloud regions
- Datacenter IP ranges

**Works:**
- AWS (EC2 with Elastic IP)
- Home broadband / personal IP (best)
- Mobile hotspot (testing)
- Residential proxy

**Note:**
- Sessions are IP-bound — changing IP will invalidate login
- Avoid GitHub Actions completely (IP pool is flagged)




## ⚙️ Installation

**Requirements:** Python 3.10+

```bash
git https://github.com/Traverser25/NopeRi.git
cd Noperi
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
USERNAME=your_naukri_email@example.com
PASSWORD=your_naukri_password
```

---

## 🚀 Quick Start 
you can simply run  main.py also

```python
from src.client.naukri_client import NaukriLoginClient
from src.client.job_client import NaukriJobClient
from dotenv import load_dotenv
import os

load_dotenv()

# 1. Login
client = NaukriLoginClient(os.getenv("USERNAME"), os.getenv("PASSWORD"))
client.login()

# 2. Upload resume
client.update_resume("path/to/your_resume.pdf")

# 3. Update profile headline
client.update_profile(headline="Backend Engineer | Python · Node.js · AWS")

# 4. Update profile summary
client.update_profile(summary="Experienced engineer with 2+ years building scalable APIs.")

# 5. Fetch recommended jobs
jc = NaukriJobClient(client)
jobs = jc.get_recommended_jobs()
for job in jobs:
    print(job.title, "—", job.company, "|", job.location)
```

---

## 📖 API Reference

### `NaukriLoginClient`

| Method | Description |
|---|---|
| `login()` | Authenticates and stores the Bearer token + session cookies |
| `update_resume(file)` | Uploads a PDF resume; accepts a file path (`str`) or a file-like object |
| `update_profile(headline, name, summary)` | Updates one or more profile fields (all arguments are optional) |
| `fetch_profile_id()` | Returns your Naukri profile ID (cached after first call) |
| `get_form_key2()` | Extracts the internal `formKey` from Naukri's JS bundle (cached) |

### `NaukriJobClient`

| Method | Description |
|---|---|
| `get_recommended_jobs()` | Returns a list of `Job` objects personalised to your profile |
| `search_jobs(keyword, location, page, experience, ...)` | 🚧 Job search — under development (see note below) |
| `apply_job(job)` | 🚧 Apply to a job — under development |

### `Job` model

```python
@dataclass
class Job:
    job_id:      str
    title:       str
    company:     str
    location:    str
    experience:  str
    salary:      str
    posted_date: str
    apply_link:  str
    description: str
    tags:        list[str]
```

---

## 🔑 The `nkparam` Problem (and Current Solution)

Naukri's job-search endpoint (`/jobapi/v3/search`) requires a request header called `nkparam` — a signed token generated inside Naukri's obfuscated JavaScript bundle that changes with each browser session. Without a valid token the API returns `403 Forbidden`.

**Current workaround — `get_Nkparam.py`:**  
A Selenium script that opens a real Chrome browser, navigates to a Naukri search page, intercepts the outgoing network request via Chrome's performance logs, and appends the captured `nkparam` value to `nkPool.txt`. The job client rotates through this pool at runtime.

```bash
python nk_param_getter.py   # Run once to populate nkPool.txt, Ctrl+C to stop
```

**Ongoing work:** Reverse-engineering how Naukri computes `nkparam` directly from the JS bundle so that the Selenium dependency can be eliminated entirely for search as well.

---

## 🤖 Using Recommended Jobs as an Agent Feed

`get_recommended_jobs()` returns a plain Python list of `Job` dataclasses, making it easy to pipe into any automation or AI agent:

```python
jobs = jc.get_recommended_jobs()

# Feed into an LLM agent, a Notion database, a Telegram bot, etc.
for job in jobs:
    payload = {
        "title":    job.title,
        "company":  job.company,
        "location": job.location,
        "skills":   job.tags,
        "url":      job.apply_link,
    }
    your_agent.process(payload)
```

---

## ⚠️ Disclaimer

This project is intended for personal automation of your **own** Naukri account. Use responsibly and in accordance with [Naukri's Terms of Service](https://www.naukri.com/termsAndConditions). The authors are not affiliated with Naukri / InfoEdge India Ltd.

---

## 🛣️ Roadmap

- [ ] Reverse-engineer `nkparam` generation to remove Selenium dependency for search
- [ ] Complete job-search endpoint integration
- [ ] Complete one-click job-apply flow
- [ ] Add async support (`httpx` / `aiohttp`)
- [ ] CLI interface

---

## 🤝 Contributing

Pull requests are welcome! If you crack the `nkparam` generation algorithm, please open an issue or PR — it is the last missing piece for a fully Selenium-free client.

---
