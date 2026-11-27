"""Unit tests for the CLI-command backends.

The plugin shells out to a CLI player (``play``/``paplay``/``aplay``/
``mpg123``) via ``subprocess``; nothing is imported from an external audio
library, so the modules import cleanly. The tests assert wiring/contract,
not real playback: both the new ovos-media backend and the legacy ovos-audio
adapter build, expose the right base classes, and the supported URIs + entry
points are declared correctly.
"""
import unittest
from unittest.mock import MagicMock

from ovos_plugin_manager.templates.media import AudioPlayerBackend
from ovos_plugin_manager.templates.audio import AudioBackend

from ovos_media_plugin_cli import CLIAudioService, CLIBaseService
from ovos_media_plugin_cli.audio import CLIOldAudioService, load_service


class TestNewBackend(unittest.TestCase):
    def test_audio_backend_is_audioplayerbackend(self):
        svc = CLIAudioService({}, bus=MagicMock())
        self.assertIsInstance(svc, AudioPlayerBackend)
        self.assertIsInstance(svc, CLIBaseService)

    def test_supported_uris(self):
        svc = CLIAudioService({}, bus=MagicMock())
        uris = svc.supported_uris()
        self.assertIn('file', uris)
        self.assertIn('http', uris)


class TestPlayerCommand(unittest.TestCase):
    """player_cmd: explicit config wins, else platform/shutil.which auto-detect."""

    def test_explicit_command_config_wins(self):
        svc = CLIAudioService({"command": "mpv --no-terminal"}, bus=MagicMock())
        svc.load_track("https://example.com/song.mp3")
        self.assertEqual(svc.player_cmd, "mpv --no-terminal")

    def test_play_cmd_alias(self):
        svc = CLIAudioService({"play_cmd": "cvlc --play-and-exit"}, bus=MagicMock())
        svc.load_track("x.mp3")
        self.assertEqual(svc.player_cmd, "cvlc --play-and-exit")

    def test_autodetect_when_unset(self):
        # with no explicit command, it resolves to *something* (or None if no
        # player is installed) without raising — the auto-detect path runs.
        svc = CLIAudioService({}, bus=MagicMock())
        svc.load_track("x.mp3")
        _ = svc.player_cmd  # must not raise


class TestLegacyAdapter(unittest.TestCase):
    def test_legacy_is_audiobackend(self):
        svc = CLIOldAudioService({}, bus=MagicMock(), name='cli')
        self.assertIsInstance(svc, AudioBackend)
        # reuses the shared subprocess engine/methods
        self.assertIsInstance(svc, CLIBaseService)
        self.assertTrue(hasattr(svc, "play"))
        self.assertTrue(hasattr(svc, "lower_volume"))

    def test_supported_uris(self):
        svc = CLIOldAudioService({}, bus=MagicMock(), name='cli')
        uris = svc.supported_uris()
        self.assertIn('file', uris)
        self.assertIn('http', uris)

    def test_load_service_builds_active_cli_backends(self):
        cfg = {"backends": {
            "mycli": {"type": "cli", "active": True},
            "off": {"type": "cli", "active": False},
            "other": {"type": "vlc", "active": True},
        }}
        services = load_service(cfg, bus=MagicMock())
        self.assertEqual(len(services), 1)
        self.assertIsInstance(services[0], CLIOldAudioService)

    def test_load_service_empty(self):
        self.assertEqual(load_service({"backends": {}}, bus=MagicMock()), [])


class TestEntryPoints(unittest.TestCase):
    """Both the new and legacy entry-point groups must be declared."""

    def test_setup_declares_new_and_legacy_groups(self):
        import os
        here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        with open(os.path.join(here, "pyproject.toml")) as f:
            setup_src = f.read()
        self.assertIn("opm.media.audio", setup_src)
        self.assertIn("mycroft.plugin.audioservice", setup_src)
        self.assertIn("ovos_media_plugin_cli.audio", setup_src)


if __name__ == "__main__":
    unittest.main()
