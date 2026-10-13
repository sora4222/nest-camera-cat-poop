"""Read a request body, refusing (413) one bigger than a limit before reading it all."""

from fastapi import HTTPException, Request


async def read_body(request: Request, limit: int) -> bytes:
    """The body of `request`, or `HTTPException(413)` when it is over `limit` bytes."""
    try:
        length = int(request.headers.get("content-length") or 0)
    except ValueError:
        length = -1
    if length < 0 or length > limit:
        raise HTTPException(413, "too large")
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise HTTPException(413, "too large")
    return body
