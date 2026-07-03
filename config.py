import os
_IS_VERCEL = bool(os.getenv('VERCEL') or os.getenv('VERCEL_ENV'))

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')
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
ENABLE_NAUKRI = _env_bool('ENABLE_NAUKRI', True)
ENABLE_LINKEDIN = _env_bool('ENABLE_LINKEDIN', not _IS_VERCEL)
SKIP_IF_COMPANY_ALREADY_APPLIED = True
SEARCH_QUERIES = [{'keyword': 'React Developer', 'location': ''}, {'keyword': 'React.js Developer', 'location': ''}, {'keyword': 'Frontend React Developer', 'location': ''}, {'keyword': 'React Native Developer', 'location': ''}, {'keyword': 'DevOps Engineer', 'location': ''}, {'keyword': 'DevOps', 'location': ''}, {'keyword': 'AWS DevOps Engineer', 'location': ''}, {'keyword': 'Site Reliability Engineer', 'location': ''}]
TITLE_KEYWORDS = ['react', 'reactjs', 'react.js', 'react native', 'frontend', 'front-end', 'front end', 'ui engineer', 'ui developer', 'web developer', 'javascript', 'typescript', 'node', 'node.js', 'nodejs', 'full stack', 'fullstack', 'full-stack', 'forward deployed', 'forward-deployed', 'forward deployed engineer', 'fde', 'devops', 'dev ops', 'sre', 'site reliability', 'platform engineer', 'cloud engineer', 'infrastructure engineer', 'kubernetes', 'docker', 'aws', 'azure', 'gcp', 'ci/cd', 'jenkins', 'terraform']
EXPERIENCE_YEARS = 2
JOB_AGE_DAYS = 3
PAGES_PER_QUERY = 1 if _IS_VERCEL else 2
SEARCH_DELAY_SEC = 1.5
APPLY_DELAY_SEC = 3
EXCEL_FILE = 'job_applications.xlsx'
APPLIED_JOBS_CSV = 'applied_jobs.csv'
LINKEDIN_COOKIES_FILE = 'linkedin_cookies.json'
LINKEDIN_LOCATION = 'India'
LINKEDIN_MAX_JOBS_PER_QUERY = 15
LINKEDIN_SEARCH_QUERIES = ['React Developer', 'React.js Developer', 'Frontend React Developer', 'DevOps Engineer', 'DevOps', 'AWS DevOps Engineer', 'Site Reliability Engineer']
LINKEDIN_HEADLESS = False
USE_BRAVE_BROWSER = True
BRAVE_BINARY_PATH = ''
LINKEDIN_EASY_APPLY_MAX_STEPS = 25
USE_OPENROUTER_FOR_LINKEDIN = True
OPENROUTER_MODEL = 'openai/gpt-oss-120b:free'
APPLICANT_PROFILE = {'current_ctc_annual': 168000, 'expected_ctc_annual': 500000, 'exp_total': '2', 'current_location': 'Pune', 'willing_to_relocate': True, 'notice_days': 30, 'full_name': 'Nehal Ingole', 'portfolio_url': '', 'skills': ['react', 'javascript', 'typescript', 'redux', 'docker', 'kubernetes', 'aws', 'ci/cd', 'jenkins', 'terraform', 'linux', 'git']}

# ---------------------------------------------------------------------------
# Work at a Startup (Y Combinator) — browser-based apply with a tailored message
# ---------------------------------------------------------------------------
ENABLE_WORKATASTARTUP = _env_bool('ENABLE_WORKATASTARTUP', not _IS_VERCEL)
WORKATASTARTUP_COOKIES_FILE = os.getenv('WORKATASTARTUP_COOKIES_FILE', 'workatastartup_cookies.json')
WORKATASTARTUP_HEADLESS = _env_bool('WORKATASTARTUP_HEADLESS', False)
# Listing URL to scrape (compact list, newest first).
WORKATASTARTUP_COMPANIES_URL = os.getenv(
    'WORKATASTARTUP_COMPANIES_URL',
    'https://www.workatastartup.com/companies?demographic=any&hasEquity=any&hasSalary=any'
    '&industry=any&interviewProcess=any&jobType=any&layout=list-compact&sortBy=created_desc'
    '&tab=any&usVisaNotRequired=any',
)
# Max company cards to open per cycle (each may contain several roles).
WORKATASTARTUP_MAX_COMPANIES = int(os.getenv('WORKATASTARTUP_MAX_COMPANIES', '15'))
# Max applications to actually submit per cycle (safety cap on outbound messages).
WORKATASTARTUP_MAX_APPLIES = int(os.getenv('WORKATASTARTUP_MAX_APPLIES', '10'))
# Only apply to roles whose title matches TITLE_KEYWORDS (False = apply to any role).
WORKATASTARTUP_FILTER_BY_TITLE = _env_bool('WORKATASTARTUP_FILTER_BY_TITLE', True)
