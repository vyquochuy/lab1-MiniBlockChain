"""
Consensus Layer - Two-Phase Consensus Engine
Tendermint-inspired consensus with Prevote and Precommit phases
"""
from typing import List, Optional, Dict
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from .block import Block, BlockHeader, BlockProposal
from .vote import Vote, VoteType, VoteCollector
from crypto.keys import KeyPair
from execution.state import State
from execution.transaction import Transaction
from execution.executor import Executor

class ConsensusEngine:
    """Manages consensus process for block finalization"""
    
    def __init__(self, chain_id: str, validator_keypair: KeyPair, 
                 all_validators: List[str], logger):
        self.chain_id = chain_id
        self.validator_keypair = validator_keypair
        self.validator_address = validator_keypair.get_address()
        self.all_validators = all_validators
        self.total_validators = len(all_validators)
        self.logger = logger
        
        # Consensus state
        self.current_height = 0
        self.current_state = State()
        self.blockchain = []  # List of finalized blocks
        self.vote_collector = VoteCollector(self.total_validators)
        
        # Pending data
        self.pending_blocks = {}  # height -> {block_hash -> Block}
        self.pending_votes = []  # Votes received before block proposal
        
        # Phase tracking
        self.prevoted = {}  # height -> block_hash we prevoted for
        self.precommitted = {}  # height -> block_hash we precommitted for
        
        # Executor
        self.executor = Executor()
    
    def initialize_genesis(self, initial_balances: Dict[str, int]):
        """Initialize blockchain with genesis block"""
        genesis_state = State()
        for address, balance in initial_balances.items():
            genesis_state.set_balance(address, balance)
        
        self.current_state = genesis_state
        genesis_block = Block.create_genesis(self.chain_id, genesis_state.get_hash())
        genesis_block.mark_finalized()
        self.blockchain.append(genesis_block)
        self.current_height = 1
        
        self.logger.log("CONSENSUS", f"Genesis block created at height 0")
        self.logger.log("STATE", f"Initial state hash: {genesis_state.get_hash()}")
    
    def propose_block(self, transactions: List[Transaction]) -> BlockProposal:
        """Propose a new block"""
        parent_block = self.blockchain[-1]
        parent_hash = parent_block.get_hash()
        
        # Execute transactions on current state
        new_state, executed_txs = self.executor.execute_transactions(
            self.current_state, transactions
        )
        
        # Create block header
        header = BlockHeader(
            height=self.current_height,
            parent_hash=parent_hash,
            state_hash=new_state.get_hash(),
            tx_root=self._compute_tx_root(transactions),
            timestamp=int(time.time()),
            proposer=self.validator_address
        )
        
        block = Block(header, transactions)
        proposal = BlockProposal(block, self.validator_address)
        
        self.logger.log("CONSENSUS", 
                       f"Proposed block at height {self.current_height}, "
                       f"hash: {block.get_hash()[:16]}..., "
                       f"txs: {len(transactions)}")
        
        return proposal
    
    def receive_proposal(self, proposal: BlockProposal):
        """Receive and validate a block proposal"""
        block = proposal.block
        height = block.header.height
        block_hash = block.get_hash()
        
        # Store pending block
        if height not in self.pending_blocks:
            self.pending_blocks[height] = {}
        self.pending_blocks[height][block_hash] = block
        
        self.logger.log("CONSENSUS", 
                       f"Received proposal at height {height}, "
                       f"hash: {block_hash[:16]}...")
        
        # Validate and prevote
        if self._validate_proposal(proposal):
            self._send_prevote(height, block_hash)
        
        # Process any pending votes
        self._process_pending_votes()
    
    def receive_vote(self, vote: Vote):
        """Receive and process a vote"""
        if not vote.verify():
            self.logger.log("CONSENSUS", f"Invalid vote signature from {vote.validator_address[:16]}...")
            return
        
        # Check if we have the block yet
        height = vote.height
        block_hash = vote.block_hash
        
        if height not in self.pending_blocks or block_hash not in self.pending_blocks[height]:
            # Block not received yet, store vote for later
            self.pending_votes.append(vote)
            return
        
        # Add vote to collector
        is_new = self.vote_collector.add_vote(vote)
        if not is_new:
            return  # Duplicate vote
        
        self.logger.log("VOTE", 
                       f"{vote.vote_type.value.upper()} from {vote.validator_address[:16]}... "
                       f"for height {height}, block {block_hash[:16]}...")
        
        # Check for transitions
        self._check_phase_transitions(height, block_hash)
    
    def _validate_proposal(self, proposal: BlockProposal) -> bool:
        """Validate block proposal"""
        block = proposal.block
        
        # Check height
        if block.header.height != self.current_height:
            return False
        
        # Check parent
        if len(self.blockchain) > 0:
            expected_parent = self.blockchain[-1].get_hash()
            if block.header.parent_hash != expected_parent:
                return False
        
        # Verify transactions
        for tx in block.transactions:
            if not tx.verify():
                return False
        
        # Verify state transition
        self.executor.reset_nonces()
        new_state, _ = self.executor.execute_transactions(
            self.current_state, block.transactions
        )
        
        if new_state.get_hash() != block.header.state_hash:
            return False
        
        return True
    
    def _send_prevote(self, height: int, block_hash: str):
        """Send prevote for a block"""
        if height in self.prevoted:
            return  # Already prevoted at this height
        
        vote = Vote(VoteType.PREVOTE, height, block_hash, 
                   self.validator_address, self.chain_id)
        vote.sign(self.validator_keypair)
        
        self.prevoted[height] = block_hash
        self.vote_collector.add_vote(vote)
        
        self.logger.log("VOTE", f"PREVOTE sent for height {height}, block {block_hash[:16]}...")
        
        return vote
    
    def _send_precommit(self, height: int, block_hash: str):
        """Send precommit for a block"""
        if height in self.precommitted:
            return  # Already precommitted at this height
        
        vote = Vote(VoteType.PRECOMMIT, height, block_hash,
                   self.validator_address, self.chain_id)
        vote.sign(self.validator_keypair)
        
        self.precommitted[height] = block_hash
        self.vote_collector.add_vote(vote)
        
        self.logger.log("VOTE", f"PRECOMMIT sent for height {height}, block {block_hash[:16]}...")
        
        return vote
    
    def _check_phase_transitions(self, height: int, block_hash: str):
        """Check if we can transition to next phase"""
        # Prevote -> Precommit transition
        if (height not in self.precommitted and 
            self.vote_collector.has_prevote_majority(height, block_hash)):
            
            prevote_count = self.vote_collector.get_prevote_count(height, block_hash)
            self.logger.log("CONSENSUS", 
                           f"Prevote majority reached at height {height}: "
                           f"{prevote_count}/{self.total_validators}")
            self._send_precommit(height, block_hash)
        
        # Precommit -> Finalization
        if self.vote_collector.has_precommit_majority(height, block_hash):
            precommit_count = self.vote_collector.get_precommit_count(height, block_hash)
            self.logger.log("CONSENSUS",
                           f"Precommit majority reached at height {height}: "
                           f"{precommit_count}/{self.total_validators}")
            self._finalize_block(height, block_hash)
    
    def _finalize_block(self, height: int, block_hash: str):
        """Finalize a block with sufficient precommits"""
        if height not in self.pending_blocks or block_hash not in self.pending_blocks[height]:
            return
        
        block = self.pending_blocks[height][block_hash]
        
        # Check if already finalized
        if block.is_finalized():
            return
        
        # Execute state transition
        self.executor.reset_nonces()
        new_state, executed_txs = self.executor.execute_transactions(
            self.current_state, block.transactions
        )
        
        # Finalize block
        block.mark_finalized()
        self.blockchain.append(block)
        self.current_state = new_state
        self.current_height += 1
        
        self.logger.log("CONSENSUS", 
                       f"✓ FINALIZED block at height {height}, "
                       f"hash: {block_hash[:16]}..., "
                       f"state: {new_state.get_hash()[:16]}..., "
                       f"executed_txs: {len(executed_txs)}")
        self.logger.log("STATE", f"New state hash: {new_state.get_hash()}")
    
    def _process_pending_votes(self):
        """Process votes that were received before block proposal"""
        processed = []
        for vote in self.pending_votes:
            height = vote.height
            block_hash = vote.block_hash
            
            if height in self.pending_blocks and block_hash in self.pending_blocks[height]:
                self.receive_vote(vote)
                processed.append(vote)
        
        for vote in processed:
            self.pending_votes.remove(vote)
    
    def _compute_tx_root(self, transactions: List[Transaction]) -> str:
        """Compute merkle root of transactions"""
        from crypto.hashing import hash_dict_hex
        tx_hashes = [tx.tx_hash for tx in transactions]
        return hash_dict_hex({"transactions": tx_hashes})
    
    def get_chain_info(self) -> Dict:
        """Get current chain information"""
        return {
            "current_height": self.current_height,
            "finalized_blocks": len(self.blockchain),
            "current_state_hash": self.current_state.get_hash(),
            "validator_address": self.validator_address
        }