"""Legacy ``ovos-audio`` (mycroft.plugin.audioservice) adapter.

The same subprocess player engine as the new ovos-media
:class:`~ovos_media_plugin_cli.CLIAudioService`, exposed under the legacy
audio-service contract so this plugin works on both stacks:

* new ``ovos-media`` — ``opm.media.audio`` → :class:`~ovos_media_plugin_cli.CLIAudioService`
* legacy ``ovos-audio`` — ``mycroft.plugin.audioservice`` → :class:`CLIOldAudioService`
  (discovered via :func:`load_service`)
"""
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


def load_service(base_config, bus):
    backends = base_config.get('backends', {})
    services = [(b, backends[b]) for b in backends
                if backends[b].get('type') in ['cli', 'ovos_cli'] and
                backends[b].get('active', True)]
    instances = [CLIOldAudioService(s[1], bus, s[0]) for s in services]
    if len(instances) == 0:
        LOG.warning("No CLI backends have been configured")
    return instances
