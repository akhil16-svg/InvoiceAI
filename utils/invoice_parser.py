import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

class InvoiceParser:
    """
    Universal invoice parser that works with ANY invoice format.
    Uses multiple fallback patterns to extract data from diverse layouts.
    """
    
    def __init__(self, use_llm: bool = False, llm_api_key: Optional[str] = None):
        self.use_llm = use_llm
        self.llm_api_key = llm_api_key
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Main parsing function"""
        if self.use_llm and self.llm_api_key:
            return self._parse_with_llm(text)
        else:
            return self._parse_with_regex(text)
    
    def _parse_with_llm(self, text: str) -> Dict[str, Any]:
        """Parse using LLM (placeholder for future)"""
        return self._parse_with_regex(text)
    
    def _parse_with_regex(self, text: str) -> Dict[str, Any]:
        """Universal regex-based parser with multiple fallbacks"""
        cleaned_text = text.replace("\n", " ").replace("  ", " ").strip()
        original_text = text  # Keep original with line breaks
        
        parsed = {
            "vendor_name": self._extract_vendor(original_text, cleaned_text),
            "invoice_number": self._extract_invoice_number(cleaned_text),
            "date": self._extract_date(cleaned_text),
            "currency": self._extract_currency(cleaned_text),
            "subtotal": self._extract_subtotal(cleaned_text),
            "tax_amount": self._extract_tax(cleaned_text),
            "tax_rate": self._extract_tax_rate(cleaned_text),
            "total_amount": self._extract_total(cleaned_text),
            "payment_method": self._extract_payment_method(cleaned_text),
            "items": self._extract_items(original_text),
            "vendor_tax_id": self._extract_tax_id(cleaned_text),
            "vendor_address": None,
            "notes": None,
            "fraud_flags": [],
            "raw_text": text,
            "parsing_method": "regex"
        }
        
        # Add fraud detection
        parsed["fraud_flags"] = self._detect_fraud(parsed, text)
        
        return parsed
    
    def _extract_vendor(self, original_text: str, cleaned_text: str) -> Optional[str]:
        """
        Extract vendor name - tries MULTIPLE patterns
        Works for: receipts, invoices, bills from any vendor
        """
        
        # Pattern 1: Lines with specific keywords
        vendor_keywords = [
            r"(?:Sold By|Supplier|Vendor|From|Bill From|Billed By)[:\s]*([A-Z][^\n]{3,80}?)(?:\n|$)",
            r"(?:Company|Business|Store|Shop)[:\s]*([A-Z][^\n]{3,80}?)(?:\n|$)"
        ]
        
        for pattern in vendor_keywords:
            match = re.search(pattern, original_text, re.IGNORECASE | re.MULTILINE)
            if match:
                vendor = match.group(1).strip()
                vendor = self._clean_vendor_name(vendor)
                if len(vendor) > 3:
                    return vendor
        
        # Pattern 2: First line with company indicators (LIMITED, LTD, INC, etc.)
        company_pattern = r"^([A-Z][A-Za-z\s&.,'-]{3,60}(?:LIMITED|LTD|PRIVATE|PVT|INC|CORP|LLC|SDN BHD|BHD))"
        match = re.search(company_pattern, original_text, re.MULTILINE)
        if match:
            return self._clean_vendor_name(match.group(1))
        
        # Pattern 3: Look for common business name patterns
        lines = [l.strip() for l in original_text.split("\n") if l.strip()]
        for line in lines[:10]:  # Check first 10 lines
            # Skip lines with invoice/receipt/bill keywords
            if any(word in line.lower() for word in ['invoice', 'receipt', 'bill', 'order', 'date', 'no.', 'total']):
                continue
            
            # Check if line looks like a business name
            if len(line) > 5 and len(line) < 80:
                # Must start with capital, have some letters
                if re.match(r'^[A-Z]', line) and sum(c.isalpha() for c in line) > 3:
                    # Check if it contains business-like words
                    business_words = ['mart', 'shop', 'store', 'restaurant', 'cafe', 'hotel', 
                                    'pharmacy', 'market', 'center', 'company', 'services',
                                    'sdn', 'bhd', 'limited', 'corp']
                    
                    if any(word in line.lower() for word in business_words):
                        return self._clean_vendor_name(line)
        
        # Pattern 4: First substantial line (fallback)
        for line in lines[:5]:
            if len(line) > 5 and len(line) < 100:
                if not any(word in line.lower() for word in ['invoice', 'receipt', 'bill', 'total', 'date']):
                    return self._clean_vendor_name(line)
        
        return None
    
    def _clean_vendor_name(self, vendor: str) -> str:
        """Clean up vendor name"""
        # Remove common suffixes from the end
        vendor = re.sub(r'\s+(Billing Address|Bill To|Address).*$', '', vendor, flags=re.IGNORECASE)
        # Remove excessive whitespace
        vendor = ' '.join(vendor.split())
        return vendor.strip()
    
    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """
        Extract invoice/receipt number - UNIVERSAL patterns
        Works for: Invoice No, Receipt No, Bill No, Order No, Ref No, etc.
        """
        patterns = [
            # Standard invoice patterns
            r"Invoice\s*(?:Number|No\.?|#)[:\s]*([A-Z0-9\-\/]+)",
            r"Receipt\s*(?:Number|No\.?|#)[:\s]*([A-Z0-9\-\/]+)",
            r"Bill\s*(?:Number|No\.?|#)[:\s]*([A-Z0-9\-\/]+)",
            r"Order\s*(?:Number|No\.?|#)[:\s]*([A-Z0-9\-\/]+)",
            r"Reference\s*(?:Number|No\.?|#)[:\s]*([A-Z0-9\-\/]+)",
            r"Ref\s*(?:No\.?|#)[:\s]*([A-Z0-9\-\/]+)",
            
            # Abbreviated forms
            r"INV[:\s#]*([A-Z0-9\-\/]+)",
            r"RCP[:\s#]*([A-Z0-9\-\/]+)",
            
            # Generic number after colon
            r"(?:No\.?|#)[:\s]*([A-Z0-9\-\/]{5,})",
            
            # Pattern like "INVOICE NO : 12345"
            r"INVOICE\s+NO\s*:\s*([A-Z0-9\-\/]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                inv_num = match.group(1).strip()
                # Filter out dates
                if not re.match(r'^\d{2}[-/]\d{2}[-/]\d{2,4}$', inv_num):
                    return inv_num
        
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """
        Extract date - UNIVERSAL patterns
        Handles: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, YYYY-MM-DD, "04 Jan 2017", etc.
        """
        patterns = [
            # With labels
            r"(?:Date|Invoice Date|Order Date|Bill Date)[:\s]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})",
            r"(?:Date|Invoice Date|Order Date|Bill Date)[:\s]*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})",
            r"(?:Date|Invoice Date)[:\s]*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",  # "04 Jan 2017"
            
            # Standalone dates
            r"\b(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})\b",
            r"\b(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})\b",
            r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b",  # "04 January 2017"
            
            # With time (17-02-18 format)
            r"(\d{2}[-/\.]\d{2}[-/\.]\d{2})\s+\d{2}:\d{2}",
            
            # Date with time like "04 Jan 2017 01:15pm"
            r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\s+\d{1,2}:\d{2}",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                return self._normalize_date(date_str)
        
        return None
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date to YYYY-MM-DD format"""
        try:
            # Try multiple formats including month names
            formats = [
                "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",  # DD-MM-YYYY
                "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",  # DD-MM-YY
                "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",  # YYYY-MM-DD
                "%m-%d-%Y", "%m/%d/%Y",              # MM-DD-YYYY
                "%d %b %Y", "%d %B %Y",              # 04 Jan 2017, 04 January 2017
                "%d-%b-%Y", "%d/%b/%Y",              # 04-Jan-2017
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except:
                    continue
            
            return date_str  # Return as-is if can't parse
        except:
            return date_str
    
    def _extract_currency(self, text: str) -> Optional[str]:
        """Detect currency - supports GLOBAL currencies"""
        currency_map = {
            # Symbols
            '₹': 'INR', 'Rs': 'INR', 'Rs.': 'INR',
            'RM': 'MYR',
            '$': 'USD', 'US$': 'USD',
            '€': 'EUR',
            '£': 'GBP',
            '¥': 'JPY',
            '₩': 'KRW',
            'A$': 'AUD',
            'C$': 'CAD',
            'S$': 'SGD',
            
            # Codes
            'INR': 'INR', 'MYR': 'MYR', 'USD': 'USD', 'EUR': 'EUR',
            'GBP': 'GBP', 'JPY': 'JPY', 'SGD': 'SGD', 'AUD': 'AUD'
        }
        
        for symbol, code in currency_map.items():
            if symbol in text:
                return code
        
        return None
    
    def _extract_subtotal(self, text: str) -> Optional[float]:
        """Extract subtotal - multiple patterns"""
        patterns = [
            r"Subtotal[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Sub[\s-]*Total[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Sub[\s-]*Amt[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except:
                    continue
        
        return None
    
    def _extract_tax(self, text: str) -> Optional[float]:
        """Extract tax amount - supports GST, VAT, Sales Tax, etc."""
        patterns = [
            r"(?:GST|VAT|Tax|Sales Tax|Service Tax)[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Tax\s+Amount[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Tax\(RM\)[:\s]*([0-9,]+\.?\d*)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except:
                    continue
        
        return None
    
    def _extract_tax_rate(self, text: str) -> Optional[float]:
        """Extract tax rate percentage"""
        patterns = [
            r"(?:GST|VAT|Tax)[^0-9]*(\d+(?:\.\d+)?)\s*%",
            r"(\d+(?:\.\d+)?)\s*%\s*(?:GST|VAT|Tax)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except:
                    continue
        
        return None
    
    def _extract_total(self, text: str) -> Optional[float]:
        """
        Extract total amount - MOST IMPORTANT
        Enhanced to handle Malaysian receipts like "Total Incl. GST:RM 20.05"
        """
        patterns = [
            # Malaysian format: "Total Incl. GST:RM 20.05"
            r"Total\s+Incl\.?\s+GST\s*:?\s*RM\s*([0-9,]+\.?\d*)",
            
            # Standard patterns
            r"Total\s+(?:Amount|Sales|Incl|Inclusive)[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Grand\s+Total[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Amount\s+Due[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Balance\s+Due[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Net\s+Amount[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            
            # Simple "TOTAL" with various separators
            r"TOTAL[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            r"Total[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            
            # With parentheses
            r"Total\s+\([^)]+\)[:\s]*[A-Z₹Rs$€£¥RM]*\s*([0-9,]+\.?\d*)",
            
            # Pattern like "Total Sales (Inclusive GST) RM 108.50"
            r"Total\s+Sales\s+\([^)]+\)\s+RM\s+([0-9,]+\.?\d*)",
            
            # Just "RM" followed by amount at end of line
            r"RM\s+([0-9,]+\.\d{2})$",
        ]
        
        # Try all patterns and collect matches
        candidates = []
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
            for match in matches:
                try:
                    amount = float(match.group(1).replace(',', ''))
                    if 0 < amount < 1000000000:  # Sanity check
                        candidates.append(amount)
                except:
                    continue
        
        # Return the largest amount (usually the final total)
        if candidates:
            return max(candidates)
        
        return None
    
    def _extract_payment_method(self, text: str) -> Optional[str]:
        """Extract payment method"""
        methods = {
            'cash': 'Cash',
            'card': 'Card',
            'credit card': 'Credit Card',
            'debit card': 'Debit Card',
            'upi': 'UPI',
            'paypal': 'PayPal',
            'bank transfer': 'Bank Transfer',
            'net banking': 'Net Banking',
            'check': 'Check',
            'cheque': 'Cheque',
            'online': 'Online Payment'
        }
        
        text_lower = text.lower()
        for key, value in methods.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_items(self, text: str) -> List[Dict[str, Any]]:
        """Extract line items - basic implementation"""
        items = []
        lines = text.split("\n")
        
        # Pattern: item name, quantity, price, total
        for line in lines:
            patterns = [
                r"^(.+?)\s+(\d+)\s*[xX×@]\s*([0-9,]+\.?\d*)\s*=?\s*([0-9,]+\.?\d*)",
                r"^(.+?)\s+Qty[:\s]*(\d+)\s+(?:Price|Rate)[:\s]*([0-9,]+\.?\d*)\s+(?:Total|Amt)[:\s]*([0-9,]+\.?\d*)",
                r"(\d+)\s+([A-Z][^\d]+?)\s+([0-9,]+\.?\d*)\s+([0-9,]+\.?\d*)",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, line.strip())
                if match:
                    try:
                        items.append({
                            "name": match.group(1).strip() if len(match.groups()) >= 4 else "Unknown",
                            "quantity": int(match.group(2)),
                            "unit_price": float(match.group(3).replace(',', '')),
                            "total": float(match.group(4).replace(',', ''))
                        })
                        break
                    except:
                        continue
        
        return items
    
    def _extract_tax_id(self, text: str) -> Optional[str]:
        """Extract vendor tax ID - supports multiple formats"""
        patterns = [
            r"GST\s+(?:Registration\s+)?No\.?[:\s]*([A-Z0-9]+)",
            r"GST\s+ID\.?[:\s]*([A-Z0-9]+)",
            r"GSTIN[:\s]*([A-Z0-9]+)",
            r"PAN\s+No\.?[:\s]*([A-Z0-9]+)",
            r"VAT\s+No\.?[:\s]*([A-Z0-9]+)",
            r"Tax\s+ID[:\s]*([A-Z0-9]+)",
            r"TIN[:\s]*([A-Z0-9]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _detect_fraud(self, parsed_data: Dict, raw_text: str) -> List[str]:
        """Detect potential fraud indicators"""
        flags = []
        
        # Missing critical fields
        if not parsed_data.get("vendor_name"):
            flags.append("MISSING_VENDOR")
        if not parsed_data.get("invoice_number"):
            flags.append("MISSING_INVOICE_NUMBER")
        if not parsed_data.get("date"):
            flags.append("MISSING_DATE")
        
        # Math inconsistency
        subtotal = parsed_data.get("subtotal")
        tax = parsed_data.get("tax_amount")
        total = parsed_data.get("total_amount")
        
        if subtotal and tax and total:
            expected_total = subtotal + tax
            if abs(expected_total - total) > 2.0:  # Allow ₹2 rounding
                flags.append("MATH_MISMATCH")
        
        # Large amount without tax
        if total and total > 100 and not tax:
            flags.append("LARGE_AMOUNT_NO_TAX")
        
        # Future date
        date_str = parsed_data.get("date")
        if date_str:
            try:
                invoice_date = datetime.strptime(date_str, "%Y-%m-%d")
                if invoice_date > datetime.now():
                    flags.append("FUTURE_DATE")
                
                # Very old (>5 years)
                years_old = (datetime.now() - invoice_date).days / 365
                if years_old > 5:
                    flags.append("VERY_OLD_INVOICE")
            except:
                pass
        
        return flags
    
    def format_html_summary(self, parsed_data: Dict) -> str:
        """Generate HTML summary for display"""
        html = "<h5>🧾 <u>Invoice Summary</u></h5>"
        
        # Vendor Section
        if parsed_data.get("vendor_name") or parsed_data.get("vendor_tax_id"):
            html += "<br><b>🏢 Vendor Information:</b><br>"
            if parsed_data.get("vendor_name"):
                html += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Vendor:</b> {parsed_data['vendor_name']}<br>"
            if parsed_data.get("vendor_tax_id"):
                html += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Tax ID:</b> {parsed_data['vendor_tax_id']}<br>"
        
        # Invoice Details
        html += "<br><b>📌 Invoice Details:</b><br>"
        if parsed_data.get("invoice_number"):
            html += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Invoice Number:</b> {parsed_data['invoice_number']}<br>"
        if parsed_data.get("date"):
            html += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Date:</b> {parsed_data['date']}<br>"
        
        # Financial Details
        html += "<br><b>💰 Financial Summary:</b><br>"
        currency = parsed_data.get("currency", "")
        
        if parsed_data.get("subtotal"):
            html += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Subtotal:</b> {currency} {parsed_data['subtotal']:.2f}<br>"
        if parsed_data.get("tax_amount"):
            tax_rate = f" ({parsed_data['tax_rate']}%)" if parsed_data.get("tax_rate") else ""
            html += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Tax{tax_rate}:</b> {currency} {parsed_data['tax_amount']:.2f}<br>"
        if parsed_data.get("total_amount"):
            html += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Total Amount:</b> {currency} {parsed_data['total_amount']:.2f}<br>"
        if parsed_data.get("payment_method"):
            html += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Payment Method:</b> {parsed_data['payment_method']}<br>"
        
        # Items
        if parsed_data.get("items"):
            html += "<br><b>📦 Line Items:</b><br>"
            for idx, item in enumerate(parsed_data['items'], 1):
                html += f"&nbsp;&nbsp;&nbsp;&nbsp;{idx}. {item['name']} - {item['quantity']} x {currency} {item['unit_price']:.2f} = {currency} {item['total']:.2f}<br>"
        
        # Fraud Flags
        if parsed_data.get("fraud_flags"):
            html += "<br><b>⚠️ Fraud Alerts:</b><br>"
            for flag in parsed_data['fraud_flags']:
                html += f"&nbsp;&nbsp;&nbsp;&nbsp;• {flag.replace('_', ' ').title()}<br>"
        
        html += f"<br><small><i>Parsing Method: {parsed_data.get('parsing_method', 'unknown')}</i></small>"
        
        return html