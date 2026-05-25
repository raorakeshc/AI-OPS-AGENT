"""CLI to reset in-repo memory scopes.

Usage:
    python scripts/memory_reset.py session
    python scripts/memory_reset.py user --id user123
    python scripts/memory_reset.py all
"""
import sys
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.admin_memory import reset_memory, MemoryResetRequest


def main():
    parser = argparse.ArgumentParser(description="Reset internal memory scopes")
    parser.add_argument("scope", choices=["session", "user", "repo", "all"])
    parser.add_argument("--id", dest="identifier", help="Optional identifier to selectively remove items")
    args = parser.parse_args()

    req = MemoryResetRequest(scope=args.scope, identifier=args.identifier)
    res = reset_memory(req)
    print(f"Removed: {res.get('removed', 0)} items from scope={args.scope}")


if __name__ == "__main__":
    main()
