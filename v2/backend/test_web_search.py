"""Test web_search hardening (P3.4): max_results, network-error vs zero-results,
fetch_content. Pure unit — monkeypatches requests, no Docker / no network.
"""
import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def _noop_ws(_m):
    pass


def _make_html(n):
    blocks = ""
    for i in range(n):
        blocks += f'''
        <div class="result ">
          <h2 class="result__title"><a href="https://ex{i}.com">Title {i}</a></h2>
          <a class="result__snippet">Snippet {i} text</a>
        </div>'''
    return f"<html><body>{blocks}</body></html>"


async def run():
    import app.agent.builtin_tools as bt

    failures = []
    session = types.SimpleNamespace(container_id="x", id="sweb")

    class Resp:
        def __init__(self, text, status=200):
            self.text = text; self.status_code = status
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    # monkeypatch requests inside the handler's module-level import
    import requests as real_requests
    orig_post = real_requests.post
    orig_get = real_requests.get

    try:
        # Case 1: max_results honored (HTML has 8, ask for 5)
        real_requests.post = lambda *a, **k: Resp(_make_html(8))
        r = await bt.handle_web_search(session, {"query": "q", "max_results": 5}, _noop_ws, None)
        n = r.count("URL: ")
        if n != 5:
            failures.append(f"Case1 max_results: expected 5 URLs, got {n}")
        else:
            print("[1] max_results=5 honored: PASS")

        # Case 2: zero results → distinct no-results message (not network error)
        real_requests.post = lambda *a, **k: Resp("<html><body>nothing</body></html>")
        r = await bt.handle_web_search(session, {"query": "zzz"}, _noop_ws, None)
        if "No results found" not in r or "NETWORK ERROR" in r:
            failures.append(f"Case2 zero-results: {r!r}")
        else:
            print("[2] zero results → 'No results found' (not network err): PASS")

        # Case 3: network error → distinct network-error message
        def boom(*a, **k):
            raise ConnectionError("dns fail")
        real_requests.post = boom
        r = await bt.handle_web_search(session, {"query": "q"}, _noop_ws, None)
        if "SEARCH NETWORK ERROR" not in r:
            failures.append(f"Case3 network-error: {r!r}")
        else:
            print("[3] network failure → SEARCH NETWORK ERROR (distinct): PASS")

        # Case 4: fetch_content pulls top-result body
        real_requests.post = lambda *a, **k: Resp(_make_html(2))
        real_requests.get = lambda *a, **k: Resp("<html><body><p>DEEP CONTENT HERE</p></body></html>")
        r = await bt.handle_web_search(session, {"query": "q", "fetch_content": True}, _noop_ws, None)
        if "DEEP CONTENT HERE" not in r:
            failures.append(f"Case4 fetch_content: {r!r}")
        else:
            print("[4] fetch_content → top result body fetched: PASS")

    finally:
        real_requests.post = orig_post
        real_requests.get = orig_get

    print()
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
