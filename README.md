# AwaazForm

A multilingual, voice-guided form assistant (English and Hindi) for people who find forms hard to fill: low vision, limited dexterity, low literacy, or language barriers.

AwaazForm asks one question at a time, listens to the answer, reads it back, and fills the form after confirmation. Its Chrome extension can click Submit only after the user explicitly confirms.

Built for Katathon 6.0, Problem 402, Theme 4: Assistive Technology. Team CodeKweens.

## Features

- Guided one-question-at-a-time flow with progress
- Account registration, sign-in and saved basic profile
- Profile-based answer suggestions in the guided flow
- Embedded Google Forms workspace with the form on the left and the in-page voice assistant on the right (requires the Chrome extension)
- Chrome side-panel extension for live Google Forms reading and filling
- Voice answers (Web Speech API) and typed answers
- Read-back and explicit confirmation before every fill
- Numbered options for choice questions
- Validation for dates, mobile numbers, emails, PIN codes and sensitive IDs
- Paste questions, or upload a `.txt` or PDF file
- Review screen with edit-any-answer, save as PDF, or copy
- English and Hindi, switchable without losing answers
- Optional progress save on the device, deleted after 24 hours
- Accessibility: keyboard shortcuts, high contrast, large text, read-aloud toggle, ARIA live updates

## Run the complete application (Windows)

The standalone HTML can still be opened for the original offline guided demo. For account sign-in, saved profiles and the Chrome extension, run the backend and website locally:

1. Open a terminal in the extracted `Awaaz-main` folder.
2. Start the backend:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8001
```

3. Open a second terminal in the `Awaaz-main` root folder and run:

```powershell
python -m http.server 8000
```

4. Open http://localhost:8000 in Chrome or Edge and create an account.
5. Install the extension using the instructions in `extension/README.md`. If it is already installed, reload it from `chrome://extensions` after updating the project files.

For production, replace the development `AUTH_SECRET` in `backend/.env` with a long random secret and use HTTPS.

## Project layout

```
index.html                  App page (modular version)
css/styles.css              All styles
js/i18n.js                  English and Hindi strings
js/data.js                  Sample forms, parser, validation, masking
js/speech.js                Speech input and output wrappers
js/app.js                   Screens, flow, review, export, accessibility
awaazform-standalone.html   Single-file build of everything above
tools/build_standalone.py   Regenerates the standalone file
```

After editing the modular files, rebuild the standalone file:

```bash
python3 tools/build_standalone.py
```

## Known limits (MVP)

- Speech uses the browser Web Speech API, not the Whisper server in the spec.
- The Chrome extension targets Google Forms and best-effort supports visible text, radio, checkbox and dropdown questions. Google sign-in, CAPTCHA, file uploads, grids, conditional logic and unusual controls may require manual completion.
- Saved progress uses browser localStorage, not server-side encrypted sessions.
- PDF export uses the browser print dialog, so output is not a tagged PDF.
- Hindi voice depends on the computer having one installed.
- Marathi, the NVIDIA Nemotron step, and server TTS are not included yet.

## Team

Shagun (frontend), Meenakshi (prompts and LLM), Vidhi (backend), Shruti (pitch and spec), Harika (testing and QA).

## Accounts and profile autofill

The backend includes registration, login, profile retrieval and profile update endpoints under `/api/auth`. Basic profile fields include full name, email, mobile number, date of birth, address, city, state, PIN code and preferred language. Passwords are PBKDF2-SHA256 hashed. Set a unique random `AUTH_SECRET` in `backend/.env` before using real accounts.

The website Sign In button opens the account dialog. Create an account or sign in, then edit the saved profile from the same dialog. Matching profile details are suggested in the guided question flow.

## Google Forms Chrome extension

The `extension/` folder contains a Chrome Manifest V3 extension. It opens in Chrome's side panel beside the original Google Form, reads visible questions, supports text/radio/checkbox/dropdown controls where detected, offers speech input/output, autofills matching profile fields, and allows the user to confirm submission. Follow `extension/README.md` to load it unpacked in Chrome.

The extension is a best-effort integration with Google's rendered form interface, not a guarantee that every Google Form or every question type can be automated. CAPTCHA, authentication, file uploads, grids, conditional sections and unusual controls may require manual completion. Submission is always user-confirmed.
