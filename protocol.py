"""BNP/1: shared wire-format helpers for bserve and bcurl.

Everything on the wire is bytes.  Integer values are unsigned big-endian.
"""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from typing import BinaryIO

MAGIC = b"BN"
VERSION = 1
HEADER = struct.Struct("!2sBBBBHI")  # magic, ver, type, flags, reserved, stream, length
MAX_PAYLOAD = 8 * 1024 * 1024

REQUEST = 1
RESPONSE = 2

# The numbers are deliberately stable protocol values, not local dictionary indexes.
KNOWN_HEADERS = {
    1: "host",
    2: "content-type",
    3: "content-length",
    4: "connection",
    5: "date",
    6: "server",
    7: "accept",
    8: "user-agent",
    9: "cache-control",
    10: "last-modified",
}
HEADER_IDS = {value: key for key, value in KNOWN_HEADERS.items()}


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Frame:
    frame_type: int
    flags: int
    stream_id: int
    payload: bytes


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """Receive exactly size bytes, treating an EOF in the middle as malformed."""
    chunks = bytearray()
    while len(chunks) < size:
        piece = sock.recv(size - len(chunks))
        if not piece:
            if not chunks:
                return b""
            raise ProtocolError("unexpected EOF inside a frame")
        chunks.extend(piece)
    return bytes(chunks)


def read_frame(sock: socket.socket) -> Frame | None:
    raw = recv_exact(sock, HEADER.size)
    if not raw:
        return None
    magic, version, frame_type, flags, reserved, stream_id, length = HEADER.unpack(raw)
    if magic != MAGIC:
        raise ProtocolError("bad magic")
    if version != VERSION:
        raise ProtocolError("unsupported version")
    if reserved != 0:
        raise ProtocolError("reserved header byte is non-zero")
    if length > MAX_PAYLOAD:
        raise ProtocolError("payload exceeds negotiated implementation limit")
    payload = recv_exact(sock, length)
    if len(payload) != length:
        raise ProtocolError("unexpected EOF before payload")
    return Frame(frame_type, flags, stream_id, payload)


def encode_frame(frame_type: int, stream_id: int, payload: bytes, flags: int = 0) -> bytes:
    if not (0 <= frame_type <= 255 and 0 <= flags <= 255 and 0 <= stream_id <= 65535):
        raise ProtocolError("header field outside its wire range")
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError("payload too large")
    return HEADER.pack(MAGIC, VERSION, frame_type, flags, 0, stream_id, len(payload)) + payload


def _take(payload: bytes, cursor: int, count: int) -> tuple[bytes, int]:
    if count < 0 or cursor + count > len(payload):
        raise ProtocolError("truncated payload field")
    return payload[cursor:cursor + count], cursor + count


def pack_headers(headers: list[tuple[str, str]]) -> bytes:
    if len(headers) > 255:
        raise ProtocolError("too many headers")
    output = bytearray([len(headers)])
    for name, value in headers:
        try:
            value_bytes = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ProtocolError("header value is not UTF-8") from exc
        name = name.lower()
        ident = HEADER_IDS.get(name, 0)
        output.append(ident)
        if ident == 0:
            name_bytes = name.encode("ascii")
            if not name_bytes or len(name_bytes) > 255:
                raise ProtocolError("literal header name is empty or too long")
            output.append(len(name_bytes))
            output.extend(name_bytes)
        if len(value_bytes) > 65535:
            raise ProtocolError("header value too long")
        output.extend(struct.pack("!H", len(value_bytes)))
        output.extend(value_bytes)
    return bytes(output)


def unpack_headers(payload: bytes, cursor: int) -> tuple[list[tuple[str, str]], int]:
    raw_count, cursor = _take(payload, cursor, 1)
    result: list[tuple[str, str]] = []
    for _ in range(raw_count[0]):
        raw_id, cursor = _take(payload, cursor, 1)
        ident = raw_id[0]
        if ident in KNOWN_HEADERS:
            name = KNOWN_HEADERS[ident]
        elif ident == 0:
            raw_len, cursor = _take(payload, cursor, 1)
            raw_name, cursor = _take(payload, cursor, raw_len[0])
            try:
                name = raw_name.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ProtocolError("literal header name is not ASCII") from exc
            if not name:
                raise ProtocolError("empty literal header name")
        else:
            raise ProtocolError("unknown indexed header name")
        raw_len, cursor = _take(payload, cursor, 2)
        raw_value, cursor = _take(payload, cursor, struct.unpack("!H", raw_len)[0])
        try:
            value = raw_value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("header value is not UTF-8") from exc
        result.append((name, value))
    return result, cursor


def make_request(path: str, headers: list[tuple[str, str]]) -> bytes:
    path_bytes = path.encode("utf-8")
    if not path_bytes or len(path_bytes) > 65535:
        raise ProtocolError("path is empty or too long")
    return b"\x01" + struct.pack("!H", len(path_bytes)) + path_bytes + pack_headers(headers)


def parse_request(payload: bytes) -> tuple[str, list[tuple[str, str]]]:
    method, cursor = _take(payload, 0, 1)
    if method != b"\x01":
        raise ProtocolError("only GET (method 1) is supported")
    raw_len, cursor = _take(payload, cursor, 2)
    path_bytes, cursor = _take(payload, cursor, struct.unpack("!H", raw_len)[0])
    try:
        path = path_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("path is not UTF-8") from exc
    headers, cursor = unpack_headers(payload, cursor)
    if cursor != len(payload):
        raise ProtocolError("trailing bytes in request")
    return path, headers


def make_response(status: int, headers: list[tuple[str, str]], body: bytes) -> bytes:
    if not 100 <= status <= 599:
        raise ProtocolError("invalid status")
    return struct.pack("!H", status) + pack_headers(headers) + struct.pack("!I", len(body)) + body


def parse_response(payload: bytes) -> tuple[int, list[tuple[str, str]], bytes]:
    raw_status, cursor = _take(payload, 0, 2)
    status = struct.unpack("!H", raw_status)[0]
    if not 100 <= status <= 599:
        raise ProtocolError("invalid status")
    headers, cursor = unpack_headers(payload, cursor)
    raw_len, cursor = _take(payload, cursor, 4)
    body, cursor = _take(payload, cursor, struct.unpack("!I", raw_len)[0])
    if cursor != len(payload):
        raise ProtocolError("trailing bytes in response")
    return status, headers, body


def hex_lines(label: str, data: bytes) -> str:
    lines = [f"{label}: {len(data)} bytes"]
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset + 16]
        hexed = " ".join(f"{byte:02x}" for byte in chunk).ljust(47)
        ascii_side = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append(f"  {offset:04x}  {hexed}  |{ascii_side}|")
    return "\n".join(lines)
