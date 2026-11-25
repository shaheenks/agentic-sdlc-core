"""Adapters for downstream systems (Connectors component; FR-CONN-001): Jira, GitHub and Bitbucket, each in its
cloud and Data Center edition. Callers pass a connection's credential; adapters keep nothing and never put the
credential, a request or a response body in an error."""

from sdlc_connectors.base import ConnectorError, Credential
from sdlc_connectors.jira import Issue, Jira, adf_to_text, text_to_adf
from sdlc_connectors.repos import Change, FileChange, OpenPullRequest, PullRequest, Repository, repository

__all__ = [
    "Change",
    "ConnectorError",
    "Credential",
    "FileChange",
    "Issue",
    "Jira",
    "OpenPullRequest",
    "PullRequest",
    "Repository",
    "adf_to_text",
    "repository",
    "text_to_adf",
]
