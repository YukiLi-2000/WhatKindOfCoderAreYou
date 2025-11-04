import pytest

from app import QUESTIONS, app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def _baseline_answers():
    return {question.field_name: "1" for question in QUESTIONS}


def test_result_page_is_english(client):
    answers = _baseline_answers()
    payload = {"lang": "en", **answers}
    response = client.post("/?lang=en", data=payload, follow_redirects=True)
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "Your Profile" in body
    assert "Start Over" in body
    assert "Download PDF" in body
    assert "你的组合" not in body
    assert "答题" not in body


def test_pdf_export_endpoint(client):
    answers = _baseline_answers()
    answers["lang"] = "en"
    response = client.post("/export/pdf", data=answers)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    content_disposition = response.headers.get("Content-Disposition", "")
    assert "DevSpectrum_" in content_disposition
    assert content_disposition.endswith(".pdf")
    assert len(response.data) > 1024


def test_pdf_export_includes_persona_sections(client, monkeypatch):
    captured = {}

    def fake_generate_pdf_report(**kwargs):
        captured["sections"] = kwargs.get("persona_sections")
        captured["tagline"] = kwargs.get("persona_tagline")
        captured["tagline_heading"] = kwargs.get("persona_tagline_heading")
        from io import BytesIO

        return BytesIO(b"stub")

    monkeypatch.setattr("app.generate_pdf_report", fake_generate_pdf_report)

    answers = _baseline_answers()
    answers["lang"] = "en"
    response = client.post("/export/pdf", data=answers)
    assert response.status_code == 200
    assert captured["sections"]
    assert captured["tagline"] is not None


def test_persona_content_matches_language(client):
    answers = _baseline_answers()

    en_response = client.post("/?lang=en", data={"lang": "en", **answers}, follow_redirects=True)
    assert en_response.status_code == 200
    en_body = en_response.get_data(as_text=True)
    assert "You are a fast-thinking problem solver" in en_body
    assert "你是那种爱挑战" not in en_body

    zh_response = client.post("/?lang=zh", data={"lang": "zh", **answers}, follow_redirects=True)
    assert zh_response.status_code == 200
    zh_body = zh_response.get_data(as_text=True)
    assert "你是那种爱挑战" in zh_body
