"""Call `whoami` on an MCP server with a bearer token (manual Stage 2 check).

Usage:
  uv run python scripts/mcp_whoami.py --token "$(az account get-access-token \
      --scope api://<ENTRA_API_CLIENT_ID>/access_as_user --query accessToken -o tsv)"
  Public endpoint (Cloudflare Tunnel): add --url https://mcp-sdlc-dev.shaheenks.co.in/mcp
  GCP stack (CH-0022; compose profile `gcp`: core-mcp-gcp on :8090):
  uv run --env-file .env python scripts/mcp_whoami.py --idp google --url http://127.0.0.1:8090/mcp
  signs you in with Google in the browser (scripts/google_id_token.py); --explain shows the
  groups and rules behind each role.
"""

import argparse
import asyncio
import json

from fastmcp import Client


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="")
    parser.add_argument("--idp", choices=("entra", "google"), default="entra")
    parser.add_argument("--url", default="http://127.0.0.1:8080/mcp")
    parser.add_argument("--explain", action="store_true", help="teams, roles, tools and why")
    args = parser.parse_args()
    if not args.token and args.idp == "google":
        from google_id_token import id_token  # scripts/ (run as a script)

        args.token = id_token()
    if not args.token:
        parser.error("pass --token, or --idp google to sign in")
    async with Client(args.url, auth=args.token) as client:
        result = await client.call_tool("whoami", {"explain": args.explain})
    print(json.dumps(result.data, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
