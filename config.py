import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "session_data"

load_dotenv(BASE_DIR / ".env")

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "").strip()
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "").strip()
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT", "").strip()
LINKEDIN_JSESSIONID = os.getenv("LINKEDIN_JSESSIONID", "").strip()

PORT = int(os.getenv("PORT", "8000"))
SCRAPER_MIN_INTERVAL_SECONDS = float(os.getenv("SCRAPER_MIN_INTERVAL_SECONDS", "3"))
GUNICORN_TIMEOUT = int(os.getenv("GUNICORN_TIMEOUT", "120"))

CREDENTIALS_CONFIGURED = bool(
  (LINKEDIN_EMAIL and LINKEDIN_PASSWORD)
  or (LINKEDIN_LI_AT and LINKEDIN_JSESSIONID)
)
