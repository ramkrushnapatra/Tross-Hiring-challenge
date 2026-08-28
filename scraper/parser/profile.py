"""Parse LinkedIn Voyager normalized JSON into a structured profile dict."""

from __future__ import annotations

from typing import Any


def _get_type(item: dict[str, Any]) -> str:
  return item.get("$type", "") or item.get("type", "")


def _text_value(value: Any) -> str | None:
  if value is None:
    return None
  if isinstance(value, str):
    return value.strip() or None
  if isinstance(value, dict):
    return value.get("text") or value.get("accessibilityText")
  return str(value)


def _date_range(item: dict[str, Any]) -> dict[str, Any] | None:
  start = item.get("startDate")
  end = item.get("endDate")

  time_period = item.get("timePeriod")
  if isinstance(time_period, dict):
    start = start or time_period.get("startDate")
    end = end or time_period.get("endDate")

  date_range = item.get("dateRange")
  if isinstance(date_range, dict):
    start = start or date_range.get("start")
    end = end or date_range.get("end")

  if not start and not end:
    return None
  return {
    "start": _format_date(start),
    "end": _format_date(end),
  }


def _is_current_role(item: dict[str, Any]) -> bool:
  if item.get("endDate") is not None:
    return False

  time_period = item.get("timePeriod")
  if isinstance(time_period, dict) and time_period.get("endDate") is not None:
    return False

  date_range = item.get("dateRange")
  if isinstance(date_range, dict) and date_range.get("end") is not None:
    return False

  return bool(item.get("startDate") or item.get("timePeriod") or item.get("dateRange"))


def _format_date(date_obj: Any) -> str | None:
  if not date_obj or not isinstance(date_obj, dict):
    return None
  year = date_obj.get("year")
  month = date_obj.get("month")
  if not year:
    return None
  if month:
    return f"{month:02d}/{year}"
  return str(year)


def _image_url(item: dict[str, Any], depth: int = 0) -> str | None:
  if depth > 4:
    return None

  vector = item.get("vectorImage")
  if isinstance(vector, dict):
    root = vector.get("rootUrl")
    artifacts = vector.get("artifacts") or []
    if root and artifacts:
      largest = max(artifacts, key=lambda a: a.get("width", 0))
      path = largest.get("fileIdentifyingUrlPathSegment", "")
      if path:
        return f"{root}{path}"
    if vector.get("url"):
      return vector["url"]

  profile_picture = item.get("profilePicture")
  if isinstance(profile_picture, dict):
    ref = profile_picture.get("displayImageReference")
    if isinstance(ref, dict):
      nested = _image_url(ref, depth + 1)
      if nested:
        return nested

  display = item.get("displayImageReference")
  if isinstance(display, dict):
    nested_vector = display.get("vectorImage")
    if isinstance(nested_vector, dict):
      nested = _image_url({"vectorImage": nested_vector}, depth + 1)
      if nested:
        return nested

  return item.get("url") or item.get("imageUrl")


def _resolve_geo_name(geo_urn: str | None, index: dict[str, dict[str, Any]]) -> str | None:
  if not geo_urn:
    return None
  geo = index.get(geo_urn)
  if not geo:
    return None
  return geo.get("defaultLocalizedName") or _text_value(geo.get("defaultLocalizedNameWithoutCountryName"))


