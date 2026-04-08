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

    # Check for generate_signals function OR BaseStrategy subclass
    generate_fn = None
    has_strategy_class = False

    for node in tree.body:
        # Check for standalone generate_signals function
        if isinstance(node, ast.FunctionDef) and node.name == "generate_signals":
            generate_fn = node
        # Check for class that might be a BaseStrategy subclass
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name in ("BaseStrategy", "RuleBasedStrategy", "MLStrategy",
                                  "StatisticalStrategy", "EnsembleStrategy", "StackingEnsemble"):
                    has_strategy_class = True
                    # Check if class has generate_signals method
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == "generate_signals":
                            generate_fn = item
                            break

    if generate_fn is None and not has_strategy_class:
        issues.append("Missing required function: generate_signals (or BaseStrategy subclass)")
    elif generate_fn is not None and generate_fn.returns is None:
        issues.append("generate_signals must declare a return annotation")

    return {"valid": len(issues) == 0, "issues": issues}
