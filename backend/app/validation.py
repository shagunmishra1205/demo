"""Python port of normalize() and helpers from the frontend's js/data.js.

Returns (valid, value, err). `err` is an i18n key the frontend already knows.
"""
import re
from datetime import date

from .schemas import FormField, Option

_DEV = "०१२३४५६७८९"
_MONTHS = ["january", "february", "march", "april", "may", "june",
           "july", "august", "september", "october", "november", "december"]


def to_ascii(s: str) -> str:
    return "".join(str(_DEV.index(c)) if c in _DEV else c for c in str(s))


def _parse_date(s: str) -> str | None:
    y = m = d = None
    if x := re.match(r"^(\d{1,2})[/\-.\s](\d{1,2})[/\-.\s](\d{4}|\d{2})$", s):
        d, m, y = int(x[1]), int(x[2]), int(x[3])
        if len(x[3]) == 2:
            y += 2000 if y < 30 else 1900
    elif x := re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s):
        y, m, d = int(x[1]), int(x[2]), int(x[3])
    elif x := re.match(r"^(\d{1,2})\s+([a-z]+)\s+(\d{4})$", s.lower()):
        d, y = int(x[1]), int(x[3])
        if x[2] not in _MONTHS:
            return None
        m = _MONTHS.index(x[2]) + 1
    else:
        return None
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def _match_option(options: list[Option], raw: str) -> Option | None:
    s = to_ascii(raw).strip().lower()
    digits = re.search(r"\d+", s)
    if digits and len(s) <= 12:
        n = int(digits.group()) - 1
        if 0 <= n < len(options):
            return options[n]
    for o in options:
        for x in (o.v, o.en, o.hi):
            y = str(x or "").lower()
            if y and (y == s or (len(y) > 3 and y in s)):
                return o
    return None


def normalize(field: FormField, raw: str | None) -> tuple[bool, str | None, str | None]:
    v = str(raw or "").strip()

    if field.type == "select":
        if not v:
            return (False, None, "errOption") if field.required else (True, "", None)
        hit = _match_option(field.options or [], v)
        return (True, hit.v, None) if hit else (False, None, "errOption")

    if not v:
        return (False, None, "errRequired") if field.required else (True, "", None)

    a = to_ascii(v)

    if field.type == "email":
        e = re.sub(r"\s+at\s+", "@", a, flags=re.I)
        e = re.sub(r"\s+dot\s+", ".", e, flags=re.I)
        e = re.sub(r"\s", "", e).lower()
        return (True, e, None) if re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", e) else (False, None, "errEmail")

    if field.type == "phone":
        d = re.sub(r"\D", "", a)
        if len(d) == 12 and d.startswith("91"):
            d = d[2:]
        if len(d) == 11 and d[0] == "0":
            d = d[1:]
        return (True, d, None) if re.fullmatch(r"[6-9]\d{9}", d) else (False, None, "errPhone")

    if field.type == "pin":
        d = re.sub(r"\D", "", a)
        return (True, d, None) if re.fullmatch(r"[1-9]\d{5}", d) else (False, None, "errPin")

    if field.type == "number":
        n = re.sub(r"[,\s]", "", a)
        return (True, n, None) if re.fullmatch(r"\d+(\.\d+)?", n) else (False, None, "errNumber")

    if field.type == "date":
        d = _parse_date(a.strip())
        return (True, d, None) if d else (False, None, "errDate")

    if field.type == "sensitive":
        s = re.sub(r"\s", "", a).upper()
        ok = re.fullmatch(r"\d{12}", s) or re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", s)
        return (True, s, None) if ok else (False, None, "errSensitive")

    return (True, v, None)


def mask_pii(text: str) -> str:
    text = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "XXXX XXXX XXXX", text)
    text = re.sub(r"\b[A-Z]{5}\d{4}[A-Z]\b", "XXXXX0000X", text)
    text = re.sub(r"\b[6-9]\d{9}\b", "XXXXXXXXXX", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email hidden]", text)
    return text
