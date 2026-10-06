"""H10: PDF ingestion: detection, text layer, outline headings, page ranges, OCR fallback + cache,
limits and failures. No model calls (a fake OCR reader) and no database (a fake cache)."""

import asyncio
import subprocess
from pathlib import Path

import pytest
from fpdf import FPDF
from sdlc_config import ConfigError, load_snapshot
from sdlc_ingest.chunker import chunk_pdf
from sdlc_ingest.files import PDF, TEXT, walk, walk_git
from sdlc_ingest.pdf import PdfDocument, PdfError, PdfPage, read_pdf

from tests.config.test_sources_config import edit_yaml
from tests.support.entra import TEST_ENV

REPO = Path(__file__).resolve().parents[2]
POLICY = REPO / "samples/sources/eng-standards/incident-policy.pdf"
SCAN = REPO / "samples/sources/platform-infra/docs/change-freeze-notice.pdf"


def run(coro):
    return asyncio.run(coro)


def text_pdf(pages: list[str], password: str | None = None) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    for text in pages:
        pdf.add_page()
        pdf.multi_cell(0, 6, text)
    if password:
        pdf.set_encryption(owner_password="owner", user_password=password)  # noqa: S106 (fixture)
    return bytes(pdf.output())


class FakeOcr:
    model = "fake-ocr"
    concurrency = 2

    def __init__(self, text: str = "CHANGE FREEZE from 20 December to 3 January"):
        self.text, self.calls = text, 0

    def read_page(self, page_pdf: bytes) -> str:
        assert page_pdf.startswith(b"%PDF-")  # one page, as a PDF of its own
        self.calls += 1
        return self.text


class FakeCacheConn:
    """Just enough of an async psycopg connection for cached_json/store_json."""

    def __init__(self):
        self.rows: dict[str, dict] = {}

    async def execute(self, sql, params=()):
        if sql.lstrip().startswith("SELECT"):
            value = self.rows.get(params[0])
            return _Cursor((value,) if value is not None else None)
        self.rows[params[0]] = params[1].obj  # Jsonb wrapper
        return _Cursor(None)


class _Cursor:
    def __init__(self, row):
        self.row = row

    async def fetchone(self):
        return self.row


# --- detection -----------------------------------------------------------------------------------


def test_walker_passes_pdfs_and_skips_other_binaries(tmp_path):
    (tmp_path / "a.pdf").write_bytes(text_pdf(["hello pdf world"]))
    (tmp_path / "renamed.bin").write_bytes(text_pdf(["detected by header"]))
    (tmp_path / "fake.pdf").write_bytes(b"\x89PNG not a pdf")
    (tmp_path / "notes.md").write_text("# notes")
    files = {f.path: f for f in walk(tmp_path, ("**/*",), ())}
    assert files["a.pdf"].media_type == PDF and files["a.pdf"].raw.startswith(b"%PDF-")
    assert files["a.pdf"].text == "" and files["a.pdf"].is_pdf
    assert files["renamed.bin"].is_pdf  # the header decides, not the extension
    assert "fake.pdf" not in files  # binary, not a PDF
    assert files["notes.md"].media_type == TEXT


def test_git_walker_reads_pdf_blobs(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "doc.pdf").write_bytes(text_pdf(["from git"]))
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(repo)]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "pdf"], check=True)
    _, files = walk_git(repo, "HEAD", ("**/*.pdf",), ())
    [file] = list(files)
    assert file.path == "doc.pdf" and file.is_pdf


# --- text layer, outline, chunks ------------------------------------------------------------------


def test_text_layer_and_outline_of_the_sample_policy():
    document = run(read_pdf(None, POLICY.read_bytes(), max_pages=50))
    assert [p.origin for p in document.pages] == ["text", "text", "text"]
    assert "status page within 30 minutes" in document.pages[1].text
    assert [(o.level, o.title, o.page) for o in document.outline][:3] == [
        (1, "1 Purpose and scope", 1),
        (1, "2 Severity levels", 1),
        (1, "3 Response", 2),
    ]


