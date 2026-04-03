import re
from pathlib import Path
from typing import Dict
from typing import List

from doc_executor.markdown_specs import load_builtin_markdown_rule_packs
from doc_executor.markdown_specs import load_project_markdown_rule_packs
from doc_executor.models import AuditReport
from doc_executor.models import ExecutionGraph
from doc_executor.models import GapPlan
from doc_executor.models import NormalizedSpec
from doc_executor.models import PatchBundle
from doc_executor.models import ProjectProfile
from doc_executor.models import RuleSet
from doc_executor.models import average_confidence
from doc_executor.text import lines_to_text


class ProjectProfileAgent:
    def run(self, repo_path: Path, rules: RuleSet, rules_path: Path) -> ProjectProfile:
        settings_files = list(repo_path.rglob("settings.py"))
        model_files = list(repo_path.rglob("models.py"))
        url_files = list(repo_path.rglob("urls.py"))
        test_files = list(repo_path.rglob("test*.py"))
        service_patterns = []
        for candidate in ["services.py", "selectors.py", "repositories.py"]:
            if any(repo_path.rglob(candidate)):
                service_patterns.append(candidate.replace(".py", ""))
        apps = self._detect_apps(settings_files)
        models = self._detect_models(model_files, repo_path)
        api_routes = self._detect_routes(url_files, repo_path)
        if not apps:
            inferred_apps = []
            for model in models:
                app_name = model.get("app", "")
                if app_name and app_name not in inferred_apps:
                    inferred_apps.append(app_name)
            apps = inferred_apps
        unknowns = []
        if not settings_files:
            unknowns.append("未发现 Django settings.py，项目画像置信度下降")
        confidence = average_confidence(
            [
                0.9 if settings_files else 0.4,
                0.8 if models else 0.5,
                0.7 if apps else 0.4,
            ]
        )
        return ProjectProfile(
            language="Python",
            framework="Django" if settings_files else "Unknown",
            apps=apps,
            models=models,
            api_routes=api_routes,
            service_patterns=service_patterns,
            test_layout=[str(path.relative_to(repo_path)) for path in test_files],
            env_constraints={"forbidden_envs": list(rules.forbidden_envs)},
            rule_file=str(rules_path),
            unknowns=unknowns,
            source_refs=[str(path.relative_to(repo_path)) for path in settings_files + model_files + url_files],
            confidence=confidence,
        )

    def _detect_apps(self, settings_files: List[Path]) -> List[str]:
        apps = []
        pattern = re.compile(r"['\"]([a-zA-Z0-9_\\.]+)['\"]")
        for path in settings_files:
            content = path.read_text(encoding="utf-8")
            for match in pattern.findall(content):
                if match.startswith("django."):
                    continue
                if match not in apps:
                    apps.append(match)
        return apps

    def _detect_models(self, model_files: List[Path], repo_path: Path) -> List[Dict[str, str]]:
        models = []
        pattern = re.compile(r"class\\s+([A-Za-z0-9_]+)\\(models\\.Model\\):")
        for path in model_files:
            content = path.read_text(encoding="utf-8")
            app_name = path.parent.name
            if path.parent.name == "models":
                app_name = path.parent.parent.name
            for class_name in pattern.findall(content):
                models.append(
                    {
                        "name": class_name,
                        "app": app_name,
                        "path": str(path.relative_to(repo_path)),
                    }
                )
        return models

    def _detect_routes(self, url_files: List[Path], repo_path: Path) -> List[Dict[str, str]]:
        routes = []
        pattern = re.compile(r"['\"](/[^'\"]*)['\"]")
        for path in url_files:
            content = path.read_text(encoding="utf-8")
            for route_path in pattern.findall(content):
                routes.append(
                    {
                        "path": route_path,
                        "source": str(path.relative_to(repo_path)),
                    }
                )
        return routes


