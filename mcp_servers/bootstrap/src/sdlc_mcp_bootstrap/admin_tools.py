"""Admin tools for the config/policy layer. Who may call them is decided by config (the admin
role's "*" grant); they read only the request's config snapshot, never secrets.
"""

from sdlc_config import ConfigStore, PolicyCache

from sdlc_mcp_bootstrap.identity import request_identity


def make_admin_tools(store: ConfigStore, cache: PolicyCache) -> list:
    async def config_info() -> dict:
        """Active config version, environment, load time and last reload error."""
        snapshot = (await request_identity()).snapshot
        return {
            "config_version": snapshot.version,
            "env": snapshot.env,
            "loaded_at": snapshot.loaded_at.isoformat(),
            "last_reload_error": store.last_error,
            "counts": {
                "roles": len(snapshot.roles),
                "teams": len(snapshot.teams),
                "tools": len(snapshot.tools),
                "groups": len(snapshot.groups.alias_by_id),
            },
        }

    async def config_explain(groups: list[str], app_roles: list[str] | None = None) -> dict:
        """Explain the effective permissions of a persona: group aliases and/or app roles."""
        snapshot = (await request_identity()).snapshot
        known = set(snapshot.groups.alias_by_id.values())
        policy = cache.get(snapshot, [g for g in groups if g in known], app_roles or [])
        view = policy.explain()
        view["unknown_groups"] = sorted(set(groups) - known)
        return view

    return [config_info, config_explain]
