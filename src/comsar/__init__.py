import pkg_resources as _pkg

from ._tracks.timbre import TimbreTrack
from ._tracks.pitch import PitchTrack

__version__ = _pkg.get_distribution('comsar').version
