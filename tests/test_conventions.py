import json
import tempfile
import unittest
from pathlib import Path

from doc_executor.conventions import ConventionError
from doc_executor.conventions import initialize_repository_convention
from doc_executor.conventions import RepositoryConvention
from doc_executor.conventions import resolve_repository_convention
from doc_executor.pipeline import PipelineRunResult
from doc_executor.pipeline import run_pipeline_from_convention


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_convention_repo(base_dir: Path) -> Path:
    repo_dir = base_dir / "convention_repo"
    write_file(repo_dir / "manage.py", "print('manage')")
    write_file(
        repo_dir / "project" / "settings.py",
        "INSTALLED_APPS = ['teacher_app', 'rest_framework']\n",
    )
    write_file(repo_dir / "project" / "urls.py", "urlpatterns = []\n")
    write_file(
        repo_dir / "teacher_app" / "models.py",
        "from django.db import models\n\n\nclass LegacyTeacher(models.Model):\n    name = models.CharField(max_length=32)\n",
    )
    write_file(
        repo_dir / "docs" / "spec.md",
        "# Teacher API\n"
        "## Entity: TeacherProfile\n"
        "- field: teacher_name:str:required\n"
        "## API: POST /api/teacher-profiles\n"
        "- request: teacher_name\n"
        "- response: id, teacher_name\n",
    )
    write_file(
        repo_dir / "rules" / "rules.json",
        json.dumps(
            {
                "forbidden_envs": ["prod_tx"],
                "forbidden_patterns": {
                    "join": ".jo" "in(",
                    "function_import": "import ",
                },
                "n_plus_one_markers": [".get(", ".filter("],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    write_file(
        repo_dir / "agents" / "audit_reviewer.md",
        "# 审计 Agent\n\n## 目标\n- 校验补丁是否符合规则\n",
    )
    return repo_dir


class ConventionTests(unittest.TestCase):
    def test_initialize_repository_convention_creates_default_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "fresh_repo"
            repo_dir.mkdir(parents=True, exist_ok=True)

            convention = initialize_repository_convention(repo_dir)

            self.assertIsInstance(convention, RepositoryConvention)
            self.assertTrue((repo_dir / "docs" / "spec.md").exists())
            self.assertTrue((repo_dir / "rules" / "rules.json").exists())
            self.assertTrue((repo_dir / "agents" / "audit_reviewer.md").exists())
            self.assertTrue((repo_dir / "artifacts").exists())
            spec_content = (repo_dir / "docs" / "spec.md").read_text(encoding="utf-8")
            rules_content = (repo_dir / "rules" / "rules.json").read_text(encoding="utf-8")
            self.assertIn("## Entity: ExampleEntity", spec_content)
            self.assertIn('"forbidden_envs"', rules_content)

    def test_initialize_repository_convention_does_not_overwrite_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "existing_repo"
            repo_dir.mkdir(parents=True, exist_ok=True)
            write_file(repo_dir / "docs" / "spec.md", "# Existing\n")

            with self.assertRaises(ConventionError):
                initialize_repository_convention(repo_dir)

    def test_initialize_repository_convention_can_force_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "force_repo"
            repo_dir.mkdir(parents=True, exist_ok=True)
            write_file(repo_dir / "docs" / "spec.md", "# Existing\n")
            write_file(repo_dir / "rules" / "rules.json", "{}\n")

            initialize_repository_convention(repo_dir, force=True)

            spec_content = (repo_dir / "docs" / "spec.md").read_text(encoding="utf-8")
            self.assertIn("ExampleEntity", spec_content)

    def test_resolve_repository_convention_uses_default_locations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = create_convention_repo(Path(tmp_dir))

            convention = resolve_repository_convention(repo_dir)

            self.assertIsInstance(convention, RepositoryConvention)
            self.assertEqual(convention.spec_path, repo_dir / "docs" / "spec.md")
            self.assertEqual(convention.rules_path, repo_dir / "rules" / "rules.json")
            self.assertEqual(convention.artifacts_root, repo_dir / "artifacts")
            self.assertIn(repo_dir / "agents", convention.markdown_directories)
            self.assertIn(repo_dir / "rules", convention.markdown_directories)

    def test_run_pipeline_from_convention_runs_without_explicit_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = create_convention_repo(Path(tmp_dir))

            result = run_pipeline_from_convention(
                repo_path=repo_dir,
                stop_after="planned",
            )

            self.assertIsInstance(result, PipelineRunResult)
            self.assertEqual(result.stage, "planned")
            self.assertTrue((repo_dir / "artifacts" / result.run_id / "gap_plan.json").exists())

    def test_resolve_repository_convention_requires_spec_and_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "broken_repo"
            repo_dir.mkdir(parents=True, exist_ok=True)

            with self.assertRaises(ConventionError):
                resolve_repository_convention(repo_dir)
