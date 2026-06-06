#!/usr/bin/env python3
"""Manual integration smoke tests for the ingest API. Run: python test_ingest.py"""

import os
import sys
import time
from typing import Any

import requests

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8888")
PDF_URL = "https://arxiv.org/pdf/1706.03762"
WIKI_URL = "https://en.wikipedia.org/wiki/Retrieval-augmented_generation"
SEARCH_QUERY = "transformer attention mechanism"
TIMEOUT = 300


class TestResult:
    def __init__(self, name: str, passed: bool, elapsed_ms: float, detail: str = ""):
        self.name = name
        self.passed = passed
        self.elapsed_ms = elapsed_ms
        self.detail = detail


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def test_health() -> TestResult:
    name = "GET /health"
    start = time.perf_counter()
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        elapsed = _elapsed_ms(start)
        if resp.status_code != 200:
            return TestResult(name, False, elapsed, f"HTTP {resp.status_code}")
        data = resp.json()
        ok = (
            data.get("status") in ("ok", "error")
            and "services" in data
            and data["services"].get("chroma") == "ok"
            and data["services"].get("supabase") == "ok"
        )
        detail = (
            f"status={data.get('status')}, "
            f"chroma={data.get('services', {}).get('chroma')}, "
            f"supabase={data.get('services', {}).get('supabase')}"
        )
        return TestResult(name, ok, elapsed, detail)
    except Exception as exc:
        return TestResult(name, False, _elapsed_ms(start), str(exc))


def test_ingest_pdf() -> TestResult:
    name = "POST /api/v1/ingest/pdf"
    start = time.perf_counter()
    try:
        pdf_resp = requests.get(PDF_URL, timeout=60)
        pdf_resp.raise_for_status()
        files = {
            "file": ("attention_is_all_you_need.pdf", pdf_resp.content, "application/pdf"),
        }
        data = {"title": "Attention Is All You Need"}
        resp = requests.post(
            f"{BASE_URL}/api/v1/ingest/pdf",
            files=files,
            data=data,
            timeout=TIMEOUT,
        )
        elapsed = _elapsed_ms(start)
        if resp.status_code != 200:
            return TestResult(name, False, elapsed, f"HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        ok = (
            body.get("status") == "success"
            and body.get("chunk_count", 0) > 0
            and bool(body.get("document_id"))
        )
        detail = (
            f"document_id={body.get('document_id')}, "
            f"chunks={body.get('chunk_count')}, "
            f"title={body.get('title')!r}"
        )
        return TestResult(name, ok, elapsed, detail)
    except Exception as exc:
        return TestResult(name, False, _elapsed_ms(start), str(exc))


def test_ingest_url() -> TestResult:
    name = "POST /api/v1/ingest/url"
    start = time.perf_counter()
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/ingest/url",
            json={"url": WIKI_URL, "title": "Retrieval-augmented generation"},
            timeout=TIMEOUT,
        )
        elapsed = _elapsed_ms(start)
        if resp.status_code != 200:
            return TestResult(name, False, elapsed, f"HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        ok = (
            body.get("status") == "success"
            and body.get("chunk_count", 0) > 0
            and bool(body.get("document_id"))
        )
        detail = (
            f"document_id={body.get('document_id')}, "
            f"chunks={body.get('chunk_count')}, "
            f"url={body.get('url', WIKI_URL)[:50]}..."
        )
        return TestResult(name, ok, elapsed, detail)
    except Exception as exc:
        return TestResult(name, False, _elapsed_ms(start), str(exc))


def test_search() -> tuple[TestResult, list[dict[str, Any]]]:
    name = "GET /api/v1/ingest/search"
    start = time.perf_counter()
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v1/ingest/search",
            params={"q": SEARCH_QUERY, "k": 5},
            timeout=60,
        )
        elapsed = _elapsed_ms(start)
        if resp.status_code != 200:
            result = TestResult(
                name, False, elapsed, f"HTTP {resp.status_code}: {resp.text[:200]}"
            )
            return result, []
        results = resp.json()
        ok = isinstance(results, list) and len(results) > 0
        detail = f"hits={len(results)}"
        if ok:
            top = results[0]
            detail += (
                f", top_score={top.get('score', 0):.3f}, "
                f"title={top.get('document_title', '')!r}"
            )
        return TestResult(name, ok, elapsed, detail), results
    except Exception as exc:
        return TestResult(name, False, _elapsed_ms(start), str(exc)), []


def print_summary_table(results: list[TestResult]) -> None:
    print()
    print("=" * 90)
    print(f"{'TEST':<32} {'RESULT':<8} {'TIME (ms)':>10}  DETAILS")
    print("-" * 90)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{result.name:<32} {status:<8} {result.elapsed_ms:>10.0f}  {result.detail}"
        )
    print("=" * 90)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        print("Some tests failed. Is the backend running?")
        print(f"  uvicorn main:app --reload --port 8000")
        print(f"  API_BASE_URL={BASE_URL}")


def print_search_table(results: list[dict[str, Any]]) -> None:
    if not results:
        return
    print()
    print("Search results (top 5):")
    print("-" * 90)
    print(f"{'#':<3} {'SCORE':>6}  {'SOURCE':<8}  {'TITLE':<30}  SNIPPET")
    print("-" * 90)
    for i, hit in enumerate(results[:5], start=1):
        score = hit.get("score", 0)
        source = hit.get("source_type", "")
        title = (hit.get("document_title") or "")[:30]
        snippet = (hit.get("text") or "").replace("\n", " ")[:60]
        print(f"{i:<3} {score:>6.3f}  {source:<8}  {title:<30}  {snippet}...")
    print("-" * 90)


def main() -> int:
    print(f"API base URL: {BASE_URL}\n")

    health = test_health()
    pdf = test_ingest_pdf()
    url = test_ingest_url()
    search, search_hits = test_search()

    all_results = [health, pdf, url, search]
    print_summary_table(all_results)
    print_search_table(search_hits)

    return 0 if all(r.passed for r in all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
