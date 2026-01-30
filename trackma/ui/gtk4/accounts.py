"""
Trackma GTK4 Account Selection Page.

Provides an AdwNavigationPage for selecting existing accounts and adding
new ones. Communicates account selection via the ``account-open`` signal.
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

    Signals:
        account-open(account_num: int): Emitted when the user selects an account.
    """

    __gtype_name__ = "TrackmaAccountPage"
    __gsignals__ = {
        "account-open": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, account_manager: AccountManager, **kwargs: Any) -> None:
        super().__init__(title="Accounts", **kwargs)
        self._manager = account_manager
        self._build_ui()

    def _build_ui(self) -> None:
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

        # Content: either account list or empty state
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
        clamp = Adw.Clamp(maximum_size=600, margin_top=24, margin_bottom=24, margin_start=12, margin_end=12)

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
        menu = Gio.Menu()
        menu.append("About Trackma", "app.about")
        return menu

    def refresh_accounts(self) -> None:
        """Reload account list from AccountManager."""
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

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        action_row = row
        account_num: int = action_row._account_num  # type: ignore[attr-defined]
        self.emit("account-open", account_num)

    def _on_add_clicked(self, _button: Gtk.Button) -> None:
        nav_view = self.get_parent()
        if not isinstance(nav_view, Adw.NavigationView):
            return
        add_page = AddAccountPage(self._manager)
        add_page.connect("account-added", self._on_account_added)
        nav_view.push(add_page)

    def _on_edit_clicked(self, button: Gtk.Button) -> None:
        account_num: int = button._account_num  # type: ignore[attr-defined]
        nav_view = self.get_parent()
        if not isinstance(nav_view, Adw.NavigationView):
            return
        edit_page = EditAccountPage(self._manager, account_num)
        edit_page.connect("account-edited", lambda _p: self.refresh_accounts())
        nav_view.push(edit_page)

    def _on_delete_clicked(self, button: Gtk.Button) -> None:
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
        dialog.present(self.get_root())

    def _on_delete_response(
        self, dialog: Adw.AlertDialog, response: str, account_num: int
    ) -> None:
        if response == "remove":
            self._manager.delete_account(account_num)
            self.refresh_accounts()

    def _on_account_added(self, _page: AddAccountPage) -> None:
        self.refresh_accounts()


class AddAccountPage(Adw.NavigationPage):
    """Page for adding a new account.

    Signals:
        account-added(): Emitted after an account is successfully added.
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

    def _build_ui(self) -> None:
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
        clamp = Adw.Clamp(maximum_size=600, margin_top=24, margin_bottom=24, margin_start=12, margin_end=12)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # API selector group
        api_group = Adw.PreferencesGroup(title="Service")
        self._api_names: list[str] = list(utils.available_libs.keys())
        string_list = Gtk.StringList()
        for api_key in self._api_names:
            string_list.append(utils.available_libs[api_key][0])

        self._api_row = Adw.ComboRow(title="Service", model=string_list)
        self._api_row.connect("notify::selected", self._on_api_changed)
        api_group.add(self._api_row)
        content.append(api_group)

        # Credentials group
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

        # Trigger initial state
        self._on_api_changed(self._api_row, None)

    def _get_selected_api(self) -> str:
        idx = self._api_row.get_selected()
        return self._api_names[idx]

    def _get_login_type(self) -> utils.Login:
        api = self._get_selected_api()
        return utils.available_libs[api][2]

    def _on_api_changed(self, _row: Adw.ComboRow, _pspec: Any) -> None:
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
        api = self._get_selected_api()
        auth_url = utils.available_libs[api][3]

        if utils.available_libs[api][2] == utils.Login.OAUTH_PKCE:
            code_verifier = utils.oauth_generate_pkce()
            self._adding_extra = {"code_verifier": code_verifier}
            auth_url = auth_url % code_verifier

        self._oauth_pin_requested = True
        self._update_confirm_sensitivity()

        launcher = Gtk.UriLauncher(uri=auth_url)
        window = self.get_root()
        launcher.launch(window, None, None)

    def _on_fields_changed(self, _row: Adw.EntryRow) -> None:
        self._update_confirm_sensitivity()

    def _update_confirm_sensitivity(self) -> None:
        username = self._username_row.get_text().strip()
        password = self._password_row.get_text().strip()
        login_type = self._get_login_type()

        has_fields = bool(username) and bool(password)

        if login_type in (utils.Login.OAUTH, utils.Login.OAUTH_PKCE):
            self._confirm_button.set_sensitive(has_fields and self._oauth_pin_requested)
        else:
            self._confirm_button.set_sensitive(has_fields)

    def _on_confirm(self, _button: Gtk.Button) -> None:
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

    Signals:
        account-edited(): Emitted after the account is successfully updated.
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
        self._api_key = self._account["api"]
        self._login_type = utils.available_libs[self._api_key][2]
        self._adding_extra: dict[str, str] = {}
        self._oauth_pin_requested = False
        self._build_ui()

    def _build_ui(self) -> None:
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
            maximum_size=600, margin_top=24, margin_bottom=24, margin_start=12, margin_end=12
        )
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # Info group (read-only)
        info_group = Adw.PreferencesGroup(title="Account")
        lib_info = utils.available_libs.get(self._api_key)
        display_name = lib_info[0] if lib_info else self._api_key
        info_group.add(Adw.ActionRow(title="Service", subtitle=display_name))
        content.append(info_group)

        # Credentials group
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

    def _on_pin_request(self, _button: Gtk.Button) -> None:
        auth_url = utils.available_libs[self._api_key][3]

        if self._login_type == utils.Login.OAUTH_PKCE:
            code_verifier = utils.oauth_generate_pkce()
            self._adding_extra = {"code_verifier": code_verifier}
            auth_url = auth_url % code_verifier

        self._oauth_pin_requested = True
        self._update_save_sensitivity()

        launcher = Gtk.UriLauncher(uri=auth_url)
        launcher.launch(self.get_root(), None, None)

    def _on_fields_changed(self, _row: Adw.EntryRow) -> None:
        self._update_save_sensitivity()

    def _update_save_sensitivity(self) -> None:
        username = self._username_row.get_text().strip()
        password = self._password_row.get_text().strip()
        has_fields = bool(username) and bool(password)

        is_oauth = self._login_type in (utils.Login.OAUTH, utils.Login.OAUTH_PKCE)
        if is_oauth:
            self._save_button.set_sensitive(has_fields and self._oauth_pin_requested)
        else:
            self._save_button.set_sensitive(has_fields)

    def _on_save(self, _button: Gtk.Button) -> None:
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
