class SaveError(Exception):
    """Base class: the original file is intact whenever this is raised."""
class Conflict(SaveError): pass
class VerifyFailed(SaveError):
    def __init__(self, msg, report=None):
        super().__init__(msg); self.report = report or {}
class UnsupportedVersion(SaveError): pass
class GateClosed(SaveError): pass
class OverwriteDisabled(SaveError): pass
class Locked(SaveError): pass
class DiskError(SaveError): pass
class Exists(SaveError): pass
class HardlinkTarget(SaveError): pass     # target has other hard links; replace-by-rename would detach them (they keep the OLD content)
class ReadOnlyTarget(SaveError): pass     # target carries a read-only flag/mode; refused up front unless Config.allow_readonly


def exit_code(exc):
    """Batch/CLI exit code of the contract: 0 ok, 3 refused (disabled/gate/exists/unsupported/read-only), 4 conflict/locked, 5 verify failed, 6 disk error."""
    if exc is None: return 0
    if isinstance(exc, (OverwriteDisabled, GateClosed, Exists, UnsupportedVersion, ReadOnlyTarget, HardlinkTarget)): return 3
    if isinstance(exc, (Conflict, Locked)): return 4
    if isinstance(exc, VerifyFailed): return 5
    if isinstance(exc, DiskError): return 6
    return 1
