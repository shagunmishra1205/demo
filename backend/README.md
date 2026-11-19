# AwaazForm Backend

FastAPI + SQLite + SQLAlchemy + Pydantic. Handles answer validation, form parsing (pasted text, .txt, PDF) and optional progress saving.

## Run

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8001
```

Interactive docs: http://localhost:8001/docs

## Test

```bash
python -m pytest -q
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/forms` | List sample forms |
| GET | `/api/forms/{id}` | One sample form (`scholar`, `camp`) |
| POST | `/api/validate` | Body `{field, raw}` -> `{valid, value, err}` |
| POST | `/api/parse/text` | Body `{text}` -> fields (unclear ones flagged) |
| POST | `/api/parse/file` | Multipart `file` (.txt or .pdf) -> fields |
| POST | `/api/parse/url` | Body `{url}` -> the questions found on a public form link (Google Forms or ordinary HTML forms) |
| POST | `/api/extract/text` | Multipart `file` (.txt or .pdf) -> `{text}` (used by the frontend upload) |
| POST | `/api/sessions` | Save progress (optional, user-initiated) |
| GET | `/api/sessions/{id}` | Load saved progress |
| DELETE | `/api/sessions/{id}` | Delete saved progress |

## Privacy

- The account profile stores the basic details the user provides. Passwords are PBKDF2-HMAC-SHA256 hashed and never stored in plain text.
- Sensitive form answers (Aadhaar, PAN etc.) are not part of the basic profile and should not be added unless there is a clear user need.
- Saved progress expires after 24 hours (`SESSION_TTL_HOURS`).
- Audio is never received or stored by the backend; speech recognition runs in the browser.
- The backend never submits a form. The Chrome extension can click the original form's Submit button only after explicit user confirmation.

## Reading a form link

`POST /api/parse/url` visits a public https link and returns its questions in the same shape as `/api/parse/text`.

- **Google Forms** (including `forms.gle` short links): the parser attempts to read embedded page data. For live interaction and more reliable question detection, use the Chrome extension.
- **Ordinary HTML forms**: inputs, dropdowns, radio groups and text areas, with their labels.
- **Flagged, not guessed**: checkboxes, file uploads, grids and time fields are returned with `flag: true`.
- **Cannot read**: forms that need a sign-in, or pages that build their questions with JavaScript (for example Microsoft Forms). The API answers with a `code` (`needs_signin`, `no_questions`, `fetch_failed`, `blocked`, `too_large`, `not_html`) and the app asks the user to paste the questions instead.
- **Safety**: the server only visits public https addresses on port 443. Localhost, private networks and cloud metadata addresses are refused, redirects are re-checked at every step, and downloads are capped at 2 MB and 10 seconds.
- **Privacy**: only the link is received by this parser, never answers. Links are not stored or logged by the app.

### Filling the real form (Google Forms)

For live form filling, use the Chrome extension in the top-level `extension/` folder. It reads the visible question controls from the currently open Google Form, fills supported fields in the original page, and can move between sections. It runs beside the original page in Chrome's side panel. The user reviews answers and explicitly confirms before the extension clicks Submit. The extension does not send form answers to this backend.

The backend link parser remains a helper for public forms. Google can change its page format without notice, so the browser extension uses the rendered page as a second route when server-side parsing cannot read a link.

Google can change the data format of its forms without notice. If a Google Form stops being read, `extract_google_form` in `app/urlforms.py` is the place to look.

## Frontend connection

`js/api.js` in the frontend calls this server and falls back to on-device logic when it is off.
Used now: `/api/health`, `/api/parse/text`, `/api/parse/url`, `/api/extract/text`.
Not used by default: `/api/validate` (switch `SERVER_VALIDATION` in `js/api.js`) and `/api/sessions`,
because the app promises that answers stay on the device.

## Calling it directly

```js
const API = 'http://localhost:8001/api';

const res = await fetch(`${API}/validate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ field, raw: answerText }),
});
const { valid, value, err } = await res.json();
```

`err` is an i18n key the frontend already has (`errPhone`, `errDate`, ...).


## User accounts (new)

The API supports basic user registration, login, and profile management:

- `POST /api/auth/register` creates an account and returns a bearer access token.
- `POST /api/auth/login` signs in and returns a bearer access token.
- `GET /api/auth/me` returns the signed-in user's profile.
- `PATCH /api/auth/me` updates basic profile details.
- `POST /api/auth/logout` confirms logout; because access tokens are stateless, the client must discard its token.

Send the token in the `Authorization: Bearer <token>` header for protected endpoints. Passwords are hashed with PBKDF2-HMAC-SHA256 and are never returned by the API. Set a long, random `AUTH_SECRET` in the environment before deployment. Use HTTPS in production.
