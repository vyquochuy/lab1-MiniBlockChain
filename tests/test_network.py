"""
Unit Tests for Network Layer
Tests unreliable network simulation
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from network.network import UnreliableNetwork
from node import Logger
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
    
    # Wait for delivery
    time.sleep(0.02)
    
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
    start_time = time.time()
    network.send_message("alice", "bob", "TEST", {"data": "hello"})
    
    # Try to deliver immediately (should be empty)
    messages = network.deliver_ready_messages()
    assert len(messages) == 0, "Message delivered too early"
    
    # Wait for delay
    time.sleep(0.11)
    
    # Now should be delivered
    messages = network.deliver_ready_messages()
    elapsed = time.time() - start_time
    
    assert len(messages) == 1, "Message not delivered"
    assert elapsed >= 0.05, f"Message delivered too early: {elapsed}s"
    
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
    
    # Wait and deliver
    time.sleep(0.02)
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
    
    # Wait and deliver
    time.sleep(0.02)
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
    
    # Send messages in sequence
    for i in range(10):
        network.send_message("alice", "bob", "TEST", {"seq": i})
        time.sleep(0.001)  # Small delay between sends
    
    # Wait for all deliveries
    time.sleep(0.1)
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
    
    # Wait and deliver
    time.sleep(0.02)
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
    
    # Should be deliverable immediately
    time.sleep(0.005)
    messages = network.deliver_ready_messages()
    
    assert len(messages) == 1, "Message not delivered in zero-delay mode"
    
    print("PASSED: Zero-delay mode works for testing")
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
        test_zero_delay_mode
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
        status = "PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\nALL NETWORK TESTS PASSED!")
        return 0
    else:
        print("\nSOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_all_network_tests()
    sys.exit(exit_code)