"""Standalone Windows Desktop Application Launcher for the 10-Module School Management ERP."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

from werkzeug.serving import make_server

from desktop_app.api import create_app
from desktop_app.database import Database, get_default_db_path


def find_free_port() -> int:
    """Bind to port 0 on localhost to obtain an available ephemeral TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class ServerThread(threading.Thread):
    """Background WSGI server thread bound strictly to 127.0.0.1."""

    def __init__(self, app, port: int) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.server = make_server("127.0.0.1", port, app, threaded=True)

    def run(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()


def wait_for_server(url: str, timeout: float = 10.0) -> bool:
    """Wait until `/api/health` responds with HTTP 200."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.05)
    return False


def run_self_test(base_url: str) -> int:
    """Verify live HTTP server, SQLite WAL database, 10-module bootstrap, and UI HTML."""
    with urllib.request.urlopen(f"{base_url}/api/health", timeout=5.0) as resp:
        health = json.loads(resp.read().decode("utf-8"))
        assert health.get("ok") is True, f"Health check failed: {health}"

    with urllib.request.urlopen(f"{base_url}/api/bootstrap", timeout=5.0) as resp:
        boot = json.loads(resp.read().decode("utf-8"))
        assert boot.get("ok") is True, "Bootstrap failed"
        assert boot["kpis"]["active_students"] >= 1, "Seeded students missing"

    with urllib.request.urlopen(f"{base_url}/", timeout=5.0) as resp:
        html = resp.read().decode("utf-8")
        assert "School Management ERP" in html, "UI index.html missing title"

    print(
        json.dumps(
            {
                "self_test": "PASSED",
                "db_path": health.get("db_path"),
                "kpis": boot.get("kpis"),
            }
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="School Management ERP Desktop App")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run automated startup, SQLite WAL, and API self-test then exit.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Optional localhost port (defaults to an automatic free port).",
    )
    args = parser.parse_args()

    db = Database(get_default_db_path())
    app = create_app(db, seed=True)
    port = args.port or find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    srv = ServerThread(app, port)
    srv.start()

    if not wait_for_server(base_url):
        print("Error: Local ERP server failed to start.", file=sys.stderr)
        return 1

    if args.self_test:
        rc = run_self_test(base_url)
        srv.shutdown()
        return rc

    try:
        import webview

        webview.create_window(
            title="School Management ERP — Standalone Desktop Edition",
            url=base_url,
            width=1380,
            height=860,
            min_size=(1024, 680),
        )
        webview.start()
    except Exception:
        webbrowser.open(base_url)
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
    finally:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

