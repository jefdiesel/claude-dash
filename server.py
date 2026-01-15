#!/usr/bin/env python3
"""Claude Max Token Usage Tracker - Local Server"""

import json
import os
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

PORT = 8889
DATA_FILE = Path(__file__).parent / "usage.json"
PUBLIC_DIR = Path(__file__).parent / "public"
CLAUDE_LOGS_DIR = Path.home() / ".claude" / "logs"

DEFAULT_DATA = {
    "monthlyLimit": 45_000_000,
    "weeklyLimit": 11_000_000,
    "sessionLimit": 1_500_000,  # 5-hour rolling window
    "resetDay": 1,
    "sessions": []
}


def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return DEFAULT_DATA.copy()


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def scan_claude_logs():
    """Attempt to parse Claude Code logs for token usage."""
    found = []
    if not CLAUDE_LOGS_DIR.exists():
        return {"error": "No Claude logs directory found", "path": str(CLAUDE_LOGS_DIR)}

    log_files = list(CLAUDE_LOGS_DIR.glob("*.json")) + list(CLAUDE_LOGS_DIR.glob("**/*.jsonl"))

    for log_file in sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        try:
            content = log_file.read_text()
            # Try parsing as JSON or JSONL
            for line in content.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    # Look for token usage fields (adjust based on actual log format)
                    if "usage" in entry or "tokens" in entry or "input_tokens" in entry:
                        found.append({
                            "file": log_file.name,
                            "data": entry
                        })
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            pass

    return {"found": len(found), "samples": found[:5], "log_dir": str(CLAUDE_LOGS_DIR)}


def process_otel_logs(otel_data):
    """Extract token usage from OpenTelemetry log events."""
    sessions_added = []

    for resource_log in otel_data.get("resourceLogs", []):
        for scope_log in resource_log.get("scopeLogs", []):
            for record in scope_log.get("logRecords", []):
                # Look for claude_code.api_request events
                event_name = None
                input_tokens = 0
                output_tokens = 0
                cache_read = 0
                cache_creation = 0
                model = ""

                # Parse attributes
                for attr in record.get("attributes", []):
                    key = attr.get("key", "")
                    value = attr.get("value", {})

                    # Get the actual value (could be intValue, stringValue, etc.)
                    val = value.get("intValue") or value.get("stringValue") or value.get("doubleValue", 0)

                    if key == "event.name":
                        event_name = val
                    elif key == "input_tokens":
                        input_tokens = int(val) if val else 0
                    elif key == "output_tokens":
                        output_tokens = int(val) if val else 0
                    elif key == "cache_read_tokens":
                        cache_read = int(val) if val else 0
                    elif key == "cache_creation_tokens":
                        cache_creation = int(val) if val else 0
                    elif key == "model":
                        model = str(val)

                # Only process API request events with token data
                # event.name is "api_request", body is "claude_code.api_request"
                if event_name == "api_request" and (input_tokens > 0 or output_tokens > 0):
                    session = {
                        "timestamp": datetime.now().isoformat(),
                        "input": input_tokens + cache_creation,  # cache_read doesn't count toward limits
                        "output": output_tokens,
                        "note": f"auto: {model}" if model else "auto"
                    }

                    data = load_data()
                    data["sessions"].append(session)
                    save_data(data)
                    sessions_added.append(session)

    return sessions_added


class UsageHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/usage":
            self.send_json(load_data())
        elif path == "/api/scan-logs":
            self.send_json(scan_claude_logs())
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        # OpenTelemetry logs endpoint
        if path == "/v1/logs":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            sessions = process_otel_logs(body)
            self.send_json({"ok": True, "sessions_added": len(sessions)})

        elif path == "/api/session":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            data = load_data()
            session = {
                "timestamp": datetime.now().isoformat(),
                "input": body.get("input", 0),
                "output": body.get("output", 0),
                "note": body.get("note", "")
            }
            data["sessions"].append(session)
            save_data(data)
            self.send_json({"ok": True, "session": session})

        elif path == "/api/settings":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            data = load_data()
            if "limit" in body:
                data["limit"] = int(body["limit"])
            if "resetDay" in body:
                data["resetDay"] = int(body["resetDay"])
            save_data(data)
            self.send_json({"ok": True})

        elif path == "/api/delete-session":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            data = load_data()
            idx = body.get("index")
            if idx is not None and 0 <= idx < len(data["sessions"]):
                removed = data["sessions"].pop(idx)
                save_data(data)
                self.send_json({"ok": True, "removed": removed})
            else:
                self.send_json({"ok": False, "error": "Invalid index"})

        elif path == "/api/calibration":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            data = load_data()
            if "calibrations" not in data:
                data["calibrations"] = []
            data["calibrations"].append(body)
            save_data(data)
            self.send_json({"ok": True, "calibration": body})

        else:
            self.send_error(404)

    def send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress logging


if __name__ == "__main__":
    # Initialize data file if needed
    if not DATA_FILE.exists():
        save_data(DEFAULT_DATA)

    print(f"Token Usage Tracker running at http://localhost:{PORT}")
    print(f"Data file: {DATA_FILE}")
    HTTPServer(("", PORT), UsageHandler).serve_forever()
