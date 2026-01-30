"""
Trackma GTK4 Account Management Pages.

Provides navigation pages for selecting, adding, editing, and deleting
user accounts.  All pages are ``AdwNavigationPage`` subclasses designed
to be pushed onto the parent ``AdwNavigationView`` owned by the main
window.

Auth flow overview:

* **PASSWD** (Kitsu, VNDB) — username and password entered directly.
* **OAUTH** (AniList, Shikimori) — user clicks *Request PIN* to open
  the provider's authorization page in the browser, then pastes the
  resulting PIN back into the form.
* **OAUTH_PKCE** (MyAnimeList) — same as OAUTH but a PKCE
  ``code_verifier`` is generated and appended to the authorization URL.
  The verifier is stored in the account's ``extra`` dict for the
  subsequent token exchange performed by the engine.
"""

from __future__ import annotations

import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk

from trackma import utils
from trackma.accounts import AccountManager

logger = logging.getLogger(__name__)


class AccountPage(Adw.NavigationPage):
    """Account selection page shown at startup.

    Displays a boxed list of existing accounts.  Each row is
    activatable (emits ``account-open``) and carries edit/delete
    suffix buttons.  When no accounts exist, an ``AdwStatusPage``
    prompts the user to add one.

    Args:
        account_manager: The shared ``AccountManager`` instance.
        **kwargs: Forwarded to ``Adw.NavigationPage``.

    Signals:
        account-open(account_num: int): Emitted when the user
            activates an account row.
    """

    __gtype_name__ = "TrackmaAccountPage"
    __gsignals__ = {
        "account-open": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, account_manager: AccountManager, **kwargs: Any) -> None:
        super().__init__(title="Accounts", **kwargs)
        self._manager = account_manager
        self._build_ui()

    # -- UI construction -----------------------------------------------------

    def _build_ui(self) -> None:
        """Build the toolbar view, empty state, and account list."""
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        add_button = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add Account")
        add_button.connect("clicked", self._on_add_clicked)
        header.pack_start(add_button)

        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=self._build_menu(),
        )
        header.pack_end(menu_button)
        toolbar_view.add_top_bar(header)

        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Empty state
        empty_page = Adw.StatusPage(
            icon_name="system-users-symbolic",
            title="No Accounts",
            description="Add an account to get started",
        )
        self._content_stack.add_named(empty_page, "empty")

        # Account list
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(
            maximum_size=600,
            margin_top=24,
            margin_bottom=24,
            margin_start=12,
            margin_end=12,
        )

        self._list_group = Adw.PreferencesGroup(title="Select Account")
        self._listbox = Gtk.ListBox(
            css_classes=["boxed-list"],
            selection_mode=Gtk.SelectionMode.NONE,
        )
        self._listbox.connect("row-activated", self._on_row_activated)
        self._list_group.add(self._listbox)
        clamp.set_child(self._list_group)
        scroll.set_child(clamp)
        self._content_stack.add_named(scroll, "list")

        toolbar_view.set_content(self._content_stack)
        self.set_child(toolbar_view)

        self.refresh_accounts()

    def _build_menu(self) -> Gio.Menu:
        """Build the primary hamburger menu for the account page."""
        menu = Gio.Menu()
        menu.append("About Trackma", "app.about")
        return menu

    # -- Public interface ----------------------------------------------------

    def refresh_accounts(self) -> None:
        """Reload the account list from the ``AccountManager``.

        Switches between the empty-state and the list view depending
        on whether any accounts exist.
        """
        # Clear existing rows
        while True:
            row = self._listbox.get_row_at_index(0)
            if row is None:
                break
            self._listbox.remove(row)

        accounts = list(self._manager.get_accounts())
        if not accounts:
            self._content_stack.set_visible_child_name("empty")
            return

        self._content_stack.set_visible_child_name("list")
        for num, account in accounts:
            self._add_account_row(num, account)

    # -- Row construction ----------------------------------------------------

    def _add_account_row(self, num: int, account: dict[str, Any]) -> None:
        """Append a single account row to the list.

        Args:
            num: Account number used by ``AccountManager``.
            account: Account dict with at least ``username`` and ``api`` keys.
        """
        api_key = account["api"]
        lib_info = utils.available_libs.get(api_key)
        display_name = lib_info[0] if lib_info else api_key

        row = Adw.ActionRow(
            title=GLib.markup_escape_text(account["username"]),
            subtitle=display_name,
            activatable=True,
        )
        row._account_num = num  # type: ignore[attr-defined]

        edit_button = Gtk.Button(
            icon_name="document-edit-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
            tooltip_text="Edit",
        )
        edit_button._account_num = num  # type: ignore[attr-defined]
        edit_button.connect("clicked", self._on_edit_clicked)
        row.add_suffix(edit_button)

        delete_button = Gtk.Button(
            icon_name="user-trash-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
            tooltip_text="Remove",
        )
        delete_button._account_num = num  # type: ignore[attr-defined]
        delete_button._account_username = account["username"]  # type: ignore[attr-defined]
        delete_button.connect("clicked", self._on_delete_clicked)
        row.add_suffix(delete_button)

        row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        self._listbox.append(row)

    # -- Signal handlers -----------------------------------------------------

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Emit ``account-open`` with the activated row's account number."""
        account_num: int = row._account_num  # type: ignore[attr-defined]
        self.emit("account-open", account_num)

    def _on_add_clicked(self, _button: Gtk.Button) -> None:
        """Push the *Add Account* page onto the navigation view."""
        nav_view = self.get_parent()
        if not isinstance(nav_view, Adw.NavigationView):
            return
        add_page = AddAccountPage(self._manager)
        add_page.connect("account-added", self._on_account_added)
        nav_view.push(add_page)

    def _on_edit_clicked(self, button: Gtk.Button) -> None:
        """Push the *Edit Account* page for the clicked row."""
        account_num: int = button._account_num  # type: ignore[attr-defined]
        nav_view = self.get_parent()
        if not isinstance(nav_view, Adw.NavigationView):
            return
        edit_page = EditAccountPage(self._manager, account_num)
        edit_page.connect("account-edited", lambda _p: self.refresh_accounts())
        nav_view.push(edit_page)

    def _on_delete_clicked(self, button: Gtk.Button) -> None:
        """Show a confirmation dialog before deleting an account."""
        account_num: int = button._account_num  # type: ignore[attr-defined]
        username: str = button._account_username  # type: ignore[attr-defined]

        dialog = Adw.AlertDialog(
            heading="Remove Account?",
            body=f'Remove "{username}" from the account list?',
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response, account_num)
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Widget) else None
        dialog.present(parent)

    def _on_delete_response(
        self, _dialog: Adw.AlertDialog, response: str, account_num: int
    ) -> None:
        """Delete the account if the user confirmed removal."""
        if response == "remove":
            self._manager.delete_account(account_num)
            self.refresh_accounts()

    def _on_account_added(self, _page: AddAccountPage) -> None:
        """Refresh the list after a new account is added."""
        self.refresh_accounts()


