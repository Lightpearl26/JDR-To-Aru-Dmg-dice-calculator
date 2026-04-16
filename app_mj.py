# -*- coding: utf-8 -*-
"""
App MJ — Maître du Jeu
======================
Lance avec :
    python v2/app_mj.py

Fenêtre principale du MJ :
  - Panneau gauche : contrôle serveur, liste des joueurs connectés, chat
  - Zone centrale  : EntityCards des entités chargées (double-clic → fiche)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from random import randint
import socket
import sys
from uuid import uuid4
from pathlib import Path
from typing import Optional
from asyncio.subprocess import Process as AsyncioProcess

def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


_V2_DIR = _runtime_root()
os.chdir(_V2_DIR)
sys.path.insert(0, str(_V2_DIR))

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QInputDialog,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from libs.character import Character, Entity
from libs.dice import Dice
from libs.server.server import Server
from libs.server.__main__ import start_vps_relay, stop_vps_relay
from libs.net.protocol import ChatMessage, CommandMessage
from libs.net.state_sync import serialize_entity_state
from libs.gui.entity_card import EntityCard
from libs.gui.entity_sheet import EntitySheet


# ── Palette ───────────────────────────────────────────────────────────────────

_APP_BG       = "#11111b"
_PANEL_BG     = "#1e1e2e"
_PANEL_BORDER = "#45475a"
_HEADER_BG    = "#282838"
_TEXT_PRIMARY = "#cdd6f4"
_TEXT_SEC     = "#9399b2"
_TEXT_MUTED   = "#45475a"
_GREEN        = "#a6e3a1"
_RED          = "#f38ba8"
_YELLOW       = "#f9e2af"
_PURPLE       = "#cba6f7"
_ACCENT       = "#8060c0"

# Relay VPS (meme base que start_server.py)
_RELAY_HOST = "31.97.55.226"
_RELAY_USER = "root"
_RELAY_SSH_PORT = 22
_RELAY_PUBLIC_PORT = 7799
_RELAY_TUNNEL_PORT = 17799
_RELAY_KEY_FILE = str(Path.home() / ".ssh" / "jdr_vps_ed25519")


def _guess_lan_ip() -> str:
    """Retourne une IP LAN probable pour partage rapide."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


# ── Widget Machine a Sous pour l'ordre de combat ───────────────────────────────

class _SlotMachineRoster(QWidget):
    """Affiche l'ordre des tours comme une machine a sous avec animation de defilement."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[str, str, str]] = []  # (name, d20_str, status_str)
        self._current_idx: int = -1
        self._anim_offset: float = 0.0
        self._anim_direction: int = 1
        self._item_height = 32
        self._visible_items = 5

        self.setMinimumHeight((self._item_height * self._visible_items) + 16)
        self.setStyleSheet(f"background:{_APP_BG};")

        self._anim = QPropertyAnimation(self, b"animOffset")
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.Type.OutElastic)

    @pyqtProperty(float)
    def animOffset(self) -> float:
        return self._anim_offset

    @animOffset.setter
    def animOffset(self, value: float) -> None:
        self._anim_offset = value
        self.update()

    def set_roster(self, items: list[tuple[str, str, str]], current_idx: int) -> None:
        """Actualise le roster et declenche l'animation."""
        was_idx = self._current_idx
        self._items = items
        self._current_idx = max(-1, min(current_idx, len(items) - 1))

        # Declencher animation si changement d'index
        if was_idx >= 0 and was_idx != self._current_idx:
            n = len(items)
            if n > 1:
                step_forward = (self._current_idx - was_idx) % n
                step_backward = (was_idx - self._current_idx) % n
                self._anim_direction = 1 if step_forward <= step_backward else -1
            else:
                self._anim_direction = 1

            self._anim.stop()
            # L animation doit finir alignee sur le slot central (offset 0).
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim_offset = 1.0
            self._anim.start()
        else:
            self._anim_offset = 0.0
            self._anim_direction = 1

        self.update()

    def paintEvent(self, event) -> None:
        if not self._items or self._current_idx < 0:
            p = QPainter(self)
            p.fillRect(self.rect(), QBrush(QColor(_PANEL_BG)))
            p.setPen(QColor(_TEXT_SEC))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Aucun tour en cours")
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fond
        p.fillRect(self.rect(), QBrush(QColor(_PANEL_BG)))

        # Cadre
        border = QColor(_PANEL_BORDER)
        p.setPen(QPen(border, 1))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)

        # Zone centrale (highlight)
        center_y = (self.height() - self._item_height) // 2
        p.fillRect(0, center_y, self.width(), self._item_height, QBrush(QColor(_ACCENT + "22")))

        # Afficher plusieurs items visibles avec wrapping cyclique
        n = len(self._items)
        half_window = self._visible_items // 2
        anim_shift = self._item_height * self._anim_offset * self._anim_direction
        for slot in range(-half_window, half_window + 1):
            # Calculer l'index reel avec wrapping
            real_idx = (self._current_idx + slot) % n
            name, d20_str, status = self._items[real_idx]

            # Decaler toute la pile dans le sens de rotation pour eviter
            # le chevauchement des lignes sur de petits rosters (2 entites).
            offset_y = (slot * self._item_height) - anim_shift

            # Aligner chaque ligne sur la grille des slots pour garder
            # le curseur et le highlight parfaitement synchronises.
            y = int(center_y + offset_y)

            is_current = (slot == 0)
            if is_current:
                text_color = _YELLOW
            elif abs(slot) == 1:
                text_color = _TEXT_PRIMARY
            else:
                text_color = _TEXT_SEC
            marker = "▶ " if is_current else "  "

            text = f"{marker}{name} | {d20_str} | {status}"
            p.setPen(QColor(text_color))
            p.drawText(4, y, self.width() - 8, self._item_height, Qt.AlignmentFlag.AlignVCenter, text)


# ── Thread serveur ────────────────────────────────────────────────────────────

class _ServerWorker(QThread):
    """Exécute le serveur asyncio dans un thread dédié."""

    started_ok           = pyqtSignal(int)         # port
    stopped              = pyqtSignal()
    client_joined        = pyqtSignal(str)         # username
    client_left          = pyqtSignal(str)         # username
    entity_registered    = pyqtSignal(str)         # entity_name (auto-load côté MJ)
    spell_request_received = pyqtSignal(dict)      # spell request dict
    attack_request_received = pyqtSignal(dict)     # attack request dict
    damage_roll_result_received = pyqtSignal(dict) # damage roll result dict
    chat_received        = pyqtSignal(str, str)    # sender, message
    relay_info           = pyqtSignal(str)         # message relay
    relay_endpoint       = pyqtSignal(str)         # host du relay si actif
    error_occurred       = pyqtSignal(str)

    def __init__(self, host: str, port: int, password: str) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._password = password
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Server | None = None
        self._stop_event: asyncio.Event | None = None
        self._relay_args: argparse.Namespace | None = None
        self._relay_process: Optional[AsyncioProcess] = None
        self._relay_log_task: Optional[asyncio.Task[None]] = None

    # ── Thread entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_main())
        finally:
            self._loop.close()

    async def _async_main(self) -> None:
        self._stop_event = asyncio.Event()
        self._server = Server(self._host, self._port, self._password)
        try:
            await self._server.setup()
            self.started_ok.emit(self._port)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return

        # Démarrage relay VPS (si configuré)
        if _RELAY_HOST:
            self._relay_args = argparse.Namespace(
                host=self._host,
                port=self._port,
                password=self._password,
                relay_host=_RELAY_HOST,
                relay_user=_RELAY_USER,
                relay_ssh_port=_RELAY_SSH_PORT,
                relay_public_port=_RELAY_PUBLIC_PORT,
                relay_tunnel_port=_RELAY_TUNNEL_PORT,
                relay_key_file=_RELAY_KEY_FILE,
            )
            try:
                self._relay_process, self._relay_log_task = await start_vps_relay(self._relay_args)
                if self._relay_process is not None:
                    self.relay_info.emit(
                        f"Relay VPS actif: {_RELAY_HOST}:{_RELAY_PUBLIC_PORT} -> local:{self._port}"
                    )
                    self.relay_endpoint.emit(_RELAY_HOST)
            except RuntimeError as exc:
                self.relay_info.emit(f"Relay VPS indisponible: {exc}")
                self.relay_endpoint.emit("")

        known: set[str] = set()
        known_entities: set[tuple[str, str]] = set()  # (username, entity_name)
        while not self._stop_event.is_set():
            # Clients snapshot
            current = set(self._server.connected_clients.keys())
            for new in current - known:
                self.client_joined.emit(new)
                join_msg = CommandMessage("PLAYER_JOINED", {"username": new})
                for session in list(self._server.connected_clients.values()):
                    try:
                        await session.send_message(join_msg)
                    except Exception:
                        pass
            for left in known - current:
                self.client_left.emit(left)
                left_msg = CommandMessage("PLAYER_LEFT", {"username": left})
                for session in list(self._server.connected_clients.values()):
                    try:
                        await session.send_message(left_msg)
                    except Exception:
                        pass
            known = current
            
            # Détection des entités enregistrées
            current_entities = set()
            for session in list(self._server.connected_clients.values()):
                if session.bound_entity:
                    entity_name = str(session.bound_entity).strip()
                    if entity_name:
                        key = (session.username, entity_name)
                        current_entities.add(key)
                        # Émettre signal si c'est une nouvelle entité
                        if key not in known_entities:
                            self.entity_registered.emit(entity_name)
            known_entities = current_entities

            # Drain spell requests from all sessions
            for session in list(self._server.connected_clients.values()):
                if hasattr(session, "spell_requests"):
                    while session.spell_requests:
                        req = session.spell_requests.pop(0)
                        self.spell_request_received.emit(req)

            # Drain attack requests from all sessions
            for session in list(self._server.connected_clients.values()):
                if hasattr(session, "attack_requests"):
                    while session.attack_requests:
                        req = session.attack_requests.pop(0)
                        self.attack_request_received.emit(req)

            # Drain damage roll results from all sessions
            for session in list(self._server.connected_clients.values()):
                if hasattr(session, "damage_roll_results"):
                    while session.damage_roll_results:
                        req = session.damage_roll_results.pop(0)
                        self.damage_roll_result_received.emit(req)

            # Drain chat logs from all sessions
            for session in list(self._server.connected_clients.values()):
                while session.chat_log:
                    msg = session.chat_log.pop(0)
                    self.chat_received.emit(msg.sender, msg.message)

            await asyncio.sleep(0.3)

        await stop_vps_relay(self._relay_process, self._relay_log_task, self._relay_args)
        await self._server.shutdown()
        self.stopped.emit()

    # ── Public API (thread-safe) ──────────────────────────────────────────────

    def stop_server(self) -> None:
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    def broadcast_chat(self, sender: str, text: str) -> None:
        if self._loop is None or self._server is None:
            return

        async def _do() -> None:
            msg = ChatMessage(sender=sender, message=text)
            for session in list(self._server.connected_clients.values()):
                try:
                    await session.send_message(msg)
                except Exception:
                    pass

        asyncio.run_coroutine_threadsafe(_do(), self._loop)

    def push_entity_state(self, entity_name: str, state: dict[str, object]) -> None:
        """Envoie un snapshot d'etat a tous les clients lies a cette entite."""
        if self._loop is None or self._server is None:
            return

        async def _do() -> None:
            msg = CommandMessage("STATE_SYNC", {"entity_name": entity_name, "state": state})
            for session in list(self._server.connected_clients.values()):
                bound = (session.bound_entity or "").strip()
                if bound == entity_name:
                    try:
                        await session.send_message(msg)
                    except Exception:
                        pass

        asyncio.run_coroutine_threadsafe(_do(), self._loop)

    def broadcast_command(self, command: str, args: dict[str, object] | None = None) -> None:
        """Diffuse une commande protocole a tous les clients connectes."""
        if self._loop is None or self._server is None:
            return

        payload = args or {}

        async def _do() -> None:
            msg = CommandMessage(command, payload)
            for session in list(self._server.connected_clients.values()):
                try:
                    await session.send_message(msg)
                except Exception:
                    pass

        asyncio.run_coroutine_threadsafe(_do(), self._loop)

    def send_command_to_entity(self, entity_name: str, command: str, args: dict[str, object] | None = None) -> bool:
        """Envoie une commande a la session liee a une entite specifique."""
        if self._loop is None or self._server is None:
            return False

        entity_name = str(entity_name).strip()
        if not entity_name:
            return False
        payload = args or {}

        async def _do() -> bool:
            sent = False
            msg = CommandMessage(command, payload)
            for session in list(self._server.connected_clients.values()):
                bound = str(session.bound_entity or "").strip()
                if bound != entity_name:
                    continue
                try:
                    await session.send_message(msg)
                    sent = True
                except Exception:
                    pass
            return sent

        future = asyncio.run_coroutine_threadsafe(_do(), self._loop)
        try:
            return bool(future.result(timeout=1.5))
        except Exception:
            return False

    def broadcast_assets_files(self, categories: list[str] | None = None) -> None:
        """Envoie les fichiers JSON d'assets aux joueurs (sync fichiers réelle)."""
        if self._loop is None or self._server is None:
            return

        selected = categories or ["characters", "items", "spells"]
        allowed = {"characters", "items", "spells"}
        selected = [c for c in selected if c in allowed]
        if not selected:
            return

        async def _do() -> None:
            files_to_send: list[tuple[str, Path]] = []
            for category in selected:
                folder = Path("assets") / category
                if not folder.exists():
                    continue
                for p in sorted(folder.glob("*.json")):
                    files_to_send.append((category, p))

            begin_msg = CommandMessage(
                "ASSET_SYNC_BEGIN",
                {
                    "categories": selected,
                    "count": len(files_to_send),
                },
            )
            for session in list(self._server.connected_clients.values()):
                try:
                    await session.send_message(begin_msg)
                except Exception:
                    pass

            sent_count = 0
            for category, file_path in files_to_send:
                try:
                    content = file_path.read_text(encoding="utf-8")
                except OSError:
                    continue

                msg = CommandMessage(
                    "ASSET_FILE_SYNC",
                    {
                        "category": category,
                        "file_name": file_path.name,
                        "content": content,
                    },
                )
                for session in list(self._server.connected_clients.values()):
                    try:
                        await session.send_message(msg)
                    except Exception:
                        pass
                sent_count += 1

            done_msg = CommandMessage(
                "ASSET_SYNC_DONE",
                {
                    "categories": selected,
                    "count": sent_count,
                },
            )
            for session in list(self._server.connected_clients.values()):
                try:
                    await session.send_message(done_msg)
                except Exception:
                    pass

        asyncio.run_coroutine_threadsafe(_do(), self._loop)


