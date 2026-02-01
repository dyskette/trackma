"""
Trackma GTK4 Main Window.

Primary application window using libadwaita. Uses an AdwNavigationView
to flow from account selection to the show list. All interaction with
the Trackma core happens exclusively through Engine methods.

The window lifecycle is:

1. On construction, the account page is shown.
2. If a default account exists, engine startup begins immediately.
3. On account selection, the engine is started in a background thread
   while a loading page is displayed.
4. Once the engine is ready, the navigation stack is replaced with
   the (placeholder) library page.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from trackma.ui.gtk4.accounts import AccountPage
from trackma.ui.gtk4.show_view import ShowListPage

if TYPE_CHECKING:
    from trackma.engine import Engine
    from trackma.ui.gtk4.application import TrackmaApplication

logger = logging.getLogger(__name__)


class MainWindow(Adw.ApplicationWindow):
    """Main application window.

    Hosts an ``AdwNavigationView`` whose root page is the account
    selector.  After the user picks an account the engine is created
    on a background thread and, once ready, the navigation stack is
    replaced with a placeholder library page.

    Args:
        application: The owning ``TrackmaApplication``.
        **kwargs: Forwarded to ``Adw.ApplicationWindow``.
    """

    def __init__(self, application: TrackmaApplication, **kwargs: Any) -> None:
        super().__init__(application=application, **kwargs)

        self._app = application
        self._engine: Engine | None = None

        self.set_default_size(800, 600)
        self.set_title("Trackma")

        self._build_ui()
        self._try_default_account()

    # -- UI construction -----------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the widget tree: toast overlay → navigation view."""
        self._toast_overlay = Adw.ToastOverlay()

        self._nav_view = Adw.NavigationView()
        self._toast_overlay.set_child(self._nav_view)

        self._account_page = AccountPage(self._app.account_manager)
        self._account_page.connect("account-open", self._on_account_open)
        self._nav_view.add(self._account_page)

        self.set_content(self._toast_overlay)

    # -- Account selection ---------------------------------------------------

    def _try_default_account(self) -> None:
        """Skip the account page when a default account is configured."""
        default = self._app.account_manager.get_default()
        if default is not None:
            for num, account in self._app.account_manager.get_accounts():
                if account is default:
                    self._start_engine(num)
                    return

    def _on_account_open(self, _page: AccountPage, account_num: int) -> None:
        """Handle the ``account-open`` signal from the account page."""
        self._app.account_manager.set_default(account_num)
        self._start_engine(account_num)

    # -- Engine lifecycle ----------------------------------------------------

    def _start_engine(self, account_num: int) -> None:
        """Start the engine on a background thread.

        Pushes a loading page with a spinner while the engine
        connects.  On success the navigation stack is replaced with
        the library page; on failure a toast is shown and the loading
        page is popped.

        Args:
            account_num: Account number passed to ``AccountManager.get_account``.
        """
        account = self._app.account_manager.get_account(account_num)

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

                engine = Engine(account=account, message_handler=self._core_message_handler)
                engine.start()
                GLib.idle_add(self._on_engine_ready, engine)
            except Exception as e:
                GLib.idle_add(self._on_engine_error, str(e))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_engine_ready(self, engine: Engine) -> bool:
        """Replace the loading page with the library page.

        Called on the main thread via ``GLib.idle_add``.

        Returns:
            ``GLib.SOURCE_REMOVE`` so the idle callback is not repeated.
        """
        self._engine = engine
        self._app._engine = engine

        list_page = ShowListPage(engine=engine)
        list_page.connect("switch-account", lambda _page: self._on_switch_account(None))
        self._nav_view.replace([list_page])
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _core_message_handler(classname: str, msg_type: int, message: str) -> None:
        """Forward Trackma core messages to Python logging."""
        from trackma.messenger import TYPE_DEBUG, TYPE_WARN

        if msg_type == TYPE_DEBUG:
            logger.debug("[%s] %s", classname, message)
        elif msg_type == TYPE_WARN:
            logger.warning("[%s] %s", classname, message)
        else:
            logger.info("[%s] %s", classname, message)

    def _on_engine_error(self, message: str) -> bool:
        """Pop the loading page and show an error toast.

        Called on the main thread via ``GLib.idle_add``.

        Returns:
            ``GLib.SOURCE_REMOVE`` so the idle callback is not repeated.
        """
        self._nav_view.pop()
        self.show_toast(f"Engine error: {message}", timeout=5)
        return GLib.SOURCE_REMOVE

    def _on_switch_account(self, _button: Gtk.Button | None = None) -> None:
        """Unload the current engine and return to the account page."""
        if self._engine is not None:
            try:
                self._engine.unload()
            except Exception:
                logger.exception("Error unloading engine")
            self._engine = None
            self._app._engine = None

        self._account_page.refresh_accounts()
        self._nav_view.replace([self._account_page])

    # -- Utilities -----------------------------------------------------------

    def show_toast(self, message: str, *, timeout: int = 3) -> None:
        """Display a transient toast notification.

        Args:
            message: Text shown in the toast.
            timeout: Seconds before the toast auto-dismisses.
        """
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self._toast_overlay.add_toast(toast)
