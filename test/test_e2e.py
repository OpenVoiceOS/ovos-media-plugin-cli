"""End-to-end tests: drive the real CLI OCP backend through a real
``OCPMediaPlayer`` on a FakeBus via ovoscope's media harness.

The plugin shells out to a CLI player via ``subprocess.Popen``, so
``ovos_media_plugin_cli.subprocess`` is mocked: no real player is launched.
The spawned (mocked) process reports itself as already finished
(``poll()`` -> 0) so the backend's blocking ``play()`` loop returns promptly
instead of waiting on a real child. Everything else is real: the OCP player
routes the play/pause/stop requests to ``CLIAudioService`` exactly as
ovos-media would at runtime. A deterministic ``command`` is configured so
``player_cmd`` never depends on which players happen to be installed.

Requires ``ovoscope[media]`` (pulls ovos-media).
"""
import unittest
from unittest.mock import MagicMock, patch

try:
    from ovoscope import OCPPlayerHarness
    from ovos_utils.ocp import MediaEntry, PlaybackType, PlayerState
    HAVE_HARNESS = True
except Exception:
    HAVE_HARNESS = False

import ovos_media_plugin_cli
from ovos_media_plugin_cli import CLIAudioService

URI = "http://example.com/song.mp3"
# a real, always-present no-op command so player_cmd is deterministic
CONFIG = {"command": "true"}


def _factory(bus):
    """Build the real CLI audio backend for injection into the OCP player."""
    return CLIAudioService(CONFIG, bus)


def _mock_subprocess():
    """A subprocess mock whose spawned process reports itself as finished.

    ``poll()`` returning a non-``None`` value makes ``_is_process_running()``
    False, so the backend's blocking ``play()`` loop exits immediately (the bus
    handler that calls ``play()`` runs synchronously, so a live process would
    deadlock the harness).
    """
    sub = MagicMock()
    sub.Popen.return_value.poll.return_value = 0
    return sub


@unittest.skipUnless(HAVE_HARNESS, "ovoscope[media] not installed")
class TestCLIEndToEnd(unittest.TestCase):
    def test_play_pause_resume_stop_through_ocp(self):
        mock_sub = _mock_subprocess()
        with patch.object(ovos_media_plugin_cli, "subprocess", mock_sub):
            with OCPPlayerHarness(backend_factory=_factory) as h:
                entry = MediaEntry(uri=URI, playback=PlaybackType.AUDIO)

                h.play(entry)
                h.assert_player_state(PlayerState.PLAYING)
                h.assert_now_playing_uri(URI)
                # the real backend actually shelled out via its (mocked) engine
                mock_sub.Popen.assert_called()
                self.assertIn(URI, mock_sub.Popen.call_args[0][0])

                h.pause()
                h.assert_player_state(PlayerState.PAUSED)

                h.resume()
                h.assert_player_state(PlayerState.PLAYING)

                h.stop()
                h.assert_player_state(PlayerState.STOPPED)

    def test_backend_is_the_real_cli_plugin(self):
        with patch.object(ovos_media_plugin_cli, "subprocess", _mock_subprocess()):
            with OCPPlayerHarness(backend_factory=_factory) as h:
                self.assertIsInstance(h.backend, CLIAudioService)
                self.assertEqual(h.backend.player_cmd, "true")
                self.assertIn("file", h.backend.supported_uris())
                self.assertIn("http", h.backend.supported_uris())


if __name__ == "__main__":
    unittest.main()
