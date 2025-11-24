"""Utilities to export the account plan as a PDF."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

import pdfkit
from flask import render_template
from weasyprint import HTML

from core.models import AccountPlan


def render_account_plan_html(account_plan: AccountPlan) -> str:
    """Render the plan using the report template."""

    return render_template("report.html", plan=account_plan)


def generate_pdf_from_account_plan(account_plan: AccountPlan) -> bytes:
    """Render HTML and convert to PDF (pdfkit preferred, WeasyPrint fallback)."""

    html = render_account_plan_html(account_plan)

    try:
        pdf_bytes: Optional[bytes] = pdfkit.from_string(html, False)
        if pdf_bytes:
            return pdf_bytes
    except OSError:
        pass

    # Fallback to WeasyPrint if wkhtmltopdf is not available.
    buffer = BytesIO()
    HTML(string=html).write_pdf(buffer)
    return buffer.getvalue()
