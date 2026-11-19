"""Reads the questions of an online form from its page HTML.

Two readers:
  1. Google Forms: the page carries all questions as JSON in FB_PUBLIC_LOAD_DATA_.
  2. Any ordinary HTML <form>: inputs, selects, textareas, radio groups.

Pages that build their form with JavaScript (Microsoft Forms, many portals) or need a
sign-in expose no questions to a plain download. Those are reported, never guessed.
Fields the app cannot answer one-by-one (checkboxes, file uploads, grids, time) are
included but flagged so the user is told to check them.
"""
import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .fetcher import FetchError
from .parser import guess_type
from .schemas import FormField, Option

MAX_FIELDS = 60
MARKER = "FB_PUBLIC_LOAD_DATA_"


def _clean(text: str | None) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\(required\)|\*+\s*$", "", text, flags=re.I).strip()
    return text


def _lang_of(text: str) -> str:
    return "hi" if re.search(r"[ऀ-ॿ]", text) else "en"


def _labels(text: str) -> dict[str, str]:
    return {_lang_of(text): text}


def _options(labels: list[str]) -> list[Option]:
    return [Option(v=x, en=x, hi=x) for x in labels if x]


# ---------------------------------------------------------------- Google Forms
# Item type numbers used by Google Forms in FB_PUBLIC_LOAD_DATA_.
_G_TEXT, _G_PARAGRAPH, _G_CHOICE, _G_DROPDOWN, _G_CHECKBOX = 0, 1, 2, 3, 4
_G_SCALE, _G_GRID, _G_DATE, _G_TIME, _G_FILE = 5, 7, 9, 10, 13
_G_NO_ANSWER = {6, 8, 11, 12}  # section title, page break, image, video


def _load_google_data(html: str):
    pos = html.find(MARKER)
    if pos < 0:
        return None
    start = html.find("[", pos)
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(html[start:])
    except ValueError:
        return None
    return data if isinstance(data, list) else None


def _get(seq, *path):
    for i in path:
        try:
            seq = seq[i]
        except (IndexError, KeyError, TypeError):
            return None
    return seq


def extract_google_form(html: str) -> tuple[str, list[FormField]] | None:
    data = _load_google_data(html)
    items = _get(data, 1, 1)
    if not isinstance(items, list):
        return None

    title = _clean(_get(data, 1, 8) or _get(data, 3) or "") or "Google Form"
    fields: list[FormField] = []

    for item in items:
        kind = _get(item, 3)
        label = _clean(_get(item, 1) if isinstance(_get(item, 1), str) else "")
        answers = _get(item, 4)
        if kind in _G_NO_ANSWER or not isinstance(answers, list) or not answers or not label:
            continue
        first = answers[0]
        entry = _get(first, 0)
        raw_options = _get(first, 1)
        required = _get(first, 2) == 1
        hint_text = _clean(_get(item, 2) if isinstance(_get(item, 2), str) else "")

        ftype, options, flag = "text", None, False
        if kind in (_G_CHOICE, _G_DROPDOWN, _G_SCALE):
            labels = [str(_get(o, 0) or "") for o in (raw_options or []) if isinstance(o, list)]
            options = _options(labels)
            ftype = "select"
            flag = not options  # "Other: ____" only, or unreadable
        elif kind == _G_CHECKBOX:
            ftype = "select"
            options = _options([str(_get(o, 0) or "") for o in (raw_options or []) if isinstance(o, list)])
            flag = True  # several answers allowed; the app takes one answer per question
        elif kind == _G_DATE:
            ftype = "date"
        elif kind in (_G_TEXT, _G_PARAGRAPH):
            ftype = guess_type(label)
        elif kind in (_G_GRID, _G_TIME, _G_FILE):
            flag = True  # cannot be answered one at a time yet
        else:
            flag = True  # a question type we do not know: flag it, do not guess

        # Only questions a pre-filled link can fill get a key. Grids have one entry per row,
        # and time/file questions are not supported, so those are left for the user to do.
        fillable = kind in (_G_TEXT, _G_PARAGRAPH, _G_CHOICE, _G_DROPDOWN, _G_CHECKBOX, _G_SCALE, _G_DATE)
        fields.append(FormField(
            id=f"q{len(fields) + 1}",
            type=ftype,
            required=required and ftype != "sensitive",
            label=_labels(label),
            hint=_labels(hint_text) if hint_text else None,
            options=options,
            flag=flag,
            lang=_lang_of(label),
            source_key=f"entry.{entry}" if entry is not None and fillable else None,
        ))
        if len(fields) >= MAX_FIELDS:
            break
    return title, fields


# ------------------------------------------------------------------ plain HTML
_SKIP_INPUT = {"hidden", "submit", "button", "reset", "image", "password"}
_PLACEHOLDER = re.compile(r"^(select|choose|pick|--)", re.I)


def _humanize(name: str) -> str:
    return re.sub(r"[_\-\[\]]+", " ", name).strip().capitalize()


