"""
Unit tests for InvoiceParser and fraud detection logic.
Run with: pytest tests/ -v
"""
import pytest
from utils.invoice_parser import InvoiceParser


@pytest.fixture
def parser():
    return InvoiceParser(use_llm=False)


# ---------------------------------------------------------------------------
# InvoiceParser — field extraction
# ---------------------------------------------------------------------------

class TestInvoiceNumberExtraction:
    def test_standard_invoice_label(self, parser):
        text = "Invoice Number: INV-2024-001\nTotal: $500"
        result = parser.parse(text)
        assert result["invoice_number"] == "INV-2024-001"

    def test_abbreviated_inv_prefix(self, parser):
        text = "INV#: 98765\nDate: 2024-01-15"
        result = parser.parse(text)
        assert result["invoice_number"] == "98765"

    def test_receipt_number(self, parser):
        text = "Receipt No. RCP-0042\nTotal: RM 20.00"
        result = parser.parse(text)
        assert result["invoice_number"] == "RCP-0042"

    def test_missing_invoice_number(self, parser):
        text = "Vendor: ACME Corp\nTotal: $100"
        result = parser.parse(text)
        assert result["invoice_number"] is None


class TestDateExtraction:
    def test_iso_date(self, parser):
        result = parser.parse("Date: 2024-03-15\nTotal: $50")
        assert result["date"] == "2024-03-15"

    def test_dd_mm_yyyy_slash(self, parser):
        result = parser.parse("Invoice Date: 15/03/2024\nTotal: $50")
        assert result["date"] == "2024-03-15"

    def test_written_month(self, parser):
        result = parser.parse("Date: 04 Jan 2017\nTotal: $50")
        assert result["date"] == "2017-01-04"

    def test_missing_date(self, parser):
        result = parser.parse("Vendor: Shop\nTotal: $50")
        assert result["date"] is None


class TestTotalExtraction:
    def test_simple_total(self, parser):
        result = parser.parse("Total: $250.00")
        assert result["total_amount"] == 250.0

    def test_grand_total(self, parser):
        result = parser.parse("Grand Total: 1,500.00")
        assert result["total_amount"] == 1500.0

    def test_malaysian_rm_format(self, parser):
        result = parser.parse("Total Incl. GST: RM 20.05")
        assert result["total_amount"] == 20.05

    def test_amount_due(self, parser):
        result = parser.parse("Amount Due: $99.99")
        assert result["total_amount"] == 99.99


class TestCurrencyExtraction:
    def test_usd_symbol(self, parser):
        assert parser.parse("Total: $100")["currency"] == "USD"

    def test_inr_symbol(self, parser):
        assert parser.parse("Total: ₹500")["currency"] == "INR"

    def test_myr_prefix(self, parser):
        assert parser.parse("Total: RM 20.05")["currency"] == "MYR"

    def test_euro_symbol(self, parser):
        assert parser.parse("Amount: €45.00")["currency"] == "EUR"


class TestTaxExtraction:
    def test_gst_amount(self, parser):
        result = parser.parse("GST: $5.00\nTotal: $105.00")
        assert result["tax_amount"] == 5.0

    def test_tax_rate_percent(self, parser):
        result = parser.parse("GST 6%: RM 1.20\nTotal: RM 21.20")
        assert result["tax_rate"] == 6.0


# ---------------------------------------------------------------------------
# Fraud detection (via InvoiceParser._detect_fraud)
# ---------------------------------------------------------------------------

class TestFraudDetection:
    def test_no_flags_on_clean_invoice(self, parser):
        data = {
            "vendor_name": "ACME Corp",
            "invoice_number": "INV-001",
            "date": "2024-06-01",
            "subtotal": 100.0,
            "tax_amount": 10.0,
            "total_amount": 110.0,
        }
        flags = parser._detect_fraud(data, "")
        assert flags == []

    def test_missing_vendor_flagged(self, parser):
        data = {"vendor_name": None, "invoice_number": "INV-001",
                "date": "2024-06-01", "total_amount": 50.0}
        flags = parser._detect_fraud(data, "")
        assert "MISSING_VENDOR" in flags

    def test_missing_invoice_number_flagged(self, parser):
        data = {"vendor_name": "Shop", "invoice_number": None,
                "date": "2024-06-01", "total_amount": 50.0}
        flags = parser._detect_fraud(data, "")
        assert "MISSING_INVOICE_NUMBER" in flags

    def test_future_date_flagged(self, parser):
        data = {"vendor_name": "Shop", "invoice_number": "INV-001",
                "date": "2099-01-01", "total_amount": 50.0}
        flags = parser._detect_fraud(data, "")
        assert "FUTURE_DATE" in flags

    def test_math_mismatch_flagged(self, parser):
        data = {
            "vendor_name": "Shop", "invoice_number": "INV-001",
            "date": "2024-01-01",
            "subtotal": 100.0, "tax_amount": 10.0,
            "total_amount": 999.0,   # wrong — should be 110
        }
        flags = parser._detect_fraud(data, "")
        assert "MATH_MISMATCH" in flags

    def test_very_old_invoice_flagged(self, parser):
        data = {"vendor_name": "Shop", "invoice_number": "INV-001",
                "date": "2010-01-01", "total_amount": 50.0}
        flags = parser._detect_fraud(data, "")
        assert "VERY_OLD_INVOICE" in flags

    def test_large_amount_no_tax_flagged(self, parser):
        data = {"vendor_name": "Shop", "invoice_number": "INV-001",
                "date": "2024-01-01", "total_amount": 500.0,
                "tax_amount": None}
        flags = parser._detect_fraud(data, "")
        assert "LARGE_AMOUNT_NO_TAX" in flags


# ---------------------------------------------------------------------------
# Parsing method label
# ---------------------------------------------------------------------------

class TestParsingMethod:
    def test_regex_method_label(self, parser):
        result = parser.parse("Total: $10")
        assert result["parsing_method"] == "regex"
