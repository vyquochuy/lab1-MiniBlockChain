"""
Execution Layer - Transaction Executor
Deterministically applies transactions to state
"""
from typing import List, Tuple
from .state import State
from .transaction import Transaction

class Executor:
    """Executes transactions on state"""
    
    def __init__(self):
        self.processed_nonces = {}  # Track nonces per address
    
    def execute_transaction(self, state: State, tx: Transaction) -> Tuple[bool, str]:
        """
        Execute a single transaction on state
        Returns (success, error_message)
        """
        # Verify signature
        if not tx.verify():
            return False, "Invalid signature"
        
        # Check nonce (prevent replay attacks)
        expected_nonce = self.processed_nonces.get(tx.from_addr, 0)
        if tx.nonce != expected_nonce:
            return False, f"Invalid nonce. Expected {expected_nonce}, got {tx.nonce}"
        
        # Check balance
        from_balance = state.get_balance(tx.from_addr)
        if from_balance < tx.amount:
            return False, f"Insufficient balance. Has {from_balance}, needs {tx.amount}"
        
        # Execute transfer
        success = state.transfer(tx.from_addr, tx.to_addr, tx.amount)
        if not success:
            return False, "Transfer failed"
        
        # Update nonce
        self.processed_nonces[tx.from_addr] = tx.nonce + 1
        
        return True, ""
    
    def execute_transactions(self, state: State, transactions: List[Transaction]) -> Tuple[State, List[str]]:
        """
        Execute ordered list of transactions on state
        Returns (new_state, list of tx hashes that succeeded)
        """
        new_state = state.copy()
        executed_txs = []
        
        for tx in transactions:
            success, error = self.execute_transaction(new_state, tx)
            if success:
                executed_txs.append(tx.tx_hash)
            # Even if transaction fails, we continue with others
        
        return new_state, executed_txs
    
    def reset_nonces(self):
        """Reset nonce tracking (for new execution context)"""
        self.processed_nonces = {}