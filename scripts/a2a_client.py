"""Ask the SDLC agent over A2A (version-03 P4 C4), as a manual check of the A2A endpoint.

Usage (PowerShell):
  $env:SDLC_TOKEN = az account get-access-token --scope api://<ENTRA_API_CLIENT_ID>/access_as_user `
      --query accessToken -o tsv
  uv run python scripts/a2a_client.py "How is row level security handled?"
  uv run python scripts/a2a_client.py --context <contextId from the last answer> "And for ingest?"
  uv run python scripts/a2a_client.py --card            # the public agent card
  Tunnel: add --url https://app-sdlc-dev.shaheenks.co.in

Prints the answer, the tools the agent used, and the A2UI cards (texts and links) it attached.
The token is read from --token or SDLC_TOKEN and is never printed.
"""

import argparse
import json
import os
import sys
import uuid

import httpx

A2UI_MIME = "application/json+a2ui"


def card_lines(operations: list[dict]) -> list[str]:
    lines = []
    for op in operations:
        update = op.get("updateComponents")
        if not update:
            continue
        lines.append(f"  card {update.get('surfaceId')}:")
        for c in update.get("components", []):
            if c.get("component") == "Text":
                lines.append(f"    {c.get('text')}")
            url = (c.get("action") or {}).get("functionCall", {}).get("args", {}).get("url")
            if url:
                lines.append(f"    link -> {url}")
    return lines


def show(task: dict) -> None:
    agent_parts = [
        p for m in task.get("history", []) if m.get("role") == "agent" for p in m["parts"]
    ]
    tools = [
        p["data"]["name"]
        for p in agent_parts
        if p.get("metadata", {}).get("adk_type") == "function_call"
    ]
    cards = [p["data"] for p in agent_parts if p.get("metadata", {}).get("mimeType") == A2UI_MIME]
    answer = [
        p["text"]
        for p in agent_parts
        if p.get("kind") == "text" and not p.get("metadata", {}).get("adk_thought")
    ]
    status = task.get("status", {})
    if status.get("state") != "completed":
        failure = [p.get("text", "") for p in (status.get("message") or {}).get("parts", [])]
        print(f"status: {status.get('state')} {' '.join(failure)}")
    print("\n".join(answer) or "(no text answer)")
    print(f"\ntools: {', '.join(tools) or 'none'}")
    if cards:
        print("A2UI cards:")
        print("\n".join(card_lines(cards)))
    print(f"\ncontextId: {task.get('contextId')}  (pass --context to continue)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("text", nargs="?", help="what to ask")
    parser.add_argument("--url", default="http://localhost:4180", help="app base URL")
    parser.add_argument("--token", default=os.environ.get("SDLC_TOKEN"))
    parser.add_argument("--context", help="continue this A2A context (conversation)")
    parser.add_argument("--card", action="store_true", help="print the agent card and exit")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    base = args.url.rstrip("/")

    with httpx.Client(timeout=args.timeout, follow_redirects=False) as http:
        if args.card:
            resp = http.get(f"{base}/.well-known/agent-card.json")
            print(resp.status_code)
            print(json.dumps(resp.json(), indent=2) if resp.is_success else resp.text[:500])
            return 0 if resp.is_success else 1
        if not args.text:
            parser.error("say what to ask (or use --card)")
        message = {
            "role": "user",
            "messageId": str(uuid.uuid4()),
            "parts": [{"kind": "text", "text": args.text}],
        }
        if args.context:
            message["contextId"] = args.context
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {"message": message},
        }
        headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
        resp = http.post(f"{base}/a2a", json=body, headers=headers)
    if not resp.is_success:
        print(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return 1
    reply = resp.json()
    if "error" in reply:
        print(f"error: {reply['error'].get('message')}")
        return 1
    show(reply["result"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
