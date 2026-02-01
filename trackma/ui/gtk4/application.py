"""
Trackma GTK4 Application.

Main application class using Adw.Application. Handles the application
lifecycle, global actions, and coordination between the engine and UI.

This is the entry point for the GTK4 frontend. It owns the
AccountManager and Engine instances, and creates the main window
on activation.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from trackma.accounts import AccountManager
from trackma.engine import Engine

if TYPE_CHECKING:
    from trackma.ui.gtk4.window import MainWindow

logger = logging.getLogger(__name__)


class TrackmaApplication(Adw.Application):
    """Main Trackma GTK4 application.

    Manages the application lifecycle following GNOME conventions:
    ``do_startup`` for one-time setup, ``do_activate`` to present
    the window, and ``do_shutdown`` for cleanup.

    Attributes:
        engine: The current Engine instance, or ``None`` if no
            account has been selected yet.
        account_manager: Shared AccountManager used by the window
            to list, add, edit, and delete accounts.
    """

    def __init__(self) -> None:
        super().__init__(
            application_id="org.trackma.Trackma",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        self._engine: Engine | None = None
        self._account_manager = AccountManager()
        self._window: MainWindow | None = None

    def do_startup(self) -> None:
        """Perform one-time initialization: actions, style, app name."""
        Adw.Application.do_startup(self)

        self._register_icons()
        self._setup_actions()

        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        GLib.set_application_name("Trackma")
        GLib.set_prgname("trackma")

    def do_activate(self) -> None:
        """Create the main window on first activation, then present it."""
        if self._window is None:
            from trackma.ui.gtk4.window import MainWindow

            self._window = MainWindow(application=self)
        self._window.present()

    def do_shutdown(self) -> None:
        """Unload the engine (if running) and shut down the application."""
        if self._engine is not None:
            self._engine.unload()
        Adw.Application.do_shutdown(self)

    def _register_icons(self) -> None:
        """Add bundled icons to the default icon theme search path."""
        icons_dir = Path(__file__).parent / "data" / "icons"
        if icons_dir.is_dir():
            icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            icon_theme.add_search_path(str(icons_dir))

    def _setup_actions(self) -> None:
        """Register application-level actions and keyboard accelerators."""
        actions: list[tuple[str, Any, list[str] | None]] = [
            ("quit", lambda *_: self.quit(), ["<Control>q"]),
            ("preferences", self._on_preferences, ["<Control>comma"]),
            ("about", self._on_about, None),
        ]

        for name, callback, accels in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

    def _on_preferences(self, _action: Gio.SimpleAction, _param: Any) -> None:
        """Present the Preferences dialog."""
        if self._engine is None:
            return
        from trackma.ui.gtk4.settings import SettingsDialog

        dialog = SettingsDialog(engine=self._engine)
        dialog.present(self._window)

    def _on_about(self, _action: Gio.SimpleAction, _param: Any) -> None:
        """Present the About dialog."""
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
        """The active Engine instance, or ``None``."""
        return self._engine

    @property
    def account_manager(self) -> AccountManager:
        """The shared AccountManager for this application."""
        return self._account_manager
