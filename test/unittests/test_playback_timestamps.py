"""The playback timestamp contract for the CLI backends.

``MediaBackend`` gives the two timestamp methods three answers (
ovos-plugin-manager#442):

    None    nothing is playing, so there is no track to be anywhere in
    -1      something is playing but it has no finite duration
    a value milliseconds

This backend pipes to a subprocess CLI player and never learns a duration
from it, so a playing track always reports -1 for length, the same answer a
live stream gets elsewhere: a duration this backend cannot know is not the
same claim as a duration of zero.

``supports_seek`` is also asserted False: ``set_track_position`` is a no-op,
so a consumer must not be told this backend has a seekable timeline.
"""
import unittest
from unittest.mock import MagicMock

from ovos_media_plugin_cli import CLIAudioService, CLIBaseService
from ovos_media_plugin_cli.audio import CLIOldAudioService


class TestNothingPlaying(unittest.TestCase):
    """Stopped is None, and it is not either of the other two answers."""

    def test_position_is_none(self):
        svc = CLIAudioService({}, bus=MagicMock())
        self.assertIsNone(svc.get_track_position())

    def test_length_is_none(self):
        svc = CLIAudioService({}, bus=MagicMock())
        self.assertIsNone(svc.get_track_length())

    def test_neither_is_minus_one(self):
        """-1 would claim a track plays with unknown duration, which a
        stopped player is not."""
        svc = CLIAudioService({}, bus=MagicMock())
        self.assertNotEqual(svc.get_track_position(), -1)
        self.assertNotEqual(svc.get_track_length(), -1)

    def test_neither_is_zero(self):
        """0 is a legitimate position, and a legitimate length is never 0."""
        svc = CLIAudioService({}, bus=MagicMock())
        self.assertNotEqual(svc.get_track_position(), 0)
        self.assertNotEqual(svc.get_track_length(), 0)


class TestATrackIsPlaying(unittest.TestCase):
    """A playing track has a real position but an unknown length."""

    def test_position_is_the_elapsed_time(self):
        svc = CLIAudioService({}, bus=MagicMock())
        svc.ts = 1000.0
        with unittest.mock.patch("ovos_media_plugin_cli.time") as mocked_time:
            mocked_time.time.return_value = 1007.5
            self.assertEqual(svc.get_track_position(), 7500)

    def test_length_is_minus_one(self):
        """The duration can never be known, so it is always -1 while
        something plays, never 0 and never the elapsed position."""
        svc = CLIAudioService({}, bus=MagicMock())
        svc.ts = 1000.0
        self.assertEqual(svc.get_track_length(), -1)

    def test_length_does_not_grow_with_position(self):
        """Length stays -1 for the whole playing state. A progress bar fed
        from both position and length never reads 100% while playing."""
        svc = CLIAudioService({}, bus=MagicMock())
        svc.ts = 1000.0
        with unittest.mock.patch("ovos_media_plugin_cli.time") as mocked_time:
            mocked_time.time.return_value = 1050.0
            position = svc.get_track_position()
            length = svc.get_track_length()
        self.assertNotEqual(length, position)
        self.assertEqual(length, -1)


class TestLegacyAdapterSharesTheContract(unittest.TestCase):
    """CLIOldAudioService reuses CLIBaseService's timestamp methods."""

    def test_position_is_none_when_stopped(self):
        svc = CLIOldAudioService({}, bus=MagicMock(), name='cli')
        self.assertIsNone(svc.get_track_position())

    def test_length_is_none_when_stopped(self):
        svc = CLIOldAudioService({}, bus=MagicMock(), name='cli')
        self.assertIsNone(svc.get_track_length())

    def test_length_is_minus_one_while_playing(self):
        svc = CLIOldAudioService({}, bus=MagicMock(), name='cli')
        svc.ts = 1000.0
        self.assertEqual(svc.get_track_length(), -1)


class TestSupportsSeek(unittest.TestCase):
    """set_track_position is a no-op, so this backend cannot seek."""

    def test_new_backend_does_not_support_seek(self):
        svc = CLIAudioService({}, bus=MagicMock())
        self.assertFalse(svc.supports_seek)

    def test_legacy_adapter_does_not_support_seek(self):
        svc = CLIOldAudioService({}, bus=MagicMock(), name='cli')
        self.assertFalse(svc.supports_seek)

    def test_base_service_class_attribute(self):
        self.assertFalse(CLIBaseService.supports_seek)


if __name__ == "__main__":
    unittest.main()
