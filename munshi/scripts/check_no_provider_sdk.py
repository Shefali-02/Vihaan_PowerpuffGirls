#!/usr/bin/env python3
"""Fail if any Python file imports an LLM provider SDK. All LLM calls must go through modules/ai/gateway.py."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = {"openai", "anthropic", "google.generativeai", "google.genai", "cohere", "mistralai", "groq",
             "together", "litellm", "langchain", "langchain_openai", "llama_index", "vertexai", "boto3"}
SKIP_DIRS = {"node_modules", ".venv", "venv", "chain", ".git", "__pycache__"}


def offenders(root: Path = ROOT) -> list[str]:
    out = []
    for py in root.rglob("*.py"):
        if SKIP_DIRS & set(py.relative_to(root).parts):
            continue
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if any(n == f or n.startswith(f + ".") for f in FORBIDDEN):
                    out.append(f"{py.relative_to(root)}:{node.lineno} imports {n}")
    return out


if __name__ == "__main__":
    bad = offenders()
    for b in bad:
        print("FORBIDDEN:", b)
    print("provider-SDK check:", "FAIL" if bad else "PASS")
    sys.exit(1 if bad else 0)
