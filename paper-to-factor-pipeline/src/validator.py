import ast
import re
from pathlib import Path


def validate_factor(factor_path: str) -> dict:
    path = Path(factor_path)
    issues: list[str] = []

    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"valid": False, "issues": [f"Unable to read factor file: {exc}"]}

    if re.search(r"\.?shift\(\s*-", raw):
        issues.append("Potential look-ahead bias detected: negative shift usage")

    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return {"valid": False, "issues": ["Syntax error in factor file"]}

    generate_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "generate_signals":
            generate_fn = node
            break

    if generate_fn is None:
        issues.append("Missing required function: generate_signals")
    elif generate_fn.returns is None:
        issues.append("generate_signals must declare a return annotation")

    return {"valid": len(issues) == 0, "issues": issues}
