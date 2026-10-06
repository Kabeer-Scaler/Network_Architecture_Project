from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bserve import serve_connection
from protocol import (REQUEST, RESPONSE, encode_frame, make_request, make_response,
                      parse_response, read_frame)


class BNPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.docroot = Path(self.temp.name)
        (self.docroot / "hello.bin").write_bytes(b"\x00binary\xff\n")
        self.client, server = socket.socketpair()
        self.worker = threading.Thread(target=serve_connection, args=(server, self.docroot, False), daemon=True)
        self.worker.start()

    def tearDown(self):
        self.client.close()
        self.worker.join(timeout=1)
        self.temp.cleanup()

    def ask(self, stream_id: int, path: str):
        payload = make_request(path, [("host", "test:1")])
        self.client.sendall(encode_frame(REQUEST, stream_id, payload))
        frame = read_frame(self.client)
        self.assertEqual(frame.frame_type, RESPONSE)
        self.assertEqual(frame.stream_id, stream_id)
        return parse_response(frame.payload)

    def test_binary_body_and_404(self):
        status, headers, body = self.ask(1, "/hello.bin")
        self.assertEqual(status, 200)
        self.assertIn(("content-length", "9"), headers)
        self.assertEqual(body, b"\x00binary\xff\n")
        status, _, body = self.ask(2, "/missing.txt")
        self.assertEqual(status, 404)
        self.assertEqual(body, b"404 Not Found\n")

    def test_bad_request_then_good_request_same_connection(self):
        # A legal frame with a malformed request payload earns 400 and does not poison the TCP connection.
        self.client.sendall(encode_frame(REQUEST, 1, b"\x01\x00"))
        first = read_frame(self.client)
        self.assertEqual(parse_response(first.payload)[0], 400)
        self.assertEqual(self.ask(2, "/hello.bin")[0], 200)

    def test_unknown_frame_is_skipped_cleanly(self):
        self.client.sendall(encode_frame(99, 77, b"ignored"))
        self.client.sendall(encode_frame(REQUEST, 3, make_request("/hello.bin", [])))
        reply = read_frame(self.client)
        self.assertEqual(reply.stream_id, 3)
        self.assertEqual(parse_response(reply.payload)[0], 200)

    def test_traversal_is_bad_request(self):
        self.assertEqual(self.ask(1, "/../secret")[0], 400)


class ClientIntegrationTests(unittest.TestCase):
    def test_bcurl_process_returns_body_and_verbose_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "item.txt").write_bytes(b"client integration\n")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            server = subprocess.Popen([sys.executable, str(ROOT / "bserve.py"), str(root), str(port)],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            try:
                # bserve prints only after bind/listen, so its first diagnostic is a ready signal.
                self.assertIn("serving", server.stderr.readline())
                result = subprocess.run([sys.executable, str(ROOT / "bcurl.py"), "-v",
                                         f"127.0.0.1:{port}/item.txt"], cwd=ROOT,
                                        capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(result.stdout, b"client integration\n")
                self.assertIn(b"request frame", result.stderr)
                self.assertIn(b"response frame", result.stderr)
            finally:
                server.terminate()
                server.wait(timeout=5)
                server.stderr.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
