"""The legacy adapter bypasses MediaBackend.__init__ on purpose, so it must
initialize every attribute that MediaBackend's concrete methods read — the
legacy service drives ``add_list()``, which resolves to
``MediaBackend.load_track`` through the MRO."""
import threading
import time
import unittest
import unittest.mock
from time import monotonic

from ovos_utils.fakebus import FakeBus

from ovos_media_plugin_cli.audio import CLIOldAudioService


class TestLegacyShimState(unittest.TestCase):
    def test_add_list_reaches_load_track_without_raising(self):
        svc = CLIOldAudioService({"type": "ovos_cli"}, FakeBus(), "cli")
        svc.add_list(["http://fake.mp3"])
        self.assertEqual(svc._now_playing, "http://fake.mp3")
        self.assertEqual(svc.meta, {})

    def test_add_list_emits_nothing_on_the_bus(self):
        # the legacy service owns state emission; a plugin emission here
        # feeds back into the service on a synchronous bus
        bus = FakeBus()
        seen = []
        bus.on("message", lambda m: seen.append(m))
        svc = CLIOldAudioService({"type": "ovos_cli"}, bus, "cli")
        svc.add_list(["http://fake.mp3"])
        self.assertEqual(seen, [])

    def test_natural_end_emits_nothing_on_the_bus(self):
        # natural end reaches the service through _track_start_callback(None);
        # an engine-initiated ocp_stop here re-enters the service's own
        # handlers on a synchronous bus. A track must be loaded first:
        # ocp_stop no-ops on an empty _now_playing, which would mask the
        # difference.
        bus = FakeBus()
        seen = []
        bus.on("message", lambda m: seen.append(m))
        svc = CLIOldAudioService({"type": "ovos_cli"}, bus, "cli")
        ended = []
        svc.set_track_start_callback(lambda t: ended.append(t))
        svc.add_list(["http://fake.mp3"])
        svc.on_track_end()
        self.assertEqual(seen, [])
        self.assertEqual(ended, [None])

    def test_play_returns_before_the_engine_loop_completes(self):
        # the legacy service calls play() under its service lock; a play()
        # that blocks for the track's duration deadlocks the service. The
        # engine loop is slowed deliberately so a blocking play() cannot
        # pass by finishing instantly.
        from ovos_media_plugin_cli import CLIBaseService
        started = threading.Event()
        finished = threading.Event()

        def slow_engine_play(self, repeat=False):
            started.set()
            time.sleep(1.0)
            finished.set()

        svc = CLIOldAudioService({"type": "ovos_cli"}, FakeBus(), "cli")
        svc.add_list(["http://fake.mp3"])
        with unittest.mock.patch.object(CLIBaseService, "play",
                                        slow_engine_play):
            t = monotonic()
            svc.play()
            elapsed = monotonic() - t
        self.assertLess(elapsed, 0.5)
        self.assertTrue(started.wait(2.0))
        self.assertFalse(finished.is_set() and elapsed >= 1.0)
        finished.wait(2.0)

    def test_service_driven_ocp_start_still_reports(self):
        # the legacy service calls ocp_start() itself after play(); that
        # sanctioned, service-driven path must keep emitting
        bus = FakeBus()
        seen = []
        bus.on("message", lambda m: seen.append(m))
        svc = CLIOldAudioService({"type": "ovos_cli"}, bus, "cli")
        svc.add_list(["http://fake.mp3"])
        svc.ocp_start()
        self.assertGreater(len(seen), 0)


if __name__ == "__main__":
    unittest.main()
