"""
Built-in tool handlers — extracted from loop.py's _do_execute_tool().

Each handler follows the uniform signature:
    async def handler(session, tool_input, ws_send, cancel_event) -> str

Registration function at the bottom wires all handlers + schemas into ToolRegistry.
"""

import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------

async def handle_shell_exec(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.tools import requires_approval, truncate_output
    from app.deps import _docker_manager

    command = tool_input.get("command", "")
    if requires_approval(command):
        request_id = uuid.uuid4().hex[:8]
        await ws_send({
            "type": "approval_request",
            "request_id": request_id,
            "action": "shell_exec",
            "command": command,
            "risk_level": "medium",
        })
        from app.agent.loop import _wait_for_approval
        approval = await _wait_for_approval(request_id)
        if not approval.get("approved"):
            return "Command rejected by user."
        command = approval.get("modified_command") or command

    # Optional working directory — convenience so the agent needn't prefix every
    # command with `cd` (each shell_exec is a fresh shell). Quoted to stay safe.
    cwd = tool_input.get("cwd")
    if cwd:
        import shlex as _shlex
        command = f"cd {_shlex.quote(str(cwd))} && {command}"

    # Generous default ceiling (15 min) so long but legit ops (pip/apt installs,
    # builds) aren't killed, while still preventing an infinite hang. The agent
    # can pass a smaller `timeout` for quick checks.
    try:
        timeout = int(tool_input.get("timeout", 900))
    except (TypeError, ValueError):
        timeout = 900

    exec_id = uuid.uuid4().hex[:8]

    # Stream output LIVE to the UI as it arrives, AND capture the real exit code at
    # the end. cancel_check lets the user abort mid-run. coreutils `timeout` (inside
    # exec_command_stream) actually kills a hung process, so we never block forever.
    def _cancelled():
        return cancel_event is not None and cancel_event.is_set()

    # Memory cap: a command that prints forever (e.g. `yes`, `cat /dev/urandom`)
    # would otherwise grow output_parts until the backend OOMs. We still STREAM
    # every chunk live to the UI, but only RETAIN up to _MAX_RETAIN bytes in RAM
    # (head + tail) for the agent's return value.
    _MAX_RETAIN = 256 * 1024  # 256 KB kept in memory for the return string
    output_parts = []
    retained_bytes = 0
    overflow_bytes = 0
    exit_code = -1
    timed_out = False
    cancelled = False
    stream_error = None
    try:
        async for stype, chunk in _docker_manager.exec_command_stream(
            session.container_id, command, timeout=timeout, cancel_check=_cancelled
        ):
            if stype == "__cancelled__":
                cancelled = True
                break
            if stype == "__error__":
                stream_error = chunk
                break
            if stype == "__done__":
                code_str, to_str = chunk.split("|", 1)
                exit_code = int(code_str) if code_str.lstrip("-").isdigit() else -1
                timed_out = to_str == "1"
                break
            # Always stream live to UI; retain in RAM only up to the cap.
            await ws_send({"type": "terminal_output", "exec_id": exec_id, "content": chunk, "stream": stype, "done": False})
            if retained_bytes < _MAX_RETAIN:
                output_parts.append(chunk)
                retained_bytes += len(chunk)
            else:
                overflow_bytes += len(chunk)
    except Exception as e:
        stream_error = f"{type(e).__name__}: {e}"

    await ws_send({"type": "terminal_output", "exec_id": exec_id, "content": "", "stream": "stdout", "done": True})

    if cancelled:
        partial = "".join(output_parts)
        return f"[CANCELLED by user]\n{partial[-2000:]}" if partial else "[CANCELLED by user before any output]"
    if stream_error is not None:
        return f"shell_exec error: {stream_error}"

    full_output = "".join(output_parts)
    if overflow_bytes:
        full_output += f"\n...[{overflow_bytes} bytes of further output dropped — command produced too much; redirect to a file and read_file instead]"
    truncated, was_truncated = truncate_output(full_output)
    status_tag = f"[exit_code={exit_code}]" + (f" [TIMED OUT after {timeout}s — partial output above]" if timed_out else "")

    if was_truncated:
        # Save the full output via tar (copy_file_to) — NOT heredoc, so output
        # containing any marker string can no longer break the write.
        output_path = f"/tmp/output_{exec_id}.txt"
        try:
            await _docker_manager.copy_file_to(session.container_id, full_output.encode("utf-8"), output_path)
            await ws_send({
                "type": "file_ready",
                "path": output_path,
                "download_url": f"/api/sessions/{session.id}/files{output_path}",
                "size_bytes": len(full_output.encode()),
            })
            saved = f"\n\n[Full output ({len(full_output.splitlines())} lines) saved to {output_path}]"
        except Exception as e:
            saved = f"\n\n[Could not save full output: {e}]"
        return f"{status_tag}\n{truncated}{saved}"

    body = full_output if full_output else "(no output)"
    return f"{status_tag}\n{body}"


_MAX_WRITE_BYTES = 10 * 1024 * 1024  # 10 MB cap to avoid filling the container


async def handle_write_file(session, tool_input, ws_send, cancel_event) -> str:
    import shlex

    from app.deps import _docker_manager

    raw_path = tool_input.get("path", "") or "/workspace/file.txt"
    content = tool_input.get("content", "")
    mode = (tool_input.get("mode") or "overwrite").strip().lower()

    # #2 — Resolve relative paths against /workspace (copy_file_to needs an absolute
    # path; agents frequently pass 'rel.txt'). Reject obviously bad input clearly.
    path = raw_path.strip()
    if not path:
        path = "/workspace/file.txt"
    if not path.startswith("/"):
        path = "/workspace/" + path
    qpath = shlex.quote(path)

    data = content.encode("utf-8")

    # #1 — APPEND mode: read existing content first, then write old+new (copy_file_to
    # only overwrites). Done in-tool so the byte-faithful, injection-safe tar path is kept.
    prefix = b""
    if mode == "append":
        try:
            existing = await _docker_manager.copy_file_from(session.container_id, path)
            if isinstance(existing, (bytes, bytearray)):
                prefix = bytes(existing)
        except Exception:
            prefix = b""  # file doesn't exist yet → append == create
    final = prefix + data
    n = len(final)

    if n > _MAX_WRITE_BYTES:
        return (
            f"WRITE FAILED: resulting content is {n} bytes, exceeds the {_MAX_WRITE_BYTES} byte "
            f"(10 MB) limit for {path}. Split the file or write incrementally."
        )

    # #4 — Note if we're overwriting an existing file (so the agent knows old data is gone).
    overwrite_note = ""
    if mode != "append":
        try:
            ec_old, old_sz = await _docker_manager.exec_command_simple(
                session.container_id, f"stat -c %s -- {qpath} 2>/dev/null"
            )
            if old_sz.strip().isdigit() and int(old_sz.strip()) > 0:
                overwrite_note = f" (overwrote existing file, was {int(old_sz.strip())} bytes)"
        except Exception:
            pass

    # Write via tar/put_archive (copy_file_to) — NO shell, injection-safe.
    try:
        await _docker_manager.copy_file_to(session.container_id, final, path)
    except Exception as e:
        return (
            f"WRITE FAILED: cannot write to {path} — {type(e).__name__}. "
            f"Check the path is a writable absolute location (e.g. under /workspace)."
        )

    # #3 — Verify by READING THE FILE BACK and comparing real bytes, not just size.
    # Size-only verification is "self-fulfilling" for append (n is derived from the
    # bytes we just assembled). Reading back proves the content truly landed:
    #   - whole file must equal `final`, and
    #   - for append, the TAIL must equal exactly the data we added (proves the new
    #     data is present at the end, not silently lost or mis-placed).
    try:
        readback = await _docker_manager.copy_file_from(session.container_id, path)
        readback = bytes(readback) if isinstance(readback, (bytes, bytearray)) else None
    except Exception:
        readback = None

    if readback is None:
        return (
            f"WRITE FAILED: {path} — wrote without error but the file is not readable "
            f"afterward (likely a read-only or special filesystem). Pick a writable path under /workspace."
        )
    if readback != final:
        return (
            f"WRITE MISMATCH: {path} — on-disk content ({len(readback)} bytes) differs from what was "
            f"written ({n} bytes). The write may have been truncated or interleaved with another write."
        )
    if mode == "append" and data and not readback.endswith(data):
        return (
            f"APPEND MISMATCH: {path} — the appended data is not at the end of the file on disk. "
            f"The append may have failed or the file changed concurrently."
        )

    verb = "appended to" if mode == "append" else "written"
    return f"File {verb}: {path} ({n} bytes, verified by readback){overwrite_note}"


async def handle_read_file(session, tool_input, ws_send, cancel_event) -> str:
    import shlex

    from app.deps import _docker_manager

    raw_path = tool_input.get("path", "") or ""
    if not raw_path.strip():
        return "READ ERROR: no path provided."
    # Resolve relative paths under /workspace (consistent with write_file).
    path = raw_path.strip()
    if not path.startswith("/"):
        path = "/workspace/" + path
    try:
        max_lines = int(tool_input.get("max_lines", 200))
    except (TypeError, ValueError):
        max_lines = 200
    try:
        offset = int(tool_input.get("offset", 1))
    except (TypeError, ValueError):
        offset = 1
    if offset < 1:
        offset = 1
    # Soft size cap (chars) — default 50KB so a huge file can't flood the LLM
    # context. The agent can override with max_bytes for large logs/dumps.
    try:
        max_bytes = int(tool_input.get("max_bytes", 50000))
    except (TypeError, ValueError):
        max_bytes = 50000
    line_numbers = bool(tool_input.get("line_numbers", False))
    qpath = shlex.quote(path)

    # Distinguish missing file from empty file via test -f exit code.
    ec, _ = await _docker_manager.exec_command_simple(
        session.container_id, f"test -f {qpath}"
    )
    if ec != 0:
        ec_dir, _ = await _docker_manager.exec_command_simple(session.container_id, f"test -d {qpath}")
        if ec_dir == 0:
            return f"READ ERROR: {path} is a directory, not a file."
        return f"FILE NOT FOUND: {path}"

    # Byte size of the file.
    _, sz_out = await _docker_manager.exec_command_simple(session.container_id, f"wc -c < {qpath}")
    try:
        nbytes = int(sz_out.strip())
    except ValueError:
        nbytes = 0
    if nbytes == 0:
        return f"[{path}: empty file (0 bytes)]\n(empty file)"

    # Binary detection: grep -qI returns non-zero if the file looks binary (has NUL
    # bytes). Refuse to dump binary into the context — it's useless to the LLM and
    # produces a misleading line count.
    ec_bin, _ = await _docker_manager.exec_command_simple(
        session.container_id, f"grep -qI . {qpath}"
    )
    if ec_bin != 0:
        return (
            f"[{path}: BINARY file, {nbytes} bytes] — not shown as text (would corrupt context). "
            f"To inspect it, use shell_exec with `file {path}`, `xxd {path} | head`, or `hexdump -C {path} | head`."
        )

    # Total line count (for "more below" hint). wc -l counts newlines; a final line
    # without trailing newline isn't counted, so floor at 1 for a non-empty file.
    _, wc_out = await _docker_manager.exec_command_simple(session.container_id, f"wc -l < {qpath}")
    try:
        total_lines = max(int(wc_out.strip()), 1)
    except ValueError:
        total_lines = -1

    # Read window: lines [offset .. offset+max_lines-1].
    if line_numbers:
        read_cmd = f"cat -n {qpath} | tail -n +{offset} | head -n {max_lines}"
    else:
        read_cmd = f"tail -n +{offset} {qpath} | head -n {max_lines}"
    _, output = await _docker_manager.exec_command_simple(session.container_id, read_cmd)

    end_line = offset + max(0, len(output.splitlines()) - 1) if output else offset
    total_str = str(total_lines) if total_lines >= 0 else "?"
    header = f"[{path}: lines {offset}-{end_line} of {total_str}]"
    if total_lines >= 0 and end_line < total_lines:
        header += f" — {total_lines - end_line} more line(s) below (use offset={end_line + 1})"

    # Soft byte cap: even within max_lines, a single very long line can be huge.
    # Truncate the returned text and tell the agent how to get more.
    body = output
    if len(body) > max_bytes:
        body = body[:max_bytes] + (
            f"\n...[output truncated at {max_bytes} chars of {nbytes}-byte file — "
            f"raise max_bytes, use offset, or grep for specifics]"
        )

    return f"{header}\n{body}" if output else f"{header}\n(no lines in this range)"


# User-Agents rotated on retry / across engines to dodge simple bot-blocks.
_WEB_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]
_FALLBACK_HOSTS = {"youtube.com", "google.com", "bing.com", "facebook.com",
                   "duckduckgo.com", "amazon.com", "wikipedia.org"}


