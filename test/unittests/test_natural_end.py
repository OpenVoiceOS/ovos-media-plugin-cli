"""Regression tests for the MediaBackend v2 playback-event lifecycle.

A track that ends naturally (the CLI player process exits on its own, the
play() loop falls through to on_track_end() with no stop() ever called) must
report PlaybackEvent.END_OF_MEDIA via the bound event reporter - never emit
an ``ovos.common_play.*`` bus message directly. State/wire messages are the
daemon's job, not the plugin's; the backend only reports physical events.

Explicit-stop-vs-natural-end and nonzero-exit-code-vs-clean-exit are both
dispatched by the base class's ``report_track_end`` (reading/clearing its
own ``_stop_requested`` flag, and treating any non-None ``error`` as an
ERROR regardless of the stop flag), so these tests drive the real ``stop()``
machinery / a real subprocess exit code rather than poking plugin-private
state directly.
"""
import unittest
from unittest.mock import MagicMock, patch

from ovos_utils.fakebus import FakeBus
from ovos_plugin_manager.templates.media import PlaybackEvent

from ovos_media_plugin_cli import CLIAudioService


class RecordingReporter:
    """A bound event reporter that records every ``report(event, **data)``
    call, standing in for the daemon side of ``bind_event_reporter``."""

    def __init__(self):
        self.events = []

    def __call__(self, event, **data):
        self.events.append((event, data))


class TestPlaybackEventLifecycle(unittest.TestCase):

    def _service(self, uri="file:///tmp/track.wav"):
        bus = FakeBus()
        reporter = RecordingReporter()
        service = CLIAudioService({}, bus=bus)
        service.bind_event_reporter(reporter)
        service.load_track(uri)
        service._is_playing = True
        return service, reporter, bus

    def test_natural_track_end_reports_end_of_media(self):
        service, reporter, _ = self._service()

        # simulate the play() loop falling through because the process
        # exited on its own, with no stop() ever called by us
        service.on_track_end()

        events = [e for e, _ in reporter.events]
        self.assertIn(PlaybackEvent.END_OF_MEDIA, events,
                       f"natural end-of-media never reported END_OF_MEDIA; saw: {events}")
        end_data = dict(reporter.events[events.index(PlaybackEvent.END_OF_MEDIA)][1])
        self.assertEqual(end_data.get("uri"), "file:///tmp/track.wav")

    def test_explicit_stop_reports_stopped_not_end_of_media(self):
        """Drive the real base stop() -> _stop() machinery: stop() sets the
        base's _stop_requested flag, _stop() breaks the (already-stopped-in-
        this-test) play loop, and on_track_end()'s report_track_end() call
        reads/clears that flag to pick STOPPED over END_OF_MEDIA."""
        service, reporter, _ = self._service()

        # _stop() sets the plugin's own _stop_signal, then blocks until
        # _is_playing goes False - exactly what the real play() loop's exit
        # path (which calls on_track_end()) does once it observes the
        # signal. Mimic that on a background thread, waiting for the
        # signal the way play()'s wait loop would, so stop()'s blocking
        # wait is driven for real through the public API rather than
        # racing it.
        import threading

        def fake_play_loop_exit():
            while not service._stop_signal:
                pass
            service.on_track_end()

        t = threading.Thread(target=fake_play_loop_exit)
        t.start()
        stopped = service.stop()
        t.join(timeout=2)

        self.assertTrue(stopped)
        events = [e for e, _ in reporter.events]
        self.assertIn(PlaybackEvent.STOPPED, events)
        self.assertNotIn(PlaybackEvent.END_OF_MEDIA, events)

    def test_on_track_end_does_not_deadlock_stop(self):
        service, _, _ = self._service()
        service.on_track_end()
        self.assertFalse(service._is_playing)

    def test_on_track_end_with_error_reports_error_with_uri_and_message(self):
        service, reporter, _ = self._service()

        service.on_track_end(error="failed to play track")

        events = [e for e, _ in reporter.events]
        self.assertIn(PlaybackEvent.ERROR, events)
        error_data = dict(reporter.events[events.index(PlaybackEvent.ERROR)][1])
        self.assertEqual(error_data.get("uri"), "file:///tmp/track.wav")
        self.assertIsInstance(error_data.get("error"), str)
        self.assertTrue(error_data["error"])

    def test_no_reporter_bound_does_not_raise(self):
        # a backend must be safe to construct and drive standalone (no
        # daemon attached) - report() should just no-op
        service = CLIAudioService({}, bus=FakeBus())
        service.load_track("file:///tmp/track.wav")
        service.on_track_end()  # must not raise

    def test_lifecycle_never_emits_on_the_bus(self):
        """A backend that emits any ovos.common_play.* state message itself
        is buggy by definition - the daemon owns that wire, not the plugin.
        Playback state flows exclusively through report()/bind_event_reporter,
        so the plugin-private bus should see zero emit() calls across a full
        start/pause/resume/end lifecycle."""
        service, reporter, _ = self._service()
        service.bus.emit = MagicMock()

        service.on_track_start()
        service.pause()
        service.resume()
        service.on_track_end()

        service.bus.emit.assert_not_called()


class FakeProcess:
    """Stand-in for the subprocess.Popen object play_audio() returns:
    exits immediately, on its own, with a configurable return code."""

    def __init__(self, returncode):
        self._returncode = returncode
        self._polled = False

    def poll(self):
        # first poll (inside the wait loop's _is_process_running check)
        # reports "still running" once, so the loop body runs at least
        # once before the process is observed to have exited - mirrors a
        # real short-lived process racing the 0.25s poll interval.
        if not self._polled:
            self._polled = True
            return None
        return self._returncode


class TestSubprocessExitCode(unittest.TestCase):
    """A player subprocess exiting with a nonzero return code must be
    reported as ERROR, never mapped to a natural END_OF_MEDIA."""

    def _play_with_returncode(self, returncode):
        bus = FakeBus()
        reporter = RecordingReporter()
        service = CLIAudioService({"command": "true"}, bus=bus)
        service.bind_event_reporter(reporter)
        service.load_track("file:///tmp/track.wav")

        with patch("ovos_media_plugin_cli.play_audio",
                   return_value=FakeProcess(returncode)):
            with patch("ovos_media_plugin_cli.sleep"):
                service.play()

        return reporter

    def test_nonzero_exit_code_reports_error(self):
        reporter = self._play_with_returncode(1)

        events = [e for e, _ in reporter.events]
        self.assertIn(PlaybackEvent.ERROR, events,
                       f"nonzero exit was not reported as ERROR; saw: {events}")
        self.assertNotIn(PlaybackEvent.END_OF_MEDIA, events)
        error_data = dict(reporter.events[events.index(PlaybackEvent.ERROR)][1])
        self.assertEqual(error_data.get("uri"), "file:///tmp/track.wav")
        self.assertIn("1", error_data.get("error", ""))

    def test_zero_exit_code_reports_end_of_media(self):
        reporter = self._play_with_returncode(0)

        events = [e for e, _ in reporter.events]
        self.assertIn(PlaybackEvent.END_OF_MEDIA, events,
                       f"clean exit was not reported as END_OF_MEDIA; saw: {events}")
        self.assertNotIn(PlaybackEvent.ERROR, events)


if __name__ == "__main__":
    unittest.main()
