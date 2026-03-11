# Traktor Logger

Version: v0.1.0

**A real-time logging and monitoring solution for Traktor QML modding.** Track application events, controller state, and system behavior in a live browser dashboard without code restarts or log file hunting.

## Why This Exists

When working with Traktor QML mods, understanding application behavior and controller state is essential:

- ✅ **This tool**: Real-time HTTP-based logging and event monitoring displayed in a browser dashboard

## API Client Lineage and Integration

`traktor-logger` now includes the API client functionality directly, so you do not need to install a separate `traktor-api-client` package.

**Lineage note**: the integrated API layer is based on the original project by Erik Minekus:

- https://github.com/ErikMinekus/traktor-api-client

**This package combines two capabilities for complete logging and monitoring**:

1. **traktor-logger** (this project): Manual HTTP logging via `Logger` QML component
2. **traktor-api-client lineage** (Erik Minekus): Automatic metadata collection from controllers

**The result**: Install once, get both manual event logs AND automatic real-time state tracking (deck status, mixer levels, BPM, etc.) flowing to the same dashboard.

First install the `install-traktor-mod` script from:

- https://github.com/lsmith77/traktor-kontrol-qml
- Setup and usage guide: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/00_HANDBOOK.md

When you install with `logger install`, it automatically:

- Installs Logger.qml for manual logging
- Installs Api modules for automatic metadata collection
- Downloads/updates the logger package (including server code)

**Two complementary logging approaches**:

- **Manual logs**: Add `logger.info()` to your code for tracking application events and state changes
- **Automatic monitoring**: Enable API integration on at least one connected controller to see live deck/mixer state

**Important**: The server can run immediately, but Live Metadata only appears once API integration is active on a connected controller.

## Quick Start (install-traktor-mod workflow)

Use the `install-traktor-mod` script from the main handbook repo to install and wire the logger package cleanly.

### 1. Install logger package into Traktor QML

```bash
install-traktor-mod logger install
```

This installs:

- `Logger.qml` for manual `logger.info/debug/warn/error` output
- API modules for metadata transport
- server files under `~/.traktor-mod/traktor-logger`

### 2. Start the logger server

```bash
install-traktor-mod server start
```

### 3. Open dashboard

Open `http://localhost:8080`.

### 4. Enable data flow in Traktor

- **Console Logs tab**: Add `Logger` usage in the QML modules you want to monitor
- **Live Metadata tab**: Enable API integration on at least one connected controller (for example via `enable-metadata`)

Without integration/mapping, the server runs but receives no events.

### 5. Restart Traktor and test

Interact with decks/controls and verify both tabs update.

### Relevant install documentation (handbook)

- Handbook index: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/00_HANDBOOK.md
- Install / backup / restore workflow: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/01_BASICS.md#install--backup--restore-the-safe-workflow
- Troubleshooting logger flow: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/04_TROUBLESHOOTING.md#technique-4-advanced-debugging-with-http-logger-structured-logging

---

## ⚠️ Security Considerations

**This is a development logging and monitoring tool. It exposes live data from Traktor for inspection.**

### Important Warnings

1. **Do NOT log sensitive credentials**: Passwords, API keys, tokens, or authentication data will appear in plaintext in the browser dashboard and terminal. Never log them.

2. **Local-only by default**:
   - Server binds to `localhost:8080` only (no network exposure by default)
   - If using SSH tunneling or port forwarding, ensure your network is trusted
   - Anyone with localhost access can view all logs and metadata

3. **No authentication**: The dashboard has no password protection. On shared machines, this tool is not appropriate for multi-user systems.

4. **Plaintext storage**:
   - Logs and metadata stored in memory (100 logs max; lost on shutdown)
   - Metadata objects persist indefinitely until server restart
   - Data is never encrypted

### Best Practices

- **Local use only** on your personal dev machine
- **Audit your logs**: Verify you're not logging or monitoring sensitive data
- **Restart regularly**: Clear accumulated logs and reset state
- **Firewall protection**: Don't expose `:8080` to untrusted networks

---

## Features

| Feature                 | Benefit                                   |
| ----------------------- | ----------------------------------------- |
| **Real-time dashboard** | See logs instantly; no restart needed     |
| **4 log levels**        | debug, info, warn, error (color-coded)    |
| **JSON data support**   | Log complex objects, not just strings     |
| **Auto-refresh**        | Dashboard updates automatically (500ms)   |
| **Filtering**           | Show only errors, warnings, etc.          |
| **Browser-based**       | Works on any device on your local network |
| **Console output**      | Logs appear colored in terminal too       |
| **No dependencies**     | Python 3 built-in; no npm install needed  |

---

## API Reference

