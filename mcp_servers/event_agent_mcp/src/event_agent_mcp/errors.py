"""A refusal or failure a tool reports to its caller, with a stable code for the audit record."""


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