class DocumentNormalizationAgent:
    def run(self, spec_path: Path) -> NormalizedSpec:
        lines = spec_path.read_text(encoding="utf-8").splitlines()
        entities = []
        apis = []
        business_rules = []
        validation_rules = []
        non_goals = []
        unknowns = []
        source_refs = []
        current_entity = None
        current_api = None
        section = ""
        line_number = 0
        for line in lines:
            line_number += 1
            stripped = line.strip()
            if stripped.startswith("## Entity:"):
                entity_name = stripped.split(":", 1)[1].strip()
                current_entity = {"name": entity_name, "fields": []}
                entities.append(current_entity)
                current_api = None
                section = "entity"
                source_refs.append(str(spec_path) + ":" + str(line_number))
                continue
            if stripped.startswith("## API:"):
                api_text = stripped.split(":", 1)[1].strip()
                parts = api_text.split(" ", 1)
                method = parts[0] if parts else "GET"
                path = parts[1] if len(parts) > 1 else "/"
                current_api = {"method": method, "path": path, "request": [], "response": []}
                apis.append(current_api)
                current_entity = None
                section = "api"
                source_refs.append(str(spec_path) + ":" + str(line_number))
                continue
            if stripped.startswith("## Rule"):
                section = "rule"
                continue
            if stripped.startswith("## Unknown"):
                section = "unknown"
                continue
            if stripped.startswith("## NonGoal"):
                section = "non_goal"
                continue
            if stripped.startswith("- field:") and current_entity is not None:
                field_text = stripped.split(":", 1)[1].strip()
                current_entity["fields"].append({"definition": field_text})
                continue
            if stripped.startswith("- request:") and current_api is not None:
                request_text = stripped.split(":", 1)[1].strip()
                current_api["request"].append(request_text)
                continue
            if stripped.startswith("- response:") and current_api is not None:
                response_text = stripped.split(":", 1)[1].strip()
                current_api["response"].append(response_text)
                continue
            if stripped.startswith("- "):
                value = stripped[2:].strip()
                if section == "rule":
                    business_rules.append(value)
                    if "must" in value or "required" in value:
                        validation_rules.append(value)
                elif section == "unknown":
                    unknowns.append(value)
                elif section == "non_goal":
                    non_goals.append(value)
        confidence = average_confidence(
            [
                0.8 if entities else 0.5,
                0.8 if apis else 0.5,
                0.7 if business_rules else 0.5,
            ]
        )
        return NormalizedSpec(
            entities=entities,
            apis=apis,
            business_rules=business_rules,
            validation_rules=validation_rules,
            non_goals=non_goals,
            unknowns=unknowns,
            source_refs=source_refs,
            confidence=confidence,
        )


class GapPlanningAgent:
    def run(self, project_profile: ProjectProfile, normalized_spec: NormalizedSpec) -> GapPlan:
        existing_model_names = []
        for model in project_profile.models:
            existing_model_names.append(model.get("name", "").lower())
        existing_routes = []
        for route in project_profile.api_routes:
            existing_routes.append(route.get("path", ""))
        model_changes = []
        api_changes = []
        logic_changes = []
        test_changes = []
        risks = []
        requires_approval = []
        for entity in normalized_spec.entities:
            action = "create"
            if entity.get("name", "").lower() in existing_model_names:
                action = "update"
                risks.append("实体 " + entity.get("name", "") + " 已存在，需人工确认覆盖策略")
            model_changes.append(
                {
                    "action": action,
                    "name": entity.get("name", ""),
                    "fields": list(entity.get("fields", [])),
                }
            )
            requires_approval.append("model:" + entity.get("name", ""))
            test_changes.append(
                {
                    "name": "test_model_" + entity.get("name", "").lower(),
                    "kind": "model",
                }
            )
        for api in normalized_spec.apis:
            action = "create"
            if api.get("path", "") in existing_routes:
                action = "update"
                risks.append("接口 " + api.get("path", "") + " 已存在，需人工确认兼容方式")
            api_changes.append(
                {
                    "action": action,
                    "method": api.get("method", ""),
                    "path": api.get("path", ""),
                }
            )
            requires_approval.append("api:" + api.get("path", ""))
            test_changes.append(
                {
                    "name": "test_api_" + api.get("path", "/").replace("/", "_"),
                    "kind": "api",
                }
            )
        for rule in normalized_spec.business_rules:
            logic_changes.append({"rule": rule})
        confidence = average_confidence(
            [project_profile.confidence, normalized_spec.confidence]
        )
        return GapPlan(
            model_changes=model_changes,
            api_changes=api_changes,
            logic_changes=logic_changes,
            test_changes=test_changes,
            conflicts=[],
            risks=risks,
            requires_approval=requires_approval,
            unknowns=list(normalized_spec.unknowns),
            source_refs=list(normalized_spec.source_refs),
            confidence=confidence,
        )


