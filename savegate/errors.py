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
class ReadOnlyTarget(SaveError): pass     # target carries a read-only flag/mode; refused up front unless Config.allow_readonly
