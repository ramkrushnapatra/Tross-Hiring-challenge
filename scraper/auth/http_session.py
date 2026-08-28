"""LinkedIn HTTP session — login and cookie management without a browser."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any

from curl_cffi import requests as curl_requests

from config import (
  CREDENTIALS_CONFIGURED,
  LINKEDIN_EMAIL,
  LINKEDIN_JSESSIONID,
  LINKEDIN_LI_AT,
  LINKEDIN_PASSWORD,
  SCRAPER_MIN_INTERVAL_SECONDS,
  SESSION_DIR,
)
from scraper.exceptions import ScraperError

logger = logging.getLogger(__name__)

LOGIN_CSRF_PATTERNS = (
  re.compile(r'data-csrf="([^"]+)"'),
  re.compile(r'name="loginCsrfParam"\s+value="([^"]+)"'),
  re.compile(r'"loginCsrfParam"\s*:\s*"([^"]+)"'),
  re.compile(r"loginCsrfParam&quot;:&quot;([^&]+)&quot;"),
)

COOKIE_AUTH_HELP = (
  "LinkedIn blocked automated login. Log in at linkedin.com in your browser, "
  "open DevTools → Application → Cookies → linkedin.com, copy "
  "li_at and JSESSIONID into .env as LINKEDIN_LI_AT and LINKEDIN_JSESSIONID, "
  "then restart the server."
)


class LinkedInHttpSession:
  """Maintains an authenticated HTTP session for direct Voyager API calls."""

  def __init__(self) -> None:
    self._lock = threading.Lock()
    self._last_request_time = 0.0
    self._authenticated = False
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    self._cookie_path = SESSION_DIR / "cookies.json"
    self._client = curl_requests.Session(impersonate="chrome120")
    self._load_cookies()
    self._bootstrap_cookie_auth()

  def _load_cookies(self) -> None:
    if not self._cookie_path.exists():
      return
    try:
      data = json.loads(self._cookie_path.read_text(encoding="utf-8"))
      for name, value in data.items():
        self._client.cookies.set(name, value, domain=".linkedin.com")
    except (json.JSONDecodeError, OSError) as exc:
      logger.warning("Could not load saved cookies: %s", exc)

  def _save_cookies(self) -> None:
    cookies = dict(self._client.cookies)
    self._cookie_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")

  def _bootstrap_cookie_auth(self) -> None:
    if LINKEDIN_LI_AT:
      self._client.cookies.set("li_at", LINKEDIN_LI_AT, domain=".linkedin.com")
    if LINKEDIN_JSESSIONID:
      self._client.cookies.set("JSESSIONID", LINKEDIN_JSESSIONID, domain=".linkedin.com")

  def _extract_login_csrf(self, html: str) -> str | None:
    for pattern in LOGIN_CSRF_PATTERNS:
      match = pattern.search(html)
      if match:
        return match.group(1)
    jsession = self._client.cookies.get("JSESSIONID")
    if jsession:
      return jsession.strip('"')
    return None

  def _has_li_at(self) -> bool:
    return bool(self._client.cookies.get("li_at"))

  def ensure_authenticated(self) -> None:
    if self._authenticated and self._has_li_at():
      return

    with self._lock:
      if self._authenticated and self._has_li_at():
        return

      if self._has_li_at() and self._validate_session():
        self._authenticated = True
        return

      if not CREDENTIALS_CONFIGURED:
        raise ScraperError(
          "LinkedIn credentials not configured. Set LINKEDIN_EMAIL and "
          "LINKEDIN_PASSWORD (or LINKEDIN_LI_AT and LINKEDIN_JSESSIONID) in .env.",
          "CREDENTIALS_NOT_CONFIGURED",
        )

      if LINKEDIN_LI_AT and LINKEDIN_JSESSIONID:
        raise ScraperError(
          "LinkedIn session cookies are invalid or expired. "
          "Refresh LINKEDIN_LI_AT and LINKEDIN_JSESSIONID in .env.",
          "SESSION_EXPIRED",
        )

      if LINKEDIN_EMAIL and LINKEDIN_PASSWORD:
        self._login_with_password()
        return

      raise ScraperError(COOKIE_AUTH_HELP, "SESSION_EXPIRED")

  def _validate_session(self) -> bool:
    if not self._has_li_at() or not self._client.cookies.get("JSESSIONID"):
      return False
    try:
      response = self._client.get(
        "https://www.linkedin.com/voyager/api/me",
        headers=self.api_headers(),
        timeout=60,
      )
      return response.status_code == 200
    except Exception:
      return False

  def _login_with_password(self) -> None:
    logger.info("Logging into LinkedIn via HTTP...")
    login_page = self._client.get("https://www.linkedin.com/login", timeout=60)
    if login_page.status_code != 200:
      raise ScraperError("Could not load LinkedIn login page", "LOGIN_FAILED")

    csrf = self._extract_login_csrf(login_page.text)
    if not csrf:
      raise ScraperError(
        f"Could not extract login CSRF token. {COOKIE_AUTH_HELP}",
        "LOGIN_FAILED",
      )

    jsession = (self._client.cookies.get("JSESSIONID") or "").strip('"')
    response = self._client.post(
      "https://www.linkedin.com/uas/login-submit",
      data={
        "session_key": LINKEDIN_EMAIL,
        "session_password": LINKEDIN_PASSWORD,
        "loginCsrfParam": csrf,
      },
      headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.linkedin.com/login",
        "Origin": "https://www.linkedin.com",
        "csrf-token": jsession or csrf,
      },
      timeout=60,
    )

    final_url = str(response.url).lower()
    if "unexpected_error" in final_url or ("checkpoint" in final_url and not self._has_li_at()):
      raise ScraperError(COOKIE_AUTH_HELP, "LOGIN_VERIFICATION_REQUIRED")

    if "login" in final_url and not self._has_li_at():
      raise ScraperError(
        f"LinkedIn login failed. Check email/password. {COOKIE_AUTH_HELP}",
        "LOGIN_FAILED",
      )

    if not self._has_li_at():
      raise ScraperError(
        f"LinkedIn login did not return a session cookie. {COOKIE_AUTH_HELP}",
        "LOGIN_FAILED",
      )

    self._authenticated = True
    self._save_cookies()
    logger.info("LinkedIn HTTP login successful")

  def get_csrf_token(self) -> str:
    jsession = self._client.cookies.get("JSESSIONID")
    if not jsession:
      raise ScraperError("CSRF token (JSESSIONID) not found", "SESSION_ERROR")
    return jsession.strip('"')

  def api_headers(self) -> dict[str, str]:
    return {
      "csrf-token": self.get_csrf_token(),
      "x-restli-protocol-version": "2.0.0",
      "x-li-lang": "en_US",
      "accept": "application/vnd.linkedin.normalized+json+2.1",
      "accept-language": "en-US,en;q=0.9",
      "referer": "https://www.linkedin.com/",
    }

  def throttle(self) -> None:
    elapsed = time.time() - self._last_request_time
    if elapsed < SCRAPER_MIN_INTERVAL_SECONDS:
      time.sleep(SCRAPER_MIN_INTERVAL_SECONDS - elapsed)
    self._last_request_time = time.time()

  def get(self, url: str) -> Any:
    self.ensure_authenticated()
    self.throttle()
    return self._client.get(url, headers=self.api_headers(), timeout=60)

  def mark_session_expired(self) -> None:
    self._authenticated = False

  def close(self) -> None:
    self._client.close()


_session: LinkedInHttpSession | None = None
_session_lock = threading.Lock()


def get_http_session() -> LinkedInHttpSession:
  global _session
  with _session_lock:
    if _session is None:
      _session = LinkedInHttpSession()
    return _session


def close_http_session() -> None:
  global _session
  with _session_lock:
    if _session:
      _session.close()
      _session = None
