const API = 'http://127.0.0.1:8001/api';
const TOKEN_KEY = 'awaazform_token';
const $ = (id) => document.getElementById(id);
let tabId = null;
let formData = null;
let index = 0;
let profile = null;
let done = new Set();
let recognition = null;

async function api(path, options = {}) {
  const saved = await chrome.storage.local.get(TOKEN_KEY);
  const headers = { ...(options.headers || {}) };
  if (saved[TOKEN_KEY]) headers.Authorization = `Bearer ${saved[TOKEN_KEY]}`;
  if (options.body) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${API}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Unable to connect to AwaazForm.');
  return data;
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  tabId = tab?.id ?? null;
  return tab;
}

async function send(type, extra = {}) {
  await activeTab();
  if (!tabId) throw new Error('No active browser tab found.');
  try { return await chrome.tabs.sendMessage(tabId, { type, ...extra }); }
  catch { throw new Error('Open a Google Form tab, then refresh the form list.'); }
}

function matchProfile(label) {
  const text = (label || '').toLowerCase();
  if (/father|mother|guardian|parent|emergency|alternate|spouse|first name|last name|middle name/.test(text)) return '';
  const rules = [
    [/\b(full name|applicant name|name of applicant|your name|name)\b|नाम|पूरा नाम/, 'full_name'],
    [/\b(email|e-mail)\b|ईमेल/, 'email'],
    [/\b(phone|mobile|contact number)\b|मोबाइल|फोन/, 'mobile_number'],
    [/\b(date of birth|birth date|dob)\b|जन्म तिथि/, 'date_of_birth'],
    [/\b(address|residential address)\b|पता/, 'address'],
    [/\b(city|town)\b|शहर/, 'city'],
    [/\b(state)\b|राज्य/, 'state'],
    [/\b(pin code|pincode|postal code|zip code)\b|पिन कोड/, 'pin_code'],
  ];
  for (const [pattern, key] of rules) if (pattern.test(text) && profile?.[key]) return String(profile[key]);
  return '';
}

async function loadProfile() {
  profile = await api('/auth/me');
  $('authPanel').hidden = true;
  $('assistantPanel').hidden = false;
  $('userName').textContent = profile.full_name;
  $('userEmail').textContent = profile.email;
  await scanForm(true);
}

async function scanForm(autoFill = false) {
  $('connection').textContent = 'Reading form…';
  const data = await send('AWAAZ_SCAN');
  formData = data;
  done = new Set();
  $('formTitle').textContent = data.title || 'Google Form';
  $('formMeta').textContent = `${data.total} question(s) found · ${new URL(data.url).hostname}`;
  if (!data.questions.length) {
    $('questionText').textContent = 'No supported questions found on this page.';
    $('connection').textContent = 'No form detected';
    return;
  }
  if (autoFill && profile) {
    for (const question of data.questions) {
      const suggested = matchProfile(question.label);
      if (!suggested) continue;
      const result = await send('AWAAZ_FILL', { index: question.index, value: suggested });
      if (result?.ok) done.add(question.index);
    }
  }
  index = data.questions.findIndex((q) => !done.has(q.index));
  if (index < 0) index = data.questions.length;
  $('connection').textContent = 'Google Form connected';
  renderQuestion();
}

function renderQuestion() {
  if (!formData?.questions?.length) return;
  const question = formData.questions[index];
  if (!question) {
    $('questionText').textContent = 'All visible questions have been reviewed.';
    $('answer').value = '';
    $('progressFill').style.width = '100%';
    $('progressText').textContent = `${done.size} of ${formData.total} completed`;
    $('questionNumber').textContent = 'SECTION COMPLETE';
    $('questionRequired').textContent = 'Use Next section if the form has another page, or Submit form when you reach the final page.';
    $('submitForm').disabled = done.size < formData.total;
    return;
  }
  $('questionNumber').textContent = `QUESTION ${index + 1} OF ${formData.total}`;
  $('questionText').textContent = question.label;
  $('questionRequired').textContent = question.required ? 'Required question' : 'Optional question';
  $('answer').value = '';
  $('progressFill').style.width = `${(done.size / Math.max(1, formData.total)) * 100}%`;
  $('progressText').textContent = `${done.size} of ${formData.total} completed`;
  $('submitForm').disabled = done.size < formData.total;
  const box = $('optionsBox'); box.replaceChildren(); box.hidden = !question.options?.length;
  (question.options || []).forEach((option) => {
    const button = document.createElement('button');
    button.className = 'option'; button.type = 'button'; button.textContent = option;
    button.addEventListener('click', () => {
      box.querySelectorAll('.option').forEach((b) => b.classList.remove('selected'));
      button.classList.add('selected'); $('answer').value = option;
    });
    box.append(button);
  });
  $('actionMessage').textContent = done.size ? `${done.size} answer(s) filled, including matching profile details.` : '';
  speakQuestion();
}

