#!/usr/bin/env python3
"""
Traktor Logger Server
Receives QML debug logs via HTTP and displays them in a web dashboard.

⚠️  SECURITY WARNINGS:
- Do NOT log passwords, API keys, tokens, or credentials (they appear in plaintext)
- Server binds to localhost:8080 only (no network exposure by default)
- No authentication — anyone with localhost access can view all logs and metadata
- On shared machines, this tool should not be used
- All data stored in memory and never encrypted

Usage:
    python3 server.py              # Start with CLI output
    python3 server.py --quiet      # Start with CLI output suppressed
    python3 server.py -q           # Alias for --quiet

Then visit: http://localhost:8080 (browser dashboard always works regardless of CLI mode)

Console Output (unless --quiet):
    - Colored logs by level: DEBUG (cyan), INFO (green), WARN (yellow), ERROR (red), METADATA (magenta)
    - Displays message + data in real-time as logs arrive
    - Useful for immediate feedback without switching to browser

To integrate with your QML code, use the Logger.qml component:
    import Traktor.Defines 1.0

    Logger { id: logger }

    Component.onCompleted: {
        logger.log("My debug message", {value: 42, name: "test"})
        logger.warn("This is a warning")
        logger.error("This is an error")
    }
"""

import http.server
import json
import time
import sys
from datetime import datetime
from urllib.parse import urlparse
from collections import deque

# Security configuration
# Rate limiting and size limits help prevent abuse but are NOT a substitute for access control
MAX_LOGS = 100
MAX_LOG_PAYLOAD_SIZE = 100 * 1024  # 100 KB per log entry (prevents memory exhaustion)
MAX_MESSAGE_LENGTH = 10 * 1024  # 10 KB per message
MAX_DATA_SIZE = 50 * 1024  # 50 KB per data object
RATE_LIMIT_PER_SECOND = 100  # Max logs per second across all sources

# CLI logging configuration
QUIET_MODE = "--quiet" in sys.argv or "-q" in sys.argv

# Store last 100 log entries
logs = deque(maxlen=MAX_LOGS)
LOG_LOCK = None  # Simple synchronization
request_times = deque(maxlen=RATE_LIMIT_PER_SECOND)


# ⚠️  All logs are stored in plaintext and visible to any local user
def print_cli_output(level, message, data):
    """Print formatted output to CLI (unless in quiet mode)"""
    if QUIET_MODE:
        return

    level_color = {
        "debug": "\033[36m",  # Cyan
        "info": "\033[32m",  # Green
        "warn": "\033[33m",  # Yellow
        "error": "\033[31m",  # Red
        "metadata": "\033[35m",  # Magenta
    }
    reset = "\033[0m"
    color = level_color.get(level, "")

    output = f"{color}[{level.upper():8s}]{reset} {message}"
    if data:
        output += f" {json.dumps(data)}"

    print(output)


# Store live metadata (deck state, master clock, playlist, etc)
# ⚠️  Metadata is stored in plaintext and visible to any process/user with localhost access
metadata = {
    "decks": {},  # {0: {...}, 1: {...}, ...}
    "deck_audio": {},  # {A: {...}, B: {...}, ...}
    "deck_effects": {},  # {A: {...}, B: {...}, ...}
    "deck_loops": {},  # {A: {...}, B: {...}, ...}
    "deck_cues": {},  # {A: {...}, B: {...}, ...}
    "deck_stems": {},  # {A: {...}, B: {...}, ...}
    "master": {},
    "master_audio": {},
    "channels": {},  # {1: {...}, 2: {...}}
    "playlist": {},
    "browser": {},
    "last_update": None,
}


