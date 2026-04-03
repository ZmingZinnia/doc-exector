from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Type
from typing import TypeVar

from doc_executor.models import model_to_dict


T = TypeVar("T")


def utc_now_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class ArtifactStore:
    def __init__(self, artifacts_root: Path, run_id: str) -> None:
        self.artifacts_root = artifacts_root
        self.run_id = run_id
        self.run_dir = artifacts_root / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def save_json(self, name: str, payload: Any) -> Path:
        path = self.run_dir / name
        if hasattr(payload, "__dataclass_fields__"):
            serializable = asdict(payload)
        else:
            serializable = model_to_dict(payload)
        path.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load_json(self, name: str) -> Dict[str, Any]:
        path = self.run_dir / name
        return json.loads(path.read_text(encoding="utf-8"))

    def load_model(self, name: str, model_type: Type[T]) -> T:
        data = self.load_json(name)
        return model_type.from_dict(data)

    def save_state(self, stage: str) -> None:
        state = self.read_state()
        history = list(state.get("history", []))
        history.append({"stage": stage, "at": utc_now_text()})
        state["latest_stage"] = stage
        state["history"] = history
        state["run_id"] = self.run_id
        self.save_json("state.json", state)

    def read_state(self) -> Dict[str, Any]:
        path = self.run_dir / "state.json"
        if not path.exists():
            return {"run_id": self.run_id, "history": []}
        return json.loads(path.read_text(encoding="utf-8"))
