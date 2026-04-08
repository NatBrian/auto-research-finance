import importlib.util
import json
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _DummyFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self):
        def _decorator(func):
            return func

        return _decorator

    def run(self, transport: str = "stdio"):
        return None


def _load_module(module_name: str, path: Path, injected_modules: dict[str, types.ModuleType]):
    previous = {name: sys.modules.get(name) for name in injected_modules}

    try:
        sys.modules.update(injected_modules)
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in previous.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def _mcp_stub_modules() -> dict[str, types.ModuleType]:
    mcp_mod = types.ModuleType("mcp")
    server_mod = types.ModuleType("mcp.server")
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = _DummyFastMCP
    return {
        "mcp": mcp_mod,
        "mcp.server": server_mod,
        "mcp.server.fastmcp": fastmcp_mod,
    }


def test_arxiv_server_tools_return_json_payloads():
    class _FakeAuthor:
        def __init__(self, name: str):
            self.name = name

    class _FakeResult:
        def __init__(self, short_id: str, categories: list[str]):
            self._short_id = short_id
            self.title = f"Paper {short_id}"
            self.authors = [_FakeAuthor("Alice"), _FakeAuthor("Bob")]
            self.published = None
            self.updated = None
            self.summary = "Signal formula with a 12-month lookback."
            self.categories = categories
            self.pdf_url = f"https://arxiv.org/pdf/{short_id}.pdf"
            self.entry_id = f"http://arxiv.org/abs/{short_id}"

        def get_short_id(self) -> str:
            return self._short_id

    class _FakeSearch:
        def __init__(self, query=None, max_results=None, sort_by=None, id_list=None):
            self.id_list = id_list or []

    class _FakeClient:
        def results(self, search):
            if search.id_list:
                return iter([_FakeResult(search.id_list[0], ["q-fin.TR"])])
            return iter(
                [
                    _FakeResult("1234.5678", ["q-fin.TR"]),
                    _FakeResult("9999.0001", ["cs.AI"]),
                ]
            )

    arxiv_mod = types.ModuleType("arxiv")
    arxiv_mod.Client = _FakeClient
    arxiv_mod.Search = _FakeSearch
    arxiv_mod.SortCriterion = types.SimpleNamespace(Relevance="relevance")
    arxiv_mod.Result = _FakeResult

    module = _load_module(
        "test_arxiv_server",
        PROJECT_ROOT / "mcp_servers" / "arxiv_server" / "server.py",
        {**_mcp_stub_modules(), "arxiv": arxiv_mod},
    )

    assert module.ping_arxiv()["status"] == "ok"

    search_payload = json.loads(module.search_papers("momentum"))
    assert isinstance(search_payload, list)
    assert len(search_payload) == 1
    assert search_payload[0]["arxiv_id"] == "1234.5678"

    detail_payload = json.loads(module.fetch_paper_details("1234.5678"))
    assert detail_payload["title"] == "Paper 1234.5678"
    assert detail_payload["pdf_url"].endswith("1234.5678.pdf")


def test_backtest_server_returns_json_payload():
    core_backtester_mod = types.ModuleType("src.core.backtester")
    utils_mod = types.ModuleType("src.utils")

    class _StubEnhancedBacktester:
        def __init__(self, config):
            self.config = config

        def run(self):
            return {"status": "success", "message": "", "sharpe_ratio": 1.23}

    core_backtester_mod.EnhancedBacktester = _StubEnhancedBacktester
    utils_mod.load_config = lambda path="config/settings.yaml": {"loaded": True}
    utils_mod.safe_json_dumps = json.dumps

    module = _load_module(
        "test_backtest_server",
        PROJECT_ROOT / "mcp_servers" / "backtest_server" / "server.py",
        {**_mcp_stub_modules(), "src.core.backtester": core_backtester_mod, "src.utils": utils_mod},
    )

    assert module.ping_backtest()["status"] == "ok"

    payload = json.loads(module.run_backtest())
    assert payload["status"] == "success"
    assert payload["sharpe_ratio"] == 1.23
