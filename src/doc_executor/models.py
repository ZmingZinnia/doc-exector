from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict
from typing import List


STAGES = [
    "detected",
    "normalized",
    "planned",
    "plan_approved",
    "tasked",
    "patched",
    "patch_approved",
    "audited",
]


def average_confidence(values: List[float]) -> float:
    if not values:
        return 0.0
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    if count == 0:
        return 0.0
    return total / count


def model_to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


@dataclass
class RuleSet:
    forbidden_envs: List[str]
    forbidden_patterns: Dict[str, str]
    n_plus_one_markers: List[str]
    raw: Dict[str, Any]
    markdown_rule_packs: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleSet":
        return cls(
            forbidden_envs=list(data.get("forbidden_envs", [])),
            forbidden_patterns=dict(data.get("forbidden_patterns", {})),
            n_plus_one_markers=list(data.get("n_plus_one_markers", [])),
            raw=dict(data.get("raw", {})),
            markdown_rule_packs=list(data.get("markdown_rule_packs", [])),
        )


@dataclass
class ProjectProfile:
    language: str
    framework: str
    apps: List[str]
    models: List[Dict[str, Any]]
    api_routes: List[Dict[str, Any]]
    service_patterns: List[str]
    test_layout: List[str]
    env_constraints: Dict[str, Any]
    rule_file: str
    unknowns: List[str]
    source_refs: List[str]
    confidence: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectProfile":
        return cls(
            language=data.get("language", ""),
            framework=data.get("framework", ""),
            apps=list(data.get("apps", [])),
            models=list(data.get("models", [])),
            api_routes=list(data.get("api_routes", [])),
            service_patterns=list(data.get("service_patterns", [])),
            test_layout=list(data.get("test_layout", [])),
            env_constraints=dict(data.get("env_constraints", {})),
            rule_file=data.get("rule_file", ""),
            unknowns=list(data.get("unknowns", [])),
            source_refs=list(data.get("source_refs", [])),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass
class NormalizedSpec:
    entities: List[Dict[str, Any]]
    apis: List[Dict[str, Any]]
    business_rules: List[str]
    validation_rules: List[str]
    non_goals: List[str]
    unknowns: List[str]
    source_refs: List[str]
    confidence: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormalizedSpec":
        return cls(
            entities=list(data.get("entities", [])),
            apis=list(data.get("apis", [])),
            business_rules=list(data.get("business_rules", [])),
            validation_rules=list(data.get("validation_rules", [])),
            non_goals=list(data.get("non_goals", [])),
            unknowns=list(data.get("unknowns", [])),
            source_refs=list(data.get("source_refs", [])),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass
class GapPlan:
    model_changes: List[Dict[str, Any]]
    api_changes: List[Dict[str, Any]]
    logic_changes: List[Dict[str, Any]]
    test_changes: List[Dict[str, Any]]
    conflicts: List[str]
    risks: List[str]
    requires_approval: List[str]
    unknowns: List[str]
    source_refs: List[str]
    confidence: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GapPlan":
        return cls(
            model_changes=list(data.get("model_changes", [])),
            api_changes=list(data.get("api_changes", [])),
            logic_changes=list(data.get("logic_changes", [])),
            test_changes=list(data.get("test_changes", [])),
            conflicts=list(data.get("conflicts", [])),
            risks=list(data.get("risks", [])),
            requires_approval=list(data.get("requires_approval", [])),
            unknowns=list(data.get("unknowns", [])),
            source_refs=list(data.get("source_refs", [])),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass
class ExecutionGraph:
    tasks: List[Dict[str, Any]]
    dependencies: Dict[str, List[str]]
    task_type: List[str]
    input_refs: List[str]
    guardrails: List[str]
    approval_points: List[str]
    unknowns: List[str]
    source_refs: List[str]
    confidence: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionGraph":
        return cls(
            tasks=list(data.get("tasks", [])),
            dependencies=dict(data.get("dependencies", {})),
            task_type=list(data.get("task_type", [])),
            input_refs=list(data.get("input_refs", [])),
            guardrails=list(data.get("guardrails", [])),
            approval_points=list(data.get("approval_points", [])),
            unknowns=list(data.get("unknowns", [])),
            source_refs=list(data.get("source_refs", [])),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass
class PatchBundle:
    file_edits: List[Dict[str, Any]]
    proposed_code_units: List[Dict[str, Any]]
    test_additions: List[Dict[str, Any]]
    notes: List[str]
    limitations: List[str]
    rule_assertions: List[str]
    unknowns: List[str]
    source_refs: List[str]
    confidence: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatchBundle":
        return cls(
            file_edits=list(data.get("file_edits", [])),
            proposed_code_units=list(data.get("proposed_code_units", [])),
            test_additions=list(data.get("test_additions", [])),
            notes=list(data.get("notes", [])),
            limitations=list(data.get("limitations", [])),
            rule_assertions=list(data.get("rule_assertions", [])),
            unknowns=list(data.get("unknowns", [])),
            source_refs=list(data.get("source_refs", [])),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass
class AuditReport:
    spec_alignment: List[str]
    rule_violations: List[str]
    architecture_findings: List[str]
    orm_findings: List[str]
    env_findings: List[str]
    test_coverage_findings: List[str]
    approval_recommendation: str
    unknowns: List[str]
    source_refs: List[str]
    confidence: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditReport":
        return cls(
            spec_alignment=list(data.get("spec_alignment", [])),
            rule_violations=list(data.get("rule_violations", [])),
            architecture_findings=list(data.get("architecture_findings", [])),
            orm_findings=list(data.get("orm_findings", [])),
            env_findings=list(data.get("env_findings", [])),
            test_coverage_findings=list(data.get("test_coverage_findings", [])),
            approval_recommendation=data.get("approval_recommendation", "approved"),
            unknowns=list(data.get("unknowns", [])),
            source_refs=list(data.get("source_refs", [])),
            confidence=float(data.get("confidence", 0.0)),
        )
