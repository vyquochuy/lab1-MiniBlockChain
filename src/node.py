"""
Main Node Implementation
Integrates all layers: crypto, network, consensus, execution
"""
import os
import sys
import time

from crypto.keys import KeyPair
from consensus.vote import Vote
from typing import List, Dict, Any
from consensus.block import BlockProposal
from execution.transaction import Transaction
from network.network import UnreliableNetwork
from network.message import MessageType, Message
from consensus.consensus import ConsensusEngine

sys.path.append(os.path.dirname(__file__))
class Logger:
    """Simple logger for debugging and testing"""
    
    def __init__(self, node_id: str, verbose: bool = True):
        self.node_id = node_id
        self.verbose = verbose
        self.logs = []
    
    def log(self, category: str, message: str):
        """Log a message"""
        timestamp = time.time()
        log_entry = f"[{self.node_id[:8]}] [{category}] {message}"
        self.logs.append({
            "timestamp": timestamp,
            "node": self.node_id,
            "category": category,
            "message": message
        })
        if self.verbose:
            print(log_entry)
    
    def get_logs(self) -> List[Dict]:
        """Get all logs"""
        return self.logs

class BlockchainNode:
    """Full blockchain node with consensus"""
    
    def __init__(self, node_id: str, chain_id: str, keypair: KeyPair,
                 all_validator_addresses: List[str], network: UnreliableNetwork,
                 verbose: bool = True):
        self.node_id = node_id
        self.chain_id = chain_id
        self.keypair = keypair
        self.address = keypair.get_address()
        self.all_validators = all_validator_addresses
        self.network = network
        
        # Logger
        self.logger = Logger(self.address, verbose)
        
        # Consensus engine
        self.consensus = ConsensusEngine(
            chain_id=chain_id,
            validator_keypair=keypair,
            all_validators=all_validator_addresses,
            logger=self.logger
        )
        
        # Transaction pool
        self.tx_pool: List[Transaction] = []
        
        # Track sent votes to avoid duplicates
        self.sent_votes = set()
        
        self.logger.log("NODE", f"Node initialized with address {self.address[:16]}...")
    
    def initialize_genesis(self, initial_balances: Dict[str, int]):
        """Initialize with genesis block"""
        self.consensus.initialize_genesis(initial_balances)
    
    def create_transaction(self, to_address: str, amount: int) -> Transaction:
        """Create and sign a transaction"""
        nonce = len([tx for tx in self.tx_pool if tx.from_addr == self.address])
        tx = Transaction(
            from_addr=self.address,
            to_addr=to_address,
            amount=amount,
            nonce=nonce,
            chain_id=self.chain_id
        )
        tx.sign(self.keypair)
        return tx
    
    def submit_transaction(self, tx: Transaction):
        """Submit transaction to pool"""
        if tx.verify():
            self.tx_pool.append(tx)
            self.logger.log("TX", 
                           f"Transaction added to pool: {tx.from_addr[:8]}... → "
                           f"{tx.to_addr[:8]}... amount: {tx.amount}")
            
            # Broadcast to other validators
            self.network.broadcast_message(
                sender=self.address,
                receivers=self.all_validators,
                message_type="TRANSACTION",
                payload=tx.to_dict()
            )
    
    def propose_block_if_leader(self):
        """Propose block if this node is the leader for current height"""
        # Simple leader selection: round-robin based on height
        height = self.consensus.current_height
        leader_index = height % len(self.all_validators)
        leader_address = self.all_validators[leader_index]
        
        if leader_address == self.address and len(self.tx_pool) > 0:
            # We are the leader and have transactions
            proposal = self.consensus.propose_block(self.tx_pool)
            
            # Broadcast proposal
            self.network.broadcast_message(
                sender=self.address,
                receivers=self.all_validators,
                message_type="BLOCK_PROPOSAL",
                payload=proposal.to_dict()
            )
            
            # Process our own proposal
            self.consensus.receive_proposal(proposal)
            
            # Get the prevote we created
            height = proposal.block.header.height
            if height in self.consensus.prevoted:
                block_hash = self.consensus.prevoted[height]
                # Broadcast our prevote
                self._broadcast_votes_for_height(height)
            
            # Clear processed transactions
            self.tx_pool = []
    
    def tick(self):
        """
        Xử lý một tick của node - tự động xử lý tất cả events.
        """
        # 1. Xử lý network messages từ inbox
        messages = self.network.get_messages(self.address)
        
        for msg in messages:
            if msg.receiver != self.address:
                continue
            
            msg_type = msg.message_type
            payload = msg.payload
            
            if msg_type == "BLOCK_PROPOSAL":
                proposal = BlockProposal.from_dict(payload)
                self.consensus.receive_proposal(proposal)
                
                # Broadcast our prevote if we created one
                height = proposal.block.header.height
                self._broadcast_votes_for_height(height)
            
            elif msg_type == "VOTE":
                vote = Vote.from_dict(payload)
                
                # Check for duplicate
                vote_id = (vote.vote_type.value, vote.height, 
                          vote.block_hash, vote.validator_address)
                if vote_id in self.sent_votes:
                    continue  # Already processed this vote
                
                self.consensus.receive_vote(vote)
                
                # Check if we should send precommit
                height = vote.height
                self._broadcast_votes_for_height(height)
            
            elif msg_type == "TRANSACTION":
                tx = Transaction.from_dict(payload)
                if tx.verify() and tx not in self.tx_pool:
                    self.tx_pool.append(tx)
        
        # 2. Xử lý consensus events (propose block nếu là leader)
        self.propose_block_if_leader()
    
    def process_network_messages(self):
        """
        DEPRECATED: Dùng tick() thay vì method này.
        Giữ lại để backward compatibility.
        """
        messages = self.network.deliver_ready_messages(receiver=self.address)
        
        for msg in messages:
            if msg.receiver != self.address:
                continue
            
            msg_type = msg.message_type
            payload = msg.payload
            
            if msg_type == "BLOCK_PROPOSAL":
                proposal = BlockProposal.from_dict(payload)
                self.consensus.receive_proposal(proposal)
                
                # Broadcast our prevote if we created one
                height = proposal.block.header.height
                self._broadcast_votes_for_height(height)
            
            elif msg_type == "VOTE":
                vote = Vote.from_dict(payload)
                
                # Check for duplicate
                vote_id = (vote.vote_type.value, vote.height, 
                          vote.block_hash, vote.validator_address)
                if vote_id in self.sent_votes:
                    continue  # Already processed this vote
                
                self.consensus.receive_vote(vote)
                
                # Check if we should send precommit
                height = vote.height
                self._broadcast_votes_for_height(height)
            
            elif msg_type == "TRANSACTION":
                tx = Transaction.from_dict(payload)
                if tx.verify() and tx not in self.tx_pool:
                    self.tx_pool.append(tx)
    
    def _broadcast_votes_for_height(self, height: int):
        """Broadcast any new votes we created for this height"""
        # Broadcast prevote if we have one
        if height in self.consensus.prevoted:
            block_hash = self.consensus.prevoted[height]
            vote_id = ("prevote", height, block_hash, self.address)
            
            if vote_id not in self.sent_votes:
                from consensus.vote import Vote, VoteType
                vote = Vote(VoteType.PREVOTE, height, block_hash,
                           self.address, self.chain_id)
                vote.sign(self.keypair)
                
                self.network.broadcast_message(
                    sender=self.address,
                    receivers=self.all_validators,
                    message_type="VOTE",
                    payload=vote.to_dict()
                )
                self.sent_votes.add(vote_id)
        
        # Broadcast precommit if we have one
        if height in self.consensus.precommitted:
            block_hash = self.consensus.precommitted[height]
            vote_id = ("precommit", height, block_hash, self.address)
            
            if vote_id not in self.sent_votes:
                from consensus.vote import Vote, VoteType
                vote = Vote(VoteType.PRECOMMIT, height, block_hash,
                           self.address, self.chain_id)
                vote.sign(self.keypair)
                
                self.network.broadcast_message(
                    sender=self.address,
                    receivers=self.all_validators,
                    message_type="VOTE",
                    payload=vote.to_dict()
                )
                self.sent_votes.add(vote_id)
    
    def get_status(self) -> Dict[str, Any]:
        """Get node status"""
        return {
            "node_id": self.node_id,
            "address": self.address,
            "chain_info": self.consensus.get_chain_info(),
            "tx_pool_size": len(self.tx_pool),
            "network_stats": self.network.get_stats()
        }
    
    def get_blockchain(self):
        """Get the blockchain"""
        return self.consensus.blockchain
    
    def get_logs(self):
        """Get all logs"""
        return self.logger.get_logs()