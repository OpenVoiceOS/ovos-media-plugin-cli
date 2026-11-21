"""Regression test: a track replaced by a newer play() (next, previous, a new
request) must not report an end for the track that replaced it.

play() runs on its own thread per track. A newer play() stops the running
player and starts its own; the older thread used to watch self.process, see
it gone for a moment, and fall through to on_track_end(). That ocp_stop()
then reported END_OF_MEDIA while the NEW track was loaded and stopped it, so
ovos-media skipped a track on every "next".

Real subprocesses, with `sleep` as the player: the uri is the seconds.
"""
import threading
import time
import unittest

from ovos_utils.fakebus import FakeBus
from ovos_utils.ocp import MediaState

from ovos_media_plugin_cli import CLIAudioService


class TestReplacedTrack(unittest.TestCase):

    def setUp(self):
        self.bus = FakeBus()
        self.ends = []
        self.t0 = time.monotonic()
        self.bus.on("ovos.common_play.media.state", self._on_state)
        self.service = CLIAudioService({"command": "sleep"}, bus=self.bus)

    def _on_state(self, message):
        if message.data.get("state") == MediaState.END_OF_MEDIA:
            self.ends.append(time.monotonic() - self.t0)

    def _play(self, seconds):
        self.service._now_playing = f"file://{seconds}"
        thread = threading.Thread(target=self.service.play, daemon=True)
        thread.start()
        return thread

    def test_a_replaced_track_returns_at_once(self):
        """The replaced track's thread must not stay behind watching the new
        track's player: it would end with it (or with a later one) and could
        report that track's end."""
        first = self._play(5)
        time.sleep(0.5)
        second = self._play(3)
        first.join(1.5)
        self.assertFalse(first.is_alive(),
                         "the replaced track's thread is still running, watching the new track")
        self.assertEqual(self.ends, [], "the replaced track reported an end")
        second.join(5)

    def test_next_track_plays_to_its_own_end(self):
        first = self._play(5)
        time.sleep(0.5)
        replaced_at = time.monotonic() - self.t0
        second = self._play(1)
        second.join(5)
        first.join(5)

        self.assertFalse(first.is_alive(), "the replaced track's thread never returned")
        self.assertEqual(len(self.ends), 1, f"ends reported at {self.ends}")
        self.assertGreaterEqual(self.ends[0], replaced_at + 0.9,
                                "an end was reported before the new track had played")

    def test_a_track_that_is_not_replaced_still_ends(self):
        self._play(0.3).join(5)
        self.assertEqual(len(self.ends), 1)


if __name__ == "__main__":
    unittest.main()
