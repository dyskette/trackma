"""
Trackma GTK4 Show List View.

Displays the user's anime/manga list organized by status using an
AdwNavigationSplitView sidebar. The sidebar lists statuses; the content
area shows a GtkListView for the selected status, backed by a chain of
Gio.ListStore -> SortListModel -> FilterListModel -> SingleSelection.

All interaction with the Trackma core happens exclusively through
Engine methods. Engine signals are marshaled to the main thread via
GLib.idle_add.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk

if TYPE_CHECKING:
    from trackma.engine import Engine
    from trackma.ui.gtk4.show_detail import ShowDetailPage

logger = logging.getLogger(__name__)


class ShowObject(GObject.Object):
    """GObject wrapper around a Trackma show dictionary.

    Wraps the plain dict so it can live inside a ``Gio.ListStore``.
    Property changes emit ``notify`` automatically, which drives
    UI updates through GtkExpression / property bindings.

    Args:
        data: Show dictionary from the engine.
    """

    __gtype_name__ = "TrackmaShowObject"

    show_id = GObject.Property(type=int, default=0)  # type: ignore[assignment]
    title = GObject.Property(type=str, default="")  # type: ignore[assignment]
    progress = GObject.Property(type=int, default=0)  # type: ignore[assignment]
    total = GObject.Property(type=int, default=0)  # type: ignore[assignment]
    score = GObject.Property(type=float, default=0.0)  # type: ignore[assignment]
    status = GObject.Property(type=str, default="")  # type: ignore[assignment]
    queued = GObject.Property(type=bool, default=False)  # type: ignore[assignment]

    def __init__(self, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._data: dict[str, Any] = {}
        if data is not None:
            self._apply(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShowObject:
        """Create a ``ShowObject`` from a Trackma show dictionary."""
        return cls(data=data)

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """Update properties in-place from a show dictionary."""
        self._apply(data)

    def get_data(self) -> dict[str, Any]:
        """Return the underlying show dictionary."""
        return self._data

    def _apply(self, data: dict[str, Any]) -> None:
        """Set all GObject properties from a show dictionary."""
        self._data = data
        self.show_id = data.get("id", 0)
        self.title = data.get("title", "")
        self.progress = data.get("my_progress", 0)
        self.total = data.get("total", 0)
        self.score = float(data.get("my_score", 0))
        self.status = str(data.get("my_status", ""))
        self.queued = bool(data.get("queued", False))


class ShowListPage(Adw.NavigationPage):
    """Navigation page displaying the show list with a status sidebar.

    Uses an ``AdwNavigationSplitView`` with a sidebar listing statuses
    and a content area showing shows for the selected status.

    Signals:
        switch-account: Emitted when the user clicks the Switch Account button.

    Args:
        engine: Started Trackma Engine instance.
        **kwargs: Forwarded to ``Adw.NavigationPage``.
    """

    __gtype_name__ = "TrackmaShowListPage"
    __gsignals__ = {
        "switch-account": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, engine: Engine, **kwargs: Any) -> None:
        super().__init__(title="Library", **kwargs)
        self._engine = engine
        self._mediainfo: dict[str, Any] = engine.mediainfo
        self._statuses: dict[str | int, str] = self._mediainfo["statuses_dict"]
        self._stores: dict[str | int, Gio.ListStore] = {}
        self._current_status: str | int | None = None

        self._build_ui()
        self._populate_stores()
        self._connect_engine_signals()

        # Select first status
        self._sidebar_list.select_row(self._sidebar_list.get_row_at_index(0))

    # -- UI construction -------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the widget tree.

        Layout::

            AdwNavigationSplitView
            ├── sidebar: AdwNavigationPage
            │   └── AdwToolbarView
            │       ├── [top] AdwHeaderBar (accounts btn, hamburger menu)
            │       └── [content] GtkListBox (.navigation-sidebar)
            └── content: AdwNavigationPage
                └── AdwToolbarView
                    ├── [top] AdwHeaderBar (search toggle)
                    ├── [top] GtkSearchBar
                    └── [content] GtkStack (list | empty status page)

        The split view collapses automatically on narrow windows,
        turning the sidebar into a pushed navigation page with a
        back button.
        """
        self._split_view = Adw.NavigationSplitView()

        # -- Sidebar -----------------------------------------------------------
        sidebar_toolbar = Adw.ToolbarView()

        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_title_widget(Adw.WindowTitle(title="Trackma"))

        accounts_btn = Gtk.Button(
            icon_name="system-users-symbolic",
            tooltip_text="Switch Account",
        )
        accounts_btn.connect("clicked", lambda _b: self.emit("switch-account"))
        sidebar_header.pack_start(accounts_btn)
        sidebar_header.pack_end(self._build_menu_button())

        sidebar_toolbar.add_top_bar(sidebar_header)

        self._sidebar_list = Gtk.ListBox()
        self._sidebar_list.add_css_class("navigation-sidebar")
        self._sidebar_list.connect("row-selected", self._on_sidebar_row_selected)

        self._status_keys: list[str | int] = []
        for status_num, status_name in self._statuses.items():
            row = Gtk.ListBoxRow()
            label = Gtk.Label(
                label=status_name,
                xalign=0,
            )
            label.set_margin_start(8)
            label.set_margin_end(8)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            row.set_child(label)
            self._sidebar_list.append(row)
            self._status_keys.append(status_num)

        sidebar_toolbar.set_content(self._sidebar_list)

        sidebar_page = Adw.NavigationPage(title="Library")
        sidebar_page.set_child(sidebar_toolbar)

        # -- Content -----------------------------------------------------------
        content_toolbar = Adw.ToolbarView()

        self._content_header = Adw.HeaderBar()
        self._content_title = Adw.WindowTitle(title="", subtitle="")
        self._content_header.set_title_widget(self._content_title)

        self._search_btn = Gtk.ToggleButton(
            icon_name="edit-find-symbolic",
            tooltip_text="Search",
        )
        self._content_header.pack_end(self._search_btn)

        content_toolbar.add_top_bar(self._content_header)

        # Search bar
        self._search_entry = Gtk.SearchEntry(
            placeholder_text="Search shows...",
            hexpand=True,
        )
        self._search_bar = Gtk.SearchBar(child=self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        self._search_btn.bind_property(
            "active", self._search_bar, "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )
        self._search_entry.connect("search-changed", self._on_search_changed)
        content_toolbar.add_top_bar(self._search_bar)

        # Shared list view + empty state
        self._content_store = Gio.ListStore(item_type=ShowObject)

        sorter = Gtk.StringSorter(
            expression=Gtk.PropertyExpression.new(ShowObject, None, "title"),
        )
        sort_model = Gtk.SortListModel(model=self._content_store, sorter=sorter)

        self._string_filter = Gtk.StringFilter(
            expression=Gtk.PropertyExpression.new(ShowObject, None, "title"),
            match_mode=Gtk.StringFilterMatchMode.SUBSTRING,
            ignore_case=True,
        )
        self._filter_model = Gtk.FilterListModel(
            model=sort_model, filter=self._string_filter,
        )

        selection = Gtk.SingleSelection(model=self._filter_model, autoselect=False)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_row_setup)
        factory.connect("bind", self._on_row_bind)
        factory.connect("unbind", self._on_row_unbind)

        self._list_view = Gtk.ListView(
            model=selection,
            factory=factory,
            single_click_activate=True,
        )
        self._list_view.connect("activate", self._on_row_activated)

        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vexpand=True,
        )
        scrolled.set_child(self._list_view)

        self._empty_page = Adw.StatusPage(
            icon_name="view-list-symbolic",
            title="No Shows",
            description="",
        )

        self._content_stack = Gtk.Stack()
        self._content_stack.add_named(scrolled, "list")
        self._content_stack.add_named(self._empty_page, "empty")

        self._filter_model.connect("items-changed", self._update_empty_state)

        content_toolbar.set_content(self._content_stack)

        self._content_page = Adw.NavigationPage(title="Shows")
        self._content_page.set_child(content_toolbar)

        # -- Assemble split view -----------------------------------------------
        self._split_view.set_sidebar(sidebar_page)
        self._split_view.set_content(self._content_page)

        self.set_child(self._split_view)

        # Key capture for search
        self._search_bar.set_key_capture_widget(self)

        # Actions
        self._setup_actions()

    def _build_menu_button(self) -> Gtk.MenuButton:
        """Build the hamburger menu with sync actions and About."""
        menu = Gio.Menu()

        sync_section = Gio.Menu()
        sync_section.append("Download List", "page.download")
        sync_section.append("Upload Changes", "page.upload")
        menu.append_section(None, sync_section)

        about_section = Gio.Menu()
        about_section.append("About Trackma", "app.about")
        menu.append_section(None, about_section)

        return Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu,
        )

    def _setup_actions(self) -> None:
        """Register page-level actions for download and upload."""
        group = Gio.SimpleActionGroup()

        download_action = Gio.SimpleAction.new("download", None)
        download_action.connect("activate", self._on_download)
        group.add_action(download_action)

        upload_action = Gio.SimpleAction.new("upload", None)
        upload_action.connect("activate", self._on_upload)
        group.add_action(upload_action)

        self.insert_action_group("page", group)

    # -- Sidebar selection -----------------------------------------------------

    def _on_sidebar_row_selected(
        self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None,
    ) -> None:
        """Handle sidebar status selection.

        Swaps the content store to show items for the newly selected
        status.  On collapsed layouts, navigates forward to the content
        page automatically.

        Args:
            listbox: The sidebar ``GtkListBox``.
            row: The selected row, or ``None`` if deselected.
        """
        if row is None:
            return

        index = row.get_index()
        if index < 0 or index >= len(self._status_keys):
            return

        status_num = self._status_keys[index]
        self._current_status = status_num
        status_name = self._statuses[status_num]

        self._content_title.set_title(status_name)
        self._content_page.set_title(status_name)
        self._empty_page.set_description(
            f"No shows with status \u201c{status_name}\u201d"
        )

        # Swap content store items
        self._content_store.remove_all()
        if status_num in self._stores:
            store = self._stores[status_num]
            for i in range(store.get_n_items()):
                item = store.get_item(i)
                if item is not None:
                    self._content_store.append(item)

        self._update_empty_state()

        # On collapsed layout, show the content page
        if self._split_view.get_collapsed():
            self._split_view.set_show_content(True)

    def _update_empty_state(self, *_args: Any) -> None:
        """Toggle between the list view and the empty status page."""
        if self._filter_model.get_n_items() == 0:
            self._content_stack.set_visible_child_name("empty")
        else:
            self._content_stack.set_visible_child_name("list")

    # -- Row factory -----------------------------------------------------------

    def _on_row_setup(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Create the widget structure for a single show row.

        Called once per visible row slot.  The box and its child labels
        are reused across different items via bind/unbind.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        title_label = Gtk.Label(
            xalign=0,
            hexpand=True,
            ellipsize=3,  # Pango.EllipsizeMode.END
        )
        title_label.add_css_class("body")

        progress_label = Gtk.Label(xalign=1)
        progress_label.add_css_class("dim-label")

        score_label = Gtk.Label(xalign=1)
        score_label.add_css_class("dim-label")

        box.append(title_label)
        box.append(progress_label)
        box.append(score_label)

        # Stash references for bind/unbind
        box._title_label = title_label  # type: ignore[attr-defined]
        box._progress_label = progress_label  # type: ignore[attr-defined]
        box._score_label = score_label  # type: ignore[attr-defined]
        box._bindings = []  # type: ignore[attr-defined]

        list_item.set_child(box)

    def _on_row_bind(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind a ``ShowObject`` to the row widgets.

        Sets label text and connects ``notify`` handlers so the row
        updates live when properties change.
        """
        box = list_item.get_child()
        show: ShowObject = list_item.get_item()  # type: ignore[assignment]

        box._title_label.set_text(show.title)  # type: ignore[union-attr]

        # Format progress
        if show.total > 0:
            box._progress_label.set_text(f"{show.progress}/{show.total}")  # type: ignore[union-attr]
        else:
            box._progress_label.set_text(f"{show.progress}/?")  # type: ignore[union-attr]

        # Format score
        can_score = self._mediainfo.get("can_score", False)
        if can_score and show.score > 0:
            score_step = self._mediainfo.get("score_step", 1)
            if isinstance(score_step, float) and score_step != int(score_step):
                box._score_label.set_text(f"\u2605 {show.score:.1f}")  # type: ignore[union-attr]
            else:
                box._score_label.set_text(f"\u2605 {int(show.score)}")  # type: ignore[union-attr]
            box._score_label.set_visible(True)  # type: ignore[union-attr]
        else:
            box._score_label.set_visible(False)  # type: ignore[union-attr]

        # Update on property changes
        bindings = []
        for prop in ("title", "progress", "total", "score"):
            handler_id = show.connect(f"notify::{prop}", self._on_show_prop_changed, box)
            bindings.append((show, handler_id))
        box._bindings = bindings  # type: ignore[union-attr]

    def _on_row_unbind(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Disconnect property-change handlers when the row is recycled."""
        box = list_item.get_child()
        for obj, handler_id in box._bindings:  # type: ignore[union-attr]
            obj.disconnect(handler_id)
        box._bindings = []  # type: ignore[union-attr]

    def _on_show_prop_changed(
        self,
        show: ShowObject,
        _pspec: GObject.ParamSpec,
        box: Gtk.Box,
    ) -> None:
        """Re-render row when a show property changes."""
        box._title_label.set_text(show.title)  # type: ignore[attr-defined]
        if show.total > 0:
            box._progress_label.set_text(f"{show.progress}/{show.total}")  # type: ignore[attr-defined]
        else:
            box._progress_label.set_text(f"{show.progress}/?")  # type: ignore[attr-defined]

        can_score = self._mediainfo.get("can_score", False)
        if can_score and show.score > 0:
            score_step = self._mediainfo.get("score_step", 1)
            if isinstance(score_step, float) and score_step != int(score_step):
                box._score_label.set_text(f"\u2605 {show.score:.1f}")  # type: ignore[attr-defined]
            else:
                box._score_label.set_text(f"\u2605 {int(show.score)}")  # type: ignore[attr-defined]
            box._score_label.set_visible(True)  # type: ignore[attr-defined]
        else:
            box._score_label.set_visible(False)  # type: ignore[attr-defined]

    # -- Data population -------------------------------------------------------

    def _populate_stores(self) -> None:
        """Fill all status stores from the engine's current list."""
        for status_num in self._statuses:
            if status_num not in self._stores:
                self._stores[status_num] = Gio.ListStore(item_type=ShowObject)
            store = self._stores[status_num]
            store.remove_all()
            shows = self._engine.filter_list(status_num)
            for show_data in shows:
                store.append(ShowObject.from_dict(show_data))

    def _refresh_content_view(self) -> None:
        """Re-sync content store from the backing store for current status."""
        if self._current_status is None:
            return
        self._content_store.remove_all()
        if self._current_status in self._stores:
            store = self._stores[self._current_status]
            for i in range(store.get_n_items()):
                item = store.get_item(i)
                if item is not None:
                    self._content_store.append(item)
        self._update_empty_state()

    # -- Search ----------------------------------------------------------------

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Apply the search query to the shared string filter."""
        query = entry.get_text().strip()
        if query:
            self._string_filter.set_search(query)
        else:
            self._string_filter.set_search("")

    # -- Row activation --------------------------------------------------------

    def _on_row_activated(self, list_view: Gtk.ListView, position: int) -> None:
        """Open the detail page for the activated show.

        Finds the ``AdwNavigationView`` ancestor and pushes a
        ``ShowDetailPage`` onto it.

        Args:
            list_view: The ``GtkListView``.
            position: Index of the activated item in the selection model.
        """
        model = list_view.get_model()
        if model is None:
            return
        show_obj: ShowObject | None = model.get_item(position)  # type: ignore[assignment]
        if show_obj is None:
            return

        show_data = show_obj.get_data()
        if not show_data:
            return

        # Walk up to find the NavigationView
        nav_view = self._find_nav_view()
        if nav_view is None:
            logger.warning("No AdwNavigationView found for detail push")
            return

        from trackma.ui.gtk4.show_detail import ShowDetailPage

        detail_page = ShowDetailPage(engine=self._engine, show_data=show_data)
        nav_view.push(detail_page)

    def _find_nav_view(self) -> Adw.NavigationView | None:
        """Walk up the widget tree to find the nearest NavigationView."""
        widget: Gtk.Widget | None = self.get_parent()
        while widget is not None:
            if isinstance(widget, Adw.NavigationView):
                return widget
            widget = widget.get_parent()
        return None

    # -- Engine signals --------------------------------------------------------

    def _connect_engine_signals(self) -> None:
        """Connect to engine signals for live list updates."""
        self._engine.connect_signal("episode_changed", self._on_episode_changed)
        self._engine.connect_signal("score_changed", self._on_score_changed)
        self._engine.connect_signal("status_changed", self._on_status_changed)
        self._engine.connect_signal("show_added", self._on_show_added)
        self._engine.connect_signal("show_deleted", self._on_show_deleted)

    def _find_show_object(
        self, show_id: int, status: str | int | None = None,
    ) -> tuple[Gio.ListStore, int, ShowObject] | None:
        """Find a ShowObject by id across stores.

        Args:
            show_id: The show's id.
            status: If given, only search in that status store.

        Returns:
            Tuple of (store, position, show_object) or None.
        """
        stores = (
            [(status, self._stores[status])] if status is not None and status in self._stores
            else self._stores.items()
        )
        for _status, store in stores:
            for i in range(store.get_n_items()):
                obj = store.get_item(i)
                if obj is not None and obj.show_id == show_id:
                    return store, i, obj
        return None

    def _on_episode_changed(self, show: dict[str, Any]) -> None:
        """Engine callback for episode changes; marshals to main thread."""
        GLib.idle_add(self._handle_show_update, show)

    def _on_score_changed(self, show: dict[str, Any]) -> None:
        """Engine callback for score changes; marshals to main thread."""
        GLib.idle_add(self._handle_show_update, show)

    def _handle_show_update(self, show: dict[str, Any]) -> bool:
        """Update a ``ShowObject`` in-place from fresh show data."""
        result = self._find_show_object(show.get("id", 0))
        if result is not None:
            _store, _pos, obj = result
            obj.update_from_dict(show)
        return GLib.SOURCE_REMOVE

    def _on_status_changed(self, show: dict[str, Any], old_status: str | int) -> None:
        """Engine callback for status changes; marshals to main thread."""
        GLib.idle_add(self._handle_status_changed, show, old_status)

    def _handle_status_changed(self, show: dict[str, Any], old_status: str | int) -> bool:
        """Move a show between backing stores and refresh the content view."""
        show_id = show.get("id", 0)
        # Remove from old status store
        result = self._find_show_object(show_id, old_status)
        if result is not None:
            store, pos, _obj = result
            store.remove(pos)

        # Add to new status store
        new_status = show.get("my_status", 0)
        if new_status in self._stores:
            self._stores[new_status].append(ShowObject.from_dict(show))

        # Refresh content view if affected status is currently shown
        if self._current_status in (old_status, new_status):
            self._refresh_content_view()

        return GLib.SOURCE_REMOVE

    def _on_show_added(self, show: dict[str, Any]) -> None:
        """Engine callback for show additions; marshals to main thread."""
        GLib.idle_add(self._handle_show_added, show)

    def _handle_show_added(self, show: dict[str, Any]) -> bool:
        """Append a new show to the appropriate backing store."""
        status = show.get("my_status", 0)
        if status in self._stores:
            self._stores[status].append(ShowObject.from_dict(show))
        if status == self._current_status:
            self._refresh_content_view()
        return GLib.SOURCE_REMOVE

    def _on_show_deleted(self, show: dict[str, Any]) -> None:
        """Engine callback for show deletions; marshals to main thread."""
        GLib.idle_add(self._handle_show_deleted, show)

    def _handle_show_deleted(self, show: dict[str, Any]) -> bool:
        """Remove a show from its backing store and refresh the content view."""
        result = self._find_show_object(show.get("id", 0))
        if result is not None:
            store, pos, _obj = result
            store.remove(pos)
            if self._current_status is not None:
                self._refresh_content_view()
        return GLib.SOURCE_REMOVE

    # -- Sync actions ----------------------------------------------------------

    def _on_download(self, _action: Gio.SimpleAction, _param: Any) -> None:
        """Action handler for ``page.download``."""
        self._run_in_thread(self._do_download)

    def _on_upload(self, _action: Gio.SimpleAction, _param: Any) -> None:
        """Action handler for ``page.upload``."""
        self._run_in_thread(self._do_upload)

    def _do_download(self) -> None:
        """Download the remote list in a background thread."""
        try:
            self._engine.list_download()
            GLib.idle_add(self._on_download_complete)
        except Exception as e:
            GLib.idle_add(self._show_toast, f"Download failed: {e}")

    def _on_download_complete(self) -> bool:
        """Repopulate all stores after a successful download."""
        self._populate_stores()
        self._refresh_content_view()
        self._show_toast("List downloaded")
        return GLib.SOURCE_REMOVE

    def _do_upload(self) -> None:
        """Upload queued changes in a background thread."""
        try:
            self._engine.list_upload()
            GLib.idle_add(self._show_toast, "Changes uploaded")
        except Exception as e:
            GLib.idle_add(self._show_toast, f"Upload failed: {e}")

    def _run_in_thread(self, target: Callable[[], None]) -> None:
        """Run *target* on a daemon thread."""
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def _show_toast(self, message: str) -> bool:
        """Show a toast by walking up to the nearest ToastOverlay."""
        widget: Gtk.Widget | None = self
        while widget is not None:
            if isinstance(widget, Adw.ToastOverlay):
                toast = Adw.Toast.new(message)
                toast.set_timeout(3)
                widget.add_toast(toast)
                return GLib.SOURCE_REMOVE
            widget = widget.get_parent()
        logger.warning("No ToastOverlay found for message: %s", message)
        return GLib.SOURCE_REMOVE
