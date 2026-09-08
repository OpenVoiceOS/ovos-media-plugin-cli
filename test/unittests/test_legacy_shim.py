"""The legacy adapter bypasses MediaBackend.__init__ on purpose, so it must
initialize every attribute that MediaBackend's concrete methods read — the
legacy service drives ``add_list()``, which resolves to
``MediaBackend.load_track`` through the MRO."""
import unittest

from ovos_utils.fakebus import FakeBus

from ovos_media_plugin_cli.audio import CLIOldAudioService


class TestLegacyShimState(unittest.TestCase):
    def test_add_list_reaches_load_track_without_raising(self):
        svc = CLIOldAudioService({"type": "ovos_cli"}, FakeBus(), "cli")
        svc.add_list(["http://fake.mp3"])
        self.assertEqual(svc._now_playing, "http://fake.mp3")
        self.assertEqual(svc.meta, {})


if __name__ == "__main__":
    unittest.main()
