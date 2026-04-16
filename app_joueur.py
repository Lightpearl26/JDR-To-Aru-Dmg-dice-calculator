# -*- coding: utf-8 -*-
"""
App Joueur — Client
===================
Lance avec :
    python v2/app_joueur.py

Affiche une boîte de connexion, puis la fiche du personnage + panneau de chat.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from random import randint
from pathlib import Path

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
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from libs.character import Character, Entity
from libs.client.client import Client
from libs.gui.entity_sheet import EntitySheet
from libs.net.state_sync import apply_entity_state


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
_SETTINGS_FILE = Path("cache/player_settings_v2.json")


def _list_character_names() -> list[str]:
    folder = Path("assets/characters")
    if not folder.exists():
        return []
    return sorted(p.stem for p in folder.glob("*.json"))


def _load_player_settings() -> dict[str, object]:
    defaults: dict[str, object] = {
        "host": "127.0.0.1",
        "port": 7799,
        "username": "",
        "char_name": "",
    }
    try:
        if not _SETTINGS_FILE.exists():
            return defaults
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return defaults
        defaults.update({
            "host": str(data.get("host", defaults["host"])),
            "port": int(data.get("port", defaults["port"])),
            "username": str(data.get("username", defaults["username"])),
            "char_name": str(data.get("char_name", defaults["char_name"])),
        })
        return defaults
    except (OSError, ValueError, TypeError):
        return defaults


def _save_player_settings(settings: dict[str, object]) -> None:
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        # Non bloquant: l'app continue même si on ne peut pas écrire les préférences.
        pass


# ── Thread client ─────────────────────────────────────────────────────────────

class _ClientWorker(QThread):
    """Exécute le client asyncio dans un thread dédié."""

    connected      = pyqtSignal()
    disconnected   = pyqtSignal(str)   # raison
    auth_ok        = pyqtSignal()
    auth_failed    = pyqtSignal(str)   # raison
    chat_received  = pyqtSignal(str, str)  # sender, message
    state_synced   = pyqtSignal(dict)  # payload
    assets_sync_requested = pyqtSignal(dict)  # payload
    combat_order_synced = pyqtSignal(dict)  # payload
    player_event = pyqtSignal(dict)  # {event: joined|left, username: str}
    damage_roll_requested = pyqtSignal(dict)  # payload DAMAGE_ROLL_REQUEST
    error_occurred = pyqtSignal(str)

    def __init__(self, host: str, port: int, username: str, password: str, entity_name: str) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._entity_name = entity_name
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Client | None = None
        self._stop_event: asyncio.Event | None = None

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
        self._client = Client(
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            character_name=self._entity_name,
            tls_insecure=True,
        )
        try:
            await self._client.setup()
            self.connected.emit()
        except ConnectionRefusedError:
            self.error_occurred.emit("Connexion refusée. Le serveur est-il démarré ?")
            return
        except OSError as exc:
            self.error_occurred.emit(f"Erreur réseau : {exc}")
            return

        # Attente auth (max 5 s)
        for _ in range(50):
            await asyncio.sleep(0.1)
            if self._client.session and self._client.session.is_authenticated:
                break
        else:
            reason = self._client.last_error or "Délai d'authentification dépassé"
            self.auth_failed.emit(reason)
            await self._client.shutdown()
            return

        self.auth_ok.emit()

        # Boucle de polling
        seen_chat = 0
        seen_sync = 0
        seen_assets_sync = 0
        seen_combat_sync = 0
        seen_player_events = 0
        seen_damage_roll_requests = 0
        while not self._stop_event.is_set():
            if not self._client.session or not self._client.session.is_active:
                self.disconnected.emit("Connexion perdue")
                return

            # Nouveaux messages chat
            while len(self._client.chat_log) > seen_chat:
                msg = self._client.chat_log[seen_chat]
                if hasattr(msg, "sender") and hasattr(msg, "message"):
                    self.chat_received.emit(msg.sender, msg.message)
                seen_chat += 1

            # Nouveaux snapshots d'etat
            while len(self._client.state_updates) > seen_sync:
                payload = self._client.state_updates[seen_sync]
                if isinstance(payload, dict):
                    self.state_synced.emit(payload)
                seen_sync += 1

            # Notification de synchro assets demandee par le MJ
            while len(self._client.asset_sync_events) > seen_assets_sync:
                payload = self._client.asset_sync_events[seen_assets_sync]
                if isinstance(payload, dict):
                    self.assets_sync_requested.emit(payload)
                seen_assets_sync += 1

            # Mises a jour d'ordre de tour du combat
            while len(self._client.combat_updates) > seen_combat_sync:
                payload = self._client.combat_updates[seen_combat_sync]
                if isinstance(payload, dict):
                    self.combat_order_synced.emit(payload)
                seen_combat_sync += 1

            # Evenements joueurs (connexion/deconnexion)
            while len(self._client.player_events) > seen_player_events:
                payload = self._client.player_events[seen_player_events]
                if isinstance(payload, dict):
                    self.player_event.emit(payload)
                seen_player_events += 1

            # Demandes de jet de degats envoyees par le serveur
            while len(self._client.damage_roll_requests) > seen_damage_roll_requests:
                payload = self._client.damage_roll_requests[seen_damage_roll_requests]
                if isinstance(payload, dict):
                    self.damage_roll_requested.emit(payload)
                seen_damage_roll_requests += 1

            await asyncio.sleep(0.2)

        await self._client.shutdown()
        self.disconnected.emit("Déconnexion propre")

    # ── Public API (thread-safe) ──────────────────────────────────────────────

    def send_chat(self, text: str) -> None:
        if self._loop and self._client:
            asyncio.run_coroutine_threadsafe(self._client.send_chat(text), self._loop)

    def send_spell_request(
            self,
            spell_key: str,
            targets: list[str] | None = None,
            user_dices: dict[str, int] | None = None,
        ) -> None:
        if self._loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.send_spell_request(spell_key, targets, user_dices),
                self._loop
            )

    def send_attack_request(
            self,
            action: str,
            target: str,
            user_dices: dict[str, int] | None = None,
        ) -> None:
        if self._loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.send_attack_request(action, target, user_dices),
                self._loop,
            )

    def send_damage_roll_result(
            self,
            request_id: str,
            damage_dice: str,
            rolls: list[int],
            total: int,
        ) -> None:
        if self._loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.send_damage_roll_result(request_id, damage_dice, rolls, total),
                self._loop,
            )

    def stop(self) -> None:
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)


# ── Dialogue de connexion ─────────────────────────────────────────────────────

class LoginDialog(QDialog):
    def __init__(
        self,
        settings: dict[str, object],
        character_names: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connexion au serveur")
        self.setModal(True)
        self.setFixedSize(360, 300)
        self.setStyleSheet(f"""
            QDialog {{ background:{_PANEL_BG}; }}
            QLabel {{ color:{_TEXT_PRIMARY}; background:transparent; }}
            QLineEdit, QSpinBox {{
                background:#182030; color:{_TEXT_PRIMARY};
                border:1px solid {_PANEL_BORDER}; border-radius:4px;
                padding:5px 8px; font-size:12px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        title = QLabel("JDR-To-Aru — Joueur")
        f = QFont(); f.setBold(True); f.setPointSize(13)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._host = QLineEdit(str(settings.get("host", "127.0.0.1")))
        self._port = QSpinBox()
        self._port.setRange(1024, 65535)
        self._port.setValue(int(settings.get("port", 7799)))
        self._username = QLineEdit(str(settings.get("username", "")))
        self._username.setPlaceholderText("Votre pseudo")
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Mot de passe de la salle")
        self._char_name = QComboBox()
        self._char_name.setEditable(True)
        self._char_name.addItems(character_names)
        self._char_name.setCurrentText(str(settings.get("char_name", "")))
        self._char_name.setStyleSheet(f"""
            QComboBox {{
                background:#182030; color:{_TEXT_PRIMARY};
                border:1px solid {_PANEL_BORDER}; border-radius:4px;
                padding:5px 8px; font-size:12px;
            }}
            QComboBox::drop-down {{ border:none; }}
            QComboBox QAbstractItemView {{
                background:#182030; color:{_TEXT_PRIMARY};
                selection-background-color:{_ACCENT};
            }}
        """)

        lbl_style = f"color:{_TEXT_SEC}; font-size:11px;"
        for lbl_text, widget in [
            ("Serveur :", self._host),
            ("Port :", self._port),
            ("Pseudo :", self._username),
            ("Mot de passe :", self._password),
            ("Personnage :", self._char_name),
        ]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(lbl_style)
            form.addRow(lbl, widget)

        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Se connecter")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        btns.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(f"""
            QPushButton {{
                background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                border-radius:4px; font-weight:bold; padding:5px 14px;
            }}
            QPushButton:hover {{ background:#3a4a3a; }}
        """)
        btns.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(f"""
            QPushButton {{
                background:{_PANEL_BG}; color:{_TEXT_SEC}; border:1px solid {_PANEL_BORDER};
                border-radius:4px; padding:5px 14px;
            }}
            QPushButton:hover {{ background:#2a2a3a; }}
        """)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── Accesseurs ────────────────────────────────────────────────────────────

    @property
    def host(self) -> str:
        return self._host.text().strip()

    @property
    def port(self) -> int:
        return self._port.value()

    @property
    def username(self) -> str:
        return self._username.text().strip()

    @property
    def password(self) -> str:
        return self._password.text()

    @property
    def char_name(self) -> str:
        return self._char_name.currentText().strip()

    def accept(self) -> None:
        if not self.username:
            QMessageBox.warning(self, "Champ manquant", "Le pseudo est obligatoire.")
            return
        if not self.char_name:
            QMessageBox.warning(self, "Champ manquant", "Le nom du personnage est obligatoire.")
            return
        super().accept()


class ReconnectDialog(QDialog):
    """Boite de dialogue légère pour modifier les paramètres de reconnexion."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paramètres de reconnexion")
        self.setModal(True)
        self.setFixedSize(360, 240)
        self.setStyleSheet(f"""
            QDialog {{ background:{_PANEL_BG}; }}
            QLabel {{ color:{_TEXT_PRIMARY}; background:transparent; }}
            QLineEdit, QSpinBox {{
                background:#182030; color:{_TEXT_PRIMARY};
                border:1px solid {_PANEL_BORDER}; border-radius:4px;
                padding:5px 8px; font-size:12px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        title = QLabel("Modifier la connexion")
        f = QFont(); f.setBold(True); f.setPointSize(13)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._host = QLineEdit(host)
        self._port = QSpinBox()
        self._port.setRange(1024, 65535)
        self._port.setValue(int(port))
        self._username = QLineEdit(username)
        self._username.setPlaceholderText("Votre pseudo")
        self._password = QLineEdit(password)
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Mot de passe de la salle")

        lbl_style = f"color:{_TEXT_SEC}; font-size:11px;"
        for lbl_text, widget in [
            ("Serveur :", self._host),
            ("Port :", self._port),
            ("Pseudo :", self._username),
            ("Mot de passe :", self._password),
        ]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(lbl_style)
            form.addRow(lbl, widget)

        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn is not None:
            ok_btn.setText("Reconnecter")
            ok_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                    border-radius:4px; font-weight:bold; padding:5px 14px;
                }}
                QPushButton:hover {{ background:#3a4a3a; }}
            """)
        if cancel_btn is not None:
            cancel_btn.setText("Annuler")
            cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{_PANEL_BG}; color:{_TEXT_SEC}; border:1px solid {_PANEL_BORDER};
                    border-radius:4px; padding:5px 14px;
                }}
                QPushButton:hover {{ background:#2a2a3a; }}
            """)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    @property
    def host(self) -> str:
        return self._host.text().strip()

    @property
    def port(self) -> int:
        return self._port.value()

    @property
    def username(self) -> str:
        return self._username.text().strip()

    @property
    def password(self) -> str:
        return self._password.text()

    def accept(self) -> None:
        if not self.host:
            QMessageBox.warning(self, "Champ manquant", "L'adresse du serveur est obligatoire.")
            return
        if not self.username:
            QMessageBox.warning(self, "Champ manquant", "Le pseudo est obligatoire.")
            return
        super().accept()


# ── Panel droit : chat ────────────────────────────────────────────────────────

class _ChatPanel(QFrame):
    send_requested = pyqtSignal(str)
    reconnect_requested = pyqtSignal()
    disconnect_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(230)
        self.setStyleSheet(f"""
            QFrame {{
                background:{_PANEL_BG};
                border-left:1px solid {_PANEL_BORDER};
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_status_section())
        root.addWidget(self._hline())
        root.addWidget(self._make_players_section())
        root.addWidget(self._hline())
        root.addWidget(self._make_chat_section(), 1)

    def _make_status_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{_PANEL_BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(4)

        title = QLabel("Connexion")
        f = QFont(); f.setBold(True); f.setPointSize(10)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

        self._conn_lbl = QLabel("○ Déconnecté")
        self._conn_lbl.setStyleSheet(f"color:{_RED}; font-size:10px; background:transparent;")
        lay.addWidget(self._conn_lbl)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._btn_reconnect = QPushButton("Reconnecter")
        self._btn_reconnect.setStyleSheet(f"""
            QPushButton {{
                background:#2a2a3a; color:{_YELLOW}; border:1px solid {_PANEL_BORDER};
                border-radius:4px; font-size:10px; padding:4px 6px;
            }}
            QPushButton:hover {{ background:#3a3a4a; }}
        """)
        self._btn_reconnect.clicked.connect(self.reconnect_requested.emit)
        row.addWidget(self._btn_reconnect)

        self._btn_disconnect = QPushButton("Déconnecter")
        self._btn_disconnect.setEnabled(False)
        self._btn_disconnect.setStyleSheet(f"""
            QPushButton {{
                background:#3a1e1e; color:{_RED}; border:1px solid #c04040;
                border-radius:4px; font-size:10px; padding:4px 6px;
            }}
            QPushButton:hover {{ background:#4a2e2e; }}
            QPushButton:disabled {{ background:{_PANEL_BG}; color:{_TEXT_MUTED}; border:1px solid {_TEXT_MUTED}; }}
        """)
        self._btn_disconnect.clicked.connect(self.disconnect_requested.emit)
        row.addWidget(self._btn_disconnect)

        lay.addLayout(row)

        return w

    def _make_players_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{_PANEL_BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        title = QLabel("Joueurs en ligne")
        f = QFont(); f.setBold(True); f.setPointSize(9)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

        self._players_list = QListWidget()
        self._players_list.setFixedHeight(70)
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
        w.setStyleSheet(f"background:{_PANEL_BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(6)

        title = QLabel("Chat")
        f = QFont(); f.setBold(True); f.setPointSize(10)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        lay.addWidget(title)

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

        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Message…")
        self._chat_input.setEnabled(False)
        self._chat_input.setStyleSheet(f"""
            QLineEdit {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; padding:4px 6px; font-size:10px;
            }}
            QLineEdit:disabled {{ color:{_TEXT_MUTED}; }}
        """)
        self._chat_input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._chat_input)

        self._send_btn = QPushButton("→")
        self._send_btn.setFixedWidth(28)
        self._send_btn.setEnabled(False)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background:{_ACCENT}; color:white; border:none;
                border-radius:3px; font-weight:bold; font-size:13px;
            }}
            QPushButton:hover {{ background:#9070d0; }}
            QPushButton:disabled {{ background:{_TEXT_MUTED}; }}
        """)
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)
        lay.addLayout(input_row)

        return w

    def _on_send(self) -> None:
        text = self._chat_input.text().strip()
        if text:
            self._chat_input.clear()
            self.send_requested.emit(text)

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{_PANEL_BORDER};")
        return line

    def append_chat(self, sender: str, message: str, color: str = _TEXT_PRIMARY) -> None:
        lbl = QLabel(
            f"<b style='color:{_YELLOW};'>{sender}</b> "
            f"<span style='color:{color};'>{message}</span>"
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background:transparent; font-size:10px;")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, lbl)
        QTimer.singleShot(50, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    def set_connected(self, connected: bool, label: str = "") -> None:
        if connected:
            self._conn_lbl.setText(f"● {label}")
            self._conn_lbl.setStyleSheet(f"color:{_GREEN}; font-size:10px; background:transparent;")
            self._chat_input.setEnabled(True)
            self._send_btn.setEnabled(True)
            self._btn_disconnect.setEnabled(True)
        else:
            self._conn_lbl.setText("○ Déconnecté")
            self._conn_lbl.setStyleSheet(f"color:{_RED}; font-size:10px; background:transparent;")
            self._chat_input.setEnabled(False)
            self._send_btn.setEnabled(False)
            self._btn_disconnect.setEnabled(False)
            self._players_list.clear()

    def add_player(self, username: str) -> None:
        # Évite les doublons
        for i in range(self._players_list.count()):
            if self._players_list.item(i).text().endswith(username):
                return
        self._players_list.addItem(f"● {username}")

    def remove_player(self, username: str) -> None:
        for i in range(self._players_list.count()):
            if self._players_list.item(i).text().endswith(username):
                self._players_list.takeItem(i)
                break


# ── Fenêtre de lancement de sort ──────────────────────────────────────────────

class SpellCastDialog(QDialog):
    """Popup pour lancer un sort avec ses dés."""
    
    spell_cast = pyqtSignal(str, list, dict)  # spell_key, targets, user_dices
    
    def __init__(
            self,
            spell_key: str,
            spell: object,
            available_targets: list[str],
            parent: QWidget | None = None,
        ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Lancer : {spell_key}")
        self.setStyleSheet(f"QDialog {{ background:{_APP_BG}; }}")
        self.setMinimumWidth(400)
        self.spell_key = spell_key
        self.spell = spell
        self.available_targets = [t for t in available_targets if t]
        self._is_multi = bool(getattr(self.spell, "targeting", "single") == "multi")
        self.user_dices: dict[str, int] = {}
        self._dice_widgets: dict[str, tuple[QLabel, QPushButton]] = {}
        self._updating_checks = False
        self._build_ui()

    def _extract_dice_requirements(self) -> set[str]:
        """Extrait les statistiques qui nécessitent des dés."""
        required = set()
        if not hasattr(self.spell, "effects"):
            return required
        
        for effect in self.spell.effects:
            formula = effect.formula
            if not hasattr(formula, "placeholders"):
                continue
            
            for cls, args in formula.placeholders:
                # Extraire les stats depuis DiceRatio et DiceAttack
                if cls.__name__ == "DiceRatio" and len(args) >= 1:
                    arg = str(args[0])
                    if "." in arg:
                        who, stat = arg.split(".", 1)
                        if who == "user":
                            required.add(stat)
                elif cls.__name__ == "DiceAttack":
                    # DiceAttack utilise le premier argument (user.stat)
                    if len(args) >= 1:
                        arg = str(args[0])
                        if "." in arg:
                            who, stat = arg.split(".", 1)
                            if who == "user":
                                required.add(stat)
        
        return required

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)
        
        # Titre
        title = QLabel(f"Lancer {self.spell_key}")
        f = QFont(); f.setBold(True); f.setPointSize(12)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        root.addWidget(title)

        target_mode = "multi" if self._is_multi else "single"
        target_lbl = QLabel(f"Cibles ({target_mode})")
        target_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold; background:transparent;")
        root.addWidget(target_lbl)

        self._target_list = QListWidget()
        self._target_list.setFixedHeight(110)
        self._target_list.setStyleSheet(f"""
            QListWidget {{
                background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                border-radius:3px; font-size:10px;
            }}
            QListWidget::item:selected {{ background:{_ACCENT}; }}
        """)
        for name in self.available_targets:
            item = QListWidgetItem(name)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._target_list.addItem(item)
        if not self._is_multi and self._target_list.count() > 0:
            self._target_list.item(0).setCheckState(Qt.CheckState.Checked)
        self._target_list.itemChanged.connect(self._on_target_item_changed)
        root.addWidget(self._target_list)
        
        # Dés détectés
        required_stats = self._extract_dice_requirements()
        if required_stats:
            dice_lbl = QLabel(f"Dés détectés : {', '.join(sorted(required_stats))}")
            dice_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
            root.addWidget(dice_lbl)
            
            # Zone de dés
            dice_box = QVBoxLayout()
            dice_box.setSpacing(6)
            for stat in sorted(required_stats):
                row = QHBoxLayout()
                row.setSpacing(8)
                
                stat_lbl = QLabel(f"{stat}:")
                stat_lbl.setFixedWidth(60)
                stat_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
                row.addWidget(stat_lbl)
                
                result_lbl = QLabel("—")
                result_lbl.setFixedWidth(40)
                result_lbl.setStyleSheet(f"color:{_YELLOW}; font-weight:bold; background:transparent;")
                
                roll_btn = QPushButton(f"d100")
                roll_btn.setFixedWidth(60)
                roll_btn.setStyleSheet(f"""
                    QPushButton {{
                        background:#285a28; color:{_GREEN}; border:1px solid #50a050;
                        border-radius:3px; font-size:10px; font-weight:bold;
                    }}
                    QPushButton:hover {{ background:#387a38; }}
                """)
                roll_btn.clicked.connect(lambda _, s=stat, l=result_lbl: self._roll_dice(s, l))
                row.addWidget(roll_btn)
                
                row.addStretch()
                row.addWidget(result_lbl)
                
                self._dice_widgets[stat] = (result_lbl, roll_btn)
                dice_box.addLayout(row)
            
            root.addLayout(dice_box)
        else:
            no_dice_lbl = QLabel("Aucun dé requis pour ce sort.")
            no_dice_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:11px; background:transparent;")
            root.addWidget(no_dice_lbl)
        
        root.addStretch()
        
        # Boutons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{_PANEL_BG}; color:{_TEXT_SEC}; border:1px solid {_PANEL_BORDER};
                border-radius:4px; padding:6px 14px;
            }}
            QPushButton:hover {{ background:#2a2a3a; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        
        btn_row.addStretch()
        
        cast_btn = QPushButton("Lancer le sort")
        cast_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                border-radius:4px; font-weight:bold; padding:6px 14px;
            }}
            QPushButton:hover {{ background:#3a4a3a; }}
        """)
        cast_btn.clicked.connect(self._on_cast)
        btn_row.addWidget(cast_btn)
        
        root.addLayout(btn_row)

    def _roll_dice(self, stat: str, result_lbl: QLabel) -> None:
        """Lance 1d100 pour une stat."""
        from libs.dice import Dice
        dice = Dice.roll("1d100")
        value = dice.dices_values[0] if dice.dices_values else 1
        self.user_dices[stat] = value
        result_lbl.setText(str(value))

    def _on_target_item_changed(self, changed_item: QListWidgetItem) -> None:
        if self._updating_checks:
            return
        if not self._is_multi and changed_item.checkState() == Qt.CheckState.Checked:
            self._updating_checks = True
            for i in range(self._target_list.count()):
                item = self._target_list.item(i)
                if item is not changed_item:
                    item.setCheckState(Qt.CheckState.Unchecked)
            self._updating_checks = False

    def _checked_targets(self) -> list[str]:
        return [
            self._target_list.item(i).text()
            for i in range(self._target_list.count())
            if self._target_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _on_cast(self) -> None:
        """Envoie la demande de sort."""
        targets = self._checked_targets()
        if not targets:
            QMessageBox.warning(self, "Lancer sort", "Choisis au moins une cible.")
            return
        self.spell_cast.emit(self.spell_key, targets, self.user_dices)
        self.accept()


class AttackRequestDialog(QDialog):
    """Popup joueur pour demander un strike/shoot avec son de d100."""

    request_ready = pyqtSignal(str, str, dict)  # action, target, user_dices

    def __init__(
            self,
            action: str,
            attacker_name: str,
            target_names: list[str],
            parent: QWidget | None = None,
        ) -> None:
        super().__init__(parent)
        self._action = str(action).strip().lower()
        self._attacker_name = attacker_name

        self.setWindowTitle(f"Demande {self._action}")
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet(f"QDialog {{ background:{_APP_BG}; }}")

        if self._action == "strike":
            self._user_stat = "str"
            matchup = "user(str) vs target(con)"
        else:
            self._user_stat = "dex"
            matchup = "user(dex) vs target(agi)"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        title = QLabel(f"{attacker_name} demande {self._action}")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        root.addWidget(title)

        matchup_lbl = QLabel(matchup)
        matchup_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
        root.addWidget(matchup_lbl)

        target_row = QHBoxLayout()
        target_row.setSpacing(8)
        target_row.addWidget(QLabel("Cible:"))
        self._target_combo = QComboBox()
        self._target_combo.addItems(target_names)
        self._target_combo.setStyleSheet(
            f"QComboBox {{ background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};"
            " border-radius:4px; padding:4px 8px; font-size:10px; }}"
        )
        target_row.addWidget(self._target_combo, 1)
        root.addLayout(target_row)

        dice_row = QHBoxLayout()
        dice_row.setSpacing(8)
        stat_lbl = QLabel(f"Dé {self._user_stat}:")
        stat_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        dice_row.addWidget(stat_lbl)

        self._dice_spin = QSpinBox()
        self._dice_spin.setRange(1, 100)
        self._dice_spin.setValue(50)
        self._dice_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dice_spin.setStyleSheet(
            f"QSpinBox {{ background:#182030; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};"
            " border-radius:3px; font-size:10px; padding:2px 4px; min-width:58px; }}"
        )
        dice_row.addWidget(self._dice_spin)

        roll_btn = QPushButton("d100")
        roll_btn.setStyleSheet(f"""
            QPushButton {{
                background:#285a28; color:{_GREEN}; border:1px solid #50a050;
                border-radius:3px; font-size:10px; font-weight:bold;
            }}
            QPushButton:hover {{ background:#387a38; }}
        """)
        roll_btn.clicked.connect(lambda: self._dice_spin.setValue(randint(1, 100)))
        dice_row.addWidget(roll_btn)
        dice_row.addStretch()
        root.addLayout(dice_row)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:{_PANEL_BG}; color:{_TEXT_SEC}; border:1px solid {_PANEL_BORDER};"
            " border-radius:4px; padding:6px 14px; }}"
        )
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()

        send_btn = QPushButton("Envoyer la demande")
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                border-radius:4px; font-weight:bold; padding:6px 14px;
            }}
            QPushButton:hover {{ background:#3a4a3a; }}
        """)
        send_btn.clicked.connect(self._on_send)
        btn_row.addWidget(send_btn)
        root.addLayout(btn_row)

    def _on_send(self) -> None:
        target = self._target_combo.currentText().strip()
        if not target:
            QMessageBox.warning(self, "Demande d'attaque", "Choisis une cible.")
            return
        user_dices = {self._user_stat: int(self._dice_spin.value())}
        self.request_ready.emit(self._action, target, user_dices)
        self.accept()


class DamageRollDialog(QDialog):
    """Popup joueur pour lancer les des de degats demandes par le MJ."""

    result_ready = pyqtSignal(str, str, list, int)  # request_id, damage_dice, rolls, total

    def __init__(self, payload: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._payload = payload
        self._rolls: list[int] = []
        self._total: int = 0

        self._request_id = str(payload.get("request_id", "")).strip()
        self._damage_dice = str(payload.get("damage_dice", "")).strip()
        self._action = str(payload.get("action", "")).strip()
        self._attacker = str(payload.get("attacker", "")).strip()
        self._target = str(payload.get("target", "")).strip()

        self.setWindowTitle("Jet de degats")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setStyleSheet(f"QDialog {{ background:{_APP_BG}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        title = QLabel("Resolution des degats")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        root.addWidget(title)

        info = QLabel(f"{self._attacker} -> {self._target} [{self._action}]")
        info.setStyleSheet(f"color:{_TEXT_SEC}; font-size:10px; background:transparent;")
        root.addWidget(info)

        dice_lbl = QLabel(f"Des a lancer: {self._damage_dice}")
        dice_lbl.setStyleSheet(f"color:{_YELLOW}; font-size:10px; background:transparent;")
        root.addWidget(dice_lbl)

        self._result_lbl = QLabel("Resultat: —")
        self._result_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; font-size:10px; background:transparent;")
        root.addWidget(self._result_lbl)

        btn_row = QHBoxLayout()
        self._roll_btn = QPushButton("Lancer degats")
        self._roll_btn.setStyleSheet(f"""
            QPushButton {{
                background:#2a3a2a; color:{_GREEN}; border:1px solid #50a050;
                border-radius:4px; font-weight:bold; padding:6px 12px;
            }}
            QPushButton:hover {{ background:#3a4a3a; }}
        """)
        self._roll_btn.clicked.connect(self._roll_damage)
        btn_row.addWidget(self._roll_btn)

        self._send_btn = QPushButton("Envoyer")
        self._send_btn.setEnabled(False)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background:{_ACCENT}; color:white; border:none;
                border-radius:4px; font-weight:bold; padding:6px 12px;
            }}
            QPushButton:hover {{ background:#9070d0; }}
            QPushButton:disabled {{ background:{_TEXT_MUTED}; }}
        """)
        self._send_btn.clicked.connect(self._send_result)
        btn_row.addWidget(self._send_btn)
        root.addLayout(btn_row)

    def _roll_damage(self) -> None:
        from libs.dice import Dice
        try:
            dice = Dice.roll(self._damage_dice)
            self._rolls = [int(v) for v in dice.dices_values]
            self._total = int(sum(self._rolls))
        except Exception:
            self._rolls = []
            self._total = 0
        rolls_str = "+".join(str(v) for v in self._rolls) if self._rolls else "—"
        self._result_lbl.setText(f"Resultat: {rolls_str} = {self._total}")
        self._send_btn.setEnabled(True)

    def _send_result(self) -> None:
        self.result_ready.emit(self._request_id, self._damage_dice, self._rolls, self._total)
        self.accept()


class _SlotMachineRoster(QWidget):
    """Affiche l'ordre des tours en machine a sous avec animation cyclique."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[str, str, str]] = []
        self._current_idx: int = -1
        self._anim_offset: float = 0.0
        self._anim_direction: int = 1
        self._item_height = 22
        self._visible_items = 3

        self.setMinimumHeight((self._item_height * self._visible_items) + 8)
        self.setMaximumHeight((self._item_height * self._visible_items) + 8)
        self.setStyleSheet(f"background:{_APP_BG};")

        self._anim = QPropertyAnimation(self, b"animOffset")
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def animOffset(self) -> float:
        return self._anim_offset

    @animOffset.setter
    def animOffset(self, value: float) -> None:
        self._anim_offset = value
        self.update()

    def set_roster(self, items: list[tuple[str, str, str]], current_idx: int) -> None:
        old_idx = self._current_idx
        self._items = items
        self._current_idx = max(-1, min(current_idx, len(items) - 1))

        if old_idx >= 0 and old_idx != self._current_idx and len(items) > 0:
            n = len(items)
            if n > 1:
                step_forward = (self._current_idx - old_idx) % n
                step_backward = (old_idx - self._current_idx) % n
                self._anim_direction = 1 if step_forward <= step_backward else -1
            else:
                self._anim_direction = 1

            self._anim.stop()
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim_offset = 1.0
            self._anim.start()
        else:
            self._anim_offset = 0.0
            self._anim_direction = 1

        self.update()

    def clear_roster(self) -> None:
        self._items = []
        self._current_idx = -1
        self._anim_offset = 0.0
        self._anim_direction = 1
        self._anim.stop()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QBrush(QColor(_PANEL_BG)))

        border = QColor(_PANEL_BORDER)
        p.setPen(QPen(border, 1))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)

        if not self._items or self._current_idx < 0:
            p.setPen(QColor(_TEXT_SEC))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Pas de combat actif")
            return

        center_y = (self.height() - self._item_height) // 2
        p.fillRect(0, center_y, self.width(), self._item_height, QBrush(QColor(_ACCENT + "22")))

        n = len(self._items)
        half_window = self._visible_items // 2
        anim_shift = self._item_height * self._anim_offset * self._anim_direction

        for slot in range(-half_window, half_window + 1):
            idx = (self._current_idx + slot) % n
            name, d20_str, status = self._items[idx]

            y = int(center_y + (slot * self._item_height) - anim_shift)

            is_current = slot == 0
            if is_current:
                text_color = _YELLOW
            elif abs(slot) == 1:
                text_color = _TEXT_PRIMARY
            else:
                text_color = _TEXT_SEC

            marker = "▶ " if is_current else "  "
            txt = f"{marker}{name} | {d20_str} | {status}"
            p.setPen(QColor(text_color))
            p.drawText(6, y, self.width() - 12, self._item_height, Qt.AlignmentFlag.AlignVCenter, txt)


class _CombatOrderPanel(QFrame):
    """Panneau compact affichant l'ordre de tour reçu du serveur."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMaximumHeight(120)
        self.setStyleSheet(f"""
            QFrame {{
                background:{_PANEL_BG};
                border:1px solid {_PANEL_BORDER};
                border-radius:6px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        title = QLabel("Tour en cours")
        f = QFont(); f.setBold(True); f.setPointSize(8)
        title.setFont(f)
        title.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        root.addWidget(title)

        self._state_lbl = QLabel("Hors combat")
        self._state_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:9px; background:transparent;")
        root.addWidget(self._state_lbl)

        self._roster = _SlotMachineRoster()
        root.addWidget(self._roster)

    def clear_state(self) -> None:
        self._state_lbl.setText("Hors combat")
        self._roster.clear_roster()

    def set_from_payload(self, payload: dict) -> None:
        active = bool(payload.get("active", False))
        order = payload.get("order", [])
        if not active or not isinstance(order, list) or not order:
            self.clear_state()
            return

        participants_raw = payload.get("participants", [])
        participants: dict[str, dict[str, object]] = {}
        if isinstance(participants_raw, list):
            for entry in participants_raw:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", "")).strip()
                if name:
                    participants[name] = entry

        current_idx = int(payload.get("current_turn_idx", -1))
        if not (0 <= current_idx < len(order)):
            current_name = str(payload.get("current_turn", ""))
            current_idx = order.index(current_name) if current_name in order else -1

        round_number = int(payload.get("round", 1))
        current_name = str(payload.get("current_turn", "") or "—")
        self._state_lbl.setText(f"Round {round_number} | Tour: {current_name}")

        items: list[tuple[str, str, str]] = []
        for raw_name in order:
            name = str(raw_name)
            info = participants.get(name, {})
            initiative = int(info.get("initiative", 1)) if isinstance(info, dict) else 1
            status = str(info.get("status", "OK")) if isinstance(info, dict) else "OK"
            items.append((name, f"d20:{initiative:02d}", status))

        self._roster.set_roster(items, current_idx)


# ── Fenêtre principale Joueur ─────────────────────────────────────────────────

class PlayerWindow(QMainWindow):
    def __init__(self, entity: Entity, username: str, host: str, port: int, password: str) -> None:
        super().__init__()
        self._entity = entity
        self._username = username
        self._host = host
        self._port = port
        self._password = password
        self._worker: _ClientWorker | None = None
        self._is_connected = False
        self._received_first_sync = False
        self._last_combat_chat_key: tuple[int, str] | None = None
        self._last_combat_payload: dict[str, object] = {}
        self._combat_targets: list[str] = []
        self._combat_spell_targets: list[str] = []

        self.setWindowTitle(f"JDR-To-Aru — {entity.name}")
        self.resize(1100, 720)
        self.setStyleSheet(f"QMainWindow {{ background:{_APP_BG}; }}")

        self._build_ui()

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #45475a; }")

        self._sheet = EntitySheet(
            self._entity,
            show_cast_buttons=True,
            gm_mode=False,
        )
        self._sheet.cast_requested.connect(self._on_cast_spell)
        splitter.addWidget(self._sheet)

        right_panel = QWidget()
        right_root = QVBoxLayout(right_panel)
        right_root.setContentsMargins(0, 0, 0, 0)
        right_root.setSpacing(6)

        self._chat_panel = _ChatPanel()
        self._chat_panel.send_requested.connect(self._on_send_chat)
        self._chat_panel.reconnect_requested.connect(self._on_reconnect_requested)
        self._chat_panel.disconnect_requested.connect(self._on_disconnect_requested)
        right_root.addWidget(self._chat_panel, 1)

        self._combat_panel = _CombatOrderPanel()
        right_root.addWidget(self._combat_panel, 0, Qt.AlignmentFlag.AlignBottom)

        attack_row = QHBoxLayout()
        attack_row.setSpacing(6)
        self._req_strike_btn = QPushButton("Req strike")
        self._req_shoot_btn = QPushButton("Req shoot")
        for btn in (self._req_strike_btn, self._req_shoot_btn):
            btn.setEnabled(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:#2a2a3a; color:{_TEXT_PRIMARY}; border:1px solid {_PANEL_BORDER};
                    border-radius:4px; font-size:9px; padding:4px 8px;
                }}
                QPushButton:hover {{ background:#3a3a4a; }}
                QPushButton:disabled {{ color:{_TEXT_MUTED}; background:{_PANEL_BG}; }}
            """)
            attack_row.addWidget(btn)
        self._req_strike_btn.clicked.connect(lambda: self._open_attack_request("strike"))
        self._req_shoot_btn.clicked.connect(lambda: self._open_attack_request("shoot"))
        right_root.addLayout(attack_row)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        self.setCentralWidget(splitter)

    def connect_to_server(self, host: str, port: int, password: str) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._worker = _ClientWorker(host, port, self._username, password, self._entity.name)
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.auth_ok.connect(self._on_auth_ok)
        self._worker.auth_failed.connect(self._on_auth_failed)
        self._worker.chat_received.connect(self._on_chat_received)
        self._worker.state_synced.connect(self._on_state_synced)
        self._worker.assets_sync_requested.connect(self._on_assets_sync_requested)
        self._worker.combat_order_synced.connect(self._on_combat_order_synced)
        self._worker.player_event.connect(self._on_player_event)
        self._worker.damage_roll_requested.connect(self._on_damage_roll_requested)
        self._worker.error_occurred.connect(self._on_network_error)
        self._worker.start()

    def _on_connected(self) -> None:
        self._chat_panel.append_chat("Système", "Connexion en cours…", color=_YELLOW)

    def _on_auth_ok(self) -> None:
        self._is_connected = True
        self._chat_panel.set_connected(True, self._username)
        self._chat_panel.add_player(self._username)
        self._chat_panel.append_chat("Système", "Authentifié avec succès.", color=_GREEN)

    def _on_auth_failed(self, reason: str) -> None:
        self._is_connected = False
        self._chat_panel.set_connected(False)
        self._chat_panel.append_chat("Système", f"Échec : {reason}", color=_RED)

    def _on_disconnected(self, reason: str) -> None:
        self._is_connected = False
        self._chat_panel.set_connected(False)
        self._combat_panel.clear_state()
        self._last_combat_chat_key = None
        self._last_combat_payload = {}
        self._combat_targets = []
        self._combat_spell_targets = []
        self._update_attack_buttons()
        self._chat_panel.append_chat("Système", f"Déconnecté : {reason}", color=_YELLOW)
        self._worker = None

    def _on_chat_received(self, sender: str, message: str) -> None:
        self._chat_panel.append_chat(sender, message)

    def _on_state_synced(self, payload: dict) -> None:
        entity_name = str(payload.get("entity_name", ""))
        if entity_name != self._entity.name:
            return
        state = payload.get("state", {})
        if not isinstance(state, dict):
            return

        apply_entity_state(self._entity, state)
        self._sheet.set_entity(self._entity)

        if not self._received_first_sync:
            self._received_first_sync = True
            self._chat_panel.append_chat("Système", "Fiche synchronisée avec le MJ.", color=_GREEN)

    def _on_network_error(self, reason: str) -> None:
        self._is_connected = False
        self._chat_panel.set_connected(False)
        self._combat_panel.clear_state()
        self._last_combat_chat_key = None
        self._last_combat_payload = {}
        self._combat_targets = []
        self._combat_spell_targets = []
        self._update_attack_buttons()
        self._chat_panel.append_chat("Erreur", reason, color=_RED)
        self._worker = None

    def _on_assets_sync_requested(self, payload: dict) -> None:
        """Notification/suivi de synchro de fichiers assets demandée par le MJ."""
        event = str(payload.get("event", ""))
        if event == "begin":
            count = int(payload.get("count", 0))
            self._chat_panel.append_chat(
                "Système",
                f"Synchronisation des assets démarrée ({count} fichier(s)).",
                color=_YELLOW,
            )
            return
        if event == "done":
            count = int(payload.get("count", 0))
            self._chat_panel.append_chat(
                "Système",
                f"Synchronisation des assets terminée ({count} fichier(s) reçus).",
                color=_GREEN,
            )
            return

    def _on_combat_order_synced(self, payload: dict) -> None:
        """Met a jour le widget combat client depuis les infos du serveur."""
        if not isinstance(payload, dict):
            return

        self._last_combat_payload = payload
        self._combat_panel.set_from_payload(payload)
        self._combat_targets = [
            str(name) for name in payload.get("order", [])
            if str(name) and str(name) != self._entity.name
        ] if isinstance(payload.get("order", []), list) else []
        self._combat_spell_targets = [
            str(name) for name in payload.get("order", []) if str(name)
        ] if isinstance(payload.get("order", []), list) else []
        self._update_attack_buttons()

        active = bool(payload.get("active", False))
        if not active:
            self._last_combat_chat_key = None
            return

        order = payload.get("order", [])
        if not isinstance(order, list) or not order:
            return

        current = str(payload.get("current_turn", "") or "-")
        round_number = int(payload.get("round", 1))
        chat_key = (round_number, current)
        if self._last_combat_chat_key == chat_key:
            return
        self._last_combat_chat_key = chat_key
        self._chat_panel.append_chat(
            "Combat",
            f"Round {round_number} | Tour: {current} | Ordre: {' > '.join(str(x) for x in order)}",
            color=_YELLOW,
        )

    def _on_player_event(self, payload: dict) -> None:
        """Log des connexions/deconnexions de joueurs reçues du serveur."""
        if not isinstance(payload, dict):
            return
        event = str(payload.get("event", "")).strip()
        username = str(payload.get("username", "")).strip()
        if not username:
            return

        # Ignore les notifications sur soi-meme pour ne pas bruiter le chat.
        if username == self._username:
            return

        if event == "joined":
            self._chat_panel.add_player(username)
            self._chat_panel.append_chat(
                "Système",
                f"{username} vient de se connecter.",
                color=_GREEN,
            )
        elif event == "left":
            self._chat_panel.remove_player(username)
            self._chat_panel.append_chat(
                "Système",
                f"{username} vient de se déconnecter.",
                color=_YELLOW,
            )

    def _on_cast_spell(self, spell_key: str) -> None:
        """Handle spell cast request from EntitySheet."""
        if not self._is_connected:
            self._chat_panel.append_chat("Système", "Tu n'es pas connecté au serveur.", color=_YELLOW)
            return
        
        # Charger le sort
        from libs.spells.spell_def import Spell
        spell = Spell.from_name(spell_key)
        if spell is None:
            self._chat_panel.append_chat("Système", f"Sort introuvable : {spell_key}", color=_RED)
            return

        spell_targets = list(self._combat_spell_targets)
        if not spell_targets:
            spell_targets = [self._entity.name]
        
        # Ouvrir le popup de lancement
        dialog = SpellCastDialog(spell_key, spell, spell_targets, self)
        dialog.spell_cast.connect(self._on_spell_cast_confirmed)
        dialog.exec()

    def _on_spell_cast_confirmed(self, spell_key: str, targets: list[str], user_dices: dict) -> None:
        """Confirmation du lancement après le popup."""
        if self._worker and self._worker.isRunning():
            self._worker.send_spell_request(spell_key, targets, user_dices)
            dices_str = ", ".join(f"{k}:{v}" for k, v in sorted(user_dices.items())) if user_dices else "—"
            targets_str = ", ".join(str(t) for t in targets) if targets else "—"
            self._chat_panel.append_chat(
                "Système",
                f"📤 Demande lancée : {spell_key} -> [{targets_str}] (dés: {dices_str})",
                color=_YELLOW
            )

    def _update_attack_buttons(self) -> None:
        active = bool(self._last_combat_payload.get("active", False))
        current_turn = str(self._last_combat_payload.get("current_turn", ""))
        is_my_turn = active and current_turn == self._entity.name
        has_target = bool(self._combat_targets)
        can_request = bool(self._is_connected and is_my_turn and has_target)
        self._req_strike_btn.setEnabled(can_request)
        self._req_shoot_btn.setEnabled(can_request)

    def _open_attack_request(self, action: str) -> None:
        if not self._is_connected:
            self._chat_panel.append_chat("Système", "Tu n'es pas connecté au serveur.", color=_YELLOW)
            return
        if not self._combat_targets:
            self._chat_panel.append_chat("Système", "Aucune cible disponible.", color=_YELLOW)
            return

        dialog = AttackRequestDialog(action, self._entity.name, self._combat_targets, self)
        dialog.request_ready.connect(self._on_attack_request_confirmed)
        dialog.exec()

    def _on_attack_request_confirmed(self, action: str, target: str, user_dices: dict) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.send_attack_request(action, target, user_dices)
            dices_str = ", ".join(f"{k}:{v}" for k, v in sorted(user_dices.items())) if user_dices else "—"
            self._chat_panel.append_chat(
                "Système",
                f"📤 Demande {action} vers {target} (dés: {dices_str})",
                color=_YELLOW,
            )

    def _on_damage_roll_requested(self, payload: dict) -> None:
        """Affiche la popup de jet de degats demandee par le serveur."""
        if not isinstance(payload, dict):
            return
        request_id = str(payload.get("request_id", "")).strip()
        damage_dice = str(payload.get("damage_dice", "")).strip()
        if not request_id or not damage_dice:
            return

        dialog = DamageRollDialog(payload, self)
        dialog.result_ready.connect(self._on_damage_roll_confirmed)
        dialog.exec()

    def _on_damage_roll_confirmed(self, request_id: str, damage_dice: str, rolls: list, total: int) -> None:
        if self._worker and self._worker.isRunning():
            clean_rolls = [int(v) for v in rolls]
            self._worker.send_damage_roll_result(request_id, damage_dice, clean_rolls, int(total))
            rolls_str = "+".join(str(v) for v in clean_rolls) if clean_rolls else "—"
            self._chat_panel.append_chat(
                "Combat",
                f"📤 Dégâts envoyés ({damage_dice}): {rolls_str} = {int(total)}",
                color=_YELLOW,
            )

    def _on_send_chat(self, text: str) -> None:
        if not self._is_connected:
            self._chat_panel.append_chat("Système", "Tu n'es pas connecté au serveur.", color=_YELLOW)
            return
        self._chat_panel.append_chat(self._username, text, color=_PURPLE)
        if self._worker and self._worker.isRunning():
            self._worker.send_chat(text)

    def _on_disconnect_requested(self, silent: bool = False) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        self._worker = None
        self._is_connected = False
        self._chat_panel.set_connected(False)
        self._combat_panel.clear_state()
        self._last_combat_chat_key = None
        self._last_combat_payload = {}
        self._combat_targets = []
        self._combat_spell_targets = []
        self._update_attack_buttons()
        if not silent:
            self._chat_panel.append_chat("Système", "Déconnexion demandée.", color=_YELLOW)

    def _on_reconnect_requested(self) -> None:
        reconnect_dlg = ReconnectDialog(
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            parent=self,
        )
        if reconnect_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._host = reconnect_dlg.host
        self._port = reconnect_dlg.port
        self._username = reconnect_dlg.username
        self._password = reconnect_dlg.password

        _save_player_settings(
            {
                "host": self._host,
                "port": self._port,
                "username": self._username,
                "char_name": self._entity.character.name,
            }
        )

        self._on_disconnect_requested(silent=True)
        self._chat_panel.append_chat(
            "Système",
            f"Reconnexion de {self._username} vers {self._host}:{self._port}...",
            color=_YELLOW,
        )
        self.connect_to_server(self._host, self._port, self._password)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        super().closeEvent(event)


# ── Entrée ────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    settings = _load_player_settings()
    dlg = LoginDialog(settings=settings, character_names=_list_character_names())
    if dlg.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    _save_player_settings(
        {
            "host": dlg.host,
            "port": dlg.port,
            "username": dlg.username,
            "char_name": dlg.char_name,
        }
    )

    char = Character.from_name(dlg.char_name)
    if char is None:
        QMessageBox.critical(
            None,
            "Personnage introuvable",
            f"Le personnage « {dlg.char_name} » n'existe pas dans les assets.",
        )
        sys.exit(1)

    entity = Entity(name=dlg.char_name, character=char)

    win = PlayerWindow(
        entity,
        username=dlg.username,
        host=dlg.host,
        port=dlg.port,
        password=dlg.password,
    )
    win.show()
    win.connect_to_server(dlg.host, dlg.port, dlg.password)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
