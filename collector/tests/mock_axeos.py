#!/usr/bin/env python3
"""Minimal stand-in for the AxeOS HTTP API, serving a recorded /api/system/info response."""

from __future__ import annotations

import argparse
import http.server
import pathlib
import threading

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "system_info.json"


class Handler(http.server.BaseHTTPRequestHandler):
    body = FIXTURE.read_bytes()

    def do_GET(self):  # noqa: N802 (http.server naming)
        if self.path != "/api/system/info":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *_):
        pass


def serve(port: int = 0) -> tuple[http.server.HTTPServer, threading.Thread]:
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    http.server.HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
