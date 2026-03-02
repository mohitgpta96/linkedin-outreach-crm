"""
Enrichment Phase 2C: Company Website Intelligence
Crawls each company's website to extract:
- What they do (one-sentence summary)
- Team size signals
- Open roles (other than PM)
- Recent growth signals
- How they describe their own product/challenges
"""

import logging
import re
import time
import requests
from bs4 import BeautifulSoup
from apify_client import ApifyClient

from config import (
    APIFY_TOKEN,
    APIFY_WEBSITE_CRAWLER,
    WEBSITE_PAGES_TO_CRAWL,
    MAX_PROFILES_TO_ENRICH,
)

logger = logging.getLogger(__name__)

# Pages that give the most insight
HIGH_VALUE_PAGE_PATTERNS = [
    r"/about",
    r"/team",
    r"/product",
    r"/services",
    r"/careers",
    r"/blog",
    r"/news",
    r"/$",  # homepage
]

SIZE_PATTERNS = [
    (r"\b(\d+)\+?\s*employees\b",   "employees"),
    (r"\b(\d+)\+?\s*people\b",      "people"),
    (r"\bteam of (\d+)\b",          "people"),
    (r"\b(\d{2,3})\s*member",       "people"),
]

GROWTH_SIGNALS_PATTERNS = [
    r"series [ab]", r"raised \$", r"funding", r"launched", r"shipped",
    r"new hir", r"grew \d+", r"growing fast",
]


def _extract_company_size(text: str) -> str:
    for pattern, unit in SIZE_PATTERNS:
        match = re.search(pattern, text, re.I)
        if match:
            n = int(match.group(1))
            if n < 500:
                return f"{n} {unit}"
    return ""


def _extract_growth_signals(text: str) -> str:
    found = []
    for pattern in GROWTH_SIGNALS_PATTERNS:
        match = re.search(pattern, text, re.I)
        if match:
            start = max(0, match.start() - 20)
            end   = min(len(text), match.end() + 60)
            snippet = text[start:end].strip().replace("\n", " ")
            found.append(snippet)
    return "; ".join(found[:3])


def _extract_open_roles(text: str) -> str:
    """Find mentions of open roles other than PM."""
    role_patterns = [
        r"hiring\s+(?:a\s+)?([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})",
        r"open (?:role|position)[s]? for ([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})",
        r"join us as (?:a\s+)?([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})",
        r"([A-Z][a-z]+(?: [A-Z][a-z]+){0,3}) - (Apply|Open)",
    ]
    roles = []
    for pattern in role_patterns:
        for match in re.finditer(pattern, text):
            role = match.group(1).strip()
            pm_words = {"project manager", "product manager", "pm"}
            if role.lower() not in pm_words and len(role) > 2:
                roles.append(role)
    return ", ".join(roles[:5])


