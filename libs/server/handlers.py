#-*- coding: utf-8 -*-

"""
Server Handlers module.

This module contains handlers for server events, such as client connections, disconnections,
and message processing.
It also provides a registry of commands and their corresponding handler functions.
"""

# import built-in modules
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from time import monotonic
import asyncio

# import local modules
from ..net.protocol import ErrorType
from ..net.protocol import (
    LogMessage,
    PingMessage,
    ChatMessage,
    CommandMessage,
    ErrorMessage
)
from .session import ClientSession

if TYPE_CHECKING:
    from .server import Server

# Create command registry
COMMAND_REGISTRY: dict[str, Any] = {}

# Command register decorator
def register_cmd(cmd_name: str):
    """
    Decorator to register a command handler function.
    """
    def decorator(func: Any) -> Any:
        COMMAND_REGISTRY[cmd_name] = func
        return func
    return decorator

# Create command handler functions
async def handle_auth(
        server: Server,
        client_infos: tuple[str, int],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        username: str,
        password: str,
        character_name: str = ""
    ) -> bool:
    """
    Handle the AUTH command.
    This command is used by clients to authenticate themselves with the server.
    return True if authentication is successful, False otherwise.
    """
    if username in server.connected_clients:
        print(f"[auth] rejected username={username!r} peer={client_infos} reason=username-already-in-use")
        await server.send_error(
            writer,
            ErrorType.AUTH_REJECTED,
            "Username already in use"
        )
        return False

    if password != server.password:
        print(f"[auth] rejected username={username!r} peer={client_infos} reason=invalid-password")
        await server.send_error(writer, ErrorType.AUTH_REJECTED, "Invalid password")
        return False

    if username.strip().lower() == "admin":
        print(f"[auth] rejected username={username!r} peer={client_infos} reason=reserved-username")
        await server.send_error(
            writer, ErrorType.AUTH_REJECTED, "Username 'Admin' is reserved"
        )
        return False

    session = ClientSession(
        username=username,
        conn_infos=client_infos,
        reader=reader,
        writer=writer
    )
    server.connected_clients[username] = session
    
    # Auto-register entity if provided
    if character_name:
        character_name = str(character_name).strip()
        if character_name:
            session.bound_entity = character_name
            await server.send_message(
                writer,
                CommandMessage("AUTH_OK", {"username": username, "entity_name": character_name})
            )
            print(
                f"[auth] accepted username={username!r} peer={client_infos} "
                f"entity={character_name!r} active_clients={len(server.connected_clients)}"
            )
            return True
    
    await server.send_message(writer, CommandMessage("AUTH_OK", {"username": username}))
    print(
        f"[auth] accepted username={username!r} peer={client_infos} "
        f"active_clients={len(server.connected_clients)}"
    )
    return True

@register_cmd("QUIT")
async def handle_quit(server, session) -> None:
    """
    Handle the QUIT command.
    This command is used by clients to disconnect from the server.
    """
    print(f"[session] closing username={session.username!r} peer={session.connection} reason=client-quit")
    await session.close()
    server.connected_clients.pop(session.username, None)

@register_cmd("REGISTER_ENTITY")
async def handle_register_entity(server, session, entity_name: str) -> None:
    """Associe la session reseau du joueur a une entite MJ cible."""
    _ = server
    entity_name = str(entity_name).strip()
    if not entity_name:
        await session.send_error(ErrorType.INVALID_COMMAND, "entity_name is required")
        return

    session.bound_entity = entity_name
    await session.send_message(
        CommandMessage("REGISTERED_ENTITY", {"entity_name": entity_name})
    )
    print(
        f"[bind] username={session.username!r} peer={session.connection} "
        f"entity={entity_name!r}"
    )

