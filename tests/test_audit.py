import unittest

from doc_executor.agents import ValidationAuditAgent
from doc_executor.models import (
    AuditReport,
    GapPlan,
    NormalizedSpec,
    PatchBundle,
    ProjectProfile,
    RuleSet,
)


class AuditAgentTests(unittest.TestCase):
    def test_audit_agent_reports_rule_violations_and_missing_alignment(self) -> None:
        agent = ValidationAuditAgent()
        rules = RuleSet(
            forbidden_envs=["prod_tx"],
            forbidden_patterns={
                "join": ".jo" "in(",
                "function_import": "import ",
            },
            n_plus_one_markers=[".get(", ".filter("],
            raw={},
        )
        profile = ProjectProfile(
            language="Python",
            framework="Django",
            apps=["teacher_app"],
            models=[],
            api_routes=[],
            service_patterns=[],
            test_layout=[],
            env_constraints={"forbidden_envs": ["prod_tx"]},
            rule_file="rules.json",
            unknowns=[],
            source_refs=[],
            confidence=0.8,
        )
        spec = NormalizedSpec(
            entities=[{"name": "TeacherProfile", "fields": []}],
            apis=[{"method": "POST", "path": "/api/teacher-profiles"}],
            business_rules=["teacher_name must be unique"],
            validation_rules=[],
            non_goals=[],
            unknowns=[],
            source_refs=["spec.md:1"],
            confidence=0.8,
        )
        gap_plan = GapPlan(
            model_changes=[{"name": "TeacherProfile"}],
            api_changes=[{"path": "/api/teacher-profiles"}],
            logic_changes=[],
            test_changes=[],
            conflicts=[],
            risks=[],
            requires_approval=[],
            unknowns=[],
            source_refs=["spec.md:1"],
            confidence=0.8,
        )
        patch_bundle = PatchBundle(
            file_edits=[
                {
                    "path": "teacher_app/services.py",
                    "content": "def build_name(parts):\n    import os\n    return '-'." "join(parts)\n",
                },
                {
                    "path": "teacher_app/views.py",
                    "content": "for item in items:\n    Teacher.objects.get(id=item.teacher_id)\n",
                },
            ],
            proposed_code_units=[],
            test_additions=[],
            notes=[],
            limitations=[],
            rule_assertions=[],
            unknowns=[],
            source_refs=["spec.md:1"],
            confidence=0.8,
        )

        report = agent.run(
            project_profile=profile,
            normalized_spec=spec,
            gap_plan=gap_plan,
            patch_bundle=patch_bundle,
            rules=rules,
            target_env="dev_tx",
        )

        self.assertIsInstance(report, AuditReport)
        self.assertGreaterEqual(len(report.rule_violations), 2)
        self.assertTrue(any("N+1" in finding for finding in report.orm_findings))
        self.assertEqual(report.approval_recommendation, "changes_required")