class DebugLogHandler(http.server.BaseHTTPRequestHandler):
    def _handle_json_post(self, metadata_key, path_pattern=None):
        """Generic JSON POST handler with validation

        Args:
            metadata_key: Key to store in metadata dict (e.g., "decks", "deck_audio")
            path_pattern: If callable, extract identifier from path using this function

        Returns: (success, data, identifier) tuple
        """
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_LOG_PAYLOAD_SIZE:
            self.send_response(413)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Payload too large"}).encode("utf-8"))
            return (False, None, None)

        body = self.rfile.read(content_length).decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
            identifier = path_pattern(self.path) if path_pattern else None

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

            return (True, data, identifier)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode("utf-8"))
            return (False, None, None)

    def _store_metadata(self, data, key, sub_key=None):
        """Store metadata and update last_update timestamp"""
        entry = {"state": data, "timestamp": datetime.now().isoformat()}

        if sub_key:
            if key not in metadata:
                metadata[key] = {}
            metadata[key][sub_key] = entry
            print_cli_output("metadata", f"{key}/{sub_key}", data)
        else:
            metadata[key] = entry
            print_cli_output("metadata", key, data)

        metadata["last_update"] = datetime.now().isoformat()

    def do_POST(self):
        """Handle POST requests for debug logs and metadata"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/log":
            # Rate limiting check
            now = time.time()
            request_times.append(now)
            if len(request_times) >= RATE_LIMIT_PER_SECOND:
                oldest = now - 1.0
                if request_times[0] > oldest:
                    # Too many requests in last second
                    self.send_response(429)  # Too Many Requests
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({"error": "Rate limit exceeded"}).encode("utf-8")
                    )
                    return

            # Size limit check
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_LOG_PAYLOAD_SIZE:
                self.send_response(413)  # Payload Too Large
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": "Payload too large"}).encode("utf-8")
                )
                return

            body = self.rfile.read(content_length).decode("utf-8", errors="replace")

            try:
                data = json.loads(body)

                # Validate message size
                message = data.get("message", "")
                if len(message) > MAX_MESSAGE_LENGTH:
                    message = message[:MAX_MESSAGE_LENGTH] + "...[truncated]"

                # Validate data object size
                data_obj = data.get("data", None)
                data_str = json.dumps(data_obj) if data_obj else ""
                if len(data_str) > MAX_DATA_SIZE:
                    data_obj = {"error": "Data object too large", "size": len(data_str)}

                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": data.get("level", "info"),
                    "message": message,
                    "data": data_obj,
                }
                logs.append(log_entry)

                # Send response
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

                # Print to console (unless quiet mode)
                print_cli_output(
                    log_entry["level"], log_entry["message"], log_entry["data"]
                )

            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode("utf-8"))

        elif path == "/logs":
            # Return all logs as JSON
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy", "default-src 'self'; script-src 'self'"
            )
            self.end_headers()
            self.wfile.write(json.dumps(list(logs)).encode("utf-8"))

        elif path == "/metadata":
            # Receive and store metadata from QML (legacy format with type/state fields)
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_LOG_PAYLOAD_SIZE:
                self.send_response(413)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": "Payload too large"}).encode("utf-8")
                )
                return

            body = self.rfile.read(content_length).decode("utf-8", errors="replace")

            try:
                data = json.loads(body)
                metadata_type = data.get("type", "")
                state = data.get("state", {})

                # Store metadata by type
                if metadata_type.startswith("deck/"):
                    deck_id = metadata_type.split("/")[1]
                    metadata["decks"][deck_id] = {
                        "state": state,
                        "timestamp": datetime.now().isoformat(),
                    }
                elif metadata_type == "master":
                    metadata["master"] = {
                        "state": state,
                        "timestamp": datetime.now().isoformat(),
                    }
                elif metadata_type == "playlist":
                    metadata["playlist"] = {
                        "state": state,
                        "timestamp": datetime.now().isoformat(),
                    }

                metadata["last_update"] = datetime.now().isoformat()

                # Print to console (unless quiet mode)
                print_cli_output("metadata", metadata_type, state)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode("utf-8"))

        elif path.startswith("/metadata/deck/"):
            # Handle /metadata/deck/A, /metadata/deck/B, etc.
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_LOG_PAYLOAD_SIZE:
                self.send_response(413)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": "Payload too large"}).encode("utf-8")
                )
                return

            body = self.rfile.read(content_length).decode("utf-8", errors="replace")

            try:
                data = json.loads(body)
                deck_letter = path.split("/")[-1]

                metadata["decks"][deck_letter] = {
                    "state": data,
                    "timestamp": datetime.now().isoformat(),
                }
                metadata["last_update"] = datetime.now().isoformat()

                # Print to console (unless quiet mode)
                print_cli_output("metadata", f"deck/{deck_letter}", data)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode("utf-8"))

        elif path == "/metadata/master":
            # Handle /metadata/master
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_LOG_PAYLOAD_SIZE:
                self.send_response(413)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": "Payload too large"}).encode("utf-8")
                )
                return

            body = self.rfile.read(content_length).decode("utf-8", errors="replace")

            try:
                data = json.loads(body)

                metadata["master"] = {
                    "state": data,
                    "timestamp": datetime.now().isoformat(),
                }
                metadata["last_update"] = datetime.now().isoformat()

                # Print to console (unless quiet mode)
                print_cli_output("metadata", "master", data)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode("utf-8"))

        elif path.startswith("/deckLoaded/"):
            # traktor-api-client: /deckLoaded/A, /deckloaded/B, etc.
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_LOG_PAYLOAD_SIZE:
                self.send_response(413)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": "Payload too large"}).encode("utf-8")
                )
                return

            body = self.rfile.read(content_length).decode("utf-8", errors="replace")

            try:
                data = json.loads(body)
                deck_letter = path.split("/")[-1]

                metadata["decks"][deck_letter] = {
                    "state": data,
                    "timestamp": datetime.now().isoformat(),
                    "event": "deckLoaded",
                }
                metadata["last_update"] = datetime.now().isoformat()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

                print_cli_output("metadata", f"deckLoaded/{deck_letter}", data)

            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode("utf-8"))

        elif path.startswith("/updateDeck/"):
            # traktor-api-client: /updateDeck/A, /updateDeck/B, etc.
            success, data, deck_letter = self._handle_json_post(
                "decks", lambda p: p.split("/")[-1]
            )
            if success:
                # Merge update with existing deck state
                if deck_letter not in metadata["decks"]:
                    metadata["decks"][deck_letter] = {"state": {}}
                metadata["decks"][deck_letter]["state"].update(data)
                metadata["decks"][deck_letter]["timestamp"] = datetime.now().isoformat()
                metadata["decks"][deck_letter]["event"] = "updateDeck"
                metadata["last_update"] = datetime.now().isoformat()
                print_cli_output("metadata", f"updateDeck/{deck_letter}", data)

        elif path == "/updateMasterClock":
            # traktor-api-client: /updateMasterClock
            success, data, _ = self._handle_json_post("master")
            if success:
                self._store_metadata(data, "master")
                metadata["master"]["event"] = "updateMasterClock"
                print_cli_output("metadata", "updateMasterClock", data)

        elif path.startswith("/updateChannel/"):
            # traktor-api-client: /updateChannel/1, /updateChannel/2, etc.
            success, data, channel = self._handle_json_post(
                "channels", lambda p: p.split("/")[-1]
            )
            if success:
                if "channels" not in metadata:
                    metadata["channels"] = {}
                metadata["channels"][channel] = {
                    "state": data,
                    "timestamp": datetime.now().isoformat(),
                    "event": "updateChannel",
                }
                metadata["last_update"] = datetime.now().isoformat()
                print_cli_output("metadata", f"updateChannel/{channel}", data)

        elif path.startswith("/updateDeckAudio/"):
            # Audio controls: volume, EQ, filter
            success, data, deck = self._handle_json_post(
                "deck_audio", lambda p: p.split("/")[-1]
            )
            if success:
                self._store_metadata(data, "deck_audio", deck)

        elif path.startswith("/updateDeckEffects/"):
            success, data, deck = self._handle_json_post(
                "deck_effects", lambda p: p.split("/")[-1]
            )
            if success:
                self._store_metadata(data, "deck_effects", deck)

        elif path.startswith("/updateDeckLoop/"):
            success, data, deck = self._handle_json_post(
                "deck_loops", lambda p: p.split("/")[-1]
            )
            if success:
                self._store_metadata(data, "deck_loops", deck)

        elif path.startswith("/updateDeckCues/"):
            success, data, deck = self._handle_json_post(
                "deck_cues", lambda p: p.split("/")[-1]
            )
            if success:
                self._store_metadata(data, "deck_cues", deck)

        elif path.startswith("/updateDeckStems/"):
            success, data, deck = self._handle_json_post(
                "deck_stems", lambda p: p.split("/")[-1]
            )
            if success:
                # Log stem data for debugging
                if data and "stems" in data:
                    for idx, stem in enumerate(data["stems"]):
                        if stem.get("filterOn"):
                            print(
                                f"Deck {deck} Stem {idx+1}: volume={stem.get('volume', 0):.2f}, filter={stem.get('filter', 0.5):.2f}, filterOn={stem.get('filterOn')}"
                            )
                self._store_metadata(data, "deck_stems", deck)

        elif path == "/updateMasterAudio":
            success, data, _ = self._handle_json_post("master_audio")
            if success:
                self._store_metadata(data, "master_audio")

        elif path == "/updateBrowser":
            success, data, _ = self._handle_json_post("browser")
            if success:
                self._store_metadata(data, "browser")

        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        """Handle GET requests for the dashboard"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            )
            self.end_headers()
            self.wfile.write(get_html_dashboard().encode("utf-8"))

        elif path == "/logs":
            # Return logs as JSON
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(json.dumps(list(logs)).encode("utf-8"))

        elif path == "/state":
            # Return current metadata state
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(json.dumps(metadata).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def get_html_dashboard():
    """Return HTML for the debug dashboard with logs and metadata tabs"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Traktor Logger</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --bg-0: #08090b;
            --bg-1: #11151a;
            --bg-2: #1a1f27;
            --bg-3: #252c36;
            --line: #2e3744;
            --text: #e6ebf2;
            --text-dim: #9aa7b8;
            --accent: #ff7a1a;
            --accent-soft: rgba(255, 122, 26, 0.18);
            --ok: #7cd14d;
        }
        body {
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            background: radial-gradient(circle at top, #12161c 0%, var(--bg-0) 55%);
            color: var(--text);
            padding: 20px;
            line-height: 1.6;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--line);
        }
        h1 {
            font-size: 24px;
            color: var(--accent);
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }
        .status {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--ok);
            animation: pulse 1s infinite;
            box-shadow: 0 0 8px rgba(124, 209, 77, 0.6);
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 0;
            margin-bottom: 20px;
            border-bottom: 2px solid var(--line);
        }
        .tab-btn {
            padding: 12px 24px;
            background: transparent;
            color: var(--text-dim);
            border: none;
            cursor: pointer;
            font-weight: bold;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .tab-btn:hover {
            color: var(--text);
        }
        .tab-btn.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
        }
        
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        button {
            padding: 8px 16px;
            background: linear-gradient(180deg, #3a4658 0%, #242d39 100%);
            color: var(--text);
            border: 1px solid #3f4d60;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.2s;
        }
        button:hover {
            border-color: var(--accent);
            box-shadow: inset 0 0 0 1px var(--accent-soft);
        }
        button.danger {
            background: linear-gradient(180deg, #8b3131 0%, #6e2222 100%);
            color: white;
            border-color: #944343;
        }
        button.danger:hover {
            border-color: #df5c5c;
        }
        
        /* Logs view */
        .log-container {
            background: linear-gradient(180deg, #0f1318 0%, #0b0f14 100%);
            border: 1px solid var(--line);
            border-radius: 4px;
            height: 600px;
            overflow-y: auto;
            padding: 0;
        }
        .log-entry {
            padding: 12px 16px;
            border-bottom: 1px solid #1f2530;
            display: flex;
            gap: 12px;
            font-size: 13px;
            transition: background 0.2s;
        }
        .log-entry:hover {
            background: #18202b;
        }
        .log-entry.debug { --level-color: #4dbed1; }
        .log-entry.info { --level-color: var(--ok); }
        .log-entry.warn { --level-color: #f9b44c; }
        .log-entry.error { --level-color: #f26666; }
        .log-level {
            min-width: 60px;
            font-weight: bold;
            color: var(--level-color);
            text-transform: uppercase;
            font-size: 11px;
        }
        .log-time {
            min-width: 100px;
            color: var(--text-dim);
            font-size: 12px;
            font-family: monospace;
        }
        .log-message {
            flex: 1;
            word-break: break-word;
        }
        .log-data {
            color: #93a0b1;
            font-size: 12px;
            margin-top: 4px;
            font-family: monospace;
            max-height: 100px;
            overflow: auto;
        }
        
        /* Metadata view - compact deck HUD */
        .metadata-container {
            background: linear-gradient(180deg, #0f1318 0%, #0b0f14 100%);
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: 12px;
        }
        .hud-master {
            display: grid;
            grid-template-columns: repeat(6, minmax(110px, 1fr));
            gap: 8px;
            margin-bottom: 10px;
        }
        .hud-chip {
            background: #161d26;
            border: 1px solid #2d3643;
            border-radius: 4px;
            padding: 6px 8px;
            min-height: 50px;
        }
        .hud-chip-label {
            color: var(--text-dim);
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 3px;
        }
        .hud-chip-value {
            color: var(--text);
            font-size: 13px;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .hud-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .deck-hud {
            background: linear-gradient(180deg, #1a2028 0%, #141a22 100%);
            border: 1px solid #2d3643;
            border-radius: 6px;
            padding: 10px;
            min-height: auto;
            display: grid;
            grid-template-rows: auto auto 1fr;
            gap: 8px;
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02);
        }
        .deck-hud.inactive {
            opacity: 0.6;
            border-style: dashed;
        }
        .deck-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }
        .deck-name {
            color: var(--accent);
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-weight: 700;
        }
        .deck-flags {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            justify-content: flex-end;
        }
        .deck-flag {
            border: 1px solid #3a4658;
            border-radius: 999px;
            padding: 1px 7px;
            font-size: 10px;
            letter-spacing: 0.03em;
            color: #c7d1de;
            background: #1a222e;
        }
        .deck-flag.on {
            color: #0f120c;
            background: var(--ok);
            border-color: #95de70;
            font-weight: 700;
        }
        .deck-track {
            border: 1px solid #2a3340;
            background: #121821;
            border-radius: 4px;
            padding: 7px 8px;
            min-height: 54px;
        }
        .deck-title {
            color: var(--text);
            font-weight: 700;
            font-size: 13px;
            line-height: 1.2;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .deck-subtitle {
            color: var(--text-dim);
            font-size: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-top: 2px;
        }
        .deck-metrics {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 6px;
            align-content: start;
        }
        .metric {
            background: #10161e;
            border: 1px solid #283140;
            border-radius: 4px;
            padding: 5px 7px;
            min-height: 44px;
        }
        .metric.audio {
            background: linear-gradient(180deg, #1a1f28 0%, #0f141d 100%);
            border: 1px solid #3a4656;
            box-shadow: inset 0 0 0 1px rgba(255, 159, 64, 0.12);
        }
        .metric-label {
            color: #93a0b1;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .metric.audio .metric-label {
            color: #ffa940;
        }
        .metric-value {
            color: #ffd9b8;
            font-size: 13px;
            font-weight: 700;
            margin-top: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .metric.audio .metric-value {
            color: #ffb366;
        }
        .playlist-strip {
            margin-top: 10px;
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
        }
        .playlist-item {
            background: #131a23;
            border: 1px solid #2d3643;
            border-radius: 4px;
            padding: 6px 8px;
        }
        .playlist-item .metadata-label {
            font-size: 10px;
            margin-bottom: 2px;
        }
        .playlist-item .metadata-value {
            font-size: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .browser-container {
            padding: 12px;
        }
        .browser-path {
            font-size: 12px;
            color: #93a0b1;
            margin-bottom: 12px;
            padding: 6px 10px;
            background: #131a23;
            border: 1px solid #2d3643;
            border-radius: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .browser-path span {
            color: #e6ebf2;
        }
        .browser-list {
            border: 1px solid #2d3643;
            border-radius: 4px;
            overflow: hidden;
        }
        .browser-row {
            display: grid;
            grid-template-columns: 32px 1fr 80px 60px 50px;
            align-items: center;
            padding: 5px 8px;
            border-bottom: 1px solid #1e2733;
            font-size: 12px;
            color: #c7d1de;
            gap: 8px;
        }
        .browser-row:last-child {
            border-bottom: none;
        }
        .browser-row.selected {
            background: rgba(90, 140, 255, 0.15);
            border-left: 3px solid #5a8cff;
            color: #e6ebf2;
        }
        .browser-row.above {
            background: #0f1318;
        }
        .browser-row.below {
            background: #111820;
        }
        .browser-row .br-idx {
            color: #4e5e72;
            font-size: 11px;
            text-align: right;
        }
        .browser-row .br-name {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .browser-row .br-artist {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #93a0b1;
            font-size: 11px;
        }
        .browser-row .br-bpm {
            text-align: right;
            color: #ffd9b8;
            font-size: 11px;
        }
        .browser-row .br-key {
            text-align: right;
            font-size: 11px;
            color: #b3c8ff;
        }
        .browser-row.selected .br-name {
            font-weight: 700;
        }
        .browser-header {
            display: grid;
            grid-template-columns: 32px 1fr 80px 60px 50px;
            padding: 4px 8px;
            font-size: 10px;
            color: #4e5e72;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            gap: 8px;
            margin-bottom: 2px;
        }
        @media (max-width: 980px) {
            .hud-master {
                grid-template-columns: repeat(3, minmax(110px, 1fr));
            }
            .hud-grid {
                grid-template-columns: 1fr;
            }
        }
        @media (max-width: 640px) {
            .hud-master {
                grid-template-columns: repeat(2, minmax(110px, 1fr));
            }
            .deck-metrics {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .playlist-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        .metadata-number {
            color: #ffd9b8;
            font-weight: 600;
        }
        .metadata-bool-true {
            color: var(--ok);
            font-weight: 700;
        }
        .metadata-bool-false {
            color: #d2dae6;
            opacity: 0.8;
            font-weight: 600;
        }
        .empty-state {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 320px;
            color: #6f7d90;
            font-size: 14px;
        }
        .filter-controls {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 6px 12px;
            background: #1a212b;
            color: var(--text);
            border: 1px solid #3b4656;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }
        .filter-btn.active {
            background: var(--accent);
            color: #111;
            border-color: var(--accent);
            font-weight: 700;
        }
        .filter-btn:hover {
            border-color: var(--accent);
        }
        
        code {
            background: #1f2630;
            padding: 2px 6px;
            border-radius: 3px;
        }
        
        /* Fullscreen mode */
        .fullscreen-mode {
            padding: 0 !important;
        }
        .fullscreen-mode header,
        .fullscreen-mode .tabs,
        .fullscreen-mode #toggleDebugMetadata,
        .fullscreen-mode #fullscreenBtn {
            display: none !important;
        }
        .fullscreen-mode .container {
            padding: 0;
            max-width: none;
        }
        .fullscreen-mode #metadata {
            padding: 0;
        }
        .fullscreen-mode .metadata-container {
            margin: 0;
            padding: 8px;
            border: none;
            border-radius: 0;
        }
        .fullscreen-btn {
            padding: 6px 12px;
            background: #1a212b;
            color: var(--text);
            border: 1px solid #3b4656;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
            margin-left: auto;
        }
        .fullscreen-btn:hover {
            border-color: var(--accent);
            color: var(--accent);
        }
        
        /* Fullscreen close button */
        .fullscreen-close-btn {
            position: fixed;
            top: 12px;
            right: 12px;
            width: 24px;
            height: 24px;
            background: linear-gradient(180deg, #3a4658 0%, #242d39 100%);
            border: 1px solid #3f4d60;
            border-radius: 3px;
            color: var(--text);
            font-size: 12px;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            transition: all 0.2s;
            font-weight: bold;
            line-height: 1;
        }
        .fullscreen-close-btn:hover {
            border-color: var(--accent);
            color: var(--accent);
            box-shadow: inset 0 0 0 1px var(--accent-soft);
        }
        .fullscreen-mode .fullscreen-close-btn {
            display: flex;
        }
    </style>
</head>
<body>
    <button class="fullscreen-close-btn" id="fullscreenCloseBtn" title="Close fullscreen (or press ESC)">✕</button>
    <div class="container">
        <header>
            <h1>🧭 Traktor Logger</h1>
            <div class="status">
                <div class="status-indicator"></div>
                <span>Listening on <code>localhost:8080</code></span>
            </div>
        </header>

        <!-- Tabs -->
        <div class="tabs">
            <button class="tab-btn active" data-tab="logs">📝 Console Logs</button>
            <button class="tab-btn" data-tab="metadata">📊 Live Metadata</button>
            <button class="tab-btn" data-tab="browser">🎵 Browser</button>
        </div>

        <!-- Logs Tab -->
        <div id="logs" class="tab-content active">
            <div class="controls">
                <button id="refreshBtn">🔄 Auto-refresh (on)</button>
                <button id="clearBtn" class="danger">🗑️ Clear logs</button>
            </div>

            <div class="filter-controls">
                <button class="filter-btn active" data-level="all">All</button>
                <button class="filter-btn" data-level="debug">🔵 Debug</button>
                <button class="filter-btn" data-level="info">🟢 Info</button>
                <button class="filter-btn" data-level="warn">🟡 Warn</button>
                <button class="filter-btn" data-level="error">🔴 Error</button>
            </div>

            <div class="log-container" id="logContainer">
                <div class="empty-state">Waiting for logs...</div>
            </div>
        </div>

        <!-- Metadata Tab -->
        <div id="metadata" class="tab-content">
            <div class="controls">
                <button id="toggleDebugMetadata">🔍 Raw Metadata (off)</button>
                <button id="fullscreenBtn" class="fullscreen-btn">⛶ Fullscreen</button>
            </div>
            <div class="metadata-container" id="metadataContainer">
                <div class="empty-state">No metadata received yet. Interact with Traktor to send deck/master state.</div>
            </div>
            <div id="debugMetadataContainer" style="display:none; margin-top: 20px;">
                <h3 style="color: var(--accent); margin-bottom: 10px;">Raw Metadata (for debugging):</h3>
                <pre id="debugMetadataContent" style="background: #0f1318; border: 1px solid var(--line); border-radius: 4px; padding: 12px; overflow-x: auto; font-size: 11px; max-height: 400px; overflow-y: auto;"></pre>
            </div>
        </div>

        <!-- Browser Tab -->
        <div id="browser" class="tab-content">
            <div class="browser-container" id="browserContainer">
                <div class="empty-state">No browser data received yet. Open the browser on your controller.</div>
            </div>
        </div>
    </div>

    <script>
        let autoRefresh = true;
        let autoRefreshMetadata = true;
        let selectedLevel = "all";
        let allLogs = [];
        let allMetadata = {};
        let showDebugMetadata = false;
        let isFullscreen = false;

        const logContainer = document.getElementById("logContainer");
        const metadataContainer = document.getElementById("metadataContainer");
        const refreshBtn = document.getElementById("refreshBtn");
        const clearBtn = document.getElementById("clearBtn");
        const filterBtns = document.querySelectorAll(".filter-btn");
        const tabBtns = document.querySelectorAll(".tab-btn");
        const tabContents = document.querySelectorAll(".tab-content");
        const toggleDebugMetadataBtn = document.getElementById("toggleDebugMetadata");
        const debugMetadataContainer = document.getElementById("debugMetadataContainer");
        const debugMetadataContent = document.getElementById("debugMetadataContent");
        const fullscreenBtn = document.getElementById("fullscreenBtn");
        const fullscreenCloseBtn = document.getElementById("fullscreenCloseBtn");

        // Tab switching
        tabBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                const tabId = btn.dataset.tab;
                tabBtns.forEach(b => b.classList.remove("active"));
                tabContents.forEach(c => c.classList.remove("active"));
                btn.classList.add("active");
                document.getElementById(tabId).classList.add("active");
            });
        });

        refreshBtn.addEventListener("click", () => {
            autoRefresh = !autoRefresh;
            refreshBtn.textContent = autoRefresh ? "🔄 Auto-refresh ON" : "⏸️ Auto-refresh OFF";
        });

        clearBtn.addEventListener("click", () => {
            if (confirm("Clear all logs?")) {
                allLogs = [];
                renderLogs();
            }
        });

        filterBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                filterBtns.forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                selectedLevel = btn.dataset.level;
                renderLogs();
            });
        });

        toggleDebugMetadataBtn.addEventListener("click", () => {
            showDebugMetadata = !showDebugMetadata;
            debugMetadataContainer.style.display = showDebugMetadata ? "block" : "none";
            toggleDebugMetadataBtn.textContent = showDebugMetadata 
                ? "🔍 Raw Metadata ON" 
                : "🔍 Raw Metadata OFF";
        });

        // Fullscreen toggle
        fullscreenBtn.addEventListener("click", () => {
            isFullscreen = !isFullscreen;
            document.body.classList.toggle("fullscreen-mode", isFullscreen);
            fullscreenBtn.textContent = isFullscreen ? "✕ Exit Fullscreen" : "⛶ Fullscreen";
        });

        // Fullscreen close button click
        fullscreenCloseBtn.addEventListener("click", () => {
            isFullscreen = false;
            document.body.classList.remove("fullscreen-mode");
            fullscreenBtn.textContent = "⛶ Fullscreen";
        });

        // ESC key to exit fullscreen
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && isFullscreen) {
                isFullscreen = false;
                document.body.classList.remove("fullscreen-mode");
                fullscreenBtn.textContent = "⛶ Fullscreen";
            }
        });

        function fetchLogs() {
            fetch("/logs")
                .then(res => res.json())
                .then(data => {
                    allLogs = data;
                    renderLogs();
                })
                .catch(err => console.error("Error fetching logs:", err));
        }

        function fetchMetadata() {
            fetch("/state")
                .then(res => res.json())
                .then(data => {
                    allMetadata = data;
                    renderMetadata();
                    renderBrowser();
                })
                .catch(err => console.error("Error fetching metadata:", err));
        }

        function renderLogs() {
            const filtered = selectedLevel === "all" 
                ? allLogs 
                : allLogs.filter(log => log.level === selectedLevel);

            if (filtered.length === 0) {
                logContainer.innerHTML = '<div class="empty-state">No logs to display</div>';
                return;
            }

            logContainer.innerHTML = filtered.map(log => {
                const time = new Date(log.timestamp).toLocaleTimeString();
                let html = `
                    <div class="log-entry ${log.level}">
                        <div class="log-level">${log.level}</div>
                        <div class="log-time">${time}</div>
                        <div>
                            <div class="log-message">${escapeHtml(log.message)}</div>
                `;
                if (log.data) {
                    html += `<div class="log-data">${escapeHtml(JSON.stringify(log.data, null, 2))}</div>`;
                }
                html += `</div></div>`;
                return html;
            }).join("");

            // Auto-scroll to bottom
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        function renderMetadata() {
            const decks = allMetadata.decks || {};
            const master = allMetadata.master || {};
            const channels = allMetadata.channels || {};
            const masterAudio = (allMetadata.master_audio && allMetadata.master_audio.state) || {};
            const deckAudio = allMetadata.deck_audio || {};
            const deckEffects = allMetadata.deck_effects || {};
            const deckLoops = allMetadata.deck_loops || {};
            const deckCues = allMetadata.deck_cues || {};
            const deckStems = allMetadata.deck_stems || {};
            const browser = (allMetadata.browser && allMetadata.browser.state) || {};
            const playlist = allMetadata.playlist || {};

            if (Object.keys(decks).length === 0 && Object.keys(master).length === 0) {
                metadataContainer.innerHTML = '<div class="empty-state">No metadata received yet</div>';
                return;
            }

            // Update debug view if visible
            if (showDebugMetadata) {
                debugMetadataContent.textContent = JSON.stringify(allMetadata, null, 2);
            }

            const masterState = master.state || {};
            const masterBpm = masterState.bpm;
            const masterDeck = masterState.deck;
            const deckMap = normalizeDeckMap(decks);
            
            let html = '';
            
            // Master audio controls section
            if (Object.keys(masterAudio).length > 0) {
                html += '<div style="margin-bottom: 15px; background: rgba(255,159,64,0.1); border: 1px solid #3a4656; border-radius: 4px; padding: 12px;">';
                html += '<div style="font-size: 12px; color: #ffa940; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; font-weight: 700;">🎚️ Master Audio</div>';
                html += '<div>';
                html += masterAudio.master_volume !== undefined ? renderColoredFader('Volume', masterAudio.master_volume) : '';
                html += masterAudio.master_eq_low !== undefined ? renderColoredFader('EQ Low', masterAudio.master_eq_low) : '';
                html += masterAudio.master_eq_mid !== undefined ? renderColoredFader('EQ Mid', masterAudio.master_eq_mid) : '';
                html += masterAudio.master_eq_high !== undefined ? renderColoredFader('EQ High', masterAudio.master_eq_high) : '';
                html += masterAudio.crossfader !== undefined ? renderColoredFader('Crossfader', masterAudio.crossfader) : '';
                html += masterAudio.headphone_mix !== undefined ? renderColoredFader('Headphone Mix', masterAudio.headphone_mix) : '';
                html += '</div></div>';
            }
            
            // Build top strip: master info + channel levels (CH 1-4 mapped to Deck A-D)
            html += '<div style="margin-bottom: 15px; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px;">';

            html += `
                <div style="background: #161d26; border: 1px solid #2d3643; padding: 8px; border-radius: 4px;">
                    <div style="font-size: 10px; color: #93a0b1; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Master Deck</div>
                    <div style="font-size: 14px; color: #e6ebf2; font-weight: 700;">${escapeHtml(formatCompactValue(masterDeck, "—"))}</div>
                </div>
            `;

            html += `
                <div style="background: #161d26; border: 1px solid #2d3643; padding: 8px; border-radius: 4px;">
                    <div style="font-size: 10px; color: #93a0b1; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Master Tempo</div>
                    <div style="font-size: 14px; color: #e6ebf2; font-weight: 700;">${masterBpm ? escapeHtml(masterBpm.toFixed(1)) : "—"}</div>
                </div>
            `;

            for (let ch = 1; ch <= 4; ch++) {
                const chData = (channels[ch] && channels[ch].state) ? channels[ch].state : {};
                const onAir = asBool(chData.isOnAir);
                const levelRaw = Number(chData.onAirLevel);
                const levelNorm = Number.isFinite(levelRaw) ? Math.max(0, Math.min(1, levelRaw)) : 0;
                const levelPct = (levelNorm * 100).toFixed(1);
                const deckLetter = String.fromCharCode(64 + ch);
                const fillColor = onAir ? '#7cd14d' : '#6e7b8f';

                html += `
                    <div style="background: ${onAir ? 'rgba(124,209,77,0.12)' : 'rgba(100,100,100,0.12)'}; border: 1px solid ${onAir ? '#95de70' : '#3a4656'}; padding: 8px; border-radius: 4px;">
                        <div style="display: flex; justify-content: space-between; gap: 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                            <span style="color: ${onAir ? '#95de70' : '#93a0b1'};">CH ${ch} (${deckLetter})</span>
                        </div>
                        <div style="height: 18px; background: #0f1318; border: 1px solid #2b3442; border-radius: 3px; overflow: hidden; margin-bottom: 4px;">
                            <div style="height: 100%; width: ${levelPct}%; background: linear-gradient(90deg, ${fillColor} 0%, ${fillColor} 100%); box-shadow: inset 0 0 6px rgba(0,0,0,0.45);"></div>
                        </div>
                        <div style="font-size: 12px; color: ${onAir ? '#d6efbf' : '#c7d1de'}; font-weight: 700;">${levelPct}%</div>
                    </div>
                `;
            }
            html += '</div>';

            html += '<div class="hud-grid">';
            html += renderDeckHud(0, deckMap[0], masterBpm, masterDeck, deckAudio, deckEffects, deckLoops, deckCues, deckStems);
            html += renderDeckHud(1, deckMap[1], masterBpm, masterDeck, deckAudio, deckEffects, deckLoops, deckCues, deckStems);
            html += renderDeckHud(2, deckMap[2], masterBpm, masterDeck, deckAudio, deckEffects, deckLoops, deckCues, deckStems);
            html += renderDeckHud(3, deckMap[3], masterBpm, masterDeck, deckAudio, deckEffects, deckLoops, deckCues, deckStems);
            html += '</div>';

            const playlistState = playlist.state || {};
            if (Object.keys(playlistState).length > 0) {
                const topPlaylistFields = Object.entries(playlistState).slice(0, 4);
                html += '<div class="playlist-strip">';
                topPlaylistFields.forEach(([key, value]) => {
                    html += `
                        <div class="playlist-item">
                            <div class="metadata-label">${escapeHtml(key)}</div>
                            <div class="metadata-value">${formatCompactValue(value)}</div>
                        </div>
                    `;
                });
                html += '</div>';
            }

            metadataContainer.innerHTML = html;
        }

        function renderBrowser() {
            const browserContainer = document.getElementById("browserContainer");
            const playlist = allMetadata.playlist || {};
            const state = playlist.state || {};
            const items = state.items || [];

            if (!state.path && items.length === 0) {
                browserContainer.innerHTML = '<div class="empty-state">No browser data received yet. Open the browser on your controller.</div>';
                return;
            }

            const pathSegments = (state.path || "").split(" | ").filter(s => s.length > 0);
            const pathHtml = pathSegments.map((seg, i) =>
                i < pathSegments.length - 1
                    ? escapeHtml(seg) + ' <span style="color:#3a4656">›</span> '
                    : '<span>' + escapeHtml(seg) + '</span>'
            ).join("");

            let html = '<div class="browser-path">' + (pathHtml || '—') + '</div>';

            if (items.length === 0) {
                html += '<div class="empty-state" style="margin-top:12px">No items in window</div>';
                browserContainer.innerHTML = html;
                return;
            }

            html += '<div class="browser-header">';
            html += '<div>#</div><div>Name / Track</div><div>Artist</div><div>BPM</div><div>Key</div>';
            html += '</div>';
            html += '<div class="browser-list">';

            items.forEach(item => {
                const isSel = item.isSelected;
                const isAbove = !isSel && item.index < (state.selectedIndex || 0);
                const rowClass = isSel ? "selected" : (isAbove ? "above" : "below");
                const name = item.trackName || item.nodeName || "—";
                const artist = item.artistName || "";
                const bpm = (item.bpm != null && item.bpm > 0) ? Number(item.bpm).toFixed(1) : "";
                const key = item.key || "";

                html += '<div class="browser-row ' + rowClass + '">';
                html += '<div class="br-idx">' + escapeHtml(String(item.index + 1)) + '</div>';
                html += '<div class="br-name">' + escapeHtml(name) + '</div>';
                html += '<div class="br-artist">' + escapeHtml(artist) + '</div>';
                html += '<div class="br-bpm">' + escapeHtml(bpm) + '</div>';
                html += '<div class="br-key">' + escapeHtml(key) + '</div>';
                html += '</div>';
            });

            html += '</div>';
            browserContainer.innerHTML = html;
        }

        function normalizeDeckMap(decks) {
            const out = { 0: null, 1: null, 2: null, 3: null };
            Object.entries(decks || {}).forEach(([rawId, data]) => {
                const normalized = normalizeDeckId(rawId);
                if (normalized >= 0 && normalized <= 3) {
                    out[normalized] = data;
                }
            });
            return out;
        }

        function normalizeDeckId(deckId) {
            const asNumber = Number(deckId);
            if (Number.isFinite(asNumber)) {
                return asNumber;
            }
            const upper = String(deckId).toUpperCase();
            if (upper === "A") return 0;
            if (upper === "B") return 1;
            if (upper === "C") return 2;
            if (upper === "D") return 3;
            return -1;
        }

        function renderDeckHud(deckIndex, deckData, masterBpm, masterDeck, deckAudio, deckEffects, deckLoops, deckCues, deckStems) {
            const state = (deckData && deckData.state) ? deckData.state : {};
            const deckLetter = getDeckLabel(deckIndex);
            const isMaster = masterDeck && String(masterDeck).toUpperCase() === deckLetter;
            const title = state.title || "-";
            const artist = state.artist || "-";
            const bpm = state.bpm || "-";
            const keyText = state.keyText || state.key || "-";
            const elapsedTime = state.elapsedTime || 0;
            const trackLength = state.trackLength || 0;
            const tempo = state.tempo || 1;
            
            // Get optional audio/effects/loop/cue/stems data for this deck
            const audioData = (deckAudio[deckLetter] && deckAudio[deckLetter].state) || {};
            const effectsData = (deckEffects[deckLetter] && deckEffects[deckLetter].state) || {};
            const loopData = (deckLoops[deckLetter] && deckLoops[deckLetter].state) || {};
            const cueData = (deckCues[deckLetter] && deckCues[deckLetter].state) || {};
            const stemsData = (deckStems[deckLetter] && deckStems[deckLetter].state) || {};
            
            // Calculate remaining time
            let remaining = "-";
            if (trackLength > 0 && elapsedTime >= 0) {
                const remainingSecs = trackLength - elapsedTime;
                remaining = remainingSecs > 0 ? formatTime(remainingSecs) : "00:00";
            }
            
            // Convert tempo multiplier to BPM offset
            let tempoOffset = "-";
            if (tempo && typeof tempo === "number" && masterBpm) {
                const offsetPercent = ((tempo - 1) * 100).toFixed(1);
                tempoOffset = offsetPercent > 0 ? `+${offsetPercent}%` : `${offsetPercent}%`;
            }
            
            const playing = asBool(state.isPlaying);
            const synced = asBool(state.isSynced);
            const keyLock = asBool(state.isKeyLockOn);
            // Deck is loaded if it has any state data at all (not just empty title/artist)
            const loaded = Object.keys(state).length > 0;

            const rawDeckType = pickFirst(state, [
                "deckType",
                "deck_type",
                "type",
                "contentType",
                "content_type",
                "trackType",
                "track_type"
            ]);
            const activeSlot = pickFirst(state, ["activeSlot", "active_slot", "slot", "currentSlot"]);
            const stemCount = pickFirst(state, ["stemCount", "stem_count", "stems", "stemSlots"]);
            const remixCount = pickFirst(state, ["remixCount", "remix_count", "remixSlots"]);
            const hasDeckTypeInfo = rawDeckType !== undefined || activeSlot !== undefined || stemCount !== undefined || remixCount !== undefined;
            const deckTypeLabel = hasDeckTypeInfo
                ? formatDeckType(rawDeckType, activeSlot, stemCount, remixCount)
                : "-";

            const deckClass = loaded ? "deck-hud" : "deck-hud inactive";
            return `
                <div class="${deckClass}">
                    <div class="deck-top">
                        <div class="deck-name">Deck ${deckLetter}</div>
                        <div class="deck-flags">
                            <span class="deck-flag ${loaded ? "on" : ""}">LOAD</span>
                            <span class="deck-flag ${playing ? "on" : ""}">PLAY</span>
                            <span class="deck-flag ${synced ? "on" : ""}">SYNC</span>
                            <span class="deck-flag ${keyLock ? "on" : ""}">🔐KEY</span>
                            <span class="deck-flag ${isMaster ? "on" : ""}">MASTER</span>
                        </div>
                    </div>
                    <div class="deck-track">
                        <div class="deck-title">${escapeHtml(title)}</div>
                        <div class="deck-subtitle">${escapeHtml(artist)}</div>
                    </div>
                    <div class="deck-metrics">
                        <div class="metric"><div class="metric-label">BPM</div><div class="metric-value">${escapeHtml(formatCompactValue(bpm, "-"))}</div></div>
                        <div class="metric"><div class="metric-label">Key</div><div class="metric-value">${escapeHtml(formatCompactValue(keyText, "-"))}</div></div>
                        <div class="metric"><div class="metric-label">Elapsed</div><div class="metric-value">${escapeHtml(formatTime(elapsedTime))}</div></div>
                        <div class="metric"><div class="metric-label">Remaining</div><div class="metric-value">${escapeHtml(remaining)}</div></div>
                        <div class="metric"><div class="metric-label">Tempo</div><div class="metric-value">${escapeHtml(tempoOffset)}</div></div>
                        <div class="metric"><div class="metric-label">SYNC</div><div class="metric-value">${synced ? "ON" : "OFF"}</div></div>
                        <div class="metric"><div class="metric-label">Key Lock</div><div class="metric-value">${keyLock ? "ON" : "OFF"}</div></div>
                        <div class="metric"><div class="metric-label">Deck Type</div><div class="metric-value">${escapeHtml(formatCompactValue(deckTypeLabel, "-"))}</div></div>
                    </div>
                    
                    ${Object.keys(audioData).length > 0 ? `
                    <div style="margin-top: 8px; padding: 8px; background: rgba(255,159,64,0.1); border: 1px solid #3a4656; border-radius: 4px;">
                        <div style="font-size: 9px; color: #ffa940; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; font-weight: 700;">🔊 Audio Controls</div>
                        <div style="font-size: 10px; line-height: 1.6;">
                            ${audioData.volume !== undefined ? renderColoredFader('Volume', audioData.volume) : ''}
                            ${audioData.eq_low !== undefined ? renderColoredFader('EQ Low', audioData.eq_low) : ''}
                            ${audioData.eq_mid !== undefined ? renderColoredFader('EQ Mid', audioData.eq_mid) : ''}
                            ${audioData.eq_high !== undefined ? renderColoredFader('EQ High', audioData.eq_high) : ''}
                        </div>
                    </div>
                    ` : ''}
                    
                    ${Object.keys(effectsData).length > 0 ? `
                    <div style="margin-top: 8px; padding: 6px; background: rgba(102,204,255,0.1); border: 1px solid #3a4656; border-radius: 4px;">
                        <div style="font-size: 9px; color: #66ccff; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; font-weight: 700;">FX</div>
                        <div style="font-size: 10px; color: #99ddff;">
                            ${effectsData.active_effects ? effectsData.active_effects.join(", ") : "None"}
                        </div>
                    </div>
                    ` : ''}
                    
                    ${Object.keys(loopData).length > 0 ? `
                    <div style="margin-top: 8px; padding: 6px; background: ${asBool(loopData.is_looped) ? 'rgba(92,184,92,0.1)' : 'rgba(100,100,100,0.1)'}; border: 1px solid ${asBool(loopData.is_looped) ? '#7cd14d' : '#3a4656'}; border-radius: 4px;">
                        <div style="font-size: 9px; color: ${asBool(loopData.is_looped) ? '#7cd14d' : '#93a0b1'}; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; font-weight: 700;">Loop${asBool(loopData.is_looped) ? ' ON' : ''}</div>
                        <div style="font-size: 10px; color: ${asBool(loopData.is_looped) ? '#9dd14d' : '#c7d1de'};">
                            ${loopData.loop_length ? formatTime(loopData.loop_length) : '-'} 
                            ${loopData.loop_size ? `(${loopData.loop_size}B)` : ''}
                        </div>
                    </div>
                    ` : ''}
                    
                    ${Array.isArray(cueData.cue_points) && cueData.cue_points.length > 0 ? `
                    <div style="margin-top: 8px; padding: 6px; background: rgba(200,180,255,0.1); border: 1px solid #3a4656; border-radius: 4px;">
                        <div style="font-size: 9px; color: #d4b5ff; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; font-weight: 700;">Cues (${cueData.cue_points.length})</div>
                        <div style="font-size: 9px; color: #e0c7ff; display: flex; flex-wrap: wrap; gap: 4px;">
                            ${cueData.cue_points.slice(0, 3).map((c, idx) => `<span style="background: #2d2545; padding: 2px 4px; border-radius: 2px;">#${idx + 1} ${c.name || 'Cue'}</span>`).join('')}
                        </div>
                    </div>
                    ` : ''}
                    
                    ${stemsData.stems && Array.isArray(stemsData.stems) && stemsData.stems.length > 0 ? `
                    <div style="margin-top: 8px; padding: 8px; background: rgba(100,200,255,0.08); border: 1px solid #3a4656; border-radius: 4px;">
                        <div style="font-size: 9px; color: #66ccff; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; font-weight: 700;">🎚️ Stems</div>
                        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;">
                            ${stemsData.stems.map((stem, idx) => {
                                const stemNames = ['Drums', 'Bass', 'Other', 'Vocals'];
                                const volume = stem.volume !== undefined ? stem.volume : 0;
                                const filter = stem.filter !== undefined ? stem.filter : 0.5;
                                const filterOn = !!(stem.filterOn);
                                const volumePct = Math.round(volume * 100);
                                const filterPct = Math.round(Math.abs(filter - 0.5) * 200);
                                const volColor = volume > 0.66 ? '#7cd14d' : volume > 0.33 ? '#ffa940' : '#ff6b6b';
                                const filterType = filter < 0.5 ? 'LP' : filter > 0.5 ? 'HP' : '';
                                return `
                                    <div style="background: #0f141d; border: 1px solid #283140; border-radius: 4px; padding: 6px; text-align: center;">
                                        <div style="font-size: 9px; color: #93a0b1; margin-bottom: 4px; font-weight: 600;">${stemNames[idx]}</div>
                                        <div style="height: 40px; background: #0a0d12; border: 1px solid #1a1f28; border-radius: 2px; overflow: hidden; margin-bottom: 4px; position: relative;">
                                            <div style="position: absolute; bottom: 0; width: 100%; height: ${volumePct}%; background: linear-gradient(180deg, ${volColor} 0%, ${volColor} 100%); transition: height 0.1s;"></div>
                                        </div>
                                        <div style="font-size: 10px; color: ${volColor}; font-weight: 700;">${volumePct}%</div>
                                        ${filterOn ? `<div style="font-size: 8px; color: #ffa940; margin-top: 2px; font-weight: 600;">🎛️ ${filterType}${filterPct}%</div>` : ''}
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                    ` : ''}
                    
                </div>
            `;
        }

        function formatTime(seconds) {
            if (!Number.isFinite(seconds) || seconds < 0) return "-";
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
        }

        function getDeckLabel(deckId) {
            const asNumber = Number(deckId);
            if (Number.isFinite(asNumber)) {
                return String.fromCharCode(65 + asNumber);
            }
            return String(deckId).toUpperCase();
        }

        function pickFirst(obj, keys) {
            if (!obj) return undefined;
            for (const key of keys) {
                if (obj[key] !== undefined && obj[key] !== null && obj[key] !== "") {
                    return obj[key];
                }
            }
            return undefined;
        }

        function asBool(value) {
            if (value === true || value === false) {
                return value;
            }
            if (typeof value === "number") {
                return value !== 0;
            }
            if (typeof value === "string") {
                const normalized = value.trim().toLowerCase();
                if (["1", "true", "on", "yes", "playing", "enabled", "master"].includes(normalized)) {
                    return true;
                }
                if (["0", "false", "off", "no", "stopped", "disabled"].includes(normalized)) {
                    return false;
                }
            }
            return false;
        }

        function boolLabel(value) {
            if (value === undefined || value === null || value === "") {
                return "-";
            }
            return asBool(value) ? "ON" : "OFF";
        }

        function detectMasterDeckIndex(masterState) {
            const candidate = pickFirst(masterState, [
                "master_deck",
                "deck_master",
                "tempo_master_deck",
                "masterDeck",
                "tempoMasterDeck",
                "master",
                "active_deck",
                "current_deck",
                "deck_id",
                "tempo_master",
                "sync_master"
            ]);

            if (candidate === undefined || candidate === null) {
                return -1;
            }

            if (typeof candidate === "number") {
                if (candidate >= 0 && candidate <= 3) return candidate;
                if (candidate >= 1 && candidate <= 4) return candidate - 1;
            }

            const text = String(candidate).trim().toUpperCase();
            if (text === "A") return 0;
            if (text === "B") return 1;
            if (text === "C") return 2;
            if (text === "D") return 3;
            if (text === "1") return 0;
            if (text === "2") return 1;
            if (text === "3") return 2;
            if (text === "4") return 3;

            return -1;
        }

        function formatCompactValue(value, fallback = "-") {
            if (value === undefined || value === null || value === "") {
                return fallback;
            }
            if (typeof value === "boolean") {
                return value ? "ON" : "OFF";
            }
            if (typeof value === "number") {
                return formatNumber(value);
            }
            return String(value);
        }

        function formatDeckType(deckType, activeSlot, stemCount, remixCount) {
            // Determine base deck type
            let baseType = "Track";
            if (deckType !== undefined && deckType !== null) {
                // Handle numeric deck types: 0=Track, 1=Remix, 2=Stem, 3=Live Input
                if (typeof deckType === "number") {
                    if (deckType === 0) baseType = "Track";
                    else if (deckType === 1) baseType = "Remix";
                    else if (deckType === 2) baseType = "Stem";
                    else if (deckType === 3) baseType = "Live Input";
                } else {
                    // Handle string deck types
                    const type = String(deckType).toLowerCase();
                    if (type.includes("stem")) baseType = "Stem";
                    else if (type.includes("remix")) baseType = "Remix";
                    else if (type.includes("live") || type.includes("input")) baseType = "Live Input";
                }
            }

            // Build slot indicator
            let slotIndicator = "";
            if (baseType === "Stem" && stemCount) {
                slotIndicator = ` [${activeSlot || "?"}/${stemCount}]`;
            } else if (baseType === "Remix" && remixCount) {
                slotIndicator = ` [${activeSlot || "?"}/${remixCount}]`;
            } else if ((stemCount && baseType !== "Stem") || (remixCount && baseType !== "Remix")) {
                // Show available slots even if mode isn't explicitly set
                if (stemCount) slotIndicator = ` Stems(${stemCount})`;
                if (remixCount) slotIndicator = ` Remixes(${remixCount})`;
            }

            return baseType + slotIndicator;
        }

        function renderColoredFader(label, value) {
            if (value === undefined || value === null) return '';
            
            // Normalize value to 0-1 range
            let normalized = value;
            if (typeof value === 'string') {
                normalized = parseFloat(value);
            }
            if (!Number.isFinite(normalized)) return '';
            
            // Clamp to 0-1
            normalized = Math.max(0, Math.min(1, normalized));
            const percent = (normalized * 100).toFixed(0);
            
            // Color based on level: red (low) -> yellow (mid) -> green (high)
            let color = '#95de70'; // Green
            let bgColor = 'rgba(149,222,112,0.2)';
            if (normalized < 0.33) {
                color = '#ff7a7a'; // Red
                bgColor = 'rgba(255,122,122,0.2)';
            } else if (normalized < 0.66) {
                color = '#ffa940'; // Orange/Yellow
                bgColor = 'rgba(255,169,64,0.2)';
            }
            
            return `
                <div style="margin-bottom: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                        <span style="font-size: 9px; color: #93a0b1; text-transform: uppercase; letter-spacing: 0.04em;">${label}</span>
                        <span style="font-size: 10px; color: ${color}; font-weight: 600;">${percent}%</span>
                    </div>
                    <div style="width: 100%; height: 16px; background: #0f1318; border: 1px solid #1f2630; border-radius: 2px; overflow: hidden;">
                        <div style="height: 100%; width: ${percent}%; background: linear-gradient(90deg, ${color} 0%, ${color} 100%); box-shadow: inset 0 0 4px rgba(0,0,0,0.5), 0 0 8px ${color}44; transition: width 0.1s ease;"></div>
                    </div>
                </div>
            `;
        }

        function formatMetadataValue(value) {
            if (value === null || value === undefined) return '<em>null</em>';
            if (typeof value === 'boolean') {
                return value
                    ? '<span class="metadata-bool-true">ON</span>'
                    : '<span class="metadata-bool-false">OFF</span>';
            }
            if (typeof value === 'number') {
                return `<span class="metadata-number">${formatNumber(value)}</span>`;
            }
            if (typeof value === 'object') {
                return escapeHtml(JSON.stringify(value, null, 2));
            }
            return escapeHtml(String(value));
        }

        function formatNumber(value) {
            if (!Number.isFinite(value)) {
                return String(value);
            }

            const abs = Math.abs(value);
            if (Number.isInteger(value)) {
                return String(value);
            }

            if (abs >= 1000) {
                return value.toFixed(1);
            }

            if (abs >= 100) {
                return value.toFixed(1);
            }

            if (abs >= 1) {
                return value.toFixed(2);
            }

            return value.toFixed(3);
        }

        function escapeHtml(text) {
            const div = document.createElement("div");
            div.textContent = text;
            return div.innerHTML;
        }

        // Initial fetch
        fetchLogs();
        fetchMetadata();

        // Auto-refresh
        setInterval(() => {
            if (autoRefresh) {
                fetchLogs();
            }
        }, 500);

        setInterval(() => {
            if (autoRefreshMetadata) {
                fetchMetadata();
            }
        }, 500);
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    PORT = 8080
    server = http.server.HTTPServer(("localhost", PORT), DebugLogHandler)
    print(f"\n🧭 Traktor Logger Server")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📍 localhost:{PORT}")
    if QUIET_MODE:
        print(f"🔇 Quiet mode: CLI output suppressed")
    else:
        print(f"📝 Real-time logs appear here + on dashboard")
    print(f"\n🔗 Open browser: http://localhost:{PORT}")
    print(f"\n⚠️  SECURITY:")
    print(f"  • Do NOT log passwords, API keys, tokens, or credentials")
    print(f"  • localhost-only binding (no network exposure)")
    print(f"  • No authentication — local access only")
    print(f"  • Data in memory, plaintext, never encrypted")
    print(
        f"  • Rate limits: {RATE_LIMIT_PER_SECOND} logs/sec, {MAX_LOG_PAYLOAD_SIZE/1024:.0f}KB max per entry"
    )
    print(f"\nPress Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        server.shutdown()
