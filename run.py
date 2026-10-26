"""Cross-platform task runner (equivalent to the Makefile, works on Windows).

Usage:
    python run.py all
    python run.py download | clean | load | analyze | maps | export | test
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from crashmap.config import setup_logging  # noqa: E402

log = logging.getLogger("run")


def task_download() -> None:
    from crashmap import download

    download.main()


def task_clean() -> None:
    from crashmap import clean

    clean.main()


def task_load() -> None:
    from crashmap import load_postgres

    load_postgres.main()


def task_analyze() -> None:
    from crashmap import analyze, model

    analyze.main()
    model.main()


def task_maps() -> None:
    from crashmap import maps

    maps.main()


def task_export() -> None:
    from crashmap import export_gold

    export_gold.main()


def task_test() -> None:
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)


TASKS = {
    "download": task_download,
    "clean": task_clean,
    "load": task_load,
    "analyze": task_analyze,
    "maps": task_maps,
    "export": task_export,
    "test": task_test,
}
PIPELINE = ["download", "clean", "test", "load", "analyze", "maps", "export"]


def main() -> None:
    parser = argparse.ArgumentParser(description="CrashMap France pipeline")
    parser.add_argument("target", choices=[*TASKS, "all"], help="step to run")
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="with 'all': skip the PostgreSQL step (no database available)",
    )
    args = parser.parse_args()
    setup_logging()

    steps = PIPELINE if args.target == "all" else [args.target]
    if args.skip_load:
        steps = [s for s in steps if s != "load"]
    for step in steps:
        log.info("=== %s ===", step)
        TASKS[step]()
    log.info("Done: %s", ", ".join(steps))


if __name__ == "__main__":
    main()
