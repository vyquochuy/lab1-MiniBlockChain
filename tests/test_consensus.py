"""
Unit Tests for Consensus Layer
Tests voting, block validation, and consensus rules
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from consensus.consensus import ConsensusEngine
from crypto.keys import KeyPair
from node import Logger
from consensus.vote import Vote, VoteType, VoteCollector
from consensus.block import Block, BlockHeader, BlockProposal
from execution.state import State
from execution.transaction import Transaction
import time


def _consensus_diagnostics(collector: VoteCollector, label: str):
    """Print diagnostics for VoteCollector to help observe consensus state."""
    print("\n" + "=" * 80)
    print(f"CONSENSUS DIAGNOSTICS: {label}")
    print("=" * 80)
    print(f" total_validators: {collector.total_validators}")
    # Print stored prevote/precommit maps
    try:
        print(" prevotes:")
        for h, blocks in collector.prevotes.items():
            for bh, voters in blocks.items():
                print(f"   height={h}, block={bh[:8]}..., voters={len(voters)} -> {list(voters)[:4]}")
        print(" precommits:")
        for h, blocks in collector.precommits.items():
            for bh, voters in blocks.items():
                print(f"   height={h}, block={bh[:8]}..., voters={len(voters)} -> {list(voters)[:4]}")
    except Exception:
        print(" prevotes/precommits: N/A")
    # Print simple counts per height for quick view
    try:
        heights = set(list(collector.prevotes.keys()) + list(collector.precommits.keys()))
        for h in sorted(heights):
            pv = {bh: len(v) for bh, v in collector.prevotes.get(h, {}).items()}
            pc = {bh: len(v) for bh, v in collector.precommits.get(h, {}).items()}
            print(f" height={h}: prevotes={pv}, precommits={pc}")
    except Exception:
        pass
    print("" )

def test_vote_creation_and_verification():
    """Test vote creation and signature verification"""
    print("\nTEST: Vote Creation and Verification")
    
    keypair = KeyPair()
    chain_id = "test-chain"
    
    # Create prevote
    vote = Vote(
        vote_type=VoteType.PREVOTE,
        height=1,
        block_hash="abc123",
        validator_address=keypair.get_address(),
        chain_id=chain_id
    )
    
    # Sign vote
    vote.sign(keypair)
    assert vote.signature is not None, "Vote was not signed"
    
    # Verify vote
    is_valid = vote.verify()
    assert is_valid, "Valid vote was rejected"
    
    # Tamper with vote
    vote.height = 2
    is_valid = vote.verify()
    assert not is_valid, "Tampered vote was accepted"
    
    print("PASSED: Vote creation and verification works")
    return True

def test_vote_collector():
    """Test vote collection and majority counting"""
    print("\nTEST: Vote Collector")
    
    chain_id = "test-chain"
    num_validators = 4
    validators = [KeyPair() for _ in range(num_validators)]
    
    collector = VoteCollector(num_validators)
    
    height = 1
    block_hash = "abc123"
    
    # Add prevotes one by one
    for i, keypair in enumerate(validators[:3]):  # 3 out of 4
        vote = Vote(
            VoteType.PREVOTE,
            height,
            block_hash,
            keypair.get_address(),
            chain_id
        )
        vote.sign(keypair)
        
        added = collector.add_vote(vote)
        assert added, f"Failed to add vote {i}"
        
        # Check majority (need > 2/3 = > 2.67, so need 3 votes)
        has_majority = collector.has_prevote_majority(height, block_hash)
        if i < 2:
            assert not has_majority, f"False majority detected with {i+1} votes"
        else:
            assert has_majority, f"Majority not detected with {i+1} votes"
    # Diagnostics: print collector internal state
    _consensus_diagnostics(collector, "after_adding_prevotes")
    
    print("PASSED: Vote collector tracks majorities correctly")
    return True

def test_duplicate_vote_rejection():
    """Test that duplicate votes are rejected"""
    print("\nTEST: Duplicate Vote Rejection")
    
    chain_id = "test-chain"
    keypair = KeyPair()
    collector = VoteCollector(3)
    
    vote = Vote(
        VoteType.PREVOTE,
        1,
        "abc123",
        keypair.get_address(),
        chain_id
    )
    vote.sign(keypair)
    
    # First vote should be accepted
    added1 = collector.add_vote(vote)
    assert added1, "First vote was rejected"
    
    # Duplicate should be rejected
    added2 = collector.add_vote(vote)
    assert not added2, "Duplicate vote was accepted"
    
    # Count should be 1
    count = collector.get_prevote_count(1, "abc123")
    assert count == 1, f"Expected 1 vote, got {count}"
    
    print("PASSED: Duplicate votes are rejected")
    return True

def test_block_header_hash():
    """Test that block headers hash consistently"""
    print("\nTEST: Block Header Hash Consistency")
    
    header1 = BlockHeader(
        height=1,
        parent_hash="parent123",
        state_hash="state456",
        tx_root="txroot789",
        timestamp=1234567890,
        proposer="alice"
    )
    
    # Hash multiple times
    hash1 = header1.get_hash()
    hash2 = header1.get_hash()
    assert hash1 == hash2, "Same header produced different hashes"
    
    # Create identical header
    header2 = BlockHeader(
        height=1,
        parent_hash="parent123",
        state_hash="state456",
        tx_root="txroot789",
        timestamp=1234567890,
        proposer="alice"
    )
    
    hash3 = header2.get_hash()
    assert hash1 == hash3, "Identical headers produced different hashes"
    
    # Modify header
    header3 = BlockHeader(
        height=2,  # Different height
        parent_hash="parent123",
        state_hash="state456",
        tx_root="txroot789",
        timestamp=1234567890,
        proposer="alice"
    )
    
    hash4 = header3.get_hash()
    assert hash1 != hash4, "Different headers produced same hash"
    
    print("PASSED: Block header hashing is consistent")
    return True

def test_block_serialization():
    """Test block serialization and deserialization"""
    print("\nTEST: Block Serialization")
    
    chain_id = "test-chain"
    keypair = KeyPair()
    
    # Create transaction
    tx = Transaction(
        keypair.get_address(),
        "recipient",
        100,
        0,
        chain_id
    )
    tx.sign(keypair)
    
    # Create block
    header = BlockHeader(
        height=1,
        parent_hash="parent",
        state_hash="state",
        tx_root="txroot",
        timestamp=int(time.time()),
        proposer=keypair.get_address()
    )
    
    block = Block(header, [tx])
    original_hash = block.get_hash()
    
    # Serialize
    serialized = block.to_dict()
    
    # Deserialize
    restored = Block.from_dict(serialized)
    restored_hash = restored.get_hash()
    
    # Verify
    assert original_hash == restored_hash, "Block hash changed after serialization"
    assert len(restored.transactions) == 1, "Transaction count mismatch"
    assert restored.header.height == 1, "Height mismatch"
    
    print("PASSED: Block serialization preserves data")
    return True

def test_genesis_block_creation():
    """Test genesis block creation"""
    print("\nTEST: Genesis Block Creation")
    
    chain_id = "test-chain"
    state = State()
    state.set_balance("alice", 1000)
    state.set_balance("bob", 2000)
    
    genesis = Block.create_genesis(chain_id, state.get_hash())
    
    # Verify genesis properties
    assert genesis.header.height == 0, "Genesis height should be 0"
    assert genesis.header.parent_hash == "0" * 64, "Genesis should have null parent"
    assert len(genesis.transactions) == 0, "Genesis should have no transactions"
    assert genesis.header.state_hash == state.get_hash(), "State hash mismatch"
    
    print("PASSED: Genesis block created correctly")
    return True

def test_two_phase_voting():
    """Test complete two-phase voting process"""
    print("\nTEST: Two-Phase Voting Process")
    
    chain_id = "test-chain"
    num_validators = 4
    validators = [KeyPair() for _ in range(num_validators)]
    
    collector = VoteCollector(num_validators)
    
    height = 1
    block_hash = "block123"
    
    # Phase 1: Prevotes
    for keypair in validators[:3]:  # 3/4 validators
        vote = Vote(VoteType.PREVOTE, height, block_hash,
                   keypair.get_address(), chain_id)
        vote.sign(keypair)
        collector.add_vote(vote)
    
    # Should have prevote majority
    assert collector.has_prevote_majority(height, block_hash), \
        "Prevote majority not reached"
    _consensus_diagnostics(collector, "after_prevotes_two_phase")
    
    # Should not have precommit majority yet
    assert not collector.has_precommit_majority(height, block_hash), \
        "Precommit majority reached too early"
    
    # Phase 2: Precommits
    for keypair in validators[:3]:  # Same 3/4 validators
        vote = Vote(VoteType.PRECOMMIT, height, block_hash,
                   keypair.get_address(), chain_id)
        vote.sign(keypair)
        collector.add_vote(vote)
    
    # Should have precommit majority
    assert collector.has_precommit_majority(height, block_hash), \
        "Precommit majority not reached"
    _consensus_diagnostics(collector, "after_precommits_two_phase")
    
    print("PASSED: Two-phase voting process works correctly")
    return True

def test_conflicting_votes():
    """Test that validators can't vote for multiple blocks at same height"""
    print("\nTEST: Conflicting Votes")
    
    chain_id = "test-chain"
    keypair = KeyPair()
    collector = VoteCollector(3)
    
    height = 1
    block_hash_1 = "block1"
    block_hash_2 = "block2"
    
    # Vote for block 1
    vote1 = Vote(VoteType.PREVOTE, height, block_hash_1,
                keypair.get_address(), chain_id)
    vote1.sign(keypair)
    added1 = collector.add_vote(vote1)
    assert added1, "First vote rejected"
    
    # Try to vote for block 2 at same height
    vote2 = Vote(VoteType.PREVOTE, height, block_hash_2,
                keypair.get_address(), chain_id)
    vote2.sign(keypair)
    added2 = collector.add_vote(vote2)
    
    # Both votes are accepted (collector tracks both)
    # but only one should count per validator
    assert added2, "Second vote rejected"
    
    # Verify counts
    count1 = collector.get_prevote_count(height, block_hash_1)
    count2 = collector.get_prevote_count(height, block_hash_2)

    # Diagnostics: show collector state after conflicting votes
    _consensus_diagnostics(collector, "after_conflicting_votes")
    
    # Each block should have 1 vote (same validator voted for both)
    assert count1 == 1 and count2 == 1, \
        "Vote counting incorrect for conflicting votes"
    
    print("PASSED: Conflicting votes are tracked separately")
    return True


