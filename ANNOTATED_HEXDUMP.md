# Annotated BNP/1 exchange

This is the exact exchange produced by `bcurl -v localhost:9000/index.html` against `bserve ./www 9000`. Offsets are hexadecimal, and the ASCII column is only a reading aid; the bytes are authoritative. The response body is 96 bytes because the sample file ends in a newline.

## Request — 54 bytes

```text
0000  42 4e 01 01 00 00 00 01 00 00 00 2a 01 00 0b 2f  |BN.........*.../|
0010  69 6e 64 65 78 2e 68 74 6d 6c 02 01 00 0e 6c 6f  |index.html....lo|
0020  63 61 6c 68 6f 73 74 3a 39 30 30 30 08 00 07 62  |calhost:9000...b|
0030  63 75 72 6c 2f 31                                |curl/1|
```

- `00–01` `42 4e`: magic `BN`; `02` is version 1; `03` is request type 1.
- `04` flags 0 and `05` reserved 0. `06–07` stream ID 1. `08–0b` is payload length `0x2a` = 42.
- `0c` method 1 (GET); `0d–0e` path length 11; `0f–19` UTF-8 `/index.html`.
- `1a` says there are two headers. `1b` header ID 1 = `host`; `1c–1d` says its value is 14 bytes; `1e–2b` is `localhost:9000`.
- `2c` header ID 8 = `user-agent`; `2d–2e` says its value is 7 bytes; `2f–35` is `bcurl/1`.

## Response — 145 bytes

```text
0000  42 4e 01 02 00 00 00 01 00 00 00 85 00 c8 03 02  |BN..............|
0010  00 09 74 65 78 74 2f 68 74 6d 6c 03 00 02 39 36  |..text/html...96|
0020  04 00 0a 6b 65 65 70 2d 61 6c 69 76 65 00 00 00  |...keep-alive...|
0030  60 3c 21 64 6f 63 74 79 70 65 20 68 74 6d 6c 3e  |`<!doctype html>|
0040  0a 3c 68 74 6d 6c 3e 3c 62 6f 64 79 3e 3c 68 31  |.<html><body><h1|
0050  3e 42 4e 50 2f 31 20 64 65 6d 6f 3c 2f 68 31 3e  |>BNP/1 demo</h1>|
0060  3c 70 3e 62 69 6e 61 72 79 20 70 72 6f 74 6f 63  |<p>binary protoc|
0070  6f 6c 20 69 73 20 77 6f 72 6b 69 6e 67 2e 3c 2f  |ol is working.</|
0080  70 3e 3c 2f 62 6f 64 79 3e 3c 2f 68 74 6d 6c 3e  |p></body></html>|
0090  0a                                               |.|
```

- `00–01` magic, `02` version 1, `03` response type 2; `04–05` are zero; `06–07` echoes stream 1; `08–0b` payload length `0x85` = 133.
- `0c–0d` status `0x00c8` = 200. `0e` says three headers follow.
- `0f` header ID 2 (`content-type`), `10–11` value length 9, and `12–1a` is `text/html`.
- `1b` header ID 3 (`content-length`), `1c–1d` value length 2, and `1e–1f` is ASCII `96`.
- `20` header ID 4 (`connection`), `21–22` value length 10, and `23–2c` is `keep-alive`.
- `2d–30` body length `0x00000060` = 96. `31–90` are the exact 96 HTML bytes written to standard output.
