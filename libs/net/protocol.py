#-*- coding: utf-8 -*-

"""
Network protocol module.

This module defines the network protocol for communication between clients and servers.
"""

# import built-in modules
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Any

# import third-party modules
from json import dumps, loads


# Create enums
class MessageType(Enum):
    """
    Enum representing the type of message sended over the network.
    """
    LOG = "LOG" # Log message for debbuging purposes
    PING = "PING" # Ping message for latency measurement
    MSG = "MSG" # Generic chat message between players
    CMD = "CMD" # Command message for game/network control
    ERROR = "ERROR" # Error message for protocol errors

class ErrorType(Enum):
    """
    Enum representing the type of error sended over the network.
    """
    RATE_LIMIT = "RATE_LIMIT" # Too many messages sent in a short time
    INVALID_COMMAND = "INVALID_COMMAND" # Command message with unknown command
    ENCODING = "ENCODING" # Message with invalid encoding or JSON format
    TIMEOUT = "TIMEOUT" # No message received within expected time frame
    CLOSED = "CLOSED" # Connection closed by the other party
    AUTH_REJECTED = "AUTH_REJECTED" # Authentication failed (if applicable)

# Create constants
PROTOCOL_VERSION = "1.0"

# Create message classes
@dataclass(slots=True)
class NetworkMessage:
    """
    Class representing a message sended over the network.
    """
    type: MessageType
    content: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> bytes:
        """
        Encode the message as a JSON string converted to bytes
        that is sendable over the network.
        """
        payload = {
            "type": self.type.value,
            **self.content,
        }
        return dumps(payload, indent=None, ensure_ascii=False).encode("utf-8")

class LogMessage(NetworkMessage):
    """
    Class representing a log message sended over the network.
    """
    def __init__(self, log: str) -> None:
        NetworkMessage.__init__(self,
            type=MessageType.LOG,
            content={"log": log}
        )

    @property
    def log(self) -> str:
        """
        Get the log message content.
        """
        return self.content.get("log", "")

class PingMessage(NetworkMessage):
    """
    Class representing a ping message sended over the network.
    """
    def __init__(self, ping_id: int) -> None:
        NetworkMessage.__init__(self,
            type=MessageType.PING,
            content={"ping_id": ping_id}
        )
    
    @property
    def ping_id(self) -> int:
        """
        Get the ping id content.
        """
        return self.content.get("ping_id", 0)

class ChatMessage(NetworkMessage):
    """
    Class representing a chat message sended over the network.
    """
    def __init__(self, sender: str, message: str) -> None:
        NetworkMessage.__init__(self,
            type=MessageType.MSG,
            content={"sender": sender, "message": message}
        )

    @property
    def sender(self) -> str:
        """
        Get the sender of the chat message.
        """
        return self.content.get("sender", "")

    @property
    def message(self) -> str:
        """
        Get the content of the chat message.
        """
        return self.content.get("message", "")

class CommandMessage(NetworkMessage):
    """
    Class representing a command message sended over the network.
    """
    def __init__(self, command: str, args: dict[str, Any]) -> None:
        NetworkMessage.__init__(self,
            type=MessageType.CMD,
            content={"command": command, "args": args}
        )
    
    @property
    def command(self) -> str:
        """
        Get the command name of the command message.
        """
        return self.content.get("command", "")

    @property
    def args(self) -> dict[str, Any]:
        """
        Get the arguments of the command message.
        """
        return self.content.get("args", {})

class ErrorMessage(NetworkMessage):
    """
    Class representing an error message sended over the network.
    """
    def __init__(self, error_type: ErrorType, reason: str) -> None:
        NetworkMessage.__init__(self,
            type=MessageType.ERROR,
            content={"error_type": error_type.value, "reason": reason}
        )
    
    @property
    def error_type(self) -> ErrorType:
        """
        Get the error type of the error message.
        """
        error_type_str = self.content.get("error_type", "")
        try:
            return ErrorType(error_type_str)
        except ValueError:
            return ErrorType.ENCODING # Default to encoding error if unknown

    @property
    def reason(self) -> str:
        """
        Get the reason of the error message.
        """
        return self.content.get("reason", "")

# Create decoding function
def decode(raw: bytes) -> NetworkMessage:
    """
    Decode a raw message received over the network into a NetworkMessage object.
    It will automatically create the correct subclass of NetworkMessage based on
    the "type" field in the JSON payload.
    """
    try:
        data = loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid message payload: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Protocol error: payload must be a JSON object")

    msg_type = data.get("type")
    if msg_type is None:
        raise ValueError("Protocol error: missing 'type' field")

    try:
        msg_type_enum = MessageType(msg_type)
    except ValueError as exc:
        raise ValueError(f"Protocol error: unknown message type '{msg_type}'") from exc

    if msg_type_enum == MessageType.LOG:
        log = data.get("log")
        if not isinstance(log, str):
            raise ValueError("Protocol error: 'log' field must be a string")
        return LogMessage(log=log)

    elif msg_type_enum == MessageType.PING:
        ping_id = data.get("ping_id")
        if not isinstance(ping_id, int):
            raise ValueError("Protocol error: 'ping_id' field must be an integer")
        return PingMessage(ping_id=ping_id)

    elif msg_type_enum == MessageType.MSG:
        sender = data.get("sender")
        message = data.get("message")
        if not isinstance(sender, str):
            raise ValueError("Protocol error: 'sender' field must be a string")
        if not isinstance(message, str):
            raise ValueError("Protocol error: 'message' field must be a string")
        return ChatMessage(sender=sender, message=message)

    elif msg_type_enum == MessageType.CMD:
        command = data.get("command")
        args = data.get("args", {})
        if not isinstance(command, str):
            raise ValueError("Protocol error: 'command' field must be a string")
        if not isinstance(args, dict):
            raise ValueError("Protocol error: 'args' field must be a JSON object")
        return CommandMessage(command=command, args=args)

    elif msg_type_enum == MessageType.ERROR:
        error_type = data.get("error_type")
        reason = data.get("reason")
        if not isinstance(error_type, str):
            raise ValueError("Protocol error: 'error_type' field must be a string")
        if not isinstance(reason, str):
            raise ValueError("Protocol error: 'reason' field must be a string")
        try:
            error_type_enum = ErrorType(error_type)
        except ValueError as exc:
            raise ValueError(f"Protocol error: unknown error type '{error_type}'") from exc
        return ErrorMessage(error_type=error_type_enum, reason=reason)

    else:
        raise ValueError(f"Protocol error: unhandled message type '{msg_type}'")
