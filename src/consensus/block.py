"""
Consensus Layer - Block Structure
Ordered set of transactions with parent reference and state commitment
"""
from typing import List, Dict, Any, Optional
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from crypto.hashing import hash_dict_hex
from execution.transaction import Transaction

class BlockHeader:
    """Block header with commitments"""
    
    def __init__(self, height: int, parent_hash: str, state_hash: str, 
                 tx_root: str, timestamp: int, proposer: str):
        self.height = height
        self.parent_hash = parent_hash
        self.state_hash = state_hash
        self.tx_root = tx_root
        self.timestamp = timestamp
        self.proposer = proposer
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "height": self.height,
            "parent_hash": self.parent_hash,
            "state_hash": self.state_hash,
            "tx_root": self.tx_root,
            "timestamp": self.timestamp,
            "proposer": self.proposer
        }
    
    def get_hash(self) -> str:
        """Get hash of this header"""
        return hash_dict_hex(self.to_dict())
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        return cls(
            d["height"], d["parent_hash"], d["state_hash"],
            d["tx_root"], d["timestamp"], d["proposer"]
        )

class Block:
    """Complete block with header and transactions"""
    
    def __init__(self, header: BlockHeader, transactions: List[Transaction]):
        self.header = header
        self.transactions = transactions
        self.block_hash = None
        self._finalized = False
    
    def get_hash(self) -> str:
        """Get hash of this block"""
        if self.block_hash is None:
            self.block_hash = self.header.get_hash()
        return self.block_hash
    
    def is_finalized(self) -> bool:
        """Check if block is finalized"""
        return self._finalized
    
    def mark_finalized(self):
        """Mark this block as finalized"""
        self._finalized = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": self.header.to_dict(),
            "transactions": [tx.to_dict() for tx in self.transactions],
            "block_hash": self.get_hash(),
            "finalized": self._finalized
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        header = BlockHeader.from_dict(d["header"])
        transactions = [Transaction.from_dict(tx) for tx in d["transactions"]]
        block = cls(header, transactions)
        block.block_hash = d.get("block_hash")
        block._finalized = d.get("finalized", False)
        return block
    
    @staticmethod
    def create_genesis(chain_id: str, initial_state_hash: str) -> 'Block':
        """Create genesis block"""
        header = BlockHeader(
            height=0,
            parent_hash="0" * 64,
            state_hash=initial_state_hash,
            tx_root="0" * 64,
            timestamp=int(time.time()),
            proposer="genesis"
        )
        return Block(header, [])

class BlockProposal:
    """Block proposal for consensus"""
    
    def __init__(self, block: Block, proposer_address: str):
        self.block = block
        self.proposer_address = proposer_address
        self.proposal_hash = block.get_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "block": self.block.to_dict(),
            "proposer_address": self.proposer_address,
            "proposal_hash": self.proposal_hash
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        block = Block.from_dict(d["block"])
        return cls(block, d["proposer_address"])