# ovos-media-plugin-cli

Generic **command-line playback** plugin for
[ovos-media](https://github.com/OpenVoiceOS/ovos-media) — and the legacy
`ovos-audio` service.

It plays a track by shelling out to a CLI media player. You can point it at **any**
command-line player; if you don't, it auto-detects the best available one for your
platform.

- **Explicit command** — set `command` (e.g. `"mpv --no-terminal"`,
  `"cvlc --play-and-exit"`, `"ffplay -nodisp -autoexit"`); the track URI is appended
  as the final argument.
- **Auto-detect** (default) — when no command is set, the plugin picks the best
  available player via `shutil.which`, per platform: `sox` (`play`) is preferred,
  then `mpg123`/`paplay`/`aplay` on Linux, `afplay` on macOS.

Pause/resume use process signals (`SIGSTOP`/`SIGCONT`); stop terminates the child.

## Install

```bash
pip install ovos-media-plugin-cli
```

`sox` is recommended for the widest format/URL coverage when relying on auto-detect.

## Configuration

New `ovos-media`:

```json
{
  "media": {
    "preferred_audio_services": ["mplayer", "vlc", "cli"],
    "audio_players": {
      "cli": {
        "module": "ovos-media-audio-plugin-cli",
        "aliases": ["Command line", "CLI Player"],
        "active": true,
        "command": "mpv --no-terminal"
      }
    }
  }
}
```

Omit `command` to auto-detect. Legacy `ovos-audio`:

```json
{
  "Audio": {
    "backends": {
      "cli": { "type": "cli", "active": true, "command": "mpv --no-terminal" }
    }
  }
}
```

### Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `command` (alias `play_cmd`) | str | _auto-detect_ | CLI player command; the URI is appended as the last arg. |
| `active` | bool | `true` | Enable/disable this backend instance. |

## Entry points

| Group | Name | Object |
|-------|------|--------|
| `opm.media.audio` | `ovos-media-audio-plugin-cli` | `ovos_media_plugin_cli:CLIAudioService` |
| `mycroft.plugin.audioservice` | `ovos_cli` | `ovos_media_plugin_cli.audio` |
