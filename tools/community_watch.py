"""Community listening helper (e.g., Reddit, forums)."""

from __future__ import annotations

from typing import List, Dict


def scan_reddit(query: str) -> List[Dict[str, str]]:
    """Return representative community discussions for the query."""

    topic = query or "emerging product sentiment"
    return [
        {
            "platform": "Reddit",
            "thread": f"r/strategy - {topic}",
            "summary": "Users dissect perceived gaps and wishlist features.",
            "url": "https://reddit.com/r/strategy/comments/placeholder",
        },
        {
            "platform": "Reddit",
            "thread": "r/gamingindustry",
            "summary": "Developers debate partnerships and monetization scenarios.",
            "url": "https://reddit.com/r/gamingindustry/comments/placeholder2",
        },
    ]