def _extract_main_text(html_text: str, limit: int = 4000) -> str:
    """Strip boilerplate from an HTML page and return the main visible text."""
    from lxml import html as _h
    tree = _h.fromstring(html_text)
    for bad in tree.xpath('//script | //style | //nav | //footer | //header | //noscript | //svg'):
        try:
            bad.getparent().remove(bad)
        except Exception:
            pass
    text = " ".join(tree.xpath('//body//text()'))
    return " ".join(text.split())[:limit]


async def _ddg_search(query: str, ua: str):
    """DuckDuckGo HTML endpoint. Returns list of (title, link, snippet) or raises."""
    import urllib.parse
    import requests
    from lxml import html
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    resp = await asyncio.to_thread(
        requests.post, url, headers={"User-Agent": ua}, data={"q": query}, timeout=12
    )
    resp.raise_for_status()
    tree = html.fromstring(resp.text)
    out = []
    for r in tree.xpath('//div[contains(@class, "result ")]'):
        t = r.xpath('.//h2[@class="result__title"]/a')
        sn = r.xpath('.//a[@class="result__snippet"]')
        if not t or not sn:
            continue
        title = "".join(t[0].itertext()).strip()
        link = t[0].get("href")
        snippet = "".join(sn[0].itertext()).strip()
        if link and link.startswith("//duckduckgo.com/l/?uddg="):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
            link = qs.get("uddg", [link])[0]
        out.append((title, link, snippet))
    return out


async def _ddg_lite_search(query: str, ua: str):
    """DuckDuckGo Lite — different markup, survives when the HTML endpoint blocks."""
    import urllib.parse
    import requests
    from lxml import html
    url = "https://lite.duckduckgo.com/lite/"
    resp = await asyncio.to_thread(
        requests.post, url, headers={"User-Agent": ua}, data={"q": query}, timeout=12
    )
    resp.raise_for_status()
    tree = html.fromstring(resp.text)
    out = []
    links = tree.xpath('//a[contains(@class,"result-link")]')
    snippets = tree.xpath('//td[contains(@class,"result-snippet")]')
    for i, a in enumerate(links):
        title = "".join(a.itertext()).strip()
        link = a.get("href")
        snippet = "".join(snippets[i].itertext()).strip() if i < len(snippets) else ""
        out.append((title, link, snippet))
    return out


# --- Firecrawl (self-hosted): anti-detection scrape/search/map/crawl --------
def _firecrawl_headers():
    from app.config import settings
    h = {"Content-Type": "application/json"}
    if settings.firecrawl_api_key:
        h["Authorization"] = f"Bearer {settings.firecrawl_api_key}"
    return h


