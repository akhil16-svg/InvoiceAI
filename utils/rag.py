"""
Retrieval layer of the InvoiceAI RAG pipeline.

The corpus is the logged-in user's own invoices (already isolated per user in
the database), so retrieval is grounded in their personal documents. Each
invoice becomes one document combining its structured fields and raw OCR text.

Retrieval is BM25 (rank-bm25): the corpus is small (hundreds of short docs per
user), fully local, and rebuilt fresh from the DB on demand - no embedding
service, vector store, or index persistence needed. An aggregate-statistics
header is always included in the context so portfolio-wide questions ("total
spend this year", "how many flagged invoices") are answerable even when no
single invoice matches the query.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _fmt_amount(inv: Dict, key: str) -> str:
    value = inv.get(key)
    if value is None:
        return "?"
    try:
        return f"{inv.get('currency') or ''} {float(value):,.2f}".strip()
    except (TypeError, ValueError):
        return str(value)


def _doc_text(inv: Dict) -> str:
    """Flatten one invoice into a searchable document."""
    parts = [
        str(inv.get("vendor_name") or ""),
        str(inv.get("invoice_number") or ""),
        str(inv.get("date") or ""),
        str(inv.get("payment_method") or ""),
        str(inv.get("currency") or ""),
        " ".join(str(f) for f in inv.get("fraud_flags") or []),
    ]
    for item in inv.get("items") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("name") or ""))
    parts.append(str(inv.get("raw_text") or ""))
    return " ".join(p for p in parts if p)


def _summarize(inv: Dict) -> str:
    """Compact, citable summary of one invoice for the LLM context."""
    lines = [
        f"invoice_number: {inv.get('invoice_number') or 'unknown'}",
        f"vendor: {inv.get('vendor_name') or 'unknown'}",
        f"date: {inv.get('date') or 'unknown'}",
        f"total: {_fmt_amount(inv, 'total_amount')}",
        f"subtotal: {_fmt_amount(inv, 'subtotal')}",
        f"tax: {_fmt_amount(inv, 'tax_amount')}",
        f"payment_method: {inv.get('payment_method') or 'unknown'}",
    ]
    flags = inv.get("fraud_flags") or []
    if flags:
        lines.append("fraud_flags: " + ", ".join(flags))
    items = [i for i in (inv.get("items") or []) if isinstance(i, dict)]
    if items:
        lines.append("items: " + "; ".join(
            f"{i.get('name', '?')} x{i.get('quantity', '?')}" for i in items[:10]
        ))
    raw = str(inv.get("raw_text") or "").strip()
    if raw:
        lines.append("raw_text_excerpt: " + re.sub(r"\s+", " ", raw)[:600])
    return "\n".join(lines)


class InvoiceRAG:
    """BM25 retrieval + context building over one user's invoices."""

    def __init__(self, invoices: List[Dict[str, Any]]):
        self.invoices = invoices or []
        self._bm25: Optional[BM25Okapi] = None
        tokenized = [_tokenize(_doc_text(inv)) for inv in self.invoices]
        # BM25Okapi requires a non-empty corpus with at least one token
        if any(tokenized):
            self._bm25 = BM25Okapi([toks or ["empty"] for toks in tokenized])

    def search(self, query: str, k: int = 6) -> List[Tuple[Dict, float]]:
        """Top-k invoices for the query, best first. Empty list if no corpus."""
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.invoices, scores), key=lambda p: p[1], reverse=True)
        # Keep zero-score docs only if nothing scored - recency is then the
        # best signal we have (invoices come from the DB newest-first).
        hits = [(inv, s) for inv, s in ranked if s > 0][:k]
        return hits or [(inv, 0.0) for inv in self.invoices[:k]]

    def aggregate_stats(self) -> str:
        """Portfolio-wide stats so global questions don't depend on retrieval."""
        n = len(self.invoices)
        if n == 0:
            return "The user has no invoices stored yet."
        totals: Dict[str, float] = {}
        dates = []
        vendors: Dict[str, int] = {}
        flagged = 0
        for inv in self.invoices:
            cur = inv.get("currency") or "?"
            try:
                totals[cur] = totals.get(cur, 0.0) + float(inv.get("total_amount") or 0)
            except (TypeError, ValueError):
                pass
            if inv.get("date"):
                dates.append(str(inv["date"]))
            if inv.get("vendor_name"):
                vendors[inv["vendor_name"]] = vendors.get(inv["vendor_name"], 0) + 1
            if inv.get("fraud_flags"):
                flagged += 1
        lines = [f"total_invoices: {n}", f"invoices_with_fraud_flags: {flagged}"]
        if totals:
            lines.append("total_spend_by_currency: " + ", ".join(
                f"{c} {v:,.2f}" for c, v in sorted(totals.items())
            ))
        if dates:
            lines.append(f"date_range: {min(dates)} to {max(dates)}")
        if vendors:
            top = sorted(vendors.items(), key=lambda p: p[1], reverse=True)[:8]
            lines.append("top_vendors_by_count: " + ", ".join(f"{v} ({c})" for v, c in top))
        return "\n".join(lines)

    def build_context(self, query: str, k: int = 6) -> Tuple[str, List[Dict]]:
        """
        Build the grounding context for one question.

        Returns (context_string, retrieved_invoices) - the invoices are
        surfaced in the UI as sources.
        """
        hits = self.search(query, k=k)
        blocks = [
            "## Portfolio summary (all invoices)",
            self.aggregate_stats(),
            "",
            f"## Most relevant invoices for this question (top {len(hits)})",
        ]
        for i, (inv, _score) in enumerate(hits, 1):
            blocks.append(f"\n### Invoice {i}\n{_summarize(inv)}")
        if not hits:
            blocks.append("(none - the user has no stored invoices)")
        return "\n".join(blocks), [inv for inv, _ in hits]
