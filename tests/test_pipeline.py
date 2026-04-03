import json
import tempfile
import unittest
from pathlib import Path

from doc_executor.approvals import approve_run_stage
from doc_executor.pipeline import (
    ApprovalRequiredError,
    PipelineRunResult,
    run_pipeline,
)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_sample_repo(base_dir: Path) -> Path:
    repo_dir = base_dir / "sample_repo"
    write_file(repo_dir / "manage.py", "print('manage')")
    write_file(
        repo_dir / "project" / "settings.py",
        "INSTALLED_APPS = ['teacher_app', 'rest_framework']\n",
    )
    write_file(
        repo_dir / "project" / "urls.py",
        "urlpatterns = []\n",
    )
    write_file(
        repo_dir / "teacher_app" / "models.py",
        "from django.db import models\n\n\nclass LegacyTeacher(models.Model):\n    name = models.CharField(max_length=32)\n",
    )
    write_file(
        repo_dir / "teacher_app" / "tests" / "test_models.py",
        "def test_placeholder():\n    assert True\n",
    )
    return repo_dir


def create_spec(base_dir: Path) -> Path:
    spec_path = base_dir / "spec.md"
    write_file(
        spec_path,
        "# Teacher API\n"
        "## Entity: TeacherProfile\n"
        "- field: teacher_name:str:required\n"
        "- field: biography:text:optional\n"
        "## API: POST /api/teacher-profiles\n"
        "- request: teacher_name, biography\n"
        "- response: id, teacher_name, biography\n"
        "## Rule\n"
        "- teacher_name must be unique\n"
        "## Unknown\n"
        "- 是否需要审计字段\n",
    )
    return spec_path


def create_rules(base_dir: Path) -> Path:
    rules_path = base_dir / "rules.json"
    write_file(
        rules_path,
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
    return rules_path


class PipelineTests(unittest.TestCase):
    def test_run_pipeline_creates_core_artifacts_until_planned_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            repo_dir = create_sample_repo(base_dir)
            spec_path = create_spec(base_dir)
            rules_path = create_rules(base_dir)

            result = run_pipeline(
                repo_path=repo_dir,
                spec_path=spec_path,
                rules_path=rules_path,
                artifacts_root=base_dir / "artifacts",
                stop_after="planned",
            )

            self.assertIsInstance(result, PipelineRunResult)
            self.assertEqual(result.stage, "planned")
            self.assertTrue((result.run_dir / "project_profile.json").exists())
            self.assertTrue((result.run_dir / "normalized_spec.json").exists())
            self.assertTrue((result.run_dir / "gap_plan.json").exists())

    def test_run_pipeline_requires_approvals_before_later_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            repo_dir = create_sample_repo(base_dir)
            spec_path = create_spec(base_dir)
            rules_path = create_rules(base_dir)

            initial = run_pipeline(
                repo_path=repo_dir,
                spec_path=spec_path,
                rules_path=rules_path,
                artifacts_root=base_dir / "artifacts",
                stop_after="planned",
            )

            with self.assertRaises(ApprovalRequiredError):
                run_pipeline(
                    repo_path=repo_dir,
                    spec_path=spec_path,
                    rules_path=rules_path,
                    artifacts_root=base_dir / "artifacts",
                    run_id=initial.run_id,
                    resume_from="planned",
                    stop_after="patched",
                )

            approve_run_stage(initial.run_dir, "planned", reviewer="qa")

            patched = run_pipeline(
                repo_path=repo_dir,
                spec_path=spec_path,
                rules_path=rules_path,
                artifacts_root=base_dir / "artifacts",
                run_id=initial.run_id,
                resume_from="planned",
                stop_after="patched",
            )
            self.assertEqual(patched.stage, "patched")
            self.assertTrue((patched.run_dir / "patch_bundle.json").exists())

            approve_run_stage(patched.run_dir, "patched", reviewer="qa")

            audited = run_pipeline(
                repo_path=repo_dir,
                spec_path=spec_path,
                rules_path=rules_path,
                artifacts_root=base_dir / "artifacts",
                run_id=initial.run_id,
                resume_from="patched",
            )
            self.assertEqual(audited.stage, "audited")
            self.assertTrue((audited.run_dir / "audit_report.json").exists())

    def test_prod_tx_is_blocked_before_pipeline_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            repo_dir = create_sample_repo(base_dir)
            spec_path = create_spec(base_dir)
            rules_path = create_rules(base_dir)

            with self.assertRaisesRegex(RuntimeError, "prod_tx"):
                run_pipeline(
                    repo_path=repo_dir,
                    spec_path=spec_path,
                    rules_path=rules_path,
                    artifacts_root=base_dir / "artifacts",
                    target_env="prod_tx",
                )
