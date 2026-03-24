# Traktor Logger

Version: v1.0.0

**A real-time logging and monitoring solution for Traktor QML modding.** Track application events, controller state, and system behavior in a live browser dashboard without code restarts or log file hunting.

## Why This Exists

When working with Traktor QML mods, understanding application behavior and controller state is essential:

- ✅ **This tool**: Real-time HTTP-based logging and event monitoring displayed in a browser dashboard

## Credits

The integrated API layer is based on the original project by Erik Minekus:

https://github.com/ErikMinekus/traktor-api-client

The playlist API layer is based on the work from DJMirror:
https://www.patreon.com/cw/DjMirrorTraktor

Both projects where pivotal in the creation of this solution that integrates both concepts and advances the APIs while providing a ready made UI.

## API Client Integration

First install the `traktor-mod` script from (for manual install instructions see #manual-installation-without-traktor-mod):

- https://github.com/lsmith77/traktor-kontrol-qml
- Setup and usage guide: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/00_HANDBOOK.md

When you install with `logger install`, it automatically:

- Downloads/updates the logger package (including server code)
- Installs Logger.qml for manual logging
- Installs Api modules for automatic metadata collection

**Two complementary logging approaches**:

- **Manual logs**: Add `logger.info()` to your code for tracking application events and state changes
- **Automatic monitoring**: Enable API integration on at least one connected controller to see live deck/mixer state

**Important**: The server can run immediately, but Live Metadata only appears once API integration is active on a connected controller.

> **Disclaimer:** The server.py Python server and QML files are vibe coded via AI with minimal code review. Use with caution and review scripts before production use.

## Quick Start (traktor-mod workflow)

Use the `traktor-mod` script from the main handbook repo to install and wire the logger package cleanly.

### 1. Install logger package into Traktor QML

```bash
traktor-mod logger install
traktor-mod enable-metadata S8 # use D2 if you have a physical D2
```

`enable-metadata S8` wires API integration into the S8 controller QML. You don't need a physical S8 — see step 2.

### 2. Register S8 in Traktor's Controller Manager

Traktor only loads a controller's QML when that controller is registered. Skip this stepif you have a physical S8 or D2 connected.

Adding S8 as a pre-mapped controller (even without the hardware) is enough:

1. Launch Traktor Pro
2. Go to **Preferences** (⌘, on macOS or Ctrl+, on Windows)
3. Select the **Controller Manager** tab
4. Click **Add** → **Pre-Mapped** → **Traktor Kontrol** → **S8**

### 3. Start the logger server

```bash
traktor-mod server start
```

### 4. Open dashboard and test

Open `http://localhost:8080`, restart Traktor, and interact with decks to verify both tabs update.

### Relevant install documentation (handbook)

- Handbook index: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/00_HANDBOOK.md
- Install / backup / restore workflow: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/01_BASICS.md#install--backup--restore-the-safe-workflow
- Troubleshooting logger flow: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/04_TROUBLESHOOTING.md#technique-4-advanced-debugging-with-http-logger-structured-logging

---

## Manual Installation (without traktor-mod)

If you prefer not to use the `traktor-mod` script, you can install the logger by hand.

**Traktor's QML folder** (referenced as `<qml>` below):

- **Windows**: `C:\Program Files\Native Instruments\Traktor Pro 4\Resources64\qml`
- **macOS**: `/Applications/Native Instruments/Traktor Pro 4/Traktor Pro 4.app/Contents/Resources/qml`
  (right-click the app → Show Package Contents → Contents/Resources/qml)

### 1. Download the logger package

Download and extract **https://github.com/lsmith77/traktor-logger/archive/refs/heads/main.zip** — you'll get a folder like `traktor-logger-main`.

### 2. Copy files into Traktor's QML folder

#### Logger.qml

Copy `traktor-logger-main/qml/Logger.qml` to `<qml>/Defines/Logger.qml`, creating the `Defines/` folder if needed.

Open `<qml>/Defines/qmldir` in a text editor (create if it doesn't exist):

- If creating fresh, paste:
  ```
  module Traktor.Defines
  Logger 1.0 Logger.qml
  ```
- If the file already exists but has no line starting with `Logger`, add:
  ```
  Logger 1.0 Logger.qml
  ```

#### Api modules

Copy everything inside `traktor-logger-main/qml/CSI/Common/Api/` to `<qml>/CSI/Common/Api/`, creating the `Api/` folder if needed.

#### Screens modules

Copy everything inside `traktor-logger-main/qml/Screens/Common/` to `<qml>/Screens/Common/`, creating the `Common/` folder if needed. Also copy `traktor-logger-main/qml/CSI/Common/Api/ApiClient.js` to `<qml>/Screens/Common/ApiClient.js`.

> **macOS**: Dragging a folder onto an existing folder in Finder replaces it entirely. Use Terminal to overlay files safely:
> ```sh
> cp -R traktor-logger-main/qml/Screens/Common/ "<qml>/Screens/Common/"
> ```

Restart Traktor. The logger is now available via `import Traktor.Defines 1.0` in any QML file.

### 3. Enable metadata collection (optional)

Metadata lets the logger automatically report deck state, tempo, channel info, and browser activity.

#### Wire ApiModule into a controller

The recommended approach is to use S8 — you can register it as a virtual controller in Traktor without physical hardware. If you have a D2, use D2 instead (it's already registered, no extra step needed).

1. Open `<qml>/CSI/S8/S8.qml` in a text editor (or `D2/D2.qml` if you have a D2).

2. Add this line immediately after the last `import`:

   ```qml
   import "../Common/Api"
   ```

   Skip if the file already contains `Common/Api`.

3. Find the `Mapping {` line and add `ApiModule {}` on the very next line:

   ```qml
   Mapping {
     // Automatic metadata collection
     ApiModule {}
   ```

   Skip if the file already contains `ApiModule`.

4. Save the file.

5. Register S8 in Traktor's Controller Manager (skip if you used D2 or already have a physical S8):
   1. Launch Traktor Pro
   2. Go to **Preferences** (⌘, on macOS or Ctrl+, on Windows)
   3. Select the **Controller Manager** tab
   4. Click **Add** → **Pre-Mapped** → **Traktor Kontrol** → **S8**

#### Enable browser monitoring

S8 and D2 share the same screen file (`Screens/S8/Views/Screen.qml`), which is instantiated twice (left + right). Gate `ApiBrowser` with `isLeftScreen` to avoid duplicate posts.

1. Open `<qml>/Screens/S8/Views/Screen.qml` (D2 has no separate screen folder — it uses this same file).

2. Add this import after the last `import` line:
   ```qml
   import "../../Common" as LoggerScreens
   ```

3. Add this as the first child of the root element (the first `{` after the imports):
   ```qml
   LoggerScreens.ApiBrowser { active: isLeftScreen }
   ```

4. Save the file.

Restart Traktor, then open the logger dashboard at `http://localhost:8080`.

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
- **Browser/playlist state**: Current browser path, selected playlist, selected row/track — requires a controller with a display (S4MK3, S8, D2); not available on screen-less controllers (X1, Z1, F1, etc.)

#### Enable via traktor-mod

1. **Install the logger and wire a controller**:

   ```bash
   traktor-mod logger install
   traktor-mod enable-metadata S8
   ```

   > **D2 users**: use `enable-metadata D2` — no need to add a virtual S8.
   > **S8 users**: use `enable-metadata S8` — no need to add a pre-mapped S8 in step 2.

2. **Register S8 in Traktor** (skip if you used D2 or have a physical S8):
   - Traktor: **Preferences** (⌘, / Ctrl+,) → **Controller Manager** → **Add** → **Pre-Mapped** → **Traktor Kontrol** → **S8**

3. **Start the server**:

   ```bash
   traktor-mod server start
   ```

4. **View the dashboard**: Open http://localhost:8080 → **📊 Live Metadata** or **🎵 Browser** tab

**Notes**:

- If only Logger is installed and no metadata integration is enabled, Live Metadata remains empty.

#### View Automatic Metadata

1. **Enable metadata integration** for your active controller(s)
2. **Start the server**: `traktor-mod server start`
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

### Dashboard Tabs

The browser dashboard has **three tabs**:

- **📝 Console Logs** — All `logger.log()`, `logger.info()`, etc. messages for event tracking
- **📊 Live Metadata** — Real-time state of decks, master clock, mixer, and channels
- **🎵 Browser** — Current browser path and a windowed list of items around the selected row

All tabs auto-refresh every 500ms when enabled.

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

See `examples/` for quick snippets and monitoring patterns, including browser/playlist telemetry via `browser-playlist-monitoring.qml`.

---

## Troubleshooting

- If dashboard is unreachable, run `traktor-mod server start` (or `python3 ~/.traktor-mod/traktor-logger/server.py`).
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
./scripts/traktor-mod logger install --branch feature/xyz
./scripts/traktor-mod enable-metadata D2
# Open http://localhost:8080 to verify the feature
```

### Rapid Local Development

To iterate on traktor-logger locally without GitHub round-trips:

```bash
# Clone locally
git clone https://github.com/lsmith77/traktor-logger.git ~/dev/traktor-logger

# Install from local repo
./scripts/traktor-mod logger install --local ~/dev/traktor-logger

# Edit files in ~/dev/traktor-logger/
# Reinstall (instant):
./scripts/traktor-mod logger install --local ~/dev/traktor-logger
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
