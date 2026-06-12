"""Configuration for multi-platform job auto-apply (Naukri, LinkedIn, Foundit, remote boards)."""

import os

_IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))

# Local loop: minutes between cycles when running react_devops_auto_apply.py on your PC
LOOP_INTERVAL_MINUTES = 30

# Vercel Cron schedule is in vercel.json (once daily: "30 4 * * *" = ~10:00 AM IST)

# Set False to disable a platform without removing code
ENABLE_NAUKRI = True
# LinkedIn needs Brave/Selenium — off on Vercel serverless
ENABLE_LINKEDIN = not _IS_VERCEL

# Extra job boards — fetch listings and log company + apply URL to Excel
ENABLE_FOUNDIT = True
ENABLE_REMOTE_OK = True
ENABLE_SURELY_REMOTE = True
ENABLE_REMOTIVE = True

# Keywords used on Foundit + Surely Remote (Naukri uses SEARCH_QUERIES)
EXTERNAL_BOARD_KEYWORDS = [
    "DevOps Engineer",
    "DevOps",
    "AWS DevOps Engineer",
    "Site Reliability Engineer",
    "Platform Engineer",
    "Kubernetes Engineer",
]

# Foundit pages per keyword (URL pattern: ...-jobs, ...-jobs-2, ...)
FOUNDIT_MAX_PAGES = 2 if _IS_VERCEL else 5

# Skip jobs when this company was already applied (any platform, Excel "Applied" rows)
SKIP_IF_COMPANY_ALREADY_APPLIED = True

# Search keywords — empty location = All India on Naukri
# DevOps-focused list; add React entries back if you want both roles.
SEARCH_QUERIES = [
    {"keyword": "DevOps Engineer", "location": ""},
    {"keyword": "DevOps", "location": ""},
    {"keyword": "Senior DevOps Engineer", "location": ""},
    {"keyword": "AWS DevOps Engineer", "location": ""},
    {"keyword": "Azure DevOps Engineer", "location": ""},
    {"keyword": "Cloud DevOps Engineer", "location": ""},
    {"keyword": "Kubernetes Engineer", "location": ""},
    {"keyword": "Site Reliability Engineer", "location": ""},
    {"keyword": "Platform Engineer", "location": ""},
    {"keyword": "Infrastructure Engineer", "location": ""},
    {"keyword": "CI/CD Engineer", "location": ""},
    {"keyword": "Linux DevOps Engineer", "location": ""},
]

# Only apply when job title matches at least one of these (case-insensitive)
TITLE_KEYWORDS = [
    "devops",
    "dev ops",
    "sre",
    "site reliability",
    "platform engineer",
    "cloud engineer",
    "infrastructure engineer",
    "kubernetes",
    "k8s",
    "docker",
    "aws",
    "azure",
    "gcp",
    "ci/cd",
    "cicd",
    "jenkins",
    "terraform",
    "ansible",
    "linux admin",
    "release engineer",
]

# Experience in years (Naukri search filter)
EXPERIENCE_YEARS = 2

# Max age of job postings in days (1 = today only; 30 = last month)
JOB_AGE_DAYS = 14

# Naukri returns up to 20 jobs per API page — raise pages to cover more listings.
# Local: fetch until a page is empty or MAX_PAGES_PER_QUERY is reached.
# Vercel: keep low to stay within the 5-minute serverless timeout.
MAX_PAGES_PER_QUERY = 3 if _IS_VERCEL else 10
PAGES_PER_QUERY = MAX_PAGES_PER_QUERY  # legacy alias used in logs

# Results per Naukri search API call (Naukri default is 20)
NAUKRI_RESULTS_PER_PAGE = 20

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
