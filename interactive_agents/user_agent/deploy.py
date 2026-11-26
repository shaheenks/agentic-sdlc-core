"""Deploy user_agent to Agent Runtime (DEC-0004, DEC-0010).

    uv run python interactive_agents/user_agent/deploy.py --env dev [--dry-run]

The engine `sdlc-user-agent-<env>` runs as the interactive agents' service account, which user_agent_mcp knows as the
`user_agent` caller (identity.callers), and calls user_agent_mcp's URL with that account's ID token. Project, service
account and user_agent_mcp's URL come from `terraform output` in infra/gcp unless given. Staging and deployment:
tools/agent_runtime_deploy.py.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from agent_runtime_deploy import Target, deploy, require_clean, terraform_output  # noqa: E402

REGION = "europe-west3"
TARGET = Target(
    package="user_agent",
    component=Path(__file__).resolve().parent,
    uv_package="sdlc-user-agent",
    operations=[
        "async_create_session",
        "async_get_session",
        "async_list_sessions",
        "async_delete_session",
        "async_stream_query",
    ],
    description="user_agent: knowledge search and brainstorming for the signed-in user",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", default="dev")
    parser.add_argument("--region", default=REGION)
    parser.add_argument("--project", default="", help="default: terraform output project_id")
    parser.add_argument(
        "--service-account", default="", help="default: terraform output interactive_agents_service_account"
    )
    parser.add_argument(
        "--mcp-url", default="", help="user_agent_mcp's URL; default: terraform output user_agent_mcp_url"
    )
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--review-model", default="gemini-3.5-flash", help="The reviewers' model")
    parser.add_argument("--model-location", default="eu", help="Vertex AI location of the model (NFR-HOST-005)")
    parser.add_argument("--allow-dirty", action="store_true", help="deploy uncommitted code (tests only)")
    parser.add_argument("--dry-run", action="store_true", help="stage and print; deploy nothing")
    args = parser.parse_args(argv)

    commit = require_clean(args.allow_dirty)
    project = args.project or terraform_output("project_id")
    account = args.service_account or terraform_output("interactive_agents_service_account")
    mcp_url = (args.mcp_url or terraform_output("user_agent_mcp_url")).rstrip("/")
    if not (project and account and mcp_url):
        sys.exit("need --project, --service-account and --mcp-url (or the Terraform outputs)")
    env = {
        "SDLC_MCP_URL": f"{mcp_url}/mcp",
        "SDLC_MCP_AUDIENCE": mcp_url,  # user_agent_mcp's PUBLIC_URL
        "SDLC_CALLER_AUTH": "id_token",
        "SDLC_MCP_TIMEOUT": "30",  # a scaled-to-zero user_agent_mcp needs a few seconds
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
        print(f"sdlc_ui's SDLC_AGENT_URL: https://{args.region}-aiplatform.googleapis.com/v1/{engine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
