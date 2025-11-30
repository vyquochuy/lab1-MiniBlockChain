"""
Cryptography Layer - Hashing and Commitments
Collision-resistant hash function for state and block commitments
"""
import hashlib
import json
from typing import Any, Dict

def hash_data(data: bytes) -> bytes:
    """Hash arbitrary bytes using SHA-256"""
    return hashlib.sha256(data).digest()

def hash_dict(data: Dict[str, Any]) -> bytes:
    """Hash a dictionary deterministically"""
    # Deterministic JSON encoding
    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hash_data(json_str.encode('utf-8'))

def hash_hex(data: bytes) -> str:
    """Return hex representation of hash"""
    return hashlib.sha256(data).hexdigest()

def hash_dict_hex(data: Dict[str, Any]) -> str:
    """Return hex hash of dictionary"""
    return hash_hex(json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8'))