"""Errors from the optional AI path. They never fail an investigation."""


class AIDisabledError(Exception):
    """Raised when a caller asks for analysis while AI is turned off."""


class AIProviderError(Exception):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(status)
