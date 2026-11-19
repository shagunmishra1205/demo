# AwaazForm Chrome Extension (Manifest V3)

The extension supports two workflows: (1) the AwaazForm website can embed a Google Form on the left and show the voice assistant on the right; (2) you can open a Google Form directly and use the Chrome side panel. The extension content script runs inside embedded Google Forms frames so the in-page assistant can read questions, accept spoken or typed answers, fill supported fields, move between sections, and click Submit only after you confirm.

## Requirements

- Google Chrome with the Side Panel API (Chrome 114 or newer recommended).
- AwaazForm backend running locally at `http://127.0.0.1:8001`.
- A registered AwaazForm account. Create it from the AwaazForm website first.

## Install for development

1. Start the backend (instructions are in `backend/README.md`).
2. Open Chrome and visit `chrome://extensions`.
3. Turn on **Developer mode**.
4. Choose **Load unpacked**.
5. Select this `extension` folder.
6. Keep the extension enabled. If it was already installed, click **Reload** on its card in `chrome://extensions` so the updated all-frames permission takes effect.
7. Open `http://localhost:8000` and paste a full `https://docs.google.com/forms/.../viewform` responder link into AwaazForm.
8. The Google Form opens inside the left panel and the AwaazForm voice assistant appears on the right.
9. If you prefer, you can still open a Google Form directly in a tab and use the extension icon to open the Chrome side panel.

## Use

1. The in-page assistant connects to the Google Form frame through the extension.
2. It reads the currently visible questions and speaks the current question aloud.
3. Type an answer or select **Speak answer** to dictate it. Review the captured answer.
4. Select **Fill & next** to put the answer into the matching Google Form question.
5. Use **Next section** for multi-page forms. The assistant scans the next section.
6. On the final section, review the answers and select **Submit form**. Confirm the browser prompt before submission.
7. The standalone Chrome side-panel workflow remains available for opening a Google Form directly in its own tab.

## Compatibility and safety limits

- This extension is specifically designed for Google Forms pages on `docs.google.com/forms` and their `forms.gle` short links. It does not promise support for every third-party form builder.
- It works with the questions and controls currently rendered in the active section. Forms that require sign-in, CAPTCHA, file uploads, grids, unusual date widgets, conditional logic, or custom controls may require manual completion.
- Google can change its page structure. If a question is not detected or filled correctly, refresh the form scan and complete that field manually.
- The extension does not bypass Google permissions, CAPTCHA, sign-in, or required validation.
- It never submits automatically. The user must click **Submit form** and confirm.
- Account data is requested from the local AwaazForm backend. The extension stores the access token in Chrome extension storage and the backend stores password hashes, not plain-text passwords.
- Before using with real personal data, configure a strong `AUTH_SECRET`, use HTTPS for a deployed backend, and review the privacy/security configuration.

## Backend URL

The development extension uses `http://127.0.0.1:8001/api`. If you deploy the backend elsewhere, update the `API` constant at the top of `sidepanel.js` and add the deployed origin to the extension's `host_permissions` in `manifest.json`.
