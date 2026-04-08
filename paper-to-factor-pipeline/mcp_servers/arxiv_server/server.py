import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import arxiv
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("arxiv-server", json_response=True)


def _paper_to_dict(result: arxiv.Result) -> dict:
    return {
        "arxiv_id": result.get_short_id(),
        "title": result.title,
        "authors": [a.name for a in result.authors],
        "published": result.published.isoformat() if result.published else None,
        "updated": result.updated.isoformat() if result.updated else None,
        "summary": result.summary,
        "categories": result.categories,
        "pdf_url": result.pdf_url,
        "entry_id": result.entry_id,
    }


@mcp.tool()
def ping_arxiv() -> dict:
    return {"status": "ok", "message": "arxiv MCP server is running"}


@mcp.tool()
def search_papers(query: str, category_filter: str = "q-fin", max_results: int = 10) -> str:
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )

        papers = []
        for result in client.results(search):
            if any(cat.startswith(category_filter) for cat in result.categories):
                papers.append(_paper_to_dict(result))

        return json.dumps(papers)
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc), "traceback": traceback.format_exc()})


@mcp.tool()
def fetch_paper_details(arxiv_id: str) -> str:
    try:
        client = arxiv.Client()
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(client.results(search))
        return json.dumps(_paper_to_dict(result))
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc), "traceback": traceback.format_exc()})


if __name__ == "__main__":
    mcp.run(transport="stdio")
