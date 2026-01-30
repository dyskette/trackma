"""
Trackma GTK4 Main Window.

Primary application window using libadwaita. Serves as the main container
for all UI components. Communicates exclusively through Engine methods.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

if TYPE_CHECKING:
    from trackma.engine import Engine
    from trackma.ui.gtk4.application import TrackmaApplication

logger = logging.getLogger(__name__)


class MainWindow(Adw.ApplicationWindow):
    """Main application window."""

    def __init__(self, application: TrackmaApplication, **kwargs: Any) -> None:
        super().__init__(application=application, **kwargs)

        self._app = application
        self._engine: Engine | None = None

        self.set_default_size(800, 600)
        self.set_title("Trackma")

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the window UI."""
        toolbar_view = Adw.ToolbarView()

        # Header bar
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._build_menu())
        header.pack_end(menu_button)

        # Content: status page as placeholder
        status_page = Adw.StatusPage()
        status_page.set_title("Trackma")
        status_page.set_description("Select an account to get started")
        status_page.set_icon_name("org.trackma.Trackma")
        toolbar_view.set_content(status_page)

        # Toast overlay wrapping everything
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(toolbar_view)
        self.set_content(self._toast_overlay)

    def _build_menu(self) -> Gio.Menu:
        """Build the primary menu."""
        menu = Gio.Menu()
        menu.append("About Trackma", "app.about")
        return menu

    def show_toast(self, message: str, *, timeout: int = 3) -> None:
        """Display a toast notification."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self._toast_overlay.add_toast(toast)
