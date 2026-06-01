"""Configuration for Naukri + LinkedIn auto-apply (React Developer & DevOps Engineer)."""

import os

_IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))

# Run both platforms in a loop; wait this many minutes between cycles
LOOP_INTERVAL_MINUTES = 30

# Set False to disable a platform without removing code
ENABLE_NAUKRI = True
# LinkedIn needs Brave/Selenium — off on Vercel serverless
ENABLE_LINKEDIN = not _IS_VERCEL

# Skip jobs when this company was already applied (any platform, Excel "Applied" rows)
SKIP_IF_COMPANY_ALREADY_APPLIED = True

# Search keywords — jobs are fetched for each entry (All India when location is empty)
SEARCH_QUERIES = [
    {"keyword": "React Developer", "location": ""},
    {"keyword": "React.js Developer", "location": ""},
    {"keyword": "Frontend React Developer", "location": ""},
    {"keyword": "React Native Developer", "location": ""},
    {"keyword": "DevOps Engineer", "location": ""},
    {"keyword": "DevOps", "location": ""},
    {"keyword": "AWS DevOps Engineer", "location": ""},
    {"keyword": "Site Reliability Engineer", "location": ""},
]

# Only apply when job title matches at least one of these (case-insensitive)
TITLE_KEYWORDS = [
    "react",
    "reactjs",
    "react.js",
    "react native",
    "frontend",
    "front-end",
    "devops",
    "dev ops",
    "sre",
    "site reliability",
    "platform engineer",
    "cloud engineer",
    "kubernetes",
    "docker",
    "aws",
    "azure",
    "gcp",
    "ci/cd",
    "jenkins",
    "terraform",
]

# Experience in years (Naukri search filter)
EXPERIENCE_YEARS = 2

# Max age of job postings in days (1 = today, 3 = last 3 days)
JOB_AGE_DAYS = 3

# Pages to fetch per search query (1 on Vercel to stay within serverless timeout)
PAGES_PER_QUERY = 1 if _IS_VERCEL else 2

# Delay between API calls (seconds) — avoid rate limits
SEARCH_DELAY_SEC = 1.5
APPLY_DELAY_SEC = 3

# Excel file — all runs append to this same file (Naukri + LinkedIn)
EXCEL_FILE = "job_applications.xlsx"

# Legacy CSV (optional backup; Excel is the main store)
APPLIED_JOBS_CSV = "applied_jobs.csv"

# LinkedIn job search (browser automation)
LINKEDIN_COOKIES_FILE = "linkedin_cookies.json"
LINKEDIN_LOCATION = "India"
LINKEDIN_MAX_JOBS_PER_QUERY = 15
LINKEDIN_SEARCH_QUERIES = [
    "React Developer",
    "React.js Developer",
    "Frontend React Developer",
    "DevOps Engineer",
    "DevOps",
    "AWS DevOps Engineer",
    "Site Reliability Engineer",
]

# Browser headless for LinkedIn (set False to watch the browser)
LINKEDIN_HEADLESS = False

# Sign-in and LinkedIn automation use Brave (Chromium). Set False to use default Chrome.
USE_BRAVE_BROWSER = True
# Leave empty to auto-detect on Windows; or set full path to brave.exe
BRAVE_BINARY_PATH = ""

# LinkedIn Easy Apply popup — max Next/Review/Submit steps per job
LINKEDIN_EASY_APPLY_MAX_STEPS = 25

# OpenRouter AI for tricky LinkedIn questions (set OPENROUTER_API_KEY in .env)
USE_OPENROUTER_FOR_LINKEDIN = True
OPENROUTER_MODEL = "openai/gpt-oss-120b:free"

# Your profile — used when Naukri asks questions during apply
APPLICANT_PROFILE = {
    "current_ctc_annual": 168000,   # ₹1,68,000 per year
    "expected_ctc_annual": 500000,  # ₹5,00,000 per year
    "exp_total": "2",               # years of experience (all questions)
    "current_location": "Pune",
    "willing_to_relocate": True,
    "notice_days": 30,
    "skills": [
        "react", "javascript", "typescript", "redux",
        "docker", "kubernetes", "aws", "ci/cd",
        "jenkins", "terraform", "linux", "git",
    ],
}
