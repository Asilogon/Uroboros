#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uroboros Commit Helper (Python version, encoding-safe).

Builds a commit message in the project convention:

    [X.Y.Z] Short description

    Detailed changes:
    - Item 1
    - Item 2

Usage:
    python scripts/commit.py           # interactive
    python scripts/commit.py --dry-run # preview only
    python scripts/commit.py --no-add  # don't run `git add -A`
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_git() -> str | None:
    g = shutil.which("git")
    if g:
        return g
    candidates = [
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        str(Path.home() / "AppData/Local/Programs/Git/bin/git.exe"),
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def run(git: str, *args: str) -> int:
    return subprocess.call([git, *args])


def ask(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Uroboros commit helper")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-add", action="store_true")
    args = ap.parse_args()

    git = find_git()
    if not git:
        print("ERROR: Git not found. Install Git for Windows: https://git-scm.com/download/win")
        return 1

    toplevel = subprocess.run(
        [git, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    )
    if toplevel.returncode != 0:
        print("ERROR: Current directory is not a git repository. Run: git init")
        return 1
    repo = Path(toplevel.stdout.strip())
    import os
    os.chdir(repo)

    print()
    print("=== Uroboros Commit Helper ===")
    print(f"Repo: {repo}")
    print()

    status = subprocess.run([git, "status", "--short"], capture_output=True, text=True).stdout.strip()
    if not status:
        print("No changes to commit.")
        return 0
    print("Changed files:")
    for line in status.splitlines():
        print(f"  {line}")
    print()

    while True:
        ver = ask("Version (SemVer, e.g. 0.2.0): ").lstrip("v")
        if re.fullmatch(r"\d+\.\d+\.\d+", ver):
            break
        print("  Format must be X.Y.Z (digits and dots only).")

    while True:
        subject = ask("Short description (max 72 chars): ").rstrip(".")
        if 0 < len(subject) <= 72:
            break
        print("  Length must be 1..72 characters.")

    print()
    print("Detailed changes (one per line, empty line to finish):")
    bullets: list[str] = []
    while True:
        line = ask("  - ").strip()
        if not line:
            break
        bullets.append(line)

    msg = f"[{ver}] {subject}"
    if bullets:
        msg += "\n\nDetailed changes:\n" + "\n".join(f"- {b}" for b in bullets)

    print()
    print("--- Final commit message ---")
    print(msg)
    print("----------------------------")

    if args.dry_run:
        print("[DryRun] Commit not created.")
        return 0

    confirm = ask("Create commit? (y/N): ").lower()
    if not confirm.startswith("y"):
        print("Cancelled.")
        return 0

    if not args.no_add:
        if run(git, "add", "-A") != 0:
            print("ERROR: git add failed")
            return 1

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write(msg)
        tmp = f.name
    try:
        rc = run(git, "commit", "-F", tmp)
        if rc != 0:
            print("ERROR: git commit failed")
            return 1
        print()
        print("Commit created successfully.")
        run(git, "log", "-1", "--oneline")
    finally:
        Path(tmp).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
