from dataclasses import dataclass
from pathlib import Path
import uuid

from doc_executor.conventions import resolve_repository_convention
from doc_executor.agents import CodeExecutionAgent
from doc_executor.agents import DocumentNormalizationAgent
from doc_executor.agents import ExecutionPlanningAgent
from doc_executor.agents import GapPlanningAgent
from doc_executor.agents import ProjectProfileAgent
from doc_executor.agents import ValidationAuditAgent
from doc_executor.approvals import is_stage_approved
from doc_executor.artifacts import ArtifactStore
from doc_executor.guards import assert_environment_allowed
from doc_executor.guards import assert_paths_exist
from doc_executor.models import AuditReport
from doc_executor.models import ExecutionGraph
from doc_executor.models import GapPlan
from doc_executor.models import NormalizedSpec
from doc_executor.models import PatchBundle
from doc_executor.models import ProjectProfile
from doc_executor.models import STAGES
from doc_executor.rules import load_rule_set


class ApprovalRequiredError(RuntimeError):
    pass


@dataclass
class PipelineRunResult:
    run_id: str
    run_dir: Path
    stage: str


def create_run_id() -> str:
    return uuid.uuid4().hex[:12]


def run_pipeline(
    repo_path: Path,
    spec_path: Path,
    rules_path: Path,
    artifacts_root: Path,
    run_id: str = "",
    resume_from: str = "",
    stop_after: str = "",
    target_env: str = "dev_tx",
) -> PipelineRunResult:
    assert_paths_exist(repo_path, spec_path, rules_path)
    rule_set = load_rule_set(repo_path, rules_path)
    assert_environment_allowed(target_env, rule_set)
    if not run_id:
        run_id = create_run_id()
    artifact_store = ArtifactStore(artifacts_root, run_id)
    stop_stage = stop_after if stop_after else "audited"
    profile = None
    normalized_spec = None
    gap_plan = None
    execution_graph = None
    patch_bundle = None
    if _needs_load("detected", resume_from):
        profile = artifact_store.load_model("project_profile.json", ProjectProfile)
    else:
        profile = ProjectProfileAgent().run(repo_path, rule_set, rules_path)
        artifact_store.save_json("project_profile.json", profile)
        artifact_store.save_state("detected")
        if stop_stage == "detected":
            return PipelineRunResult(run_id=run_id, run_dir=artifact_store.run_dir, stage="detected")
    if _needs_load("normalized", resume_from):
        normalized_spec = artifact_store.load_model("normalized_spec.json", NormalizedSpec)
    else:
        normalized_spec = DocumentNormalizationAgent().run(spec_path)
        artifact_store.save_json("normalized_spec.json", normalized_spec)
        artifact_store.save_state("normalized")
        if stop_stage == "normalized":
            return PipelineRunResult(run_id=run_id, run_dir=artifact_store.run_dir, stage="normalized")
    if _needs_load("planned", resume_from):
        gap_plan = artifact_store.load_model("gap_plan.json", GapPlan)
    else:
        gap_plan = GapPlanningAgent().run(profile, normalized_spec)
        artifact_store.save_json("gap_plan.json", gap_plan)
        artifact_store.save_state("planned")
        if stop_stage == "planned":
            return PipelineRunResult(run_id=run_id, run_dir=artifact_store.run_dir, stage="planned")
    if _requires_pass_through("plan_approved", resume_from, stop_stage):
        if not is_stage_approved(artifact_store.run_dir, "planned"):
            raise ApprovalRequiredError("Stage planned requires approval before continuing")
        artifact_store.save_state("plan_approved")
        if stop_stage == "plan_approved":
            return PipelineRunResult(run_id=run_id, run_dir=artifact_store.run_dir, stage="plan_approved")
    if _needs_load("tasked", resume_from):
        execution_graph = artifact_store.load_model("execution_graph.json", ExecutionGraph)
    else:
        execution_graph = ExecutionPlanningAgent().run(gap_plan, rule_set)
        artifact_store.save_json("execution_graph.json", execution_graph)
        artifact_store.save_state("tasked")
        if stop_stage == "tasked":
            return PipelineRunResult(run_id=run_id, run_dir=artifact_store.run_dir, stage="tasked")
    if _needs_load("patched", resume_from):
        patch_bundle = artifact_store.load_model("patch_bundle.json", PatchBundle)
    else:
        patch_bundle = CodeExecutionAgent().run(repo_path, profile, normalized_spec, execution_graph, rule_set)
        artifact_store.save_json("patch_bundle.json", patch_bundle)
        artifact_store.save_state("patched")
        if stop_stage == "patched":
            return PipelineRunResult(run_id=run_id, run_dir=artifact_store.run_dir, stage="patched")
    if _requires_pass_through("patch_approved", resume_from, stop_stage):
        if not is_stage_approved(artifact_store.run_dir, "patched"):
            raise ApprovalRequiredError("Stage patched requires approval before continuing")
        artifact_store.save_state("patch_approved")
        if stop_stage == "patch_approved":
            return PipelineRunResult(run_id=run_id, run_dir=artifact_store.run_dir, stage="patch_approved")
    audit_report = ValidationAuditAgent().run(
        project_profile=profile,
        normalized_spec=normalized_spec,
        gap_plan=gap_plan,
        patch_bundle=patch_bundle,
        rules=rule_set,
        target_env=target_env,
    )
    artifact_store.save_json("audit_report.json", audit_report)
    artifact_store.save_state("audited")
    return PipelineRunResult(run_id=run_id, run_dir=artifact_store.run_dir, stage="audited")


def run_pipeline_from_convention(
    repo_path: Path,
    run_id: str = "",
    resume_from: str = "",
    stop_after: str = "",
    target_env: str = "dev_tx",
) -> PipelineRunResult:
    convention = resolve_repository_convention(repo_path)
    return run_pipeline(
        repo_path=convention.repo_path,
        spec_path=convention.spec_path,
        rules_path=convention.rules_path,
        artifacts_root=convention.artifacts_root,
        run_id=run_id,
        resume_from=resume_from,
        stop_after=stop_after,
        target_env=target_env,
    )


def _needs_load(stage: str, resume_from: str) -> bool:
    if not resume_from:
        return False
    return STAGES.index(stage) <= STAGES.index(resume_from)


def _requires_pass_through(stage: str, resume_from: str, stop_stage: str) -> bool:
    if resume_from:
        if STAGES.index(stage) <= STAGES.index(resume_from):
            return False
    return STAGES.index(stage) <= STAGES.index(stop_stage)
