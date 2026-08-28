# Tross Hiring Challenge — LinkedIn Profile API

A hosted REST API that accepts a LinkedIn profile URL and returns structured JSON profile data. Built by **reverse-engineering LinkedIn's internal Voyager REST API** and calling endpoints **directly over HTTP** — **no browser, no Playwright, no DOM scraping**.



---

## Important — LinkedIn credentials are required

**This API will not work without a LinkedIn session.**

LinkedIn does not expose a public API for arbitrary profile data. The internal **Voyager API** (`/voyager/api/...`) requires authenticated cookies (`li_at`, `JSESSIONID`) and a CSRF token.

| Setup | Result |
|-------|--------|
| **Cookies in `.env`** (`LINKEDIN_LI_AT`, `LINKEDIN_JSESSIONID`) | **Recommended** — no email/password needed |
| **Email + password in `.env`** | Optional fallback — HTTP login → cookies (often blocked by LinkedIn) |
| **No credentials** | `/health` → `CREDENTIALS_NOT_CONFIGURED`; `/profile` fails |
| **No login (public only)** | Very limited data — not sufficient for this challenge |

**You do not need both.** Cookies alone are enough. Username and password are optional and usually fail on automated/cloud login.

The challenge PDF states: _"You may use your own LinkedIn credentials in the backend."_

---

## Approach — browser-free reverse engineering

```
Client → Flask API → curl_cffi HTTP client → Voyager REST endpoints → Parser → JSON
                              ↑
                    cookies + CSRF (from HTTP login or .env)
```

1. **Discover endpoints** — LinkedIn's website calls `/voyager/api/identity/dash/profiles` with `memberIdentity` and `decorationId` params (found via DevTools → Network).
2. **Authenticate via HTTP** — `POST /uas/login-submit` with email/password, or use pre-saved session cookies.
3. **Call Voyager directly** — `GET` requests with `Cookie`, `csrf-token`, and `x-restli-protocol-version` headers.
4. **Parse** — Walk the `included` array in Voyager JSON and map to a clean response schema.

**No browser is used.** No Playwright, Chromium, or page navigation.

---

## Problems faced and how they were solved

| Problem | Solution |
|---------|----------|
| No public LinkedIn API | Reverse-engineered Voyager REST endpoints |
| Auth required | HTTP login or cookie-based session |
| CSRF token | Read `JSESSIONID` cookie → `csrf-token` header |
| `dateRange` vs `startDate` | Parser reads `dateRange.start` / `dateRange.end` |
| Image parser recursion | Fixed `_image_url()` infinite loop |
| Playwright threading issues | Removed browser entirely — pure `curl_cffi` HTTP |
| Deprecated `profileView` (410) | Use `identity/dash/profiles` with `decorationId` |
| Cloud secrets | Env vars in platform dashboard only — not in repo |

---

## Why credentials are in `.env` (not a separate config file)

| File | Purpose |
|------|---------|
| **`config.py`** | Reads settings from environment — no secrets in code |
| **`.env`** | Local secrets (gitignored) |
| **`.env.example`** | Template — safe to commit |
| **Cloud dashboard** | Railway/Render env vars for production |

Never commit `.env`, `session_data/`, or cookie files.

**For cloud deploy: set credentials only in the platform dashboard (Railway / Render / Fly.io). Do not put credentials in the GitHub repo.**

---

## API documentation

Base URL (local): `http://localhost:8000`

**Endpoints:** `GET /health`, `POST /profile` only.

### `GET /health`

**Healthy session:**

```json
{
  "status": "ok",
  "linkedin_session": "active",
  "credentials_configured": true,
  "auth_method": "http"
}
```

**Degraded (missing or invalid credentials):**

```json
{
  "status": "degraded",
  "linkedin_session": "inactive",
  "credentials_configured": false,
  "error": "LinkedIn credentials missing...",
  "code": "CREDENTIALS_NOT_CONFIGURED"
}
```

### `POST /profile`

**Headers:** `Content-Type: application/json`

**Body:**
```json
{
  "url": "https://www.linkedin.com/in/username"
}
```

**Success (200):**

```json
{
  "success": true,
  "source_url": "https://www.linkedin.com/in/username",
  "scraped_at": "2026-08-28T10:30:00Z",
  "profile": {
    "public_identifier": "username",
    "name": {
      "first": "Jane",
      "last": "Doe",
      "full": "Jane Doe"
    },
    "headline": "Software Engineer at Example Co",
    "location": {
      "full": "Bengaluru, Karnataka, India",
      "city": "Bengaluru",
      "country": "India"
    },
    "about": "Short bio text...",
    "profile_image_url": "https://media.licdn.com/...",
    "experience": [
      {
        "title": "Software Engineer",
        "company": "Example Co",
        "location": "Bengaluru, India",
        "description": "Role description...",
        "date_range": {
          "start": "01/2022",
          "end": null
        },
        "is_current": true
      }
    ],
    "education": [
      {
        "school": "Example University",
        "degree": "Bachelor of Technology",
        "field_of_study": "Computer Science",
        "date_range": {
          "start": "2018",
          "end": "2022"
        },
        "description": null
      }
    ],
    "skills": [
      {
        "name": "Python",
        "endorsement_count": 12
      }
    ],
    "certifications": [
      {
        "name": "AWS Certified Developer",
        "authority": "Amazon Web Services",
        "issue_date": "06/2023",
        "expiration_date": null,
        "url": "https://..."
      }
    ],
    "languages": [
      {
        "name": "English",
        "proficiency": "Native or bilingual proficiency"
      }
    ]
  },
  "metadata": {
    "completeness": "full",
    "warnings": []
  }
}
```

