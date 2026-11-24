from user_agent import NAME
from user_agent.__main__ import main


def test_skeleton_runs():
    assert NAME == "user_agent"
    assert main() == 0
