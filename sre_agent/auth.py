import contextvars

import google.auth
from google.oauth2.credentials import Credentials

_credentials_context: contextvars.ContextVar[Credentials | None] = (
    contextvars.ContextVar("credentials_context", default=None)
)


def set_current_credentials(creds: Credentials) -> None:
    """Sets the credentials for the current context."""
    _credentials_context.set(creds)


def get_current_credentials() -> tuple[google.auth.credentials.Credentials, str | None]:
    """Gets the credentials for the current context, falling back to default.

    Returns:
        A tuple of (credentials, project_id).
    """
    creds = _credentials_context.get()
    if creds:
        return creds, None

    # Fallback to default if no user credentials (e.g. running locally or background tasks)
    return google.auth.default()


def get_current_credentials_or_none() -> Credentials | None:
    """Gets the explicitly set credentials or None."""
    return _credentials_context.get()
