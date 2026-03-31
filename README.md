# Traktor Logger

Version: v1.2.0

**A real-time logging and monitoring solution for Traktor QML modding.** Track application events, controller state, and system behavior in a live browser dashboard without code restarts or log file hunting.

## Why This Exists

When working with Traktor QML mods, understanding application behavior and controller state is essential. This tool provides real-time HTTP-based logging and event monitoring in a browser dashboard — no restarts or log-file hunting.

## Credits

The integrated API layer is based on the original project by Erik Minekus:

https://github.com/ErikMinekus/traktor-api-client

The playlist API layer is based on the work from DJMirror:
https://www.patreon.com/cw/DjMirrorTraktor

Both projects were pivotal in the creation of this solution that integrates both concepts and advances the APIs while providing a ready-made UI.

## API Client Integration

First install the `traktor-mod` script (for manual install instructions see [Manual Installation](#manual-installation-without-traktor-mod)):

- https://github.com/lsmith77/traktor-kontrol-qml
- Setup and usage guide: https://github.com/lsmith77/traktor-kontrol-qml/blob/main/00_HANDBOOK.md

**Two complementary logging approaches**:

- **Manual logs**: Add `logger.info()` to your code for tracking application events and state changes
- **Automatic monitoring**: Enable API integration on at least one connected controller to see live deck/mixer state

**Important**: The server can run immediately, but Live Metadata only appears once API integration is active on a connected controller.

> **Disclaimer:** The server.py Python server and QML files are vibe coded via AI with minimal code review. Use with caution and review scripts before production use.

## Quick Start (traktor-mod workflow)

Use the `traktor-mod` script from the main handbook repo to install and wire the logger package cleanly.

### 1. Install logger package into Traktor QML

```bash
traktor-mod logger pull
traktor-mod --source ~/.traktor-mod/traktor-logger
```

This installs Logger.qml, the qmldir module registration, and all Api components into Traktor's QML.

### 2. Wire ApiModule into a controller

```bash
traktor-mod logger api S8 # use D2 if you have a physical D2
```

`logger api S8` injects `ApiModule {}` into the S8 controller QML. You don't need a physical S8 — see step 2.

### 3. Register S8 in Traktor's Controller Manager

Traktor only loads a controller's QML when that controller is registered. Skip this step if you have a physical S8 or D2 connected.

Adding S8 as a pre-mapped controller (even without the hardware) is enough:

1. Launch Traktor Pro
2. Go to **Preferences** (⌘, on macOS or Ctrl+, on Windows)
3. Select the **Controller Manager** tab
4. Click **Add** → **Pre-Mapped** → **Traktor Kontrol** → **S8**

### 4. Start the logger server

```bash
traktor-mod server start
```

### 5. Open dashboard and test

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

**Windows**: Simply drag the `traktor-logger-main/qml/` folder onto `<qml>` in Explorer — Windows merges the folder contents automatically.

**macOS**: Finder replaces entire folders when you drag them. Use Terminal to overlay files safely:

```sh
cp -R traktor-logger-main/qml/ "<qml>/"
```

This copies all files from `qml/` into `<qml>/`, preserving existing content.

#### Manual file-by-file approach (all platforms)

If you prefer explicit control:

- Copy `traktor-logger-main/qml/Defines/Logger.qml` → `<qml>/Defines/Logger.qml`
- Open `<qml>/Defines/qmldir` (create if missing) and ensure it contains:
  ```
  module Traktor.Defines
  Logger 1.0 Logger.qml
  ```
  If the file already exists, just add `Logger 1.0 Logger.qml` if it's not already there.
- Copy everything inside `traktor-logger-main/qml/CSI/Common/Api/` → `<qml>/CSI/Common/Api/`
- Copy everything inside `traktor-logger-main/qml/Screens/Common/` → `<qml>/Screens/Common/`

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

### HTTP API spec

The server exposes interactive **API documentation** powered by Swagger UI at:

```
http://localhost:8080/docs
```

> **Note**: Swagger UI loads its assets from a CDN (`unpkg.com`), so internet access is required when opening this page. The server itself has no additional dependencies.

The underlying **OpenAPI 3.1 spec** can be downloaded directly at:

```
http://localhost:8080/openapi.yaml
```

Both links are also available in the dashboard header.

---

All methods accept a `message` string and an optional `data` object:

| Method                      | Level        |
| --------------------------- | ------------ |
| `logger.log(msg, [data])`   | info (alias) |
| `logger.info(msg, [data])`  | info         |
| `logger.debug(msg, [data])` | debug        |
| `logger.warn(msg, [data])`  | warn         |
| `logger.error(msg, [data])` | error        |

```qml
logger.info("Mapping loaded")
logger.warn("Experimental feature active", { feature: "custom-knob" })
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

1. **Install the logger package and wire a controller**:

   ```bash
   traktor-mod logger pull
   traktor-mod --source ~/.traktor-mod/traktor-logger
   traktor-mod logger api S8
   ```

> **D2 users**: use `logger api D2` instead. **S8 users**: use `logger api S8`. Both can skip step 3 (no virtual controller registration needed).

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

| Method                                | Sends                                                         |
| ------------------------------------- | ------------------------------------------------------------- |
| `logger.sendDeckState(deckId, state)` | Deck play state, BPM, track info — shown in Live Metadata tab |
| `logger.sendMasterState(state)`       | Master BPM and tempo                                          |
| `logger.sendPlaylistState(state)`     | Playlist name, track count, selected track                    |

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

---

## Examples

Add `Logger { id: logger }` to any controller mapping, then call `logger.info/warn/error/debug` with an optional data object:

```qml
import QtQuick 2.0
import CSI 1.0

Mapping {
    Logger { id: logger }

    Component.onCompleted: {
        logger.info("Mapping loaded")
        logger.warn("Experimental feature active", { feature: "custom-knob" })
        logger.error("Unexpected value", { expected: 1, got: 0 })
        logger.debug("State snapshot", { playing: false, bpm: 120, deck: 1 })
    }
}
```

---

## Troubleshooting

- If dashboard is unreachable, run `traktor-mod server start` (or `python3 ~/.traktor-mod/traktor-logger/server.py`).
- If **Console Logs** is empty, verify Logger is integrated in the active QML path and restart Traktor.
- If **Live Metadata** is empty, enable metadata integration on at least one connected controller (`traktor-mod logger api <controller>`).
- If port `8080` is in use, update `PORT` in `server.py`.

---

## Development Workflow

### Testing from GitHub Branches

To test traktor-logger from a development branch before it's merged to main:

```bash
# Pull a feature branch into the local cache
traktor-mod logger pull --branch feature/xyz
# Install from cache
traktor-mod --source ~/.traktor-mod/traktor-logger
traktor-mod logger api D2
# Open http://localhost:8080 to verify the feature
```

### Rapid Local Development

To iterate on traktor-logger locally without GitHub round-trips:

```bash
# Clone locally
git clone https://github.com/lsmith77/traktor-logger.git ~/dev/traktor-logger

# Install directly from local clone using a symlink
traktor-mod --source ~/dev/traktor-logger --symlink
```

---

## License

See `LICENSE` in this folder.
