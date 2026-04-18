#-*- coding: utf-8 -*-

"""
Server sessions module.

This module defines the ClientSession class, which manages the state of a single client
and acts as a connection wrapper for the server's basic operations.
"""

# Import built-in modules
from __future__ import annotations
from typing import Optional
from asyncio import StreamReader, StreamWriter
from time import monotonic

# Import local modules
from ..net.protocol import (
    NetworkMessage,
    ErrorMessage,
    CommandMessage,
    ChatMessage
)
from ..net.protocol import decode, ErrorType


# Create Sessions
class ClientSession:
    """
    Class representing a client session, which manages the state of a single client
    and acts as a connection wrapper for the server's basic operations.
    """
    def __init__(
            self,
            username: str,
            conn_infos: tuple[str, int],
            reader: StreamReader,
            writer: StreamWriter
        ) -> None:
        self.username = username
        self.connection = conn_infos
        self.reader = reader
        self.writer = writer

        # heartbeat management
        self.last_ping_id: Optional[int] = None
        self.last_ping_time: float = monotonic()
        self.last_pong_time: float = monotonic()

        # rate limiting
        self.last_message_time: float = 0.0
        self.rate_limit_strikes: int = 0

        # state management
        self.is_active: bool = True

        # session data
        self.chat_log: list[ChatMessage] = []
        self.bound_entity: str | None = None
        self.bound_character: str | None = None

    async def send_message(self, message: NetworkMessage) -> None:
        """
        Send a message to the client.
        """
        data = message.encode() + b"\n"
        self.writer.write(data)
        await self.writer.drain()

    async def receive_message(self) -> Optional[NetworkMessage]:
        """
        Recieve a message from the client.
        """
        data = await self.reader.readline()
        if not data:
            raise ConnectionError("Connection closed by client")
        message = decode(data.strip())
        return message

    async def send_error(self, error_type: ErrorType, error_message: str) -> None:
        """
        Send an error message to the client.
        """
        await self.send_message(ErrorMessage(
            error_type=error_type,
            reason=error_message
        ))

    async def close(self) -> None:
        """
        Close the client session and clean up resources.
        """
        if not self.is_active:
            return
        self.is_active = False
        try:
            await self.send_message(CommandMessage("CLOSE", {}))
        except (ConnectionError, OSError, RuntimeError) as e:
            print(f"Error sending close message to {self.username}: {e}")
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except (ConnectionError, OSError, RuntimeError) as e:
            print(f"Error closing connection for {self.username}: {e}")
