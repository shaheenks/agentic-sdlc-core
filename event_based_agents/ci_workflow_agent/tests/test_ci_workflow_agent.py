from ci_workflow_agent import NAME
from ci_workflow_agent.__main__ import main


def test_skeleton_runs():
    assert NAME == "ci_workflow_agent"
    assert main() == 0