class AddAccountPage(Adw.NavigationPage):
    """Page for adding a new account.

    Presents an API selector (``AdwComboRow``) and credential fields
    whose labels adapt to the selected service's authentication type.
    For OAuth services a *Request PIN* button opens the authorization
    URL in the default browser via ``Gtk.UriLauncher``.

    Args:
        account_manager: The shared ``AccountManager`` instance.
        **kwargs: Forwarded to ``Adw.NavigationPage``.

    Signals:
        account-added(): Emitted after the account is persisted.
    """

    __gtype_name__ = "TrackmaAddAccountPage"
    __gsignals__ = {
        "account-added": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, account_manager: AccountManager, **kwargs: Any) -> None:
        super().__init__(title="Add Account", **kwargs)
        self._manager = account_manager
        self._adding_extra: dict[str, str] = {}
        self._oauth_pin_requested = False
        self._build_ui()

    # -- UI construction -----------------------------------------------------

    def _build_ui(self) -> None:
        """Build the form: API combo, username/password rows, PIN button."""
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        self._confirm_button = Gtk.Button(
            label="Add",
            css_classes=["suggested-action"],
            sensitive=False,
        )
        self._confirm_button.connect("clicked", self._on_confirm)
        header.pack_end(self._confirm_button)
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(
            maximum_size=600,
            margin_top=24,
            margin_bottom=24,
            margin_start=12,
            margin_end=12,
        )

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # API selector
        api_group = Adw.PreferencesGroup(title="Service")
        self._api_names: list[str] = list(utils.available_libs.keys())
        string_list = Gtk.StringList()
        for api_key in self._api_names:
            string_list.append(utils.available_libs[api_key][0])

        self._api_row = Adw.ComboRow(title="Service", model=string_list)
        self._api_row.connect("notify::selected", self._on_api_changed)
        api_group.add(self._api_row)
        content.append(api_group)

        # Credential fields
        self._creds_group = Adw.PreferencesGroup(title="Credentials")

        self._username_row = Adw.EntryRow(title="Username")
        self._username_row.connect("changed", self._on_fields_changed)
        self._creds_group.add(self._username_row)

        self._password_row = Adw.PasswordEntryRow(title="Password")
        self._password_row.connect("changed", self._on_fields_changed)
        self._creds_group.add(self._password_row)

        self._pin_request_button = Gtk.Button(
            label="Request PIN",
            css_classes=["pill"],
            halign=Gtk.Align.CENTER,
            margin_top=12,
            visible=False,
        )
        self._pin_request_button.connect("clicked", self._on_pin_request)

        content.append(self._creds_group)
        content.append(self._pin_request_button)

        clamp.set_child(content)
        scroll.set_child(clamp)
        toolbar_view.set_content(scroll)
        self.set_child(toolbar_view)

        # Set initial field labels based on the default selection
        self._on_api_changed(self._api_row, None)

    # -- Helpers -------------------------------------------------------------

    def _get_selected_api(self) -> str:
        """Return the ``available_libs`` key for the currently selected API."""
        idx = self._api_row.get_selected()
        return self._api_names[idx]

    def _get_login_type(self) -> utils.Login:
        """Return the ``Login`` enum for the currently selected API."""
        api = self._get_selected_api()
        return utils.available_libs[api][2]

    def _update_confirm_sensitivity(self) -> None:
        """Enable the *Add* button only when all required fields are filled.

        For OAuth APIs the PIN must also have been requested first.
        """
        username = self._username_row.get_text().strip()
        password = self._password_row.get_text().strip()
        login_type = self._get_login_type()

        has_fields = bool(username) and bool(password)

        if login_type in (utils.Login.OAUTH, utils.Login.OAUTH_PKCE):
            self._confirm_button.set_sensitive(has_fields and self._oauth_pin_requested)
        else:
            self._confirm_button.set_sensitive(has_fields)

    # -- Signal handlers -----------------------------------------------------

    def _on_api_changed(self, _row: Adw.ComboRow, _pspec: Any) -> None:
        """Adapt field labels and button visibility to the selected API."""
        login_type = self._get_login_type()
        self._adding_extra = {}
        self._oauth_pin_requested = False

        self._username_row.set_text("")
        self._password_row.set_text("")

        if login_type in (utils.Login.OAUTH, utils.Login.OAUTH_PKCE):
            self._username_row.set_title("Name")
            self._password_row.set_title("PIN")
            self._pin_request_button.set_visible(True)
        else:
            self._username_row.set_title("Username")
            self._password_row.set_title("Password")
            self._pin_request_button.set_visible(False)

        self._update_confirm_sensitivity()

    def _on_pin_request(self, _button: Gtk.Button) -> None:
        """Open the provider's authorization URL in the default browser.

        For OAUTH_PKCE APIs a ``code_verifier`` is generated and stored
        in ``_adding_extra`` so it can be passed to ``add_account`` later.
        """
        api = self._get_selected_api()
        auth_url: str = utils.available_libs[api][3]

        if utils.available_libs[api][2] == utils.Login.OAUTH_PKCE:
            code_verifier = utils.oauth_generate_pkce()
            self._adding_extra = {"code_verifier": code_verifier}
            auth_url = auth_url % code_verifier

        self._oauth_pin_requested = True
        self._update_confirm_sensitivity()

        launcher = Gtk.UriLauncher(uri=auth_url)
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None
        launcher.launch(parent, None, None)

    def _on_fields_changed(self, _row: Adw.EntryRow) -> None:
        """Re-evaluate the *Add* button state when input changes."""
        self._update_confirm_sensitivity()

    def _on_confirm(self, _button: Gtk.Button) -> None:
        """Persist the new account and pop back to the account list."""
        api = self._get_selected_api()
        username = self._username_row.get_text().strip()
        password = self._password_row.get_text().strip()

        try:
            self._manager.add_account(username, password, api, self._adding_extra)
        except utils.AccountError as e:
            logger.error("Failed to add account: %s", e)
            return

        self.emit("account-added")

        nav_view = self.get_parent()
        if isinstance(nav_view, Adw.NavigationView):
            nav_view.pop()


