"""A refusal or failure a tool reports to its caller, with a stable code for the audit record."""

HTTP_STATUS = {"not_found": 404, "not_allowed": 403, "rate_limited": 429, "unavailable": 503}


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    @property
    def http_status(self) -> int:
        return HTTP_STATUS.get(self.code, 400)
