"""Ask the user agent on Agent Runtime a question as a signed-in user (manual check, CH-0014).

Usage (a test user's token, not the admin's; the token is never printed):
  uv run python scripts/agent_runtime_query.py --token "$(az account get-access-token \\
      --scope api://<ENTRA_API_CLIENT_ID>/access_as_user --query accessToken -o tsv)" \\
      "Call whoami and tell me my teams and roles."
  --session <id>   continue a conversation; --threads  only list your conversations
  GCP stack (CH-0022, the engine's default): `uv run --env-file .env python
  scripts/agent_runtime_query.py --idp google` signs you in with Google in the browser
  (scripts/google_id_token.py) instead of --token.

It calls the engine's `stream_query` and prints every event with the seconds since the call
started, so you can see whether the answer streams (events spread over time) or arrives at once.
Tool calls and their results are shown by name only; text is shown as it arrives. Then it lists
your conversations with `list_threads`. The Google caller is your gcloud ADC account (it needs
permission to query the engine); who the user is comes only from the user token.
"""

import argparse
import asyncio
import sys
import time

PROJECT = "sdlc-demo-env01"
REGION = "asia-southeast1"
ENGINE = "sdlc-user-agent-dev"


def find_engine(client, display_name: str):
    for engine in client.agent_engines.list():
        if engine.api_resource.display_name == display_name:
            return client.agent_engines.get(name=engine.api_resource.name)
    sys.exit(f"engine {display_name} not found in {REGION} (deploy it first)")


def describe(event: dict) -> str:
    """One line per event: text as it arrived, tool calls and results by name only."""
    if "session" in event and len(event) == 1:
        return f"session {event['session']}"
    parts = (event.get("content") or {}).get("parts") or []
    out = []
    for part in parts:
        if part.get("text"):
            out.append(part["text"].replace("\n", " ")[:200])
        elif part.get("function_call") or part.get("functionCall"):
            call = part.get("function_call") or part.get("functionCall")
            out.append(f"[tool call {call.get('name')}]")
        elif part.get("function_response") or part.get("functionResponse"):
            resp = part.get("function_response") or part.get("functionResponse")
            out.append(f"[tool result {resp.get('name')}]")
    if isinstance(event.get("error"), dict):  # a refusal from the runtime app (CH-0019)
        return f"refused: {event['error'].get('code')}: {event['error'].get('message')}"
    if event.get("error_code") or event.get("errorCode"):
        out.append(f"[error {event.get('error_code') or event.get('errorCode')}]")
    return f"{event.get('author', '?')}: " + (" ".join(out) or "(no content)")


async def run(args) -> int:
    import vertexai

    client = vertexai.Client(project=args.project, location=args.region)
    engine = find_engine(client, args.engine)
    if not args.threads:
        started = time.monotonic()
        kwargs = {"message": args.message, "user_token": args.token}
        if args.session:
            kwargs["session_id"] = args.session
        count = 0
        async for event in engine.stream_query(**kwargs):
            count += 1
            print(f"{time.monotonic() - started:6.1f}s  {describe(event)}", flush=True)
        print(f"{count} events in {time.monotonic() - started:.1f}s")
    threads = await engine.list_threads(user_token=args.token)
    if isinstance(threads, dict):
        print(describe(threads))
        return 1
    print("your conversations:")
    for thread in threads or []:
        print(f"  {thread['updatedAt']}  {thread['threadId']}  {thread['title']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--token", default="", help="the user's token (Entra access or Google ID)")
    parser.add_argument(
        "--idp", choices=("entra", "google"), default="entra", help="google: sign in in the browser"
    )
    parser.add_argument("message", nargs="?", default="Call whoami and tell me my teams and roles.")
    parser.add_argument("--session", default="")
    parser.add_argument("--threads", action="store_true", help="only list your conversations")
    parser.add_argument("--engine", default=ENGINE)
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--region", default=REGION)
    args = parser.parse_args()
    if not args.token and args.idp == "google":
        from google_id_token import id_token  # scripts/ (run as a script)

        args.token = id_token()
    if not args.token:
        parser.error("pass --token, or --idp google to sign in")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
