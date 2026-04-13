"""
JSON file-based state storage.

Tracks which dates have been processed (deduplication) and maintains
a human-readable run log. Designed to be swappable — replace this with
a database, Redis, or cloud key-value store by implementing the same
interface.

The run_log.json is committed to the repo by the GitHub Actions workflow,
giving you a permanent audit trail visible directly in GitHub.
"""
from __future__ import annotations
import json
import pathlib
from datetime import datetime, timezone
from ..models import Result


class JsonStateStore:
    """
    Stores state in state/run_log.json.

    Schema
    ------
    {
      "completed_dates": ["2025-01-01", "2025-01-02", ...],
      "runs": [
        {
          "date": "2025-01-01",
          "engine": "clambakesanta",
          "timestamp": "2025-01-01T12:00:00",
          "themes": ["National Pizza Day"],
          "content_preview": "Cheese pulls skyward..."
        },
        ...
      ]
    }
    """

    def __init__(self, state_dir: str = "state"):
        self.state_dir = pathlib.Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.state_dir / "run_log.json"

    def already_ran_today(self, date_str: str) -> bool:
        """Return True if a successful run was already recorded for date_str."""
        return date_str in self._load().get("completed_dates", [])

    def record_run(self, result: Result) -> None:
        """Append a run record and mark date as complete."""
        log = self._load()
        log.setdefault("completed_dates", [])
        log.setdefault("runs", [])

        date_str = result.event.date_str
        if date_str not in log["completed_dates"]:
            log["completed_dates"].append(date_str)

        log["runs"].append({
            "date": date_str,
            "engine": result.engine_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "themes": result.metadata.get("themes", []),
            "content_preview": result.content[:120].replace("\n", " "),
        })

        self.log_path.write_text(
            json.dumps(log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load(self) -> dict:
        if self.log_path.exists():
            try:
                return json.loads(self.log_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}
