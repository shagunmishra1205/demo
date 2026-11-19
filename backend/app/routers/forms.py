import pymupdf  # PyMuPDF
import json
import urllib.parse
import urllib.request
from pydantic import BaseModel, Field
from fastapi import APIRouter, File, HTTPException, UploadFile

from ..config import settings
from ..fetcher import FetchError, fetch_html
from ..parser import parse_text
from ..samples import SAMPLE_FORMS
from ..schemas import FormDef, ParseResponse, ParseTextRequest, ParseUrlRequest, ValidateRequest, ValidateResponse
from ..urlforms import extract_from_page
from ..validation import normalize

router = APIRouter(prefix="/api", tags=["forms"])


@router.get("/forms", response_model=list[FormDef])
def list_forms():
    return list(SAMPLE_FORMS.values())


@router.get("/forms/{form_id}", response_model=FormDef)
def get_form(form_id: str):
    form = SAMPLE_FORMS.get(form_id)
    if not form:
        raise HTTPException(404, "Form not found")
    return form


@router.post("/validate", response_model=ValidateResponse)
def validate_answer(req: ValidateRequest):
    valid, value, err = normalize(req.field, req.raw)
    return ValidateResponse(valid=valid, value=value, err=err)


def _response(fields, lang_hint: str) -> ParseResponse:
    title = {"en": "Your form", "hi": "आपका फॉर्म"}
    return ParseResponse(title=title, fields=fields, flagged=sum(1 for f in fields if f.flag))


@router.post("/parse/text", response_model=ParseResponse)
def parse_pasted_text(req: ParseTextRequest):
    fields = parse_text(req.text)
    if not fields:
        raise HTTPException(422, "No questions found in the text")
    return _response(fields, "en")


async def _read_upload(file: UploadFile) -> str:
    """Return the text of an uploaded .pdf or .txt file, or raise an HTTP error."""
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")

    name = (file.filename or "").lower()
    if name.endswith(".pdf") or file.content_type == "application/pdf":
        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                text = "\n".join(page.get_text() for page in doc)
        except Exception:
            raise HTTPException(422, "Could not read this PDF")
        if not text.strip():
            raise HTTPException(422, "This PDF has no readable text (it may be a scan)")
        return text
    if name.endswith(".txt") or (file.content_type or "").startswith("text/"):
        return data.decode("utf-8", errors="replace")
    raise HTTPException(415, "Upload a .pdf or .txt file")


@router.post("/extract/text")
async def extract_text(file: UploadFile = File(...)):
    """Plain text of an uploaded PDF/TXT. The frontend puts it in the paste box for review."""
    return {"text": (await _read_upload(file)).strip()}


@router.post("/parse/file", response_model=ParseResponse)
async def parse_uploaded_file(file: UploadFile = File(...)):
    fields = parse_text(await _read_upload(file))
    if not fields:
        raise HTTPException(422, "No questions found in the file")
    return _response(fields, "en")


@router.post("/parse/url", response_model=ParseResponse)
def parse_form_url(req: ParseUrlRequest):
    """Visit a public form link and read its questions. Only the link is received, never answers."""
    try:
        final_url, html = fetch_html(req.url.strip())
        source, title, fields = extract_from_page(final_url, html)
    except FetchError as e:
        raise HTTPException(e.status, detail={"code": e.code, "message": e.message})
    return ParseResponse(
        title={"en": title, "hi": title},
        fields=fields,
        flagged=sum(1 for f in fields if f.flag),
        source=source,
        source_url=final_url,
    )

class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    target: str = "hi"


@router.post("/translate")
def translate_text(req: TranslateRequest):
    """Translate a form question or option for spoken guidance."""
    target = "hi" if req.target.lower().startswith("hi") else "en"

    if target == "en":
        return {"translated": req.text}

    query = urllib.parse.urlencode({
        "client": "gtx",
        "sl": "auto",
        "tl": target,
        "dt": "t",
        "q": req.text
    })

    request = urllib.request.Request(
        f"https://translate.googleapis.com/translate_a/single?{query}",
        headers={"User-Agent": "Mozilla/5.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))

        translated = "".join(
            part[0] for part in payload[0] if part and part[0]
        ).strip()

        if not translated:
            raise ValueError("Empty translation")

        return {"translated": translated}

    except Exception as exc:
        raise HTTPException(
            502,
            "Question translation is temporarily unavailable. Please try again."
        ) from exc

