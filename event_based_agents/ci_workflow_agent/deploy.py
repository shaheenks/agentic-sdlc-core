"""Deploy ci_workflow_agent to the event agents' Agent Runtime engine (DEC-0007, DEC-0015).

    uv run python event_based_agents/ci_workflow_agent/deploy.py --env dev [--dry-run]

The engine `sdlc-ci-workflow-agent-<env>` runs as the event agents' service account (the system identity), which
event_agent_mcp knows as the `event_agents` caller (identity.callers), and calls event_agent_mcp's URL with that
account's ID token. Project, service account and event_agent_mcp's URL come from `terraform output` in infra/gcp
unless given. Put the printed resource name in `event_agent_engine` of the Terraform variables, so the event gateway
starts runs on it. Staging and deployment: tools/agent_runtime_deploy.py.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from agent_runtime_deploy import Target, deploy, require_clean, terraform_output  # noqa: E402

REGION = "europe-west3"
TARGET = Target(
    package="ci_workflow_agent",
    component=Path(__file__).resolve().parent,
    uv_package="sdlc-ci-workflow-agent",
    operations=["async_create_session", "async_get_session", "async_stream_query"],
    description="ci_workflow_agent: plans and implements approved designs, one run per event",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", default="dev")
    parser.add_argument("--region", default=REGION)
    parser.add_argument("--project", default="", help="default: terraform output project_id")
    parser.add_argument("--service-account", default="", help="default: terraform output event_agents_service_account")
    parser.add_argument(
        "--mcp-url", default="", help="event_agent_mcp's URL; default: terraform output event_agent_mcp_url"
    )
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--review-model", default="gemini-3.5-flash")
    parser.add_argument("--model-location", default="eu", help="Vertex AI location of the model (NFR-HOST-005)")
    parser.add_argument("--allow-dirty", action="store_true", help="deploy uncommitted code (tests only)")
    parser.add_argument("--dry-run", action="store_true", help="stage and print; deploy nothing")
    args = parser.parse_args(argv)

    commit = require_clean(args.allow_dirty)
    project = args.project or terraform_output("project_id")
    account = args.service_account or terraform_output("event_agents_service_account")
    mcp_url = (args.mcp_url or terraform_output("event_agent_mcp_url")).rstrip("/")
    if not (project and account and mcp_url):
        sys.exit("need --project, --service-account and --mcp-url (or the Terraform outputs)")
    env = {
        "SDLC_MCP_URL": f"{mcp_url}/mcp",
        "SDLC_MCP_AUDIENCE": mcp_url,  # event_agent_mcp's PUBLIC_URL
        "SDLC_CALLER_AUTH": "id_token",
        "SDLC_MCP_TIMEOUT": "1300",  # workspace_run waits for the Code Workspace job (up to 1200 s)
        "SDLC_AGENT_MODEL": args.model,
        "SDLC_REVIEW_MODEL": args.review_model,
        "SDLC_MODEL_LOCATION": args.model_location,
    }
    engine = deploy(
        TARGET,
        env_name=args.env,
        region=args.region,
        project=project,
        account=account,
        env_vars=env,
        commit=commit,
        dry_run=args.dry_run,
    )
    if engine:
        print(f'Terraform: event_agent_engine = "{engine}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