def _label_for(soup: BeautifulSoup, el) -> str:
    if el.get("aria-label"):
        return _clean(el["aria-label"])
    if el.get("id"):
        lab = soup.find("label", attrs={"for": el["id"]})
        if lab:
            return _clean(lab.get_text(" "))
    parent = el.find_parent("label")
    if parent:
        copy = BeautifulSoup(str(parent), "html.parser")
        for tag in copy.find_all(["input", "select", "textarea"]):
            tag.decompose()
        text = _clean(copy.get_text(" "))
        if text:
            return text
    ref = el.get("aria-labelledby")
    if ref:
        found = soup.find(id=ref.split()[0])
        if found:
            return _clean(found.get_text(" "))
    for attr in ("placeholder", "title"):
        if el.get(attr):
            return _clean(el[attr])
    return _humanize(el.get("name") or el.get("id") or "")


def _group_label(soup: BeautifulSoup, first) -> str:
    fieldset = first.find_parent("fieldset")
    if fieldset and fieldset.find("legend"):
        return _clean(fieldset.find("legend").get_text(" "))
    return _humanize(first.get("name") or "")


def _is_required(el, label_raw: str = "") -> bool:
    return el.has_attr("required") or el.get("aria-required") == "true" or label_raw.rstrip().endswith("*")


def extract_html_form(html: str) -> tuple[str, list[FormField]] | None:
    soup = BeautifulSoup(html, "html.parser")
    page_title = _clean(soup.title.get_text(" ")) if soup.title else ""

    def controls(scope):
        return [c for c in scope.find_all(["input", "select", "textarea"])
                if c.name != "input" or (c.get("type") or "text").lower() not in _SKIP_INPUT]

    forms = soup.find_all("form") or [soup]
    scope = max(forms, key=lambda f: len(controls(f)))

    fields: list[FormField] = []
    seen_groups: set[tuple[str, str]] = set()

    def add(label, ftype, required, options=None, flag=False, key=None):
        if not label:
            label = "Question"
            flag = True
        fields.append(FormField(
            id=f"q{len(fields) + 1}", type=ftype, required=required and ftype != "sensitive",
            label=_labels(label), options=options, flag=flag, lang=_lang_of(label), source_key=key,
        ))

    for el in controls(scope):
        if len(fields) >= MAX_FIELDS:
            break
        if el.has_attr("disabled"):
            continue
        itype = (el.get("type") or "text").lower() if el.name == "input" else el.name
        key = el.get("name") or el.get("id")

        if itype in ("radio", "checkbox"):
            group = el.get("name") or el.get("id") or str(len(fields))
            if (itype, group) in seen_groups:
                continue
            seen_groups.add((itype, group))
            members = [m for m in scope.find_all("input", attrs={"type": itype, "name": el.get("name")})] if el.get("name") else [el]
            labels = [_label_for(soup, m) for m in members]
            if itype == "checkbox" and len(members) == 1:
                add(labels[0], "select", _is_required(el), _options(["Yes", "No"]), flag=True, key=key)
            else:
                add(_group_label(soup, el), "select", any(_is_required(m) for m in members),
                    _options(labels), flag=(itype == "checkbox" or not labels), key=key)
            continue

        label = _label_for(soup, el)
        required = _is_required(el, label)

        if itype == "select":
            labels = [_clean(o.get_text(" ")) for o in el.find_all("option")
                      if o.get("value", o.get_text()) != "" and not _PLACEHOLDER.match(_clean(o.get_text(" ")))]
            add(label, "select", required, _options(labels), flag=not labels, key=key)
        elif itype == "file":
            add(label, "text", required, flag=True, key=key)
        elif itype == "email":
            add(label, "email", required, key=key)
        elif itype == "tel":
            add(label, "phone", required, key=key)
        elif itype == "number":
            add(label, "number", required, key=key)
        elif itype == "date":
            add(label, "date", required, key=key)
        elif itype in ("datetime-local", "time", "month", "week", "range", "color"):
            add(label, "text", required, flag=True, key=key)
        else:
            add(label, guess_type(f"{label} {el.get('name') or ''}"), required, key=key)

    if not fields:
        return None
    return page_title or "Web form", fields


# ----------------------------------------------------------------------- entry
def extract_from_page(final_url: str, html: str) -> tuple[str, str, list[FormField]]:
    """Returns (source, title, fields) or raises FetchError."""
    host = (urlparse(final_url).hostname or "").lower()
    if host == "accounts.google.com":
        raise FetchError("needs_signin", "This form needs a sign-in, so it cannot be read.")

    google = extract_google_form(html)
    if google and google[1]:
        return "google_forms", google[0], google[1]

    generic = extract_html_form(html)
    if generic and generic[1]:
        return "html", generic[0], generic[1]

    raise FetchError(
        "no_questions",
        "No questions found on that page. It may need a sign-in or build its questions with JavaScript.",
    )
