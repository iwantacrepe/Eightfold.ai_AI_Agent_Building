"""Social listening stubs for Twitter/X and LinkedIn."""

from __future__ import annotations

from typing import Any, Dict, List


def scan_twitter(company: str, query: str) -> List[Dict[str, Any]]:
    """Return representative social chatter for the query."""

    base = query or f"{company} product launch"
    return [
        {
            "platform": "Twitter",
            "handle": "@industrywatch",
            "content": f"Analysts discussing {company}'s latest move: {base}.",
            "url": "https://twitter.com/industrywatch/status/1",
        },
        {
            "platform": "Twitter",
            "handle": "@customervoice",
            "content": f"Users highlighting opportunities / gaps tied to {base}.",
            "url": "https://twitter.com/customervoice/status/2",
        },
    ]


def scan_linkedin(company: str, query: str) -> List[Dict[str, Any]]:
    """Return mock LinkedIn posts or hiring updates relevant to the company."""

    base = query or f"{company} hiring roadmap"
    return [
        {
            "platform": "LinkedIn",
            "author": "Head of Talent",
            "content": f"{company} recruiter mentions focus on {base} roles.",
            "url": "https://www.linkedin.com/posts/sample",
        },
        {
            "platform": "LinkedIn",
            "author": "Product Director",
            "content": f"Thought leadership post about {base} priorities.",
            "url": "https://www.linkedin.com/posts/sample2",
        },
    ]
