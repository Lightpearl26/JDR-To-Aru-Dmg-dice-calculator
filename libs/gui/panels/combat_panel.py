# -*- coding: utf-8 -*-

"""
Combat Panel - Turn-based combat management
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from pygame import Rect

from ..pygame_ui import Frame, UIWidget

if TYPE_CHECKING:
    from libs.session_manager import SessionManager
    from libs.resource_manager import ResourceManager


class CombatPanel(Frame):
    """
    Panel for managing turn-based combat.
    
    Workflow:
    1. Setup: Select enemies to add to combat
    2. Initiative: Roll and sort initiative order
    3. Combat: Turn-by-turn resolution
    4. End: Victory/defeat screen
    
    Features:
    - Enemy selection UI
    - Initiative roller
    - Turn order display
    - Combat actions (Strike, Shoot, Spell, Check)
    - HP tracking
    - Combat log
    """

    def __init__(
        self,
        parent: Optional[UIWidget], 
        rect: Rect,
    ) -> None:
        Frame.__init__(self, parent, rect)

        self._build_ui()

    @property
    def session_manager(self) -> SessionManager:
        """Convenience property to access the session manager from the app."""
        return self.app.session_manager

    @property
    def resource_manager(self) -> ResourceManager:
        """Convenience property to access the resource manager from the app."""
        return self.app.resource_manager

    def _build_ui(self) -> None:
        """Initialize UI"""
