(() => {
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim();
  const textOf = (el) => clean(el?.innerText || el?.textContent || '');
  const questionRoots = () => [...document.querySelectorAll('[role="listitem"]')]
    .filter((root) => visible(root) && root.querySelector('input,textarea,[role="textbox"],[role="radio"],[role="checkbox"],[role="listbox"],[role="combobox"]'));

  function scan() {
    const roots = questionRoots();
    const questions = roots.map((root, index) => {
      const heading = root.querySelector('.M7eMe,[role="heading"],legend');
      const label = clean(textOf(heading) || textOf(root).split('\n')[0]);
      const required = !!root.querySelector('[aria-label*="Required" i],.vnumgf') || root.getAttribute('aria-required') === 'true';
      const controls = [...root.querySelectorAll('input:not([type="hidden"]),textarea,[role="textbox"],[role="radio"],[role="checkbox"],[role="listbox"],[role="combobox"]')].filter(visible);
      let type = 'text';
      if (root.querySelector('[role="radio"]')) type = 'radio';
      else if (root.querySelector('[role="checkbox"]')) type = 'checkbox';
      else if (root.querySelector('[role="listbox"],[role="combobox"]')) type = 'select';
      else if (root.querySelector('input[type="date"],input[aria-label*="Month" i],input[aria-label*="Day" i],input[aria-label*="Year" i]')) type = 'date';
      else if (root.querySelector('textarea')) type = 'textarea';
      const options = [...root.querySelectorAll('[role="radio"],[role="checkbox"]')].map((el) => clean(el.getAttribute('aria-label') || textOf(el))).filter(Boolean);
      return { index, label: label || `Question ${index + 1}`, required, type, options };
    });
    return { title: clean(document.title) || 'Google Form', url: location.href, questions, total: questions.length };
  }

  function setNativeValue(el, value) {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(el, value); else el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  async function fillQuestion(index, value) {
    const root = questionRoots()[index];
    if (!root) return { ok: false, error: 'Question is no longer on this page. Refresh the question list.' };
    const text = String(value ?? '').trim();
    if (!text) return { ok: false, error: 'Answer is empty.' };
    if (root.querySelectorAll('[role="radiogroup"]').length > 1) return { ok: false, error: 'Grid questions must be completed manually.' };
    if (root.querySelector('input[type="file"]')) return { ok: false, error: 'File uploads must be completed manually on the original form.' };
    const radios = [...root.querySelectorAll('[role="radio"]')].filter(visible);
    const checks = [...root.querySelectorAll('[role="checkbox"]')].filter(visible);
    if (radios.length) {
      const match = radios.find((el) => textOf(el).toLowerCase() === text.toLowerCase() || (el.getAttribute('aria-label') || '').toLowerCase() === text.toLowerCase());
      if (!match) return { ok: false, error: 'That answer does not match one of the available options.' };
      match.click(); return { ok: true };
    }
    if (checks.length) {
      const wanted = text.split(/[,;\n]/).map((v) => v.trim().toLowerCase()).filter(Boolean);
      let matched = 0;
      checks.forEach((el) => { if (wanted.includes(textOf(el).toLowerCase())) { el.click(); matched++; } });
      return matched ? { ok: true } : { ok: false, error: 'No checkbox option matched that answer.' };
    }
    const monthInput = root.querySelector('input[aria-label*="Month" i]');
    const dayInput = root.querySelector('input[aria-label*="Day" i]');
    const yearInput = root.querySelector('input[aria-label*="Year" i]');
    if (monthInput && dayInput && yearInput) {
      let year, month, day;
      let match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
      if (match) [, year, month, day] = match;
      else if ((match = text.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})$/))) [, day, month, year] = match;
      if (!year) return { ok: false, error: 'Enter the date as DD/MM/YYYY or YYYY-MM-DD.' };
      setNativeValue(monthInput, String(Number(month)));
      setNativeValue(dayInput, String(Number(day)));
      setNativeValue(yearInput, String(year));
      return { ok: true };
    }
    const nativeDate = root.querySelector('input[type="date"]');
    if (nativeDate) {
      const normalized = /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : (() => {
        const m = text.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})$/);
        return m ? `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}` : '';
      })();
      if (!normalized) return { ok: false, error: 'Enter the date as DD/MM/YYYY or YYYY-MM-DD.' };
      setNativeValue(nativeDate, normalized); return { ok: true };
    }
    const nativeSelect = root.querySelector('select');
    if (nativeSelect) {
      const option = [...nativeSelect.options].find((o) => o.text.trim().toLowerCase() === text.toLowerCase() || o.value.toLowerCase() === text.toLowerCase());
      if (!option) return { ok: false, error: 'That answer is not one of the available options.' };
      nativeSelect.value = option.value; nativeSelect.dispatchEvent(new Event('change', { bubbles: true })); return { ok: true };
    }
    const googleSelect = root.querySelector('[role="listbox"],[role="combobox"]');
    if (googleSelect) {
      googleSelect.click();
      await new Promise((resolve) => setTimeout(resolve, 180));
      const option = [...document.querySelectorAll('[role="option"]')].find((o) => textOf(o).toLowerCase() === text.toLowerCase());
      if (!option) return { ok: false, error: 'That option could not be selected automatically. Choose it on the form manually.' };
      option.click(); return { ok: true };
    }
    const input = root.querySelector('textarea,input:not([type="hidden"]),[role="textbox"]');
    if (!input) return { ok: false, error: 'This question type needs manual completion.' };
    if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) setNativeValue(input, text);
    else { input.focus(); input.textContent = text; input.dispatchEvent(new InputEvent('input', { bubbles: true, data: text, inputType: 'insertText' })); }
    return { ok: true };
  }

  function clickButton(patterns) {
    const buttons = [...document.querySelectorAll('button,[role="button"]')].filter(visible);
    const button = buttons.find((b) => patterns.some((p) => p.test(textOf(b) || b.getAttribute('aria-label') || '')));
    if (!button) return { ok: false, error: 'The required button was not found on this page.' };
    button.click(); return { ok: true };
  }

  // Bridge requests from the AwaazForm page to this Google Forms iframe.
  window.addEventListener('message', async (event) => {
    if (event.source !== window.parent || !/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(event.origin)) return;
    const message = event.data;
    if (message?.channel !== 'AWAAZFORM_BRIDGE' || !message.requestId) return;
    let result = null;
    let error = null;
    try {
      if (message.type === 'SCAN') result = scan();
      else if (message.type === 'FILL') result = await fillQuestion(Number(message.index), message.value);
      else if (message.type === 'NEXT_SECTION') result = clickButton([/^next$/i, /^continue$/i, /next section/i]);
      else if (message.type === 'SUBMIT') result = clickButton([/^submit$/i, /submit form/i, /send/i]);
      else error = 'Unsupported assistant action.';
    } catch (e) { error = e?.message || 'The form could not be accessed.'; }
    window.parent.postMessage({ channel: 'AWAAZFORM_BRIDGE_RESULT', requestId: message.requestId, result, error }, event.origin);
  });

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === 'AWAAZ_SCAN') { sendResponse(scan()); return true; }
    if (message?.type === 'AWAAZ_FILL') { fillQuestion(Number(message.index), message.value).then(sendResponse); return true; }
    if (message?.type === 'AWAAZ_NEXT_SECTION') {
      sendResponse(clickButton([/^next$/i, /^continue$/i, /next section/i])); return true;
    }
    if (message?.type === 'AWAAZ_SUBMIT') {
      const result = clickButton([/^submit$/i, /submit form/i, /send/i]);
      if (result.ok) setTimeout(() => sendResponse({ ok: true, submitted: /response has been recorded|your response has been recorded|submitted/i.test(document.body.innerText) }), 500);
      else sendResponse(result);
      return true;
    }
  });
})();