function speakQuestion() {
  const question = formData?.questions?.[index];
  if (!question || !('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(question.label);
  utterance.lang = profile?.preferred_language === 'hi' ? 'hi-IN' : 'en-IN';
  speechSynthesis.speak(utterance);
}

function startSpeech() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { $('actionMessage').textContent = 'Voice input is not supported in this browser. You can type your answer.'; return; }
  if (recognition) recognition.abort();
  recognition = new SpeechRecognition();
  recognition.lang = profile?.preferred_language === 'hi' ? 'hi-IN' : 'en-IN';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  $('actionMessage').textContent = 'Listening…';
  recognition.onresult = (event) => { $('answer').value = event.results[0][0].transcript; $('actionMessage').textContent = 'Answer captured. Review it, then fill the form.'; };
  recognition.onerror = () => { $('actionMessage').textContent = 'Could not hear that. Please try again or type your answer.'; };
  recognition.start();
}

function moveToNextQuestion(question) {
  const next = formData.questions.findIndex((q) => q.index > question.index && !done.has(q.index));
  index = next < 0 ? formData.questions.length : next;
  renderQuestion();
}

async function fillAndNext() {
  const value = $('answer').value.trim();
  if (!value) { $('actionMessage').textContent = 'Please speak or type an answer first.'; return; }
  const question = formData.questions[index];
  const result = await send('AWAAZ_FILL', { index: question.index, value });
  if (!result?.ok) { $('actionMessage').textContent = result?.error || 'Could not fill this answer.'; return; }
  done.add(question.index);
  moveToNextQuestion(question);
}

async function nextSection() {
  const result = await send('AWAAZ_NEXT_SECTION');
  if (!result?.ok) { $('actionMessage').textContent = result?.error || 'No next section button found.'; return; }
  $('actionMessage').textContent = 'Moving to the next section…';
  await new Promise((resolve) => setTimeout(resolve, 1000));
  await scanForm(true);
}

async function submitForm() {
  if (done.size < (formData?.total || 0)) { $('actionMessage').textContent = 'Please complete or review all visible questions before submitting.'; return; }
  if (!confirm('Submit this Google Form now? Please make sure all answers are correct.')) return;
  const result = await send('AWAAZ_SUBMIT');
  $('actionMessage').textContent = result?.ok ? 'Submit button clicked. Check the form page for its confirmation message.' : (result?.error || 'Could not submit this form.');
}

$('loginForm').addEventListener('submit', async (event) => {
  event.preventDefault(); $('authError').textContent = '';
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    const result = await api('/auth/login', { method: 'POST', body: JSON.stringify(values) });
    await chrome.storage.local.set({ [TOKEN_KEY]: result.access_token });
    await loadProfile();
  } catch (error) { $('authError').textContent = error.message; }
});
$('refresh').addEventListener('click', () => scanForm(true).catch((e) => { $('actionMessage').textContent = e.message; }));
$('readQuestion').addEventListener('click', speakQuestion);
$('speakAnswer').addEventListener('click', startSpeech);
$('fillAnswer').addEventListener('click', () => fillAndNext().catch((e) => { $('actionMessage').textContent = e.message; }));
$('manualDone').addEventListener('click', () => { const q = formData?.questions?.[index]; if (!q) return; done.add(q.index); moveToNextQuestion(q); });
$('nextSection').addEventListener('click', () => nextSection().catch((e) => { $('actionMessage').textContent = e.message; }));
$('submitForm').addEventListener('click', () => submitForm().catch((e) => { $('actionMessage').textContent = e.message; }));
$('logout').addEventListener('click', async () => { await chrome.storage.local.remove(TOKEN_KEY); profile = null; $('assistantPanel').hidden = true; $('authPanel').hidden = false; });

(async function init() {
  try {
    await activeTab();
    const tab = await chrome.tabs.get(tabId);
    const allowed = /^https:\/\/(docs\.google\.com\/forms\/|forms\.gle\/)/.test(tab.url || '');
    if (!allowed) $('connection').textContent = 'Open a Google Form tab';
    const saved = await chrome.storage.local.get(TOKEN_KEY);
    if (saved[TOKEN_KEY]) {
      try { await loadProfile(); }
      catch { await chrome.storage.local.remove(TOKEN_KEY); $('authPanel').hidden = false; $('assistantPanel').hidden = true; }
    }
  } catch { $('connection').textContent = 'Open a Google Form tab'; }
})();
