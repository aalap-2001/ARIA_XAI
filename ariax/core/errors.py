class AriaError(Exception):
    code = "ARIA_ERROR"

    def __init__(self, message: str, details=None):
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self):
        return {"error": self.code, "message": self.message, "details": self.details}


class NotAuthorized(AriaError):
    code = "NOT_AUTHORIZED"


class NotPermitted(AriaError):
    code = "NOT_PERMITTED"


class BundleInvalid(AriaError):
    code = "BUNDLE_INVALID"


class GateViolation(AriaError):
    code = "GATE_VIOLATION"


class KillSwitchEngaged(AriaError):
    code = "KILL_SWITCH"


class NotFound(AriaError):
    code = "NOT_FOUND"
