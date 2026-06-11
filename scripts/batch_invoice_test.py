#!/usr/bin/env python3
"""
Run a repeatable invoice batch through the live InvoiceAI API.

This is an evaluation harness, not ML model training. It creates a fresh test
user, seeds demo AP context, saves synthetic invoices with known business
scenarios, and prints the resulting risk, PO matching, and workflow summary.
"""

import argparse
import json
import random
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


def request_json(base_url, path, method="GET", token=None, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {raw}") from exc


def auth(base_url, email, password):
    payload = {"name": "Invoice Batch Tester", "email": email, "password": password}
    try:
        return request_json(base_url, "/auth/register", method="POST", payload=payload)
    except RuntimeError:
        return request_json(base_url, "/auth/login", method="POST", payload={"email": email, "password": password})


def build_invoice(index, run_id):
    invoice_date = date(2026, 5, 1) + timedelta(days=index % 21)
    scenarios = [
        "matched_po_low",
        "over_po_high",
        "high_value_no_po",
        "unknown_vendor",
        "missing_fields",
        "duplicate_like",
        "approved_ready",
        "paid_small",
    ]
    scenario = scenarios[index % len(scenarios)]
    invoice_number = f"BATCH-{run_id}-{index + 1:04d}"

    invoice = {
        "invoice_number": invoice_number,
        "vendor_name": "Brightline Electric",
        "date": invoice_date.isoformat(),
        "currency": "USD",
        "subtotal": 3200,
        "tax_amount": 0,
        "total_amount": 3200,
        "fraud_flags": [],
        "source_file": f"synthetic-{index + 1:04d}.png",
    }

    if scenario == "matched_po_low":
        invoice.update(
            {
                "vendor_name": "Brightline Electric",
                "purchase_order_number": "PO-5127",
                "project_code": "PROP-100",
                "cost_code": "MAINT-ELEC",
                "total_amount": 3200,
                "subtotal": 3200,
            }
        )
    elif scenario == "over_po_high":
        invoice.update(
            {
                "vendor_name": "Apex Roofing Co",
                "purchase_order_number": "PO-4802",
                "project_code": "CAPEX-22",
                "cost_code": "REPAIR-ROOF",
                "total_amount": 22000 + (index % 3) * 750,
                "subtotal": 22000 + (index % 3) * 750,
                "fraud_flags": ["total_mismatch", "large_amount"],
            }
        )
    elif scenario == "high_value_no_po":
        invoice.update(
            {
                "vendor_name": "Northstar Security",
                "project_code": "PROP-100",
                "cost_code": "OPS-SEC",
                "total_amount": 7400 + index * 10,
                "subtotal": 7400 + index * 10,
            }
        )
    elif scenario == "unknown_vendor":
        invoice.update(
            {
                "vendor_name": "Horizon Plumbing",
                "total_amount": 2100 + index * 7,
                "subtotal": 2100 + index * 7,
            }
        )
    elif scenario == "missing_fields":
        invoice.update(
            {
                "vendor_name": "",
                "date": None,
                "total_amount": 1550 + index,
                "subtotal": 1550 + index,
                "fraud_flags": ["missing_vendor"],
            }
        )
    elif scenario == "duplicate_like":
        invoice.update(
            {
                "vendor_name": "Brightline Electric",
                "date": "2026-05-01",
                "purchase_order_number": "PO-5127",
                "project_code": "PROP-100",
                "cost_code": "MAINT-ELEC",
                "total_amount": 3200,
                "subtotal": 3200,
            }
        )
    elif scenario == "approved_ready":
        invoice.update(
            {
                "vendor_name": "Apex Roofing Co",
                "purchase_order_number": "PO-4802",
                "project_code": "CAPEX-22",
                "cost_code": "REPAIR-ROOF",
                "total_amount": 16000 + (index % 5) * 100,
                "subtotal": 16000 + (index % 5) * 100,
                "workflow_status": "approved",
            }
        )
    elif scenario == "paid_small":
        invoice.update(
            {
                "vendor_name": "Northstar Security",
                "project_code": "PROP-100",
                "cost_code": "OPS-SEC",
                "total_amount": 800 + index,
                "subtotal": 800 + index,
                "workflow_status": "paid",
                "payment_status": "paid",
            }
        )

    return scenario, invoice


def run_batch(base_url, count, email, password, seed_demo=True):
    random.seed(42)
    auth_payload = auth(base_url, email, password)
    token = auth_payload["token"]
    if seed_demo:
        request_json(base_url, "/ops/demo", method="POST", token=token)

    run_id = str(int(time.time()))[-6:]
    expected_scenarios = Counter()
    saved_records = []
    for index in range(count):
        scenario, invoice = build_invoice(index, run_id)
        expected_scenarios[scenario] += 1
        response = request_json(base_url, "/invoices", method="POST", token=token, payload={"invoice": invoice})
        saved_records.append({"scenario": scenario, "invoice": response["invoice"]})

    listed = request_json(base_url, "/invoices", token=token)
    invoices = listed.get("invoices", [])
    summary = listed.get("summary", {})
    ap = summary.get("ap", {})
    saved_invoices = [record["invoice"] for record in saved_records]
    scenario_breakdown = {}
    for scenario in expected_scenarios:
        invoices_for_scenario = [record["invoice"] for record in saved_records if record["scenario"] == scenario]
        scenario_breakdown[scenario] = {
            "count": len(invoices_for_scenario),
            "risk_counts": dict(Counter(invoice.get("risk_level", "unknown") for invoice in invoices_for_scenario)),
            "match_counts": dict(Counter(invoice.get("match_status", "unknown") for invoice in invoices_for_scenario)),
            "workflow_counts": dict(Counter(invoice.get("workflow_status", "unknown") for invoice in invoices_for_scenario)),
            "average_risk_score": round(
                sum(float(invoice.get("risk_score") or 0) for invoice in invoices_for_scenario) / max(len(invoices_for_scenario), 1),
                1,
            ),
        }

    high_risk = sorted(
        [invoice for invoice in invoices if invoice.get("risk_level") == "high"],
        key=lambda invoice: invoice.get("risk_score", 0),
        reverse=True,
    )

    return {
        "base_url": base_url,
        "test_user": email,
        "requested_invoices": count,
        "stored_invoices_for_user": len(invoices),
        "expected_scenarios": dict(expected_scenarios),
        "scenario_breakdown": scenario_breakdown,
        "risk_counts": Counter(invoice.get("risk_level", "unknown") for invoice in saved_invoices),
        "match_counts": Counter(invoice.get("match_status", "unknown") for invoice in saved_invoices),
        "workflow_counts": Counter(invoice.get("workflow_status", "unknown") for invoice in saved_invoices),
        "ap_summary": {
            "ready_to_pay": ap.get("ready_to_pay"),
            "blocked_amount": ap.get("blocked_amount"),
            "po_match_rate": ap.get("po_match_rate"),
            "assignment_rate": ap.get("assignment_rate"),
            "overdue_count": ap.get("overdue_count"),
            "due_soon_count": ap.get("due_soon_count"),
        },
        "top_high_risk": [
            {
                "invoice_number": invoice.get("invoice_number"),
                "vendor_name": invoice.get("vendor_name"),
                "risk_score": invoice.get("risk_score"),
                "match_status": invoice.get("match_status"),
                "reasons": invoice.get("risk_reasons", [])[:3],
            }
            for invoice in high_risk[:8]
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Batch-test InvoiceAI with synthetic invoice scenarios.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api")
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default="Password123!")
    parser.add_argument("--no-seed-demo", action="store_true")
    parser.add_argument("--output", help="Optional path to write the JSON report.")
    args = parser.parse_args()

    email = args.email or f"batch-test+{int(time.time())}@example.com"
    report = run_batch(args.base_url, args.count, email, args.password, seed_demo=not args.no_seed_demo)

    serializable_report = json.loads(json.dumps(report, default=dict))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(serializable_report, indent=2), encoding="utf-8")

    print(json.dumps(serializable_report, indent=2))


if __name__ == "__main__":
    main()