async def _firecrawl_scrape(url: str, limit: int = 8000, page_headers: dict | None = None,
                            actions: list | None = None) -> str | None:
    """Scrape one URL via Firecrawl (renders JS, rotates proxy). Returns markdown
    or None if Firecrawl is unavailable (caller falls back to plain requests).

    AUTH support:
      - page_headers: sent to the TARGET page (e.g. {"Authorization":"Bearer ..."} or
        {"Cookie":"session=..."}) → access token/cookie-gated pages.
      - actions: Firecrawl browser actions (wait/click/write/press) → drive a login
        form before scraping, e.g. type user/pass → click submit → wait → scrape.
    """
    import requests
    from app.config import settings
    if not settings.firecrawl_url:
        return None
    payload = {"url": url, "formats": ["markdown"]}
    if page_headers:
        payload["headers"] = page_headers
    if actions:
        payload["actions"] = actions
    try:
        r = await asyncio.to_thread(
            requests.post, f"{settings.firecrawl_url.rstrip('/')}/v1/scrape",
            headers=_firecrawl_headers(), json=payload, timeout=90,
        )
        r.raise_for_status()
        md = (r.json().get("data") or {}).get("markdown", "")
        return md[:limit] if md else ""
    except Exception:
        return None


async def _firecrawl_search(query: str, ua: str):
    """Search via Firecrawl /v1/search. Returns (title, link, snippet) list or raises."""
    import requests
    from app.config import settings
    r = await asyncio.to_thread(
        requests.post, f"{settings.firecrawl_url.rstrip('/')}/v1/search",
        headers=_firecrawl_headers(), json={"query": query, "limit": 8}, timeout=45,
    )
    r.raise_for_status()
    data = r.json().get("data") or []
    out = []
    for it in data:
        out.append((it.get("title", ""), it.get("url", ""), it.get("description", "") or it.get("snippet", "")))
    return out


async def handle_web_search(session, tool_input, ws_send, cancel_event) -> str:
    import urllib.parse
    import requests

    query = tool_input.get("query", "")
    direct_url = tool_input.get("url", "")  # if set → fetch this URL directly, no search
    page_headers = tool_input.get("headers") or None   # auth: Bearer/Cookie to target page
    actions = tool_input.get("actions") or None         # auth: login flow (wait/click/write/press)
    try:
        max_results = int(tool_input.get("max_results", 3))
    except (TypeError, ValueError):
        max_results = 3
    max_results = max(1, min(max_results, 10))
    fetch_content = bool(tool_input.get("fetch_content", False))

    # ---- Mode B: direct URL fetch (for known/important sources search can't surface) ----
    if direct_url:
        if not direct_url.startswith(("http://", "https://")):
            direct_url = "https://" + direct_url
        # Prefer Firecrawl (renders JS, rotates proxy, beats anti-bot, supports auth
        # via headers/actions). Falls back to plain requests if Firecrawl unavailable.
        fc = await _firecrawl_scrape(direct_url, limit=8000, page_headers=page_headers, actions=actions)
        if fc:
            await ws_send({"type": "agent_retrieval", "query": f"[firecrawl] {direct_url}",
                           "results": [{"title": direct_url, "url": direct_url, "snippet": fc[:200]}], "count": 1})
            return f"**[Content of {direct_url} — via Firecrawl/JS-render]**\n{fc}"
        last_err = None
        for ua in _WEB_UAS:
            try:
                page = await asyncio.to_thread(
                    requests.get, direct_url, headers={"User-Agent": ua}, timeout=15
                )
                page.raise_for_status()
                text = _extract_main_text(page.text, limit=8000)
                await ws_send({"type": "agent_retrieval", "query": f"[fetch] {direct_url}",
                               "results": [{"title": direct_url, "url": direct_url, "snippet": text[:200]}], "count": 1})
                if not text.strip():
                    return f"[Fetched {direct_url} — HTTP {page.status_code}] but no readable text (likely JS-rendered or login/captcha wall — enable Firecrawl for this)."
                return f"**[Content of {direct_url}]**\n{text}"
            except Exception as e:
                last_err = e
        return (
            f"FETCH FAILED: {direct_url} — {type(last_err).__name__}: {last_err}. "
            f"The page may require login/captcha/JS. If you have credentials, use shell_exec with curl + auth headers."
        )

    if not query.strip():
        return "No query provided. Pass `query` to search, or `url` to fetch a page directly."

    q_lower = query.lower()

    def _is_junk(link: str) -> bool:
        if not link:
            return True
        # DuckDuckGo ad/redirect links (y.js?ad_domain=...) are sponsored, not real results.
        if "duckduckgo.com/y.js" in link or "ad_provider=" in link or "ad_domain=" in link:
            return True
        try:
            host = urllib.parse.urlparse(link).netloc.lower()
        except Exception:
            return False
        if host.startswith("www."):
            host = host[4:]
        root = ".".join(host.split(".")[-2:]) if host else ""
        if root in _FALLBACK_HOSTS and root.split(".")[0] not in q_lower:
            return urllib.parse.urlparse(link).path.strip("/") == ""
        return False

    # ---- Mode A: search with multi-engine fallback + UA rotation ----
    # Firecrawl first (best quality + anti-bot) when configured, then free DDG fallbacks.
    from app.config import settings as _st
    engines = []
    if _st.firecrawl_url:
        engines.append(("firecrawl", _firecrawl_search))
    engines += [("duckduckgo", _ddg_search), ("ddg-lite", _ddg_lite_search)]
    raw, engine_used, errors = [], None, []
    for ename, efn in engines:
        for ua in _WEB_UAS:
            try:
                hits = await efn(query, ua)
                if hits:
                    raw, engine_used = hits, ename
                    break
            except Exception as e:
                errors.append(f"{ename}: {type(e).__name__}")
        if raw:
            break

    if not raw and errors:
        await ws_send({"type": "agent_retrieval", "query": query, "results": [], "count": 0, "error": "; ".join(errors[:4])})
        return (
            f"SEARCH NETWORK ERROR — all engines failed ({'; '.join(errors[:4])}). "
            f"Retry shortly, or use `url` to fetch a specific page directly."
        )

    # Dedup by host+path, drop junk fallback homepages.
    results, structured, filtered_junk, seen = [], [], 0, set()
    for title, link, snippet in raw:
        if _is_junk(link or ""):
            filtered_junk += 1
            continue
        key = (link or "").split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        results.append(f"**{title}**\n{snippet}\nURL: {link}")
        structured.append({"title": title, "url": link, "snippet": snippet[:200]})
        if len(results) >= max_results:
            break

    # Optional: fetch full text of the top result.
    if fetch_content and structured:
        top_url = structured[0]["url"]
        try:
            page = await asyncio.to_thread(requests.get, top_url, headers={"User-Agent": _WEB_UAS[0]}, timeout=12)
            page.raise_for_status()
            results.append(f"**[Full content of top result: {top_url}]**\n{_extract_main_text(page.text)}")
        except Exception as e:
            results.append(f"**[Could not fetch top result content: {type(e).__name__}]**")

    await ws_send({"type": "agent_retrieval", "query": query, "results": structured, "count": len(structured)})

    if not results:
        if filtered_junk:
            return (
                f"No relevant results for {query!r} — only generic fallback pages were filtered out. "
                f"Rephrase with specifics. NOTE: these engines can't reach login/captcha/JS sources — "
                f"use `url` to fetch a known page directly."
            )
        return f"No results found for {query!r} (0 hits). Try rephrasing."
    header = f"[engine: {engine_used}]"
    tail = f"\n\n[{filtered_junk} fallback result(s) filtered out]" if filtered_junk else ""
    return f"{header}\n" + "\n\n---\n\n".join(results) + tail


