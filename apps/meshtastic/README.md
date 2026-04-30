# Meshtastic app

LoRa mesh chat + node list for devices with a Meshtastic-compatible LoRa radio (currently T-Deck Plus running tophyGo).

Picocalc has no LoRa hardware, so this app declares `"platforms": ["tdeck"]` in `app.json` and is hidden on picocalc launchers that filter by the platforms field (see picocalc-compat-notes in the tophyGo repo).

## Depends on `ctx.lora`

The app expects the firmware HAL to expose this API on `ctx.lora`:

```python
ctx.lora.send_text(channel: str, text: str) -> bool
ctx.lora.poll() -> list[dict]
    # each dict: {'channel', 'from', 'text', 'rssi', 'snr',
    #             optional 'lat', 'lon', 'short', 'long'}
ctx.lora.set_channel(name: str, psk: str) -> None
```

These match the scaffolded API in tophyGo's `firmware/picoware/core/lora.py`. The raw SX1262 driver there is functional; the Meshtastic protocol wrapper (protobuf + channel PSK + node identity) is a TODO. Until that wrapper lands, `send_text()` raises `NotImplementedError` — this app catches it and surfaces `[Meshtastic layer pending]` in the UI so you can still navigate the app and see the framework without a radio stack.

## UI

| State | Keys |
|---|---|
| Chat (default) | Type to compose. ENTER sends. UP/DOWN scroll history. F1 next channel. F2 node list. F10 settings. ESC exits. |
| Nodes | Sorted by most-recent activity. Color-coded: green = seen in last 5 min, orange = last 30 min, gray = older. F2/ESC returns to chat. |
| Settings | Short/long name, add channel (name + optional PSK hex), GPS-share interval, clear history. |

## Storage

Per-user state lives in `/sd/picoware/data/meshtastic/`:

- `settings.json` — names, channels, PSKs, GPS-share interval
- `history.json` — last 200 messages (ring-buffer trimmed on write)

## GPS position sharing

If `gps_share_interval_s > 0` and `ctx.gps` is available with a valid fix, the app periodically broadcasts a text message `"pos <lat>,<lon>"` on the current channel. Future work: pack position into a Meshtastic `POSITION_APP` portnum packet instead of plain text.

## Known gaps

- Meshtastic protobuf layer not yet implemented in `ctx.lora`. Once done, `send_text` / `poll` stop being stubs.
- No PKI / channel encryption negotiation yet — relies on PSK passed through `set_channel`.
- No DM support (unicast by node id). Broadcast-only on the current channel.
- No ACK / retry handling surfaced in UI.
- `from` is shown as last 4 chars of node id if the node hasn't announced a short name.
