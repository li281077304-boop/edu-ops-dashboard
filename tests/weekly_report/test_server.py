import json
import socket
from threading import Thread

from edu_ops.weekly_report.server import WeeklyReportHandler


def test_health_endpoint_returns_complete_snapshot_module_response():
    client, server = socket.socketpair()
    client.settimeout(2)
    server.settimeout(2)
    handler_errors = []

    def handle_request():
        try:
            WeeklyReportHandler(server, ("local", 0), object())
        except BaseException as error:
            handler_errors.append(error)

    worker = Thread(
        target=handle_request,
        name="weekly-report-test-handler",
        daemon=True,
    )
    worker.start()
    test_error = None
    cleanup_errors = []
    try:
        client.sendall(
            b"GET /weekly-report/healthz HTTP/1.1\r\n"
            b"Host: local\r\n"
            b"Connection: close\r\n\r\n"
        )
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = client.recv(4096)
            if not chunk:
                raise AssertionError("HTTP response ended before its headers")
            response += chunk

        header_end = response.index(b"\r\n\r\n")
        headers = response[:header_end].decode("iso-8859-1").split("\r\n")
        content_length = int(
            next(
                line.split(":", 1)[1].strip()
                for line in headers
                if line.lower().startswith("content-length:")
            )
        )
        body = response[header_end + 4 :]
        if len(body) > content_length:
            raise AssertionError("HTTP response contained more bytes than Content-Length")
        while len(body) < content_length:
            chunk = client.recv(4096)
            if not chunk:
                raise AssertionError("HTTP response ended before Content-Length bytes arrived")
            body += chunk
            if len(body) > content_length:
                raise AssertionError("HTTP response contained more bytes than Content-Length")

        assert headers[0].startswith("HTTP/1.0 200")
        assert content_length == len(body)
        assert json.loads(body) == {"status": "ok", "module": "weekly-report"}
    except BaseException as error:
        test_error = error
    finally:
        for connection in (client, server):
            try:
                connection.close()
            except BaseException as error:
                cleanup_errors.append(error)

        try:
            worker.join(timeout=2)
        except BaseException as error:
            cleanup_errors.append(error)

        if worker.is_alive():
            cleanup_errors.append(AssertionError("weekly report handler thread did not stop"))
        if handler_errors:
            cleanup_errors.extend(handler_errors)

    if test_error is not None:
        if cleanup_errors:
            cleanup_error = AssertionError(
                "Weekly Report HTTP boundary cleanup failed: "
                + "; ".join(repr(error) for error in cleanup_errors)
            )
            raise test_error from cleanup_error
        raise test_error
    if cleanup_errors:
        raise AssertionError(
            "Weekly Report HTTP boundary cleanup failed: "
            + "; ".join(repr(error) for error in cleanup_errors)
        ) from cleanup_errors[0]