class ExecutionPlanningAgent:
    def run(self, gap_plan: GapPlan, rules: RuleSet) -> ExecutionGraph:
        tasks = []
        dependencies: Dict[str, List[str]] = {}
        task_types = []
        input_refs = []
        model_task_ids = []
        api_task_ids = []
        task_index = 1
        for change in gap_plan.model_changes:
            task_id = "task_" + str(task_index)
            task_index += 1
            tasks.append(
                {
                    "id": task_id,
                    "task_type": "model_update",
                    "payload": change,
                }
            )
            dependencies[task_id] = []
            task_types.append("model_update")
            input_refs.append("model:" + change.get("name", ""))
            model_task_ids.append(task_id)
        for change in gap_plan.api_changes:
            task_id = "task_" + str(task_index)
            task_index += 1
            tasks.append(
                {
                    "id": task_id,
                    "task_type": "api_update",
                    "payload": change,
                }
            )
            dependencies[task_id] = list(model_task_ids)
            task_types.append("api_update")
            input_refs.append("api:" + change.get("path", ""))
            api_task_ids.append(task_id)
        for change in gap_plan.logic_changes:
            task_id = "task_" + str(task_index)
            task_index += 1
            tasks.append(
                {
                    "id": task_id,
                    "task_type": "logic_update",
                    "payload": change,
                }
            )
            dependencies[task_id] = list(api_task_ids)
            task_types.append("logic_update")
            input_refs.append("logic:" + change.get("rule", ""))
        for change in gap_plan.test_changes:
            task_id = "task_" + str(task_index)
            task_index += 1
            tasks.append(
                {
                    "id": task_id,
                    "task_type": "test_update",
                    "payload": change,
                }
            )
            dependencies[task_id] = list(dependencies.keys())
            task_types.append("test_update")
            input_refs.append("test:" + change.get("name", ""))
        guardrails = []
        for forbidden_env in rules.forbidden_envs:
            guardrails.append("禁止执行环境: " + forbidden_env)
        for pack_source in rules.markdown_rule_packs:
            guardrails.append("加载规则包: " + pack_source)
        guardrails.append("禁止 join")
        guardrails.append("禁止函数内 import")
        guardrails.append("禁止 N+1 ORM 查询")
        return ExecutionGraph(
            tasks=tasks,
            dependencies=dependencies,
            task_type=task_types,
            input_refs=input_refs,
            guardrails=guardrails,
            approval_points=["planned", "patched"],
            unknowns=list(gap_plan.unknowns),
            source_refs=list(gap_plan.source_refs),
            confidence=gap_plan.confidence,
        )


