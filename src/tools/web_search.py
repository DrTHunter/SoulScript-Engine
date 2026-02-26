"""Web search tool — lets agents search the web via SearXNG and scrape pages.

Uses a local SearXNG Docker instance to perform web searches, then scrapes
and extracts the main content from the top results.  Supports three modes:
  - fast:   quick factual lookups (configurable pages/words)
  - normal: typical questions (configurable pages/words)
  - deep:   research-level queries (configurable pages/words)

Also provides a single-page scrape action for fetching a specific URL.
Settings are persisted in config/settings.json under "tool_config.web_search".
"""

import json
import os
import re
import unicodedata
import concurrent.futures
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

import requests

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_DEFAULT_SEARXNG_URL = os.environ.get(
    "SEARXNG_URL", "http://localhost:3000/search"
)

_DEFAULT_IGNORED_SITES = (
    "facebook.com,instagram.com,twitter.com,x.com,pinterest.com,"
    "tiktok.com,linkedin.com,reddit.com,scribd.com,slideshare.net,"
    "docplayer.net,pdfcoffee.com,yumpu.com,issuu.com,"
    "stackprinter.appspot.com,stackovernet.com,stackoverrun.com,"
    "stackoom.com,thinbug.com,reposhub.com,tutorialspoint.com,"
    "javatpoint.com,guru99.com,simplilearn.com,w3resource.com,"
    "codegrepper.com,brainly.com,studocu.com,coursehero.com,"
    "chegg.com,answers.com,answers.yahoo.com,ask.com,"
    "quora.com,investopedia.com,techtarget.com,w3schools.com,"
    "wikihow.com"
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Default mode presets: {mode: {pages, return_count, word_limit}}
DEFAULT_MODE_PRESETS: Dict[str, Dict[str, int]] = {
    "fast":   {"pages": 2, "return_count": 2, "word_limit": 1200},
    "normal": {"pages": 5, "return_count": 3, "word_limit": 1500},
    "deep":   {"pages": 8, "return_count": 5, "word_limit": 3000},
}

# Knowledge-gate: keywords that signal the LLM should just use its own knowledge
_SKIP_SEARCH_SIGNALS = [
    "i already know",
    "from my training",
    "general knowledge",
    "common knowledge",
    "well-known fact",
    "no search needed",
]

# Path to settings file (resolved relative to project root)
_SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "settings.json"


def _load_tool_config() -> Dict[str, Any]:
    """Load web_search config from settings.json."""
    if not _SETTINGS_FILE.exists():
        return {}
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tool_config", {}).get("web_search", {})
    except Exception:
        return {}


def get_effective_config() -> Dict[str, Any]:
    """Return the merged config (defaults + user overrides). Used by the UI."""
    saved = _load_tool_config()
    return {
        "searxng_url": saved.get("searxng_url", _DEFAULT_SEARXNG_URL),
        "ignored_sites": saved.get("ignored_sites", _DEFAULT_IGNORED_SITES),
        "require_justification": saved.get("require_justification", True),
        "modes": {
            mode: {
                "pages": saved.get("modes", {}).get(mode, {}).get("pages", defaults["pages"]),
                "return_count": saved.get("modes", {}).get(mode, {}).get("return_count", defaults["return_count"]),
                "word_limit": saved.get("modes", {}).get(mode, {}).get("word_limit", defaults["word_limit"]),
            }
            for mode, defaults in DEFAULT_MODE_PRESETS.items()
        },
    }


def _get_mode_preset(mode: str) -> tuple:
    """Get (scrape_count, return_count, word_limit) for a mode, checking settings."""
    cfg = get_effective_config()
    m = cfg["modes"].get(mode, cfg["modes"]["normal"])
    return (m["pages"], m["return_count"], m["word_limit"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _clean_text(text: str) -> str:
    """Normalise whitespace and strip stray HTML."""
    if any(ch in text for ch in ("<", ">", "&lt;", "&gt;")):
        if BS4_AVAILABLE:
            soup = BeautifulSoup(text, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _remove_emojis(text: str) -> str:
    return "".join(c for c in text if not unicodedata.category(c).startswith("So"))


def _truncate(text: str, word_limit: int) -> str:
    words = text.split()
    if len(words) <= word_limit:
        return text
    return " ".join(words[:word_limit]) + "..."


def _extract_content(html: str, word_limit: int) -> str:
    """Extract main page content, preferring trafilatura then BS4."""
    if TRAFILATURA_AVAILABLE:
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
                include_links=False,
                no_fallback=False,
            )
            if extracted:
                return _truncate(_clean_text(extracted), word_limit)
        except Exception:
            pass

    if not BS4_AVAILABLE:
        return _truncate(_clean_text(html), word_limit)

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    main = None
    for sel in ("main", "article", "[role='main']", ".content",
                ".main-content", ".post-content", ".entry-content",
                "#content", "#main"):
        main = soup.select_one(sel)
        if main:
            break

    node = main if main else soup
    return _truncate(_clean_text(node.get_text(separator=" ", strip=True)), word_limit)


def _fetch_page(url: str, word_limit: int, ignored_sites: str) -> dict | None:
    """Download a URL and return structured result or None on failure."""
    base = _get_base_url(url)
    if ignored_sites:
        for site in ignored_sites.split(","):
            if site.strip() in base:
                return None
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        content = _extract_content(resp.text, word_limit)
        # Extract title
        title = "No title"
        if BS4_AVAILABLE:
            soup = BeautifulSoup(resp.text, "html.parser")
            if soup.title and soup.title.string:
                title = _remove_emojis(soup.title.string.strip())
        return {"title": title, "url": url, "content": content}
    except requests.exceptions.RequestException:
        return None


# ---------------------------------------------------------------------------
# Tool class (follows runtime tool protocol)
# ---------------------------------------------------------------------------

class WebSearchTool:
    """Search the web via SearXNG and optionally scrape page content."""

    def __init__(self):
        # Config is loaded dynamically per-call from settings.json
        pass

    @staticmethod
    def definition() -> Dict[str, Any]:
        return {
            "name": "web_search",
            "description": (
                "Search the web using SearXNG and retrieve relevant page content. "
                "IMPORTANT: Before searching, you MUST first assess whether you "
                "already have sufficient knowledge to answer. Fill in 'knowledge_check' "
                "with what you already know and 'reason' with why a web search is needed. "
                "If you can confidently answer from your training data, do NOT use this tool. "
                "Use action 'search' with a query and mode (fast/normal/deep). "
                "Use action 'scrape' with a url to fetch a single page. "
                "Choose 'fast' for quick lookups, 'normal' for typical questions, "
                "'deep' only when explicitly asked for thorough research."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["search", "scrape"],
                        "description": (
                            "'search' — query SearXNG and scrape top results. "
                            "'scrape' — fetch and extract content from a single URL."
                        ),
                    },
                    "knowledge_check": {
                        "type": "string",
                        "description": (
                            "REQUIRED for 'search'. State what you already know about "
                            "this topic from your training data. Be honest — if you "
                            "can answer confidently, say so and do NOT search."
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "REQUIRED for 'search'. Explain WHY you need the internet "
                            "for this query. Valid reasons: real-time/current data needed, "
                            "topic is beyond your training cutoff, need to verify uncertain info, "
                            "user explicitly asked to search the web, need a specific URL/source."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (required for 'search' action).",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["fast", "normal", "deep"],
                        "description": (
                            "Search depth: 'fast' (2 pages, quick), "
                            "'normal' (5 pages, balanced), "
                            "'deep' (8 pages, thorough). Default: normal."
                        ),
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to scrape (required for 'scrape' action).",
                    },
                },
                "required": ["action"],
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> str:
        action = arguments.get("action", "search")
        if action == "scrape":
            return self._scrape(arguments)

        # ── Knowledge gate: check if the agent justified the search ──
        cfg = get_effective_config()
        if cfg.get("require_justification", True):
            gate_result = self._knowledge_gate(arguments)
            if gate_result is not None:
                return gate_result

        return self._search(arguments)

    # ---- knowledge gate ----
    def _knowledge_gate(self, arguments: Dict[str, Any]) -> str | None:
        """Evaluate whether the search is justified.

        Returns a JSON string telling the agent to use its own knowledge
        if the justification is weak, or None to proceed with the search.
        """
        knowledge_check = (arguments.get("knowledge_check") or "").strip()
        reason = (arguments.get("reason") or "").strip()

        # If agent explicitly says it already knows → bounce back
        if knowledge_check:
            lower_kc = knowledge_check.lower()
            for signal in _SKIP_SEARCH_SIGNALS:
                if signal in lower_kc:
                    return json.dumps({
                        "gate": "blocked",
                        "message": (
                            "You indicated you already have this knowledge. "
                            "Use your training data to answer instead of searching. "
                            "Your stated knowledge: " + knowledge_check
                        ),
                    })

        # If no reason provided at all → remind agent to justify
        if not reason:
            return json.dumps({
                "gate": "missing_justification",
                "message": (
                    "Web search requires a 'reason' explaining why the internet "
                    "is needed. Valid reasons: real-time data, beyond training cutoff, "
                    "need to verify uncertain info, user asked to search, need specific URL. "
                    "If you can answer from your own knowledge, do so without searching."
                ),
            })

        # Reason provided → allow the search
        return None

    # ---- search ----
    def _search(self, arguments: Dict[str, Any]) -> str:
        query = arguments.get("query", "").strip()
        if not query:
            return json.dumps({"error": "No query provided."})

        mode = arguments.get("mode", "normal")
        scrape_count, return_count, word_limit = _get_mode_preset(mode)
        cfg = get_effective_config()
        searxng_url = cfg["searxng_url"]
        ignored_sites = cfg["ignored_sites"]

        # Query SearXNG
        params = {
            "q": query,
            "format": "json",
            "number_of_results": scrape_count,
        }
        try:
            resp = requests.get(
                searxng_url,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])[:scrape_count]
        except requests.exceptions.RequestException as exc:
            return json.dumps({"error": f"SearXNG request failed: {exc}"})

        if not results:
            return json.dumps({"results": [], "message": "No results found."})

        # Scrape pages in parallel
        collected: list[dict] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(
                    _fetch_page,
                    r["url"],
                    word_limit,
                    ignored_sites,
                ): r
                for r in results
            }
            for future in concurrent.futures.as_completed(futures):
                page = future.result()
                if page and len(collected) < return_count:
                    # Inject search snippet
                    snippet = futures[future].get("content", "")
                    if snippet:
                        page["snippet"] = _remove_emojis(snippet)
                    collected.append(page)

        return json.dumps(
            {"query": query, "mode": mode, "results": collected},
            ensure_ascii=False,
            separators=(",", ":"),
        )

    # ---- scrape ----
    def _scrape(self, arguments: Dict[str, Any]) -> str:
        url = arguments.get("url", "").strip()
        if not url:
            return json.dumps({"error": "No URL provided."})

        _, _, word_limit = _get_mode_preset("normal")
        page = _fetch_page(url, word_limit, "")
        if page is None:
            return json.dumps({"error": f"Failed to fetch {url}"})
        return json.dumps(page, ensure_ascii=False, separators=(",", ":"))
