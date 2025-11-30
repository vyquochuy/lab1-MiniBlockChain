"""
Cryptography Layer - Message Signing with Domain Separation
Ensures signatures cannot be reused across different message types
"""
import json
from typing import Dict, Any

class SignedMessage:
    """Base class for signed messages with domain separation"""
    
    DOMAIN_TX = "TX"
    DOMAIN_VOTE = "VOTE"
    DOMAIN_BLOCK = "BLOCK"
    
    def __init__(self, domain: str, chain_id: str, data: Dict[str, Any]):
        self.domain = domain
        self.chain_id = chain_id
        self.data = data
        self.signature = None
        self.signer_address = None
    
    def get_signing_bytes(self) -> bytes:
        """Get deterministic bytes for signing with domain separation"""
        message_dict = {
            "domain": self.domain,
            "chain_id": self.chain_id,
            "data": self.data
        }
        # Deterministic JSON encoding (sorted keys, no whitespace)
        json_str = json.dumps(message_dict, sort_keys=True, separators=(',', ':'))
        return json_str.encode('utf-8')
    
    def sign(self, keypair):
        """Sign the message with given keypair"""
        signing_bytes = self.get_signing_bytes()
        self.signature = keypair.sign(signing_bytes)
        self.signer_address = keypair.get_address()
    
    def verify(self, public_key_bytes: bytes) -> bool:
        """Verify the signature"""
        if self.signature is None:
            return False
        from .keys import KeyPair
        signing_bytes = self.get_signing_bytes()
        return KeyPair.verify(public_key_bytes, self.signature, signing_bytes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        import base64
        return {
            "domain": self.domain,
            "chain_id": self.chain_id,
            "data": self.data,
            "signature": base64.b64encode(self.signature).decode() if self.signature else None,
            "signer_address": self.signer_address
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        """Reconstruct from dictionary"""
        import base64
        msg = cls(d["domain"], d["chain_id"], d["data"])
        if d.get("signature"):
            msg.signature = base64.b64decode(d["signature"])
        msg.signer_address = d.get("signer_address")
        return msg