**Field notes:**
- `date_range.start` / `date_range.end` — `MM/YYYY` or `YYYY`; `end` is `null` for current roles.
- `metadata.completeness` — `"full"` or `"partial"` (partial when many sections are missing).
- `metadata.warnings` — list of missing sections, e.g. `"No skills available"`.
- Some fields may be `null` or empty arrays depending on profile privacy and Voyager data.

**Error (4xx/5xx):**

```json
{
  "success": false,
  "error": "Human-readable error message",
  "code": "INVALID_URL"
}
```

**Error codes:** `MISSING_URL`, `INVALID_URL`, `PROFILE_NOT_FOUND`, `CREDENTIALS_NOT_CONFIGURED`, `SESSION_EXPIRED`, `LOGIN_FAILED`, `LOGIN_VERIFICATION_REQUIRED`, `INTERNAL_ERROR`

---

## Local setup

```bash
git clone https://github.com/ramkrushnapatra/Tross-Hiring-challenge.git
cd Tross-Hiring-challenge
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # add credentials
python app.py
```

### Configure `.env` (pick one option)

**Option 1 — session cookies** (recommended; no email/password required):

1. Log in at [linkedin.com](https://www.linkedin.com) in Chrome/Edge.
2. Open DevTools (F12) → **Application** → **Cookies** → `https://www.linkedin.com`.
3. Copy **`li_at`** and **`JSESSIONID`** values into `.env`:

```env
LINKEDIN_LI_AT=your_li_at_cookie
LINKEDIN_JSESSIONID=your_jsessionid_cookie
```

**Option 2 — email + password** (optional; may be blocked by LinkedIn CAPTCHA):
```env
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=yourpassword
```

### Test

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/profile \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://www.linkedin.com/in/username\"}"
```

---

## Docker / cloud deployment

```bash
docker build -t linkedin-profile-api .
docker run -p 8000:8000 \
  -e LINKEDIN_LI_AT=your_li_at_cookie \
  -e LINKEDIN_JSESSIONID=your_jsessionid_cookie \
  linkedin-profile-api
```

### Railway / Render / Fly.io

1. Push repo to GitHub (no `.env`).
2. Connect repo; use Dockerfile or Python 3 build.
3. Set **only** `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` in the platform **Environment Variables** tab (email/password not required).
4. Deploy — platform provides HTTPS URL.

Lightweight image (~150MB) — no Chromium required.

---

## Project structure

```
├── app.py                    # Flask routes
├── config.py                 # Env config
├── scraper/
│   ├── auth/
│   │   └── http_session.py   # HTTP login + cookie jar (no browser)
│   ├── voyager/
│   │   ├── constants.py      # Endpoint URLs + decorationIds
│   │   └── client.py         # Direct Voyager HTTP calls
│   ├── parser/               # Voyager JSON → response schema
│   ├── utils/                # URL parsing
│   └── services/             # Orchestration
├── Dockerfile
└── requirements.txt
```

---

## Known limitations

1. **Credentials required** — Voyager returns 401 without a valid session.
2. **HTTP login may trigger CAPTCHA** — use cookie option (`LINKEDIN_LI_AT` / `LINKEDIN_JSESSIONID`) as fallback.
3. **Voyager API drift** — `decorationId` values can change; update `scraper/voyager/constants.py`.
4. **Rate limits** — Default 3s between requests; keep volume low.
5. **Partial profiles** — Private profiles may return incomplete data (`metadata.completeness: partial`).
6. **Some sections depend on decorationId** — skills/education availability varies by endpoint bundle.

---

## Security

- **Never commit** `.env`, `session_data/`, or cookie files — they are listed in `.gitignore`.
- **No secrets in source code** — credentials are read only from environment variables via `config.py`.
- Use **`.env.example`** as the template (empty placeholders); copy to `.env` locally.
- **Cloud:** set `LINKEDIN_EMAIL` / `LINKEDIN_PASSWORD` or cookie vars only in the platform dashboard.
- API callers send only a profile URL — not LinkedIn credentials.
- Rotate your LinkedIn password if credentials were ever shared or exposed.

### Before pushing to GitHub

```bash
git status          # .env and session_data/ must NOT appear
git check-ignore -v .env
```

If `.env` shows up in `git status`, do **not** push until it is gitignored.

---

## Reference

- Challenge: reverse-engineer LinkedIn APIs; hosted HTTPS API; credentials allowed in backend.
- [PhantomBuster LinkedIn Profile Scraper](https://phantombuster.com/automations/linkedin/5589386912058181/linkedin-profile-scraper) (session-based reference)
- Voyager API: `https://www.linkedin.com/voyager/api/`
