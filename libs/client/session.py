# -*- coding: utf-8 -*-
from __future__ import annotations
from asyncio import StreamReader, StreamWriter
from time import monotonic

from ..net.protocol import ErrorMessage, ErrorType, NetworkMessage, decode


class ClientSession:
    def __init__(
        self,
        username: str,
        connection: tuple[str, int],
        reader: StreamReader,
        writer: StreamWriter,
    ) -> None:
        self.username = username
        self.connection = connection
        self.reader = reader
        self.writer = writer

        self.is_active: bool = True
        self.is_authenticated: bool = False

        self.last_message_time: float = 0.0
        self.last_ping_id: int | None = None
        self.last_ping_time: float = monotonic()
        self.last_pong_time: float = monotonic()

    async def send_message(self, message: NetworkMessage) -> None:
        data = message.encode() + b"\n"
        self.writer.write(data)
        await self.writer.drain()

    async def receive_message(self) -> NetworkMessage:
        data = await self.reader.readline()
        if not data:
            raise ConnectionError("Connection closed by server")
        return decode(data.strip())

    async def send_error(self, error_type: ErrorType, reason: str) -> None:
        await self.send_message(ErrorMessage(error_type=error_type, reason=reason))

    async def close(self) -> None:
        if not self.is_active:
            return
        self.is_active = False
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except (ConnectionError, OSError, RuntimeError):
            return
