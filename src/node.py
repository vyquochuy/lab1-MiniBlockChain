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
from consensus.consensus import BlockHeader

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
        
        # Header/ body separation
        self.pending_block_bodies = {} # block_hash -> transactions
        self.accepted_headers = set()
        self.requested_bodies = set() 
        
        self.logger.log("NODE", f"Node initialized with address {self.address}")
    
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
        # Use (height-1) so that at height=1 the first validator (index 0) is leader
        leader_index = (height - 1) % len(self.all_validators)
        leader_address = self.all_validators[leader_index]
        
        if leader_address == self.address and len(self.tx_pool) > 0:
            # We are the leader and have transactions
            proposal = self.consensus.propose_block(self.tx_pool)
            block_hash = proposal.block.get_hash()
            
            self.logger.log("CONSENSUS",
                            f"Broadcasting HEADER for block {block_hash[:16]}...")
            
            
            # STEP 1: Broadcast header
            self.network.broadcast_message(
                sender=self.address,
                receivers=self.all_validators,
                message_type="BLOCK_HEADER",
                payload={
                    "header": proposal.block.header.to_dict(),
                    "proposer_address": proposal.proposer_address,
                    "block_hash": block_hash
                }
            )
            # For backward compatibility with older peers, also broadcast full proposal
            self.network.broadcast_message(
                sender=self.address,
                receivers=self.all_validators,
                message_type="BLOCK_PROPOSAL",
                payload=proposal.to_dict()
            )
            # Step 2: Store body để gửi sau
            self.pending_block_bodies[block_hash] = proposal.block.transactions
            
            # Step 3: auto-accept our own header
            self.accepted_headers.add(block_hash)
            
            # Step 4: Process our own proposal
            self.consensus.receive_proposal(proposal)
            
            # Step 5: Get the prevote we created
            height = proposal.block.header.height
            if height in self.consensus.prevoted:
                block_hash = self.consensus.prevoted[height]
                # Broadcast our prevote
                self._broadcast_votes_for_height(height)
            
            # Clear processed transactions
            self.tx_pool = []
            
    # 
    def _handle_block_header(self, payload: Dict[str, Any]):
        """
        Handle received block header.
        Accept header and request body if valid.
        """
        header = BlockHeader.from_dict(payload["header"])
        proposer_address = payload["proposer_address"]
        block_hash = payload["block_hash"]
        
        self.logger.log("CONSENSUS", 
                    f"Received HEADER for block {block_hash[:16]}... at height {header.height}")
        
        # Basic validation of header
        if header.height != self.consensus.current_height:
            self.logger.log("CONSENSUS", 
                        f"Rejected header: wrong height {header.height} (expected {self.consensus.current_height})")
            return
        
        # Check parent hash
        if len(self.consensus.blockchain) > 0:
            expected_parent = self.consensus.blockchain[-1].get_hash()
            if header.parent_hash != expected_parent:
                self.logger.log("CONSENSUS", 
                            f"Rejected header: wrong parent {header.parent_hash[:16]}...")
                return
        
        # Accept header
        self.accepted_headers.add(block_hash)
        self.logger.log("CONSENSUS", 
                    f"✓ ACCEPTED header {block_hash[:16]}...")
        
        # Request body from proposer
        if block_hash not in self.requested_bodies:
            self.requested_bodies.add(block_hash)
            
            self.logger.log("CONSENSUS", 
                        f"Requesting BODY for block {block_hash[:16]}...")
            
            self.network.send_message(
                sender=self.address,
                receiver=proposer_address,
                message_type="BLOCK_BODY_REQUEST",
                payload={"block_hash": block_hash}
            )
    
    # 
    def _handle_block_body_request(self, sender: str, payload: Dict[str, Any]):
        """
        Handle request for block body.
        Send body if we have it.
        """
        block_hash = payload["block_hash"]
        
        self.logger.log("CONSENSUS", 
                    f"Received BODY REQUEST for {block_hash[:16]}... from {sender[:8]}...")
        
        # Check if we have this body
        if block_hash not in self.pending_block_bodies:
            self.logger.log("CONSENSUS", 
                        f"Don't have body for {block_hash[:16]}...")
            return
        
        transactions = self.pending_block_bodies[block_hash]
        
        self.logger.log("CONSENSUS", 
                    f"Sending BODY for {block_hash[:16]}... to {sender[:8]}... ({len(transactions)} txs)")
        
        # Send body to requester
        self.network.send_message(
            sender=self.address,
            receiver=sender,
            message_type="BLOCK_BODY",
            payload={
                "block_hash": block_hash,
                "transactions": [tx.to_dict() for tx in transactions]
            }
        )
        
    #
    def _handle_block_body(self, payload: Dict[str, Any]):
        """
        Handle received block body.
        Reconstruct full block and process.
        """
        block_hash = payload["block_hash"]
        
        self.logger.log("CONSENSUS", 
                    f"Received BODY for block {block_hash[:16]}...")
        
        # Check if we accepted this header
        if block_hash not in self.accepted_headers:
            self.logger.log("CONSENSUS", 
                        f"Received body for non-accepted header {block_hash[:16]}...")
            return
        
        # Check if we already have full block in pending
        height = None
        header = None
        for h, blocks in self.consensus.pending_blocks.items():
            if block_hash in blocks:
                self.logger.log("CONSENSUS", 
                            f"Already have full block {block_hash[:16]}...")
                return
            # Try to find header info (would need to store separately)
        
        # Reconstruct transactions
        transactions = [Transaction.from_dict(tx) for tx in payload["transactions"]]
        
        self.logger.log("CONSENSUS", 
                    f"Reconstructed block {block_hash[:16]}... with {len(transactions)} txs")
        
        # For now, we need to get the header from somewhere
        # In a complete implementation, we'd store headers separately
        # This is a simplified version - in production, store headers when received
        
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
            
            if msg_type == "BLOCK_HEADER":
                self._handle_block_header(payload)
            
            elif msg_type == "BLOCK_BODY_REQUEST":
                self._handle_block_body_request(msg.sender, payload)
                
            elif msg_type == "BLOCK_BODY":
                self._handle_block_body(payload)
            
            elif msg_type == "BLOCK_PROPOSAL":
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