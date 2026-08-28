# Tross Hiring Challenge — LinkedIn Profile API

A hosted REST API that accepts a LinkedIn profile URL and returns structured JSON profile data. Built by **reverse-engineering LinkedIn's internal Voyager REST API** and calling endpoints **directly over HTTP** — **no browser, no Playwright, no DOM scraping**.



---

## Important — LinkedIn credentials are required

**This API will not work without a LinkedIn session.**

LinkedIn does not expose a public API for arbitrary profile data. The internal **Voyager API** (`/voyager/api/...`) requires authenticated cookies (`li_at`, `JSESSIONID`) and a CSRF token.

| Setup | Result |
|-------|--------|
| **Email + password in `.env`** | HTTP login → cookies → Voyager calls |
| **Cookies in `.env`** (`LINKEDIN_LI_AT`, `LINKEDIN_JSESSIONID`) | Skip login; use cookies directly |
| **No credentials** | `/health` → `CREDENTIALS_NOT_CONFIGURED`; `/profile` fails |
| **No login (public only)** | Very limited data — not sufficient for this challenge |

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

```json
{
  "status": "ok",
  "linkedin_session": "active",
  "credentials_configured": true,
  "auth_method": "http"
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

**Success (200):** Returns `success`, `source_url`, `scraped_at`, `profile` (name, headline, location, about, experience, education, skills, certifications, languages, profile image), and `metadata`.

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

**Option 1 — email + password:**
```env
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=yourpassword
```

**Option 2 — session cookies** (recommended if HTTP login hits CAPTCHA):

1. Log in at [linkedin.com](https://www.linkedin.com) in Chrome/Edge.
2. Open DevTools (F12) → **Application** → **Cookies** → `https://www.linkedin.com`.
3. Copy **`li_at`** and **`JSESSIONID`** values into `.env`:

```env
LINKEDIN_LI_AT=your_li_at_cookie
LINKEDIN_JSESSIONID=your_jsessionid_cookie
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
  -e LINKEDIN_EMAIL=your@email.com \
  -e LINKEDIN_PASSWORD=yourpassword \
  linkedin-profile-api
```

### Railway / Render / Fly.io

1. Push repo to GitHub (no `.env`).
2. Connect repo; use Dockerfile.
3. Set `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD` (or cookie vars) in **platform Variables** tab.
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