### `logger.log(message, [data])`

Send an info-level message.

```qml
logger.log("User clicked button", { button: "SYNC", deck: 1 })
```

### `logger.info(message, [data])`

Send an info-level message (same as `log`).

```qml
logger.info("App initialized")
```

### `logger.debug(message, [data])`

Send a debug-level message (useful for detailed state).

```qml
logger.debug("Current tempo", { bpm: 120.5 })
```

### `logger.warn(message, [data])`

Send a warning-level message.

```qml
logger.warn("Feature not supported", { controller: "Z1MK2" })
```

### `logger.error(message, [data])`

Send an error-level message.

```qml
logger.error("Failed to sync", { reason: "Network timeout" })
```

---

## Live Metadata Monitoring (Deck State, BPM, Playlist Info)

Beyond console logs, the logger can also track and display **live metadata**—real-time state observations from your controller like play states, BPM, track info, and more.

### Automatic Metadata Collection

Enable metadata API integration on at least one connected controller to automatically track and send:

- **Deck state**: Track loaded, play/pause, tempo, key, sync, BPM
- **Mixer levels**: Channel volumes, crossfader position
- **Clock data**: Beat position, phase, master tempo

#### Enable via install-traktor-mod

1. **Install the logger first**:

   ```bash
   ./install-traktor-mod --install-logger-only
   ```

2. **Enable controller metadata integration**:

```bash
install-traktor-mod --enable-metadata=D2,S8,X1MK3
```

3. **Start the server**:

   ```bash
   install-traktor-mod --start-server
   ```

`install-traktor-mod` downloads/updates the logger package and can launch the server directly with this flag.

4. **View the dashboard**: Open http://localhost:8080 → **📊 Live Metadata** tab

**Notes**:

- Metadata requires at least one integrated controller that is connected and active.
- If only Logger is installed and no metadata integration is enabled, Live Metadata remains empty.

#### View Automatic Metadata

1. **Enable metadata integration** for your active controller(s)
2. **Start the server**: `install-traktor-mod --start-server`
3. **Launch Traktor** and interact with decks
4. **Open dashboard**: http://localhost:8080 → **📊 Live Metadata** tab

You'll see real-time updates of deck state, mixer levels, and clock without modifying any QML files.

#### ⚠️ Important: Live Metadata Shows Only Events After Server Start

**The Live Metadata view is based on consuming streams of messages from the controller.** It only displays state changes that occur **after the server is started and the UI is loaded**.

- If a track is already loaded and playing in Traktor _before_ the server starts, the Live Metadata view will **not** show it initially.
- Once you interact with the decks (play, pause, load a new track, adjust tempo, etc.) _after_ the server is running, those changes **will** appear in the dashboard.
- Metadata is accumulated only from that point forward and persists until the server restarts.

**Example scenario**:

1. Traktor is running with a track loaded and playing
2. You start the logger server
3. You open the dashboard
4. The Live Metadata tab appears empty (no deck state yet)
5. You pause the track → the pause event is captured and shown
6. You load a new track → the new track state is captured and shown
7. But the original track state before server start is not known to the UI

This is by design: the logger monitors Traktor's message stream for new events, not a snapshot of the current state at connection time.

### Manual Metadata API

If automatic collection doesn't suit your needs, you can manually send metadata from your QML code:

### Metadata API

The Logger provides methods to send different types of metadata:

### `logger.sendDeckState(deckId, state)`

Send deck state (play, BPM, track info, etc). Shown in dashboard under "Live Metadata" tab.

```qml
Logger { id: logger }

// Track deck state and send periodically
Timer {
    interval: 1000
    repeat: true
    running: deck1IsPlaying

    onTriggered: {
        logger.sendDeckState(0, {  // deckId = 0 (Deck A)
            title: currentTrack.title,
            artist: currentTrack.artist,
            bpm: 120.5,
            tempo: 100,
            playing: true,
            elapsed: "1:23",
            synced: false
        })
    }
}
```

### `logger.sendMasterState(state)`

Send master BPM, tempo, and other master properties.

```qml
Logger { id: logger }

AppProperty { id: masterBpm; path: "app.traktor.master.bpm.base_bpm" }

onMasterBpmChanged: {
    logger.sendMasterState({
        bpm: masterBpm.value,
        tempo: 100
    })
}
```

### `logger.sendPlaylistState(state)`

Send playlist info (selected track, track count, playlist name, etc).

```qml
Logger { id: logger }

logger.sendPlaylistState({
    playlist: "My Favorites",
    track_count: 150,
    selected_track: "My Song",
    selected_index: 42
})
```

### Dashboard: Logs vs Metadata Tabs

The browser dashboard now has **two tabs**:

