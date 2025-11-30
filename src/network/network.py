"""
Network Layer - Unreliable Network Simulation
Simulates message delays, duplicates, reordering, and drops
"""
import random
import time
from typing import List, Callable, Any, Dict
from dataclasses import dataclass
from collections import defaultdict

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
        
        # Simulation time (không dùng time.time() nữa)
        self.simulation_time = 0.0
        
        # Message queue - messages chờ đến delivery_time
        self.message_queue: List[NetworkMessage] = []
        
        # Inbox cho mỗi node - messages đã sẵn sàng để deliver
        self.inboxes: Dict[str, List[NetworkMessage]] = defaultdict(list)
        
        self.delivered_count = 0
        self.dropped_count = 0
        self.duplicated_count = 0
    
    def send_message(self, sender: str, receiver: str, 
                     message_type: str, payload: Any):
        """Send a message through the unreliable network"""
        # Dùng simulation time thay vì time.time()
        send_time = self.simulation_time
        
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
        
        delivery_time = send_time + delay
        
        # Create message
        msg = NetworkMessage(
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
            send_time=send_time,
            delivery_time=delivery_time
        )
        
        self.message_queue.append(msg)
        
        self.logger.log("NETWORK", 
                       f"→ SENT {message_type} from {sender[:8]}... to {receiver[:8]}... "
                       f"(delay: {delay:.3f}s, delivery at t={delivery_time:.3f})")
        
        # Simulate message duplication
        if random.random() < self.duplicate_rate:
            duplicate_delay = random.uniform(self.delay_range[0], self.delay_range[1])
            duplicate_msg = NetworkMessage(
                sender=sender,
                receiver=receiver,
                message_type=message_type,
                payload=payload,
                send_time=send_time,
                delivery_time=send_time + duplicate_delay
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
    
    def tick(self, delta_time: float):
        """
        Advance simulation time và tự động deliver messages đã đến delivery_time.
        Đây là method chính để network "chạy liên tục".
        
        Args:
            delta_time: Thời gian mô phỏng trôi qua (không phải real time)
        """
        # Advance simulation time
        self.simulation_time += delta_time
        
        # Deliver messages đã đến delivery_time vào inbox của receiver
        remaining_messages = []
        
        for msg in self.message_queue:
            if msg.delivery_time <= self.simulation_time:
                # Message đã đến thời điểm deliver
                self.inboxes[msg.receiver].append(msg)
                self.delivered_count += 1
                self.logger.log(
                    "NETWORK",
                    f"← DELIVERED {msg.message_type} to {msg.receiver[:8]}... "
                    f"(latency: {self.simulation_time - msg.send_time:.3f}s, t={self.simulation_time:.3f})"
                )
            else:
                # Message chưa đến thời điểm deliver
                remaining_messages.append(msg)
        
        self.message_queue = remaining_messages
        
        # Messages trong inbox có thể đến out of order
        for receiver in self.inboxes:
            random.shuffle(self.inboxes[receiver])
    
    def get_messages(self, receiver: str) -> List[NetworkMessage]:
        """
        Lấy messages từ inbox của receiver (và xóa chúng khỏi inbox).
        Node sẽ gọi method này để lấy messages.
        """
        messages = self.inboxes[receiver]
        self.inboxes[receiver] = []
        return messages
    
    def deliver_ready_messages(self, receiver: str = None) -> List[NetworkMessage]:
        """
        DEPRECATED: Dùng get_messages() thay vì method này.
        Giữ lại để backward compatibility với tests.
        
        Tự động advance time một chút để deliver messages đã đến delivery_time.
        """
        # Advance time một chút để deliver messages đã đến delivery_time
        # Đây là workaround cho tests cũ - trong production nên dùng tick()
        if len(self.message_queue) > 0:
            # Tìm message có delivery_time sớm nhất
            min_delivery_time = min(msg.delivery_time for msg in self.message_queue)
            if min_delivery_time > self.simulation_time:
                # Advance time đến delivery_time của message sớm nhất
                delta = min_delivery_time - self.simulation_time + 0.001  # Thêm 1ms để chắc chắn
                self.tick(delta)
        
        if receiver is not None:
            return self.get_messages(receiver)
        else:
            # Return all messages from all inboxes
            all_messages = []
            for receiver_addr in list(self.inboxes.keys()):
                all_messages.extend(self.get_messages(receiver_addr))
            return all_messages
    
    def get_stats(self):
        """Get network statistics"""
        total_inbox = sum(len(msgs) for msgs in self.inboxes.values())
        return {
            "delivered": self.delivered_count,
            "dropped": self.dropped_count,
            "duplicated": self.duplicated_count,
            "pending": len(self.message_queue),
            "in_inboxes": total_inbox,
            "simulation_time": self.simulation_time
        }
    
    def get_simulation_time(self) -> float:
        """Get current simulation time"""
        return self.simulation_time
