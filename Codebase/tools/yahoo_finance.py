"""Yahoo Finance helper powered by the yfinance package."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote_plus

import requests

try:  # pragma: no cover - optional dependency
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None  # type: ignore

SEARCH_API = "https://query2.finance.yahoo.com/v1/finance/search"


def fetch_financials(company: str, scope: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[name-defined]
    """Return structured financial metrics. Falls back gracefully when data is missing."""

    ticker = _resolve_ticker(company, scope)
    if not ticker or not yf:
        return {
            "company": company,
            "symbol": ticker,
            "metrics": {},
            "summary": "Ticker not found or yfinance unavailable.",
            "source": None,
        }

    try:
        instrument = yf.Ticker(ticker)
        info = instrument.info or {}
    except Exception:  # pragma: no cover - network or ticker lookup issue
        return {
            "company": company,
            "symbol": ticker,
            "metrics": {},
            "summary": "Unable to retrieve Yahoo Finance profile.",
            "source": _quote_url(ticker),
        }

    metrics = {
        "market_cap": info.get("marketCap"),
        "revenue": info.get("totalRevenue"),
        "ebitda": info.get("ebitda"),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "free_cashflow": info.get("freeCashflow"),
        "debt_to_equity": info.get("debtToEquity"),
        "beta": info.get("beta"),
        "revenue_growth_yoy": info.get("revenueGrowth"),
    }

    cleaned_metrics = {k: _format_metric(v) for k, v in metrics.items() if v is not None}

    return {
        "company": company,
        "symbol": ticker,
        "currency": info.get("currency"),
        "financial_year_end": info.get("financialCurrency"),
        "metrics": cleaned_metrics,
        "summary": info.get("longBusinessSummary", ""),
        "source": _quote_url(ticker),
    }


def _resolve_ticker(company: str, scope: Dict[str, Any]) -> Optional[str]:
    if not company:
        return None
    possible = scope.get("ticker") or scope.get("symbol")
    if isinstance(possible, str) and possible.strip():
        return possible.strip().upper()

    # If the user typed a ticker-like string we can honor it directly
    if company.isupper() and " " not in company and len(company) <= 5:
        return company

    try:
        response = requests.get(
            SEARCH_API,
            params={"q": company, "quotesCount": 1, "newsCount": 0},
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:  # pragma: no cover - network issues
        return None

    quotes = payload.get("quotes", [])
    if not quotes:
        return None

    symbol = quotes[0].get("symbol")
    return symbol.upper() if symbol else None


def _quote_url(ticker: Optional[str]) -> Optional[str]:
    if not ticker:
        return None
    return f"https://finance.yahoo.com/quote/{quote_plus(ticker)}"


def _format_metric(value: Any) -> Any:
    if isinstance(value, (int, float)):
        if abs(value) >= 1_000_000_000:
            return f"{value / 1_000_000_000:.1f}B"
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if abs(value) >= 1_000:
            return f"{value / 1_000:.1f}K"
        return round(value, 2)
    return value