class CodeExecutionAgent:
    def run(
        self,
        repo_path: Path,
        project_profile: ProjectProfile,
        normalized_spec: NormalizedSpec,
        execution_graph: ExecutionGraph,
        rules: RuleSet,
    ) -> PatchBundle:
        app_name = self._pick_app_name(project_profile)
        file_edits = []
        proposed_code_units = []
        test_additions = []
        notes = []
        limitations = ["v1 仅生成 model 代码草案，不生成 migration"]
        rule_assertions = [
            "未直接写入仓库代码",
            "已附带 Markdown 规则包来源",
            "目标环境需继续通过守卫检查",
        ]
        for entity in normalized_spec.entities:
            model_content = self._build_model_content(entity)
            file_edits.append(
                {
                    "path": app_name + "/models.py",
                    "content": model_content,
                }
            )
            proposed_code_units.append(
                {
                    "kind": "model",
                    "name": entity.get("name", ""),
                    "target": app_name + "/models.py",
                }
            )
        for api in normalized_spec.apis:
            view_content = self._build_view_content(api, normalized_spec.entities)
            file_edits.append(
                {
                    "path": app_name + "/views.py",
                    "content": view_content,
                }
            )
            proposed_code_units.append(
                {
                    "kind": "api",
                    "name": api.get("path", ""),
                    "target": app_name + "/views.py",
                }
            )
        test_content = self._build_test_content(normalized_spec)
        test_additions.append(
            {
                "path": app_name + "/tests/test_generated.py",
                "content": test_content,
            }
        )
        notes.append("执行图任务数: " + str(len(execution_graph.tasks)))
        for pack in load_builtin_markdown_rule_packs():
            notes.append("内置规则说明: " + pack.source)
        for pack in load_project_markdown_rule_packs(repo_path):
            notes.append("项目规则说明: " + pack.source)
        return PatchBundle(
            file_edits=file_edits,
            proposed_code_units=proposed_code_units,
            test_additions=test_additions,
            notes=notes,
            limitations=limitations,
            rule_assertions=rule_assertions,
            unknowns=list(normalized_spec.unknowns),
            source_refs=list(normalized_spec.source_refs),
            confidence=average_confidence([project_profile.confidence, normalized_spec.confidence]),
        )

    def _pick_app_name(self, project_profile: ProjectProfile) -> str:
        for app_name in project_profile.apps:
            if "." in app_name:
                continue
            if app_name.startswith("django"):
                continue
            return app_name
        if project_profile.models:
            return project_profile.models[0].get("app", "app")
        return "app"

    def _build_model_content(self, entity: Dict[str, object]) -> str:
        lines = [
            "from django.db import models",
            "",
            "",
            "class " + str(entity.get("name", "GeneratedModel")) + "(models.Model):",
        ]
        fields = entity.get("fields", [])
        if not isinstance(fields, list):
            fields = []
        for field_data in fields:
            definition = ""
            if isinstance(field_data, dict):
                definition = str(field_data.get("definition", "name:str:required"))
            field_name, field_code = self._parse_field_definition(definition)
            lines.append("    " + field_name + " = " + field_code)
        lines.append("")
        lines.append("    class Meta:")
        lines.append("        app_label = 'generated'")
        return lines_to_text(lines)

    def _parse_field_definition(self, definition: str) -> List[str]:
        parts = definition.split(":")
        field_name = parts[0].strip() if parts else "name"
        field_type = parts[1].strip() if len(parts) > 1 else "str"
        required = parts[2].strip() if len(parts) > 2 else "required"
        if field_type == "text":
            field_code = "models.TextField(blank=" + self._blank_text(required) + ", null=" + self._blank_text(required) + ")"
        else:
            field_code = "models.CharField(max_length=255, blank=" + self._blank_text(required) + ", null=" + self._blank_text(required) + ")"
        return [field_name, field_code]

    def _blank_text(self, required: str) -> str:
        if required == "required":
            return "False"
        return "True"

    def _build_view_content(
        self,
        api: Dict[str, object],
        entities: List[Dict[str, object]],
    ) -> str:
        model_name = "GeneratedModel"
        if entities:
            model_name = str(entities[0].get("name", "GeneratedModel"))
        lines = [
            "from django.http import JsonResponse",
            "from django.views import View",
            "",
            "",
            "class GeneratedEndpointView(View):",
            "    def post(self, request):",
            "        payload = {'message': 'Patch proposal only', 'model': '" + model_name + "'}",
            "        return JsonResponse(payload, status=202)",
        ]
        return lines_to_text(lines)

    def _build_test_content(self, normalized_spec: NormalizedSpec) -> str:
        lines = [
            "from django.test import TestCase",
            "",
            "",
            "class GeneratedContractTests(TestCase):",
            "    def test_generated_spec_has_entities(self):",
            "        self.assertGreaterEqual(" + str(len(normalized_spec.entities)) + ", 1)",
        ]
        return lines_to_text(lines)


