import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_convention_repo(base_dir: Path) -> Path:
    repo_dir = base_dir / "repo"
    write_file(repo_dir / "manage.py", "print('manage')")
    write_file(repo_dir / "project" / "settings.py", "INSTALLED_APPS = ['demo']\n")
    write_file(repo_dir / "project" / "urls.py", "urlpatterns = []\n")
    write_file(repo_dir / "demo" / "models.py", "from django.db import models\n")
    write_file(
        repo_dir / "docs" / "spec.md",
        "# Demo\n## Entity: Demo\n- field: name:str:required\n",
    )
    write_file(
        repo_dir / "rules" / "rules.json",
        json.dumps({"forbidden_envs": ["prod_tx"]}, ensure_ascii=False),
    )
    return repo_dir


def build_cli_env() -> dict:
    return {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}


class CliTests(unittest.TestCase):
    def test_cli_run_command_outputs_run_summary_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            repo_dir = create_convention_repo(base_dir)

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "doc_executor",
                    "run",
                    "--repo",
                    str(repo_dir),
                    "--stop-after",
                    "planned",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=build_cli_env(),
            )

            self.assertEqual(process.returncode, 0, process.stderr)
            payload = json.loads(process.stdout)
            self.assertEqual(payload["stage"], "planned")
            self.assertIn("run_id", payload)

    def test_cli_run_rejects_removed_explicit_path_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            repo_dir = create_convention_repo(base_dir)

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "doc_executor",
                    "run",
                    "--repo",
                    str(repo_dir),
                    "--spec",
                    str(repo_dir / "docs" / "spec.md"),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=build_cli_env(),
            )

            self.assertNotEqual(process.returncode, 0)
            self.assertIn("unrecognized arguments", process.stderr)

    def test_cli_init_creates_repository_convention_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "doc_executor",
                    "init",
                    "--repo",
                    str(repo_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=build_cli_env(),
            )

            self.assertEqual(process.returncode, 0, process.stderr)
            payload = json.loads(process.stdout)
            self.assertEqual(payload["repo"], str(repo_dir))
            self.assertTrue((repo_dir / "docs" / "spec.md").exists())
            self.assertTrue((repo_dir / "rules" / "rules.json").exists())
            self.assertTrue((repo_dir / "agents" / "audit_reviewer.md").exists())
            self.assertTrue((repo_dir / "artifacts").exists())

    def test_cli_init_force_overwrites_existing_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            write_file(repo_dir / "docs" / "spec.md", "# Existing\n")
            write_file(repo_dir / "rules" / "rules.json", "{}\n")

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "doc_executor",
                    "init",
                    "--repo",
                    str(repo_dir),
                    "--force",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=build_cli_env(),
            )

            self.assertEqual(process.returncode, 0, process.stderr)
            spec_content = (repo_dir / "docs" / "spec.md").read_text(encoding="utf-8")
            self.assertIn("ExampleEntity", spec_content)

    def test_cli_approve_uses_repo_and_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            repo_dir = create_convention_repo(base_dir)

            run_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "doc_executor",
                    "run",
                    "--repo",
                    str(repo_dir),
                    "--stop-after",
                    "planned",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=build_cli_env(),
            )
            self.assertEqual(run_process.returncode, 0, run_process.stderr)
            run_payload = json.loads(run_process.stdout)

            approve_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "doc_executor",
                    "approve",
                    "--repo",
                    str(repo_dir),
                    "--run-id",
                    run_payload["run_id"],
                    "--stage",
                    "planned",
                    "--reviewer",
                    "tester",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=build_cli_env(),
            )

            self.assertEqual(approve_process.returncode, 0, approve_process.stderr)
            approve_payload = json.loads(approve_process.stdout)
            self.assertEqual(approve_payload["stage"], "planned")
            self.assertEqual(approve_payload["run_id"], run_payload["run_id"])

    def test_cli_approve_reports_missing_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = create_convention_repo(Path(tmp_dir))

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "doc_executor",
                    "approve",
                    "--repo",
                    str(repo_dir),
                    "--run-id",
                    "missingrun",
                    "--stage",
                    "planned",
                    "--reviewer",
                    "tester",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=build_cli_env(),
            )

            self.assertNotEqual(process.returncode, 0)
            self.assertIn("missingrun", process.stderr)

    def test_cli_run_reports_missing_convention_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            repo_dir.mkdir(parents=True, exist_ok=True)

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "doc_executor",
                    "run",
                    "--repo",
                    str(repo_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=build_cli_env(),
            )

            self.assertNotEqual(process.returncode, 0)
            self.assertIn("init", process.stderr)
