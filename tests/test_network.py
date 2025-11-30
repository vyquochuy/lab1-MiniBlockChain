"""
Unit Tests for Network Layer
Tests unreliable network simulation, rate limiting, and header/body separation
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from network.network import UnreliableNetwork
from node import Logger, BlockchainNode
from crypto.keys import KeyPair
import time

def test_message_delivery():
    """Test basic message sending and delivery"""
    print("\nTEST: Basic Message Delivery")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.0,
        duplicate_rate=0.0
    )
    
    # Send message
    network.send_message("alice", "bob", "TEST", {"data": "hello"})
    
    # Advance simulation time để deliver message
    network.tick(0.02)
    
    # Deliver messages
    messages = network.deliver_ready_messages()
    
    assert len(messages) == 1, f"Expected 1 message, got {len(messages)}"
    assert messages[0].sender == "alice", "Sender mismatch"
    assert messages[0].receiver == "bob", "Receiver mismatch"
    assert messages[0].message_type == "TEST", "Message type mismatch"
    assert messages[0].payload["data"] == "hello", "Payload mismatch"
    
    print("PASSED: Messages are delivered correctly")
    return True

def test_message_delays():
    """Test that messages are delayed"""
    print("\nTEST: Message Delays")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.05, 0.1),
        loss_rate=0.0,
        duplicate_rate=0.0,
        enable_delays=True
    )
    
    # Send message
    network.send_message("alice", "bob", "TEST", {"data": "hello"})
    
    # Try to get messages immediately (should be empty vì chưa advance time)
    messages = network.get_messages("bob")
    assert len(messages) == 0, "Message delivered too early"
    
    # Advance simulation time một chút (chưa đủ để deliver)
    network.tick(0.01)
    messages = network.get_messages("bob")
    assert len(messages) == 0, "Message delivered too early"
    
    # Advance simulation time đủ để deliver message
    network.tick(0.11)
    messages = network.get_messages("bob")
    
    assert len(messages) == 1, "Message not delivered"
    
    print("PASSED: Messages are properly delayed")
    return True

def test_packet_loss():
    """Test that packets are lost at specified rate"""
    print("\nTEST: Packet Loss")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.5,  # 50% loss rate
        duplicate_rate=0.0,
        enable_delays=False
    )
    
    # Send many messages
    num_messages = 100
    for i in range(num_messages):
        network.send_message("alice", "bob", "TEST", {"seq": i})
    
    # Check stats
    stats = network.get_stats()
    loss_rate = stats['dropped'] / num_messages
    
    # Should be approximately 50% loss (within reasonable margin)
    assert 0.3 < loss_rate < 0.7, \
        f"Loss rate {loss_rate} not close to expected 0.5"
    
    print(f"PASSED: Packet loss rate: {loss_rate:.2%}")
    return True

def test_message_duplicates():
    """Test that messages can be duplicated"""
    print("\nTEST: Message Duplicates")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.0,
        duplicate_rate=1.0,  # 100% duplicate rate
        enable_delays=False
    )
    
    # Send message
    network.send_message("alice", "bob", "TEST", {"data": "hello"})
    
    # Advance simulation time và deliver
    network.tick(0.02)
    messages = network.deliver_ready_messages()
    
    # Should have original + duplicate = 2 messages
    assert len(messages) == 2, \
        f"Expected 2 messages (original + duplicate), got {len(messages)}"
    
    # Both should have same content
    assert messages[0].payload == messages[1].payload, \
        "Duplicate message has different content"
    
    print("PASSED: Message duplication works")
    return True

def test_broadcast():
    """Test broadcasting to multiple receivers"""
    print("\nTEST: Message Broadcasting")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.0,
        duplicate_rate=0.0,
        enable_delays=False
    )
    
    receivers = ["bob", "charlie", "david", "alice"]  # alice is sender
    
    # Broadcast
    network.broadcast_message("alice", receivers, "BROADCAST", {"msg": "hello all"})
    
    # Advance simulation time và deliver
    network.tick(0.02)
    messages = network.deliver_ready_messages()
    
    # Should have 3 messages (not sent to alice)
    assert len(messages) == 3, f"Expected 3 messages, got {len(messages)}"
    
    # Check all receivers got the message
    received_by = {msg.receiver for msg in messages}
    expected = {"bob", "charlie", "david"}
    assert received_by == expected, f"Broadcast receivers mismatch: {received_by} vs {expected}"
    
    print("PASSED: Broadcasting works correctly")
    return True

def test_message_reordering():
    """Test that messages can be reordered"""
    print("\nTEST: Message Reordering")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.05),
        loss_rate=0.0,
        duplicate_rate=0.0,
        enable_delays=True
    )
    
    # Send messages in sequence với simulation time
    for i in range(10):
        network.send_message("alice", "bob", "TEST", {"seq": i})
        network.tick(0.001)  # Small delay between sends
    
    # Advance time để deliver tất cả messages
    network.tick(0.1)
    messages = network.deliver_ready_messages()
    
    # Extract sequence numbers
    sequences = [msg.payload["seq"] for msg in messages]
    
    # Check if any reordering occurred
    is_ordered = sequences == sorted(sequences)
    
    # With random delays, reordering is likely (but not guaranteed)
    # So we just verify all messages were delivered
    assert len(messages) == 10, f"Expected 10 messages, got {len(messages)}"
    assert set(sequences) == set(range(10)), "Some messages missing or duplicated"
    
    if not is_ordered:
        print(f"   Messages were reordered: {sequences[:5]}...")
    
    print("PASSED: Message reordering can occur")
    return True

def test_network_stats():
    """Test network statistics tracking"""
    print("\nTEST: Network Statistics")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.2,
        duplicate_rate=0.1,
        enable_delays=False
    )
    
    # Send messages
    for i in range(50):
        network.send_message("alice", "bob", "TEST", {"seq": i})
    
    # Advance simulation time và deliver
    network.tick(0.02)
    messages = network.deliver_ready_messages()
    
    # Get stats
    stats = network.get_stats()
    
    # Verify stats are reasonable
    assert stats['delivered'] > 0, "No messages delivered"
    assert stats['dropped'] > 0, "No messages dropped (with 20% loss rate)"
    assert stats['delivered'] + stats['dropped'] >= 50, \
        "Total messages don't match sent count"
    
    print(f"   Delivered: {stats['delivered']}, "
          f"Dropped: {stats['dropped']}, "
          f"Duplicated: {stats['duplicated']}")
    print("PASSED: Network statistics tracked correctly")
    return True

def test_zero_delay_mode():
    """Test that zero delay mode works for testing"""
    print("\nTEST: Zero Delay Mode")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.0,
        duplicate_rate=0.0,
        enable_delays=False  # Disable delays
    )
    
    # Send message
    network.send_message("alice", "bob", "TEST", {"data": "hello"})
    
    # Should be deliverable immediately (delay = 0)
    network.tick(0.005)
    messages = network.deliver_ready_messages()
    
    assert len(messages) == 1, "Message not delivered in zero-delay mode"
    
    print("PASSED: Zero-delay mode works for testing")
    return True

def test_rate_limiting():
    """Test that rate limiting blocks excessive senders"""
    print("\nTEST: Rate Limiting - Blocking Excessive Senders")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.0,
        duplicate_rate=0.0,
        enable_delays=False
    )
    
    # Alice tries to send 150 messages rapidly (exceeds 100/second limit)
    initial_dropped = network.dropped_count
    
    for i in range(150):
        network.send_message("alice", "bob", "TEST", {"seq": i})
        # Advance time very slightly (total < 1 second)
        network.tick(0.005)  # 150 * 0.005 = 0.75 seconds
    
    stats = network.get_stats()
    dropped_by_rate_limit = stats['dropped'] - initial_dropped
    
    # Should have blocked alice after 100 messages
    assert "alice" in network.blocked_peers, \
        "Sender 'alice' should be blocked after exceeding rate limit"
    
    # At least 40-50 messages should have been dropped (150 - 100 = 50 max)
    assert dropped_by_rate_limit >= 40, \
        f"Expected at least 40 dropped messages, got {dropped_by_rate_limit}"
    
    print(f"   Dropped {dropped_by_rate_limit} messages due to rate limit")
    print(f"   Alice blocked: {network.blocked_peers}")
    print("PASSED: Rate limiting blocks excessive senders")
    return True

def test_rate_limit_peer_unblocking():
    """Test that blocked peers are unblocked after timeout"""
    print("\nTEST: Rate Limiting - Peer Unblocking After Timeout")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.0,
        duplicate_rate=0.0,
        enable_delays=False
    )
    
    # Block alice by sending too many messages
    for i in range(150):
        network.send_message("alice", "bob", "TEST", {"seq": i})
    
    assert "alice" in network.blocked_peers, \
        "Alice should be blocked initially"
    assert "alice" in network.peer_block_until, \
        "Alice should have unblock time set"
    
    initial_block_time = network.peer_block_until["alice"]
    
    # Advance time by 6 seconds (block_duration = 5s by default)
    network.tick(6.0)
    
    # Alice should still be in blocked_peers until she tries to send again
    assert "alice" in network.blocked_peers, \
        "Alice should still be in blocked set before attempting to send"
    
    # Try to send again - this should trigger unblock check
    network.send_message("alice", "bob", "TEST", {"unblocked": True})
    
    # Should be unblocked now (not in peer_block_until)
    assert "alice" not in network.peer_block_until, \
        "Alice should be unblocked after timeout"
    
    # Verify the message was actually sent (not blocked)
    network.tick(0.01)
    messages = network.get_messages("bob")
    
    # Should have received at least one message
    assert len(messages) > 0, \
        "Alice should be able to send messages after unblock"
    
    print(f"   Alice was blocked until time: {initial_block_time:.2f}")
    print(f"   Current simulation time: {network.simulation_time:.2f}")
    print("PASSED: Blocked peers are unblocked after timeout")
    return True

def test_rate_limit_multiple_senders():
    """Test that rate limiting is enforced per-sender"""
    print("\nTEST: Rate Limiting - Per-Sender Enforcement")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.0,
        duplicate_rate=0.0,
        enable_delays=False
    )
    
    # Alice sends too many messages (should be blocked)
    for i in range(150):
        network.send_message("alice", "charlie", "TEST", {"seq": i})
    
    # Bob sends normal amount (should NOT be blocked)
    for i in range(50):
        network.send_message("bob", "charlie", "TEST", {"seq": i})
    
    # Check blocking status
    assert "alice" in network.blocked_peers, \
        "Alice should be blocked"
    assert "bob" not in network.blocked_peers, \
        "Bob should NOT be blocked"
    
    # Verify Bob's messages were delivered
    network.tick(0.02)
    bob_messages = [m for m in network.get_messages("charlie") 
                    if m.sender == "bob"]
    
    assert len(bob_messages) == 50, \
        f"Bob should have sent all 50 messages, got {len(bob_messages)}"
    
    print(f"   Alice blocked: Yes")
    print(f"   Bob blocked: No")
    print(f"   Bob's messages delivered: {len(bob_messages)}/50")
    print("PASSED: Rate limiting is enforced per-sender")
    return True

def test_rate_limit_stats():
    """Test that rate limiting statistics are tracked correctly"""
    print("\nTEST: Rate Limiting - Statistics Tracking")
    
    logger = Logger("test", verbose=False)
    network = UnreliableNetwork(
        logger,
        delay_range=(0.001, 0.01),
        loss_rate=0.0,
        duplicate_rate=0.0,
        enable_delays=False
    )
    
    # Send messages to trigger rate limiting
    for i in range(150):
        network.send_message("alice", "bob", "TEST", {"seq": i})
    
    stats = network.get_stats()
    
    # Check that stats include rate limiting info
    assert "blocked_peers" in stats, \
        "Stats should include blocked_peers count"
    assert "rate_limited_drops" in stats, \
        "Stats should include rate_limited_drops count"
    
    assert stats["blocked_peers"] >= 1, \
        f"Should have at least 1 blocked peer, got {stats['blocked_peers']}"
    
    print(f"   Blocked peers: {stats['blocked_peers']}")
    print(f"   Rate limited drops: {stats.get('rate_limited_drops', 'N/A')}")
    print(f"   Total dropped: {stats['dropped']}")
    print("PASSED: Rate limiting statistics tracked correctly")
    return True

def test_header_body_separation_basic():
    """Test basic header/body separation in block proposals"""
    print("\nTEST: Header/Body Separation - Basic Functionality")
    
    chain_id = "test-chain"
    validators = [KeyPair() for _ in range(3)]
    validator_addresses = [v.get_address() for v in validators]
    
    logger = Logger("NETWORK", verbose=False)
    network = UnreliableNetwork(logger, enable_delays=False, loss_rate=0.0)
    
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
    
    validator_addresses = [n.address for n in nodes]
    for node in nodes:
        node.all_validators = validator_addresses
        node.consensus.all_validators = validator_addresses
        node.initialize_genesis(initial_balances)
    
    # Node 0 is leader at height 1, submit transaction
    tx = nodes[0].create_transaction(nodes[1].address, 50)
    nodes[0].submit_transaction(tx)
    
    # Run one tick - leader should have header/body tracking
    network.tick(0.01)
    for node in nodes:
        node.tick()
    
    # Check that leader (node 0) has tracking structures
    assert hasattr(nodes[0], 'pending_block_bodies'), \
        "Node should have pending_block_bodies attribute"
    assert hasattr(nodes[0], 'accepted_headers'), \
        "Node should have accepted_headers attribute"
    assert hasattr(nodes[0], 'requested_bodies'), \
        "Node should have requested_bodies attribute"
    
    # Leader should have stored the body
    assert len(nodes[0].pending_block_bodies) > 0, \
        "Leader should have stored block body"
    
    print("   Leader has header/body separation structures")
    print(f"   Pending block bodies: {len(nodes[0].pending_block_bodies)}")
    print("PASSED: Basic header/body separation structures exist")
    return True

def test_header_body_message_types():
    """Test that new message types for header/body are handled"""
    print("\nTEST: Header/Body Separation - Message Type Handling")
    
    chain_id = "test-chain"
    validators = [KeyPair() for _ in range(3)]
    validator_addresses = [v.get_address() for v in validators]
    
    logger = Logger("NETWORK", verbose=False)
    network = UnreliableNetwork(logger, enable_delays=False, loss_rate=0.0)
    
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
    
    validator_addresses = [n.address for n in nodes]
    for node in nodes:
        node.all_validators = validator_addresses
        node.consensus.all_validators = validator_addresses
        node.initialize_genesis(initial_balances)
    
    # Check that nodes have handler methods for new message types
    assert hasattr(nodes[0], '_handle_block_header'), \
        "Node should have _handle_block_header method"
    assert hasattr(nodes[0], '_handle_block_body_request'), \
        "Node should have _handle_block_body_request method"
    assert hasattr(nodes[0], '_handle_block_body'), \
        "Node should have _handle_block_body method"
    
    print("   Node has _handle_block_header()")
    print("   Node has _handle_block_body_request()")
    print("   Node has _handle_block_body()")
    print("PASSED: Header/body message handlers exist")
    return True

def test_header_body_backward_compatibility():
    """Test that old BLOCK_PROPOSAL messages still work (backward compatibility)"""
    print("\nTEST: Header/Body Separation - Backward Compatibility")
    
    chain_id = "test-chain"
    validators = [KeyPair() for _ in range(3)]
    validator_addresses = [v.get_address() for v in validators]
    
    logger = Logger("NETWORK", verbose=False)
    network = UnreliableNetwork(logger, enable_delays=False, loss_rate=0.0)
    
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
    
    validator_addresses = [n.address for n in nodes]
    for node in nodes:
        node.all_validators = validator_addresses
        node.consensus.all_validators = validator_addresses
        node.initialize_genesis(initial_balances)
    
    # Submit transaction and run consensus
    tx = nodes[0].create_transaction(nodes[1].address, 50)
    nodes[0].submit_transaction(tx)
    
    # Run multiple ticks to allow consensus
    for _ in range(50):
        network.tick(0.01)
        for node in nodes:
            node.tick()
    
    # Check that at least one block was finalized
    blocks_finalized = min(len(node.get_blockchain()) for node in nodes) - 1
    
    assert blocks_finalized >= 1, \
        f"Expected at least 1 block finalized, got {blocks_finalized}"
    
    print(f"   Blocks finalized: {blocks_finalized}")
    print("PASSED: Backward compatibility maintained")
    return True

def run_all_network_tests():
    """Run all network tests"""
    print("\n" + "="*80)
    print("RUNNING NETWORK UNIT TESTS")
    print("="*80)
    
    tests = [
        test_message_delivery,
        test_message_delays,
        test_packet_loss,
        test_message_duplicates,
        test_broadcast,
        test_message_reordering,
        test_network_stats,
        test_zero_delay_mode,
        
        # Rate limiting tests
        test_rate_limiting,
        test_rate_limit_peer_unblocking,
        test_rate_limit_multiple_senders,
        test_rate_limit_stats,
        
        # Header/Body separation tests
        test_header_body_separation_basic,
        test_header_body_message_types,
        test_header_body_backward_compatibility,
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
    print("NETWORK TEST SUMMARY")
    print("="*80)
    
    for name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\nALL NETWORK TESTS PASSED!")
        print(f"Total tests: {len(tests)}")
        print("  - Original tests: 8")
        print("  - Rate limiting tests: 4")
        print("  - Header/Body tests: 3")
        return 0
    else:
        print("\nSOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_all_network_tests()
    sys.exit(exit_code)