@register_cmd("SPELL_REQUEST")
async def handle_spell_request(
    server, session, spell_key: str, targets: list | None = None, user_dices: dict | None = None
) -> None:
    """Handle spell cast request from client.
    
    Args:
        spell_key: spell name/key
        user_dices: dict of stat -> rolled value (optional)
    """
    entity_name = str(session.bound_entity or "").strip()
    if not entity_name:
        await session.send_error(ErrorType.INVALID_COMMAND, "Entity not registered")
        return
    
    spell_key = str(spell_key).strip()
    user_dices = user_dices or {}
    clean_targets = [str(t).strip() for t in (targets or []) if str(t).strip()]
    
    # Enregistrer la demande dans la session
    request = {
        "spell_key": spell_key,
        "user": entity_name,
        "targets": clean_targets,
        "user_dices": dict(user_dices),
        "username": session.username,
    }
    if not hasattr(session, "spell_requests"):
        session.spell_requests = []
    session.spell_requests.append(request)
    
    # Envoyer confirmation au client
    await session.send_message(
        CommandMessage("SPELL_REQUEST_ACK", {"spell": spell_key, "status": "pending"})
    )
    
    dices_str = ", ".join(f"{k}:{v}" for k, v in sorted(user_dices.items())) if user_dices else "—"
    targets_str = ",".join(clean_targets) if clean_targets else "—"
    print(
        f"[spell] request username={session.username!r} spell={spell_key!r} "
        f"user={entity_name!r} targets={targets_str} dices={dices_str}"
    )


@register_cmd("ATTACK_REQUEST")
async def handle_attack_request(
    server,
    session,
    action: str,
    target: str,
    user_dices: dict | None = None,
) -> None:
    """Handle strike/shoot request from client."""
    _ = server
    entity_name = str(session.bound_entity or "").strip()
    if not entity_name:
        await session.send_error(ErrorType.INVALID_COMMAND, "Entity not registered")
        return

    action = str(action).strip().lower()
    if action not in {"strike", "shoot"}:
        await session.send_error(ErrorType.INVALID_COMMAND, "action must be strike or shoot")
        return

    target = str(target).strip()
    if not target:
        await session.send_error(ErrorType.INVALID_COMMAND, "target is required")
        return

    user_dices = user_dices or {}
    request = {
        "action": action,
        "user": entity_name,
        "target": target,
        "user_dices": dict(user_dices),
        "username": session.username,
    }
    if not hasattr(session, "attack_requests"):
        session.attack_requests = []
    session.attack_requests.append(request)

    await session.send_message(
        CommandMessage("ATTACK_REQUEST_ACK", {"action": action, "target": target, "status": "pending"})
    )

    dices_str = ", ".join(f"{k}:{v}" for k, v in sorted(user_dices.items())) if user_dices else "—"
    print(
        f"[attack] request username={session.username!r} action={action!r} "
        f"user={entity_name!r} target={target!r} dices={dices_str}"
    )


@register_cmd("DAMAGE_ROLL_RESULT")
async def handle_damage_roll_result(
    server,
    session,
    request_id: str,
    damage_dice: str,
    rolls: list | None = None,
    total: int | None = None,
) -> None:
    """Receive damage roll result from player for MJ validation/apply."""
    _ = server
    entity_name = str(session.bound_entity or "").strip()
    if not entity_name:
        await session.send_error(ErrorType.INVALID_COMMAND, "Entity not registered")
        return

    request_id = str(request_id).strip()
    if not request_id:
        await session.send_error(ErrorType.INVALID_COMMAND, "request_id is required")
        return

    damage_dice = str(damage_dice).strip()
    clean_rolls = [int(v) for v in (rolls or [])]
    computed_total = int(total if total is not None else sum(clean_rolls))

    payload = {
        "request_id": request_id,
        "user": entity_name,
        "username": session.username,
        "damage_dice": damage_dice,
        "rolls": clean_rolls,
        "total": computed_total,
    }
    if not hasattr(session, "damage_roll_results"):
        session.damage_roll_results = []
    session.damage_roll_results.append(payload)

    await session.send_message(
        CommandMessage(
            "DAMAGE_ROLL_RESULT_ACK",
            {"request_id": request_id, "status": "received"},
        )
    )

    print(
        f"[damage] result username={session.username!r} user={entity_name!r} "
        f"request={request_id!r} cmd={damage_dice!r} rolls={clean_rolls} total={computed_total}"
    )

