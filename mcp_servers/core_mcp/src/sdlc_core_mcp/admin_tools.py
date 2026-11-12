"""Admin tools for the config/policy layer. Who may call them is decided by config (the admin
role's "*" grant); they read only the request's config snapshot, never secrets.
"""

from sdlc_config import ConfigStore, PolicyCache

from sdlc_core_mcp.identity import request_identity


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
                "app_roles": len(snapshot.app_role_values),
                "users": len(snapshot.users.alias_by_oid),
                "pending_users": len(snapshot.users.pending),
            },
        }

    async def config_explain(
        app_roles: list[str] | None = None,
        user: str | None = None,
    ) -> dict:
        """Explain the effective permissions of a persona: Entra app roles and/or a users.yaml
        user alias."""
        snapshot = (await request_identity()).snapshot
        app_roles = app_roles or []
        known_user = user if user in snapshot.users.email_by_alias else None
        policy = cache.get(snapshot, app_roles, known_user)
        view = policy.explain()
        view["unknown_app_roles"] = sorted(set(app_roles) - snapshot.app_role_values)
        if user and known_user is None:
            view["unknown_user"] = user
        return view

    return [config_info, config_explain]
