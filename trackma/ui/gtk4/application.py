"""
Trackma GTK4 Application.

Main application class using Adw.Application. Handles lifecycle,
actions, and coordination between the engine and UI.
"""

from __future__ import annotations

import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from trackma.accounts import AccountManager
from trackma.engine import Engine

logger = logging.getLogger(__name__)


class TrackmaApplication(Adw.Application):
    """Main Trackma GTK4 application."""

    def __init__(self) -> None:
        super().__init__(
            application_id="org.trackma.Trackma",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        self._engine: Engine | None = None
        self._account_manager = AccountManager()
        self._window: Any = None

    def do_startup(self) -> None:
        """One-time initialization."""
        Adw.Application.do_startup(self)

        self._setup_actions()

        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        GLib.set_application_name("Trackma")
        GLib.set_prgname("trackma")

    def do_activate(self) -> None:
        """Show the main window."""
        if self._window is None:
            from trackma.ui.gtk4.window import MainWindow

            self._window = MainWindow(application=self)
        self._window.present()

    def do_shutdown(self) -> None:
        """Cleanup on exit."""
        if self._engine is not None:
            self._engine.unload()
        Adw.Application.do_shutdown(self)

    def _setup_actions(self) -> None:
        """Register application-level actions."""
        actions: list[tuple[str, Any, list[str] | None]] = [
            ("quit", lambda *_: self.quit(), ["<Control>q"]),
            ("about", self._on_about, None),
        ]

        for name, callback, accels in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

    def _on_about(self, _action: Gio.SimpleAction, _param: None) -> None:
        """Show the about dialog."""
        about = Adw.AboutDialog(
            application_name="Trackma",
            application_icon="org.trackma.Trackma",
            version="0.11.0",
            developer_name="z411",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/z411/trackma",
        )
        about.present(self._window)

    @property
    def engine(self) -> Engine | None:
        return self._engine

    @property
    def account_manager(self) -> AccountManager:
        return self._account_manager
