"""Discover behavioral numeric constraints that require explicit classification.

The purpose of this audit is not to outlaw numbers. It is to prevent behavioral
policy from acquiring unexplained magic numbers. Mathematical identities,
protocol sequence origins, percentage-domain bounds, and benchmark-fixture
mechanics may be structural, but policy-named zero/one values are still surfaced
because values such as one worker, one LLM slot, or zero retries can be genuine
behavioral choices.

Every discovered runtime/operational constraint must be classified in
``benchmarks/constraint_registry.json``. Empirical and safety tunables must
point to a benchmark/calibration specification. Structural/external constraints
must carry a proof/rationale instead.
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

# Benchmark implementation knobs affect measurement design rather than runtime
# behavior. They are reviewed in the benchmark spec itself and are excluded from
# the runtime constraint registry to avoid circularly treating a test grid as a
# production policy.
_EXCLUDED_FILE_PATTERNS = (
    re.compile(r"(?:^|/)test_"),
    re.compile(r"(?:^|/).*benchmark\.py$"),
    re.compile(r"(?:^|/)scale_test\.py$"),
    re.compile(r"(?:^|/)adversarial_benchmark\.py$"),
    re.compile(r"(?:^|/)audit_constraints\.py$"),
)

_POLICY_WORDS = re.compile(
    r"(?:^|_)(?:"
    r"threshold|score|weight|bonus|decay|limit|max|min|minimum|maximum|"
    r"timeout|ttl|retry|retries|attempt|attempts|round|rounds|loop|loops|"
    r"budget|candidate|candidates|breadth|depth|hop|hops|window|interval|"
    r"headroom|pressure|capacity|memory|cpu|ram|percent|percentage|ratio|"
    r"count|size|length|age|days|hours|minutes|seconds|milliseconds|"
    r"batch|page|queue|wait|grace|lease|heartbeat|backoff|jitter|sample|"
    r"samples|percentile|top|beam|fanout|branch|workers|slots|tokens|items|"
    r"events|capabilities|literals|priority|concurrency|output"
    r")(?:_|$)",
    re.IGNORECASE,
)

_STRUCTURAL_NUMBERS = {0, 1, 0.0, 1.0}
_FIELD_BOUND_NAMES = {"min_length", "max_length", "ge", "gt", "le", "lt", "multiple_of"}
_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_PROMPT_RANGE_RE = re.compile(r"\b(\d+)\s*[-–]\s*(\d+)\b")
_PROMPT_BOUND_RE = re.compile(
    r"\b(?:at\s+most|up\s+to|no\s+more\s+than|exactly)\s+"
    r"(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\b",
    re.IGNORECASE,
)


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


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _qualified_owner(stack: list[str]) -> str:
    return ".".join(stack) if stack else "<module>"


def _policy_name(name: str | None) -> bool:
    return bool(name and _POLICY_WORDS.search(name))


def _field_bound_is_behavioral(field_name: str, bound: str, value: int | float) -> bool:
    """Return True only for schema bounds that constrain behavioral breadth.

    `min_length=1`, `ge=0`, positive sequence numbers, and [0,100] percentage
    domains are structural validation. Multi-item maxima/minima and unusual
    numeric ceilings are policy and must be justified.
    """
    if bound == "max_length":
        return value > 1
    if bound == "min_length":
        return value > 1
    if bound in {"ge", "gt"}:
        if value in _STRUCTURAL_NUMBERS:
            return False
        return _policy_name(field_name)
    if bound in {"le", "lt"}:
        if value == 100 and ("percent" in field_name or "percentage" in field_name):
            return False
        if value in _STRUCTURAL_NUMBERS:
            return False
        return True
    return value not in _STRUCTURAL_NUMBERS


def _prompt_number(token: str) -> int:
    lowered = token.casefold()
    return int(lowered) if lowered.isdigit() else _NUMBER_WORDS[lowered]


class _Visitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stack: list[str] = []
        self.findings: list[ConstraintFinding] = []
        self._ordinal: dict[tuple[str, str], int] = {}
        self._field_calls: set[int] = set()

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

    def _visit_function_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        args = [*node.args.posonlyargs, *node.args.args]
        defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
        for arg, default in zip(args, defaults, strict=True):
            value = _numeric_literal(default)
            if value is not None and _policy_name(arg.arg):
                self._add(default, role="function_default", value=value, name=arg.arg, source=ast.unparse(default))
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
            value = _numeric_literal(default)
            if value is not None and _policy_name(arg.arg):
                self._add(default, role="function_default", value=value, name=arg.arg, source=ast.unparse(default))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name)
        try:
            self._visit_function_defaults(node)
            self.generic_visit(node)
        finally:
            self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.stack.append(node.name)
        try:
            self._visit_function_defaults(node)
            self.generic_visit(node)
        finally:
            self.stack.pop()

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
                module_policy_constant = (
                    not self.stack
                    and isinstance(target, ast.Name)
                    and target.id.isupper()
                    and value not in _STRUCTURAL_NUMBERS
                )
                if _policy_name(name) or module_policy_constant:
                    self._add(node, role="assignment", value=value, name=name, source=ast.unparse(node))

        if (
            isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and any(
                isinstance(target, ast.Name) and target.id.endswith("_PROMPT")
                for target in node.targets
            )
        ):
            prompt_name = next(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name) and target.id.endswith("_PROMPT")
            )
            text = node.value.value
            for match in _PROMPT_RANGE_RE.finditer(text):
                self._add(
                    node,
                    role="prompt_range_max",
                    value=int(match.group(2)),
                    name=f"{prompt_name}.range_max",
                    source=match.group(0),
                )
            for match in _PROMPT_BOUND_RE.finditer(text):
                self._add(
                    node,
                    role="prompt_numeric_bound",
                    value=_prompt_number(match.group(1)),
                    name=f"{prompt_name}.numeric_bound",
                    source=match.group(0),
                )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        name = _name_of_target(node.target)
        value = _numeric_literal(node.value)
        if value is not None and (_policy_name(name) or (not self.stack and name and name.isupper() and value not in _STRUCTURAL_NUMBERS)):
            self._add(node, role="annotated_assignment", value=value, name=name, source=ast.unparse(node))

        if isinstance(node.value, ast.Call) and _call_name(node.value) == "Field" and name:
            self._field_calls.add(id(node.value))
            default_value = None
            if node.value.args:
                default_value = _numeric_literal(node.value.args[0])
            for keyword in node.value.keywords:
                if keyword.arg == "default":
                    default_value = _numeric_literal(keyword.value)
            if default_value is not None and _policy_name(name):
                self._add(
                    node.value,
                    role="field_default",
                    value=default_value,
                    name=f"{name}.default",
                    source=ast.unparse(node.value),
                )
            for keyword in node.value.keywords:
                if keyword.arg not in _FIELD_BOUND_NAMES:
                    continue
                bound_value = _numeric_literal(keyword.value)
                if bound_value is None or not _field_bound_is_behavioral(name, keyword.arg, bound_value):
                    continue
                self._add(
                    keyword.value,
                    role=f"field_bound:{keyword.arg}",
                    value=bound_value,
                    name=f"{name}.{keyword.arg}",
                    source=ast.unparse(node.value),
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = _call_name(node)
        if id(node) in self._field_calls or func_name == "Field":
            self.generic_visit(node)
            return

        for keyword in node.keywords:
            value = _numeric_literal(keyword.value)
            if value is None or keyword.arg is None:
                continue
            if _policy_name(keyword.arg):
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
                if value is not None and value > 1:
                    self._add(arg, role="range_bound", value=value, name=f"range_arg{index}", source=ast.unparse(node))
        self.generic_visit(node)


def _excluded(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(pattern.search(rel) for pattern in _EXCLUDED_FILE_PATTERNS)


def discover_python_constraints(paths: Iterable[Path] = DEFAULT_SCAN_ROOTS) -> list[ConstraintFinding]:
    findings: list[ConstraintFinding] = []
    for root in paths:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if _excluded(path):
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


def uncovered_findings(findings: Iterable[ConstraintFinding], registry: dict[str, dict[str, object]]) -> list[ConstraintFinding]:
    return [finding for finding in findings if finding.key not in registry]


def stale_registry_keys(findings: Iterable[ConstraintFinding], registry: dict[str, dict[str, object]]) -> list[str]:
    discovered = {finding.key for finding in findings}
    return sorted(key for key in registry if key not in discovered and not bool(registry[key].get("manual")))


def validate_registry_entry(key: str, entry: dict[str, object]) -> list[str]:
    errors: list[str] = []
    classification = entry.get("classification")
    allowed = {
        "EMPIRICAL_TUNABLE",
        "SAFETY_TUNABLE",
        "ENVIRONMENT_CALIBRATED",
        "STRUCTURAL_INVARIANT",
        "EXTERNAL_CONTRACT",
        "IDENTIFIER_COLLISION_BOUND",
    }
    if classification not in allowed:
        errors.append(f"{key}: invalid/missing classification")
    if not str(entry.get("rationale", "")).strip():
        errors.append(f"{key}: missing rationale")
    if classification in {"EMPIRICAL_TUNABLE", "SAFETY_TUNABLE", "ENVIRONMENT_CALIBRATED"}:
        if not str(entry.get("benchmark_id", "")).strip():
            errors.append(f"{key}: tunable has no benchmark_id")
        status = entry.get("status")
        if status not in {"PROVISIONAL", "VERIFIED", "NATIVE_REQUIRED"}:
            errors.append(f"{key}: tunable has invalid/missing status")
    return errors


def registry_errors(registry: dict[str, dict[str, object]]) -> list[str]:
    errors: list[str] = []
    for key, entry in registry.items():
        if not isinstance(entry, dict):
            errors.append(f"{key}: entry must be an object")
            continue
        errors.extend(validate_registry_entry(key, entry))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable findings")
    parser.add_argument("--fail-unregistered", action="store_true")
    args = parser.parse_args()

    findings = discover_python_constraints()
    registry = load_registry()
    uncovered = uncovered_findings(findings, registry)
    stale = stale_registry_keys(findings, registry)
    errors = registry_errors(registry)

    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2, sort_keys=True))
    else:
        print(
            f"discovered={len(findings)} registered={len(findings) - len(uncovered)} "
            f"uncovered={len(uncovered)} stale={len(stale)} invalid={len(errors)}"
        )
        for item in findings:
            status = "REGISTERED" if item.key in registry else "UNREGISTERED"
            print(f"{status} {item.key} value={item.value!r} line={item.line} role={item.role} :: {item.source}")
        for key in stale:
            print(f"STALE {key}")
        for error in errors:
            print(f"INVALID {error}")

    failed = bool(uncovered or stale or errors)
    return 1 if args.fail_unregistered and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
