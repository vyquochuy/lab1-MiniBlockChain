"""
Main Simulation Runner
Demonstrates blockchain consensus with multiple validators
"""
import sys
import os
import time
import json
import random
from crypto.keys import KeyPair
from contextlib import contextmanager
from node import BlockchainNode, Logger
from network.network import UnreliableNetwork

random.seed(0)
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))


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

def run_simulation(num_validators, num_blocks, num_txs_per_block, 
                   network_delay, loss_rate, verbose,
                   duplicate_rate: float = 0.05,
                   max_simulation_time: float = 10.0,
                   time_step: float = 1):
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
        duplicate_rate=duplicate_rate
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
    
    print("All nodes initialized with genesis block")
    print()
    
    # Simulation loop - while True để giữ mạng chạy liên tục
    # Logic "giữ mạng chạy" nằm trong Network.tick() và Node.tick()
    blocks_finalized = 0
    iteration = 0
    max_iterations = 10000
    
    print("Starting continuous network simulation...")
    print("Network and Nodes will process events continuously\n")
    
    while True:
        iteration += 1
        simulation_time = network.get_simulation_time()
        
        # Kiểm tra điều kiện dừng
        if blocks_finalized >= num_blocks:
            print(f"\nTarget blocks ({num_blocks}) reached. Stopping simulation.")
            break
        
        if iteration > max_iterations:
            print(f"\nMax iterations ({max_iterations}) reached. Stopping simulation.")
            break
        
        if simulation_time > max_simulation_time:
            print(f"\nMax simulation time ({max_simulation_time}s) reached. Stopping simulation.")
            break
        
        # 1. Network tick: advance time và tự động deliver messages đã đến delivery_time
        # Đây là phần quan trọng nhất - network tự động deliver messages
        network.tick(time_step)
        
        # 2. Mỗi node tick: tự động xử lý messages và events
        # Node tự động poll inbox và xử lý tất cả events
        for node in nodes:
            # Thêm transactions nếu pool rỗng (để có data cho blocks)
            if len(node.tx_pool) < num_txs_per_block:
                for _ in range(num_txs_per_block):
                    # Random transfer between validators
                    recipient = nodes[(nodes.index(node) + 1) % len(nodes)].address
                    tx = node.create_transaction(recipient, 10)
                    node.submit_transaction(tx)
            
            # Node tick: xử lý messages từ inbox và các events
            node.tick()
        
        # 3. Kiểm tra block mới được finalize
        current_finalized = min(len(node.get_blockchain()) for node in nodes) - 1
        if current_finalized > blocks_finalized:
            blocks_finalized = current_finalized
            print(f"\n{'='*80}")
            print(f"BLOCK {blocks_finalized} FINALIZED! (simulation time: {simulation_time:.3f}s)")
            print(f"{'='*80}\n")
        
    
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
    # Load configuration from config/config.json (fall back to sensible defaults)
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
    config = {}
    try:
        with open(config_path, 'r', encoding='utf-8') as cf:
            config = json.load(cf)
    except Exception:
        # If config not present or invalid, fall back to defaults below
        config = {}

    # Defaults
    cfg_num_validators = config.get('num_validators', 10)
    cfg_num_blocks = config.get('num_blocks', 3)
    cfg_num_txs_per_block = config.get('num_txs_per_block', 2)
    cfg_network_delay = tuple(config.get('network_delay', [0.01, 0.05]))
    cfg_loss_rate = config.get('loss_rate', 0.1)
    cfg_verbose = config.get('verbose', True)
    cfg_duplicate_rate = config.get('duplicate_rate', 0.05)
    cfg_max_simulation_time = config.get('max_simulation_time', 10.0)
    cfg_time_step = config.get('time_step', 1)

    log_txt_path = os.path.join("logs", "run_simulation_output.txt")
    with tee_output_to_file(log_txt_path):
        print(f"[run_simulation] Writing console output to {log_txt_path}")

        # Run simulation with configuration values
        nodes, success = run_simulation(
            num_validators=cfg_num_validators,
            num_blocks=cfg_num_blocks,
            num_txs_per_block=cfg_num_txs_per_block,
            network_delay=cfg_network_delay,
            loss_rate=cfg_loss_rate,
            verbose=cfg_verbose,
            duplicate_rate=cfg_duplicate_rate,
            max_simulation_time=cfg_max_simulation_time,
            time_step=cfg_time_step
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