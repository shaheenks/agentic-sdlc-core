from knowledge_ingest.__main__ import main

from knowledge_ingest import NAME


def test_skeleton_runs():
    assert NAME == "knowledge_ingest"
    assert main() == 0
