import tempfile
import unittest
from pathlib import Path

from doc_executor.agents import ProjectProfileAgent
from doc_executor.models import RuleSet


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class ProjectProfileAgentTests(unittest.TestCase):
    def test_detects_modular_settings_and_model_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            write_file(repo_dir / "manage.py", "print('manage')\n")
            write_file(
                repo_dir / "app" / "settings" / "base.py",
                "INSTALLED_APPS = [\n"
                "    'django.contrib.auth',\n"
                "    'rest_framework',\n"
                "    'apps.live',\n"
                "]\n",
            )
            write_file(
                repo_dir / "app" / "settings" / "dev_tx.py",
                "INSTALLED_APPS.append('django_extensions')\n"
                "INSTALLED_APPS.append('apps.coin')\n",
            )
            write_file(
                repo_dir / "apps" / "live" / "models" / "student_live_room.py",
                "from django.db import models\n"
                "from common.models.mixin import ModelMixin\n\n"
                "class StudentLiveRoom(ModelMixin):\n"
                "    title = models.CharField(max_length=32)\n\n"
                "    class Meta(ModelMixin.Meta):\n"
                "        db_table = 'student_live_room'\n",
            )
            write_file(
                repo_dir / "apps" / "user" / "models.py",
                "from django.contrib.auth.models import AbstractUser\n"
                "from django.db import models\n\n"
                "class User(AbstractUser):\n"
                "    nickname = models.CharField(max_length=32)\n",
            )
            write_file(
                repo_dir / "app" / "urls.py",
                "from django.urls import path\n\n"
                "urlpatterns = [path('api/demo/', lambda request: None)]\n",
            )
            write_file(repo_dir / "tests" / "test_demo.py", "def test_demo():\n    assert True\n")

            rule_set = RuleSet(
                forbidden_envs=["prod_tx"],
                forbidden_patterns={"join": ".join(", "function_import": "import "},
                n_plus_one_markers=[".get(", ".filter("],
                raw={},
            )

            profile = ProjectProfileAgent().run(
                repo_path=repo_dir,
                rules=rule_set,
                rules_path=repo_dir / "rules" / "rules.json",
            )

            self.assertEqual(profile.framework, "Django")
            self.assertIn("apps.live", profile.apps)
            self.assertIn("apps.coin", profile.apps)
            self.assertTrue(any(model["name"] == "StudentLiveRoom" for model in profile.models))
            self.assertTrue(any(model["name"] == "User" for model in profile.models))
            self.assertTrue(any(model["app"] == "live" for model in profile.models))
            self.assertTrue(any(route["path"] == "/api/demo/" for route in profile.api_routes))
