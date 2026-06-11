"""
Accounts payable workflow layer for InvoiceAI.

This module turns raw OCR invoices into operational AP records for
property-management and construction teams: vendor context, project/property
budgets, PO matching, risk scoring, due dates, and audit events.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor


def _money(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value).replace(",", "").replace("$", "").strip() or 0)
    except Exception:
        return 0.0


def _date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value)[:10], fmt)
        except Exception:
            continue
    return None


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


class APWorkflowStore:
    """PostgreSQL-backed AP workflow data for a single authenticated user."""

    def __init__(self, user_email: str):
        self.user_email = user_email
        self.pg_url = os.environ.get("DATABASE_URL")
        if not self.pg_url:
            raise ValueError("DATABASE_URL environment variable is missing for PostgreSQL.")
        self._init_postgres()

    def _connect(self):
        return psycopg2.connect(self.pg_url)

    def _init_postgres(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ap_vendors (
                id SERIAL PRIMARY KEY,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'General Services',
                payment_terms INTEGER DEFAULT 30,
                risk_level TEXT DEFAULT 'low',
                contact_email TEXT,
                tax_id TEXT,
                default_cost_code TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_email, name)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ap_projects (
                id SERIAL PRIMARY KEY,
                user_email TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'property',
                address TEXT,
                budget REAL DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_email, code)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ap_purchase_orders (
                id SERIAL PRIMARY KEY,
                user_email TEXT NOT NULL,
                po_number TEXT NOT NULL,
                vendor_name TEXT,
                project_code TEXT,
                cost_code TEXT,
                description TEXT,
                authorized_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_email, po_number)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ap_audit_events (
                id SERIAL PRIMARY KEY,
                user_email TEXT NOT NULL,
                invoice_number TEXT,
                event_type TEXT NOT NULL,
                details TEXT,
                actor TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        cursor.close()
        conn.close()

    def _upsert(self, sql: str, params: tuple) -> Dict[str, Any]:
        conn = self._connect()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(sql, params)
            row = dict(cursor.fetchone())
            conn.commit()
            return row
        finally:
            cursor.close()
            conn.close()

    def add_vendor(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("Vendor name is required.")
        return self._upsert(
            """
            INSERT INTO ap_vendors
                (user_email, name, category, payment_terms, risk_level, contact_email, tax_id, default_cost_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_email, name) DO UPDATE SET
                category = EXCLUDED.category,
                payment_terms = EXCLUDED.payment_terms,
                risk_level = EXCLUDED.risk_level,
                contact_email = EXCLUDED.contact_email,
                tax_id = EXCLUDED.tax_id,
                default_cost_code = EXCLUDED.default_cost_code
            RETURNING *
            """,
            (
                self.user_email,
                name,
                payload.get("category") or "General Services",
                int(payload.get("payment_terms") or 30),
                payload.get("risk_level") or "low",
                payload.get("contact_email"),
                payload.get("tax_id"),
                payload.get("default_cost_code"),
            ),
        )

    def add_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        code = str(payload.get("code") or "").strip().upper()
        name = str(payload.get("name") or "").strip()
        if not code or not name:
            raise ValueError("Project code and name are required.")
        return self._upsert(
            """
            INSERT INTO ap_projects
                (user_email, code, name, type, address, budget, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_email, code) DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                address = EXCLUDED.address,
                budget = EXCLUDED.budget,
                status = EXCLUDED.status
            RETURNING *
            """,
            (
                self.user_email,
                code,
                name,
                payload.get("type") or "property",
                payload.get("address"),
                _money(payload.get("budget")),
                payload.get("status") or "active",
            ),
        )

    def add_purchase_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        po_number = str(payload.get("po_number") or "").strip().upper()
        if not po_number:
            raise ValueError("PO number is required.")
        return self._upsert(
            """
            INSERT INTO ap_purchase_orders
                (user_email, po_number, vendor_name, project_code, cost_code, description, authorized_amount, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_email, po_number) DO UPDATE SET
                vendor_name = EXCLUDED.vendor_name,
                project_code = EXCLUDED.project_code,
                cost_code = EXCLUDED.cost_code,
                description = EXCLUDED.description,
                authorized_amount = EXCLUDED.authorized_amount,
                status = EXCLUDED.status
            RETURNING *
            """,
            (
                self.user_email,
                po_number,
                payload.get("vendor_name"),
                str(payload.get("project_code") or "").upper() or None,
                payload.get("cost_code"),
                payload.get("description"),
                _money(payload.get("authorized_amount")),
                payload.get("status") or "open",
            ),
        )

    def list_context(self) -> Dict[str, List[Dict[str, Any]]]:
        conn = self._connect()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM ap_vendors WHERE user_email = %s ORDER BY name", (self.user_email,))
            vendors = [dict(row) for row in cursor.fetchall()]
            cursor.execute("SELECT * FROM ap_projects WHERE user_email = %s ORDER BY code", (self.user_email,))
            projects = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                "SELECT * FROM ap_purchase_orders WHERE user_email = %s ORDER BY created_at DESC",
                (self.user_email,),
            )
            purchase_orders = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                "SELECT * FROM ap_audit_events WHERE user_email = %s ORDER BY created_at DESC LIMIT 50",
                (self.user_email,),
            )
            audit_events = [dict(row) for row in cursor.fetchall()]
            return {
                "vendors": vendors,
                "projects": projects,
                "purchase_orders": purchase_orders,
                "audit_events": audit_events,
            }
        finally:
            cursor.close()
            conn.close()

    def seed_demo_context(self) -> Dict[str, Any]:
        vendors = [
            {
                "name": "Apex Roofing Co",
                "category": "Capital Repairs",
                "payment_terms": 15,
                "risk_level": "medium",
                "contact_email": "billing@apexroofing.example",
                "default_cost_code": "REPAIR-ROOF",
            },
            {
                "name": "Brightline Electric",
                "category": "Maintenance",
                "payment_terms": 30,
                "risk_level": "low",
                "contact_email": "ap@brightline.example",
                "default_cost_code": "MAINT-ELEC",
            },
            {
                "name": "Northstar Security",
                "category": "Operations",
                "payment_terms": 30,
                "risk_level": "low",
                "contact_email": "finance@northstar.example",
                "default_cost_code": "OPS-SEC",
            },
        ]
        projects = [
            {
                "code": "PROP-100",
                "name": "Oak Ridge Apartments",
                "type": "property",
                "address": "100 Oak Ridge Ave",
                "budget": 125000,
            },
            {
                "code": "CAPEX-22",
                "name": "Roof Replacement Phase 2",
                "type": "construction",
                "address": "Oak Ridge Apartments",
                "budget": 48000,
            },
        ]
        purchase_orders = [
            {
                "po_number": "PO-4802",
                "vendor_name": "Apex Roofing Co",
                "project_code": "CAPEX-22",
                "cost_code": "REPAIR-ROOF",
                "description": "Phase 2 roofing labor and materials",
                "authorized_amount": 18500,
            },
            {
                "po_number": "PO-5127",
                "vendor_name": "Brightline Electric",
                "project_code": "PROP-100",
                "cost_code": "MAINT-ELEC",
                "description": "Common-area lighting repairs",
                "authorized_amount": 4200,
            },
        ]
        return {
            "vendors": [self.add_vendor(vendor) for vendor in vendors],
            "projects": [self.add_project(project) for project in projects],
            "purchase_orders": [self.add_purchase_order(po) for po in purchase_orders],
        }

    def append_audit_event(
        self,
        invoice_number: Optional[str],
        event_type: str,
        details: Dict[str, Any],
        actor: str,
    ) -> Dict[str, Any]:
        return self._upsert(
            """
            INSERT INTO ap_audit_events (user_email, invoice_number, event_type, details, actor)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (self.user_email, invoice_number, event_type, json.dumps(details, default=str), actor),
        )

    def enhance_invoice(self, invoice: Dict[str, Any], existing_invoices: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add AP workflow metadata, PO match status, and risk scoring."""
        existing_invoices = existing_invoices or []
        context = self.list_context()
        vendors = context["vendors"]
        projects = context["projects"]
        purchase_orders = context["purchase_orders"]

        enhanced = dict(invoice or {})
        vendor = self._match_vendor(enhanced.get("vendor_name"), vendors)
        po = self._match_purchase_order(enhanced, purchase_orders)

        if vendor:
            enhanced.setdefault("category", vendor.get("category"))
            enhanced.setdefault("cost_code", vendor.get("default_cost_code"))
        else:
            enhanced.setdefault("category", self._infer_category(enhanced))

        if po:
            enhanced["purchase_order_number"] = po.get("po_number")
            enhanced.setdefault("project_code", po.get("project_code"))
            enhanced.setdefault("cost_code", po.get("cost_code"))
        elif enhanced.get("project_code"):
            enhanced["purchase_order_number"] = enhanced.get("purchase_order_number") or ""

        project = self._match_project(enhanced.get("project_code"), projects)
        if project:
            enhanced["project_name"] = project.get("name")
            enhanced["project_type"] = project.get("type")

        due_date = enhanced.get("due_date")
        if not due_date:
            terms = int((vendor or {}).get("payment_terms") or 30)
            invoice_date = _date(enhanced.get("date")) or datetime.utcnow()
            enhanced["due_date"] = (invoice_date + timedelta(days=terms)).strftime("%Y-%m-%d")

        risk = self._score_invoice(enhanced, vendor, project, po, existing_invoices)
        enhanced.update(risk)
        enhanced.setdefault("workflow_status", "needs_review" if risk["risk_score"] >= 40 else "ready_for_approval")
        enhanced.setdefault("payment_status", "unpaid")
        enhanced.setdefault("approval_owner", "AP Manager")
        enhanced["last_evaluated_at"] = datetime.utcnow().isoformat()
        return enhanced

    def _match_vendor(self, vendor_name: Any, vendors: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        needle = _norm(vendor_name)
        if not needle:
            return None
        for vendor in vendors:
            candidate = _norm(vendor.get("name"))
            if needle == candidate or needle in candidate or candidate in needle:
                return vendor
        return None

    def _match_project(self, project_code: Any, projects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        code = _norm(project_code).upper()
        return next((project for project in projects if _norm(project.get("code")).upper() == code), None)

    def _match_purchase_order(self, invoice: Dict[str, Any], purchase_orders: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        po_number = _norm(invoice.get("purchase_order_number")).upper()
        if po_number:
            exact = next((po for po in purchase_orders if _norm(po.get("po_number")).upper() == po_number), None)
            if exact:
                return exact
        vendor_name = _norm(invoice.get("vendor_name"))
        candidates = [
            po
            for po in purchase_orders
            if po.get("status") == "open"
            and vendor_name
            and (_norm(po.get("vendor_name")) in vendor_name or vendor_name in _norm(po.get("vendor_name")))
        ]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _infer_category(self, invoice: Dict[str, Any]) -> str:
        text = " ".join(
            [
                str(invoice.get("vendor_name") or ""),
                str(invoice.get("raw_text") or ""),
                json.dumps(invoice.get("items") or []),
            ]
        ).lower()
        keywords = [
            ("roof", "Capital Repairs"),
            ("electric", "Maintenance"),
            ("security", "Operations"),
            ("plumb", "Maintenance"),
            ("clean", "Janitorial"),
            ("hvac", "Maintenance"),
            ("landscap", "Grounds"),
            ("legal", "Professional Services"),
        ]
        for keyword, category in keywords:
            if keyword in text:
                return category
        return "General Services"

    def _score_invoice(
        self,
        invoice: Dict[str, Any],
        vendor: Optional[Dict[str, Any]],
        project: Optional[Dict[str, Any]],
        po: Optional[Dict[str, Any]],
        existing_invoices: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        amount = _money(invoice.get("total_amount"))
        score = 10
        reasons = []
        flags = invoice.get("fraud_flags") or []
        if flags:
            score += min(len(flags) * 12, 36)
            reasons.append(f"{len(flags)} OCR/parser fraud signal(s)")

        for field, label in (("invoice_number", "invoice number"), ("vendor_name", "vendor"), ("date", "invoice date")):
            if not invoice.get(field):
                score += 10
                reasons.append(f"Missing {label}")

        if vendor:
            vendor_risk = _norm(vendor.get("risk_level"))
            if vendor_risk == "high":
                score += 24
                reasons.append("Vendor is marked high risk")
            elif vendor_risk == "medium":
                score += 12
                reasons.append("Vendor is marked medium risk")
        else:
            score += 12
            reasons.append("Vendor is not in approved vendor master")

        match_status = "NO_PO"
        match_delta = None
        if po:
            authorized = _money(po.get("authorized_amount"))
            match_delta = round(amount - authorized, 2)
            if authorized and amount <= authorized * 1.03:
                match_status = "MATCHED"
            elif authorized:
                match_status = "OVER_PO"
                score += 30
                reasons.append(f"Invoice exceeds PO by {match_delta:,.2f}")
            else:
                match_status = "PO_NO_LIMIT"
                score += 8
                reasons.append("PO has no authorized amount")
        elif amount > 5000:
            score += 30
            reasons.append("High-value invoice has no PO match")
        elif amount > 1000:
            score += 18
            reasons.append("Invoice over review threshold has no PO match")

        if not project and amount > 500:
            score += 12
            reasons.append("Invoice is not assigned to a project/property")

        invoice_number = _norm(invoice.get("invoice_number"))
        vendor_name = _norm(invoice.get("vendor_name"))
        invoice_date = str(invoice.get("date") or "")
        for existing in existing_invoices:
            if existing is invoice:
                continue
            if invoice_number and invoice_number == _norm(existing.get("invoice_number")):
                score += 35
                reasons.append("Duplicate invoice number already exists")
                break
            if (
                vendor_name
                and vendor_name == _norm(existing.get("vendor_name"))
                and abs(amount - _money(existing.get("total_amount"))) < 1
                and invoice_date
                and invoice_date == str(existing.get("date") or "")
            ):
                score += 35
                reasons.append("Possible duplicate vendor/date/amount")
                break

        risk_score = max(0, min(100, int(score)))
        if risk_score >= 70:
            risk_level = "high"
        elif risk_score >= 40:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "match_status": match_status,
            "match_delta": match_delta,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_reasons": reasons or ["No material AP risk detected"],
        }


def build_ap_summary(invoices: List[Dict[str, Any]], context: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    now = datetime.utcnow()
    status_counts: Dict[str, int] = {}
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    overdue = 0
    due_soon = 0
    ready_to_pay = 0.0
    blocked_amount = 0.0
    po_matched = 0
    assigned = 0
    project_spend: Dict[str, float] = {}

    for invoice in invoices:
        status = invoice.get("workflow_status") or "needs_review"
        status_counts[status] = status_counts.get(status, 0) + 1
        risk = invoice.get("risk_level") or "low"
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        amount = _money(invoice.get("total_amount"))
        due = _date(invoice.get("due_date"))
        if due and due < now and invoice.get("payment_status") != "paid":
            overdue += 1
        elif due and due <= now + timedelta(days=7) and invoice.get("payment_status") != "paid":
            due_soon += 1
        if status == "approved" and invoice.get("payment_status") != "paid":
            ready_to_pay += amount
        if status in {"needs_review", "rejected"} or risk == "high":
            blocked_amount += amount
        if invoice.get("match_status") == "MATCHED":
            po_matched += 1
        if invoice.get("project_code"):
            assigned += 1
            code = invoice.get("project_code")
            project_spend[code] = project_spend.get(code, 0.0) + amount

    projects = []
    for project in context.get("projects", []):
        code = project.get("code")
        budget = _money(project.get("budget"))
        spend = project_spend.get(code, 0.0)
        projects.append(
            {
                "code": code,
                "name": project.get("name"),
                "budget": budget,
                "spend": round(spend, 2),
                "remaining": round(budget - spend, 2),
                "utilization": round((spend / budget) * 100, 1) if budget else 0,
            }
        )

    total = len(invoices)
    return {
        "workflow_status_counts": status_counts,
        "risk_counts": risk_counts,
        "overdue_count": overdue,
        "due_soon_count": due_soon,
        "ready_to_pay": round(ready_to_pay, 2),
        "blocked_amount": round(blocked_amount, 2),
        "po_match_rate": round((po_matched / total) * 100, 1) if total else 0,
        "assignment_rate": round((assigned / total) * 100, 1) if total else 0,
        "budget_utilization": sorted(projects, key=lambda item: item["utilization"], reverse=True),
    }
