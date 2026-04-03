from datetime import datetime
import json
from pathlib import Path
from typing import Any
from typing import Dict


def approval_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def approvals_file(run_dir: Path) -> Path:
    return run_dir / "approvals.json"


def load_approvals(run_dir: Path) -> Dict[str, Any]:
    path = approvals_file(run_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_approvals(run_dir: Path, payload: Dict[str, Any]) -> None:
    approvals_file(run_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def approve_run_stage(run_dir: Path, stage: str, reviewer: str) -> None:
    payload = load_approvals(run_dir)
    payload[stage] = {
        "approved": True,
        "reviewer": reviewer,
        "approved_at": approval_timestamp(),
    }
    save_approvals(run_dir, payload)


def is_stage_approved(run_dir: Path, stage: str) -> bool:
    payload = load_approvals(run_dir)
    stage_data = payload.get(stage, {})
    return bool(stage_data.get("approved", False))
