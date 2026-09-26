class ConfigError(Exception):
    """Config is missing, malformed, or references something that does not exist.

    Carries every problem found, so one validation run reports all of them.
    """

    def __init__(self, problems: list[str]):
        self.problems = list(dict.fromkeys(problems))  # same var in several fields
        super().__init__("invalid config:\n  - " + "\n  - ".join(self.problems))
