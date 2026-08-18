from __future__ import annotations

from pathlib import Path

from .materializer import remove_generated_application

DEFAULT_DATABASE_PATH = Path("data") / "url_shortener.sqlite3"


def cleanup_local_state(
    output_directory: Path,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> list[Path]:
    """Remove only runtime artifacts created by local demos.

    The target list is intentionally explicit. This command never removes source
    code, tests, documentation, or a directory tree.
    """
    targets = [
        output_directory / "run.json",
        database_path,
        Path(f"{database_path}-journal"),
        Path(f"{database_path}-shm"),
        Path(f"{database_path}-wal"),
    ]
    removed: list[Path] = []

    removed_application = remove_generated_application(output_directory)
    if removed_application is not None:
        removed.append(removed_application)

    for target in targets:
        if target.is_file():
            target.unlink()
            removed.append(target)

    return removed
