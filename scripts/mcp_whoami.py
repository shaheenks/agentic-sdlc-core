"""Call `whoami` on an MCP server with a bearer token (manual Stage 2 check).

Usage:
  uv run python scripts/mcp_whoami.py --token "$(az account get-access-token \
      --scope api://<ENTRA_API_CLIENT_ID>/access_as_user --query accessToken -o tsv)"
"""

import argparse
import asyncio
import json

from fastmcp import Client


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8080/mcp")
    args = parser.parse_args()
    async with Client(args.url, auth=args.token) as client:
        result = await client.call_tool("whoami", {})
    print(json.dumps(result.data, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
