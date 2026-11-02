import asyncio
import sys
import os

# Local Docker services
os.environ.setdefault("POSTGRES_DSN", "postgresql://whodba:whopass@localhost:5433/who_eats_whom")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "testpass")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")

if sys.platform == "win32":
  asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / "test_results"
_results = []
_started = None


def pytest_sessionstart(session):
  global _started
  _started = datetime.now()


def pytest_runtest_logreport(report):
  # Record each test once: its result, or a failure/skip during setup
  if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
    _results.append(report)


def pytest_sessionfinish(session, exitstatus):
  LOG_DIR.mkdir(exist_ok=True)
  finished = datetime.now()

  counts = {"passed": 0, "failed": 0, "skipped": 0}
  for r in _results:
    counts[r.outcome] += 1

  lines = [
    "Who Eats Whom - test report",
    f"Started:  {_started:%Y-%m-%d %H:%M:%S}",
    f"Finished: {finished:%Y-%m-%d %H:%M:%S}  ({(finished - _started).total_seconds():.1f}s)",
    f"Python:   {sys.version.split()[0]}",
    f"Result:   {counts['passed']} passed, {counts['failed']} failed, {counts['skipped']} skipped",
    "",
    "Tests",
    "-----",
  ]
  for r in _results:
    lines.append(f"{r.outcome.upper():8} {r.nodeid}  ({r.duration:.2f}s)")

  problems = [r for r in _results if r.outcome != "passed"]
  if problems:
    lines += ["", "Failures and skips", "------------------"]
    for r in problems:
      lines.append(f"\n{r.outcome.upper()}: {r.nodeid}")
      if r.outcome == "skipped":
        lines.append(f"  {r.longrepr[2]}")
      else:
        lines.append(r.longreprtext)

  text = "\n".join(lines) + "\n"
  (LOG_DIR / f"report_{_started:%Y-%m-%d_%H-%M-%S}.txt").write_text(text, encoding="utf-8")
  (LOG_DIR / "latest.txt").write_text(text, encoding="utf-8")