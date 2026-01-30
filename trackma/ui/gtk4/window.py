"""
Trackma GTK4 Main Window.

Primary application window using libadwaita. Uses AdwNavigationView to flow
from account selection to the show list. Communicates exclusively through
Engine methods.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from trackma.ui.gtk4.accounts import AccountPage

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
        self._try_default_account()

    def _build_ui(self) -> None:
        """Construct the window UI."""
        self._toast_overlay = Adw.ToastOverlay()

        self._nav_view = Adw.NavigationView()
        self._toast_overlay.set_child(self._nav_view)

        # Account page
        self._account_page = AccountPage(self._app.account_manager)
        self._account_page.connect("account-open", self._on_account_open)
        self._nav_view.add(self._account_page)

        self.set_content(self._toast_overlay)

    def _try_default_account(self) -> None:
        """If a default account exists, start the engine immediately."""
        default = self._app.account_manager.get_default()
        if default is not None:
            # Find the account number for the default
            for num, account in self._app.account_manager.get_accounts():
                if account is default:
                    self._start_engine(num)
                    return

    def _on_account_open(self, _page: AccountPage, account_num: int) -> None:
        self._app.account_manager.set_default(account_num)
        self._start_engine(account_num)

    def _start_engine(self, account_num: int) -> None:
        """Start the engine in a background thread, showing a loading page."""
        account = self._app.account_manager.get_account(account_num)

        # Show loading page
        loading_page = Adw.NavigationPage(title="Loading")
        loading_toolbar = Adw.ToolbarView()
        loading_toolbar.add_top_bar(Adw.HeaderBar())
        loading_status = Adw.StatusPage(
            title="Loading",
            description=f"Connecting as {account['username']}...",
        )
        spinner = Gtk.Spinner(spinning=True, width_request=32, height_request=32)
        loading_status.set_child(spinner)
        loading_toolbar.set_content(loading_status)
        loading_page.set_child(loading_toolbar)
        self._nav_view.push(loading_page)

        def worker() -> None:
            try:
                from trackma.engine import Engine

                engine = Engine(account=account)
                engine.start()
                GLib.idle_add(self._on_engine_ready, engine)
            except Exception as e:
                GLib.idle_add(self._on_engine_error, str(e))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_engine_ready(self, engine: Engine) -> bool:
        self._engine = engine
        self._app._engine = engine

        # Replace loading page with placeholder list page
        list_page = Adw.NavigationPage(title="Library")
        list_toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=self._build_menu(),
        )
        header.pack_end(menu_button)

        accounts_button = Gtk.Button(
            icon_name="system-users-symbolic",
            tooltip_text="Switch Account",
        )
        accounts_button.connect("clicked", self._on_switch_account)
        header.pack_start(accounts_button)

        list_toolbar.add_top_bar(header)

        api_info = engine.api_info
        status_page = Adw.StatusPage(
            icon_name="emblem-ok-symbolic",
            title=api_info["name"],
            description=f"Logged in as {engine.get_userconfig('username')}\n"
            "List view coming soon",
        )
        list_toolbar.set_content(status_page)
        list_page.set_child(list_toolbar)

        self._nav_view.replace([list_page])
        return GLib.SOURCE_REMOVE

    def _on_engine_error(self, message: str) -> bool:
        self._nav_view.pop()
        self.show_toast(f"Engine error: {message}", timeout=5)
        return GLib.SOURCE_REMOVE

    def _on_switch_account(self, _button: Gtk.Button) -> None:
        if self._engine is not None:
            try:
                self._engine.unload()
            except Exception:
                logger.exception("Error unloading engine")
            self._engine = None
            self._app._engine = None

        self._account_page.refresh_accounts()
        self._nav_view.replace([self._account_page])

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
