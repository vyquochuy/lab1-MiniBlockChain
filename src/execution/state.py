# ============================================================================
# FILE: src/execution/state.py
# ============================================================================
"""
Execution Layer - State Management
Models state as key-value records (accounts, balances)
"""
from typing import Dict, Any
import copy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from crypto.hashing import hash_dict_hex

class State:
    """Represents the blockchain state as key-value store"""
    
    def __init__(self, initial_state: Dict[str, Any] = None):
        if initial_state is None:
            self.data = {}
        else:
            self.data = copy.deepcopy(initial_state)
    
    def get(self, key: str, default=None):
        """Get value for key"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set value for key"""
        self.data[key] = value
    
    def has(self, key: str) -> bool:
        """Check if key exists"""
        return key in self.data
    
    def get_balance(self, address: str) -> int:
        """Get balance for address"""
        return self.data.get(f"balance:{address}", 0)
    
    def set_balance(self, address: str, amount: int):
        """Set balance for address"""
        self.data[f"balance:{address}"] = amount
    
    def transfer(self, from_addr: str, to_addr: str, amount: int) -> bool:
        """Transfer tokens between addresses"""
        from_balance = self.get_balance(from_addr)
        if from_balance < amount:
            return False
        
        self.set_balance(from_addr, from_balance - amount)
        to_balance = self.get_balance(to_addr)
        self.set_balance(to_addr, to_balance + amount)
        return True
    
    def get_hash(self) -> str:
        """Get deterministic hash of state"""
        return hash_dict_hex(self.data)
    
    def copy(self):
        """Create deep copy of state"""
        return State(self.data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return copy.deepcopy(self.data)