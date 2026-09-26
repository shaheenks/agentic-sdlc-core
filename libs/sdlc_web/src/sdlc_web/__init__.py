"""Serve ADK agents to signed-in Entra users. See libs/sdlc_web/README.md."""

from sdlc_web.middleware import EntraUserBindingMiddleware

__all__ = ["EntraUserBindingMiddleware"]
