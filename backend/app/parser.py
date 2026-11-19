"""Turns pasted text or PDF text into form fields. Python port of parseText() in js/data.js.
Anything it cannot understand is flagged, never guessed."""
import re

from .schemas import FormField, Option


def guess_type(question: str) -> str:
    """Guess a field type from its label. Shared by the paste parser and the link reader."""
    if re.search(r"aadhaar|aadhar|आधार|\bpan\b|bank account|card number", question, re.I):
        return "sensitive"
    if re.search(r"date|dob|birth|जन्म|तिथि", question, re.I):
        return "date"
    if re.search(r"e-?mail|ईमेल", question, re.I):
        return "email"
    if re.search(r"phone|mobile|contact number|मोबाइल|फ़ोन|फोन", question, re.I):
        return "phone"
    if re.search(r"pin ?code|पिन", question, re.I):
        return "pin"
    if re.search(r"\b(age|amount|income|marks|quantity|how many|how old)\b", question, re.I):
        return "number"
    return "text"


def parse_text(text: str) -> list[FormField]:
    lines = []
    for line in re.split(r"\r?\n", text):
        line = re.sub(r"^\s*(?:\d+[.)]|[-•*])\s*", "", line).strip()
        if line:
            lines.append(line)

    fields: list[FormField] = []
    for i, line in enumerate(lines):
        question, options_raw = line, None
        om = re.match(r"^(.*?)\s*(?:options?|choices?|विकल्प)\s*[:：]\s*(.+)$", line, re.I)
        if om:
            question, options_raw = om.group(1) or "", om.group(2)

        lang = "hi" if re.search(r"[ऀ-ॿ]", question) else "en"
        optional = bool(re.search(r"\(optional\)|वैकल्पिक", question, re.I))
        label = re.sub(r"\(optional\)|\(वैकल्पिक\)", "", question, flags=re.I)
        label = re.sub(r"\?+\s*$", "?", label).strip()

        ftype = guess_type(question)

        options = None
        if options_raw:
            ftype = "select"
            options = [Option(v=s, en=s, hi=s) for s in (p.strip() for p in re.split(r"[,;/]", options_raw)) if s]

        letters = len(re.sub(r"[^A-Za-zऀ-ॿ]", "", label))
        flag = letters < 3 or (ftype == "select" and not options)

        fields.append(FormField(
            id=f"q{i + 1}",
            type=ftype,
            required=not optional and ftype != "sensitive",
            label={lang: label or line},
            options=options,
            flag=flag,
            lang=lang,
        ))
    return fields
