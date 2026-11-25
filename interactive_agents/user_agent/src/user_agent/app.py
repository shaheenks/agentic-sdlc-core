"""The Agent Runtime entry point (`entrypoint_module=user_agent.app`, `entrypoint_object=app`)."""

from user_agent.runtime import create_app

app = create_app()
