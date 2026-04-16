# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import TYPE_CHECKING
from time import monotonic
from pathlib import Path

from ..net.protocol import (
    ChatMessage, CommandMessage, ErrorMessage, ErrorType,
    LogMessage, PingMessage,
)
from .session import ClientSession

if TYPE_CHECKING:
    from .client import Client


async def handle_server_message(client: Client, session: ClientSession, message: object) -> None:
    if isinstance(message, PingMessage):
        session.last_ping_id = message.ping_id
        session.last_ping_time = monotonic()
        await session.send_message(PingMessage(message.ping_id))
        session.last_pong_time = monotonic()
        return

    if isinstance(message, ErrorMessage):
        client.last_error = message.reason
        if message.error_type in {ErrorType.AUTH_REJECTED, ErrorType.ENCODING, ErrorType.CLOSED}:
            await session.close()
        return

    if isinstance(message, LogMessage):
        client.logs.append(message.log)
        return

    if isinstance(message, ChatMessage):
        client.chat_log.append(message)
        return

    if isinstance(message, CommandMessage):
        if message.command == "AUTH_OK":
            session.is_authenticated = True
        elif message.command == "REGISTERED_ENTITY":
            entity_name = str(message.args.get("entity_name", ""))
            if entity_name:
                client.logs.append(f"Entity bound: {entity_name}")
        elif message.command == "STATE_SYNC":
            entity_name = str(message.args.get("entity_name", ""))
            state = message.args.get("state", {})
            if entity_name and isinstance(state, dict):
                client.state_updates.append(
                    {
                        "entity_name": entity_name,
                        "state": state,
                    }
                )
        elif message.command == "ASSET_SYNC_BEGIN":
            payload = dict(message.args) if isinstance(message.args, dict) else {}
            payload["event"] = "begin"
            client.asset_sync_events.append(payload)
        elif message.command == "ASSET_FILE_SYNC":
            args = message.args if isinstance(message.args, dict) else {}
            category = str(args.get("category", "")).strip()
            file_name = str(args.get("file_name", "")).strip()
            content = args.get("content", "")

            allowed_categories = {"characters", "items", "spells"}
            if category not in allowed_categories:
                return
            if not file_name.endswith(".json"):
                return
            safe_name = Path(file_name).name
            if not safe_name or not isinstance(content, str):
                return

            target_dir = Path("assets") / category
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / safe_name
            try:
                target_file.write_text(content, encoding="utf-8")
            except OSError as exc:
                client.logs.append(f"asset sync write failed: {safe_name} ({exc})")
                return

            client.asset_sync_events.append(
                {
                    "event": "file",
                    "category": category,
                    "file_name": safe_name,
                }
            )
        elif message.command == "ASSET_SYNC_DONE":
            payload = dict(message.args) if isinstance(message.args, dict) else {}
            payload["event"] = "done"
            client.asset_sync_events.append(payload)
        elif message.command == "COMBAT_TURN_ORDER":
            payload = dict(message.args) if isinstance(message.args, dict) else {}
            client.combat_updates.append(payload)
        elif message.command == "PLAYER_JOINED":
            args = message.args if isinstance(message.args, dict) else {}
            username = str(args.get("username", "")).strip()
            if username:
                client.player_events.append({"event": "joined", "username": username})
        elif message.command == "PLAYER_LEFT":
            args = message.args if isinstance(message.args, dict) else {}
            username = str(args.get("username", "")).strip()
            if username:
                client.player_events.append({"event": "left", "username": username})
        elif message.command == "DAMAGE_ROLL_REQUEST":
            payload = dict(message.args) if isinstance(message.args, dict) else {}
            client.damage_roll_requests.append(payload)
        return

    await session.send_error(ErrorType.INVALID_COMMAND, "Unknown message type received")


async def handle_message_loop(client: Client, session: ClientSession) -> None:
    import asyncio
    while session.is_active and client.is_running:
        try:
            message = await session.receive_message()
            session.last_message_time = monotonic()
            await handle_server_message(client, session, message)
        except asyncio.CancelledError:
            break
        except ConnectionError:
            await session.close()
            break
        except (ValueError, RuntimeError, OSError) as exc:
            client.last_error = str(exc)
            await session.close()
            break
