# -*- coding: utf-8 -*-
from __future__ import annotations
import asyncio
import ssl
from pathlib import Path

from ..net.protocol import CommandMessage, ChatMessage
from .handlers import handle_message_loop
from .session import ClientSession


class Client:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        character_name: str = "",
        tls_ca_file: str = "",
        tls_insecure: bool = False,
        tls_server_hostname: str = "jdr-server",
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.character_name = character_name

        self.tls_ca_file = tls_ca_file
        self.tls_insecure = tls_insecure
        self.tls_server_hostname = tls_server_hostname

        self.is_running: bool = False
        self.session: ClientSession | None = None
        self.read_task: asyncio.Task | None = None

        self.last_error: str = ""
        self.logs: list[str] = []
        self.chat_log: list[object] = []
        self.state_updates: list[dict[str, object]] = []
        self.asset_sync_events: list[dict[str, object]] = []
        self.combat_updates: list[dict[str, object]] = []
        self.player_events: list[dict[str, object]] = []
        self.damage_roll_requests: list[dict[str, object]] = []

    def _build_ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.tls_insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        if self.tls_ca_file:
            ca_path = Path(self.tls_ca_file)
            if not ca_path.exists():
                raise ValueError(f"TLS CA file not found: {ca_path}")
            context.load_verify_locations(cafile=str(ca_path))
        return context

    async def setup(self) -> None:
        if self.is_running:
            return
        ssl_context = self._build_ssl_context()
        reader, writer = await asyncio.open_connection(
            host=self.host,
            port=self.port,
            ssl=ssl_context,
            server_hostname=self.tls_server_hostname,
        )
        self.session = ClientSession(
            username=self.username,
            connection=(self.host, self.port),
            reader=reader,
            writer=writer,
        )
        self.is_running = True
        auth_payload = {"username": self.username, "password": self.password}
        if self.character_name:
            auth_payload["character_name"] = self.character_name
        await self.session.send_message(CommandMessage("AUTH", auth_payload))
        self.read_task = asyncio.create_task(handle_message_loop(self, self.session))

    async def send_command(self, command: str, args: dict) -> None:
        if not self.session or not self.session.is_active:
            raise RuntimeError("Client is not connected")
        await self.session.send_message(CommandMessage(command, args))

    async def send_chat(self, text: str) -> None:
        if not self.session or not self.session.is_active:
            raise RuntimeError("Client is not connected")
        await self.session.send_message(ChatMessage(self.username, text))

    async def send_spell_request(
            self,
            spell_key: str,
            targets: list[str] | None = None,
            user_dices: dict[str, int] | None = None,
        ) -> None:
        """Send spell cast request to server."""
        if not self.session or not self.session.is_active:
            raise RuntimeError("Client is not connected")
        user_dices = user_dices or {}
        targets = [str(t).strip() for t in (targets or []) if str(t).strip()]
        await self.session.send_message(
            CommandMessage("SPELL_REQUEST", {
                "spell_key": str(spell_key),
                "targets": targets,
                "user_dices": dict(user_dices),
            })
        )

    async def send_attack_request(
            self,
            action: str,
            target: str,
            user_dices: dict[str, int] | None = None,
        ) -> None:
        """Send strike/shoot request to server."""
        if not self.session or not self.session.is_active:
            raise RuntimeError("Client is not connected")
        await self.session.send_message(
            CommandMessage(
                "ATTACK_REQUEST",
                {
                    "action": str(action).strip().lower(),
                    "target": str(target).strip(),
                    "user_dices": dict(user_dices or {}),
                },
            )
        )

    async def send_damage_roll_result(
            self,
            request_id: str,
            damage_dice: str,
            rolls: list[int],
            total: int,
        ) -> None:
        """Send damage roll result back to server for MJ resolution."""
        if not self.session or not self.session.is_active:
            raise RuntimeError("Client is not connected")
        await self.session.send_message(
            CommandMessage(
                "DAMAGE_ROLL_RESULT",
                {
                    "request_id": str(request_id).strip(),
                    "damage_dice": str(damage_dice).strip(),
                    "rolls": [int(v) for v in rolls],
                    "total": int(total),
                },
            )
        )

    async def shutdown(self) -> None:
        self.is_running = False
        if self.read_task is not None:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
        if self.session is not None:
            await self.session.close()
