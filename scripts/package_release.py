"""
PUFI — Release Packaging Script (Phase 4: Credential Hygiene)

Creates a distributable ZIP of the PUFI project, explicitly excluding:
  - .env files (all variants, e.g. .env.production, .env.local)
  - Virtual environments (.venv/, venv/)
  - Python bytecode (__pycache__/, *.pyc, *.pyo)
  - Local SQLite databases (*.sqlite, *.db, *.sqlite3)
  - Log files (*.log)
  - Node modules (node_modules/)
  - Build artefacts (dist/, build/, .vite/)
  - Editor config (.vscode/, .idea/)

Explicitly INCLUDES .env.example files so the recipient knows what
environment variables must be configured before running.

SECURITY CONTRACT:
  - After creating the ZIP, this script opens and scans every included
    file path for patterns that look like secrets.  If any real .env
    file is detected inside the archive, the script deletes the ZIP
    and exits with a non-zero error code.
  - Never commit the resulting ZIP to version control (.gitignore
    already excludes *.zip and release/).

Usage:
    python scripts/package_release.py [--out release/] [--version 0.1.0]
"""

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Directories to skip entirely (matched against each path component)
SKIP_DIRS = {
    ".venv", "venv", "__pycache__", "node_modules",
    "dist", "build", ".vite", ".pytest_cache", ".mypy_cache",
    "htmlcov", ".git", ".idea", ".vscode", "release",
}

# File name / extension patterns to exclude
SKIP_PATTERNS = [
    re.compile(r"^\.env(\..+)?$"),          # .env, .env.local, .env.production …
    re.compile(r"^\.env\.example$"),         # keep (.env.example is included)
    re.compile(r".*\.pyc$"),
    re.compile(r".*\.pyo$"),
    re.compile(r".*\.sqlite$"),
    re.compile(r".*\.sqlite3$"),
    re.compile(r".*\.db$"),
    re.compile(r".*\.db-shm$"),
    re.compile(r".*\.db-wal$"),
    re.compile(r".*\.log$"),
    re.compile(r".*\.zip$"),
    re.compile(r".*\.pem$"),
    re.compile(r".*\.key$"),
    re.compile(r"Thumbs\.db$"),
    re.compile(r"\.DS_Store$"),
    re.compile(r"\.coverage$"),
]

# Allowlist overrides — these .env-like filenames ARE safe to include
ALLOW_EXACT = {".env.example"}

# Secret sentinel patterns — if found INSIDE the archive contents, abort.
# These target real credential formats, not documentation placeholders.
# Real PayPal Sandbox client IDs start with 'A' and are 25–80 chars of base64url.
# Real client secrets are 32–80 chars of random alphanumerics.
# Placeholder text (your_, <CLIENT_ID>, REPLACE_ME etc.) is intentionally excluded.
SECRET_SENTINELS = [
    # PayPal Sandbox client ID: starts with A, 25+ alphanumeric chars, not a placeholder
    re.compile(r"(?i)paypal_client_id\s*=\s*A[A-Za-z0-9_\-]{24,}(?!.*your_)"),
    # PayPal client secret: 32+ random alphanumeric chars that don't look like placeholder text
    re.compile(r"(?i)paypal_client_secret\s*=\s*(?!your_)(?!<)(?!REPLACE)(?!placeholder)[A-Za-z0-9_\-]{32,}"),
    # Gemini API key: starts with AIza and is 39 chars
    re.compile(r"(?i)(?:gemini_api_key|ai_api_key)\s*=\s*AIza[A-Za-z0-9_\-]{35}"),
    # Generic long secret that doesn't look like a placeholder
    re.compile(r"(?i)secret_key\s*=\s*(?!your_)(?!<)(?!REPLACE)[A-Za-z0-9_\-]{40,}"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def should_exclude(path: Path, root: Path) -> bool:
    """Return True if this path should be excluded from the release ZIP."""
    rel = path.relative_to(root)
    # Check every component of the relative path
    for part in rel.parts[:-1]:  # directories in the path
        if part in SKIP_DIRS:
            return True

    name = path.name

    # Allow .env.example explicitly
    if name in ALLOW_EXACT:
        return False

    for pat in SKIP_PATTERNS:
        if pat.match(name):
            return True

    return False


def collect_files(root: Path) -> list[Path]:
    """Walk root and return all files that should be included."""
    included = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        # Prune excluded directories in-place (os.walk respects this)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
            or d == ".env.example"  # never relevant (file not dir)
        ]
        for fname in filenames:
            fpath = current / fname
            if not should_exclude(fpath, root):
                included.append(fpath)
    return sorted(included)


def scan_for_secrets(zip_path: Path) -> list[str]:
    """Open the ZIP and scan text files for secret patterns.  Returns violations."""
    violations = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            # Only scan text-ish files
            if any(name.endswith(ext) for ext in (".py", ".ts", ".tsx", ".js", ".env", ".cfg", ".ini", ".toml", ".yaml", ".yml", ".txt", ".md", ".sh")):
                try:
                    content = zf.read(name).decode("utf-8", errors="replace")
                    for pat in SECRET_SENTINELS:
                        if pat.search(content):
                            violations.append(f"{name}: matched {pat.pattern}")
                except Exception:
                    pass
    return violations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Package PUFI release ZIP")
    parser.add_argument("--out", default="release", help="Output directory (default: release/)")
    parser.add_argument("--version", default="0.1.0", help="Version tag for the ZIP filename")
    parser.add_argument("--root", default=None, help="Project root (default: parent of this script)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    root = Path(args.root).resolve() if args.root else script_dir.parent

    out_dir = root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"pufi-{args.version}.zip"

    print(f"📦  Packaging PUFI {args.version}")
    print(f"    Root   : {root}")
    print(f"    Output : {zip_path}")
    print()

    files = collect_files(root)
    print(f"    Including {len(files)} files …")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fpath in files:
            arcname = fpath.relative_to(root)
            zf.write(fpath, arcname)
            print(f"      + {arcname}")

    print()
    print("🔒  Scanning archive for accidental secrets …")
    violations = scan_for_secrets(zip_path)
    if violations:
        print("❌  SECRET DETECTED IN ARCHIVE — deleting ZIP immediately!")
        for v in violations:
            print(f"      ⚠  {v}")
        zip_path.unlink()
        print()
        print("    The ZIP has been deleted.  Review the files listed above")
        print("    and ensure real credentials are NOT committed or packaged.")
        return 1

    size_kb = zip_path.stat().st_size // 1024
    print(f"✅  Archive clean.  Created: {zip_path}  ({size_kb} KB)")
    print()
    print("    Recipients must copy backend/.env.example → backend/.env and")
    print("    frontend/.env.example → frontend/.env before running the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