async def handle_site_map(session, tool_input, ws_send, cancel_event) -> str:
    """List all URLs of a site via Firecrawl /v1/map — attack-surface recon."""
    import requests
    from app.config import settings
    if not settings.firecrawl_url:
        return "site_map requires Firecrawl (not configured). Use web_search instead."
    url = tool_input.get("url", "").strip()
    if not url:
        return "site_map: provide `url` (the site to map)."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        limit = int(tool_input.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    await ws_send({"type": "agent_status", "tool": "site_map", "detail": url})
    try:
        r = await asyncio.to_thread(
            requests.post, f"{settings.firecrawl_url.rstrip('/')}/v1/map",
            headers=_firecrawl_headers(), json={"url": url, "limit": limit}, timeout=60,
        )
        r.raise_for_status()
        links = r.json().get("links") or r.json().get("data") or []
        urls = [l if isinstance(l, str) else l.get("url", "") for l in links]
        urls = [u for u in urls if u][:limit]
    except Exception as e:
        return f"SITE_MAP FAILED for {url}: {type(e).__name__}: {e}"
    if not urls:
        return f"SITE_MAP: no URLs discovered for {url}."
    return f"[site_map {url} — {len(urls)} URLs]\n" + "\n".join(urls)


async def handle_crawl_site(session, tool_input, ws_send, cancel_event) -> str:
    """Crawl a site (multiple pages → markdown) via Firecrawl /v1/crawl, poll to done."""
    import requests
    from app.config import settings
    if not settings.firecrawl_url:
        return "crawl_site requires Firecrawl (not configured)."
    url = tool_input.get("url", "").strip()
    if not url:
        return "crawl_site: provide `url`."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        limit = int(tool_input.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    try:
        max_depth = int(tool_input.get("max_depth", 2))
    except (TypeError, ValueError):
        max_depth = 2
    base = settings.firecrawl_url.rstrip("/")
    await ws_send({"type": "agent_status", "tool": "crawl_site", "detail": f"{url} (limit {limit})"})
    try:
        r = await asyncio.to_thread(
            requests.post, f"{base}/v1/crawl", headers=_firecrawl_headers(),
            json={"url": url, "limit": limit, "maxDepth": max_depth, "scrapeOptions": {"formats": ["markdown"]}}, timeout=30,
        )
        r.raise_for_status()
        job_id = r.json().get("id")
        if not job_id:
            return f"CRAWL FAILED: no job id returned ({r.text[:160]})"
        # Poll up to ~3 min.
        for _ in range(36):
            await asyncio.sleep(5)
            s = await asyncio.to_thread(requests.get, f"{base}/v1/crawl/{job_id}", headers=_firecrawl_headers(), timeout=30)
            s.raise_for_status()
            sj = s.json()
            if sj.get("status") == "completed":
                pages = sj.get("data") or []
                out = [f"[crawl {url} — {len(pages)} pages]"]
                for p in pages[:limit]:
                    md = (p.get("markdown") or "")[:1500]
                    src = (p.get("metadata") or {}).get("sourceURL", "")
                    out.append(f"### {src}\n{md}")
                return "\n\n---\n\n".join(out)
            if sj.get("status") == "failed":
                return f"CRAWL FAILED: {sj.get('error', 'unknown')}"
        return f"CRAWL TIMEOUT: job {job_id} still running after 3min. Try a smaller limit."
    except Exception as e:
        return f"CRAWL FAILED for {url}: {type(e).__name__}: {e}"


async def handle_think(session, tool_input, ws_send, cancel_event) -> str:
    thought = tool_input.get("thought", "")
    # Stream thinking content to frontend for real-time display
    await ws_send({
        "type": "agent_thinking",
        "content": thought,
        "done": False,
    })
    await ws_send({
        "type": "agent_thinking",
        "content": "",
        "done": True,
    })
    return "[Thought recorded]"


async def handle_verify_work(session, tool_input, ws_send, cancel_event) -> str:
    """Run a verification test against a success criterion.

    Ground truth is the test command's EXIT CODE (0 = pass), not keyword guessing.
    Optional assert_mode lets the caller verify in a specific way:
      - "exit_code" (default): pass iff exit == 0 (or == int(expected) if given)
      - "contains":  pass iff `expected` substring appears in output (and ran ok)
      - "regex":     pass iff re.search(expected, output)
    A timeout (default 60s) prevents a hung test from blocking the loop.
    """
    import re as _re

    from app.agent.tools import truncate_output
    from app.deps import _docker_manager

    criterion = tool_input.get("criterion", "")
    test_command = tool_input.get("test_command", "")
    expected = tool_input.get("expected", "") or ""
    assert_mode = (tool_input.get("assert_mode") or "exit_code").strip().lower()
    try:
        timeout = int(tool_input.get("timeout", 60))
    except (TypeError, ValueError):
        timeout = 60

    await ws_send({
        "type": "agent_status",
        "tool": "verify_work",
        "detail": f"Verifying: {criterion[:60]}",
    })

    if not test_command:
        return (
            f"VERIFY [{criterion}]: NO TEST COMMAND PROVIDED. "
            f"You must provide a concrete test_command (shell command that proves the criterion)."
        )

    # Run with real exit-code capture + timeout enforcement.
    try:
        exit_code, full_output, timed_out = await _docker_manager.exec_command_capture(
            session.container_id, test_command, timeout=timeout
        )
    except Exception as e:
        return f"VERIFY [{criterion}]: ERROR running test — {type(e).__name__}: {e}"

    # Stream the captured output to the UI terminal for transparency.
    exec_id = uuid.uuid4().hex[:8]
    await ws_send({"type": "terminal_output", "exec_id": exec_id, "content": full_output, "stream": "stdout", "done": False})
    await ws_send({"type": "terminal_output", "exec_id": exec_id, "content": "", "stream": "stdout", "done": True})

    truncated, _ = truncate_output(full_output)
    out_lower = full_output.lower()
    keyword_hit = any(m in out_lower for m in ["error", "traceback", "exception", "failed", "assertionerror"])

    # --- Verdict (exit code is ground truth) ---
    # ERROR (distinct from FAIL): the verification itself is mis-configured — the
    # agent's *input* is wrong, not the work under test. Surfaced so the agent
    # fixes the verify call instead of mistaking it for a failing criterion.
    _KNOWN_MODES = {"exit_code", "contains", "regex"}
    if timed_out:
        verdict = "FAIL"
        detail = f"Test TIMED OUT after {timeout}s (exit {exit_code}). Likely a hang or missing input."
    elif assert_mode not in _KNOWN_MODES:
        verdict = "ERROR"
        detail = (
            f"Unknown assert_mode '{assert_mode}'. Use one of: exit_code (default), "
            f"contains, regex. Re-call verify_work with a valid assert_mode."
        )
    elif assert_mode in ("contains", "regex") and not expected.strip():
        # Empty `expected` makes contains trivially PASS (''-in-anything) and regex
        # match-anything — a silent false-PASS. Force the agent to supply it.
        verdict = "ERROR"
        detail = (
            f"assert_mode={assert_mode} requires a non-empty `expected` value to check against. "
            f"Provide the substring/pattern that proves the criterion, or use assert_mode=exit_code."
        )
    elif assert_mode == "contains":
        ok = expected.lower() in out_lower
        verdict = "PASS" if ok else "FAIL"
        detail = f"assert_mode=contains: expected '{expected}' {'FOUND' if ok else 'NOT FOUND'} (exit {exit_code})."
    elif assert_mode == "regex":
        try:
            ok = bool(_re.search(expected, full_output))
            verdict = "PASS" if ok else "FAIL"
            detail = f"assert_mode=regex: /{expected}/ {'MATCHED' if ok else 'NO MATCH'} (exit {exit_code})."
        except _re.error as e:
            # Bad pattern = agent typo, not a failing criterion → ERROR, not FAIL.
            verdict = "ERROR"
            detail = f"assert_mode=regex: INVALID pattern /{expected}/ — {e}. Fix the regex and re-verify."
    else:
        # exit_code mode (default). If `expected` is an int, require that exact code.
        target = 0
        if expected.strip().lstrip("-").isdigit():
            target = int(expected.strip())
        ok = exit_code == target
        verdict = "PASS" if ok else "FAIL"
        detail = f"assert_mode=exit_code: exit {exit_code} (expected {target})."
        # Secondary advisory only — never overrides the exit-code verdict.
        if ok and keyword_hit:
            detail += " NOTE: output contains error-like words but exit code is success — review if this is truly OK."

    if verdict == "ERROR":
        footer = (
            "NOTE: This is a verify_work CONFIGURATION error, NOT a failed criterion. "
            "The work under test was NOT evaluated. Fix the verify_work call above and re-run."
        )
    else:
        footer = (
            "NOTE: Verdict is based on the EXIT CODE (ground truth). Review the output too. "
            "If NOT genuinely met, fix and re-verify. Do NOT report completion until all criteria PASS."
        )
    return (
        f"VERIFY [{criterion}]: {verdict}  [exit_code={exit_code}]\n"
        f"Assessment: {detail}\n"
        f"--- Test Output ---\n{truncated}\n"
        f"--- End Output ---\n"
        f"{footer}"
    )


async def handle_verify_webapp(session, tool_input, ws_send, cancel_event) -> str:
    """Prove a running web app is genuinely USABLE by issuing real HTTP requests
    against localhost:8080 INSIDE the container and asserting on the RESPONSE BODY
    (not just status 200). Ported from Nexus dev_server._wait_for_ready pattern.

    A blank-200 page or a server that returns errors on real user input will FAIL,
    which is exactly the "has a UI but doesn't work" failure mode we must catch.
    """
    import json as _json
    from app.agent.tools import truncate_output
    from app.deps import _docker_manager

    base_url = tool_input.get("app_url", "http://localhost:8080").rstrip("/")
    journey = tool_input.get("journey", [])
    if isinstance(journey, str):
        try:
            journey = _json.loads(journey)
        except Exception:
            return "VERIFY_WEBAPP: 'journey' must be a JSON array of steps. Got an unparseable string."
    if not isinstance(journey, list) or not journey:
        return (
            "VERIFY_WEBAPP: provide a non-empty 'journey' (list of steps). Each step: "
            "{name, method?, path?, body?, assert_status?, assert_contains?, assert_not_contains?}. "
            "Include at least one real user action and assert on the RESPONSE BODY, not just status."
        )

    try:
        curl_timeout = int(tool_input.get("timeout", 15))
    except (TypeError, ValueError):
        curl_timeout = 15
    try:
        warmup_retries = int(tool_input.get("warmup_retries", 5))
    except (TypeError, ValueError):
        warmup_retries = 5
    _BODY_CAP = 200_000  # don't keep more than 200KB of a response for assertions

    await ws_send({"type": "agent_status", "tool": "verify_webapp", "detail": f"E2E {len(journey)} steps @ {base_url}"})

    def _shq(s: str) -> str:
        # safe single-quote for shell
        return "'" + str(s).replace("'", "'\\''") + "'"

    results = []
    weak_steps = []
    all_pass = True
    for i, step in enumerate(journey):
        if not isinstance(step, dict):
            results.append(f"[step {i}] SKIP — not an object")
            all_pass = False
            continue
        name = step.get("name", f"step {i}")
        method = (step.get("method") or "GET").upper()
        path = step.get("path", "/")
        url = base_url + ("" if path.startswith("/") else "/") + path
        body = step.get("body")

        # Build curl: print body, then a marker + HTTP status on its own line.
        curl = f"curl -s -m {curl_timeout} -X {method} {_shq(url)}"
        if body is not None:
            payload = body if isinstance(body, str) else _json.dumps(body, ensure_ascii=False)
            curl += f" -H 'Content-Type: application/json' -d {_shq(payload)}"
        curl += " -w '\\n__HTTP_STATUS__:%{http_code}'"

        # Warmup/retry: the app may still be booting. Retry while the status is
        # 000 (connection refused / not listening yet), with linear backoff.
        status_code = ""
        body_text = ""
        attempts = 0
        while True:
            attempts += 1
            try:
                exit_code, raw, timed_out = await _docker_manager.exec_command_capture(
                    session.container_id, curl, timeout=curl_timeout + 5
                )
            except Exception as e:
                raw = ""
            # Split body vs status marker
            status_code = ""
            body_text = raw
            if "__HTTP_STATUS__:" in raw:
                body_text, _, status_part = raw.rpartition("__HTTP_STATUS__:")
                status_code = status_part.strip()
            if status_code not in ("", "000") or attempts > warmup_retries:
                break
            await asyncio.sleep(min(attempts, 3))  # 1s,2s,3s,3s...

        if len(body_text) > _BODY_CAP:
            body_text = body_text[:_BODY_CAP] + "\n...[body truncated for assertion]"

        step_pass = True
        reasons = []

        # Server not listening / no HTTP response (after warmup retries)
        if status_code in ("", "000"):
            step_pass = False
            reasons.append(f"app not responding after {attempts} attempt(s) (status 000 — server not listening?)")

        exp_status = step.get("assert_status")
        if exp_status is not None and str(exp_status) != status_code:
            step_pass = False
            reasons.append(f"status {status_code} != expected {exp_status}")

        ac = step.get("assert_contains")
        if ac:
            for needle in ([ac] if isinstance(ac, str) else ac):
                if needle not in body_text:
                    step_pass = False
                    reasons.append(f"body missing expected text: {needle!r}")

        anc = step.get("assert_not_contains")
        if anc:
            for needle in ([anc] if isinstance(anc, str) else anc):
                if needle in body_text:
                    step_pass = False
                    reasons.append(f"body contains forbidden text: {needle!r}")

        # assert_json: body must be valid JSON; optionally check required keys /
        # key==value pairs. {"required": ["answer"], "equals": {"status": "ok"}}
        aj = step.get("assert_json")
        if aj:
            try:
                parsed = _json.loads(body_text)
                for key in aj.get("required", []):
                    if not (isinstance(parsed, dict) and key in parsed):
                        step_pass = False
                        reasons.append(f"JSON missing required key: {key!r}")
                for key, val in (aj.get("equals", {}) or {}).items():
                    if not (isinstance(parsed, dict) and parsed.get(key) == val):
                        step_pass = False
                        reasons.append(f"JSON key {key!r} != {val!r} (got {parsed.get(key)!r})")
            except Exception:
                step_pass = False
                reasons.append("body is not valid JSON (assert_json failed)")

        # Weak-check detector: a step that PASSES on status alone (no body/JSON
        # assertion) does NOT prove the app is usable — a blank-200 page passes it.
        # This is exactly the "has a UI but doesn't work" trap verify_webapp exists
        # to catch, so we flag it instead of letting a hollow PASS slip by.
        has_content_assert = bool(
            step.get("assert_contains") or step.get("assert_not_contains") or step.get("assert_json")
        )
        if step_pass and not has_content_assert:
            weak_steps.append(name)

        all_pass = all_pass and step_pass
        body_preview = body_text.strip()[:300].replace("\n", " ")
        verdict = "PASS" if step_pass else "FAIL"
        detail = "ok" if step_pass else "; ".join(reasons)
        if step_pass and not has_content_assert:
            detail += " ⚠️ WEAK: passed on status only — add assert_contains/assert_json to prove real content"
        results.append(f"[{name}] {verdict} (HTTP {status_code or 'n/a'}) — {detail}\n    body: {body_preview}")

    summary = "\n".join(results)
    overall = "PASS" if all_pass else "FAIL"
    weak_note = ""
    if weak_steps:
        weak_note = (
            f"\n⚠️ WEAK VERIFICATION: step(s) {weak_steps} passed on HTTP status ALONE — this does NOT "
            f"prove the app works (a blank page returns 200 too). Re-run with assert_contains / assert_json "
            f"on these steps to assert the REAL response content before trusting this PASS."
        )
    return (
        f"VERIFY_WEBAPP: {overall} ({sum('] PASS' in r for r in results)}/{len(journey)} steps passed)\n"
        f"{summary}{weak_note}\n"
        f"NOTE: This asserts on the actual RESPONSE BODY + user journey. "
        f"If FAIL, the app is NOT genuinely usable yet — fix the real defect (use systematic-debugging skill) and re-verify. "
        f"Do NOT report the app as done until verify_webapp PASSES."
    )


async def handle_spawn_critic(session, tool_input, ws_send, cancel_event) -> str:
    """Spawn a dedicated Critic subagent that adversarially reviews a decision/design/claim.
    Works for ANY domain — the critic auto-detects the domain and researches to verify."""
    from app.agent.loop import (
        _run_loop, _session_generation, extract_last_agent_text,
        _subagent_depth, _MAX_SUBAGENT_DEPTH,
    )
    from app.agent.prompts import build_critic_prompt
    from app.agent.tool_registry import tool_registry

    subject = tool_input.get("subject", "")        # what to critique
    context = tool_input.get("context", "")        # requirement / constraints / numbers
    claims = tool_input.get("claims", "")          # specific claims to verify

    # Depth guard — prevent unbounded nested spawning.
    depth = _subagent_depth.get(session.id, 0)
    if depth >= _MAX_SUBAGENT_DEPTH:
        return (
            f"CRITIC NOT SPAWNED: nesting depth {depth} reached the limit "
            f"({_MAX_SUBAGENT_DEPTH}). Do the critique inline instead of spawning."
        )

    await ws_send({
        "type": "agent_message",
        "content": f"🔬 **Critic Agent** — phản biện: {subject[:80]}",
        "metadata": None,
    })

    critic_task = (
        f"## Đối tượng phản biện\n{subject}\n\n"
        f"## Bối cảnh / Yêu cầu (con số cụ thể)\n{context}\n\n"
    )
    if claims:
        critic_task += f"## Các claim cần kiểm chứng\n{claims}\n\n"
    critic_task += (
        "Hãy phản biện nghiêm khắc. Với MỖI claim/lựa chọn: research (web_search) để verify, "
        "đưa verdict VALID / QUESTIONABLE / WRONG kèm bằng chứng và đề xuất sửa. "
        "Kết thúc bằng tổng kết: những gì cần thay đổi TRƯỚC khi triển khai."
    )

    critic_prompt = build_critic_prompt()
    critic_tools = tool_registry.get_tool_specs(is_subagent=True)
    sub_messages = [{"role": "user", "content": [{"text": critic_task}]}]

    _subagent_depth[session.id] = depth + 1
    try:
        await _run_loop(
            session=session,
            messages=sub_messages,
            system_prompt=critic_prompt,
            tools_list=critic_tools,
            ws_send=ws_send,
            gen=_session_generation.get(session.id, 0),
            cancel_event=cancel_event,
            is_subagent=True,
            max_iterations=40,
        )
    except Exception as e:
        _subagent_depth[session.id] = depth
        return f"CRITIC ERROR: {type(e).__name__}: {e}"
    finally:
        _subagent_depth[session.id] = depth

    verdict = extract_last_agent_text(sub_messages) or "(critic produced no textual verdict — may have hit its iteration budget)"

    # Emit structured critique event for UI
    await ws_send({
        "type": "agent_critique",
        "finding": f"Critic review: {subject[:100]}",
        "resolved": False,
    })
    await ws_send({
        "type": "agent_message",
        "content": f"🔬 **Critic hoàn thành**. Áp dụng phản biện vào thiết kế trước khi build.",
        "metadata": None,
    })
    return f"CRITIC REVIEW of '{subject}':\n{verdict}\n\n[Hãy SỬA thiết kế theo phản biện trên TRƯỚC khi tiếp tục build.]"


async def handle_ask_user(session, tool_input, ws_send, cancel_event) -> str:
    question = tool_input.get("question", "")
    options = tool_input.get("options")
    await ws_send({
        "type": "agent_question",
        "question": question,
        "options": options,
    })
    from app.agent.loop import _wait_for_user_response
    response = await _wait_for_user_response(session.id)

    # Distinguish a real timeout from an actual answer so the agent can't loop on
    # a fake answer. _wait_for_user_response returns this sentinel on timeout.
    if response in ("(no response - timeout)", "(cancelled)"):
        return (
            "ASK_USER: no answer received (timeout/cancelled). Do NOT assume an answer "
            "or re-ask in a loop. Either proceed with a clearly-stated sensible default "
            "(and say so), or stop and summarize what you need from the user."
        )

    # If options were offered, note whether the response matches one (case-insensitive,
    # trimmed). We DON'T reject free-text — the user is allowed to answer in their own
    # words — but we flag a mismatch so the agent treats it as free-form, not a choice.
    if options and isinstance(options, list):
        norm = response.strip().lower()
        matched = next((o for o in options if str(o).strip().lower() == norm), None)
        if matched is not None:
            return f"User selected option: {matched}"
        return f"User responded (free-text, not one of the offered options): {response}"

    return f"User responded: {response}"


async def handle_propose_plan(session, tool_input, ws_send, cancel_event) -> str:
    plan_id = uuid.uuid4().hex[:8]
    steps = tool_input.get("steps", [])
    for i, step in enumerate(steps):
        step["id"] = f"step_{i}"
    await ws_send({
        "type": "plan_proposal",
        "plan_id": plan_id,
        "title": tool_input.get("title", "Plan"),
        "steps": steps,
    })
    from app.agent.loop import _execute_plan_steps, _wait_for_approval
    approval = await _wait_for_approval(plan_id)
    if not approval.get("approved"):
        # Distinguish an explicit rejection from "no approver responded" (autonomous
        # / headless runs) so the agent doesn't sit blind on a rejected plan.
        if approval.get("timed_out"):
            return (
                "Plan NOT approved: no approver responded (autonomous/headless run). "
                "propose_plan needs a human approver. Instead of proposing a plan, execute "
                "the steps directly with shell_exec / write_file / verify_work."
            )
        return "Plan rejected by user."

    results = await _execute_plan_steps(session, plan_id, steps, ws_send)
    return results


async def handle_load_skill(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.skill_manager import skill_manager
    skill_id = tool_input.get("skill_id", "")
    return skill_manager.load_skill_content(skill_id)


async def handle_load_agent(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.agent_manager import agent_manager
    agent_id = tool_input.get("agent_id", "")
    return agent_manager.load_agent_content(agent_id)


async def handle_spawn_subagent(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.loop import (
        _run_loop, _session_generation, extract_last_agent_text,
        _subagent_depth, _MAX_SUBAGENT_DEPTH,
    )
    from app.agent.prompts import build_system_prompt
    from app.agent.tool_registry import tool_registry

    role_name = tool_input.get("role_name", "Subagent")
    system_prompt = tool_input.get("system_prompt", "")
    task = tool_input.get("task", "")

    depth = _subagent_depth.get(session.id, 0)
    if depth >= _MAX_SUBAGENT_DEPTH:
        return (
            f"SUBAGENT NOT SPAWNED: nesting depth {depth} reached the limit "
            f"({_MAX_SUBAGENT_DEPTH}). Do the work inline instead of spawning another agent."
        )

    await ws_send({"type": "agent_message", "content": f"\U0001f528 **Khởi tạo Sub-Agent**: `{role_name}`\n*Nhiệm vụ*: {task}", "metadata": None})

    sub_system_prompt = build_system_prompt(is_subagent=True, custom_system_prompt=system_prompt)
    sub_tools = tool_registry.get_tool_specs(is_subagent=True)

    sub_messages = [
        {"role": "user", "content": [{"text": task}]}
    ]

    _subagent_depth[session.id] = depth + 1
    try:
        await _run_loop(
            session=session,
            messages=sub_messages,
            system_prompt=sub_system_prompt,
            tools_list=sub_tools,
            ws_send=ws_send,
            gen=_session_generation.get(session.id, 0),
            cancel_event=cancel_event,
            is_subagent=True,
            max_iterations=40,
        )
    except Exception as e:
        _subagent_depth[session.id] = depth
        return f"Sub-Agent '{role_name}' ERROR: {type(e).__name__}: {e}"
    finally:
        _subagent_depth[session.id] = depth

    final_answer = extract_last_agent_text(sub_messages) or "(subagent produced no textual response — may have hit its iteration budget)"

    await ws_send({"type": "agent_message", "content": f"✅ **Sub-Agent `{role_name}` Hoàn thành**.", "metadata": None})
    return f"Sub-Agent '{role_name}' completed. Final response:\n{final_answer}"


def _pipeline_checkpoint_path(session_id: str, pipeline_name: str):
    import re
    from pathlib import Path
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", pipeline_name)[:40]
    d = Path("./data/checkpoints")
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{session_id}_{safe}.json"


def _load_pipeline_checkpoint(session_id: str, pipeline_name: str) -> dict:
    import json
    path = _pipeline_checkpoint_path(session_id, pipeline_name)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_pipeline_checkpoint(session_id: str, pipeline_name: str, state: dict):
    import json
    path = _pipeline_checkpoint_path(session_id, pipeline_name)
    try:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Checkpoint save failed: {e}")


def _clear_pipeline_checkpoint(session_id: str, pipeline_name: str):
    path = _pipeline_checkpoint_path(session_id, pipeline_name)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


async def handle_execute_pipeline(session, tool_input, ws_send, cancel_event) -> str:
    """Execute a structured pipeline of stages, each as an isolated subagent.

    Supports checkpoint/resume: progress is saved after each stage. If the same
    pipeline is re-run after a crash, completed stages are skipped.
    """
    import hashlib

    from app.agent.loop import _cancel_flags, extract_last_agent_text, _run_loop, _session_generation
    from app.agent.prompts import build_system_prompt
    from app.agent.tool_registry import tool_registry

    pipeline_name = tool_input.get("name", "Pipeline")
    stages = tool_input.get("stages", [])
    shared_context = tool_input.get("context", "")
    fail_fast = tool_input.get("fail_fast", True)
    _FINDINGS_CAP = 12000  # total accumulated findings cap (avoid context blowup)

    if not stages:
        return "Error: Pipeline must have at least one stage."

    def _stage_key(stage: dict, occurrence: int) -> str:
        # Stable key by (name, goal, occurrence). name+goal keeps resume robust to
        # REORDERING (a moved-but-unchanged stage still matches its checkpoint) and
        # re-runs an EDITED stage. `occurrence` (how many identical name+goal stages
        # came before this one) keeps the key UNIQUE when stages genuinely duplicate,
        # so duplicates no longer collapse into one checkpoint entry ("partial N/N-1").
        raw = f"{stage.get('name','')}|{stage.get('goal','')}|{occurrence}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def _occurrences(stages_list: list) -> list:
        # occurrence index of each stage among identical (name,goal) siblings before it
        seen: dict = {}
        out = []
        for st in stages_list:
            sig = (st.get("name", ""), st.get("goal", ""))
            out.append(seen.get(sig, 0))
            seen[sig] = seen.get(sig, 0) + 1
        return out

    stage_occurrences = _occurrences(stages)

    # Load checkpoint — resume from where we left off (keyed by stable stage hash)
    checkpoint = _load_pipeline_checkpoint(session.id, pipeline_name)
    completed_stages = checkpoint.get("completed", {})  # {stage_key: {...}}
    # Drop legacy index-keyed checkpoints (pre-hardening) — treat as fresh run.
    if completed_stages and all(k.isdigit() for k in completed_stages):
        completed_stages = {}
    resumed = len(completed_stages) > 0

    intro = f"🔄 **Pipeline `{pipeline_name}`** — {len(stages)} stages"
    if resumed:
        intro += f" (resume: bỏ qua {len(completed_stages)} stage đã hoàn thành)"
    await ws_send({"type": "agent_message", "content": intro, "metadata": None})

    results = []
    accumulated_findings = ""

    def _cap_findings(text: str) -> str:
        # Keep the most recent findings within the cap (drop oldest).
        if len(text) <= _FINDINGS_CAP:
            return text
        return "...[older findings truncated]\n" + text[-_FINDINGS_CAP:]

    # Restore prior results into context (in pipeline order)
    for idx, stage in enumerate(stages):
        k = _stage_key(stage, stage_occurrences[idx])
        if k in completed_stages:
            prior = completed_stages[k]
            results.append(prior["result_block"])
            accumulated_findings = _cap_findings(accumulated_findings + f"\n### {prior['name']}\n{prior['summary']}\n")

    aborted = False
    for i, stage in enumerate(stages):
        skey = _stage_key(stage, stage_occurrences[i])
        # Skip stages already completed in a prior run (checkpoint resume, by name)
        if skey in completed_stages:
            continue

        if _cancel_flags.get(session.id):
            results.append(f"Stage {i+1}: CANCELLED")
            break

        stage_name = stage.get("name", f"Stage {i+1}")
        stage_goal = stage.get("goal", "")
        stage_tools_hint = stage.get("tools_hint", "")

        await ws_send({
            "type": "agent_status",
            "tool": "pipeline",
            "detail": f"[{i+1}/{len(stages)}] {stage_name}",
        })
        await ws_send({
            "type": "agent_message",
            "content": f"▶️ **Stage {i+1}/{len(stages)}**: `{stage_name}`",
            "metadata": None,
        })

        stage_prompt = (
            f"You are executing stage '{stage_name}' of pipeline '{pipeline_name}'.\n\n"
            f"## Stage Goal\n{stage_goal}\n\n"
            f"## Shared Context\n{shared_context}\n\n"
        )
        if accumulated_findings:
            stage_prompt += f"## Findings from Previous Stages\n{accumulated_findings}\n\n"
        if stage_tools_hint:
            stage_prompt += f"## Tools Hint\n{stage_tools_hint}\n\n"
        stage_prompt += (
            "Execute this stage thoroughly. Return your findings as structured text. "
            "Be concise but comprehensive."
        )

        sub_system_prompt = build_system_prompt(is_subagent=True, custom_system_prompt=f"Pipeline stage executor: {stage_name}")
        sub_tools = tool_registry.get_tool_specs(is_subagent=True)
        sub_messages = [{"role": "user", "content": [{"text": stage_prompt}]}]

        try:
            await _run_loop(
                session=session,
                messages=sub_messages,
                system_prompt=sub_system_prompt,
                tools_list=sub_tools,
                ws_send=ws_send,
                gen=_session_generation.get(session.id, 0),
                cancel_event=cancel_event,
                is_subagent=True,
            )

            stage_result = extract_last_agent_text(sub_messages) or "(No output — stage may have hit its iteration budget)"

            result_block = f"## Stage {i+1}: {stage_name}\n{stage_result}"
            results.append(result_block)
            accumulated_findings = _cap_findings(accumulated_findings + f"\n### {stage_name}\n{stage_result[:2000]}\n")

            # Save checkpoint after successful stage (keyed by stable stage hash)
            completed_stages[skey] = {
                "name": stage_name,
                "result_block": result_block,
                "summary": stage_result[:2000],
            }
            _save_pipeline_checkpoint(session.id, pipeline_name, {"completed": completed_stages})

            await ws_send({
                "type": "agent_message",
                "content": f"✅ **Stage `{stage_name}` complete**",
                "metadata": None,
            })

        except Exception as e:
            # Do NOT advance the checkpoint past a failed stage. With fail_fast
            # (default) we stop here so the agent fixes the failure instead of
            # plowing through dependent stages on a broken foundation.
            error_msg = f"Stage '{stage_name}' failed: {type(e).__name__}: {e}"
            results.append(f"## Stage {i+1}: {stage_name}\n❌ {error_msg}")
            logger.error(f"Pipeline stage error: {error_msg}")
            if fail_fast:
                aborted = True
                results.append(
                    f"Pipeline ABORTED at stage {i+1} (fail_fast). Fix this stage, then re-run "
                    f"the pipeline — completed stages will be skipped via checkpoint."
                )
                break

    # Clear checkpoint only when ALL stages completed and we didn't abort.
    all_done = (not aborted) and len(completed_stages) == len(stages)
    if all_done:
        _clear_pipeline_checkpoint(session.id, pipeline_name)

    status = "ABORTED" if aborted else ("completed" if all_done else "partial")
    summary = f"Pipeline '{pipeline_name}' {status}: {len(completed_stages)}/{len(stages)} stages done.\n\n"
    summary += "\n\n---\n\n".join(results)
    return summary


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_all_builtins(registry) -> None:
    """Register all built-in tools into the given ToolRegistry."""
    from app.agent.tools import TOOL_DEFINITIONS

    handler_map = {
        "shell_exec": handle_shell_exec,
        "write_file": handle_write_file,
        "read_file": handle_read_file,
        "web_search": handle_web_search,
        "think": handle_think,
        "ask_user": handle_ask_user,
        "propose_plan": handle_propose_plan,
        "load_skill": handle_load_skill,
        "load_agent": handle_load_agent,
    }

    for tool_def in TOOL_DEFINITIONS:
        spec = tool_def["toolSpec"]
        name = spec["name"]
        handler = handler_map.get(name)
        if handler:
            registry.register(name, spec, handler, builtin=True, category="action")

    # execute_pipeline — structured multi-stage execution
    pipeline_spec = {
        "name": "execute_pipeline",
        "description": "Execute a structured pipeline of stages. Each stage runs as an isolated subagent with its own context. Use for complex multi-phase tasks (audit, research, development). Previous stage findings automatically flow to next stage.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Pipeline name (e.g. 'API Security Audit')"},
                    "context": {"type": "string", "description": "Shared context for all stages (target info, credentials, scope)"},
                    "stages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Stage name (e.g. 'Reconnaissance')"},
                                "goal": {"type": "string", "description": "What this stage must accomplish"},
                                "tools_hint": {"type": "string", "description": "Hint about which tools to use or create"},
                            },
                            "required": ["name", "goal"],
                        },
                        "description": "Ordered list of stages to execute",
                    },
                    "fail_fast": {"type": "boolean", "description": "If true (default), stop the pipeline when a stage fails instead of running dependent stages on a broken foundation."},
                },
                "required": ["name", "stages"],
            }
        },
    }
    registry.register("execute_pipeline", pipeline_spec, handle_execute_pipeline, builtin=True, category="meta")

    # verify_work — self-verification against success criteria
    verify_spec = {
        "name": "verify_work",
        "description": "Verify your work meets a success criterion by running a real test. The verdict is based on the test's EXIT CODE (0 = pass) — design test_command to exit non-zero on failure (e.g. use 'assert', 'test', or 'exit 1'). Use AFTER building, BEFORE reporting completion, for EACH Definition-of-Done criterion. If it fails, fix and re-verify.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string", "description": "The success criterion being checked (e.g. 'RAG returns no-info for out-of-scope questions')"},
                    "test_command": {"type": "string", "description": "A concrete shell command that tests this criterion and exits non-zero on failure (e.g. 'cd /workspace && python3 test_oos.py')"},
                    "expected": {"type": "string", "description": "With assert_mode=contains/regex this is REQUIRED — the substring/pattern that must appear in the output (an empty value returns ERROR, not PASS). With assert_mode=exit_code it is optional: an expected exit code (default 0); a content string here is IGNORED."},
                    "assert_mode": {"type": "string", "enum": ["exit_code", "contains", "regex"], "description": "How to judge PASS. 'exit_code' (default): pass iff exit==0 — use when the criterion is 'command succeeds'. 'contains': output must contain `expected` — use when checking printed CONTENT. 'regex': output must match `expected`. Wrong/typo mode or missing `expected` returns verdict ERROR (a config mistake, not a failed criterion)."},
                    "timeout": {"type": "integer", "description": "Max seconds for the test before it's marked FAIL (timeout). Default 60."},
                },
                "required": ["criterion", "test_command"],
            }
        },
    }
    registry.register("verify_work", verify_spec, handle_verify_work, builtin=True, category="meta")

    # verify_webapp — prove a running web app is genuinely usable (real HTTP, assert body)
    verify_webapp_spec = {
        "name": "verify_webapp",
        "description": (
            "Prove a web app you built is GENUINELY USABLE — not just returning HTTP 200. "
            "Issues real HTTP requests to the running app (default http://localhost:8080) INSIDE the "
            "container and asserts on the RESPONSE BODY + a real user journey. MANDATORY after building "
            "any web app/API/chatbot UI, BEFORE reporting it done. A blank-200 page or a server that errors "
            "on real input will FAIL. Design the journey to exercise real user actions: e.g. GET / must "
            "contain the app's UI markup; POST /chat with an in-scope question must return a grounded answer "
            "containing a fact from the data; an out-of-scope question must return a refusal and NOT a fabricated fact."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "app_url": {"type": "string", "description": "Base URL of the running app (default http://localhost:8080)"},
                    "journey": {
                        "type": "array",
                        "description": "Ordered list of user-journey steps to assert.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Human label for this step"},
                                "method": {"type": "string", "description": "HTTP method (GET/POST/...). Default GET"},
                                "path": {"type": "string", "description": "Path, e.g. '/' or '/chat'. Default '/'"},
                                "body": {"description": "Optional request body (object → sent as JSON, or raw string)"},
                                "assert_status": {"type": "integer", "description": "Optional expected HTTP status code"},
                                "assert_contains": {"description": "String or list of strings that MUST appear in the response body"},
                                "assert_not_contains": {"description": "String or list of strings that must NOT appear (e.g. a hallucinated fact)"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["journey"],
            }
        },
    }
    registry.register("verify_webapp", verify_webapp_spec, handle_verify_webapp, builtin=True, category="meta")

    # site_map — Firecrawl /map: list all URLs of a site (recon / attack surface)
    site_map_spec = {
        "name": "site_map",
        "description": "Discover all URLs of a website (via self-hosted Firecrawl /map). Use for recon / mapping a site's attack surface, or finding pages to read. Returns a URL list.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "url": {"type": "string", "description": "Site to map (e.g. 'example.com')"},
            "limit": {"type": "integer", "description": "Max URLs to return (default 100)"},
        }, "required": ["url"]}},
    }
    registry.register("site_map", site_map_spec, handle_site_map, builtin=True, category="intelligence")

    # crawl_site — Firecrawl /crawl: scrape many pages of a site → markdown
    crawl_site_spec = {
        "name": "crawl_site",
        "description": "Crawl a website and return the markdown content of multiple pages (via self-hosted Firecrawl, renders JS + anti-bot). Use to gather documentation/data across a site. Async — polls until done.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "url": {"type": "string", "description": "Site/page to crawl"},
            "limit": {"type": "integer", "description": "Max pages (default 10)"},
            "max_depth": {"type": "integer", "description": "Max link depth from start URL (default 2)"},
        }, "required": ["url"]}},
    }
    registry.register("crawl_site", crawl_site_spec, handle_crawl_site, builtin=True, category="intelligence")

    # spawn_critic — dedicated adversarial reviewer (any domain)
    critic_spec = {
        "name": "spawn_critic",
        "description": "Spawn a dedicated Critic agent to adversarially review an important decision, design, or technical claim BEFORE you commit to it. Works for ANY domain (web/infra/pentest/ML/data/security). The critic auto-detects the domain, researches to verify each claim, and returns VALID/QUESTIONABLE/WRONG verdicts with evidence. USE THIS before finalizing architecture/tech choices or any claim you cannot back with evidence.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "What to critique (e.g. 'choice of ChromaDB as vector DB', 'this RCE payload approach', 'using pandas for 10GB dataset')"},
                    "context": {"type": "string", "description": "Requirements with concrete numbers/constraints (e.g. '1000 concurrent users', '10GB data', 'target behind Cloudflare WAF')"},
                    "claims": {"type": "string", "description": "Specific claims to verify (e.g. 'ChromaDB scales to 1k users', 'this payload bypasses WAF')"},
                },
                "required": ["subject", "context"],
            }
        },
    }
    registry.register("spawn_critic", critic_spec, handle_spawn_critic, builtin=True, category="meta")

    # spawn_subagent — special: only for main agent
    spawn_spec = {
        "name": "spawn_subagent",
        "description": "Spawn a sub-agent to handle a specific sub-task in a separate context. Use this when a task is complex or requires deep focus.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "role_name": {"type": "string", "description": "Name of the subagent role (e.g. 'Code Reviewer')"},
                    "system_prompt": {"type": "string", "description": "Custom instructions/personality for the subagent"},
                    "task": {"type": "string", "description": "The specific task the subagent must complete"},
                },
                "required": ["role_name", "task"],
            }
        },
    }
    registry.register("spawn_subagent", spawn_spec, handle_spawn_subagent, builtin=True, category="meta")
