"""
End-to-End Tests
Tests entire blockchain system with consensus and network simulation
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from crypto.keys import KeyPair
from network.network import UnreliableNetwork
from node import BlockchainNode, Logger
import time


def _log_diagnostics(nodes, network, label: str, tick: int = None):
    """Print helpful diagnostics about network and nodes for debugging."""
    header = f"DIAGNOSTICS: {label}"
    if tick is not None:
        header += f" @ tick={tick}"
    print("\n" + "-" * 80)
    print(header)
    print("-" * 80)

    # Network stats
    try:
        stats = network.get_stats()
    except Exception:
        stats = {}

    print("Network stats:")
    print(f"  simulation_time: {stats.get('simulation_time')}")
    print(f"  delivered: {stats.get('delivered')}")
    print(f"  dropped: {stats.get('dropped')}")
    print(f"  duplicated: {stats.get('duplicated')}")
    print(f"  pending (message_queue): {stats.get('pending')}")
    print(f"  in_inboxes: {stats.get('in_inboxes')}")
    print(f"  blocked_peers: {stats.get('blocked_peers')}")
    print(f"  rate_limited_drops: {stats.get('rate_limited_drops', stats.get('rate_limit_drops'))}")

    # Per-node stats
    print("\nNode states:")
    for i, node in enumerate(nodes):
        chain_len = len(node.get_blockchain())
        current_height = node.consensus.current_height
        tx_pool = len(node.tx_pool)
        last_block_hash = None
        if chain_len > 0:
            last_block_hash = node.get_blockchain()[-1].get_hash()[:16]
        prevoted = len(node.consensus.prevoted)
        precommitted = len(node.consensus.precommitted)
        print(f"  Node[{i}] {node.address[:8]}...: chain_len={chain_len}, height={current_height}, tx_pool={tx_pool}, last_block={last_block_hash}, prevoted={prevoted}, precommitted={precommitted}")


def test_single_block_finalization():
    """Test that a single block can be finalized"""
    print("\n" + "="*80)
    print("TEST: Single Block Finalization")
    print("="*80)
    
    chain_id = "test-chain"
    num_validators = 4
    
    # Create validators
    validators = [KeyPair() for _ in range(num_validators)]
    validator_addresses = [v.get_address() for v in validators]
    
    # Create network
    logger = Logger("NETWORK", False)
    network = UnreliableNetwork(logger, delay_range=(0.001, 0.01), 
                                loss_rate=0.0, enable_delays=False)
    
    # Create nodes
    nodes = []
    initial_balances = {}
    
    for i, keypair in enumerate(validators):
        node = BlockchainNode(
            node_id=f"node-{i}",
            chain_id=chain_id,
            keypair=keypair,
            all_validator_addresses=validator_addresses,
            network=network,
            verbose=False
        )
        nodes.append(node)
        initial_balances[node.address] = 1000
    
    # Update addresses
    validator_addresses = [n.address for n in nodes]
    for node in nodes:
        node.all_validators = validator_addresses
        node.consensus.all_validators = validator_addresses
    
    # Initialize genesis
    for node in nodes:
        node.initialize_genesis(initial_balances)
    
    # Submit transactions
    tx = nodes[0].create_transaction(nodes[1].address, 50)
    nodes[0].submit_transaction(tx)
    
    # Run consensus
    for t in range(100):
        # Network tick: advance time và deliver messages
        network.tick(0.01)

        # Node tick: xử lý messages và events
        for node in nodes:
            node.tick()

        # Periodic diagnostics to observe behavior
        if t % 20 == 0:
            _log_diagnostics(nodes, network, "single_block_running", t)
    
    # Verify
    finalized_count = len(nodes[0].get_blockchain())
    assert finalized_count == 2, f"Expected 2 blocks (genesis + 1), got {finalized_count}"
    
    # Check all nodes have same chain
    chain_hashes = [tuple(b.get_hash() for b in node.get_blockchain()) 
                    for node in nodes]
    assert len(set(chain_hashes)) == 1, "Not all nodes have the same blockchain"
    
    print("PASSED: Single block finalized correctly")
    return True

def test_no_double_finalization():
    """Test that no two different blocks are finalized at same height"""
    print("\n" + "="*80)
    print("TEST: No Double Finalization (Safety)")
    print("="*80)
    
    chain_id = "test-chain"
    num_validators = 4
    
    validators = [KeyPair() for _ in range(num_validators)]
    validator_addresses = [v.get_address() for v in validators]
    
    logger = Logger("NETWORK", False)
    network = UnreliableNetwork(logger, delay_range=(0.001, 0.01),
                                loss_rate=0.1)
    
    nodes = []
    initial_balances = {}
    
    for i, keypair in enumerate(validators):
        node = BlockchainNode(
            node_id=f"node-{i}",
            chain_id=chain_id,
            keypair=keypair,
            all_validator_addresses=validator_addresses,
            network=network,
            verbose=False
        )
        nodes.append(node)
        initial_balances[node.address] = 1000
    
    validator_addresses = [n.address for n in nodes]
    for node in nodes:
        node.all_validators = validator_addresses
        node.consensus.all_validators = validator_addresses
    
    for node in nodes:
        node.initialize_genesis(initial_balances)
    
    # Submit different transactions to different nodes
    for i, node in enumerate(nodes):
        recipient = nodes[(i + 1) % len(nodes)].address
        tx = node.create_transaction(recipient, 10 + i)
        node.submit_transaction(tx)
    
    # Run consensus for multiple blocks
    for _ in range(200):
        # Network tick: advance time và deliver messages
        network.tick(0.01)

        # Node tick: xử lý messages và events
        for node in nodes:
            node.tick()

        # Periodic diagnostics for long-run test
        if _ % 50 == 0:
            _log_diagnostics(nodes, network, "no_double_finalization_running", _)
    
    # Check that all nodes have same blocks at each height
    for height in range(min(len(node.get_blockchain()) for node in nodes)):
        block_hashes_at_height = set()
        for node in nodes:
            if height < len(node.get_blockchain()):
                block_hashes_at_height.add(node.get_blockchain()[height].get_hash())
        
        assert len(block_hashes_at_height) == 1, \
            f"Multiple different blocks finalized at height {height}: {block_hashes_at_height}"
    
    print("PASSED: No double finalization detected (Safety guaranteed)")
    return True

def test_invalid_signature_rejection():
    """Test that messages with invalid signatures are rejected"""
    print("\n" + "="*80)
    print("TEST: Invalid Signature Rejection")
    print("="*80)
    
    chain_id = "test-chain"
    validators = [KeyPair() for _ in range(3)]
    validator_addresses = [v.get_address() for v in validators]
    
    logger = Logger("NETWORK", False)
    network = UnreliableNetwork(logger, enable_delays=False, loss_rate=0.0)
    
    node = BlockchainNode(
        node_id="node-0",
        chain_id=chain_id,
        keypair=validators[0],
        all_validator_addresses=validator_addresses,
        network=network,
        verbose=False
    )
    
    initial_balances = {v.get_address(): 1000 for v in validators}
    node.initialize_genesis(initial_balances)
    
    # Create transaction with wrong signature
    from execution.transaction import Transaction
    tx = Transaction(node.address, validator_addresses[1], 50, 0, chain_id)
    tx.sign(validators[0])
    
    # Tamper with signature
    tx.signature = b'invalid_signature_bytes_that_wont_verify_correctly_here'
    
    # Try to submit
    initial_pool_size = len(node.tx_pool)
    node.submit_transaction(tx)
    
    # Transaction should be rejected
    assert len(node.tx_pool) == initial_pool_size, \
        "Invalid transaction was accepted"
    
    print("PASSED: Invalid signatures rejected")
    return True

def test_deterministic_replay():
    """Test that replaying same sequence produces same result"""
    print("\n" + "="*80)
    print("TEST: Deterministic Replay")
    print("="*80)
    
    def run_scenario(seed):
        import random
        random.seed(seed)
        
        def next_seed():
            return random.getrandbits(256).to_bytes(32, byteorder="big")
        
        chain_id = "test-chain"
        validators = [KeyPair.from_seed(next_seed()) for _ in range(3)]
        validator_addresses = [v.get_address() for v in validators]
        
        logger = Logger("NETWORK", False)
        network = UnreliableNetwork(logger, enable_delays=False, loss_rate=0.0,
                                    duplicate_rate=0.0)
        
        nodes = []
        initial_balances = {v.get_address(): 1000 for v in validators}
        
        for i, keypair in enumerate(validators):
            node = BlockchainNode(
                node_id=f"node-{i}",
                chain_id=chain_id,
                keypair=keypair,
                all_validator_addresses=validator_addresses,
                network=network,
                verbose=False
            )
            nodes.append(node)
        
        validator_addresses = [n.address for n in nodes]
        for node in nodes:
            node.all_validators = validator_addresses
            node.consensus.all_validators = validator_addresses
            node.initialize_genesis(initial_balances)
        
        # Submit transactions
        for i in range(3):
            sender = nodes[i % len(nodes)]
            recipient = nodes[(i + 1) % len(nodes)].address
            tx = sender.create_transaction(recipient, 10)
            sender.submit_transaction(tx)
        
        # Run consensus
        for _ in range(100):
            # Network tick: advance time và deliver messages
            network.tick(0.01)
            
            # Node tick: xử lý messages và events
            for node in nodes:
                node.tick()
        
        # Get final state hashes
        return [node.consensus.current_state.get_hash() for node in nodes]
    
    # Run twice with same seed
    result1 = run_scenario(42)
    result2 = run_scenario(42)
    
    assert result1 == result2, \
        f"Deterministic replay failed: {result1} != {result2}"
    
    print("PASSED: Deterministic replay produces identical results")
    return True

def run_all_tests():
    """Run all end-to-end tests"""
    print("\n" + "="*80)
    print("RUNNING END-TO-END TESTS")
    print("="*80)
    
    tests = [
        test_single_block_finalization,
        test_no_double_finalization,
        test_invalid_signature_rejection,
        test_deterministic_replay
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"FAILED: {e}")
            results.append((test_func.__name__, False))
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\nALL TESTS PASSED!")
        return 0
    else:
        print("\nSOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)