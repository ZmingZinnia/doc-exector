import argparse
import json
import sys
from pathlib import Path
from typing import Any
from typing import Dict

from doc_executor.approvals import approve_run_stage
from doc_executor.conventions import ConventionError
from doc_executor.conventions import initialize_repository_convention
from doc_executor.conventions import resolve_run_directory
from doc_executor.pipeline import run_pipeline_from_convention


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="doc-executor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--repo", required=True)
    init_parser.add_argument("--force", action="store_true")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--repo", required=True)
    run_parser.add_argument("--run-id", required=False, default="")
    run_parser.add_argument("--resume-from", required=False, default="")
    run_parser.add_argument("--stop-after", required=False, default="")
    run_parser.add_argument("--target-env", required=False, default="dev_tx")

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--repo", required=True)
    approve_parser.add_argument("--run-id", required=True)
    approve_parser.add_argument("--stage", required=True)
    approve_parser.add_argument("--reviewer", required=True)

    return parser


def run_cli(argv: Any = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            convention = initialize_repository_convention(
                repo_path=Path(args.repo),
                force=args.force,
            )
            print(
                json.dumps(
                    {
                        "repo": str(convention.repo_path),
                        "spec": str(convention.spec_path),
                        "rules": str(convention.rules_path),
                        "artifacts_root": str(convention.artifacts_root),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "approve":
            run_dir = resolve_run_directory(Path(args.repo), args.run_id)
            approve_run_stage(run_dir, args.stage, args.reviewer)
            print(
                json.dumps(
                    {
                        "repo": args.repo,
                        "run_id": args.run_id,
                        "run_dir": str(run_dir),
                        "stage": args.stage,
                        "approved": True,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        result = run_pipeline_from_convention(
            repo_path=Path(args.repo),
            run_id=args.run_id,
            resume_from=args.resume_from,
            stop_after=args.stop_after,
            target_env=args.target_env,
        )
        payload: Dict[str, str] = {
            "run_id": result.run_id,
            "run_dir": str(result.run_dir),
            "stage": result.stage,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except ConventionError as exc:
        message = str(exc)
        if args.command == "run":
            message += ". Please run 'doc-executor init --repo <repo>' first."
        print(message, file=sys.stderr)
        return 1
