"""Service layer — orchestrates HTTP session, Voyager client, and parser."""

from __future__ import annotations

import time

from config import CREDENTIALS_CONFIGURED
from scraper.auth.http_session import close_http_session, get_http_session
from scraper.exceptions import ScraperError
from scraper.parser.completeness import assess_completeness
from scraper.parser.profile import parse_voyager_payloads
from scraper.utils.url import extract_public_identifier, normalize_profile_url
from scraper.voyager.client import VoyagerClient

_voyager_client: VoyagerClient | None = None


def _get_voyager_client() -> VoyagerClient:
  global _voyager_client
  if _voyager_client is None:
    _voyager_client = VoyagerClient(get_http_session())
  return _voyager_client


class LinkedInProfileService:
  """Facade for scraping LinkedIn profiles via direct Voyager HTTP calls."""

  @staticmethod
  def scrape(profile_url: str) -> dict:
    public_id = extract_public_identifier(profile_url)
    if not public_id:
      raise ScraperError("Invalid LinkedIn profile URL", "INVALID_URL")

    normalized_url = normalize_profile_url(public_id)
    voyager = _get_voyager_client()
    payloads = voyager.fetch_profile_payloads(public_id)

    if not payloads:
      raise ScraperError("Profile not found or no data returned", "PROFILE_NOT_FOUND")

    profile = parse_voyager_payloads(payloads)
    if not profile or not profile.get("name", {}).get("full"):
      raise ScraperError("Profile not found or inaccessible", "PROFILE_NOT_FOUND")

    completeness, warnings = assess_completeness(profile)
    return {
      "success": True,
      "source_url": normalized_url,
      "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
      "profile": profile,
      "metadata": {
        "completeness": completeness,
        "warnings": warnings,
      },
    }

  @staticmethod
  def health() -> dict:
    if not CREDENTIALS_CONFIGURED:
      return {
        "status": "degraded",
        "linkedin_session": "inactive",
        "credentials_configured": False,
        "error": (
          "LinkedIn credentials missing. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD "
          "(or LINKEDIN_LI_AT and LINKEDIN_JSESSIONID) in .env, then restart."
        ),
        "code": "CREDENTIALS_NOT_CONFIGURED",
      }

    try:
      session = get_http_session()
      session.ensure_authenticated()
      return {
        "status": "ok",
        "linkedin_session": "active",
        "credentials_configured": True,
        "auth_method": "http",
      }
    except ScraperError as exc:
      return {
        "status": "degraded",
        "linkedin_session": "inactive",
        "credentials_configured": True,
        "error": str(exc),
        "code": exc.code,
      }
    except Exception as exc:
      return {
        "status": "error",
        "linkedin_session": "inactive",
        "credentials_configured": True,
        "error": str(exc),
      }

  @staticmethod
  def close() -> None:
    global _voyager_client
    close_http_session()
    _voyager_client = None