# ── Panel gauche ──────────────────────────────────────────────────────────────

class _LeftPanel(QFrame):
    """Contrôle serveur + liste joueurs + chat."""

    send_chat_requested = pyqtSignal(str)  # text

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._local_share = ""
        self._public_share = ""
        self.setFixedWidth(240)
        self.setStyleSheet(f"""
            QFrame {{
                background: {_PANEL_BG};
                border-right: 1px solid {_PANEL_BORDER};
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_server_section())
        root.addWidget(self._hline())
        root.addWidget(self._make_players_section())
        root.addWidget(self._hline())
        root.addWidget(self._make_chat_section(), 1)

    # ── Sections ──────────────────────────────────────────────────────────────

    def _make_server_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {_PANEL_BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(8)

        # Titre
        title = QLabel("Serveur")
        f = QFont(); f.setBold(True); f.setPointSize(10)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

        # Statut
        self._status_lbl = QLabel("○ Arrêté")
        self._status_lbl.setStyleSheet(f"color:{_RED}; font-size:11px; background:transparent;")
        lay.addWidget(self._status_lbl)

        # Zone adresse de partage
        share_title = QLabel("Adresse à partager")
        share_title.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
        lay.addWidget(share_title)

        self._local_share_lbl = QLabel("Local : —")
        self._local_share_lbl.setStyleSheet(
            f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent; font-family:Consolas,monospace;"
        )
        lay.addWidget(self._local_share_lbl)

        local_copy_btn = QPushButton("Copier local")
        local_copy_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a2a3a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:4px; font-size:10px; padding:3px 8px;
            }}
            QPushButton:hover {{ background:#3a3a4a; }}
        """)
        local_copy_btn.clicked.connect(lambda: self._copy_share(self._local_share))
        lay.addWidget(local_copy_btn)

        self._public_share_lbl = QLabel("Public (host) : —")
        self._public_share_lbl.setStyleSheet(
            f"color:{_YELLOW}; font-size:10px; background:transparent; font-family:Consolas,monospace;"
        )
        lay.addWidget(self._public_share_lbl)

        public_copy_btn = QPushButton("Copier public")
        public_copy_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a2a3a; color:{_YELLOW}; border:1px solid {_PANEL_BORDER};
                border-radius:4px; font-size:10px; padding:3px 8px;
            }}
            QPushButton:hover {{ background:#3a3a4a; }}
        """)
        public_copy_btn.clicked.connect(lambda: self._copy_share(self._public_share))
        lay.addWidget(public_copy_btn)

        self._share_feedback_lbl = QLabel("")
        self._share_feedback_lbl.setStyleSheet(f"color:{_GREEN}; font-size:9px; background:transparent;")
        lay.addWidget(self._share_feedback_lbl)

        # Port
        port_row = QHBoxLayout()
        port_row.setSpacing(6)
        port_lbl = QLabel("Port")
        port_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
        port_lbl.setFixedWidth(40)
        port_row.addWidget(port_lbl)
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(7799)
        self._port_spin.setStyleSheet(f"""
            QSpinBox {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; padding:2px 4px; font-size:11px;
            }}
        """)
        port_row.addWidget(self._port_spin)
        lay.addLayout(port_row)

        # Mot de passe
        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(6)
        pwd_lbl = QLabel("Mdp")
        pwd_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
        pwd_lbl.setFixedWidth(40)
        pwd_row.addWidget(pwd_lbl)
        self._pwd_edit = QLineEdit("ROOM42")
        self._pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd_edit.setStyleSheet(f"""
            QLineEdit {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; padding:2px 4px; font-size:11px;
            }}
        """)
        pwd_row.addWidget(self._pwd_edit)
        lay.addLayout(pwd_row)

        # Bouton start/stop
        self._srv_btn = QPushButton("Démarrer")
        self._srv_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                border-radius:4px; font-size:11px; font-weight:bold; padding:5px;
            }}
            QPushButton:hover {{ background:#3a4a3a; }}
            QPushButton:disabled {{ color:{_TEXT_MUTED}; border-color:{_TEXT_MUTED};
                background:{_PANEL_BG}; }}
        """)
        lay.addWidget(self._srv_btn)

        return w

    def _make_players_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {_PANEL_BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        title = QLabel("Joueurs connectés")
        f = QFont(); f.setBold(True); f.setPointSize(10)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

        self._players_list = QListWidget()
        self._players_list.setFixedHeight(80)
        self._players_list.setStyleSheet(f"""
            QListWidget {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; font-size:10px;
            }}
            QListWidget::item {{ padding:2px 4px; }}
        """)
        lay.addWidget(self._players_list)

        return w

    def _make_chat_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {_PANEL_BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(6)

        title = QLabel("Chat")
        f = QFont(); f.setBold(True); f.setPointSize(10)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

        # Log scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:1px solid {_PANEL_BORDER}; border-radius:3px;
                background:#182030; }}
        """)
        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background:#182030;")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(6, 6, 6, 6)
        self._chat_layout.setSpacing(3)
        self._chat_layout.addStretch()
        scroll.setWidget(self._chat_container)
        self._chat_scroll = scroll
        lay.addWidget(scroll, 1)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Message MJ…")
        self._chat_input.setStyleSheet(f"""
            QLineEdit {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; padding:4px 6px; font-size:10px;
            }}
        """)
        self._chat_input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._chat_input)

        send_btn = QPushButton("→")
        send_btn.setFixedWidth(28)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background:{_ACCENT}; color:white; border:none;
                border-radius:3px; font-weight:bold; font-size:13px;
            }}
            QPushButton:hover {{ background:#9070d0; }}
        """)
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)
        lay.addLayout(input_row)

        return w

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_send(self) -> None:
        text = self._chat_input.text().strip()
        if text:
            self._chat_input.clear()
            self.send_chat_requested.emit(text)

    # ── Public API ────────────────────────────────────────────────────────────

    def append_chat(self, sender: str, message: str, color: str = _TEXT_PRIMARY) -> None:
        lbl = QLabel(f"<b style='color:{_YELLOW};'>{sender}</b> <span style='color:{color};'>{message}</span>")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background:transparent; font-size:10px;")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        # Insert before the trailing stretch
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, lbl)
        # Scroll to bottom
        QTimer.singleShot(50, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    def add_player(self, username: str) -> None:
        self._players_list.addItem(f"● {username}")

    def remove_player(self, username: str) -> None:
        for i in range(self._players_list.count()):
            if self._players_list.item(i).text().endswith(username):
                self._players_list.takeItem(i)
                break

    def set_server_running(self, running: bool, port: int = 0) -> None:
        if running:
            self._status_lbl.setText(f"● En ligne — :{port}")
            self._status_lbl.setStyleSheet(f"color:{_GREEN}; font-size:11px; background:transparent;")
            self._srv_btn.setText("Arrêter")
            self._srv_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#3a1e1e; color:{_RED}; border:1px solid #c04040;
                    border-radius:4px; font-size:11px; font-weight:bold; padding:5px;
                }}
                QPushButton:hover {{ background:#4a2e2e; }}
            """)
            self._port_spin.setEnabled(False)
            self._pwd_edit.setEnabled(False)
        else:
            self._status_lbl.setText("○ Arrêté")
            self._status_lbl.setStyleSheet(f"color:{_RED}; font-size:11px; background:transparent;")
            self._srv_btn.setText("Démarrer")
            self._srv_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                    border-radius:4px; font-size:11px; font-weight:bold; padding:5px;
                }}
                QPushButton:hover {{ background:#3a4a3a; }}
            """)
            self._port_spin.setEnabled(True)
            self._pwd_edit.setEnabled(True)
            self._players_list.clear()
            self.set_share_endpoints(local_endpoint="", public_endpoint="")

    def set_share_endpoints(self, local_endpoint: str, public_endpoint: str = "") -> None:
        self._local_share = local_endpoint.strip()
        self._public_share = public_endpoint.strip()

        self._local_share_lbl.setText(f"Local : {self._local_share or '—'}")
        self._public_share_lbl.setText(f"Public (host) : {self._public_share or '—'}")

    def _copy_share(self, value: str) -> None:
        text = value.strip()
        if not text:
            self._share_feedback_lbl.setText("Rien à copier")
            return
        app = QApplication.instance()
        if app is None:
            return
        clipboard = app.clipboard()
        clipboard.setText(text)
        self._share_feedback_lbl.setText(f"Copié : {text}")
        QTimer.singleShot(1500, lambda: self._share_feedback_lbl.setText(""))

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{_PANEL_BORDER};")
        return line

    @property
    def srv_btn(self) -> QPushButton:
        return self._srv_btn

    @property
    def port(self) -> int:
        return self._port_spin.value()

    @property
    def password(self) -> str:
        return self._pwd_edit.text()


# ── Zone centrale ─────────────────────────────────────────────────────────────

class _CentralArea(QWidget):
    """Toolbar de chargement + grille d'EntityCards."""

    add_entity_requested = pyqtSignal(str)   # char_name
    remove_entity_requested = pyqtSignal(str)  # entity_name
    manual_spell_requested = pyqtSignal()
    sync_assets_requested = pyqtSignal()
    combat_updated = pyqtSignal(str)
    combat_action_requested = pyqtSignal(str, str)  # action, entity_name

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {_APP_BG};")
        self._char_names: list[str] = self._list_characters()
        self._cards: dict[str, EntityCard] = {}
        self._build_ui()
        
    class _ResourcesTab(QWidget):
        """Gestion des ressources du jeu (characters, items, spells)."""
        
        resources_changed = pyqtSignal(str)  # category
        sync_requested = pyqtSignal()
        
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._category_to_dir = {
                "characters": Path("assets/characters"),
                "items": Path("assets/items"),
                "spells": Path("assets/spells"),
            }
            self._current_file: Path | None = None
            self.setStyleSheet(f"background:{_APP_BG};")
            self._build_ui()
            self._refresh_list()
        
        def _build_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(12, 12, 12, 12)
            root.setSpacing(8)
        
            top = QHBoxLayout()
            top.setSpacing(8)
        
            title = QLabel("Ressources")
            f = QFont(); f.setBold(True); f.setPointSize(12)
            title.setFont(f)
            title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
            top.addWidget(title)
        
            top.addStretch()
        
            self._category_combo = QComboBox()
            self._category_combo.addItems(["characters", "items", "spells"])
            self._category_combo.setStyleSheet(f"""
                QComboBox {{
                    background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                    border-radius:4px; padding:4px 8px; font-size:11px; min-width:130px;
                }}
                QComboBox::drop-down {{ border:none; }}
            """)
            self._category_combo.currentTextChanged.connect(lambda _: self._refresh_list())
            top.addWidget(self._category_combo)
        
            refresh_btn = QPushButton("Rafraîchir")
            refresh_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#2a2a3a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                    border-radius:4px; font-size:10px; padding:4px 8px;
                }}
                QPushButton:hover {{ background:#3a3a4a; }}
            """)
            refresh_btn.clicked.connect(self._refresh_list)
            top.addWidget(refresh_btn)

            sync_btn = QPushButton("Synchroniser avec joueurs")
            sync_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#2a2a3f; color:{_YELLOW}; border:1px solid #807050;
                    border-radius:4px; font-size:10px; font-weight:bold; padding:4px 10px;
                }}
                QPushButton:hover {{ background:#3a3a4f; }}
            """)
            sync_btn.clicked.connect(self.sync_requested.emit)
            top.addWidget(sync_btn)
        
            root.addLayout(top)
        
            body = QHBoxLayout()
            body.setSpacing(10)
        
            # Colonne liste fichiers
            left_col = QVBoxLayout()
            left_col.setSpacing(6)
        
            self._resource_list = QListWidget()
            self._resource_list.setMinimumWidth(240)
            self._resource_list.setStyleSheet(f"""
                QListWidget {{
                    background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                    border-radius:4px; font-size:10px;
                }}
                QListWidget::item {{ padding:3px 6px; }}
                QListWidget::item:selected {{ background:{_ACCENT}; color:white; }}
            """)
            self._resource_list.currentTextChanged.connect(self._on_resource_selected)
            left_col.addWidget(self._resource_list, 1)
        
            left_btns = QHBoxLayout()
            left_btns.setSpacing(6)
        
            new_btn = QPushButton("+ Ajouter")
            new_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                    border-radius:4px; font-size:10px; font-weight:bold; padding:3px 8px;
                }}
                QPushButton:hover {{ background:#3a4a3a; }}
            """)
            new_btn.clicked.connect(self._on_add_resource)
            left_btns.addWidget(new_btn)
        
            del_btn = QPushButton("- Supprimer")
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#3a1e1e; color:{_RED}; border:1px solid #804040;
                    border-radius:4px; font-size:10px; font-weight:bold; padding:3px 8px;
                }}
                QPushButton:hover {{ background:#4a2a2a; }}
            """)
            del_btn.clicked.connect(self._on_delete_resource)
            left_btns.addWidget(del_btn)
        
            left_col.addLayout(left_btns)
            body.addLayout(left_col, 0)
        
            # Colonne éditeur
            right_col = QVBoxLayout()
            right_col.setSpacing(6)
        
            self._path_lbl = QLabel("Aucune ressource sélectionnée")
            self._path_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            right_col.addWidget(self._path_lbl)
        
            self._editor = QPlainTextEdit()
            self._editor.setPlaceholderText("Sélectionne une ressource pour l'éditer…")
            self._editor.setStyleSheet(f"""
                QPlainTextEdit {{
                    background:#111826; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                    border-radius:4px; font-size:11px; font-family:Consolas,monospace;
                    selection-background-color:{_ACCENT};
                }}
            """)
            right_col.addWidget(self._editor, 1)
        
            right_btns = QHBoxLayout()
            right_btns.setSpacing(6)
        
            format_btn = QPushButton("Formater JSON")
            format_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#2a3a2a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                    border-radius:4px; font-size:10px; padding:4px 8px;
                }}
                QPushButton:hover {{ background:#3a3a4a; }}
            """)
            format_btn.clicked.connect(self._on_format_json)
            right_btns.addWidget(format_btn)
        
            right_btns.addStretch()
        
            save_btn = QPushButton("Enregistrer")
            save_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                    border-radius:4px; font-size:10px; font-weight:bold; padding:4px 10px;
                }}
                QPushButton:hover {{ background:#3a4a3a; }}
            """)
            save_btn.clicked.connect(self._on_save_resource)
            right_btns.addWidget(save_btn)
        
            right_col.addLayout(right_btns)
            body.addLayout(right_col, 1)
        
            root.addLayout(body, 1)
        
        def _current_category(self) -> str:
            return self._category_combo.currentText().strip()
        
        def _current_dir(self) -> Path:
            return self._category_to_dir.get(self._current_category(), Path("assets"))
        
        def _refresh_list(self) -> None:
            folder = self._current_dir()
            folder.mkdir(parents=True, exist_ok=True)
            self._resource_list.clear()
            for p in sorted(folder.glob("*.json")):
                self._resource_list.addItem(p.name)
            self._current_file = None
            self._path_lbl.setText(f"Dossier: {folder}")
            self._editor.clear()
        
        def _on_resource_selected(self, file_name: str) -> None:
            if not file_name:
                self._current_file = None
                self._path_lbl.setText("Aucune ressource sélectionnée")
                self._editor.clear()
                return
            file_path = self._current_dir() / file_name
            self._current_file = file_path
            self._path_lbl.setText(str(file_path))
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                QMessageBox.critical(self, "Lecture ressource", f"Impossible de lire le fichier:\n{exc}")
                return
            self._editor.setPlainText(content)
        
        def _default_payload(self, category: str, name: str) -> dict[str, object]:
            if category == "characters":
                return {
                    "name": name,
                    "stats": {
                        "str": 50, "dex": 50, "int": 50, "agi": 50, "con": 50,
                        "wis": 50, "cha": 50, "per": 50, "luc": 50, "sur": 50,
                        "mental_health": 100, "drug_health": 100, "stamina": 100,
                    },
                    "stats_modifier": {},
                    "inventory": {},
                    "spells": [],
                }
            if category == "items":
                return {
                    "name": name,
                    "description": "",
                    "stats_modifier": {},
                }
            if category == "spells":
                return {
                    "name": name,
                    "cost": 10,
                    "description": "",
                    "targeting": "single",
                    "runtime_policy": "instant",
                    "delay": 1,
                    "effects": [
                        {
                            "target": "target.hp",
                            "effect": "malus",
                            "formula": "10",
                        }
                    ],
                }
            return {"name": name}
        
        def _on_add_resource(self) -> None:
            category = self._current_category()
            file_name, ok = QInputDialog.getText(
                self,
                "Nouvelle ressource",
                f"Nom du fichier JSON ({category})",
                text="nouvelle_ressource",
            )
            if not ok:
                return
            clean = str(file_name).strip()
            if not clean:
                QMessageBox.warning(self, "Nouvelle ressource", "Nom vide.")
                return
            if not clean.endswith(".json"):
                clean += ".json"
        
            path = self._current_dir() / clean
            if path.exists():
                QMessageBox.warning(self, "Nouvelle ressource", "Ce fichier existe déjà.")
                return
        
            payload = self._default_payload(category, path.stem)
            try:
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                QMessageBox.critical(self, "Nouvelle ressource", f"Impossible de créer le fichier:\n{exc}")
                return
        
            self._refresh_list()
            matches = self._resource_list.findItems(clean, Qt.MatchFlag.MatchExactly)
            if matches:
                self._resource_list.setCurrentItem(matches[0])
            self.resources_changed.emit(category)
        
        def _on_delete_resource(self) -> None:
            current = self._resource_list.currentItem()
            if current is None:
                QMessageBox.warning(self, "Suppression", "Aucune ressource sélectionnée.")
                return
            file_name = current.text()
            path = self._current_dir() / file_name
            res = QMessageBox.question(
                self,
                "Suppression",
                f"Supprimer la ressource '{file_name}' ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if res != QMessageBox.StandardButton.Yes:
                return
        
            try:
                path.unlink(missing_ok=False)
            except Exception as exc:
                QMessageBox.critical(self, "Suppression", f"Impossible de supprimer:\n{exc}")
                return
        
            category = self._current_category()
            self._refresh_list()
            self.resources_changed.emit(category)
        
        def _on_format_json(self) -> None:
            raw = self._editor.toPlainText()
            try:
                data = json.loads(raw)
            except Exception as exc:
                QMessageBox.warning(self, "Format JSON", f"JSON invalide:\n{exc}")
                return
            self._editor.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        
        def _on_save_resource(self) -> None:
            if self._current_file is None:
                QMessageBox.warning(self, "Enregistrement", "Aucune ressource sélectionnée.")
                return
        
            raw = self._editor.toPlainText()
            try:
                data = json.loads(raw)
            except Exception as exc:
                QMessageBox.warning(self, "Enregistrement", f"JSON invalide:\n{exc}")
                return
        
            try:
                self._current_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                QMessageBox.critical(self, "Enregistrement", f"Impossible d'écrire le fichier:\n{exc}")
                return
        
            QMessageBox.information(self, "Enregistrement", "Ressource enregistrée.")
            self.resources_changed.emit(self._current_category())

    class _CombatTab(QWidget):
        """Gestion de combat MJ : création, initiative d20 éditable et progression des tours."""

        combat_updated = pyqtSignal(str)
        action_requested = pyqtSignal(str, str)  # action, entity_name

        def __init__(self, get_entities_callable, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._get_entities = get_entities_callable
            self._participants: list[str] = []
            self._status: dict[str, str] = {}
            self._d20: dict[str, int] = {}
            self._order: list[str] = []
            self._current_turn_idx: int = -1
            self._round: int = 1
            self._combat_started = False
            self._build_ui()
            self.refresh_entities()

        def _build_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(12, 12, 12, 12)
            root.setSpacing(8)

            top = QHBoxLayout()
            title = QLabel("Combat")
            f = QFont(); f.setBold(True); f.setPointSize(12)
            title.setFont(f)
            title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
            top.addWidget(title)
            top.addStretch()

            refresh_btn = QPushButton("Rafraîchir entités")
            refresh_btn.clicked.connect(self.refresh_entities)
            refresh_btn.setStyleSheet(f"background:#2a2a3a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER}; border-radius:4px; padding:4px 8px;")
            top.addWidget(refresh_btn)

            new_btn = QPushButton("Nouveau combat")
            new_btn.clicked.connect(self._start_new_combat)
            new_btn.setStyleSheet(f"background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050; border-radius:4px; padding:4px 8px;")
            top.addWidget(new_btn)

            init_btn = QPushButton("Init d20")
            init_btn.clicked.connect(self._roll_initiative_d20)
            init_btn.setStyleSheet(f"background:#2a2a3f; color:{_YELLOW}; border:1px solid #807050; border-radius:4px; padding:4px 8px;")
            top.addWidget(init_btn)

            next_btn = QPushButton("tour_suivant")
            next_btn.clicked.connect(self._next_turn)
            next_btn.setStyleSheet(f"background:#3a2a1e; color:{_YELLOW}; border:1px solid #807050; border-radius:4px; padding:4px 8px; font-weight:bold;")
            top.addWidget(next_btn)

            root.addLayout(top)

            self._state_lbl = QLabel("Aucun combat actif.")
            self._state_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            root.addWidget(self._state_lbl)

            # Sélection des entités participantes
            pick_title = QLabel("Participants (entités chargées)")
            pick_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
            root.addWidget(pick_title)

            self._pool_list = QListWidget()
            self._pool_list.setFixedHeight(120)
            self._pool_list.setStyleSheet(f"""
                QListWidget {{
                    background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                    border-radius:4px; font-size:10px;
                }}
                QListWidget::item {{ padding:2px 6px; }}
            """)
            root.addWidget(self._pool_list)

            # Contrôles d'édition initiative/statut
            edit_row = QHBoxLayout()
            edit_row.setSpacing(6)

            self._fighter_combo = QComboBox()
            self._fighter_combo.setStyleSheet(f"background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER}; border-radius:4px; padding:3px 6px;")
            edit_row.addWidget(self._fighter_combo)

            d20_lbl = QLabel("d20")
            d20_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent;")
            edit_row.addWidget(d20_lbl)

            self._d20_spin = QSpinBox()
            self._d20_spin.setRange(1, 20)
            self._d20_spin.setValue(10)
            self._d20_spin.setStyleSheet(f"background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER}; border-radius:4px; padding:3px 6px;")
            edit_row.addWidget(self._d20_spin)

            set_d20_btn = QPushButton("Appliquer d20")
            set_d20_btn.clicked.connect(self._set_selected_d20)
            set_d20_btn.setStyleSheet(f"background:#2a2a3a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER}; border-radius:4px; padding:3px 8px;")
            edit_row.addWidget(set_d20_btn)

            status_lbl = QLabel("Statut")
            status_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent;")
            edit_row.addWidget(status_lbl)

            self._status_combo = QComboBox()
            self._status_combo.addItems(["OK", "KO"])
            self._status_combo.setStyleSheet(f"background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER}; border-radius:4px; padding:3px 6px;")
            edit_row.addWidget(self._status_combo)

            set_status_btn = QPushButton("Appliquer statut")
            set_status_btn.clicked.connect(self._set_selected_status)
            set_status_btn.setStyleSheet(f"background:#2a2a3a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER}; border-radius:4px; padding:3px 8px;")
            edit_row.addWidget(set_status_btn)

            edit_row.addStretch()
            root.addLayout(edit_row)

            # Roster combat (machine a sous)
            roster_title = QLabel("Ordre de combat")
            roster_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
            root.addWidget(roster_title)

            self._roster = _SlotMachineRoster()
            root.addWidget(self._roster, 1)

            # Feuille du personnage actif + actions
            action_title = QLabel("Tour en cours")
            action_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
            root.addWidget(action_title)

            action_row = QHBoxLayout()
            action_row.setSpacing(6)

            self._spell_btn = QPushButton("spell")
            self._spell_btn.setStyleSheet(
                f"background:#2a2a3f; color:{_YELLOW}; border:1px solid #807050; border-radius:4px; padding:4px 10px;"
            )
            self._spell_btn.clicked.connect(lambda: self._emit_action("spell"))
            action_row.addWidget(self._spell_btn)

            self._strike_btn = QPushButton("strike")
            self._strike_btn.setStyleSheet(
                f"background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050; border-radius:4px; padding:4px 10px;"
            )
            self._strike_btn.clicked.connect(lambda: self._emit_action("strike"))
            action_row.addWidget(self._strike_btn)

            self._shoot_btn = QPushButton("shoot")
            self._shoot_btn.setStyleSheet(
                f"background:#3a2a1e; color:{_YELLOW}; border:1px solid #807050; border-radius:4px; padding:4px 10px;"
            )
            self._shoot_btn.clicked.connect(lambda: self._emit_action("shoot"))
            action_row.addWidget(self._shoot_btn)

            action_row.addStretch()
            root.addLayout(action_row)

            self._sheet_scroll = QScrollArea()
            self._sheet_scroll.setWidgetResizable(True)
            self._sheet_scroll.setMinimumHeight(260)
            self._sheet_scroll.setStyleSheet(f"QScrollArea {{ border:1px solid {_PANEL_BORDER}; background:{_APP_BG}; border-radius:4px; }}")
            root.addWidget(self._sheet_scroll, 2)

            self._sheet_placeholder = QLabel("Aucun tour en cours.")
            self._sheet_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._sheet_placeholder.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            self._sheet_scroll.setWidget(self._sheet_placeholder)

            self._turn_sheet: EntitySheet | None = None
            self._turn_sheet_entity_name = ""

            self._fighter_combo.currentTextChanged.connect(self._on_selected_fighter_changed)

        def _entities(self) -> dict[str, Entity]:
            data = self._get_entities()
            return dict(data) if isinstance(data, dict) else {}

        def refresh_entities(self) -> None:
            entities = self._entities()
            names = sorted(entities.keys())

            # Liste pool (checkboxes)
            previously_checked = set(self._participants)
            self._pool_list.clear()
            for name in names:
                item = QListWidgetItem(name)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if name in previously_checked else Qt.CheckState.Unchecked)
                self._pool_list.addItem(item)

            # Nettoyer les participants supprimés
            alive = set(names)
            self._participants = [n for n in self._participants if n in alive]
            self._status = {k: v for k, v in self._status.items() if k in alive}
            self._d20 = {k: v for k, v in self._d20.items() if k in alive}
            self._order = [n for n in self._order if n in alive]

            self._refresh_fighter_combo()
            self._refresh_roster()

        def _refresh_fighter_combo(self) -> None:
            current = self._fighter_combo.currentText()
            self._fighter_combo.blockSignals(True)
            self._fighter_combo.clear()
            self._fighter_combo.addItems(self._participants)
            if current in self._participants:
                self._fighter_combo.setCurrentText(current)
            self._fighter_combo.blockSignals(False)
            self._on_selected_fighter_changed(self._fighter_combo.currentText())

        def _selected_pool_names(self) -> list[str]:
            out: list[str] = []
            for i in range(self._pool_list.count()):
                item = self._pool_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    out.append(item.text())
            return out

        def _start_new_combat(self) -> None:
            selected = self._selected_pool_names()
            if not selected:
                self.combat_updated.emit("Impossible de créer un combat: aucune entité sélectionnée.")
                return

            self._participants = selected
            self._status = {name: "OK" for name in self._participants}
            self._d20 = {name: randint(1, 20) for name in self._participants}
            self._recompute_order()
            self._current_turn_idx = -1
            self._round = 1
            self._combat_started = True
            self._refresh_fighter_combo()
            self._refresh_roster()
            self.combat_updated.emit(f"Nouveau combat créé avec {len(self._participants)} entité(s).")

        def _roll_initiative_d20(self) -> None:
            if not self._participants:
                self.combat_updated.emit("Aucun combat actif pour lancer l'initiative.")
                return
            self._d20 = {name: randint(1, 20) for name in self._participants}
            self._recompute_order()
            self._refresh_roster()
            self._on_selected_fighter_changed(self._fighter_combo.currentText())
            self.combat_updated.emit("Initiative d20 relancée pour tous les participants.")

        def _recompute_order(self) -> None:
            current_name = ""
            if 0 <= self._current_turn_idx < len(self._order):
                current_name = self._order[self._current_turn_idx]

            # L'ordre de tour est defini uniquement par l'initiative d20.
            # Regle de table: plus le d20 est faible, plus on agit tot.
            self._order = sorted(self._participants, key=lambda n: self._d20.get(n, 1))

            if current_name and current_name in self._order:
                self._current_turn_idx = self._order.index(current_name)
            elif self._current_turn_idx >= len(self._order):
                self._current_turn_idx = -1

        def _on_selected_fighter_changed(self, fighter_name: str) -> None:
            if not fighter_name:
                return
            self._d20_spin.setValue(self._d20.get(fighter_name, 10))
            status = self._status.get(fighter_name, "OK")
            idx = self._status_combo.findText(status)
            if idx >= 0:
                self._status_combo.setCurrentIndex(idx)

        def _set_selected_d20(self) -> None:
            name = self._fighter_combo.currentText().strip()
            if not name:
                return
            self._d20[name] = int(self._d20_spin.value())
            self._recompute_order()
            self._refresh_roster()
            self.combat_updated.emit(f"{name}: d20 initiative -> {self._d20[name]}")

        def _set_selected_status(self) -> None:
            name = self._fighter_combo.currentText().strip()
            if not name:
                return
            status = self._status_combo.currentText().strip() or "OK"
            if status not in {"OK", "KO"}:
                status = "OK"
            self._status[name] = status
            self._refresh_roster()
            self.combat_updated.emit(f"{name}: statut -> {status}")

        def _resolve_spell_events_for(self, entity_name: str) -> int:
            entities = self._entities()
            entity = entities.get(entity_name)
            if entity is None:
                return 0

            # Enregistrer les entités/sorts pour permettre aux SpellEvent de résoudre les cibles.
            from libs.registry.entity import EntityRegistry
            from libs.registry.spell import SpellRegistry

            for e in entities.values():
                EntityRegistry.register(e.name, e)
                for spell in e.character.spells.values():
                    SpellRegistry.register(spell)

            applied = 0
            for event in list(entity.spell_events):
                if event.finished:
                    continue
                valid_targets = [target_id for target_id in event.targets_ids if target_id in entities]
                before_cast = event.nb_cast
                event.apply(valid_targets)
                if event.nb_cast != before_cast or event.finished:
                    applied += 1
            return applied

        def _next_turn(self) -> None:
            if not self._combat_started or not self._order:
                self.combat_updated.emit("Aucun combat actif. Crée d'abord un nouveau combat.")
                return

            prev_idx = self._current_turn_idx
            chosen_idx = -1

            for _ in range(len(self._order)):
                self._current_turn_idx = (self._current_turn_idx + 1) % len(self._order)
                candidate = self._order[self._current_turn_idx]
                if self._status.get(candidate, "OK") == "OK":
                    chosen_idx = self._current_turn_idx
                    break

            if chosen_idx < 0:
                self.combat_updated.emit("Aucun combattant en état OK. Combat en pause.")
                self._refresh_roster()
                return

            if prev_idx >= 0 and chosen_idx <= prev_idx:
                self._round += 1

            current_name = self._order[chosen_idx]
            resolved_count = self._resolve_spell_events_for(current_name)
            self._refresh_roster()
            self.combat_updated.emit(
                f"Round {self._round} - {current_name}: 1) spell_events résolus ({resolved_count}), "
                f"2) phase d'action, 3) cliquer tour_suivant pour passer au suivant."
            )

        def _current_turn_entity_name(self) -> str:
            if 0 <= self._current_turn_idx < len(self._order):
                return str(self._order[self._current_turn_idx])
            return ""

        def _emit_action(self, action: str) -> None:
            actor = self._current_turn_entity_name()
            if not actor:
                self.combat_updated.emit("Aucun combattant actif pour cette action.")
                return
            self.action_requested.emit(str(action), actor)

        def _refresh_turn_sheet(self) -> None:
            actor = self._current_turn_entity_name()
            entities = self._entities()
            entity = entities.get(actor)

            has_actor = bool(entity is not None)
            self._spell_btn.setEnabled(has_actor)
            self._strike_btn.setEnabled(has_actor)
            self._shoot_btn.setEnabled(has_actor)

            if entity is None:
                if self._turn_sheet is not None:
                    self._turn_sheet.deleteLater()
                    self._turn_sheet = None
                self._turn_sheet_entity_name = ""
                self._sheet_placeholder = QLabel("Aucun tour en cours.")
                self._sheet_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._sheet_placeholder.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
                self._sheet_scroll.setWidget(self._sheet_placeholder)
                return

            if self._turn_sheet is None:
                self._turn_sheet = EntitySheet(entity, show_cast_buttons=False, gm_mode=True)
                self._turn_sheet_entity_name = entity.name
                self._sheet_scroll.setWidget(self._turn_sheet)
                return

            self._turn_sheet.set_entity(entity)
            self._turn_sheet_entity_name = entity.name

        def _refresh_roster(self) -> None:
            self._recompute_order()

            if not self._order:
                self._state_lbl.setText("Aucun combat actif.")
                self._roster.set_roster([], -1)
                return

            current = "—"
            if 0 <= self._current_turn_idx < len(self._order):
                current = self._order[self._current_turn_idx]
            self._state_lbl.setText(f"Combat actif | Round {self._round} | Tour actuel: {current}")

            entities = self._entities()
            items: list[tuple[str, str, str]] = []
            for name in self._order:
                status = self._status.get(name, "OK")
                d20 = self._d20.get(name, 1)
                entity = entities.get(name)
                hp = entity.get_stat("hp") if entity is not None else 0
                sta = entity.get_stat("stamina") if entity is not None else 0
                
                d20_str = f"d20:{d20:02d}"
                status_str = f"HP:{hp} | STA:{sta} | {status}"
                items.append((name, d20_str, status_str))

            self._roster.set_roster(items, self._current_turn_idx)
            self._refresh_turn_sheet()

        def combat_state_payload(self) -> dict[str, object]:
            current = ""
            if 0 <= self._current_turn_idx < len(self._order):
                current = self._order[self._current_turn_idx]

            participants: list[dict[str, object]] = []
            for name in self._order:
                participants.append(
                    {
                        "name": name,
                        "initiative": int(self._d20.get(name, 1)),
                        "status": self._status.get(name, "OK"),
                    }
                )

            return {
                "active": bool(self._combat_started and bool(self._order)),
                "round": int(self._round),
                "current_turn_idx": int(self._current_turn_idx),
                "current_turn": current,
                "order": [str(name) for name in self._order],
                "participants": participants,
            }

    def _list_characters(self) -> list[str]:
        folder = Path("assets/characters")
        if not folder.exists():
            return []
        return sorted(p.stem for p in folder.glob("*.json"))

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border:1px solid {_PANEL_BORDER}; background:{_APP_BG}; }}
            QTabBar::tab {{
                background:{_HEADER_BG}; color:{_TEXT_SEC}; border:1px solid {_PANEL_BORDER};
                padding:6px 12px; font-size:10px;
            }}
            QTabBar::tab:selected {{ color:{_TEXT_PRIMARY}; background:#32324a; }}
        """)

        # Onglet Entites
        entities_tab = QWidget()
        entities_root = QVBoxLayout(entities_tab)
        entities_root.setContentsMargins(0, 0, 0, 0)
        entities_root.setSpacing(0)

        entities_root.addWidget(self._make_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{_APP_BG}; }}")

        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet(f"background:{_APP_BG};")
        self._cards_layout = QHBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(16, 16, 16, 16)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_widget)
        entities_root.addWidget(scroll, 1)

        # Onglet Ressources
        self._resources_tab = self._ResourcesTab()
        self._resources_tab.resources_changed.connect(self._on_resources_changed)
        self._resources_tab.sync_requested.connect(self.sync_assets_requested.emit)

        # Onglet Combat
        self._combat_tab = self._CombatTab(self._collect_entities_for_combat)
        self._combat_tab.combat_updated.connect(self._on_combat_updated)
        self._combat_tab.action_requested.connect(self.combat_action_requested.emit)

        self._tabs.addTab(entities_tab, "Entités")
        self._tabs.addTab(self._resources_tab, "Ressources")
        self._tabs.addTab(self._combat_tab, "Combat")
        root.addWidget(self._tabs, 1)

    def _on_resources_changed(self, category: str) -> None:
        """Rafraichit les widgets dependants quand une ressource change."""
        if category != "characters":
            return
        current = self._char_combo.currentText()
        self._char_names = self._list_characters()
        self._char_combo.blockSignals(True)
        self._char_combo.clear()
        self._char_combo.addItems(self._char_names)
        if current in self._char_names:
            self._char_combo.setCurrentText(current)
        self._char_combo.blockSignals(False)

    def _collect_entities_for_combat(self) -> dict[str, Entity]:
        return {name: card.entity for name, card in self._cards.items()}

    def _on_combat_updated(self, message: str) -> None:
        self.refresh_all()
        self.combat_updated.emit(message)

    def current_combat_state(self) -> dict[str, object]:
        return self._combat_tab.combat_state_payload()

    def _make_toolbar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background:{_HEADER_BG}; border-bottom:1px solid {_PANEL_BORDER};
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(8)

        title = QLabel("Entités")
        f = QFont(); f.setBold(True); f.setPointSize(12)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

        lay.addSpacing(16)

        self._char_combo = QComboBox()
        self._char_combo.addItems(self._char_names)
        self._char_combo.setStyleSheet(f"""
            QComboBox {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:4px; padding:4px 8px; font-size:11px; min-width:140px;
            }}
            QComboBox::drop-down {{ border:none; }}
            QComboBox QAbstractItemView {{
                background:#182030; color:{_TEXT_PRIMARY}; selection-background-color:{_ACCENT};
            }}
        """)
        lay.addWidget(self._char_combo)

        add_btn = QPushButton("+ Ajouter")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                border-radius:4px; font-size:11px; font-weight:bold; padding:4px 10px;
            }}
            QPushButton:hover {{ background:#3a4a3a; }}
        """)
        add_btn.clicked.connect(self._on_add)
        lay.addWidget(add_btn)

        cast_btn = QPushButton("Lancer sort (MJ)")
        cast_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a2a3f; color:{_YELLOW}; border:1px solid #807050;
                border-radius:4px; font-size:11px; font-weight:bold; padding:4px 10px;
            }}
            QPushButton:hover {{ background:#3a3a4f; }}
        """)
        cast_btn.clicked.connect(self.manual_spell_requested.emit)
        lay.addWidget(cast_btn)

        lay.addStretch()

        badge = QLabel("MJ")
        badge.setStyleSheet(
            f"background:#3a1a3a; border:1px solid #c060c0; border-radius:4px;"
            f"color:#e0a0e0; font-size:10px; font-weight:bold;"
            f"padding:2px 8px; font-family:Consolas,monospace;"
        )
        lay.addWidget(badge)

        return bar

    def _on_add(self) -> None:
        char_name = self._char_combo.currentText()
        if char_name:
            self.add_entity_requested.emit(char_name)

    def add_card(self, entity: Entity) -> None:
        if entity.name in self._cards:
            return
        card = EntityCard(entity, gm_mode=True, show_cast_buttons=True)
        # Insert before the trailing stretch
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
        self._cards[entity.name] = card
        if hasattr(self, "_combat_tab"):
            self._combat_tab.refresh_entities()

    def remove_card(self, entity_name: str) -> None:
        card = self._cards.pop(entity_name, None)
        if card:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        if hasattr(self, "_combat_tab"):
            self._combat_tab.refresh_entities()

    def refresh_all(self) -> None:
        for card in self._cards.values():
            card.refresh()


# ── Panel de résolution de sorts ──────────────────────────────────────────────

class SpellResolutionDialog(QDialog):
    """Popup de résolution de sort : sélection des cibles et lancer de leurs dés."""

    def __init__(self, request: dict, entities: dict[str, Entity], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Résolution du sort")
        self.setStyleSheet(f"QDialog {{ background:{_APP_BG}; }}")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)

        self.request = request
        self.entities = entities
        self.user_dices: dict[str, int] = dict(request.get("user_dices", {})) if isinstance(request.get("user_dices", {}), dict) else {}
        self.targets_dices: dict[str, dict[str, int]] = {}
        self._user_spinboxes: dict[str, QSpinBox] = {}
        self._updating_checks = False

        from libs.spells.spell_def import Spell
        self.spell = Spell.from_name(request.get("spell_key", ""))
        self.is_multi = (self.spell is not None and self.spell.targeting == "multi")
        self._required_user_stats = self._extract_user_dice_requirements()
        self._required_target_stats = self._extract_target_dice_requirements()

        self._build_ui()

    def _extract_target_dice_requirements(self) -> set[str]:
        """Détecte les stats de défense requises (target.stat) depuis les formules."""
        required: set[str] = set()
        if not self.spell or not hasattr(self.spell, "effects"):
            return required
        for effect in self.spell.effects:
            formula = effect.formula
            if not hasattr(formula, "placeholders"):
                continue
            for cls, args in formula.placeholders:
                if cls.__name__ == "DiceRatio" and len(args) >= 1:
                    arg = str(args[0])
                    if "." in arg:
                        who, stat = arg.split(".", 1)
                        if who == "target":
                            required.add(stat)
                elif cls.__name__ == "DiceAttack" and len(args) >= 2:
                    arg = str(args[1])
                    if "." in arg:
                        who, stat = arg.split(".", 1)
                        if who == "target":
                            required.add(stat)
        return required

    def _extract_user_dice_requirements(self) -> set[str]:
        """Détecte les stats lanceur requises (user.stat) depuis les formules."""
        required: set[str] = set()
        if not self.spell or not hasattr(self.spell, "effects"):
            return required
        for effect in self.spell.effects:
            formula = effect.formula
            if not hasattr(formula, "placeholders"):
                continue
            for cls, args in formula.placeholders:
                if cls.__name__ == "DiceRatio" and len(args) >= 1:
                    arg = str(args[0])
                    if "." in arg:
                        who, stat = arg.split(".", 1)
                        if who == "user":
                            required.add(stat)
                elif cls.__name__ == "DiceAttack" and len(args) >= 1:
                    arg = str(args[0])
                    if "." in arg:
                        who, stat = arg.split(".", 1)
                        if who == "user":
                            required.add(stat)
        return required

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Titre
        title = QLabel("Résolution du sort")
        f = QFont(); f.setBold(True); f.setPointSize(12)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        root.addWidget(title)

        # Info lanceur + sort
        spell_key = self.request.get("spell_key", "Unknown")
        user = self.request.get("user", "Unknown")
        user_dices = self.request.get("user_dices", {})
        targeting_badge = "multi" if self.is_multi else "single"

        info_lbl = QLabel(
            f"<b>{user}</b> lance <b style='color:{_ACCENT};'>{spell_key}</b>"
            f" <span style='color:{_TEXT_SEC}; font-size:9px;'>[{targeting_badge}]</span>"
        )
        info_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        info_lbl.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(info_lbl)

        # Dés du lanceur (éditables par le MJ)
        user_title = QLabel("Dés lanceur :")
        user_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
        root.addWidget(user_title)

        if not self._required_user_stats:
            dices_lbl = QLabel("Aucun dé lanceur requis pour ce sort.")
            dices_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            root.addWidget(dices_lbl)
        else:
            for stat in sorted(self._required_user_stats):
                row = QHBoxLayout()
                row.setSpacing(8)

                stat_lbl = QLabel(stat)
                stat_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent; min-width:60px;")
                row.addWidget(stat_lbl)

                spin = QSpinBox()
                spin.setRange(1, 100)
                spin.setValue(int(self.user_dices.get(stat, 50)))
                spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                spin.setStyleSheet(
                    f"QSpinBox {{ background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};"
                    "border-radius:3px; font-size:10px; padding:2px 4px; min-width:58px; }}"
                )
                self._user_spinboxes[stat] = spin
                row.addWidget(spin)

                roll_btn = QPushButton("d100")
                roll_btn.setStyleSheet(f"""
                    QPushButton {{
                        background:#3c3c7a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                        border-radius:3px; padding:3px 8px; font-size:9px;
                    }}
                    QPushButton:hover {{ background:#5050aa; }}
                """)
                roll_btn.clicked.connect(lambda _=False, s=spin: s.setValue(randint(1, 100)))
                row.addWidget(roll_btn)
                row.addStretch()

                w = QWidget(); w.setStyleSheet("background:transparent;")
                w.setLayout(row)
                root.addWidget(w)

        root.addSpacing(6)

        # Section cibles (QListWidget avec checkboxes)
        target_title = QLabel("Cibles" + (" (sélection multiple)" if self.is_multi else " :"))
        target_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
        root.addWidget(target_title)

        self._target_list = QListWidget()
        self._target_list.setFixedHeight(130)
        self._target_list.setStyleSheet(f"""
            QListWidget {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; font-size:10px;
            }}
            QListWidget::item:selected {{ background:{_ACCENT}; }}
        """)
        for name in sorted(self.entities.keys()):
            item = QListWidgetItem(name)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._target_list.addItem(item)

        requested_targets = {
            str(t).strip()
            for t in self.request.get("targets", [])
            if str(t).strip() in self.entities
        }
        self._updating_checks = True
        if requested_targets:
            for i in range(self._target_list.count()):
                item = self._target_list.item(i)
                if item.text() in requested_targets:
                    item.setCheckState(Qt.CheckState.Checked)
            if not self.is_multi:
                # En single, garder uniquement une cible (la première demandée rencontrée).
                already = False
                for i in range(self._target_list.count()):
                    item = self._target_list.item(i)
                    if item.checkState() == Qt.CheckState.Checked:
                        if not already:
                            already = True
                        else:
                            item.setCheckState(Qt.CheckState.Unchecked)
        elif not self.is_multi and self._target_list.count() > 0:
            self._target_list.item(0).setCheckState(Qt.CheckState.Checked)
        self._updating_checks = False

        self._target_list.itemChanged.connect(self._on_item_changed)
        root.addWidget(self._target_list)

        root.addSpacing(6)

        # Section dés de défense par cible (scrollable)
        dice_title = QLabel("Dés de défense :")
        dice_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
        root.addWidget(dice_title)

        self._dice_scroll = QScrollArea()
        self._dice_scroll.setWidgetResizable(True)
        self._dice_scroll.setMinimumHeight(80)
        self._dice_scroll.setMaximumHeight(200)
        self._dice_scroll.setStyleSheet(f"QScrollArea {{ border:1px solid {_PANEL_BORDER}; background:{_APP_BG}; }}")
        root.addWidget(self._dice_scroll, 1)

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_ok = QPushButton("✓ Confirmer")
        btn_ok.setStyleSheet(f"""
            QPushButton {{
                background:{_GREEN}; color:#000; font-weight:bold; border:none;
                border-radius:3px; padding:6px 14px; font-size:11px;
            }}
            QPushButton:hover {{ background:#90e89c; }}
        """)
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("✗ Annuler")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background:{_RED}; color:#fff; font-weight:bold; border:none;
                border-radius:3px; padding:6px 14px; font-size:11px;
            }}
            QPushButton:hover {{ background:#f49ab6; }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        root.addLayout(btn_layout)

        # Initialiser la section des dés
        self._rebuild_dice_section()

    def _on_item_changed(self, changed_item: QListWidgetItem) -> None:
        """Gère les changements de sélection — enforce single pour sort non-multi."""
        if self._updating_checks:
            return
        if not self.is_multi and changed_item.checkState() == Qt.CheckState.Checked:
            self._updating_checks = True
            for i in range(self._target_list.count()):
                item = self._target_list.item(i)
                if item is not changed_item:
                    item.setCheckState(Qt.CheckState.Unchecked)
            self._updating_checks = False
        self._rebuild_dice_section()

    def _get_checked_targets(self) -> list[str]:
        return [
            self._target_list.item(i).text()
            for i in range(self._target_list.count())
            if self._target_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _rebuild_dice_section(self) -> None:
        """Reconstruit la section des dés selon les cibles cochées."""
        # Nettoyer les cibles décochées
        checked = set(self._get_checked_targets())
        for k in list(self.targets_dices.keys()):
            if k not in checked:
                del self.targets_dices[k]

        container = QWidget()
        container.setStyleSheet(f"background:{_APP_BG};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        if not checked:
            lbl = QLabel("Aucune cible sélectionnée.")
            lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            layout.addWidget(lbl)
        elif not self._required_target_stats:
            lbl = QLabel("Aucun dé de défense requis pour ce sort.")
            lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            layout.addWidget(lbl)
        else:
            for target_name in sorted(checked):
                if target_name not in self.targets_dices:
                    self.targets_dices[target_name] = {}

                group_lbl = QLabel(f"► {target_name}")
                f = QFont(); f.setBold(True); f.setPointSize(9)
                group_lbl.setFont(f)
                group_lbl.setStyleSheet(f"color:{_YELLOW}; background:transparent;")
                layout.addWidget(group_lbl)

                for stat in sorted(self._required_target_stats):
                    row = QHBoxLayout()
                    row.setSpacing(8)

                    stat_lbl = QLabel(stat)
                    stat_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent; min-width:60px;")
                    row.addWidget(stat_lbl)

                    existing = int(self.targets_dices[target_name].get(stat, 50))
                    spin = QSpinBox()
                    spin.setRange(1, 100)
                    spin.setValue(existing)
                    spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    spin.setStyleSheet(
                        f"QSpinBox {{ background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};"
                        "border-radius:3px; font-size:10px; padding:2px 4px; min-width:58px; }}"
                    )
                    self.targets_dices[target_name][stat] = int(existing)
                    spin.valueChanged.connect(lambda value, tn=target_name, s=stat: self._set_target_dice_value(tn, s, value))
                    row.addWidget(spin)

                    roll_btn = QPushButton("d100")
                    roll_btn.setStyleSheet(f"""
                        QPushButton {{
                            background:#3c3c7a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                            border-radius:3px; padding:3px 8px; font-size:9px;
                        }}
                        QPushButton:hover {{ background:#5050aa; }}
                    """)
                    roll_btn.clicked.connect(lambda _=False, s=spin: s.setValue(randint(1, 100)))
                    row.addWidget(roll_btn)
                    row.addStretch()

                    w = QWidget(); w.setStyleSheet("background:transparent;")
                    w.setLayout(row)
                    layout.addWidget(w)

        layout.addStretch()
        self._dice_scroll.setWidget(container)

    def _set_target_dice_value(self, target_name: str, stat: str, value: int) -> None:
        if target_name not in self.targets_dices:
            self.targets_dices[target_name] = {}
        self.targets_dices[target_name][stat] = int(value)

    def exec(self) -> dict | None:
        if super().exec() == QDialog.DialogCode.Accepted:
            targets = self._get_checked_targets()
            if not targets:
                return None
            if self._user_spinboxes:
                self.user_dices = {stat: int(spin.value()) for stat, spin in self._user_spinboxes.items()}
                self.request["user_dices"] = dict(self.user_dices)
            self.request["targets"] = targets
            self.request["targets_dices"] = {t: d for t, d in self.targets_dices.items() if t in targets}
            return self.request
        return None


class MJSpellCastDialog(QDialog):
    """Popup MJ pour lancer un sort en renseignant toutes les infos."""

    def __init__(self, entities: dict[str, Entity], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Lancer un sort (MJ)")
        self.setStyleSheet(f"QDialog {{ background:{_APP_BG}; }}")
        self.setMinimumWidth(620)
        self.setMinimumHeight(520)

        self.entities = entities
        self._updating_checks = False
        self._user_spinboxes: dict[str, QSpinBox] = {}
        self._target_spinboxes: dict[tuple[str, str], QSpinBox] = {}

        self._build_ui()
        self._on_caster_changed()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Cast manuel MJ")
        f = QFont(); f.setBold(True); f.setPointSize(12)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        root.addWidget(title)

        # Lanceur + sort
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        caster_lbl = QLabel("Lanceur")
        caster_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent;")
        top_row.addWidget(caster_lbl)

        self._caster_combo = QComboBox()
        self._caster_combo.addItems(sorted(self.entities.keys()))
        self._caster_combo.setStyleSheet(f"""
            QComboBox {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; padding:4px 6px; font-size:10px; min-width:160px;
            }}
            QComboBox::drop-down {{ border:none; }}
        """)
        self._caster_combo.currentTextChanged.connect(self._on_caster_changed)
        top_row.addWidget(self._caster_combo)

        spell_lbl = QLabel("Sort")
        spell_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent;")
        top_row.addWidget(spell_lbl)

        self._spell_combo = QComboBox()
        self._spell_combo.setStyleSheet(f"""
            QComboBox {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; padding:4px 6px; font-size:10px; min-width:220px;
            }}
            QComboBox::drop-down {{ border:none; }}
        """)
        self._spell_combo.currentTextChanged.connect(self._on_spell_changed)
        top_row.addWidget(self._spell_combo, 1)

        root.addLayout(top_row)

        # Cibles
        targets_title = QLabel("Cibles")
        targets_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
        root.addWidget(targets_title)

        self._target_list = QListWidget()
        self._target_list.setFixedHeight(140)
        self._target_list.setStyleSheet(f"""
            QListWidget {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; font-size:10px;
            }}
            QListWidget::item:selected {{ background:{_ACCENT}; }}
        """)
        self._target_list.itemChanged.connect(self._on_target_item_changed)
        root.addWidget(self._target_list)

        # Dés lanceur
        user_title = QLabel("Dés du lanceur")
        user_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
        root.addWidget(user_title)

        self._user_dice_scroll = QScrollArea()
        self._user_dice_scroll.setWidgetResizable(True)
        self._user_dice_scroll.setMinimumHeight(90)
        self._user_dice_scroll.setMaximumHeight(150)
        self._user_dice_scroll.setStyleSheet(f"QScrollArea {{ border:1px solid {_PANEL_BORDER}; background:{_APP_BG}; }}")
        root.addWidget(self._user_dice_scroll)

        # Dés cibles
        target_dice_title = QLabel("Dés des cibles")
        target_dice_title.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
        root.addWidget(target_dice_title)

        self._target_dice_scroll = QScrollArea()
        self._target_dice_scroll.setWidgetResizable(True)
        self._target_dice_scroll.setMinimumHeight(120)
        self._target_dice_scroll.setStyleSheet(f"QScrollArea {{ border:1px solid {_PANEL_BORDER}; background:{_APP_BG}; }}")
        root.addWidget(self._target_dice_scroll, 1)

        # Boutons
        btns = QHBoxLayout()
        btns.addStretch()

        ok_btn = QPushButton("✓ Lancer")
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background:{_GREEN}; color:#000; font-weight:bold; border:none;
                border-radius:3px; padding:6px 14px; font-size:11px;
            }}
            QPushButton:hover {{ background:#90e89c; }}
        """)
        ok_btn.clicked.connect(self.accept)
        btns.addWidget(ok_btn)

        cancel_btn = QPushButton("✗ Annuler")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{_RED}; color:#fff; font-weight:bold; border:none;
                border-radius:3px; padding:6px 14px; font-size:11px;
            }}
            QPushButton:hover {{ background:#f49ab6; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        root.addLayout(btns)

    def _current_caster(self) -> Entity | None:
        return self.entities.get(self._caster_combo.currentText())

    def set_caster(self, entity_name: str) -> None:
        idx = self._caster_combo.findText(str(entity_name))
        if idx >= 0:
            self._caster_combo.setCurrentIndex(idx)

    def _current_spell(self):
        caster = self._current_caster()
        if not caster:
            return None
        return caster.character.spells.get(self._spell_combo.currentText())

    def _extract_dice_requirements(self) -> tuple[set[str], set[str]]:
        """Retourne (stats_user, stats_target) nécessaires aux formules."""
        user_required: set[str] = set()
        target_required: set[str] = set()
        spell = self._current_spell()
        if not spell:
            return user_required, target_required

        for effect in spell.effects:
            formula = effect.formula
            if not hasattr(formula, "placeholders"):
                continue
            for cls, args in formula.placeholders:
                if cls.__name__ == "DiceRatio" and len(args) >= 1:
                    arg = str(args[0])
                    if "." in arg:
                        who, stat = arg.split(".", 1)
                        if who == "user":
                            user_required.add(stat)
                        elif who == "target":
                            target_required.add(stat)
                elif cls.__name__ == "DiceAttack" and len(args) >= 2:
                    user_arg = str(args[0])
                    target_arg = str(args[1])
                    if "." in user_arg:
                        who, stat = user_arg.split(".", 1)
                        if who == "user":
                            user_required.add(stat)
                    if "." in target_arg:
                        who, stat = target_arg.split(".", 1)
                        if who == "target":
                            target_required.add(stat)
        return user_required, target_required

    def _roll_into_spin(self, spin: QSpinBox) -> None:
        from libs.dice import Dice
        dice = Dice.roll("1d100")
        value = dice.dices_values[0] if dice.dices_values else 1
        spin.setValue(value)

    def _rebuild_targets(self) -> None:
        caster_name = self._caster_combo.currentText()
        spell = self._current_spell()
        is_multi = bool(spell and spell.targeting == "multi")

        self._updating_checks = True
        self._target_list.clear()
        for name in sorted(self.entities.keys()):
            item = QListWidgetItem(name)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            # défaut: 1ere cible cochée, en excluant le lanceur si possible
            default_checked = False
            if self._target_list.count() == 0:
                default_checked = (name != caster_name)
            item.setCheckState(Qt.CheckState.Checked if default_checked else Qt.CheckState.Unchecked)
            self._target_list.addItem(item)

        # si rien coché, cocher la première
        if all(self._target_list.item(i).checkState() != Qt.CheckState.Checked for i in range(self._target_list.count())):
            if self._target_list.count() > 0:
                self._target_list.item(0).setCheckState(Qt.CheckState.Checked)

        # enforce single
        if not is_multi:
            first_checked_idx = next(
                (i for i in range(self._target_list.count()) if self._target_list.item(i).checkState() == Qt.CheckState.Checked),
                0,
            )
            for i in range(self._target_list.count()):
                self._target_list.item(i).setCheckState(Qt.CheckState.Checked if i == first_checked_idx else Qt.CheckState.Unchecked)
        self._updating_checks = False

    def _checked_targets(self) -> list[str]:
        return [
            self._target_list.item(i).text()
            for i in range(self._target_list.count())
            if self._target_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _rebuild_user_dices(self) -> None:
        self._user_spinboxes = {}
        required_user, _ = self._extract_dice_requirements()

        container = QWidget()
        container.setStyleSheet(f"background:{_APP_BG};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        if not required_user:
            lbl = QLabel("Aucun dé lanceur requis pour ce sort.")
            lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            layout.addWidget(lbl)
        else:
            for stat in sorted(required_user):
                row = QHBoxLayout()
                row.setSpacing(8)

                stat_lbl = QLabel(stat)
                stat_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent; min-width:70px;")
                row.addWidget(stat_lbl)

                spin = QSpinBox()
                spin.setRange(1, 100)
                spin.setValue(50)
                spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                spin.setStyleSheet(
                    f"QSpinBox {{ background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};"
                    "border-radius:3px; font-size:10px; padding:2px 4px; min-width:58px; }}"
                )
                self._user_spinboxes[stat] = spin
                row.addWidget(spin)

                roll_btn = QPushButton("d100")
                roll_btn.setStyleSheet(f"""
                    QPushButton {{
                        background:#3c3c7a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                        border-radius:3px; padding:3px 8px; font-size:9px;
                    }}
                    QPushButton:hover {{ background:#5050aa; }}
                """)
                roll_btn.clicked.connect(lambda _=False, s=spin: self._roll_into_spin(s))
                row.addWidget(roll_btn)
                row.addStretch()

                w = QWidget(); w.setStyleSheet("background:transparent;")
                w.setLayout(row)
                layout.addWidget(w)

        layout.addStretch()
        self._user_dice_scroll.setWidget(container)

    def _rebuild_targets_dices(self) -> None:
        required_user, required_target = self._extract_dice_requirements()
        _ = required_user
        checked = self._checked_targets()

        self._target_spinboxes = {}
        container = QWidget()
        container.setStyleSheet(f"background:{_APP_BG};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        if not checked:
            lbl = QLabel("Aucune cible sélectionnée.")
            lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            layout.addWidget(lbl)
        elif not required_target:
            lbl = QLabel("Aucun dé cible requis pour ce sort.")
            lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            layout.addWidget(lbl)
        else:
            for target_name in checked:
                target_lbl = QLabel(f"► {target_name}")
                f = QFont(); f.setBold(True); f.setPointSize(9)
                target_lbl.setFont(f)
                target_lbl.setStyleSheet(f"color:{_YELLOW}; background:transparent;")
                layout.addWidget(target_lbl)

                for stat in sorted(required_target):
                    row = QHBoxLayout()
                    row.setSpacing(8)

                    stat_lbl = QLabel(stat)
                    stat_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent; min-width:70px;")
                    row.addWidget(stat_lbl)

                    spin = QSpinBox()
                    spin.setRange(1, 100)
                    spin.setValue(50)
                    spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    spin.setStyleSheet(
                        f"QSpinBox {{ background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};"
                        "border-radius:3px; font-size:10px; padding:2px 4px; min-width:58px; }}"
                    )
                    self._target_spinboxes[(target_name, stat)] = spin
                    row.addWidget(spin)

                    roll_btn = QPushButton("d100")
                    roll_btn.setStyleSheet(f"""
                        QPushButton {{
                            background:#3c3c7a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                            border-radius:3px; padding:3px 8px; font-size:9px;
                        }}
                        QPushButton:hover {{ background:#5050aa; }}
                    """)
                    roll_btn.clicked.connect(lambda _=False, s=spin: self._roll_into_spin(s))
                    row.addWidget(roll_btn)
                    row.addStretch()

                    w = QWidget(); w.setStyleSheet("background:transparent;")
                    w.setLayout(row)
                    layout.addWidget(w)

        layout.addStretch()
        self._target_dice_scroll.setWidget(container)

    def _on_caster_changed(self) -> None:
        caster = self._current_caster()
        self._spell_combo.clear()
        if caster is not None:
            self._spell_combo.addItems(sorted(caster.character.spells.keys()))
        self._on_spell_changed()

    def _on_spell_changed(self) -> None:
        self._rebuild_targets()
        self._rebuild_user_dices()
        self._rebuild_targets_dices()

    def _on_target_item_changed(self, changed_item: QListWidgetItem) -> None:
        if self._updating_checks:
            return
        spell = self._current_spell()
        is_multi = bool(spell and spell.targeting == "multi")
        if not is_multi and changed_item.checkState() == Qt.CheckState.Checked:
            self._updating_checks = True
            for i in range(self._target_list.count()):
                item = self._target_list.item(i)
                if item is not changed_item:
                    item.setCheckState(Qt.CheckState.Unchecked)
            self._updating_checks = False
        self._rebuild_targets_dices()

    def exec(self) -> dict | None:
        if super().exec() != QDialog.DialogCode.Accepted:
            return None

        caster = self._current_caster()
        if caster is None:
            QMessageBox.warning(self, "Cast sort", "Aucun lanceur sélectionné.")
            return None

        spell_key = self._spell_combo.currentText().strip()
        if not spell_key:
            QMessageBox.warning(self, "Cast sort", "Aucun sort sélectionné.")
            return None

        targets = self._checked_targets()
        if not targets:
            QMessageBox.warning(self, "Cast sort", "Sélectionne au moins une cible.")
            return None

        user_dices = {stat: int(spin.value()) for stat, spin in self._user_spinboxes.items()}

        targets_dices: dict[str, dict[str, int]] = {}
        for target_name in targets:
            target_values: dict[str, int] = {}
            for (t_name, stat), spin in self._target_spinboxes.items():
                if t_name == target_name:
                    target_values[stat] = int(spin.value())
            targets_dices[target_name] = target_values

        return {
            "spell_key": spell_key,
            "user": caster.name,
            "targets": targets,
            "user_dices": user_dices,
            "targets_dices": targets_dices,
        }


class CombatAttackDialog(QDialog):
    """Popup de resolution pour shoot/strike avec selection cible et des d100."""

    def __init__(
            self,
            action: str,
            attacker_name: str,
            target_names: list[str],
            preferred_target: str = "",
            initial_user_dice: int = 50,
            parent: QWidget | None = None,
        ) -> None:
        super().__init__(parent)
        self._action = str(action).strip().lower()
        self._attacker_name = attacker_name
        self._target_names = target_names

        action_label = "Strike" if self._action == "strike" else "Shoot"
        self.setWindowTitle(f"Resolution {action_label}")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(f"QDialog {{ background:{_APP_BG}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        if self._action == "strike":
            matchup = "user(str) vs target(con)"
        else:
            matchup = "user(dex) vs target(agi)"

        title = QLabel(f"{action_label} - {attacker_name}")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        root.addWidget(title)

        subtitle = QLabel(matchup)
        subtitle.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
        root.addWidget(subtitle)

        target_row = QHBoxLayout()
        target_row.setSpacing(8)
        target_lbl = QLabel("Cible")
        target_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        target_row.addWidget(target_lbl)

        self._target_combo = QComboBox()
        self._target_combo.addItems(target_names)
        if preferred_target and preferred_target in target_names:
            self._target_combo.setCurrentText(preferred_target)
        self._target_combo.setStyleSheet(
            f"QComboBox {{ background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};"
            " border-radius:4px; padding:4px 8px; font-size:10px; }}"
        )
        target_row.addWidget(self._target_combo, 1)
        root.addLayout(target_row)

        self._user_spin = QSpinBox()
        self._user_spin.setRange(1, 100)
        self._user_spin.setValue(max(1, min(int(initial_user_dice), 100)))
        self._target_spin = QSpinBox()
        self._target_spin.setRange(1, 100)
        self._target_spin.setValue(50)

        for spin in (self._user_spin, self._target_spin):
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setStyleSheet(
                f"QSpinBox {{ background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};"
                " border-radius:3px; font-size:10px; padding:2px 4px; min-width:58px; }}"
            )

        def _add_dice_row(label_text: str, spin: QSpinBox) -> None:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
            row.addWidget(lbl)
            row.addWidget(spin)
            roll_btn = QPushButton("d100")
            roll_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#3c3c7a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                    border-radius:3px; padding:3px 8px; font-size:9px;
                }}
                QPushButton:hover {{ background:#5050aa; }}
            """)
            roll_btn.clicked.connect(lambda _=False, s=spin: s.setValue(randint(1, 100)))
            row.addWidget(roll_btn)
            row.addStretch()
            root.addLayout(row)

        _add_dice_row("De attaquant", self._user_spin)
        _add_dice_row("De cible", self._target_spin)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:{_PANEL_BG}; color:{_TEXT_SEC}; border:1px solid {_PANEL_BORDER};"
            " border-radius:4px; padding:5px 12px; }}"
        )
        buttons.addWidget(cancel_btn)

        validate_btn = QPushButton("Valider")
        validate_btn.clicked.connect(self.accept)
        validate_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                border-radius:4px; font-weight:bold; padding:5px 12px;
            }}
            QPushButton:hover {{ background:#3a4a3a; }}
        """)
        buttons.addWidget(validate_btn)
        root.addLayout(buttons)

    def exec(self) -> dict | None:
        if super().exec() != QDialog.DialogCode.Accepted:
            return None
        target = self._target_combo.currentText().strip()
        if not target:
            return None
        return {
            "action": self._action,
            "attacker": self._attacker_name,
            "target": target,
            "user_dice": int(self._user_spin.value()),
            "target_dice": int(self._target_spin.value()),
        }


# ── Fenêtre principale MJ ─────────────────────────────────────────────────────

class MJWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JDR-To-Aru — Mode MJ")
        self.resize(1200, 700)
        self.setStyleSheet(f"QMainWindow {{ background:{_APP_BG}; }}")

        self._server_worker: _ServerWorker | None = None
        self._entities: dict[str, Entity] = {}
        self._local_share_endpoint = ""
        self._public_share_endpoint = ""
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(1000)
        self._sync_timer.timeout.connect(self._sync_entities_to_players)
        self._sync_timer.start()
        self._pending_damage_rolls: dict[str, dict[str, object]] = {}

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #45475a; }")

        self._left  = _LeftPanel()
        self._central = _CentralArea()

        splitter.addWidget(self._left)
        splitter.addWidget(self._central)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    def _connect_signals(self) -> None:
        self._left.srv_btn.clicked.connect(self._on_server_toggle)
        self._left.send_chat_requested.connect(self._on_mj_chat)
        self._central.add_entity_requested.connect(self._on_add_entity)
        self._central.manual_spell_requested.connect(self._on_manual_spell_cast)
        self._central.sync_assets_requested.connect(self._on_sync_assets_requested)
        self._central.combat_updated.connect(self._on_combat_updated)
        self._central.combat_action_requested.connect(self._on_combat_action_requested)

    # ── Server controls ───────────────────────────────────────────────────────

    def _on_server_toggle(self) -> None:
        if self._server_worker and self._server_worker.isRunning():
            self._server_worker.stop_server()
        else:
            self._start_server()

    def _start_server(self) -> None:
        port = self._left.port
        password = self._left.password
        if not password:
            QMessageBox.warning(self, "Mot de passe vide", "Veuillez saisir un mot de passe.")
            return

        self._left.srv_btn.setEnabled(False)
        self._server_worker = _ServerWorker("0.0.0.0", port, password)
        self._server_worker.started_ok.connect(self._on_server_started)
        self._server_worker.stopped.connect(self._on_server_stopped)
        self._server_worker.client_joined.connect(self._on_client_joined)
        self._server_worker.client_left.connect(self._on_client_left)
        self._server_worker.entity_registered.connect(self._on_auto_load_entity)
        self._server_worker.spell_request_received.connect(self._on_spell_request)
        self._server_worker.attack_request_received.connect(self._on_attack_request)
        self._server_worker.damage_roll_result_received.connect(self._on_damage_roll_result)
        self._server_worker.chat_received.connect(self._on_chat_received)
        self._server_worker.relay_info.connect(self._on_relay_info)
        self._server_worker.relay_endpoint.connect(self._on_relay_endpoint)
        self._server_worker.error_occurred.connect(self._on_server_error)
        self._server_worker.start()

    def _on_server_started(self, port: int) -> None:
        self._left.srv_btn.setEnabled(True)
        self._left.set_server_running(True, port)
        self._local_share_endpoint = f"{_guess_lan_ip()}:{port}"
        self._left.set_share_endpoints(
            local_endpoint=self._local_share_endpoint,
            public_endpoint=self._public_share_endpoint,
        )
        self._left.append_chat("Système", f"Serveur démarré sur le port {port}.", color=_GREEN)

    def _on_server_stopped(self) -> None:
        self._left.srv_btn.setEnabled(True)
        self._left.set_server_running(False)
        self._local_share_endpoint = ""
        self._public_share_endpoint = ""
        self._left.append_chat("Système", "Serveur arrêté.", color=_YELLOW)
        self._server_worker = None

    def _on_server_error(self, reason: str) -> None:
        self._left.srv_btn.setEnabled(True)
        self._left.set_server_running(False)
        QMessageBox.critical(self, "Erreur serveur", reason)
        self._server_worker = None

    def _on_client_joined(self, username: str) -> None:
        self._left.add_player(username)
        self._left.append_chat("Système", f"{username} a rejoint la partie.", color=_GREEN)

    def _on_client_left(self, username: str) -> None:
        self._left.remove_player(username)
        self._left.append_chat("Système", f"{username} a quitté la partie.", color=_YELLOW)

    def _on_chat_received(self, sender: str, message: str) -> None:
        self._left.append_chat(sender, message)

    def _on_relay_info(self, message: str) -> None:
        self._left.append_chat("Relay", message, color=_YELLOW)

    def _on_relay_endpoint(self, endpoint: str) -> None:
        self._public_share_endpoint = endpoint.strip()
        self._left.set_share_endpoints(
            local_endpoint=self._local_share_endpoint,
            public_endpoint=self._public_share_endpoint,
        )

    def _on_auto_load_entity(self, entity_name: str) -> None:
        """Auto-charge une entité quand un joueur s'y connecte."""
        entity_name = str(entity_name).strip()
        if not entity_name or entity_name in self._entities:
            return
        
        # Essayer de charger l'entité
        char = Character.from_name(entity_name)
        if char is None:
            self._left.append_chat(
                "Système",
                f"⚠️ Impossible de charger l'entité « {entity_name} ».",
                color=_RED
            )
            return
        
        # Ajouter à la liste
        entity = Entity(name=entity_name, character=char)
        self._entities[entity_name] = entity
        self._central.add_card(entity)
        self._left.append_chat(
            "Système",
            f"✓ Entité « {entity_name} » chargée automatiquement.",
            color=_GREEN
        )

    def _on_spell_request(self, request: dict) -> None:
        """Handle incoming spell cast request — show resolution dialog."""
        spell_key = request.get("spell_key", "Unknown")
        user = request.get("user", "Unknown")
        user_dices = request.get("user_dices", {})
        
        # Log dans le chat
        dices_str = ", ".join(f"{k}:{v}" for k, v in sorted(user_dices.items())) if user_dices else "—"
        message = f"[SORT] {user} : {spell_key} (dés: {dices_str})"
        self._left.append_chat("Demande", message, color=_YELLOW)

        # Ouvrir le dialog de résolution
        dialog = SpellResolutionDialog(request, self._entities, self)
        resolved_request = dialog.exec()

        if resolved_request:
            self._on_spell_resolved(resolved_request)

    def _on_attack_request(self, request: dict) -> None:
        """Handle incoming strike/shoot request from a player."""
        action = str(request.get("action", "")).strip().lower()
        user = str(request.get("user", "")).strip()
        target = str(request.get("target", "")).strip()
        username = str(request.get("username", "")).strip()
        user_dices = request.get("user_dices", {})

        if action not in {"strike", "shoot"} or not user:
            return

        dices_str = ", ".join(f"{k}:{v}" for k, v in sorted(user_dices.items())) if isinstance(user_dices, dict) and user_dices else "—"
        self._left.append_chat(
            "Demande",
            f"[ATTAQUE] {username or user}: {action} -> {target or '?'} (dés: {dices_str})",
            color=_YELLOW,
        )

        expected_stat = "str" if action == "strike" else "dex"
        preferred_user_dice = 50
        if isinstance(user_dices, dict):
            preferred_user_dice = int(user_dices.get(expected_stat, 50) or 50)

        self._resolve_combat_attack(
            action,
            user,
            preferred_target=target,
            forced_user_dice=preferred_user_dice,
        )

    def _on_damage_roll_result(self, payload: dict) -> None:
        """Apply damage sent by the player after DAMAGE_ROLL_REQUEST."""
        if not isinstance(payload, dict):
            return

        request_id = str(payload.get("request_id", "")).strip()
        if not request_id:
            return
        pending = self._pending_damage_rolls.pop(request_id, None)
        if not pending:
            return

        attacker_name = str(pending.get("attacker", ""))
        target_name = str(pending.get("target", ""))
        action = str(pending.get("action", ""))
        damage_dice = str(pending.get("damage_dice", ""))

        target = self._entities.get(target_name)
        if target is None:
            self._left.append_chat("Erreur", f"Cible introuvable pour dégâts: {target_name}", color=_RED)
            return

        rolls = [int(v) for v in payload.get("rolls", [])] if isinstance(payload.get("rolls", []), list) else []
        total = int(payload.get("total", 0) or 0)

        target.character.stats_modifier.hp -= total

        rolls_str = "+".join(str(v) for v in rolls) if rolls else "—"
        self._left.append_chat(
            "Combat",
            (
                f"{attacker_name} -> {target_name} [{action}] | "
                f"dégâts {damage_dice} => {rolls_str} = {total}"
            ),
            color=_YELLOW,
        )

        self._central.refresh_all()
        self._sync_entities_to_players()

    def _on_mj_chat(self, text: str) -> None:
        self._left.append_chat("MJ", text, color=_PURPLE)
        if self._server_worker:
            self._server_worker.broadcast_chat("MJ", text)

    def _on_manual_spell_cast(self, preferred_caster: str | None = None) -> None:
        """Ouvre le popup de cast manuel côté MJ."""
        if not self._entities:
            self._left.append_chat("Système", "Aucune entité chargée pour lancer un sort.", color=_YELLOW)
            return
        dialog = MJSpellCastDialog(self._entities, self)
        if preferred_caster:
            dialog.set_caster(preferred_caster)
        resolved_request = dialog.exec()
        if resolved_request:
            self._on_spell_resolved(resolved_request)

    def _on_combat_action_requested(self, action: str, entity_name: str) -> None:
        action = str(action).strip().lower()
        entity_name = str(entity_name).strip()
        if not entity_name:
            return

        if action == "spell":
            self._on_manual_spell_cast(entity_name)
            return

        if action in {"strike", "shoot"}:
            self._resolve_combat_attack(action, entity_name)
            return

    def _resolve_combat_attack(
            self,
            action: str,
            attacker_name: str,
            preferred_target: str = "",
            forced_user_dice: int | None = None,
        ) -> None:
        attacker = self._entities.get(attacker_name)
        if attacker is None:
            self._left.append_chat("Erreur", f"Attaquant introuvable: {attacker_name}", color=_RED)
            return

        target_names = sorted(name for name in self._entities.keys() if name != attacker_name)
        if not target_names:
            self._left.append_chat("Combat", "Aucune cible disponible pour cette action.", color=_YELLOW)
            return

        dialog = CombatAttackDialog(
            action,
            attacker_name,
            target_names,
            preferred_target=preferred_target,
            initial_user_dice=int(forced_user_dice if forced_user_dice is not None else 50),
            parent=self,
        )
        resolved = dialog.exec()
        if not resolved:
            return

        target_name = str(resolved.get("target", ""))
        target = self._entities.get(target_name)
        if target is None:
            self._left.append_chat("Erreur", f"Cible introuvable: {target_name}", color=_RED)
            return

        user_dice = Dice("1d100", [int(resolved.get("user_dice", 50))])
        target_dice = Dice("1d100", [int(resolved.get("target_dice", 50))])

        if action == "strike":
            matchup = "user(str) vs target(con)"
            damage_dice = attacker.strike(target, user_dice, target_dice)
            action_label = "strike"
        else:
            matchup = "user(dex) vs target(agi)"
            damage_dice = attacker.shoot(target, user_dice, target_dice)
            action_label = "shoot"

        self._left.append_chat(
            "Combat",
            (
                f"{attacker_name} -> {target_name} [{action_label}] {matchup} | "
                f"d100 attacker:{user_dice.dices_values[0]} cible:{target_dice.dices_values[0]} | "
                f"commande dégâts:{damage_dice}"
            ),
            color=_YELLOW,
        )

        if not damage_dice or damage_dice.startswith("0d"):
            self._left.append_chat("Combat", "Aucun dégât à appliquer.", color=_YELLOW)
            return

        request_id = uuid4().hex
        request_payload = {
            "request_id": request_id,
            "action": action_label,
            "attacker": attacker_name,
            "target": target_name,
            "damage_dice": damage_dice,
            "matchup": matchup,
        }

        sent_to_client = False
        if self._server_worker and self._server_worker.isRunning():
            sent_to_client = self._server_worker.send_command_to_entity(
                attacker_name,
                "DAMAGE_ROLL_REQUEST",
                request_payload,
            )

        if sent_to_client:
            self._pending_damage_rolls[request_id] = {
                "action": action_label,
                "attacker": attacker_name,
                "target": target_name,
                "damage_dice": damage_dice,
            }
            self._left.append_chat(
                "Combat",
                f"Demande de jet de dégâts envoyée à {attacker_name} ({damage_dice}).",
                color=_GREEN,
            )
            return

        # Fallback: si aucun client lié, le MJ applique localement comme avant.
        dmg = Dice.roll(damage_dice)
        damage_total = sum(dmg.dices_values)
        damage_roll = "+".join(str(v) for v in dmg.dices_values)
        target.character.stats_modifier.hp -= damage_total
        self._left.append_chat(
            "Combat",
            f"Aucun client lié à {attacker_name}. Dégâts MJ: {damage_roll} = {damage_total}",
            color=_YELLOW,
        )

        self._central.refresh_all()
        self._sync_entities_to_players()

    def _on_sync_assets_requested(self) -> None:
        """Force une synchro d'etat et notifie les joueurs qu'un refresh assets est demande."""
        self._sync_entities_to_players()
        if self._server_worker and self._server_worker.isRunning():
            self._server_worker.broadcast_assets_files(["characters", "items", "spells"])
            self._left.append_chat(
                "Système",
                "Synchronisation des fichiers assets envoyée aux joueurs.",
                color=_GREEN,
            )
        else:
            self._left.append_chat(
                "Système",
                "Serveur arrêté : synchro locale effectuée uniquement.",
                color=_YELLOW,
            )

    def _on_combat_updated(self, message: str) -> None:
        """Réagit aux actions de combat MJ: refresh UI + sync vers joueurs."""
        if message:
            self._left.append_chat("Combat", message, color=_YELLOW)

        combat_state = self._central.current_combat_state()
        if self._server_worker and self._server_worker.isRunning():
            self._server_worker.broadcast_command("COMBAT_TURN_ORDER", combat_state)

        self._sync_entities_to_players()

    def _on_spell_resolved(self, request: dict) -> None:
        """Appliquer le sort quand le MJ confirme la résolution."""
        spell_key = request.get("spell_key", "Unknown")
        user_name = request.get("user", "Unknown")
        target_names: list[str] = request.get("targets", [])
        user_dices: dict[str, int] = request.get("user_dices", {})
        targets_dices: dict[str, dict[str, int]] = request.get("targets_dices", {})

        caster_entity = self._entities.get(user_name)
        if not caster_entity:
            self._left.append_chat("Erreur", f"Lanceur introuvable : {user_name}", color=_RED)
            return

        targets: list[Entity] = []
        for name in target_names:
            entity = self._entities.get(name)
            if entity:
                targets.append(entity)
            else:
                self._left.append_chat("Erreur", f"Cible introuvable : {name}", color=_RED)

        if not targets:
            return

        try:
            success = caster_entity.cast_spell(
                spell_name=spell_key,
                targets=targets,
                user_dices=user_dices or None,
                targets_dices=targets_dices or None,
            )
            targets_str = ", ".join(target_names)
            if success:
                self._left.append_chat(
                    "Résultat",
                    f"✓ {user_name} lance {spell_key} sur {targets_str}",
                    color=_GREEN
                )
            else:
                self._left.append_chat(
                    "Erreur",
                    f"Le sort {spell_key} n'a pas pu être appliqué (non trouvé dans la liste du lanceur ?)",
                    color=_RED
                )
            self._sync_entities_to_players()
            self._central.refresh_all()
        except Exception as e:
            self._left.append_chat("Erreur", f"Erreur lors de l'application du sort : {e}", color=_RED)

    def _sync_entities_to_players(self) -> None:
        """Procedure de sync periodique MJ -> joueurs."""
        if not self._server_worker or not self._server_worker.isRunning():
            return
        for entity_name, entity in self._entities.items():
            state = serialize_entity_state(entity)
            self._server_worker.push_entity_state(entity_name, state)

    # ── Entities ──────────────────────────────────────────────────────────────

    def _on_add_entity(self, char_name: str) -> None:
        char = Character.from_name(char_name)
        if char is None:
            QMessageBox.warning(self, "Introuvable", f"Personnage « {char_name} » introuvable.")
            return

        # Nom unique si déjà présent
        entity_name = char_name
        n = 2
        while entity_name in self._entities:
            entity_name = f"{char_name} ({n})"
            n += 1

        entity = Entity(name=entity_name, character=char)
        self._entities[entity_name] = entity
        self._central.add_card(entity)

    def closeEvent(self, event) -> None:
        if self._server_worker and self._server_worker.isRunning():
            self._server_worker.stop_server()
            self._server_worker.wait(3000)
        super().closeEvent(event)


# ── Entrée ────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    win = MJWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
