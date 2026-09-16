import json
import socket
from threading import Thread

from edu_ops.weekly_report.server import WeeklyReportHandler


def test_health_endpoint_returns_complete_snapshot_module_response():
    client, server = socket.socketpair()

    def handle_request():
        WeeklyReportHandler(server, ("local", 0), object())

    worker = Thread(target=handle_request, daemon=True)
    worker.start()
    try:
        request = b"GET /weekly-report/healthz HTTP/1.1\r\nHost: local\r\nConnection: close\r\n\r\n"
        client.sendall(request)
        response = b""
        while b"\r\n\r\n" not in response:
            response += client.recv(4096)
        header_end = response.index(b"\r\n\r\n")
        headers = response[:header_end].decode("iso-8859-1").split("\r\n")
        content_length = next(
            line.split(":", 1)[1].strip()
            for line in headers
            if line.lower().startswith("content-length:")
        )
        body = response[header_end + 4 :]
        while len(body) < int(content_length):
            body += client.recv(4096)

        assert headers[0].startswith("HTTP/1.0 200")
        assert content_length == str(len(body))
        assert json.loads(body) == {"status": "ok", "module": "weekly-report"}
    finally:
        client.close()
        server.close()
        worker.join(timeout=5)
