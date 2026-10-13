"""Serve a FastAPI app with uvicorn on a background thread.

It listens on this machine only by default (`127.0.0.1`); the tunnel (Cloudflare or
Tailscale) brings `/alexa` from the internet to it.
"""

import socket
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI


@contextmanager
def serving(app: FastAPI, host: str, port: int) -> Generator[tuple[str, int]]:
    """Serve `app` on `host:port` inside the `with`; yields the address it listens on.

    Port 0 picks a free one. Raises `OSError` when the address cannot be used.
    """
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.create_server((host, port), family=family)
    config = uvicorn.Config(
        app, log_config=None, access_log=False, server_header=False, timeout_keep_alive=10
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [sock]}, name="http-server", daemon=True
    )
    thread.start()
    try:
        while not server.started and thread.is_alive():
            time.sleep(0.01)
        yield sock.getsockname()[:2]
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
