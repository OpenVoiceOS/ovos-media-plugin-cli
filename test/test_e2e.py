"""End-to-end tests: drive the real CLI OCP backend through a real
``OCPMediaPlayer`` on a FakeBus via ovoscope's media harness, using a real
CLI player (``ffplay``) against a short, real wav file.

A note on what this harness *can't* observe for this plugin: the CLI
backend's ``play()`` is a blocking call by design (it owns the subprocess
wait loop; production runs it on its own thread). Tracing confirmed
``OCPPlayerHarness`` dispatches bus messages through a single
"ocp-dispatcher" worker thread, and ``adapter.play(uri)`` - including the
backend's full blocking wait loop - runs synchronously *on that worker*
before ``OCPMediaPlayer.play()``'s own trailing ``set_player_state(PLAYING)``
executes. Because the dispatcher is single-threaded, a `pause`/`resume`/
`stop` bus message queued *while* that worker is still inside the blocking
`play()` call is not processed until `play()` returns - so a genuine
mid-playback PAUSED round trip through the full bus is not observable here;
that is a pre-existing ovos-media/harness interaction specific to a
blocking-style backend, unrelated to the natural-end fix under test.

What *is* reliably observable, and is what natural-end-of-media needs to
prove: once the real ffplay process exits on its own (no stop() ever
called), MediaState reaches END_OF_MEDIA and the backend's own bookkeeping
(``_is_playing``, ``_now_playing``) settles correctly. Pause/resume of the
real subprocess is additionally verified directly against the backend
(SIGSTOP/SIGCONT hitting the actual ffplay process), since that path does
not depend on the dispatcher queue.

The player command is real ``ffplay`` (``-nodisp -autoexit``, pointed at
``SDL_AUDIODRIVER=dummy`` so no sound card is required) playing a short
real wav generated with the stdlib ``wave`` module, so playback takes real
wall-clock time and a natural end genuinely happens - matching the
technique in ``ovos-media-plugin-ffplay``'s own natural-end regression
test.

Requires ``ovoscope[media]`` (pulls ovos-media) and the ``ffplay`` binary.
"""
import os
import shutil
import tempfile
import time
import unittest
import wave

try:
    from ovoscope import OCPPlayerHarness
    from ovos_utils.ocp import MediaEntry, MediaState, PlaybackType, PlayerState
    HAVE_HARNESS = True
except Exception:
    HAVE_HARNESS = False

from ovos_media_plugin_cli import CLIAudioService

HAVE_FFPLAY = shutil.which("ffplay") is not None


def _make_wav(path: str, duration: float, rate: int = 8000) -> None:
    n_frames = int(duration * rate)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * n_frames)


def _factory(bus):
    """Build the real CLI audio backend, configured to shell out to a real
    ffplay against a dummy (headless-safe) audio backend."""
    return CLIAudioService(
        {"command": "ffplay -nodisp -autoexit -loglevel quiet"}, bus)


class _EnvPatch:
    """Set an environment variable for the duration of a `with` block."""

    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value

    def __enter__(self):
        self._had_previous = self.key in os.environ
        self._previous = os.environ.get(self.key)
        os.environ[self.key] = self.value
        return self

    def __exit__(self, *exc):
        if self._had_previous:
            os.environ[self.key] = self._previous
        else:
            os.environ.pop(self.key, None)


@unittest.skip(
    "predates the MediaBackend v2 template: OCPPlayerHarness/OCPMediaPlayer "
    "still drive the v1 contract (ocp_start/ocp_stop, _now_playing, "
    "MediaState bus messages) this plugin no longer emits. Needs a v2-aware "
    "ovoscope harness release before re-enabling."
)
@unittest.skipUnless(HAVE_HARNESS, "ovoscope[media] not installed")
@unittest.skipUnless(HAVE_FFPLAY, "ffplay binary not installed")
class TestCLIEndToEnd(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.wav_path = os.path.join(self._tmpdir.name, "tone.wav")
        self._env_patch = _EnvPatch("SDL_AUDIODRIVER", "dummy")
        self._env_patch.__enter__()

    def tearDown(self):
        self._env_patch.__exit__(None, None, None)
        self._tmpdir.cleanup()

    def test_play_through_ocp_shells_out_to_real_player(self):
        _make_wav(self.wav_path, duration=2.0)
        uri = f"file://{self.wav_path}"

        with OCPPlayerHarness(backend_factory=_factory) as h:
            entry = MediaEntry(uri=uri, playback=PlaybackType.AUDIO)
            h.play(entry)

            # give the dispatcher worker time to reach backend.play() and
            # actually spawn the real ffplay process
            deadline = time.time() + 5
            while time.time() < deadline and not (h.backend and h.backend.process):
                time.sleep(0.02)

            self.assertIsNotNone(h.backend.process, "ffplay was never spawned")
            self.assertTrue(h.backend._is_playing)
            self.assertEqual(h.player.now_playing.uri, uri)

            # real pause/resume against the real subprocess (SIGSTOP/SIGCONT) -
            # exercised directly on the backend since a bus round trip queued
            # behind the still-running play() call on ovoscope's single
            # dispatcher worker would not be processed until play() returns
            # (see module docstring)
            h.backend.pause()
            self.assertTrue(h.backend._paused)

            h.backend.resume()
            self.assertFalse(h.backend._paused)

            self.assertTrue(h.backend.stop())
            self.assertFalse(h.backend._is_playing)

    def test_natural_track_end_emits_end_of_media(self):
        """A track that ends naturally (ffplay exits on its own once the
        short wav finishes, no stop() ever called) must report
        MediaState.END_OF_MEDIA, exactly like an explicit stop does."""
        _make_wav(self.wav_path, duration=1.0)
        uri = f"file://{self.wav_path}"

        with OCPPlayerHarness(backend_factory=_factory) as h:
            entry = MediaEntry(uri=uri, playback=PlaybackType.AUDIO)
            h.play(entry)

            deadline = time.time() + 10
            while time.time() < deadline and h.player.media_state != MediaState.END_OF_MEDIA:
                time.sleep(0.05)

            h.assert_media_state(MediaState.END_OF_MEDIA)
            self.assertIsNone(h.backend._now_playing,
                              "backend did not clear _now_playing on natural end")
            self.assertFalse(h.backend._is_playing)

    def test_backend_is_the_real_cli_plugin(self):
        with OCPPlayerHarness(backend_factory=_factory) as h:
            self.assertIsInstance(h.backend, CLIAudioService)
            self.assertEqual(h.backend.player_cmd,
                             "ffplay -nodisp -autoexit -loglevel quiet")
            self.assertIn("file", h.backend.supported_uris())
            self.assertIn("http", h.backend.supported_uris())


if __name__ == "__main__":
    unittest.main()