class EditAccountPage(Adw.NavigationPage):
    """Page for editing an existing account's credentials.

    The service (API) is shown as a read-only row.  The username and
    password/PIN fields are pre-populated and editable.  For OAuth
    services a *Request PIN* button is available to re-authorize.

    Args:
        account_manager: The shared ``AccountManager`` instance.
        account_num: The account number to edit.
        **kwargs: Forwarded to ``Adw.NavigationPage``.

    Signals:
        account-edited(): Emitted after the account is persisted.
    """

    __gtype_name__ = "TrackmaEditAccountPage"
    __gsignals__ = {
        "account-edited": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(
        self, account_manager: AccountManager, account_num: int, **kwargs: Any
    ) -> None:
        super().__init__(title="Edit Account", **kwargs)
        self._manager = account_manager
        self._account_num = account_num
        self._account = account_manager.get_account(account_num)
        self._api_key: str = self._account["api"]
        self._login_type: utils.Login = utils.available_libs[self._api_key][2]
        self._adding_extra: dict[str, str] = {}
        self._oauth_pin_requested = False
        self._build_ui()

    # -- UI construction -----------------------------------------------------

    def _build_ui(self) -> None:
        """Build the form: read-only service info and editable credentials."""
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        self._save_button = Gtk.Button(
            label="Save",
            css_classes=["suggested-action"],
            sensitive=False,
        )
        self._save_button.connect("clicked", self._on_save)
        header.pack_end(self._save_button)
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(
            maximum_size=600,
            margin_top=24,
            margin_bottom=24,
            margin_start=12,
            margin_end=12,
        )
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # Read-only service info
        info_group = Adw.PreferencesGroup(title="Account")
        lib_info = utils.available_libs.get(self._api_key)
        display_name = lib_info[0] if lib_info else self._api_key
        info_group.add(Adw.ActionRow(title="Service", subtitle=display_name))
        content.append(info_group)

        # Editable credentials
        creds_group = Adw.PreferencesGroup(title="Credentials")
        is_oauth = self._login_type in (utils.Login.OAUTH, utils.Login.OAUTH_PKCE)

        self._username_row = Adw.EntryRow(
            title="Name" if is_oauth else "Username",
            text=self._account["username"],
        )
        self._username_row.connect("changed", self._on_fields_changed)
        creds_group.add(self._username_row)

        self._password_row = Adw.PasswordEntryRow(
            title="PIN" if is_oauth else "Password",
        )
        self._password_row.connect("changed", self._on_fields_changed)
        creds_group.add(self._password_row)

        content.append(creds_group)

        if is_oauth:
            self._pin_request_button = Gtk.Button(
                label="Request PIN",
                css_classes=["pill"],
                halign=Gtk.Align.CENTER,
                margin_top=12,
            )
            self._pin_request_button.connect("clicked", self._on_pin_request)
            content.append(self._pin_request_button)

        clamp.set_child(content)
        scroll.set_child(clamp)
        toolbar_view.set_content(scroll)
        self.set_child(toolbar_view)

    # -- Helpers -------------------------------------------------------------

    def _update_save_sensitivity(self) -> None:
        """Enable the *Save* button only when all required fields are filled.

        For OAuth APIs the PIN must also have been re-requested first.
        """
        username = self._username_row.get_text().strip()
        password = self._password_row.get_text().strip()
        has_fields = bool(username) and bool(password)

        is_oauth = self._login_type in (utils.Login.OAUTH, utils.Login.OAUTH_PKCE)
        if is_oauth:
            self._save_button.set_sensitive(has_fields and self._oauth_pin_requested)
        else:
            self._save_button.set_sensitive(has_fields)

    # -- Signal handlers -----------------------------------------------------

    def _on_pin_request(self, _button: Gtk.Button) -> None:
        """Open the provider's authorization URL for re-authorization."""
        auth_url: str = utils.available_libs[self._api_key][3]

        if self._login_type == utils.Login.OAUTH_PKCE:
            code_verifier = utils.oauth_generate_pkce()
            self._adding_extra = {"code_verifier": code_verifier}
            auth_url = auth_url % code_verifier

        self._oauth_pin_requested = True
        self._update_save_sensitivity()

        launcher = Gtk.UriLauncher(uri=auth_url)
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None
        launcher.launch(parent, None, None)

    def _on_fields_changed(self, _row: Adw.EntryRow) -> None:
        """Re-evaluate the *Save* button state when input changes."""
        self._update_save_sensitivity()

    def _on_save(self, _button: Gtk.Button) -> None:
        """Persist the edited account and pop back to the account list."""
        username = self._username_row.get_text().strip()
        password = self._password_row.get_text().strip()
        extra = self._adding_extra if self._adding_extra else self._account.get("extra", {})

        try:
            self._manager.edit_account(
                self._account_num, username, password, self._api_key, extra
            )
        except utils.AccountError as e:
            logger.error("Failed to edit account: %s", e)
            return

        self.emit("account-edited")

        nav_view = self.get_parent()
        if isinstance(nav_view, Adw.NavigationView):
            nav_view.pop()
