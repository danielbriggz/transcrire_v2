import hashlib
import json


def sha256_str(text: str) -> str:
    """SHA-256 hash of a string. Used for prompt/parameter fingerprinting."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_dict(data: dict) -> str:
    """Deterministic SHA-256 hash of a dictionary. Keys are sorted before hashing."""
    serialised = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return sha256_str(serialised)