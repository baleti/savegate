import os as _os
_os.environ.setdefault('RVT_GEOM', '1')      # c4x-rvtgap: rvt_decode.Dec.STOP is fixed at import; without this the reader skips GeomStepList/GeomTable and the delete-reference scan misses referrers (gate escape)
from .errors import *
from .errors import exit_code
from .core import Config, SaveResult, Doc, open_doc, save, save_as, restore, gate_open
from .backup import list_backups
from .journal import unfinished as recover
from .guard import fingerprint, Fingerprint
