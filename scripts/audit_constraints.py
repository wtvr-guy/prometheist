"""Discover policy-like numeric constraints that require explicit classification.

The auditor is deliberately conservative: it scans production Python and
operational scripts for numeric literals whose syntactic role or identifier
suggests a threshold, limit, timeout, retry budget, resource margin, candidate
count, traversal depth, score weight, or similar behavioral constraint.

Every discovered constraint must be classified in
``benchmarks/constraint_registry.json``. The registry is the durable record of
whether a value is an invariant/external contract or an empirical tunable, and
which benchmark or calibration evidence justifies it.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_ROOTS = (ROOT / "src" / "jit_agent", ROOT / "scripts")
DEFAULT_REGISTRY = ROOT / "benchmarks" / "constraint_registry.json"

_POLICY_WORDS = re.compile(
    r"(?:^|_)(?:"
    r"threshold|score|weight|bonus|decay|limit|max|min|minimum|maximum|"
    r"timeout|ttl|retry|retries|attempt|attempts|round|rounds|loop|loops|"
    r"budget|candidate|candidates|breadth|depth|hop|hops|window|interval|"
    r"headroom|pressure|capacity|memory|cpu|ram|percent|percentage|ratio|"
    r"count|size|length|age|days|hours|minutes|seconds|milliseconds|"
    r"batch|page|queue|wait|grace|lease|heartbeat|backoff|jitter|sample|"
    r"samples|percentile|top|beam|fanout|branch|workers|slots"
    r")(?:_|$)",
    re.IGNORECASE,
)

# These literals are overwhelmingly structural (boolean-ish sentinels, first
# index, empty/non-empty bounds). They are still discovered when the identifier
# explicitly looks policy-like.
_STRUCTURAL_NUMBERS = {0, 1, 0.0, 1.0}


@dataclass(frozen=True, slots=True)
class ConstraintFinding:
    key: str
    path: str
    line: int
    owner: str
    role: str
    value: int | float
    source: str


def _numeric_literal(node: ast.AST | None) -> int | float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if isinstance(node.value, bool):
            return None
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _numeric_literal(node.operand)
        if inner is None:
            return None
        return -inner if isinstance(node.op, ast.USub) else inner
    return None


def _name_of_target(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _qualified_owner(stack: list[str]) -> str:
    return ".".join(stack) if stack else "<module>"


def _policy_name(name: str | None) -> bool:
    return bool(name and _POLICY_WORDS.search(name))


class _Visitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stack: list[str] = []
        self.findings: list[ConstraintFinding] = []
        self._ordinal: dict[tuple[str, str], int] = {}

    def _add(
        self,
        node: ast.AST,
        *,
        role: str,
        value: int | float,
        name: str | None = None,
        source: str,
    ) -> None:
        owner = _qualified_owner(self.stack)
        base = name or role
        ordinal_key = (owner, base)
        ordinal = self._ordinal.get(ordinal_key, 0) + 1
        self._ordinal[ordinal_key] = ordinal
        suffix = "" if ordinal == 1 else f"#{ordinal}"
        rel = self.path.relative_to(ROOT).as_posix()
        key = f"{rel}::{owner}::{base}{suffix}"
        self.findings.append(
            ConstraintFinding(
                key=key,
                path=rel,
                line=getattr(node, "lineno", 0),
                owner=owner,
                role=role,
                value=value,
                source=source,
            )
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name)
        try:
            args = [*node.args.posonlyargs, *node.args.args]
            defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
            for arg, default in zip(args, defaults, strict=True):
                value = _numeric_literal(default)
                if value is not None and _policy_name(arg.arg):
                    self._add(
                        default,
                        role="function_default",
                        value=value,
                        name=arg.arg,
                        source=ast.unparse(default),
                    )
            for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
                value = _numeric_literal(default)
                if value is not None and _policy_name(arg.arg):
                    self._add(
                        default,
                        role="function_default",
                        value=value,
                        name=arg.arg,
                        source=ast.unparse(default),
                    )
            self.generic_visit(node)
        finally:
            self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        try:
            self.generic_visit(node)
        finally:
            self.stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        value = _numeric_literal(node.value)
        if value is not None:
            for target in node.targets:
                name = _name_of_target(target)
                if _policy_name(name) or (
                    not self.stack
                    and isinstance(target, ast.Name)
                    and target.id.isupper()
                    and value not in _STRUCTURAL_NUMBERS
                ):
                    self._add(
                        node,
                        role="assignment",
                        value=value,
                        name=name,
                        source=ast.unparse(node),
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        value = _numeric_literal(node.value)
        name = _name_of_target(node.target)
        if value is not None and (_policy_name(name) or (not self.stack and name and name.isupper())):
            self._add(
                node,
                role="annotated_assignment",
                value=value,
                name=name,
                source=ast.unparse(node),
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        for keyword in node.keywords:
            value = _numeric_literal(keyword.value)
            if value is None or keyword.arg is None:
                continue
            if _policy_name(keyword.arg) or keyword.arg in {
                "ge", "gt", "le", "lt", "min_length", "max_length", "multiple_of"
            }:
                self._add(
                    keyword.value,
                    role=f"call_keyword:{keyword.arg}",
                    value=value,
                    name=f"{func_name or 'call'}.{keyword.arg}",
                    source=ast.unparse(node),
                )

        if func_name == "range":
            for index, arg in enumerate(node.args):
                value = _numeric_literal(arg)
                if value is not None and value not in _STRUCTURAL_NUMBERS:
                    self._add(
                        arg,
                        role="range_bound",
                        value=value,
                        name=f"range_arg{index}",
                        source=ast.unparse(node),
                    )
        elif func_name in {"min", "max"}:
            for index, arg in enumerate(node.args):
                value = _numeric_literal(arg)
                if value is not None and value not in _STRUCTURAL_NUMBERS:
                    self._add(
                        arg,
                        role=f"{func_name}_bound",
                        value=value,
                        name=f"{func_name}_arg{index}",
                        source=ast.unparse(node),
                    )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.slice, ast.Slice):
            for label, bound in (("slice_lower", node.slice.lower), ("slice_upper", node.slice.upper)):
                value = _numeric_literal(bound)
                if value is not None and value not in _STRUCTURAL_NUMBERS:
                    self._add(
                        bound,
                        role=label,
                        value=value,
                        name=label,
                        source=ast.unparse(node),
                    )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        names = [
            operand.id if isinstance(operand, ast.Name) else operand.attr if isinstance(operand, ast.Attribute) else None
            for operand in operands
        ]
        policy_context = any(_policy_name(name) for name in names)
        if policy_context:
            for operand in operands:
                value = _numeric_literal(operand)
                if value is not None and value not in _STRUCTURAL_NUMBERS:
                    self._add(
                        operand,
                        role="policy_comparison",
                        value=value,
                        name="comparison",
                        source=ast.unparse(node),
                    )
        self.generic_visit(node)


def discover_python_constraints(paths: Iterable[Path] = DEFAULT_SCAN_ROOTS) -> list[ConstraintFinding]:
    findings: list[ConstraintFinding] = []
    for root in paths:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if path.name == "audit_constraints.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            visitor = _Visitor(path)
            visitor.visit(tree)
            findings.extend(visitor.findings)
    findings.sort(key=lambda item: (item.path, item.line, item.key))
    return findings


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    constraints = payload.get("constraints", {})
    if not isinstance(constraints, dict):
        raise ValueError("constraint_registry.json must contain an object at 'constraints'")
    return constraints


def uncovered_findings(
    findings: Iterable[ConstraintFinding],
    registry: dict[str, dict[str, object]],
) -> list[ConstraintFinding]:
    return [finding for finding in findings if finding.key not in registry]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable findings")
    parser.add_argument("--fail-unregistered", action="store_true")
    args = parser.parse_args()

    findings = discover_python_constraints()
    registry = load_registry()
    uncovered = uncovered_findings(findings, registry)

    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2, sort_keys=True))
    else:
        print(f"discovered={len(findings)} registered={len(findings) - len(uncovered)} uncovered={len(uncovered)}")
        for item in findings:
            status = "REGISTERED" if item.key in registry else "UNREGISTERED"
            print(
                f"{status} {item.key} value={item.value!r} line={item.line} role={item.role} :: {item.source}"
            )

    return 1 if args.fail_unregistered and uncovered else 0


if __name__ == "__main__":
    raise SystemExit(main())
