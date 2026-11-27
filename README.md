# ovos-media-plugin-cli

Generic **command-line playback** plugin for
[ovos-media](https://github.com/OpenVoiceOS/ovos-media), and for the legacy
`ovos-audio` service.

The plugin plays a track by running a command-line media player as a
subprocess. Point it at any player command, or let it auto-detect the best
available one for your platform.

- **Explicit command**: set `command` (for example `"mpv --no-terminal"`,
  `"cvlc --play-and-exit"`, `"ffplay -nodisp -autoexit"`). The plugin appends
  the track URI as the final argument.
- **Auto-detect** (default): when you do not set a command, the plugin picks
  the best available player for your platform through `shutil.which`. It
  prefers `sox` (`play`), then tries `mpg123`, `paplay`, or `aplay` on Linux,
  and `afplay` on macOS.

Pause and resume use process signals (`SIGSTOP`/`SIGCONT`). Stop terminates
the child process.

## Install

```bash
pip install ovos-media-plugin-cli
```

Install `sox` too. It gives the widest format and URL coverage when the
plugin auto-detects a player.

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
| `command` (alias `play_cmd`) | str | _auto-detect_ | CLI player command. The plugin appends the URI as the last argument. |
| `active` | bool | `true` | Enable or disable this backend instance. |

## Entry points

| Group | Name | Object |
|-------|------|--------|
| `opm.media.audio` | `ovos-media-audio-plugin-cli` | `ovos_media_plugin_cli:CLIAudioService` |
| `mycroft.plugin.audioservice` | `ovos_cli` | `ovos_media_plugin_cli.audio` |

## Related projects

- [ovos-media](https://github.com/OpenVoiceOS/ovos-media): the media service this plugin's `opm.media.audio` entry point serves.
- [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager): defines the `MediaBackend`/`AudioPlayerBackend` and legacy `AudioBackend` base classes this plugin implements.
- [ovos-media-plugin-mpv](https://github.com/OpenVoiceOS/ovos-media-plugin-mpv), [ovos-media-plugin-vlc](https://github.com/OpenVoiceOS/ovos-media-plugin-vlc), [ovos-media-plugin-mplayer](https://github.com/OpenVoiceOS/ovos-media-plugin-mplayer), and [ovos-media-plugin-ffplay](https://github.com/OpenVoiceOS/ovos-media-plugin-ffplay): sibling audio-playback plugins for one specific player, instead of the generic CLI command this plugin wraps.

## License

Apache-2.0, see [LICENSE](LICENSE).
