# BNP/1 — Binary Network Protocol, version 1

## Purpose and connection model

BNP/1 is a small binary protocol for fetching a static file over one TCP connection. A server is started as `bserve ROOT PORT`; a client is run as `bcurl [-v] HOST:PORT/PATH`. One connection may carry any number of requests and responses in order. The client opens exactly one TCP connection for its one requested URL; it does not follow redirects or make a second connection. The server keeps a clean connection open until the peer closes it or a framing-level error makes resynchronisation unsafe.

All multibyte integers are unsigned, network byte order (big-endian). Text fields are UTF-8 unless noted. BNP/1 has an implementation payload limit of 8,388,608 bytes. The protocol carries arbitrary binary bodies without text conversion.

## Frame layer

Every message is a fixed 12-byte header followed by exactly `payload_length` bytes:

| Offset | Width | Field | Meaning |
|---:|---:|---|---|
| 0 | 2 | magic | ASCII `BN` (`42 4e`) |
| 2 | 1 | version | `1` for this specification |
| 3 | 1 | type | `1` request; `2` response; other values are extensions |
| 4 | 1 | flags | zero in version 1; receivers ignore it |
| 5 | 1 | reserved | MUST be zero (otherwise malformed) |
| 6 | 2 | stream ID | client-chosen nonzero correlation value |
| 8 | 4 | payload length | following payload length in bytes |

Fixed widths make the receiver know precisely where each frame ends, including an extension it cannot understand. Two magic bytes reject accidental non-BNP traffic early. A one-byte version and type leave room for evolution with negligible overhead. A 16-bit stream ID supports 65,535 outstanding identifiers, even though version 1 uses ordered request/reply exchanges. A 32-bit length supports useful binary files, while the explicit 8 MiB implementation cap prevents unbounded allocation. `flags` and `reserved` deliberately reserve future header space; accepting arbitrary reserved bits would make version changes ambiguous.

**Extension rule (required): a receiver meeting a frame type it does not know MUST read and discard exactly its declared payload length, then continue with the next frame.** It must not guess its fields or close a sound connection merely because its type is unfamiliar.

If magic, version, reserved byte, length limit, or complete payload cannot be read, the frame layer is malformed and the connection is closed because frame boundaries can no longer be trusted. A known request frame whose payload is malformed receives a `400` response on the same stream, and the connection remains usable.

## Header representation

After a request path or response status, headers use this form: `count:u8`, followed by `count` entries. An entry begins with `name_id:u8`. IDs 1–10 stand for these lowercase names: 1 `host`, 2 `content-type`, 3 `content-length`, 4 `connection`, 5 `date`, 6 `server`, 7 `accept`, 8 `user-agent`, 9 `cache-control`, 10 `last-modified`. Each indexed entry continues `value_length:u16, value:utf8`.

For every other name, send `name_id=0, name_length:u8, name:ASCII, value_length:u16, value:UTF-8`. Literal names must be nonempty. Indexing the ten commonly expected names saves repeated name bytes and creates a stable shared vocabulary; length-prefixing all others preserves arbitrary extension headers without a central registry. Unknown nonzero name IDs are malformed in v1, because they are not self-delimiting names.

## Request and response payloads

A request (type 1) is `method:u8, path_length:u16, path:UTF-8, headers`. Method `1` means GET and is the only valid method. `path` must start with `/`, contain no query or fragment, and have no empty, `.` or `..` components. The server resolves it beneath its configured root; a missing regular file is `404`.

A response (type 2) is `status:u16, headers, body_length:u32, body`. `body_length` must consume the rest of the frame. The server sends `content-type`, `content-length`, and `connection: keep-alive` on every response. Status is 200 for a found file, 404 for absent files, 400 for a well-framed but bad request, and 500 for an internal file error. Other response statuses make `bcurl` exit 4 for 4xx or 5 for 5xx; success exits 0. `-v` writes frame hexdumps and decoded metadata to stderr while body bytes go only to stdout.

## Interoperability checklist

An independent implementation need only construct the frame header exactly, use GET method 1, parse lengths before allocating, and follow the unknown-type rule. It must accept TCP segmentation: reads are not message boundaries. It must also reject surplus bytes in known request/response payloads, invalid UTF-8, length overruns, and paths escaping the root.