# Create server handlers
async def heartbeat_loop(server: Server) -> None:
    """
    Heartbeat loop to check for inactive clients and remove them from the server.
    """
    while server.is_running:
        now = monotonic()
        username: str
        session: ClientSession
        for username, session in list(server.connected_clients.items()):
            # handle timeout for inactive clients
            if now - session.last_pong_time > server.heartbeat_timeout:
                print(
                    f"[session] closing username={username!r} peer={session.connection} "
                    f"reason=heartbeat-timeout"
                )
                await session.send_error(
                    ErrorType.TIMEOUT,
                    "No pong received within timeout, closing connection"
                )
                await session.close()
                server.connected_clients.pop(username, None)
            else:
                if not session.last_ping_time > session.last_pong_time:
                    await session.send_message(PingMessage(int(now*1000)))
                    session.last_ping_time = now
                    session.last_ping_id = int(now*1000)
        await asyncio.sleep(server.heartbeat_interval)

async def handle_message(
        server: Server,
        session: ClientSession
    ) -> None:
    """
    handle incoming messages from the client and dispatch them to the appropriate command handlers.
    """
    while session.is_active:
        try:
            message = await session.receive_message()
            now = monotonic()
            if now - session.last_message_time < server.rate_limit_interval:
                session.rate_limit_strikes += 1
            else:
                session.rate_limit_strikes = 0
            if session.rate_limit_strikes >= server.rate_limit_threshold:
                print(
                    f"[session] closing username={session.username!r} peer={session.connection} "
                    f"reason=rate-limit strikes={session.rate_limit_strikes}"
                )
                await session.send_error(
                    ErrorType.RATE_LIMIT,
                    "Too many messages sent in a short time, please slow down"
                )
                await session.close()
                server.connected_clients.pop(session.username, None)
                break
            session.last_message_time = now
            if isinstance(message, CommandMessage):
                cmd_name = message.command
                cmd_args = message.args
                handler = COMMAND_REGISTRY.get(cmd_name)
                if handler is None:
                    await session.send_error(
                        ErrorType.INVALID_COMMAND,
                        f"Unknown command: {cmd_name}"
                    )
                    continue
                result = handler(server, session, **cmd_args)
                if asyncio.iscoroutine(result):
                    await result
            elif isinstance(message, ChatMessage):
                print(f"[chat] from={message.sender!r} to={session.username!r} message={message.message!r}")
                session.chat_log.append(message)
                for client_session in server.connected_clients.values():
                    if client_session.username != session.username:
                        await client_session.send_message(message)
            elif isinstance(message, PingMessage):
                # Update last pong time to prevent timeout
                if session.last_ping_id == message.ping_id:
                    if session.last_pong_time < session.last_ping_time:
                        session.last_pong_time = monotonic()
                else:
                    print(
                        f"[session] closing username={session.username!r} peer={session.connection} "
                        f"reason=invalid-ping-id expected={session.last_ping_id} received={message.ping_id}"
                    )
                    await session.send_error(
                        ErrorType.INVALID_COMMAND,
                        "Invalid ping_id received"
                    )
                    await session.close()
                    server.connected_clients.pop(session.username, None)
            elif isinstance(message, LogMessage):
                # Log messages are ignored by the server, as they are meant for clients
                pass
            elif isinstance(message, ErrorMessage):
                # Error messages are ignored by the server, as they are meant for clients
                pass
            else:
                print(
                    f"[session] closing username={session.username!r} peer={session.connection} "
                    f"reason=unknown-message-type"
                )
                await session.send_error(
                    ErrorType.INVALID_COMMAND,
                    "Unknown message type received"
                )
                await session.close()
                server.connected_clients.pop(session.username, None)
        except asyncio.CancelledError:
            break
        except (ConnectionError, OSError, RuntimeError) as exc:
            print(
                f"[session] closing username={session.username!r} peer={session.connection} "
                f"reason=exception detail={exc}"
            )
            await session.send_error(
                ErrorType.ENCODING,
                f"An error occurred while processing your message: {exc}"
            )
            await session.close()
            server.connected_clients.pop(session.username, None)
