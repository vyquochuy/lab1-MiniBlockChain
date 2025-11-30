"""
Network Layer - Message Protocol
Defines message types for network communication
"""
from typing import Dict, Any
from enum import Enum

class MessageType(Enum):
    """Types of messages in the network"""
    BLOCK_PROPOSAL = "block_proposal"
    VOTE = "vote"
    TRANSACTION = "transaction"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"

class Message:
    """Base message class"""
    
    def __init__(self, msg_type: MessageType, payload: Dict[str, Any]):
        self.msg_type = msg_type
        self.payload = payload
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.msg_type.value,
            "payload": self.payload
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        return cls(MessageType(d["type"]), d["payload"])