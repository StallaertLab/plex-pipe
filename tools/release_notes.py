"""Print the GitHub Release notes for one version, taken from CHANGELOG.md.

Used by .github/workflows/publish.yml; exits with an error if CHANGELOG.md has
no section for the version, so a release can't go out without notes.

    python tools/release_notes.py 0.1.0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def release_notes(version: str, changelog: Path = CHANGELOG) -> str:
    """Returns the notes for ``version``: install line, CHANGELOG section, docs link."""
    text = changelog.read_text(encoding="utf-8")
    # From "## [version] ..." up to the next "## [" heading or the link list.
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        sys.exit(f"CHANGELOG.md has no '## [{version}]' section.")
    body = match.group(1).strip()
    return (
        f'Install: `pip install "plex_pipe[all]=={version}"`\n\n'
        f"{body}\n\n"
        "Documentation: https://plexpipe.github.io/plex-pipe/latest/\n"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python tools/release_notes.py VERSION")
    print(release_notes(sys.argv[1]), end="")
