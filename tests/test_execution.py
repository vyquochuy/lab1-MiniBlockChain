"""
Unit Tests for Execution Layer
Tests state management, transactions, and deterministic execution
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from crypto.keys import KeyPair
from execution.state import State
from execution.transaction import Transaction
from execution.executor import Executor


def _exec_diagnostics(label: str, state: State = None, executor: Executor = None,
                      transactions=None, executed=None, last_error: str = None):
    print("\n" + "~" * 60)
    print(f"EXECUTION DIAGNOSTICS: {label}")
    print("~" * 60)
    if state is not None:
        try:
            d = state.to_dict()
            print(f" state_hash: {state.get_hash()}")
            # show balances only
            balances = {k[len('balance:'):]: v for k, v in d.items() if k.startswith('balance:')}
            print(f" balances: {balances}")
        except Exception as e:
            print(f" state: (error reading) {e}")
    if executor is not None:
        try:
            print(f" processed_nonces: {getattr(executor, 'processed_nonces', {})}")
        except Exception as e:
            print(f" executor: (error reading) {e}")
    if transactions is not None:
        print(f" transactions_count: {len(transactions)}")
    if executed is not None:
        print(f" executed: {executed}")
    if last_error is not None:
        print(f" last_error: {last_error}")
    print("")

def test_state_operations():
    """Test basic state operations"""
    print("\nTEST: State Operations")
    
    state = State()
    
    # Set and get
    state.set("key1", "value1")
    assert state.get("key1") == "value1", "Set/get failed"
    
    # Default value
    assert state.get("nonexistent", "default") == "default", "Default value failed"
    
    # Has key
    assert state.has("key1"), "Has key check failed"
    assert not state.has("nonexistent"), "Has key false positive"
    _exec_diagnostics("state_operations", state=state)
    
    print("PASSED: State operations work correctly")
    return True

def test_balance_operations():
    """Test balance management"""
    print("\nTEST: Balance Operations")
    
    state = State()
    
    # Initial balance should be 0
    assert state.get_balance("alice") == 0, "Initial balance should be 0"
    
    # Set balance
    state.set_balance("alice", 1000)
    assert state.get_balance("alice") == 1000, "Balance not set correctly"
    
    # Transfer
    state.set_balance("bob", 500)
    success = state.transfer("alice", "bob", 300)
    assert success, "Transfer failed"
    assert state.get_balance("alice") == 700, "Sender balance incorrect"
    assert state.get_balance("bob") == 800, "Recipient balance incorrect"
    
    # Transfer with insufficient balance
    success = state.transfer("bob", "alice", 1000)
    assert not success, "Transfer with insufficient balance succeeded"
    _exec_diagnostics("balance_operations", state=state)

    print("PASSED: Balance operations work correctly")
    return True

def test_state_hash_determinism():
    """Test that state hashing is deterministic"""
    print("\nTEST: State Hash Determinism")
    
    # Create identical states
    state1 = State()
    state1.set_balance("alice", 1000)
    state1.set_balance("bob", 2000)
    
    state2 = State()
    state2.set_balance("alice", 1000)
    state2.set_balance("bob", 2000)
    
    # Hashes should match
    hash1 = state1.get_hash()
    hash2 = state2.get_hash()
    assert hash1 == hash2, "Identical states produced different hashes"
    
    # Different insertion order
    state3 = State()
    state3.set_balance("bob", 2000)  # Bob first
    state3.set_balance("alice", 1000)  # Alice second
    
    hash3 = state3.get_hash()
    assert hash1 == hash3, "Insertion order affected hash"
    
    # Modified state should have different hash
    state4 = State()
    state4.set_balance("alice", 1000)
    state4.set_balance("bob", 3000)  # Different value
    
    hash4 = state4.get_hash()
    assert hash1 != hash4, "Different states produced same hash"
    _exec_diagnostics("state_hash_determinism", state=state1)

    print("PASSED: State hashing is deterministic")
    return True

def test_transaction_creation():
    """Test transaction creation and signing"""
    print("\nTEST: Transaction Creation")
    
    chain_id = "test-chain"
    keypair = KeyPair()
    
    tx = Transaction(
        from_addr=keypair.get_address(),
        to_addr="recipient",
        amount=100,
        nonce=0,
        chain_id=chain_id
    )
    
    # Sign transaction
    tx.sign(keypair)
    assert tx.signature is not None, "Transaction not signed"
    assert tx.tx_hash is not None, "Transaction hash not generated"
    
    # Verify transaction
    is_valid = tx.verify()
    assert is_valid, "Valid transaction rejected"
    _exec_diagnostics("transaction_creation", transactions=[tx])

    print("PASSED: Transaction creation works correctly")
    return True

def test_transaction_nonce():
    """Test that nonce prevents replay attacks"""
    print("\nTEST: Transaction Nonce (Replay Protection)")
    
    chain_id = "test-chain"
    keypair = KeyPair()
    
    state = State()
    state.set_balance(keypair.get_address(), 1000)
    
    executor = Executor()
    
    # Create and execute transaction with nonce 0
    tx1 = Transaction(keypair.get_address(), "recipient", 100, 0, chain_id)
    tx1.sign(keypair)
    
    success, error = executor.execute_transaction(state, tx1)
    assert success, f"Transaction failed: {error}"
    
    # Try to replay same transaction (same nonce)
    success, error = executor.execute_transaction(state, tx1)
    assert not success, "Replay attack succeeded"
    assert "nonce" in error.lower(), "Error should mention nonce"
    
    # Transaction with correct next nonce should work
    tx2 = Transaction(keypair.get_address(), "recipient", 100, 1, chain_id)
    tx2.sign(keypair)
    
    success, error = executor.execute_transaction(state, tx2)
    assert success, f"Valid transaction failed: {error}"
    _exec_diagnostics("transaction_nonce", state=state, executor=executor)

    print("PASSED: Nonce prevents replay attacks")
    return True

def test_transaction_signature_validation():
    """Test that invalid signatures are rejected"""
    print("\nTEST: Transaction Signature Validation")
    
    chain_id = "test-chain"
    keypair1 = KeyPair()
    keypair2 = KeyPair()
    
    # Create transaction signed by keypair1
    tx = Transaction(keypair1.get_address(), "recipient", 100, 0, chain_id)
    tx.sign(keypair1)
    
    # Verify with correct signature
    assert tx.verify(), "Valid signature rejected"
    
    # Tamper with signature
    tx.signature = keypair2.sign(b"different_data")
    assert not tx.verify(), "Invalid signature accepted"
    _exec_diagnostics("transaction_signature_validation")

    print("PASSED: Invalid signatures are rejected")
    return True

def test_executor_determinism():
    """Test that executor produces deterministic results"""
    print("\nTEST: Executor Determinism")
    
    chain_id = "test-chain"
    keypair = KeyPair()
    
    # Create transactions
    transactions = []
    for i in range(5):
        tx = Transaction(
            keypair.get_address(),
            f"recipient_{i}",
            10 * (i + 1),
            i,
            chain_id
        )
        tx.sign(keypair)
        transactions.append(tx)
    
    # Execute on first state
    state1 = State()
    state1.set_balance(keypair.get_address(), 1000)
    executor1 = Executor()
    new_state1, executed1 = executor1.execute_transactions(state1, transactions)
    hash1 = new_state1.get_hash()
    
    # Execute on second state
    state2 = State()
    state2.set_balance(keypair.get_address(), 1000)
    executor2 = Executor()
    new_state2, executed2 = executor2.execute_transactions(state2, transactions)
    hash2 = new_state2.get_hash()
    
    # Results should be identical
    assert hash1 == hash2, "Executor produced different results"
    assert executed1 == executed2, "Different transactions executed"
    _exec_diagnostics("executor_determinism", state=new_state1, executor=executor1,
                      transactions=transactions, executed=executed1)

    print("PASSED: Executor is deterministic")
    return True

def test_insufficient_balance():
    """Test that transactions with insufficient balance fail"""
    print("\nTEST: Insufficient Balance Check")
    
    chain_id = "test-chain"
    keypair = KeyPair()
    
    state = State()
    state.set_balance(keypair.get_address(), 50)  # Only 50 tokens
    
    executor = Executor()
    
    # Try to send 100 tokens
    tx = Transaction(keypair.get_address(), "recipient", 100, 0, chain_id)
    tx.sign(keypair)
    
    success, error = executor.execute_transaction(state, tx)
    assert not success, "Transaction with insufficient balance succeeded"
    assert "insufficient" in error.lower(), "Error should mention insufficient balance"
    
    # Balance should remain unchanged
    assert state.get_balance(keypair.get_address()) == 50, \
        "Balance changed despite failed transaction"
    _exec_diagnostics("insufficient_balance", state=state, executor=executor, last_error=error)

    print("PASSED: Insufficient balance is checked")
    return True

def test_state_isolation():
    """Test that state copies are independent"""
    print("\nTEST: State Isolation")
    
    original = State()
    original.set_balance("alice", 1000)
    
    # Create copy
    copy = original.copy()
    
    # Modify copy
    copy.set_balance("alice", 2000)
    copy.set_balance("bob", 500)
    
    # Original should be unchanged
    assert original.get_balance("alice") == 1000, "Original state was modified"
    assert original.get_balance("bob") == 0, "Original state was modified"
    
    # Copy should have modifications
    assert copy.get_balance("alice") == 2000, "Copy not modified correctly"
    assert copy.get_balance("bob") == 500, "Copy not modified correctly"
    _exec_diagnostics("state_isolation_original", state=original)
    _exec_diagnostics("state_isolation_copy", state=copy)

    print("PASSED: State copies are isolated")
    return True

def test_transaction_ordering():
    """Test that transaction order affects final state"""
    print("\nTEST: Transaction Ordering")
    
    chain_id = "test-chain"
    alice_key = KeyPair()
    bob_key = KeyPair()
    
    alice_addr = alice_key.get_address()
    bob_addr = bob_key.get_address()
    
    # Initial state
    state = State()
    state.set_balance(alice_addr, 1000)
    state.set_balance(bob_addr, 0)
    
    # Create transactions
    tx1 = Transaction(alice_addr, bob_addr, 500, 0, chain_id)
    tx1.sign(alice_key)
    
    tx2 = Transaction(alice_addr, bob_addr, 300, 1, chain_id)
    tx2.sign(alice_key)
    
    # Execute in order
    executor = Executor()
    new_state, executed = executor.execute_transactions(state, [tx1, tx2])
    
    # Check final balances
    assert new_state.get_balance(alice_addr) == 200, "Alice balance incorrect"
    assert new_state.get_balance(bob_addr) == 800, "Bob balance incorrect"
    assert len(executed) == 2, "Not all transactions executed"
    _exec_diagnostics("transaction_ordering", state=new_state, executor=executor, executed=executed)

    print("PASSED: Transaction ordering is respected")
    return True

def run_all_execution_tests():
    """Run all execution tests"""
    print("\n" + "="*80)
    print("RUNNING EXECUTION UNIT TESTS")
    print("="*80)
    
    tests = [
        test_state_operations,
        test_balance_operations,
        test_state_hash_determinism,
        test_transaction_creation,
        test_transaction_nonce,
        test_transaction_signature_validation,
        test_executor_determinism,
        test_insufficient_balance,
        test_state_isolation,
        test_transaction_ordering
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_func.__name__, False))
    
    print("\n" + "="*80)
    print("EXECUTION TEST SUMMARY")
    print("="*80)
    
    for name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\nALL EXECUTION TESTS PASSED!")
        return 0
    else:
        print("\nSOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_all_execution_tests()
    sys.exit(exit_code)