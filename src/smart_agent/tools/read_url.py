import httpx


def read_url(url: str) -> str:
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (SmartAgent/1.0)"
        })
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            return _extract_text_from_html(resp.text)
        return resp.text[:5000]
    except Exception as e:
        return f"Error reading URL: {e}"


def _extract_text_from_html(html: str) -> str:
    import re
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:5000]
