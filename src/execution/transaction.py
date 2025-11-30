"""
Execution Layer - Transactions
Signed requests to modify state owned by the sender
"""
from typing import Dict, Any
import base64
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from crypto.signature import SignedMessage
from crypto.keys import KeyPair

class Transaction:
    """Represents a signed transaction"""
    
    def __init__(self, from_addr: str, to_addr: str, amount: int, nonce: int, chain_id: str):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount = amount
        self.nonce = nonce
        self.chain_id = chain_id
        self.signature = None
        self.tx_hash = None
    
    def to_data_dict(self) -> Dict[str, Any]:
        """Convert transaction data to dictionary"""
        return {
            "from": self.from_addr,
            "to": self.to_addr,
            "amount": self.amount,
            "nonce": self.nonce
        }
    
    def sign(self, keypair: KeyPair):
        """Sign transaction with keypair"""
        msg = SignedMessage(
            domain=SignedMessage.DOMAIN_TX,
            chain_id=self.chain_id,
            data=self.to_data_dict()
        )
        msg.sign(keypair)
        self.signature = msg.signature
        
        # Calculate transaction hash
        from crypto.hashing import hash_dict_hex
        self.tx_hash = hash_dict_hex(self.to_dict())
    
    def verify(self) -> bool:
        """Verify transaction signature"""
        if self.signature is None:
            return False
        
        # Decode public key from address
        try:
            public_key_bytes = base64.b64decode(self.from_addr)
        except Exception:
            return False
        
        msg = SignedMessage(
            domain=SignedMessage.DOMAIN_TX,
            chain_id=self.chain_id,
            data=self.to_data_dict()
        )
        msg.signature = self.signature
        
        return msg.verify(public_key_bytes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "from": self.from_addr,
            "to": self.to_addr,
            "amount": self.amount,
            "nonce": self.nonce,
            "chain_id": self.chain_id,
            "signature": base64.b64encode(self.signature).decode() if self.signature else None,
            "tx_hash": self.tx_hash
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        """Reconstruct from dictionary"""
        tx = cls(d["from"], d["to"], d["amount"], d["nonce"], d["chain_id"])
        if d.get("signature"):
            tx.signature = base64.b64decode(d["signature"])
        tx.tx_hash = d.get("tx_hash")
        return tx