def test_chunks_follow_bookmarks_and_carry_pages():
    chunks = chunk_pdf(run(read_pdf(None, POLICY.read_bytes(), max_pages=50)))
    by_heading = {c.heading: c for c in chunks}
    escalation = by_heading["3 Response > 3.1 Escalation matrix"]
    assert (escalation.start_line, escalation.end_line) == (2, 2)  # page numbers
    assert "SEV1" in escalation.content and escalation.content.startswith("3 Response")
    assert "3 Response" not in by_heading  # title-only section merged into the next
    assert by_heading["2 Severity levels"].start_line == 1


def test_pages_without_outline_become_page_sections_and_windows_track_pages():
    long_page = "\n".join(f"line {i} " + "x" * 60 for i in range(80))
    raw = text_pdf(["short first page text here", long_page])
    document = run(read_pdf(None, raw, max_pages=50))
    chunks = chunk_pdf(document, max_tokens=200, overlap=20)
    assert chunks[0].heading == "page 1" and (chunks[0].start_line, chunks[0].end_line) == (1, 1)
    # the long text flows over several PDF pages: every chunk is headed by its own page
    assert all(c.heading == f"page {c.start_line}" and c.start_line == c.end_line for c in chunks)
    assert len(document.pages) >= 3 and len(chunks) > 3


def test_document_without_text_has_no_chunks():
    assert chunk_pdf(PdfDocument([PdfPage(1, "", "empty")])) == []


# --- OCR for text-less pages ----------------------------------------------------------------------


def test_scan_without_ocr_is_reported_not_read():
    document = run(read_pdf(None, SCAN.read_bytes(), max_pages=10, ocr=FakeOcr()))
    assert document.pages_without_text == 1 and document.ocr_calls == 0  # no conn: no OCR


def test_ocr_reads_text_less_pages_once_then_uses_the_cache():
    conn, ocr = FakeCacheConn(), FakeOcr()
    first = run(read_pdf(conn, SCAN.read_bytes(), max_pages=10, ocr=ocr))
    assert first.ocr_calls == 1 and first.pages[0].origin == "ocr"
    assert "CHANGE FREEZE" in first.pages[0].text and first.pages_without_text == 0
    [key] = conn.rows
    assert key.startswith("ocr:")
    again = run(read_pdf(conn, SCAN.read_bytes(), max_pages=10, ocr=ocr))
    assert again.ocr_calls == 0 and ocr.calls == 1 and again.pages[0].text == first.pages[0].text


def test_text_pages_never_go_to_ocr():
    ocr = FakeOcr()
    run(read_pdf(FakeCacheConn(), POLICY.read_bytes(), max_pages=10, ocr=ocr))
    assert ocr.calls == 0


# --- failures and limits --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (text_pdf(["secret"], password="pw"), "encrypted"),  # noqa: S106 (fixture)
        (b"%PDF-1.7\nthis is not a real pdf", "unreadable"),
        (text_pdf(["one", "two", "three"]), "exceeds max_pages 2"),
    ],
)
def test_bad_pdfs_raise_pdf_error(raw, message):
    with pytest.raises(PdfError, match=message):
        run(read_pdf(None, raw, max_pages=2))


# --- config ---------------------------------------------------------------------------------------


def test_pdf_settings_load(config_dir):
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    infra = snap.sources["platform-infra"]
    assert (infra.pdf_ocr, infra.pdf_max_mb, infra.pdf_max_pages) == ("gemini", 50.0, 500)
    assert snap.sources["eng-standards"].pdf_ocr == "none"
    assert snap.platform.ocr_model


@pytest.mark.parametrize(
    ("file", "mutate", "message"),
    [
        (
            "platform.yaml",
            lambda d: d["knowledge"].pop("ocr"),
            "platform.yaml has no knowledge.ocr",
        ),
        (
            "sources/platform-infra.yaml",
            lambda d: d["spec"]["ingest"]["pdf"].update(ocr="tesseract"),
            "pdf",
        ),
        (
            "sources/platform-infra.yaml",
            lambda d: d["spec"]["ingest"]["pdf"].update(password="x"),  # noqa: S106 (unknown key)
            "pdf",
        ),
    ],
)
def test_bad_pdf_config_fails(config_dir, file, mutate, message):
    edit_yaml(config_dir / file, mutate)
    with pytest.raises(ConfigError, match=message):
        load_snapshot(config_dir, "local", TEST_ENV)
