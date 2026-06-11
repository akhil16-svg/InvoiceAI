# File: utils/fraud_detection.py

def check_for_fraud(summary):
    issues = []

    # Check for missing key fields
    required_fields = ["Invoice Number", "Invoice Date", "Billing Address", "Amount in Words"]
    for field in required_fields:
        if field not in summary or not summary[field].strip():
            issues.append(f"Missing field: {field}")

    # Simple anomaly check: unusually high amount (assuming threshold)
    if "Amount in Words" in summary:
        import re
        text = summary["Amount in Words"]
        numbers = re.findall(r'\d[\d,]*\.?\d*', text.replace(",", ""))
        if numbers:
            try:
                amount = float(numbers[-1])
                if amount > 100000:  # threshold
                    issues.append("Invoice amount unusually high – please verify.")
            except ValueError:
                pass

    # Check for duplicate values in fields that shouldn't be repeated
    if summary.get("Billing Address", "") == summary.get("Shipping Address", ""):
        issues.append("Billing and Shipping addresses are identical – check if this is expected.")

    return issues