def enrich_with_website(leads: list[dict]) -> list[dict]:
    """
    For each lead with a company_website, crawl the site and extract
    company intelligence: description, size, growth signals, open roles.
    """
    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set — skipping website enrichment.")
        return leads

    # Only enrich leads that have a website and haven't been website-enriched
    to_enrich = [
        lead for lead in leads
        if lead.get("company_website") and not lead.get("what_they_do")
    ][:MAX_PROFILES_TO_ENRICH]

    if not to_enrich:
        logger.info("[Website Enrichment] Nothing to enrich.")
        return leads

    client = ApifyClient(APIFY_TOKEN)

    # Group by unique websites to avoid re-crawling the same site
    seen_websites: set[str] = set()
    unique_leads = []
    for lead in to_enrich:
        ws = lead.get("company_website", "").rstrip("/")
        if ws and ws not in seen_websites:
            seen_websites.add(ws)
            unique_leads.append(lead)

    start_urls = [
        {"url": lead["company_website"]}
        for lead in unique_leads
        if lead.get("company_website")
    ]

    logger.info(f"[Website Enrichment] Crawling {len(start_urls)} company websites...")

    run_input = {
        "startUrls": start_urls,
        "maxCrawlPages": WEBSITE_PAGES_TO_CRAWL * len(start_urls),
        "maxCrawlDepth": 2,
        "crawlerType": "cheerio",
        "proxy": {"useApifyProxy": True},
        "pageFunction": None,
    }

    try:
        run = client.actor(APIFY_WEBSITE_CRAWLER).call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as exc:
        logger.error(f"[Website Enrichment] Actor failed: {exc}")
        return leads

    # Group crawled pages by origin domain
    pages_by_domain: dict[str, list[dict]] = {}
    for item in items:
        url = item.get("url", "")
        # Extract domain as key
        domain = re.sub(r"https?://(?:www\.)?", "", url).split("/")[0]
        pages_by_domain.setdefault(domain, []).append(item)

    # Build enrichment per domain
    domain_enrichment: dict[str, dict] = {}
    for domain, pages in pages_by_domain.items():
        combined_text = " ".join(
            (p.get("text") or p.get("markdown") or p.get("html") or "")[:2000]
            for p in pages
        )

        homepage = next(
            (p for p in pages if re.search(r"/$|^https?://[^/]+$", p.get("url", ""))),
            pages[0] if pages else {},
        )
        title = homepage.get("title") or homepage.get("pageTitle") or ""
        meta_desc = homepage.get("metaDescription") or ""

        # What they do: prefer meta description, fall back to first sentence of homepage text
        what_they_do = meta_desc or title or ""
        if not what_they_do:
            body = homepage.get("text") or homepage.get("markdown") or ""
            sentences = re.split(r"[.!?]", body)
            what_they_do = next((s.strip() for s in sentences if len(s.strip()) > 20), "")

        domain_enrichment[domain] = {
            "what_they_do":     what_they_do[:200],
            "company_size":     _extract_company_size(combined_text),
            "growth_signals":   _extract_growth_signals(combined_text),
            "careers_page_roles": _extract_open_roles(combined_text),
        }

    # Merge into leads
    for lead in leads:
        ws = lead.get("company_website", "")
        if not ws:
            continue
        domain = re.sub(r"https?://(?:www\.)?", "", ws).split("/")[0]
        data = domain_enrichment.get(domain)
        if not data:
            continue
        lead.setdefault("what_they_do",       data["what_they_do"])
        lead.setdefault("company_size",       data["company_size"])
        lead.setdefault("growth_signals",     data["growth_signals"])
        lead.setdefault("careers_page_roles", data["careers_page_roles"])

    logger.info(f"[Website Enrichment] Enriched {len(domain_enrichment)} companies.")
    return leads


def _scrape_website_free(url: str) -> dict:
    """Fallback: scrape homepage with requests+BeautifulSoup (no Apify)."""
    try:
        resp = requests.get(
            url, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OutreachBot/1.0)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        title = soup.title.string.strip() if soup.title else ""

        # Meta description
        meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        meta_desc = (meta.get("content") or "").strip() if meta else ""

        # First meaningful paragraph
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
        first_para = paragraphs[0] if paragraphs else ""

        what_they_do = meta_desc or first_para or title

        # Combined text for pattern extraction
        body_text = soup.get_text(" ", strip=True)[:5000]

        return {
            "what_they_do":       what_they_do[:200],
            "company_size":       _extract_company_size(body_text),
            "growth_signals":     _extract_growth_signals(body_text),
            "careers_page_roles": _extract_open_roles(body_text),
        }
    except Exception as exc:
        logger.debug(f"[Website Free] Failed for {url}: {exc}")
        return {}


def enrich_with_website_free(leads: list[dict]) -> list[dict]:
    """
    Free fallback: scrape company homepages with requests+BeautifulSoup.
    Used when Apify credits are exhausted. Slower but costs nothing.
    """
    to_enrich = [
        lead for lead in leads
        if lead.get("company_website") and not lead.get("what_they_do")
    ][:MAX_PROFILES_TO_ENRICH]

    if not to_enrich:
        logger.info("[Website Free] Nothing to enrich.")
        return leads

    seen: set[str] = set()
    enrichment_map: dict[str, dict] = {}

    for lead in to_enrich:
        url = lead["company_website"].rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        domain = re.sub(r"https?://(?:www\.)?", "", url).split("/")[0]
        logger.info(f"[Website Free] Scraping: {url}")
        data = _scrape_website_free(url)
        if data.get("what_they_do"):
            enrichment_map[domain] = data
        time.sleep(0.3)

    for lead in leads:
        ws = lead.get("company_website", "")
        if not ws:
            continue
        domain = re.sub(r"https?://(?:www\.)?", "", ws).split("/")[0]
        data = enrichment_map.get(domain)
        if not data:
            continue
        lead.setdefault("what_they_do",       data.get("what_they_do", ""))
        lead.setdefault("company_size",       data.get("company_size", ""))
        lead.setdefault("growth_signals",     data.get("growth_signals", ""))
        lead.setdefault("careers_page_roles", data.get("careers_page_roles", ""))

    logger.info(f"[Website Free] Enriched {len(enrichment_map)} companies.")
    return leads