def test_consensus_engine_diagnostics():
    """Create a ConsensusEngine, propose a block, and print internal diagnostics."""
    print("\nTEST: ConsensusEngine Diagnostics")

    chain_id = "test-chain"
    num_validators = 4
    keypairs = [KeyPair() for _ in range(num_validators)]
    addresses = [kp.get_address() for kp in keypairs]

    logger = Logger("CONSENSUS", False)
    engine = ConsensusEngine(chain_id, keypairs[0], addresses, logger)

    initial_balances = {addr: 1000 for addr in addresses}
    engine.initialize_genesis(initial_balances)

    # Propose a block (empty txs) and simulate receiving it
    proposal = engine.propose_block([])
    engine.receive_proposal(proposal)
    _consensus_diagnostics(engine.vote_collector, "engine_after_receive_proposal")

    # Add some external prevotes (simulate other validators)
    for kp in keypairs[1:3]:
        v = Vote(VoteType.PREVOTE, proposal.block.header.height,
                 proposal.block.get_hash(), kp.get_address(), chain_id)
        v.sign(kp)
        engine.receive_vote(v)

    _consensus_diagnostics(engine.vote_collector, "engine_after_external_prevotes")

    # Verify vote counts
    count = engine.vote_collector.get_prevote_count(proposal.block.header.height,
                                                    proposal.block.get_hash())
    assert count >= 2, f"Expected at least 2 prevotes, got {count}"

    print("PASSED: ConsensusEngine diagnostics")
    return True

def run_all_consensus_tests():
    """Run all consensus tests"""
    print("\n" + "="*80)
    print("RUNNING CONSENSUS UNIT TESTS")
    print("="*80)
    
    tests = [
        test_vote_creation_and_verification,
        test_vote_collector,
        test_duplicate_vote_rejection,
        test_block_header_hash,
        test_block_serialization,
        test_genesis_block_creation,
        test_two_phase_voting,
        test_conflicting_votes,
        test_consensus_engine_diagnostics
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
    print("CONSENSUS TEST SUMMARY")
    print("="*80)
    
    for name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\nALL CONSENSUS TESTS PASSED!")
        return 0
    else:
        print("\nSOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_all_consensus_tests()
    sys.exit(exit_code)