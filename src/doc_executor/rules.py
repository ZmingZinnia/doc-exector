import json
from pathlib import Path

from doc_executor.markdown_specs import load_builtin_markdown_rule_packs
from doc_executor.markdown_specs import load_project_markdown_rule_packs
from doc_executor.models import RuleSet


def load_rule_set(repo_path: Path, rules_path: Path) -> RuleSet:
    raw = json.loads(rules_path.read_text(encoding="utf-8"))
    markdown_rule_packs = []
    for pack in load_builtin_markdown_rule_packs():
        markdown_rule_packs.append(pack.source)
    for pack in load_project_markdown_rule_packs(repo_path):
        markdown_rule_packs.append(pack.source)
    return RuleSet(
        forbidden_envs=list(raw.get("forbidden_envs", [])),
        forbidden_patterns=dict(raw.get("forbidden_patterns", {})),
        n_plus_one_markers=list(raw.get("n_plus_one_markers", [])),
        raw=raw,
        markdown_rule_packs=markdown_rule_packs,
    )
