from duckduckgo_search import DDGS


def web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return f"No results found for: '{query}'"
        output = []
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r['title']}\n   {r['body']}\n   URL: {r['href']}")
        return "\n\n".join(output)
    except Exception as e:
        return f"Search error: {e}"
