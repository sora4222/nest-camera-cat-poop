"""The real CertificateSource: fetch Alexa's signing chain from Amazon's S3 with httpx."""

import httpx

MAX_BYTES = 64 * 1024


class HttpCertificates:
    """Fetches a PEM chain over HTTPS; follows no redirects."""

    def __init__(self, http: httpx.Client | None = None) -> None:
        """Use `http` (default: a client with a 5 s timeout, Alexa waits only ~8 s)."""
        self._http = http or httpx.Client(timeout=5, follow_redirects=False)

    def fetch(self, url: str) -> bytes:
        """The body at `url`; OSError if it cannot be had or is too big."""
        try:
            with self._http.stream("GET", url, follow_redirects=False) as response:
                if response.status_code != 200:
                    raise OSError(f"{response.status_code} for {url}")
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise OSError(f"more than {MAX_BYTES} bytes at {url}")
        except httpx.HTTPError as error:
            raise OSError(f"{type(error).__name__} for {url}") from None
        return body
