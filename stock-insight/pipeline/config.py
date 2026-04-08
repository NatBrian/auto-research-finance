"""Configuration for stock report pipeline."""
import os
import urllib3
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# SSL verification (set to false for proxy environments)
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() == "true"

# Disable SSL warnings and verification if configured - MUST be done before any imports
if not SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Set environment variables BEFORE any imports
    os.environ['CURL_CA_BUNDLE'] = ''
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['SSL_CERT_FILE'] = ''

    # Patch requests
    import requests
    requests.packages.urllib3.disable_warnings()
    original_request = requests.Session.request
    def patched_request(self, method, url, **kwargs):
        kwargs.setdefault('verify', False)
        return original_request(self, method, url, **kwargs)
    requests.Session.request = patched_request

    # Patch curl_cffi BEFORE yfinance imports it
    try:
        from curl_cffi import requests as curl_requests
        # Create a custom session with verify=False
        original_curl_request = curl_requests.Session.request
        def patched_curl_request(self, method, url, **kwargs):
            kwargs.setdefault('verify', False)
            return original_curl_request(self, method, url, **kwargs)
        curl_requests.Session.request = patched_curl_request

        # Also patch the default session
        curl_requests.Session.verify = False
    except ImportError:
        pass

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATE_DIR = BASE_DIR / "template"
CACHE_DB = DATA_DIR / "cache.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Default settings
DEFAULT_SUFFIX = os.getenv("DEFAULT_SUFFIX", "JK")
DEFAULT_MODE = os.getenv("DEFAULT_MODE", "beginner")

# Cache TTLs (time-to-live)
CACHE_TTL = {
    "price": timedelta(minutes=15),
    "news": timedelta(hours=6),
    "financials": timedelta(days=7),
    "dividends": timedelta(days=7),
    "profile": timedelta(days=30),
    "analyst": timedelta(days=1),
    "ownership": timedelta(days=7),
}

# API Keys
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# API Quotas (free tier limits)
API_QUOTAS = {
    "twelvedata": {"daily": 700, "minute": 8},  # 800/day, ~10/min
    "finnhub": {"daily": 50000, "minute": 50},  # 60/min free tier
}

# Rate limiting
RATE_LIMIT = {
    "yfinance": {"calls_per_minute": 100, "backoff_base": 1, "backoff_max": 30},
}

# Metric thresholds
METRIC_THRESHOLDS = {
    "rsi_period": 14,
    "bollinger_period": 20,
    "sma_periods": [20, 50, 200],
    "min_price_rows": 14,
    "min_financial_periods": 4,  # For YoY calculations
}

# Report sections (in order)
REPORT_SECTIONS = [
    "overview",
    "valuation",
    "financials",
    "analyst",
    "dividends",
    "ownership",
    "news",
]

# Conditional sections (hide if data missing)
CONDITIONAL_SECTIONS = ["analyst", "dividends", "ownership", "news"]