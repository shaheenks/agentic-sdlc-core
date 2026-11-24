from operations_agent import NAME
from operations_agent.__main__ import main


def test_skeleton_runs():
    assert NAME == "operations_agent"
    assert main() == 0
