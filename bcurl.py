#!/usr/bin/env python3
"""BNP/1 command-line client."""
from __future__ import annotations

import argparse
import socket
import sys

from protocol import (ProtocolError, REQUEST, RESPONSE, encode_frame, hex_lines,
                      make_request, parse_response, read_frame)


def parse_url(value: str) -> tuple[str, int, str]:
    if "/" not in value:
        raise ValueError("URL must be host:port/path")
    authority, suffix = value.split("/", 1)
    if authority.count(":") != 1:
        raise ValueError("use host:port/path (IPv6 is intentionally not supported)")
    host, raw_port = authority.rsplit(":", 1)
    if not host:
        raise ValueError("empty host")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("port is not an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("port must be 1..65535")
    return host, port, "/" + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch one BNP/1 resource")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("url", help="host:port/absolute-path")
    args = parser.parse_args()
    try:
        host, port, path = parse_url(args.url)
        request_payload = make_request(path, [("host", f"{host}:{port}"),
                                              ("user-agent", "bcurl/1")])
        outbound = encode_frame(REQUEST, 1, request_payload)
        with socket.create_connection((host, port), timeout=5) as connection:
            connection.sendall(outbound)
            if args.verbose:
                print(hex_lines("request frame", outbound), file=sys.stderr)
            while True:
                frame = read_frame(connection)
                if frame is None:
                    raise ProtocolError("server closed before a response")
                if frame.frame_type != RESPONSE:
                    if args.verbose:
                        print(f"skipped unknown frame type {frame.frame_type}", file=sys.stderr)
                    continue
                if frame.stream_id != 1:
                    raise ProtocolError("response stream ID does not match request")
                status, headers, body = parse_response(frame.payload)
                if args.verbose:
                    print(hex_lines("response frame", encode_frame(frame.frame_type, frame.stream_id, frame.payload, frame.flags)), file=sys.stderr)
                    print(f"status: {status}", file=sys.stderr)
                    for name, value in headers:
                        print(f"{name}: {value}", file=sys.stderr)
                sys.stdout.buffer.write(body)
                return 0 if status < 400 else (4 if status < 500 else 5)
    except (OSError, ValueError, ProtocolError) as exc:
        print(f"bcurl: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
