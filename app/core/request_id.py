import re
import uuid

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def resolve_request_id(client_value: str | None) -> str:
    """Return a safe request id, generating one unless the client value is well-formed."""
    if client_value and _REQUEST_ID_PATTERN.match(client_value):
        return client_value
    return str(uuid.uuid4())
