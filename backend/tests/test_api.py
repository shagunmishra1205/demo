import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.samples import SAMPLE_FORMS


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:
        yield c


def field(type_, required=True, options=None):
    return {"id": "x", "type": type_, "required": required, "label": {"en": "Q"}, "options": options}


def validate(client, type_, raw, **kw):
    return client.post("/api/validate", json={"field": field(type_, **kw), "raw": raw}).json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_sample_forms(client):
    r = client.get("/api/forms")
    assert r.status_code == 200 and len(r.json()) == 2
    assert client.get("/api/forms/scholar").json()["id"] == "scholar"
    assert client.get("/api/forms/nope").status_code == 404


def test_phone(client):
    assert validate(client, "phone", "+91 98765 43210")["value"] == "9876543210"
    assert validate(client, "phone", "९८७६५ ४३२१०")["value"] == "9876543210"
    assert validate(client, "phone", "12345")["err"] == "errPhone"


def test_date(client):
    assert validate(client, "date", "15 August 2008")["value"] == "2008-08-15"
    assert validate(client, "date", "15/08/2008")["value"] == "2008-08-15"
    assert validate(client, "date", "31/02/2008")["err"] == "errDate"


def test_pin_email_number(client):
    assert validate(client, "pin", "411001")["value"] == "411001"
    assert validate(client, "pin", "011001")["err"] == "errPin"
    assert validate(client, "email", "ravi at example dot com")["value"] == "ravi@example.com"
    assert validate(client, "number", "1,200")["value"] == "1200"


def test_required_and_optional(client):
    assert validate(client, "text", "")["err"] == "errRequired"
    assert validate(client, "text", "", required=False)["valid"] is True


def test_select_by_number_and_name(client):
    opts = [{"v": "OBC", "en": "OBC", "hi": "OBC"}, {"v": "SC", "en": "SC", "hi": "SC"}]
    assert validate(client, "select", "2", options=opts)["value"] == "SC"
    assert validate(client, "select", "obc", options=opts)["value"] == "OBC"
    assert validate(client, "select", "zzz", options=opts)["err"] == "errOption"


def test_parse_text(client):
    text = "1. What is your name?\n2. Mobile number\n3. Category options: General, OBC, SC\n4. Aadhaar number (optional)"
    r = client.post("/api/parse/text", json={"text": text}).json()
    types = [f["type"] for f in r["fields"]]
    assert types == ["text", "phone", "select", "sensitive"]
    assert r["fields"][3]["required"] is False


def test_parse_empty_text(client):
    assert client.post("/api/parse/text", json={"text": "   \n  "}).status_code == 422


def test_parse_txt_file(client):
    r = client.post("/api/parse/file", files={"file": ("q.txt", b"What is your name?\nEmail", "text/plain")})
    assert r.status_code == 200 and len(r.json()["fields"]) == 2


def test_parse_pdf_file(client):
    import pymupdf as fitz
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "What is your name?\nMobile number")
    r = client.post("/api/parse/file", files={"file": ("q.pdf", doc.tobytes(), "application/pdf")})
    assert r.status_code == 200 and len(r.json()["fields"]) == 2


def test_bad_upload_type(client):
    r = client.post("/api/parse/file", files={"file": ("a.exe", b"x", "application/octet-stream")})
    assert r.status_code == 415


def test_session_roundtrip_drops_sensitive(client):
    body = {"form": SAMPLE_FORMS["scholar"], "answers": {"name": "Asha", "aadhaar": "123412341234"}, "idx": 3, "lang": "hi"}
    created = client.post("/api/sessions", json=body)
    assert created.status_code == 201
    sid = created.json()["id"]
    got = client.get(f"/api/sessions/{sid}").json()
    assert got["answers"] == {"name": "Asha"}  # Aadhaar was never stored
    assert got["idx"] == 3 and got["lang"] == "hi"
    assert client.delete(f"/api/sessions/{sid}").status_code == 204
    assert client.get(f"/api/sessions/{sid}").status_code == 404


def test_extract_text_pdf_and_txt(client):
    import pymupdf as fitz
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "What is your name?")
    r = client.post("/api/extract/text", files={"file": ("q.pdf", doc.tobytes(), "application/pdf")})
    assert r.status_code == 200 and "What is your name?" in r.json()["text"]
    r = client.post("/api/extract/text", files={"file": ("q.txt", b"Email", "text/plain")})
    assert r.json()["text"] == "Email"
    assert client.post("/api/extract/text", files={"file": ("a.exe", b"x", "application/octet-stream")}).status_code == 415
