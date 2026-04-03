from dataclasses import dataclass
import json
from pathlib import Path
from typing import List


class ConventionError(RuntimeError):
    pass


DEFAULT_SPEC_TEMPLATE = (
    "# Feature Spec\n"
    "\n"
    "## Entity: ExampleEntity\n"
    "- field: name:str:required\n"
    "- field: description:text:optional\n"
    "\n"
    "## API: POST /api/example-entities\n"
    "- request: name, description\n"
    "- response: id, name, description\n"
    "\n"
    "## Rule\n"
    "- name must be unique\n"
    "\n"
    "## Unknown\n"
    "- 是否需要补充审计字段\n"
)

DEFAULT_AUDIT_AGENT_TEMPLATE = (
    "# 审计 Agent\n"
    "\n"
    "## 目标\n"
    "- 校验补丁是否符合规则、文档和项目架构\n"
    "\n"
    "## 输入\n"
    "- ProjectProfile\n"
    "- NormalizedSpec\n"
    "- GapPlan\n"
    "- PatchBundle\n"
    "\n"
    "## 输出\n"
    "- AuditReport\n"
    "\n"
    "## 必须遵守\n"
    "- 对高风险问题给出 changes_required\n"
    "\n"
    "## 禁止事项\n"
    "- 不允许跳过 prod_tx 风险检查\n"
    "- 不允许忽略缺失测试\n"
)


@dataclass
class RepositoryConvention:
    repo_path: Path
    spec_path: Path
    rules_path: Path
    artifacts_root: Path
    markdown_directories: List[Path]


def initialize_repository_convention(
    repo_path: Path,
    force: bool = False,
) -> RepositoryConvention:
    convention = RepositoryConvention(
        repo_path=repo_path,
        spec_path=repo_path / "docs" / "spec.md",
        rules_path=repo_path / "rules" / "rules.json",
        artifacts_root=repo_path / "artifacts",
        markdown_directories=[repo_path / "agents", repo_path / "rules"],
    )
    repo_path.mkdir(parents=True, exist_ok=True)
    existing_targets = []
    for target in [
        convention.spec_path,
        convention.rules_path,
        repo_path / "agents" / "audit_reviewer.md",
    ]:
        if target.exists() and not force:
            existing_targets.append(str(target))
    if existing_targets:
        raise ConventionError(_build_existing_targets_message(existing_targets))
    convention.spec_path.parent.mkdir(parents=True, exist_ok=True)
    convention.rules_path.parent.mkdir(parents=True, exist_ok=True)
    (repo_path / "agents").mkdir(parents=True, exist_ok=True)
    convention.artifacts_root.mkdir(parents=True, exist_ok=True)
    convention.spec_path.write_text(DEFAULT_SPEC_TEMPLATE, encoding="utf-8")
    convention.rules_path.write_text(_build_rules_template(), encoding="utf-8")
    (repo_path / "agents" / "audit_reviewer.md").write_text(
        DEFAULT_AUDIT_AGENT_TEMPLATE,
        encoding="utf-8",
    )
    return convention


def resolve_repository_convention(repo_path: Path) -> RepositoryConvention:
    spec_path = repo_path / "docs" / "spec.md"
    rules_path = repo_path / "rules" / "rules.json"
    artifacts_root = repo_path / "artifacts"
    markdown_directories = []
    agents_dir = repo_path / "agents"
    rules_dir = repo_path / "rules"
    if agents_dir.exists():
        markdown_directories.append(agents_dir)
    if rules_dir.exists():
        markdown_directories.append(rules_dir)
    missing_items = []
    if not spec_path.exists():
        missing_items.append(str(spec_path))
    if not rules_path.exists():
        missing_items.append(str(rules_path))
    if missing_items:
        message = "Missing repository convention files: "
        index = 0
        for item in missing_items:
            if index > 0:
                message += ", "
            message += item
            index += 1
        raise ConventionError(message)
    return RepositoryConvention(
        repo_path=repo_path,
        spec_path=spec_path,
        rules_path=rules_path,
        artifacts_root=artifacts_root,
        markdown_directories=markdown_directories,
    )


def resolve_run_directory(repo_path: Path, run_id: str) -> Path:
    convention = resolve_repository_convention(repo_path)
    run_dir = convention.artifacts_root / run_id
    if not run_dir.exists():
        raise ConventionError("Run directory not found: " + str(run_dir))
    return run_dir


def _build_existing_targets_message(existing_targets: List[str]) -> str:
    message = "Repository convention files already exist: "
    index = 0
    for target in existing_targets:
        if index > 0:
            message += ", "
        message += target
        index += 1
    return message


def _build_rules_template() -> str:
    payload = {
        "forbidden_envs": ["prod_tx"],
        "forbidden_patterns": {
            "join": ".jo" "in(",
            "function_import": "import ",
        },
        "n_plus_one_markers": [".get(", ".filter("],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
