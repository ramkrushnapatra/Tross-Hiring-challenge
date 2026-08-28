"""LinkedIn Voyager API client — direct HTTP, no browser."""

from __future__ import annotations

import json
import logging
from typing import Any

from scraper.auth.http_session import LinkedInHttpSession
from scraper.exceptions import ScraperError
from scraper.voyager.constants import (
  PROFILE_DECORATION,
  SKILLS_DECORATION,
  TOP_CARD_DECORATION,
  VOYAGER_BASE,
)

logger = logging.getLogger(__name__)


class VoyagerClient:
  """Fetches profile data by calling LinkedIn Voyager REST endpoints directly."""

  def __init__(self, http_session: LinkedInHttpSession) -> None:
    self._session = http_session

  def build_profile_api_urls(self, public_id: str) -> list[str]:
    return [
      (
        f"{VOYAGER_BASE}/identity/dash/profiles"
        f"?q=memberIdentity&memberIdentity={public_id}"
        f"&decorationId={PROFILE_DECORATION}"
      ),
      (
        f"{VOYAGER_BASE}/identity/dash/profiles"
        f"?q=memberIdentity&memberIdentity={public_id}"
        f"&decorationId={TOP_CARD_DECORATION}"
      ),
      (
        f"{VOYAGER_BASE}/identity/dash/profiles"
        f"?q=memberIdentity&memberIdentity={public_id}"
        f"&decorationId={SKILLS_DECORATION}"
      ),
    ]

  def fetch(self, url: str) -> dict[str, Any] | None:
    response = self._session.get(url)

    if response.status_code in (401, 403):
      self._session.mark_session_expired()
      raise ScraperError("LinkedIn session expired or unauthorized", "SESSION_EXPIRED")
    if response.status_code == 404:
      return None
    if response.status_code != 200:
      logger.warning("Voyager request failed: %s status=%s", url, response.status_code)
      return None

    try:
      return response.json()
    except json.JSONDecodeError:
      logger.warning("Invalid JSON from voyager: %s", url)
      return None

  def fetch_profile_payloads(self, public_id: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for url in self.build_profile_api_urls(public_id):
      data = self.fetch(url)
      if data:
        payloads.append(data)
    return payloads
