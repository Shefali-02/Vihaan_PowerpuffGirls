"""Architecture rules enforced by AST: no provider SDKs, no cross-module model/repository imports,
no float arithmetic in ledger and rules, routers never import models/repositories or sqlalchemy."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts.check_no_provider_sdk import offenders

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"


def _imports(path: Path) -> list[tuple[int, str]]:
    out = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.lineno, node.module))
            out += [(node.lineno, f"{node.module}.{a.name}") for a in node.names]
    return out


def test_no_provider_sdk_imports():
    assert offenders() == []


def test_no_cross_module_model_or_repository_imports():
    bad = []
    for py in MODULES.rglob("*.py"):
        own = py.relative_to(MODULES).parts[0]
        for line, name in _imports(py):
            parts = name.split(".")
            if len(parts) >= 3 and parts[0] == "modules" and parts[1] != own and parts[2] in ("models", "repository"):
                bad.append(f"{py.relative_to(ROOT)}:{line} -> {name}")
    assert bad == []


def test_routers_do_not_touch_the_database():
    bad = []
    for py in (ROOT / "apps" / "api" / "routers").glob("*.py"):
        for line, name in _imports(py):
            if name.startswith("sqlalchemy") or name.endswith((".models", ".repository")) or ".models." in name \
                    or ".repository." in name:
                bad.append(f"{py.name}:{line} -> {name}")
    assert bad == []


class _FloatFinder(ast.NodeVisitor):
    def __init__(self):
        self.hits = []

    def visit_Constant(self, node):
        if isinstance(node.value, float):
            self.hits.append((node.lineno, f"float literal {node.value}"))

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Div):
            self.hits.append((node.lineno, "true division '/'"))
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "float":
            self.hits.append((node.lineno, "float()"))
        self.generic_visit(node)


def test_no_float_arithmetic_in_ledger_and_rules():
    bad = []
    for pkg in ("ledger", "rules"):
        for py in (MODULES / pkg).rglob("*.py"):
            f = _FloatFinder()
            f.visit(ast.parse(py.read_text()))
            bad += [f"{py.relative_to(ROOT)}:{ln} {what}" for ln, what in f.hits]
    assert bad == []


def test_every_business_table_has_workspace_id():
    from core.db import Base, import_all_models

    import_all_models()
    exempt = {"workspaces", "users", "audit_chain_heads"}  # identity roots / per-workspace PK
    missing = [t.name for t in Base.metadata.sorted_tables if t.name not in exempt and "workspace_id" not in t.c]
    assert missing == []