class ValidationAuditAgent:
    def run(
        self,
        project_profile: ProjectProfile,
        normalized_spec: NormalizedSpec,
        gap_plan: GapPlan,
        patch_bundle: PatchBundle,
        rules: RuleSet,
        target_env: str,
    ) -> AuditReport:
        rule_violations = []
        architecture_findings = []
        orm_findings = []
        env_findings = []
        test_coverage_findings = []
        spec_alignment = []
        if target_env in rules.forbidden_envs:
            env_findings.append("目标环境被禁止: " + target_env)
        for file_edit in patch_bundle.file_edits:
            path = str(file_edit.get("path", ""))
            content = str(file_edit.get("content", ""))
            self._scan_rule_violations(path, content, rules, rule_violations)
            self._scan_n_plus_one(path, content, rules, orm_findings)
            if path.endswith("views.py") and "service" not in path and project_profile.service_patterns:
                architecture_findings.append("项目存在 service 模式，建议确认 view 是否过重: " + path)
        if not patch_bundle.test_additions:
            test_coverage_findings.append("未生成测试建议")
        for entity in normalized_spec.entities:
            entity_name = entity.get("name", "")
            if not self._gap_has_entity(gap_plan, str(entity_name)):
                spec_alignment.append("缺少实体落地: " + str(entity_name))
        for api in normalized_spec.apis:
            api_path = api.get("path", "")
            if not self._gap_has_api(gap_plan, str(api_path)):
                spec_alignment.append("缺少接口落地: " + str(api_path))
        approval_recommendation = "approved"
        if rule_violations or orm_findings or env_findings or spec_alignment:
            approval_recommendation = "changes_required"
        return AuditReport(
            spec_alignment=spec_alignment,
            rule_violations=rule_violations,
            architecture_findings=architecture_findings,
            orm_findings=orm_findings,
            env_findings=env_findings,
            test_coverage_findings=test_coverage_findings,
            approval_recommendation=approval_recommendation,
            unknowns=list(gap_plan.unknowns),
            source_refs=list(normalized_spec.source_refs),
            confidence=average_confidence([project_profile.confidence, normalized_spec.confidence, gap_plan.confidence]),
        )

    def _scan_rule_violations(
        self,
        path: str,
        content: str,
        rules: RuleSet,
        rule_violations: List[str],
    ) -> None:
        for name, pattern in rules.forbidden_patterns.items():
            if name == "function_import":
                if self._contains_function_import(content):
                    rule_violations.append("函数内 import 违规: " + path)
                continue
            if pattern and pattern in content:
                rule_violations.append("命中禁用规则 " + name + ": " + path)

    def _scan_n_plus_one(
        self,
        path: str,
        content: str,
        rules: RuleSet,
        orm_findings: List[str],
    ) -> None:
        lines = content.splitlines()
        line_index = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("for "):
                lookahead = 0
                while lookahead < 3:
                    next_index = line_index + lookahead + 1
                    if next_index >= len(lines):
                        break
                    next_line = lines[next_index]
                    for marker in rules.n_plus_one_markers:
                        if marker in next_line:
                            orm_findings.append("Potential N+1 查询: " + path)
                            return
                    lookahead += 1
            line_index += 1

    def _contains_function_import(self, content: str) -> bool:
        lines = content.splitlines()
        def_indent = None
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if stripped.startswith("def "):
                def_indent = indent
                continue
            if def_indent is not None and stripped:
                if indent <= def_indent:
                    def_indent = None
                elif stripped.startswith("import ") or stripped.startswith("from "):
                    return True
        return False

    def _gap_has_entity(self, gap_plan: GapPlan, entity_name: str) -> bool:
        for change in gap_plan.model_changes:
            if change.get("name", "") == entity_name:
                return True
        return False

    def _gap_has_api(self, gap_plan: GapPlan, api_path: str) -> bool:
        for change in gap_plan.api_changes:
            if change.get("path", "") == api_path:
                return True
        return False
