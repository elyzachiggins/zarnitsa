"""Collect Voyennaya Mysl (Военная мысль) article PDFs from CyberLeninka.

Open-access, per-article, verbatim source PDFs — the safe way to fill the
escalation / multi-domain / war-economy grounding gaps.

This script only DOWNLOADS the real PDFs into a staging folder for review;
it does NOT create corpus entries. After you review them, we build verbatim
entries with the same pipeline as the rest of the corpus.

Run locally (needs network; my sandbox can't reach the internet):
    python scripts/collect_cyberleninka.py "неядерное сдерживание" --max 6
    python scripts/collect_cyberleninka.py "многосферная операция" --max 8
    python scripts/collect_cyberleninka.py "военно-экономическое обеспечение" --max 6

Options:
    --max N        keep up to N matching PDFs (default 6)
    --journal STR  journal-title filter substring (default "военная мысль";
                   pass "any" to keep articles from any journal)
    --pages N      max search-result pages to scan (default 4)
"""

from __future__ import annotations

import argparse
import html
import io
import os
import re
import sys
import time

import certifi
import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://cyberleninka.ru"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "corpus", "raw", "collected")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PAUSE = 2.0  # be polite: seconds between requests


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA, "Accept-Language": "ru,en;q=0.8"},
        timeout=60.0,
        verify=certifi.where(),
        follow_redirects=True,
    )


def _search_slugs(client: httpx.Client, query: str, max_pages: int) -> list[str]:
    slugs: list[str] = []
    for page in range(1, max_pages + 1):
        r = client.get(f"{BASE}/search", params={"q": query, "page": page})
        if r.status_code != 200:
            print(f"  search page {page}: HTTP {r.status_code} — stopping", flush=True)
            break
        found = re.findall(r"/article/n/([a-z0-9\-]+)", r.text)
        new = [s for s in found if s not in slugs]
        if not new:
            break
        slugs.extend(new)
        time.sleep(PAUSE)
    return slugs


def _meta(client: httpx.Client, slug: str) -> dict | None:
    r = client.get(f"{BASE}/article/n/{slug}")
    if r.status_code != 200:
        return None
    t = r.text

    def tag(name: str) -> str:
        m = re.search(rf'<meta[^>]+name="{name}"[^>]+content="([^"]*)"', t)
        return html.unescape(m.group(1)) if m else ""

    pdf = tag("citation_pdf_url") or f"{BASE}/article/n/{slug}/pdf"
    return {
        "slug": slug,
        "title": tag("citation_title") or slug,
        "journal": tag("citation_journal_title"),
        "year": tag("citation_publication_date")[:4],
        "author": tag("citation_author"),
        "pdf": pdf,
    }


def _download(client: httpx.Client, url: str, dest: str) -> int:
    r = client.get(url)
    if r.status_code == 200 and r.content[:4] == b"%PDF":
        with open(dest, "wb") as f:
            f.write(r.content)
        return len(r.content)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect CyberLeninka article PDFs.")
    ap.add_argument("query", help="search terms (Russian)")
    ap.add_argument("--max", type=int, default=6, help="max PDFs to keep")
    ap.add_argument("--journal", default="военная мысль", help="journal filter substring, or 'any'")
    ap.add_argument("--pages", type=int, default=4, help="max search pages to scan")
    args = ap.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    jfilter = "" if args.journal.lower() == "any" else args.journal.lower()

    print(f"query: {args.query!r}  | journal filter: {args.journal!r}  | max: {args.max}\n")
    kept = 0
    with _client() as client:
        slugs = _search_slugs(client, args.query, args.pages)
        print(f"found {len(slugs)} candidate articles; filtering + downloading...\n", flush=True)
        for slug in slugs:
            if kept >= args.max:
                break
            meta = _meta(client, slug)
            time.sleep(PAUSE)
            if not meta:
                continue
            if jfilter and jfilter not in meta["journal"].lower():
                continue
            dest = os.path.join(RAW_DIR, f"vm_{slug}.pdf")
            size = _download(client, meta["pdf"], dest)
            time.sleep(PAUSE)
            if size:
                kept += 1
                yr = f" ({meta['year']})" if meta["year"] else ""
                print(f"OK  {size:>8,} B  {meta['author']}{yr}: {meta['title'][:80]}")
                print(f"    {BASE}/article/n/{slug}", flush=True)
            else:
                print(f"skip (no downloadable PDF): {meta['title'][:60]}", flush=True)

    print(f"\nDownloaded {kept} PDF(s) -> {os.path.normpath(RAW_DIR)}")
    print("Review them, then tell me which to turn into verbatim corpus entries.")


if __name__ == "__main__":
    main()
