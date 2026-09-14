class ServiceError(Exception):
    """An expected failure with a message that is safe to show the user."""

    status_code = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class FetchError(ServiceError):
    """A user-supplied URL couldn't be fetched."""


class InvalidImageError(ServiceError):
    """Bytes that aren't a usable image."""


class UpstreamError(ServiceError):
    """An external API (AI, search, storage) failed."""

    status_code = 502


class NotConfiguredError(ServiceError):
    """A feature needs an API key that isn't set."""

    status_code = 503
