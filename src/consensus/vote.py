"""
Consensus Layer - Voting Mechanism
Two-phase voting: Prevote and Precommit
"""
from typing import Dict, Any
from enum import Enum
import base64
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from crypto.signature import SignedMessage
from crypto.keys import KeyPair

class VoteType(Enum):
    """Vote types in two-phase consensus"""
    PREVOTE = "prevote"
    PRECOMMIT = "precommit"

class Vote:
    """Signed validator vote for a block"""
    
    def __init__(self, vote_type: VoteType, height: int, block_hash: str, 
                 validator_address: str, chain_id: str):
        self.vote_type = vote_type
        self.height = height
        self.block_hash = block_hash
        self.validator_address = validator_address
        self.chain_id = chain_id
        self.signature = None
    
    def to_data_dict(self) -> Dict[str, Any]:
        """Convert vote data to dictionary"""
        return {
            "type": self.vote_type.value,
            "height": self.height,
            "block_hash": self.block_hash,
            "validator": self.validator_address
        }
    
    def sign(self, keypair: KeyPair):
        """Sign vote with validator's keypair"""
        msg = SignedMessage(
            domain=SignedMessage.DOMAIN_VOTE,
            chain_id=self.chain_id,
            data=self.to_data_dict()
        )
        msg.sign(keypair)
        self.signature = msg.signature
    
    def verify(self) -> bool:
        """Verify vote signature"""
        if self.signature is None:
            return False
        
        try:
            public_key_bytes = base64.b64decode(self.validator_address)
        except Exception:
            return False
        
        msg = SignedMessage(
            domain=SignedMessage.DOMAIN_VOTE,
            chain_id=self.chain_id,
            data=self.to_data_dict()
        )
        msg.signature = self.signature
        
        return msg.verify(public_key_bytes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "type": self.vote_type.value,
            "height": self.height,
            "block_hash": self.block_hash,
            "validator": self.validator_address,
            "chain_id": self.chain_id,
            "signature": base64.b64encode(self.signature).decode() if self.signature else None
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        """Reconstruct from dictionary"""
        vote = cls(
            VoteType(d["type"]),
            d["height"],
            d["block_hash"],
            d["validator"],
            d["chain_id"]
        )
        if d.get("signature"):
            vote.signature = base64.b64decode(d["signature"])
        return vote

class VoteCollector:
    """Collects and tracks votes for consensus"""
    
    def __init__(self, total_validators: int):
        self.total_validators = total_validators
        self.prevotes = {}  # height -> block_hash -> set of validator addresses
        self.precommits = {}  # height -> block_hash -> set of validator addresses
    
    def add_vote(self, vote: Vote) -> bool:
        """Add a vote and return True if it's new"""
        if not vote.verify():
            return False
        
        height = vote.height
        block_hash = vote.block_hash
        validator = vote.validator_address
        
        if vote.vote_type == VoteType.PREVOTE:
            if height not in self.prevotes:
                self.prevotes[height] = {}
            if block_hash not in self.prevotes[height]:
                self.prevotes[height][block_hash] = set()
            
            if validator in self.prevotes[height][block_hash]:
                return False  # Duplicate
            self.prevotes[height][block_hash].add(validator)
            return True
        
        elif vote.vote_type == VoteType.PRECOMMIT:
            if height not in self.precommits:
                self.precommits[height] = {}
            if block_hash not in self.precommits[height]:
                self.precommits[height][block_hash] = set()
            
            if validator in self.precommits[height][block_hash]:
                return False  # Duplicate
            self.precommits[height][block_hash].add(validator)
            return True
        
        return False
    
    def has_prevote_majority(self, height: int, block_hash: str) -> bool:
        """Check if block has prevote majority (> 2/3)"""
        if height not in self.prevotes or block_hash not in self.prevotes[height]:
            return False
        count = len(self.prevotes[height][block_hash])
        return count > (2 * self.total_validators) // 3
    
    def has_precommit_majority(self, height: int, block_hash: str) -> bool:
        """Check if block has precommit majority (> 2/3) for finalization"""
        if height not in self.precommits or block_hash not in self.precommits[height]:
            return False
        count = len(self.precommits[height][block_hash])
        return count > (2 * self.total_validators) // 3
    
    def get_prevote_count(self, height: int, block_hash: str) -> int:
        """Get prevote count for a block"""
        if height not in self.prevotes or block_hash not in self.prevotes[height]:
            return 0
        return len(self.prevotes[height][block_hash])
    
    def get_precommit_count(self, height: int, block_hash: str) -> int:
        """Get precommit count for a block"""
        if height not in self.precommits or block_hash not in self.precommits[height]:
            return 0
        return len(self.precommits[height][block_hash])