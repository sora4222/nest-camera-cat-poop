"""Send each request to the endpoint for its path; 404 for any other path."""

from collections.abc import Mapping

from catpoop.alexa_skill.endpoint import EndpointResponse
from catpoop.alexa_skill.server import Endpoint


class Routes:
    """Several endpoints behind one server."""

    def __init__(self, by_path: Mapping[str, Endpoint]) -> None:
        """Serve `by_path[path]` for each path."""
        self._by_path = dict(by_path)

    def handle(
        self, method: str, path: str, headers: dict[str, str], body: bytes
    ) -> EndpointResponse:
        """The answer of the endpoint for `path`."""
        endpoint = self._by_path.get(path)
        if endpoint is None:
            return EndpointResponse(404, b"not found")
        return endpoint.handle(method, path, headers, body)
