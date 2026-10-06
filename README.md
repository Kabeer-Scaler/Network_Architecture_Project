# Network Architecture Project — BNP/1

This submission contains the independently runnable server and client, the protocol specification, an annotated complete request/response trace, and automated tests.

## Run

In PowerShell, use two terminals from this folder:

```powershell
./bserve.cmd ./www 9000
./bcurl.cmd -v localhost:9000/index.html
```

The body is written to standard output; `-v` sends decoded fields and a hexdump of each frame to standard error. The programs use Python 3 and only its standard library. On systems with Python directly available, `python bserve.py ./www 9000` and `python bcurl.py -v localhost:9000/index.html` are equivalent.

## Deliverables

- [SPEC.md](SPEC.md) and `output/pdf/BNP1_Specification.pdf` — editable and ready-to-submit two-page specification versions.
- `bserve.py`, `bcurl.py`, and `protocol.py` — implementation (plus Windows `.cmd` launchers).
- [ANNOTATED_HEXDUMP.md](ANNOTATED_HEXDUMP.md) — one complete exchanged request and response, byte by byte.
- `tests/test_bnp.py` — framing, binary body, 404, malformed request, extension skip, path safety, and client/server integration tests.

Run the verification suite with:

```powershell
python -m unittest -v tests/test_bnp.py
```
