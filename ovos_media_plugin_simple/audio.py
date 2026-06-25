"""Legacy ``ovos-audio`` (mycroft.plugin.audioservice) adapter.

The same subprocess player engine as the new ovos-media
:class:`~ovos_media_plugin_simple.SimpleAudioService`, exposed under the legacy
audio-service contract so this plugin works on both stacks:

* new ``ovos-media`` — ``opm.media.audio`` → :class:`~ovos_media_plugin_simple.SimpleAudioService`
* legacy ``ovos-audio`` — ``mycroft.plugin.audioservice`` → :class:`SimpleOldAudioService`
  (discovered via :func:`load_service`)
"""
from ovos_plugin_manager.templates.audio import AudioBackend
from ovos_utils.log import LOG

from ovos_media_plugin_simple import SimpleBaseService


class SimpleOldAudioService(SimpleBaseService, AudioBackend):
    """Simple subprocess backend for the legacy ovos-audio service.

    Reuses every playback method (``play``/``stop``/``pause``/``resume``/
    seek/volume/position) from :class:`SimpleBaseService`; only the constructor
    differs because the legacy ``AudioBackend`` takes a ``name``.

    ``SimpleBaseService`` is listed first so its concrete methods satisfy the
    abstract playback methods declared on ``AudioBackend`` (MRO order matters).
    """

    def __init__(self, config, bus=None, name='simple'):
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
                if backends[b].get('type') in ['simple', 'ovos_simple'] and
                backends[b].get('active', True)]
    instances = [SimpleOldAudioService(s[1], bus, s[0]) for s in services]
    if len(instances) == 0:
        LOG.warning("No Simple backends have been configured")
    return instances
