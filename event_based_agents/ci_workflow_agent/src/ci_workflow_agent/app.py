"""The Agent Runtime entry point (`entrypoint_module=ci_workflow_agent.app`, `entrypoint_object=app`)."""

from ci_workflow_agent.runtime import create_app

app = create_app()
