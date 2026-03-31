# traktor-logger

**Version:** 1.2.0
**Traktor:** 4.x
**Requires:** traktor-logger server (`server.py`) running on localhost:8080

---

## What It Does

Installs a structured logging component and an automatic metadata collection layer into Traktor's QML. Streams live Traktor state to a local HTTP server over JSON and provides a real-time browser dashboard.

- **Manual logging** — `logger.info()`, `.debug()`, `.warn()`, `.error()` from any QML file
- **Deck metadata** — title, artist, BPM, key, elapsed time, loop state, hotcues, stems, sync/play state
- **Master clock** — BPM, beat phase, time signature
- **Channel state** — volume, EQ (hi/mid/lo), filter, FX assignments per channel
- **Browser monitoring** — active item tracking via screen injection (screen-capable controllers only)

---

## Installed Files

| Source (`qml/`)                     | Installed to Traktor `qml/`         | Purpose                                             |
| ----------------------------------- | ----------------------------------- | --------------------------------------------------- |
| `Defines/Logger.qml`                | `Defines/Logger.qml`                | QML logging component                               |
| `Defines/qmldir`                    | `Defines/qmldir`                    | Registers `Logger 1.0` in `Traktor.Defines` module  |
| `CSI/Common/Api/ApiModule.qml`      | `CSI/Common/Api/ApiModule.qml`      | Root metadata component — instantiate in controller |
| `CSI/Common/Api/ApiDeck.qml`        | `CSI/Common/Api/ApiDeck.qml`        | Per-deck state streamer                             |
| `CSI/Common/Api/ApiChannel.qml`     | `CSI/Common/Api/ApiChannel.qml`     | Per-channel mixer state                             |
| `CSI/Common/Api/ApiMasterClock.qml` | `CSI/Common/Api/ApiMasterClock.qml` | Master clock / BPM                                  |
| `CSI/Common/Api/ApiClient.js`       | `CSI/Common/Api/ApiClient.js`       | HTTP POST helper                                    |
| `Screens/Common/ApiBrowser.qml`     | `Screens/Common/ApiBrowser.qml`     | Browser item tracker (screen overlay)               |

---

## Dependencies

- **Python 3.9+** — required to run `server.py`
- **Traktor Pro 4.x** — QML/CSI API required

---

## Compatibility

### Works With

- Any controller after `logger api` injection

### Conflicts With

- Multiple simultaneous mods touching the same controller file — resolve with manual merge

### Not Tested On

- S4MK3, X1MK3, Z1MK2 — may lead to duplicate metadata being sent

---

## Testing Checklist

- [ ] `traktor-mod server start` launches without error
- [ ] Loading a track on Deck A triggers a POST to `http://localhost:8080/updateDeck/A`
- [ ] BPM changes are streamed via `updateMasterClock`
- [ ] Loop size reported as musical notation (`1/4`, `1`, `8`, etc.) not a raw index
- [ ] Channel volume changes trigger `updateChannel`
- [ ] Browser navigation triggers `updateBrowser` (screen-capable controllers only)

---

## See Also

- [traktor-logger README](README.md) — server setup, API endpoint reference
- `traktor-mod logger api` — surgical injection for any controller
- `traktor-mod logger pull` — download/update traktor-logger cache
