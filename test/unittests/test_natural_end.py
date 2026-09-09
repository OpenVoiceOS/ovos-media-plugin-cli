"""Regression test: a track that ends naturally (the CLI player process
exits on its own, the play() loop falls through to on_track_end() with no
stop() ever called) must report MediaState.END_OF_MEDIA /
PlayerState.STOPPED on the bus, exactly like an explicit stop does.
"""
import unittest
from unittest.mock import MagicMock

from ovos_utils.fakebus import FakeBus
from ovos_utils.ocp import MediaState, PlayerState

from ovos_media_plugin_cli import CLIAudioService


class TestNaturalEndOfMedia(unittest.TestCase):

    def _service(self):
        bus = FakeBus()
        states = []
        player_states = []
        bus.on("ovos.common_play.media.state",
               lambda msg: states.append(msg.data.get("state")))
        bus.on("ovos.common_play.player.state",
               lambda msg: player_states.append(msg.data.get("state")))
        service = CLIAudioService({}, bus=bus)
        service._now_playing = "file:///tmp/track.wav"
        service._is_playing = True
        return service, states, player_states

    def test_natural_track_end_emits_end_of_media(self):
        service, states, player_states = self._service()

        # simulate the play() loop falling through because the process
        # exited on its own, with no stop() ever called by us
        service.on_track_end()

        self.assertIn(MediaState.END_OF_MEDIA, states,
                       f"natural end-of-media never emitted END_OF_MEDIA; saw: {states}")
        self.assertIn(PlayerState.STOPPED, player_states,
                       f"natural end-of-media never emitted PlayerState.STOPPED; saw: {player_states}")

    def test_on_track_end_does_not_deadlock_stop(self):
        # ocp_stop() calls self.stop() internally; must not hang since
        # _is_playing is already False by the time it is invoked.
        service, _, _ = self._service()
        service.on_track_end()
        self.assertFalse(service._is_playing)


if __name__ == "__main__":
    unittest.main()
