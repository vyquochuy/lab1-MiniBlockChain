"""
Main Simulation Runner
Demonstrates blockchain consensus with multiple validators
"""
import sys
import os
from contextlib import contextmanager
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from crypto.keys import KeyPair
from network.network import UnreliableNetwork
from node import BlockchainNode, Logger
import time
import json


class TeeStream:
    """Duplicate writes to multiple streams (e.g., console + file)."""
    def __init__(self, *streams):
        self.streams = streams
    
    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()
    
    def flush(self):
        for stream in self.streams:
            stream.flush()


@contextmanager
def tee_output_to_file(log_path: str):
    """Context manager that mirrors stdout/stderr to a file."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    with open(log_path, "w", encoding="utf-8") as log_file:
        stdout_tee = TeeStream(original_stdout, log_file)
        stderr_tee = TeeStream(original_stderr, log_file)
        try:
            sys.stdout = stdout_tee
            sys.stderr = stderr_tee
            yield log_file
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

def run_simulation(num_validators=4, num_blocks=3, num_txs_per_block=2, 
                   network_delay=(0.01, 0.05), loss_rate=0.1, verbose=True):
    """
    Run blockchain simulation with multiple validators
    
    Args:
        num_validators: Number of validator nodes
        num_blocks: Number of blocks to finalize
        num_txs_per_block: Transactions per block
        network_delay: (min, max) network delay in seconds
        loss_rate: Packet loss rate (0.0 - 1.0)
        verbose: Print detailed logs
    """
    chain_id = "test-chain-1"
    
    print("="*80)
    print("BLOCKCHAIN LAYER 1 SIMULATION")
    print("="*80)
    print(f"Validators: {num_validators}")
    print(f"Target blocks: {num_blocks}")
    print(f"Network delay: {network_delay[0]}-{network_delay[1]}s")
    print(f"Packet loss rate: {loss_rate*100}%")
    print("="*80)
    print()
    
    # Create validators
    validators = []
    validator_addresses = []
    
    for i in range(num_validators):
        keypair = KeyPair()
        validator_addresses.append(keypair.get_address())
    
    # Create shared network
    master_logger = Logger("NETWORK", verbose)
    network = UnreliableNetwork(
        logger=master_logger,
        delay_range=network_delay,
        loss_rate=loss_rate,
        duplicate_rate=0.05
    )
    
    # Create nodes
    nodes = []
    initial_balances = {}
    
    for i, address in enumerate(validator_addresses):
        keypair = KeyPair()
        # Restore keypair from address (in real implementation, keep keypair)
        # For simulation, create new keypair but track by address
        validators.append(keypair)
        
        node = BlockchainNode(
            node_id=f"node-{i}",
            chain_id=chain_id,
            keypair=keypair,
            all_validator_addresses=validator_addresses,
            network=network,
            verbose=verbose
        )
        nodes.append(node)
        validator_addresses[i] = node.address  # Update with actual address
        
        # Initial balance
        initial_balances[node.address] = 1000
    
    # Update all nodes with correct validator addresses
    for node in nodes:
        node.all_validators = [n.address for n in nodes]
        node.consensus.all_validators = [n.address for n in nodes]
    
    # Initialize genesis on all nodes
    for node in nodes:
        node.initialize_genesis(initial_balances)
    
    print("✓ All nodes initialized with genesis block")
    print()
    
    # Simulation loop
    blocks_finalized = 0
    iteration = 0
    max_iterations = 1000
    
    while blocks_finalized < num_blocks and iteration < max_iterations:
        iteration += 1
        
        # Each node checks if it should propose
        for node in nodes:
            if blocks_finalized >= num_blocks:
                break
            
            # Add some transactions if pool is empty
            if len(node.tx_pool) < num_txs_per_block:
                for _ in range(num_txs_per_block):
                    # Random transfer between validators
                    recipient = nodes[(nodes.index(node) + 1) % len(nodes)].address
                    tx = node.create_transaction(recipient, 10)
                    node.submit_transaction(tx)
            
            # Try to propose block
            node.propose_block_if_leader()
        
        # Process network messages
        for node in nodes:
            node.process_network_messages()
        
        # Check if new block was finalized
        current_finalized = min(len(node.get_blockchain()) for node in nodes)
        if current_finalized > blocks_finalized:
            blocks_finalized = current_finalized - 1  # -1 for genesis
            print(f"\n{'='*80}")
            print(f"BLOCK {blocks_finalized} FINALIZED!")
            print(f"{'='*80}\n")
        
        # Small delay to simulate time passing
        time.sleep(0.01)
    
    print("\n" + "="*80)
    print("SIMULATION COMPLETE")
    print("="*80)
    
    # Verify consensus
    print("\nCONSENSUS VERIFICATION:")
    print("-" * 80)
    
    all_chains = [node.get_blockchain() for node in nodes]
    chain_hashes = []
    
    for i, node in enumerate(nodes):
        blockchain = node.get_blockchain()
        print(f"\nNode {i} ({node.address[:16]}...):")
        print(f"  Blocks finalized: {len(blockchain)}")
        
        chain_hash_list = [block.get_hash() for block in blockchain]
        chain_hashes.append(chain_hash_list)
        
        for j, block in enumerate(blockchain):
            print(f"    Block {j}: {block.get_hash()[:16]}... "
                  f"(state: {block.header.state_hash[:16]}...)")
    
    # Check if all chains are identical
    all_same = all(h == chain_hashes[0] for h in chain_hashes)
    
    print("\n" + "="*80)
    if all_same:
        print("SUCCESS: All nodes have identical blockchains!")
        print("Consensus achieved with finality guarantees")
    else:
        print("FAILURE: Nodes have different blockchains!")
        print("Consensus was not achieved")
    print("="*80)
    
    # Network statistics
    print("\nNETWORK STATISTICS:")
    print("-" * 80)
    stats = network.get_stats()
    print(f"  Messages delivered: {stats['delivered']}")
    print(f"  Messages dropped: {stats['dropped']}")
    print(f"  Messages duplicated: {stats['duplicated']}")
    print(f"  Messages pending: {stats['pending']}")
    print("="*80)
    
    return nodes, all_same

if __name__ == "__main__":
    log_txt_path = os.path.join("logs", "run_simulation_output.txt")
    with tee_output_to_file(log_txt_path):
        print(f"[run_simulation] Writing console output to {log_txt_path}")
        
        # Run simulation
        nodes, success = run_simulation(
            num_validators=4,
            num_blocks=3,
            num_txs_per_block=2,
            network_delay=(0.01, 0.05),
            loss_rate=0.1,
            verbose=True
        )
        
        # Save logs
        all_logs = []
        for node in nodes:
            all_logs.extend(node.get_logs())
        
        all_logs.sort(key=lambda x: x['timestamp'])
        
        with open('logs/simulation_log.json', 'w') as f:
            json.dump(all_logs, f, indent=2)
        
        print(f"\nLogs saved to logs/simulation_log.json")
        print(f"Text output saved to {log_txt_path}")
        
        if success:
            print("\nTest PASSED")
            sys.exit(0)
        else:
            print("\nTest FAILED")
            sys.exit(1)