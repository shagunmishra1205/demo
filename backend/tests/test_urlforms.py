import json
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import httpx
import pytest
from fastapi.testclient import TestClient

from app import fetcher
from app.database import Base, engine
from app.main import app
from app.urlforms import extract_from_page


def google_page(items, title="Scholarship 2026"):
    data = [None, ["Fill this in", items, None, None, None, None, None, None, title], "/forms", title, "id"]
    return f"<html><script>var FB_PUBLIC_LOAD_DATA_ = {json.dumps(data)};</script></html>"


def text_item(i, label, entry, required=1, help_=None):
    return [i, label, help_, 0, [[entry, None, required]]]


GOOGLE = google_page([
    [1, "Welcome", "Intro text", 6],                                           # section header: skipped
    text_item(2, "What is your full name?", 111, 1, "As on certificate"),
    text_item(3, "Mobile number", 222),
    text_item(4, "Aadhaar number", 333, 0),
    [5, "Category", None, 2, [[444, [["General"], ["OBC"], ["SC"]], 1]]],
    [6, "Date of birth", None, 9, [[555, None, 1]]],
    [7, "Subjects", None, 4, [[666, [["Maths"], ["Science"]], 0]]],            # checkboxes: flagged
    [8, "Upload marksheet", None, 13, [[777, None, 1]]],                       # file: flagged
    [9, "Rate us", None, 5, [[888, [["1"], ["2"], ["3"]], 1]]],
])

HTML_FORM = """
<html><head><title>Health Camp Signup</title></head><body>
<form action="/x">
  <label for="n">Full name *</label><input id="n" name="fullname" required>
  <label>Email <input type="email" name="mail"></label>
  <label for="p">Phone</label><input id="p" type="tel" name="phone" required>
  <label for="b">Blood group</label>
  <select id="b" name="blood"><option value="">Select one</option><option>A+</option><option>B+</option></select>
  <fieldset><legend>Do you need transport?</legend>
    <label><input type="radio" name="transport" value="y"> Yes</label>
    <label><input type="radio" name="transport" value="n"> No</label></fieldset>
  <input type="checkbox" name="agree" id="agree"><label for="agree">I agree to the terms</label>
  <input type="hidden" name="csrf" value="abc"><input type="password" name="pw">
  <button type="submit">Send</button>
</form></body></html>
"""


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    monkeypatch.setattr(fetcher, "_resolve", lambda host, port: ["142.250.80.46"])  # a public address
    with TestClient(app) as c:
        yield c


def fake_web(monkeypatch, pages):
    """Make fetch_html's HTTP layer serve `pages` {url: (status, headers, body)}."""
    def handler(request: httpx.Request):
        status, headers, body = pages[str(request.url)]
        return httpx.Response(status, headers=headers, text=body)
    real = fetcher.fetch_html
    monkeypatch.setattr("app.routers.forms.fetch_html", lambda url: real(url, transport=httpx.MockTransport(handler)))


HTML_HEADERS = {"content-type": "text/html; charset=utf-8"}


def test_google_form_fields():
    source, title, fields = extract_from_page("https://docs.google.com/forms/d/e/x/viewform", GOOGLE)
    assert source == "google_forms" and title == "Scholarship 2026"
    assert [f.type for f in fields] == ["text", "phone", "sensitive", "select", "date", "select", "text", "select"]
    assert fields[0].hint == {"en": "As on certificate"} and fields[0].source_key == "entry.111"
    assert fields[2].required is False                     # sensitive is never forced
    assert [o.v for o in fields[3].options] == ["General", "OBC", "SC"]
    assert [f.flag for f in fields] == [False, False, False, False, False, True, True, False]
    assert "Welcome" not in [f.label["en"] for f in fields]
    # the file-upload question cannot be pre-filled, so it has no key; the rest do
    assert [f.source_key for f in fields] == [f"entry.{n}" for n in (111, 222, 333, 444, 555, 666)] + [None, "entry.888"]


def test_html_form_fields():
    source, title, fields = extract_from_page("https://example.org/f", HTML_FORM)
    assert source == "html" and title == "Health Camp Signup"
    labels = [f.label["en"] for f in fields]
    assert labels == ["Full name", "Email", "Phone", "Blood group", "Do you need transport?", "I agree to the terms"]
    assert [f.type for f in fields] == ["text", "email", "phone", "select", "select", "select"]
    assert [o.v for o in fields[3].options] == ["A+", "B+"]       # placeholder dropped
    assert [o.v for o in fields[4].options] == ["Yes", "No"]
    assert fields[0].required and not fields[1].required
    assert fields[5].flag                                          # lone checkbox flagged
    assert "csrf" not in str(fields) and "pw" not in [f.source_key for f in fields]


