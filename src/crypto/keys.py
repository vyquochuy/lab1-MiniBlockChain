"""
Cryptography Layer - Key Management
Handles public/private key pairs for validators and participants
"""
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import base64

class KeyPair:
    """Represents a public/private key pair for signing"""
    
    def __init__(self, private_key=None, seed: bytes = None):
        if private_key is not None and seed is not None:
            raise ValueError("Provide either an existing private_key or a seed, not both")
        
        if seed is not None:
            if len(seed) != 32:
                raise ValueError("Ed25519 seeds must be exactly 32 bytes")
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        
        if private_key is None:
            # Generate new key pair
            private_key = ed25519.Ed25519PrivateKey.generate()
        
        self.private_key = private_key
        self.public_key = self.private_key.public_key()
    
    def sign(self, data: bytes) -> bytes:
        """Sign data with private key"""
        return self.private_key.sign(data)
    
    def get_public_key_bytes(self) -> bytes:
        """Get public key as bytes"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def get_address(self) -> str:
        """Get address (base64 encoded public key)"""
        return base64.b64encode(self.get_public_key_bytes()).decode()
    
    @staticmethod
    def from_seed(seed: bytes) -> 'KeyPair':
        """Create deterministic keypair from 32-byte seed"""
        return KeyPair(seed=seed)
    
    @staticmethod
    def verify(public_key_bytes: bytes, signature: bytes, data: bytes) -> bool:
        """Verify signature against public key and data"""
        try:
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, data)
            return True
        except Exception:
            return False