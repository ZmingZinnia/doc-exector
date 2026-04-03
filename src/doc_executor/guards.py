from pathlib import Path

from doc_executor.models import RuleSet


def assert_environment_allowed(target_env: str, rules: RuleSet) -> None:
    for forbidden_env in rules.forbidden_envs:
        if target_env == forbidden_env:
            raise RuntimeError("Blocked forbidden environment: " + target_env)


def assert_paths_exist(repo_path: Path, spec_path: Path, rules_path: Path) -> None:
    if not repo_path.exists():
        raise FileNotFoundError("Repository path not found: " + str(repo_path))
    if not spec_path.exists():
        raise FileNotFoundError("Spec path not found: " + str(spec_path))
    if not rules_path.exists():
        raise FileNotFoundError("Rules path not found: " + str(rules_path))
