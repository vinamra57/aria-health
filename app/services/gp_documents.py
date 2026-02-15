import logging
import re
from pathlib import Path

from pypdf import PdfReader

from app.config import GP_DOCUMENT_PATH, GP_DOCUMENT_PATIENT_NAME

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normalize for comparison: lowercase, collapse spaces."""
    if not name:
        return ""
    return " ".join(name.lower().split())


def _clean_line(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip()
    return cleaned


def extract_text_from_pdf(path: str) -> str:
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
    """Load GP document text and produce a summary (no patient check)."""
    doc_path = Path(path or GP_DOCUMENT_PATH)
    if not doc_path.exists():
        logger.warning("GP document not found at %s", doc_path)
        return "", "GP document not found."

    raw_text = extract_text_from_pdf(str(doc_path))
    summary = summarize_gp_document(raw_text)
    return raw_text, summary


def load_gp_document_for_patient(patient_name: str, path: str | None = None) -> tuple[str, str]:
    """Load GP document only if patient_name matches GP_DOCUMENT_PATIENT_NAME.

    Returns (full_text, summary) if match; else ("", "No data found from the GP.").
    """
    allowed = (GP_DOCUMENT_PATIENT_NAME or "").strip()
    if not allowed:
        logger.warning("GP_DOCUMENT_PATIENT_NAME not set; no document will be returned for any patient")
        return "", "No data found from the GP."

    if _normalize_name(patient_name) != _normalize_name(allowed):
        logger.info("Patient '%s' does not match document patient '%s'; returning no data", patient_name, allowed)
        return "", "No data found from the GP."

    raw_text, summary = load_gp_document_summary(path)
    return raw_text, summary
