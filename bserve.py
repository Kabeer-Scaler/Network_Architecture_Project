#!/usr/bin/env python3
"""Sequential, persistent-connection BNP/1 static-file server."""
from __future__ import annotations

import argparse
import mimetypes
import socket
import sys
from pathlib import Path

from protocol import (ProtocolError, REQUEST, RESPONSE, encode_frame, make_response,
                      parse_request, read_frame)


def response(status: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> bytes:
    return make_response(status, [("content-type", content_type),
                                  ("content-length", str(len(body))),
                                  ("connection", "keep-alive")], body)


def target_for(root: Path, request_path: str) -> Path:
    if not request_path.startswith("/") or "?" in request_path or "#" in request_path:
        raise ProtocolError("path must be an absolute path without query or fragment")
    pieces = request_path.split("/")[1:]
    if any(piece in ("", ".", "..") for piece in pieces):
        raise ProtocolError("empty, dot, and parent path components are forbidden")
    candidate = (root / Path(*pieces)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ProtocolError("path escapes document root") from exc
    return candidate


def handle_frame(root: Path, frame) -> bytes | None:
    # Unknown types are deliberately ignored after their declared payload was read.
    if frame.frame_type != REQUEST:
        return None
    try:
        path, _headers = parse_request(frame.payload)
        file_path = target_for(root, path)
        if not file_path.is_file():
            return response(404, b"404 Not Found\n")
        body = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        return response(200, body, content_type)
    except ProtocolError as exc:
        return response(400, f"400 Bad Request: {exc}\n".encode())
    except OSError:
        return response(500, b"500 Internal Server Error\n")


def serve_connection(connection: socket.socket, root: Path, verbose: bool) -> None:
    with connection:
        while True:
            try:
                frame = read_frame(connection)
                if frame is None:
                    return
                payload = handle_frame(root, frame)
                if payload is None:
                    if verbose:
                        print(f"skip unknown frame type {frame.frame_type} ({len(frame.payload)} bytes)", file=sys.stderr)
                    continue
                connection.sendall(encode_frame(RESPONSE, frame.stream_id, payload))
            except ProtocolError as exc:
                # A malformed header cannot safely be resynchronised; closing is required.
                if verbose:
                    print(f"protocol error; closing connection: {exc}", file=sys.stderr)
                return
            except OSError as exc:
                if verbose:
                    print(f"socket error: {exc}", file=sys.stderr)
                return


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve BNP/1 static files")
    parser.add_argument("root", type=Path)
    parser.add_argument("port", type=int)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir() or not 1 <= args.port <= 65535:
        parser.error("root must be a directory and port must be 1..65535")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("", args.port))
        listener.listen()
        print(f"bserve: BNP/1 serving {root} on port {args.port}", file=sys.stderr)
        while True:
            connection, address = listener.accept()
            if args.verbose:
                print(f"accepted {address[0]}:{address[1]}", file=sys.stderr)
            serve_connection(connection, root, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