- **📝 Console Logs** — All `logger.log()`, `logger.info()`, etc. messages for event tracking
- **📊 Live Metadata** — Real-time state of decks, master clock, playlists, and controller

Both auto-refresh every 500ms when enabled. You can disable auto-refresh for either tab independently.

### Fullscreen Mode

On the **Live Metadata** tab, click the **⛶ Fullscreen** button to enter fullscreen mode for an immersive HUD view.

**Exit fullscreen with either**:

- Click the **✕** close button in the top-right corner
- Press **ESC** key

**Benefits**:

- Manual logs for tracking application events and state changes
- Live metadata for monitoring system state in real-time
- No extra UI instrumentation needed to inspect current values

---

## Advanced Metadata Endpoints

The server accepts several optional metadata endpoints for extended monitoring. These are **not used by default** but can be integrated by QML code to send additional telemetry:

### POST `/updateDeckAudio/<deck>`

Send deck audio control state (volume, EQ, filter).

**Expected data**:

```json
{
  "volume": 0.75,
  "eq_low": 0.0,
  "eq_mid": 0.2,
  "eq_high": -0.1,
  "filter": 0.5
}
```

**Usage**: Send from ApiDeck module or custom QML signal handler.

### POST `/updateDeckEffects/<deck>`

Send active effects for a deck.

**Expected data**:

```json
{
  "active": ["reverb", "delay"],
  "reverb_amount": 0.6,
  "delay_time": 500,
  "delay_feedback": 0.4
}
```

### POST `/updateDeckLoop/<deck>`

Send loop state and sizing.

**Expected data**:

```json
{
  "active": true,
  "length": 8.0,
  "size": "8 Beat",
  "in_pos": 10.5,
  "out_pos": 18.5
}
```

### POST `/updateDeckCues/<deck>`

Send cue point information.

**Expected data**:

```json
{
  "cues": [
    { "name": "Intro", "pos": 5.2, "type": "cue" },
    { "name": "Build", "pos": 32.0, "type": "cue" },
    { "name": "Chorus", "pos": 64.5, "type": "fadeIn" }
  ]
}
```

### POST `/updateMasterAudio`

Send master channel audio control state.

**Expected data**:

```json
{
  "volume": 0.85,
  "crossfader": 0.5,
  "headphone_mix": 0.3,
  "headphone_volume": 0.9
}
```

### POST `/updateBrowser`

Send browser/playlist state (optional telemetry).

**Expected data**:

```json
{
  "playlist": "Favorites",
  "selected_track": "My Song",
  "selected_index": 42,
  "total_tracks": 150
}
```

---

## Examples

See `examples/` for quick snippets and monitoring patterns.

---

## Troubleshooting

- If dashboard is unreachable, run `install-traktor-mod --start-server` (or `python3 ~/.traktor-mod/traktor-logger/server.py`).
- If **Console Logs** is empty, verify Logger is integrated in the active QML path and restart Traktor.
- If **Live Metadata** is empty, enable metadata integration on at least one connected controller (`--enable-metadata=...`).
- If port `8080` is in use, update `PORT` in `server.py`.

---

## Server Behavior Summary

- Binds to `localhost` by default.
- Logs are in-memory (cleared when server restarts).
- Dashboard is served from `server.py` and auto-refreshes.
- Uses HTTP JSON endpoints for log and metadata updates.

---

## Development Workflow

### Testing from GitHub Branches

To test traktor-logger from a development branch before it's merged to main:

```bash
# Test a feature branch
./install-traktor-mod logger install --branch feature/xyz
./install-traktor-mod enable-metadata D2
# Open http://localhost:8080 to verify the feature
```

### Rapid Local Development

To iterate on traktor-logger locally without GitHub round-trips:

```bash
# Clone locally
git clone https://github.com/lsmith77/traktor-logger.git ~/dev/traktor-logger

# Install from local repo
./install-traktor-mod logger install --local ~/dev/traktor-logger

# Edit files in ~/dev/traktor-logger/
# Reinstall (instant):
./install-traktor-mod logger install --local ~/dev/traktor-logger
```

### Full Documentation

For complete development workflows, branch management, and local development patterns:

📖 **[LOGGER_DEVELOPMENT_WORKFLOW.md](../LOGGER_DEVELOPMENT_WORKFLOW.md)** — comprehensive guide with scenarios, troubleshooting, and best practices

📋 **[LOGGER_QUICK_REFERENCE.md](../LOGGER_QUICK_REFERENCE.md)** — command quick reference

---

## Security

Do not log secrets (passwords, tokens, keys, personal data). Dashboard and terminal output are intended for local debugging.

---

## License

See `LICENSE` in this folder.
