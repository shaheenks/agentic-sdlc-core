from code_workspace.__main__ import main

from code_workspace import NAME


def test_skeleton_runs():
    assert NAME == "code_workspace"
    assert main() == 0
