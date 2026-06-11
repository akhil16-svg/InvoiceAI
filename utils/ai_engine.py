"""
Gemini-powered AI engine for InvoiceAI.

Two capabilities:
  1. extract_invoice_fields() - structured field extraction from an invoice
     image and/or OCR text (far more robust than regex on messy receipts).
  2. answer_question() / stream_answer() - grounded Q&A over the user's own
     invoices (the generation half of the RAG pipeline in utils/rag.py).

Everything degrades gracefully: if no Google AI credentials are configured,
is_ai_available() returns False and callers fall back to the regex parser /
extractive search.

Free-tier model: gemini-2.0-flash  (generous free quota, no credit card needed)
Get your key at: https://aistudio.google.com/app/apikey
"""

import json
import os
from typing import Any, Dict, Generator, List, Optional

DEFAULT_MODEL = os.environ.get("INVOICEAI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

INVOICE_SCHEMA_DESCRIPTION = """
Return ONLY a valid JSON object (no markdown, no code fences) with exactly
these keys (use null for anything not present on the document):

{
  "vendor_name":    string | null,
  "vendor_address": string | null,
  "vendor_tax_id":  string | null,
  "invoice_number": string | null,
  "date":           string | null,
  "currency":       string | null,
  "subtotal":       number | null,
  "tax_amount":     number | null,
  "tax_rate":       number | null,
  "total_amount":   number | null,
  "payment_method": string | null,
  "items": [
    {
      "name":       string,
      "quantity":   number,
      "unit_price": number | null,
      "total":      number | null
    }
  ],
  "notes": string | null
}

Rules:
- Normalize dates to YYYY-MM-DD.
- Currency must be an ISO 4217 code (e.g. USD, INR, MYR).
- Amounts are plain numbers — no currency symbols or thousands separators.
- Never invent values; use null if the field is absent.
"""

EXTRACTION_SYSTEM = (
    "You are an invoice data extraction engine. Extract fields exactly as "
    "they appear on the document. " + INVOICE_SCHEMA_DESCRIPTION
)

QA_SYSTEM = (
    "You are the assistant inside InvoiceAI, answering questions about the "
    "user's own uploaded invoices. Ground every answer strictly in the invoice "
    "context provided — never invent invoices, vendors, or amounts. When you "
    "reference a specific invoice, cite it inline like [INV-123 / Vendor Name]. "
    "If the context does not contain the answer, say so plainly and suggest "
    "what the user could upload or check. Keep answers concise; use a short "
    "markdown table when comparing several invoices. "
    "Amounts keep their original currency."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_ai_available() -> bool:
    """True when a Google AI API key is configured."""
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


def _get_api_key() -> str:
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""


def _client():
    """Return a configured google.genai Client."""
    from google import genai
    return genai.Client(api_key=_get_api_key())


# ---------------------------------------------------------------------------
# Invoice field extraction
# ---------------------------------------------------------------------------

def extract_invoice_fields(
    ocr_text: str = "",
    image_bytes: Optional[bytes] = None,
    media_type: str = "image/jpeg",
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    Extract structured invoice fields with Gemini.

    Sends the invoice image (when available) plus the Tesseract OCR text as a
    hint, and asks for strict JSON output matching INVOICE_SCHEMA_DESCRIPTION.

    Raises on API errors — callers decide whether to fall back to regex.
    """
    from google import genai
    from google.genai import types

    client = _client()

    parts: List[Any] = []

    if image_bytes:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=media_type))

    prompt_text = EXTRACTION_SYSTEM
    if ocr_text.strip():
        prompt_text += (
            "\n\nOCR text from the document (may contain recognition errors; "
            "prefer the image when they disagree):\n\n" + ocr_text.strip()[:8000]
        )
    prompt_text += "\n\nExtract the structured fields from this invoice."
    parts.append(prompt_text)

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    # Strip accidental markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)
    parsed["parsing_method"] = "gemini"
    return parsed


# ---------------------------------------------------------------------------
# Q&A (RAG generation step)
# ---------------------------------------------------------------------------

def _build_qa_prompt(question: str, context: str) -> str:
    """Assemble the full prompt for a Q&A turn."""
    return (
        f"{QA_SYSTEM}\n\n"
        "<invoice_context>\n" + context + "\n</invoice_context>\n\n"
        "Question: " + question
    )


def _build_history(history: Optional[List[Dict[str, str]]]):
    """Convert our chat history format to google-genai Content objects."""
    from google.genai import types
    result = []
    for turn in (history or [])[-8:]:
        role = "user" if turn["role"] == "user" else "model"
        result.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
    return result


def answer_question(
    question: str,
    context: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Answer a question grounded in retrieved invoice context (non-streaming)."""
    from google.genai import types

    client = _client()
    chat = client.chats.create(model=model, history=_build_history(history))
    response = chat.send_message(_build_qa_prompt(question, context))
    return response.text


def stream_answer(
    question: str,
    context: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: str = DEFAULT_MODEL,
) -> Generator[str, None, None]:
    """Streaming variant of answer_question for st.write_stream."""
    client = _client()
    chat = client.chats.create(model=model, history=_build_history(history))

    for chunk in chat.send_message_stream(_build_qa_prompt(question, context)):
        if chunk.text:
            yield chunk.text
