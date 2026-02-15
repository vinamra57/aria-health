import logging
import re
from pathlib import Path

from pypdf import PdfReader

from app.config import GP_DOCUMENT_PATH

logger = logging.getLogger(__name__)


def _clean_line(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip()
    return cleaned


def _extract_pdf_text(path: str) -> str:
    """Extract raw text from a PDF using pypdf."""
    try:
        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return "\n".join(pages).strip()
    except Exception as exc:  # pragma: no cover - best effort extraction
        logger.warning("Failed to read GP document %s: %s", path, exc)
        return ""


def _extract_pdf_ocr(path: str) -> str:
    """Fallback OCR extraction using pdf2image + pytesseract if available."""
    try:
        from pdf2image import convert_from_path  # type: ignore
        import pytesseract  # type: ignore
    except Exception:
        logger.info("OCR dependencies not available; skipping OCR")
        return ""

    try:
        images = convert_from_path(path, dpi=200)
    except Exception as exc:
        logger.warning("Failed to render PDF for OCR: %s", exc)
        return ""

    text_chunks = []
    for image in images:
        try:
            text_chunks.append(pytesseract.image_to_string(image))
        except Exception as exc:
            logger.warning("OCR failed on a page: %s", exc)
    return "\n".join(text_chunks).strip()


def extract_text_from_pdf(path: str) -> str:
    """Extract raw text from a PDF; fallback to OCR if needed."""
    text = _extract_pdf_text(path)
    if text:
        return text
    return _extract_pdf_ocr(path)


def summarize_gp_document(raw_text: str) -> str:
    """Create a concise summary from extracted GP document text."""
    if not raw_text:
        return "No GP document content could be extracted."

    sections = {
        "Allergies": [],
        "Medications": [],
        "Conditions": [],
        "Procedures": [],
        "Labs": [],
        "Imaging": [],
        "Notes": [],
    }

    current_section = None
    lines = [_clean_line(line) for line in raw_text.splitlines()]
    for line in lines:
        if not line:
            continue

        lower = line.lower()
        if "allerg" in lower:
            current_section = "Allergies"
        elif "medication" in lower or "meds" in lower or "rx" in lower:
            current_section = "Medications"
        elif "condition" in lower or "problem list" in lower or "diagnos" in lower:
            current_section = "Conditions"
        elif "procedure" in lower or "surgery" in lower:
            current_section = "Procedures"
        elif "lab" in lower or "cbc" in lower or "bmp" in lower:
            current_section = "Labs"
        elif "imaging" in lower or "ct" in lower or "x-ray" in lower:
            current_section = "Imaging"
        elif "note" in lower or "assessment" in lower or "plan" in lower:
            current_section = "Notes"

        if ":" in line:
            label, value = [part.strip() for part in line.split(":", 1)]
            if label and value:
                matched = False
                for key in sections:
                    if key.lower() in label.lower():
                        sections[key].append(value)
                        matched = True
                        break
                if matched:
                    continue

        if current_section:
            sections[current_section].append(line)

    summary_lines = ["=== GP DOCUMENT EXTRACT ==="]
    for key, items in sections.items():
        cleaned_items = [item for item in items if item][:6]
        if cleaned_items:
            joined = "; ".join(cleaned_items)
            summary_lines.append(f"{key}: {joined}")

    if len(summary_lines) == 1:
        snippet = raw_text[:800].strip()
        summary_lines.append(snippet if snippet else "No structured fields detected.")

    summary_lines.append("=== END GP DOCUMENT ===")
    return "\n".join(summary_lines)


def load_gp_document_summary(path: str | None = None) -> tuple[str, str]:
    """Load GP document text and produce a summary."""
    doc_path = Path(path or GP_DOCUMENT_PATH)
    if not doc_path.exists():
        logger.warning("GP document not found at %s", doc_path)
        return "", "GP document not found."

    raw_text = extract_text_from_pdf(str(doc_path))
    summary = summarize_gp_document(raw_text)
    return raw_text, summary
