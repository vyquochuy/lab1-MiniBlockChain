"""
Network Layer - Unreliable Network Simulation
Simulates message delays, duplicates, reordering, and drops
"""
import random
import time
from typing import List, Callable, Any
from dataclasses import dataclass

@dataclass
class NetworkMessage:
    """Message in the network"""
    sender: str
    receiver: str
    message_type: str
    payload: Any
    send_time: float
    delivery_time: float

class UnreliableNetwork:
    """Simulates unreliable network with delays and packet loss"""
    
    def __init__(self, logger, 
                 delay_range=(0.01, 0.1),  # min, max delay in seconds
                 loss_rate=0.1,  # 10% packet loss
                 duplicate_rate=0.05,  # 5% duplicate messages
                 enable_delays=True):
        self.logger = logger
        self.delay_range = delay_range
        self.loss_rate = loss_rate
        self.duplicate_rate = duplicate_rate
        self.enable_delays = enable_delays
        
        # Message queue
        self.message_queue: List[NetworkMessage] = []
        self.delivered_count = 0
        self.dropped_count = 0
        self.duplicated_count = 0
    
    def send_message(self, sender: str, receiver: str, 
                     message_type: str, payload: Any):
        """Send a message through the unreliable network"""
        current_time = time.time()
        
        # Simulate packet loss
        if random.random() < self.loss_rate:
            self.dropped_count += 1
            self.logger.log("NETWORK", 
                           f"✗ DROPPED {message_type} from {sender[:8]}... to {receiver[:8]}...")
            return
        
        # Calculate delivery time with random delay
        if self.enable_delays:
            delay = random.uniform(self.delay_range[0], self.delay_range[1])
        else:
            delay = 0.0
        
        delivery_time = current_time + delay
        
        # Create message
        msg = NetworkMessage(
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
            send_time=current_time,
            delivery_time=delivery_time
        )
        
        self.message_queue.append(msg)
        
        self.logger.log("NETWORK", 
                       f"→ SENT {message_type} from {sender[:8]}... to {receiver[:8]}... "
                       f"(delay: {delay:.3f}s)")
        
        # Simulate message duplication
        if random.random() < self.duplicate_rate:
            duplicate_delay = random.uniform(self.delay_range[0], self.delay_range[1])
            duplicate_msg = NetworkMessage(
                sender=sender,
                receiver=receiver,
                message_type=message_type,
                payload=payload,
                send_time=current_time,
                delivery_time=current_time + duplicate_delay
            )
            self.message_queue.append(duplicate_msg)
            self.duplicated_count += 1
            self.logger.log("NETWORK", 
                           f"⚠ DUPLICATE {message_type} will be sent "
                           f"(delay: {duplicate_delay:.3f}s)")
    
    def broadcast_message(self, sender: str, receivers: List[str], 
                         message_type: str, payload: Any):
        """Broadcast message to multiple receivers"""
        for receiver in receivers:
            if receiver != sender:  # Don't send to self
                self.send_message(sender, receiver, message_type, payload)
    
    def deliver_ready_messages(self, receiver: str = None) -> List[NetworkMessage]:
        """
        Deliver messages ready to be consumed.
        
        Args:
            receiver: if provided, only deliver messages addressed to this receiver.
                      Ready messages for other receivers stay queued.
        """
        current_time = time.time()
        ready_messages = []
        ready_for_others = []
        remaining_messages = []
        
        for msg in self.message_queue:
            if msg.delivery_time <= current_time:
                if receiver is not None and msg.receiver != receiver:
                    ready_for_others.append(msg)
                    continue
                
                ready_messages.append(msg)
                self.delivered_count += 1
                self.logger.log(
                    "NETWORK",
                    f"← DELIVERED {msg.message_type} to {msg.receiver[:8]}... "
                    f"(latency: {current_time - msg.send_time:.3f}s)"
                )
            else:
                remaining_messages.append(msg)
        
        # Keep messages that are ready but destined for other receivers
        self.message_queue = remaining_messages + ready_for_others
        
        # Messages may arrive out of order
        random.shuffle(ready_messages)
        
        return ready_messages
    
    def get_stats(self):
        """Get network statistics"""
        return {
            "delivered": self.delivered_count,
            "dropped": self.dropped_count,
            "duplicated": self.duplicated_count,
            "pending": len(self.message_queue)
        }
