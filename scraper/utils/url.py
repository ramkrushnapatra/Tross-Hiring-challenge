from __future__ import annotations

import re
from urllib.parse import urlparse

LINKEDIN_PROFILE_PATTERN = re.compile(
  r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/([a-zA-Z0-9\-_%]+)/?",
  re.IGNORECASE,
)


def extract_public_identifier(profile_url: str) -> str | None:
  """Extract LinkedIn public identifier (vanity slug) from a profile URL."""
  url = profile_url.strip()
  if not url.startswith("http"):
    url = "https://" + url

  parsed = urlparse(url)
  path = parsed.path or ""

  match = LINKEDIN_PROFILE_PATTERN.search(url) or LINKEDIN_PROFILE_PATTERN.search(
    f"https://linkedin.com{path}"
  )
  if not match:
    return None

  identifier = match.group(1).strip("/")
  if not identifier or identifier.lower() in ("in", "pub"):
    return None
  return identifier


def normalize_profile_url(public_identifier: str) -> str:
  return f"https://www.linkedin.com/in/{public_identifier}/"