def _build_index(included: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
  index: dict[str, dict[str, Any]] = {}
  for item in included:
    urn = item.get("entityUrn") or item.get("*trackingId")
    if urn:
      index[urn] = item
    tracking = item.get("trackingUrn")
    if tracking:
      index[tracking] = item
  return index


def _resolve_ref(ref: Any, index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
  if isinstance(ref, dict):
    return ref
  if isinstance(ref, str) and ref in index:
    return index[ref]
  return None


def parse_voyager_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
  """Merge multiple Voyager JSON responses into one normalized profile."""
  all_included: list[dict[str, Any]] = []
  for payload in payloads:
    included = payload.get("included") or []
    all_included.extend(included)

  index = _build_index(all_included)
  profile_entity = _find_profile_entity(all_included)
  if not profile_entity:
    return {}

  public_id = profile_entity.get("publicIdentifier")
  first = profile_entity.get("firstName", "")
  last = profile_entity.get("lastName", "")
  full_name = profile_entity.get("fullName") or f"{first} {last}".strip()

  geo_urn = profile_entity.get("geoLocation", {}).get("*geo") or profile_entity.get("geoUrn")
  if isinstance(geo_urn, str):
    location = _resolve_geo_name(geo_urn, index)
  else:
    location = _text_value(profile_entity.get("locationName"))

  profile_image = _image_url(profile_entity)
  if not profile_image:
    picture = profile_entity.get("profilePicture") or profile_entity.get("picture")
    if isinstance(picture, dict):
      profile_image = _image_url(picture)

  return {
    "public_identifier": public_id,
    "name": {
      "first": first or None,
      "last": last or None,
      "full": full_name or None,
    },
    "headline": profile_entity.get("headline") or profile_entity.get("occupation"),
    "location": _parse_location(location, profile_entity, index),
    "about": profile_entity.get("summary") or profile_entity.get("about"),
    "profile_image_url": profile_image,
    "experience": _parse_experience(all_included, index),
    "education": _parse_education(all_included, index),
    "skills": _parse_skills(all_included),
    "certifications": _parse_certifications(all_included, index),
    "languages": _parse_languages(all_included, index),
  }


def _find_profile_entity(included: list[dict[str, Any]]) -> dict[str, Any] | None:
  for item in included:
    type_name = _get_type(item)
    if "identity.profile.Profile" in type_name and item.get("firstName"):
      return item
    if type_name.endswith("MiniProfile") and item.get("firstName"):
      return item
  for item in included:
    if item.get("firstName") and item.get("lastName"):
      return item
  return None


def _parse_location(
  location_text: str | None,
  profile: dict[str, Any],
  index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
  if not location_text:
    geo = profile.get("geoLocation")
    if isinstance(geo, dict):
      location_text = geo.get("geoPlaceName") or geo.get("postalCode")
  if not location_text:
    return None

  parts = [p.strip() for p in location_text.split(",")]
  city = parts[0] if parts else None
  country = parts[-1] if len(parts) > 1 else None
  return {"full": location_text, "city": city, "country": country}


def _parse_experience(
  included: list[dict[str, Any]],
  index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
  experiences: list[dict[str, Any]] = []
  seen: set[str] = set()

  for item in included:
    type_name = _get_type(item)
    if "Position" not in type_name or "PositionGroup" in type_name:
      continue
    if not item.get("title") and not item.get("companyName"):
      continue

    key = item.get("entityUrn") or f"{item.get('title')}-{item.get('companyName')}"
    if key in seen:
      continue
    seen.add(key)

    company = item.get("companyName")
    company_urn = item.get("*company") or item.get("companyUrn")
    if not company and company_urn:
      company_entity = index.get(company_urn)
      if company_entity:
        company = company_entity.get("name")

    experiences.append(
      {
        "title": item.get("title"),
        "company": company,
        "location": _text_value(item.get("locationName")),
        "description": item.get("description"),
        "date_range": _date_range(item),
        "is_current": _is_current_role(item),
      }
    )

  for item in included:
    type_name = _get_type(item)
    if "PositionGroup" not in type_name:
      continue
    company_name = item.get("companyName")
    company_urn = item.get("*company") or item.get("companyUrn")
    if not company_name and company_urn:
      company_entity = index.get(company_urn)
      if company_entity:
        company_name = company_entity.get("name")

    positions = item.get("profilePositionInPositionGroup", {}).get("*elements", [])
    if not positions and item.get("positions"):
      positions = item["positions"]

    for pos_ref in positions:
      pos = _resolve_ref(pos_ref, index) or (pos_ref if isinstance(pos_ref, dict) else None)
      if not pos:
        continue
      key = pos.get("entityUrn") or f"{pos.get('title')}-{company_name}"
      if key in seen:
        continue
      seen.add(key)
      experiences.append(
        {
          "title": pos.get("title"),
          "company": company_name or pos.get("companyName"),
          "location": _text_value(pos.get("locationName")),
          "description": pos.get("description"),
          "date_range": _date_range(pos),
          "is_current": _is_current_role(pos),
        }
      )

  return experiences


def _parse_education(
  included: list[dict[str, Any]],
  index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
  education: list[dict[str, Any]] = []
  seen: set[str] = set()

  for item in included:
    type_name = _get_type(item)
    if "Education" not in type_name:
      continue
    if not item.get("schoolName") and not item.get("degreeName"):
      continue

    key = item.get("entityUrn") or item.get("schoolName", "")
    if key in seen:
      continue
    seen.add(key)

    school_urn = item.get("*school") or item.get("schoolUrn")
    school = item.get("schoolName")
    if not school and school_urn:
      school_entity = index.get(school_urn)
      if school_entity:
        school = school_entity.get("name")

    education.append(
      {
        "school": school,
        "degree": item.get("degreeName") or item.get("degree"),
        "field_of_study": item.get("fieldOfStudy"),
        "date_range": _date_range(item),
        "description": item.get("description"),
      }
    )
  return education


def _parse_skills(included: list[dict[str, Any]]) -> list[dict[str, Any]]:
  skills: list[dict[str, Any]] = []
  seen: set[str] = set()

  for item in included:
    type_name = _get_type(item)
    if "Skill" not in type_name:
      continue
    name = item.get("name") or _text_value(item.get("title"))
    if not name or name in seen:
      continue
    seen.add(name)
    skills.append({"name": name, "endorsement_count": item.get("endorsementCount")})
  return skills


def _parse_certifications(
  included: list[dict[str, Any]],
  index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
  certs: list[dict[str, Any]] = []
  seen: set[str] = set()

  for item in included:
    type_name = _get_type(item)
    if "Certification" not in type_name:
      continue
    name = item.get("name") or item.get("title")
    if not name:
      continue
    key = item.get("entityUrn") or name
    if key in seen:
      continue
    seen.add(key)

    authority = item.get("authority") or item.get("companyName")
    authority_urn = item.get("*company") or item.get("companyUrn")
    if not authority and authority_urn:
      authority_entity = index.get(authority_urn)
      if authority_entity:
        authority = authority_entity.get("name")

    certs.append(
      {
        "name": name,
        "authority": authority,
        "issue_date": _format_date(item.get("issueDate") or item.get("timePeriod", {}).get("startDate")),
        "expiration_date": _format_date(
          item.get("expirationDate") or item.get("timePeriod", {}).get("endDate")
        ),
        "url": item.get("url"),
      }
    )
  return certs


def _parse_languages(
  included: list[dict[str, Any]],
  index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
  languages: list[dict[str, Any]] = []
  seen: set[str] = set()

  for item in included:
    type_name = _get_type(item)
    if "Language" not in type_name or "Locale" in type_name:
      continue
    name = item.get("name") or item.get("language")
    if not name or name in seen:
      continue
    seen.add(name)

    proficiency = item.get("proficiency")
    if isinstance(proficiency, str) and proficiency in index:
      proficiency = index[proficiency].get("name")

    languages.append(
      {
        "name": name,
        "proficiency": _text_value(proficiency) if proficiency else None,
      }
    )
  return languages
