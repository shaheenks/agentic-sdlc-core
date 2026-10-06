"""Generate the sample PDFs in samples/sources (H10). Synthetic content, deterministic output.

    uv run python scripts/make_sample_pdfs.py

- eng-standards/incident-policy.pdf: text PDF with nested bookmarks (sections) and a table.
- platform-infra/docs/change-freeze-notice.pdf: one image-only page (a "scan" with no text
  layer), read only through model OCR (platform-infra sets spec.ingest.pdf.ocr: gemini).

Re-running produces byte-identical files (fixed creation date), so ingest does not see a change.
"""

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FIXED_DATE = datetime(2026, 10, 1, tzinfo=UTC)


def new_pdf(title: str) -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_creation_date(FIXED_DATE)
    pdf.set_title(title)
    pdf.set_author("agentic-sdlc samples")
    pdf.set_producer("agentic-sdlc samples")
    pdf.set_auto_page_break(auto=True, margin=15)
    return pdf


def heading(pdf: FPDF, text: str, level: int) -> None:
    pdf.start_section(text, level=level)  # adds the outline (bookmark) entry
    pdf.set_font("Helvetica", "B", 15 if level == 0 else 12)
    pdf.multi_cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def para(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def incident_policy() -> bytes:
    pdf = new_pdf("Incident response policy")
    pdf.add_page()
    heading(pdf, "1 Purpose and scope", 0)
    para(
        pdf,
        "This policy defines how engineering teams declare, run and close incidents for "
        "customer-facing and money-moving services. It complements the incident management "
        "standard and applies to every tier-1 service, including payments-api, ledger-service, "
        "processor-gateway and job-runner.",
    )
    heading(pdf, "2 Severity levels", 0)
    para(
        pdf,
        "SEV1: customer money is at risk or a tier-1 service is unavailable. SEV2: a tier-1 "
        "service is degraded or a tier-2 service is down. SEV3: minor impact with a workaround.",
    )

    pdf.add_page()
    heading(pdf, "3 Response", 0)
    heading(pdf, "3.1 Escalation matrix", 1)
    para(pdf, "Response times are measured from the first alert.")
    pdf.set_font("Helvetica", size=10)
    with pdf.table(col_widths=(25, 55, 55, 55)) as table:
        for row in (
            ("Severity", "Incident commander", "First status update", "Executive notice"),
            ("SEV1", "paged within 5 minutes", "status page within 30 minutes", "within 1 hour"),
            ("SEV2", "paged within 15 minutes", "status page within 2 hours", "next business day"),
            ("SEV3", "next business day", "not required", "not required"),
        ):
            cells = table.row()
            for value in row:
                cells.cell(value)
    pdf.ln(4)
    heading(pdf, "3.2 Customer communication", 1)
    para(
        pdf,
        "For SEV1 incidents that affect customer payments or refunds, the incident commander "
        "notifies affected merchants within 4 hours, using the template approved by the "
        "payments team lead. Refund corrections are announced only after finance has confirmed "
        "the totals.",
    )

    pdf.add_page()
    heading(pdf, "4 Closing an incident", 0)
    heading(pdf, "4.1 Postmortem", 1)
    para(
        pdf,
        "Every SEV1 and SEV2 incident gets a blameless postmortem within five business days. "
        "The postmortem names the owning squad, the timeline, the root cause and at most five "
        "actions, each with an owner and a due date.",
    )
    heading(pdf, "4.2 Action tracking", 1)
    para(
        pdf,
        "Postmortem actions are reviewed weekly by the owning team's lead until they are done. "
        "An action that is more than 30 days overdue is escalated to the platform team.",
    )
    return bytes(pdf.output())


def change_freeze_notice() -> bytes:
    """One page that is only an image: a 'scanned' memo with no text layer."""
    lines = [
        "PLATFORM TEAM - CHANGE FREEZE NOTICE",
        "",
        "From 20 December to 3 January no production deploys",
        "are allowed through the deploy pipeline.",
        "",
        "Exceptions: SEV1 fixes approved by the platform lead.",
        "job-runner restarts during the freeze need a second",
        "reviewer and must follow the job-runner restart runbook.",
    ]
    image = Image.new("L", (1240, 700), color=255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=34)
    for i, line in enumerate(lines):
        draw.text((60, 60 + i * 70), line, fill=0, font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    pdf = new_pdf("Change freeze notice (scan)")
    pdf.add_page()
    pdf.image(buffer, x=10, y=20, w=190)
    return bytes(pdf.output())


def main() -> None:
    targets = {
        ROOT / "samples/sources/eng-standards/incident-policy.pdf": incident_policy(),
        ROOT
        / "samples/sources/platform-infra/docs/change-freeze-notice.pdf": change_freeze_notice(),
    }
    for path, data in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT)} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
