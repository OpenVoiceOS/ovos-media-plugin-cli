"""Legacy ``ovos-audio`` (mycroft.plugin.audioservice) adapter.

The same subprocess player engine as the new ovos-media
:class:`~ovos_media_plugin_cli.CLIAudioService`, exposed under the legacy
audio-service contract so this plugin works on both stacks:

* new ``ovos-media`` — ``opm.media.audio`` → :class:`~ovos_media_plugin_cli.CLIAudioService`
* legacy ``ovos-audio`` — ``mycroft.plugin.audioservice`` → :class:`CLIOldAudioService`
  (discovered via :func:`load_service`)
"""
from threading import Thread

from ovos_plugin_manager.templates.audio import AudioBackend
from ovos_utils.log import LOG

from ovos_media_plugin_cli import CLIBaseService


class CLIOldAudioService(CLIBaseService, AudioBackend):
    """Subprocess CLI-command backend for the legacy ovos-audio service.

    Reuses every playback method (``play``/``stop``/``pause``/``resume``/
    seek/volume/position) from :class:`CLIBaseService`; only the constructor
    differs because the legacy ``AudioBackend`` takes a ``name``.

    ``CLIBaseService`` is listed first so its concrete methods satisfy the
    abstract playback methods declared on ``AudioBackend`` (MRO order matters).
    """

    def __init__(self, config, bus=None, name='cli'):
        AudioBackend.__init__(self, config, bus, name)
        # MediaBackend's constructor is bypassed, but its concrete methods are
        # still reachable through the MRO, so every attribute those methods
        # read must be initialized here. AudioBackend covers all of them
        # except `meta`.
        self.meta = {}
        # set up the shared subprocess player engine without the new
        # MediaBackend constructor
        self.process = None
        self._stop_signal = False
        self._is_playing = False
        self._paused = False
        self.ts = 0
        self.supports_mime_hints = True
        import mimetypes
        mimetypes.init()

    def play(self, repeat=False):
        # The engine's play() runs the subprocess loop to completion and only
        # then returns; the legacy service calls play() inside its service
        # lock on a bus-handler thread and expects it to return promptly (the
        # end of the track reaches it later through _track_start_callback).
        # Run the engine loop on its own thread.
        Thread(target=CLIBaseService.play, args=(self, repeat),
               daemon=True).start()

    def load_track(self, uri, metadata=None):
        # The legacy audio service owns every ovos.common_play state emission;
        # MediaBackend.load_track (the MRO default here) emits media.state
        # itself, which the service reacts to on the same bus — a feedback
        # loop on a synchronous bus. Queue the uri without touching the bus.
        self._now_playing = uri
        self.meta.update(metadata or {})

    # The legacy service invokes ocp_start()/ocp_error() itself around play()
    # and owns when OCP state hits the bus. The engine's INTERNAL reports must
    # therefore stay off the bus: track lifecycle reaches the service through
    # the old contract's _track_start_callback, and an engine-initiated
    # ocp_stop/ocp_error re-enters the service's own handlers on a
    # synchronous bus and loops.
    def on_track_end(self):
        self._is_playing = False
        self._paused = False
        self.process = None
        self.ts = 0
        if self._track_start_callback:
            self._track_start_callback(None)

    def on_track_error(self):
        self._is_playing = False
        self._paused = False
        self.process = None
        self.ts = 0
        if self._track_start_callback:
            self._track_start_callback(None)
        # a spawn failure is reported through ocp_error, matching the
        # behaviour legacy services expect from an audio backend
        self.ocp_error()


def load_service(base_config, bus):
    backends = base_config.get('backends', {})
    services = [(b, backends[b]) for b in backends
                if backends[b].get('type') in ['cli', 'ovos_cli'] and
                backends[b].get('active', True)]
    instances = [CLIOldAudioService(s[1], bus, s[0]) for s in services]
    if len(instances) == 0:
        LOG.warning("No CLI backends have been configured")
    return instances