def test_signin_and_empty_pages():
    from app.fetcher import FetchError
    with pytest.raises(FetchError) as e:
        extract_from_page("https://accounts.google.com/ServiceLogin", "<html></html>")
    assert e.value.code == "needs_signin"
    with pytest.raises(FetchError) as e:
        extract_from_page("https://example.org", "<html><body><div id=root></div></body></html>")
    assert e.value.code == "no_questions"


def test_endpoint_google_and_redirect(client, monkeypatch):
    fake_web(monkeypatch, {
        "https://forms.gle/abc": (302, {"location": "https://docs.google.com/forms/d/e/x/viewform"}, ""),
        "https://docs.google.com/forms/d/e/x/viewform": (200, HTML_HEADERS, GOOGLE),
    })
    r = client.post("/api/parse/url", json={"url": "https://forms.gle/abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "google_forms" and len(body["fields"]) == 8 and body["flagged"] == 2
    assert body["title"]["en"] == "Scholarship 2026"
    assert body["source_url"] == "https://docs.google.com/forms/d/e/x/viewform"   # after the redirect


def test_endpoint_errors(client, monkeypatch):
    fake_web(monkeypatch, {
        "https://a.example/missing": (404, HTML_HEADERS, ""),
        "https://a.example/pdf": (200, {"content-type": "application/pdf"}, "x"),
        "https://a.example/empty": (200, HTML_HEADERS, "<html><body>hello</body></html>"),
    })
    code = lambda u: client.post("/api/parse/url", json={"url": u}).json()["detail"]["code"]
    assert code("https://a.example/missing") == "fetch_failed"
    assert code("https://a.example/pdf") == "not_html"
    assert code("https://a.example/empty") == "no_questions"


def test_too_large(client, monkeypatch):
    big = "x" * (fetcher.MAX_BYTES + 10)
    fake_web(monkeypatch, {"https://a.example/big": (200, HTML_HEADERS, big)})
    assert client.post("/api/parse/url", json={"url": "https://a.example/big"}).json()["detail"]["code"] == "too_large"


@pytest.mark.parametrize("url", [
    "http://docs.google.com/forms/x",          # not https
    "https://user:pw@docs.google.com/x",       # embedded password
    "https://docs.google.com:8443/x",          # odd port
    "ftp://example.org/x",
    "https:///nohost",
])
def test_rejects_unsafe_urls(client, url):
    r = client.post("/api/parse/url", json={"url": url})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "blocked"


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.9", "169.254.169.254",   # incl. cloud metadata
    "100.64.0.1", "0.0.0.0", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1",
])
def test_blocks_private_addresses(monkeypatch, ip):
    monkeypatch.setattr(fetcher, "_resolve", lambda h, p: [ip])
    with pytest.raises(fetcher.FetchError) as e:
        fetcher.assert_public_url("https://sneaky.example/form")
    assert e.value.code == "blocked"


def test_blocks_if_any_resolved_address_is_private(monkeypatch):
    monkeypatch.setattr(fetcher, "_resolve", lambda h, p: ["142.250.80.46", "10.0.0.1"])
    with pytest.raises(fetcher.FetchError):
        fetcher.assert_public_url("https://mixed.example/form")


def test_redirect_to_internal_address_is_blocked(client, monkeypatch):
    seen = {"https://public.example/": ["142.250.80.46"], "https://internal.example/": ["10.1.1.1"]}
    monkeypatch.setattr(fetcher, "_resolve", lambda h, p: seen[f"https://{h}/"])
    fake_web(monkeypatch, {
        "https://public.example/": (302, {"location": "https://internal.example/"}, ""),
        "https://internal.example/": (200, HTML_HEADERS, HTML_FORM),
    })
    r = client.post("/api/parse/url", json={"url": "https://public.example/"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "blocked"


def test_redirect_loop_stops(client, monkeypatch):
    fake_web(monkeypatch, {"https://loop.example/": (302, {"location": "https://loop.example/"}, "")})
    assert client.post("/api/parse/url", json={"url": "https://loop.example/"}).json()["detail"]["code"] == "fetch_failed"
