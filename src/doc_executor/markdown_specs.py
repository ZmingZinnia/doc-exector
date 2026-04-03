from dataclasses import dataclass
import importlib.resources as resources
from pathlib import Path
from typing import List


@dataclass
class MarkdownRulePack:
    name: str
    source: str
    content: str


def load_builtin_markdown_rule_packs() -> List[MarkdownRulePack]:
    packs: List[MarkdownRulePack] = []
    for package_name in ["doc_executor.agent_specs", "doc_executor.rule_packs"]:
        for item_name in resources.contents(package_name):
            if not item_name.endswith(".md"):
                continue
            content = resources.read_text(package_name, item_name, encoding="utf-8")
            packs.append(
                MarkdownRulePack(
                    name=item_name,
                    source="builtin:" + package_name.replace("doc_executor.", "") + "/" + item_name,
                    content=content,
                )
            )
    return packs


def load_project_markdown_rule_packs(repo_path: Path) -> List[MarkdownRulePack]:
    packs: List[MarkdownRulePack] = []
    for folder_name in ["agents", "rules"]:
        folder = repo_path / folder_name
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.md")):
            packs.append(
                MarkdownRulePack(
                    name=path.name,
                    source=str(path),
                    content=path.read_text(encoding="utf-8"),
                )
            )
    return packs
