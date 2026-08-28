"""Assess how complete a scraped profile response is."""

from __future__ import annotations

from typing import Any


def assess_completeness(profile: dict[str, Any]) -> tuple[str, list[str]]:
  warnings: list[str] = []
  required_fields = ["name", "headline"]
  optional_sections = [
    ("about", "about section"),
    ("experience", "experience"),
    ("education", "education"),
    ("skills", "skills"),
    ("certifications", "certifications"),
    ("languages", "languages"),
    ("profile_image_url", "profile image"),
  ]

  for field in required_fields:
    value = profile.get(field)
    if field == "name":
      if not value or not value.get("full"):
        warnings.append(f"Missing {field}")
    elif not value:
      warnings.append(f"Missing {field}")

  for key, label in optional_sections:
    value = profile.get(key)
    if not value:
      warnings.append(f"No {label} available")

  completeness = "full" if len(warnings) <= 2 else "partial"
  return completeness, warnings
