"""Delete codes and admin password checks. No Streamlit dependency.

Only a salted hash of each delete code is ever stored. The code itself is shown to the
submitter once and cannot be recovered.
"""
import hashlib
import hmac
import secrets

# No 0/O/1/I/L so a code is easy to read back from a screenshot or note.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_GROUPS, GROUP_LEN = 3, 4
MAX_FAILED_ATTEMPTS = 5


def new_delete_code() -> str:
    """12 random characters in 3 groups, e.g. 7KQ2-M9XA-C4TH (about 60 bits)."""
    groups = ["".join(secrets.choice(_ALPHABET) for _ in range(GROUP_LEN)) for _ in range(CODE_GROUPS)]
    return "-".join(groups)


def _normalise(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def _digest(salt: str, code: str) -> str:
    return hashlib.sha256((salt + _normalise(code)).encode("utf-8")).hexdigest()


def hash_code(code: str) -> str:
    """Return 'salt$hash' with a fresh random salt per shipment."""
    salt = secrets.token_hex(8)
    return f"{salt}${_digest(salt, code)}"


def verify_code(code: str, stored: str) -> bool:
    if not code or not stored or "$" not in stored:
        return False
    salt, expected = stored.split("$", 1)
    return hmac.compare_digest(_digest(salt, code), expected)


def check_admin_password(given: str, expected: str) -> bool:
    """False when no admin password is configured, so admin stays locked by default."""
    if not expected or not given:
        return False
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def attempts_exhausted(failed: int, limit: int = MAX_FAILED_ATTEMPTS) -> bool:
    return failed >= limit
