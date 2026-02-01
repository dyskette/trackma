"""
Trackma GTK4 Show List View.

Displays the user's anime/manga list as a flat list with status filtering
via a MenuButton in the header bar. The filter chain is:

    Gio.ListStore (all shows)
      → Gtk.FilterListModel (status filter)
        → Gtk.SortListModel (alphabetical)
          → Gtk.FilterListModel (search string)
            → Gtk.SingleSelection

When the search bar is active and the query is ≥ 3 characters, a debounced
remote search fires after 500 ms. Results appear in a second boxed-list
section ("Online Results") below the local matches.

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

from trackma.utils import Tracker as TrackerState

if TYPE_CHECKING:
    from trackma.engine import Engine

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
    """Navigation page displaying the show list with status filtering.

    Shows all items in a ``GtkListBox`` with ``Adw.ActionRow`` rows,
    styled as a boxed list inside an ``AdwClamp``. A ``MenuButton``
    in the header bar provides status filtering.

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
        self._current_status: str | int | None = None
        self._has_progress: bool = self._mediainfo.get("has_progress", True)
        self._can_score: bool = self._mediainfo.get("can_score", False)
        self._sort_key: str = "title"
        self._sort_ascending: bool = True
        self._remote_search_timeout_id: int = 0
        self._remote_results: list[Any] = []
        self._remote_dirty: bool = False

        self._prompt_active: bool = False

        self._build_ui()
        self._populate_store()
        self._connect_engine_signals()
        self.connect("shown", self._on_page_shown)

    # -- UI construction -------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the widget tree.

        Layout::

            AdwToolbarView
            ├── [top] AdwHeaderBar
            │   ├── [start] accounts_btn
            │   ├── [end] menu_btn (hamburger)
            │   ├── [end] sort_btn
            │   └── [end] search_btn (with status filter dropdown)
            ├── [top] GtkSearchBar
            └── [content] GtkStack (list | empty)
        """
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        self._header_title = Adw.WindowTitle(title="Library", subtitle="")
        header.set_title_widget(self._header_title)

        accounts_btn = Gtk.Button(
            icon_name="system-users-symbolic",
            tooltip_text="Switch Account",
        )
        accounts_btn.connect("clicked", lambda _button: self.emit("switch-account"))
        header.pack_start(accounts_btn)

        header.pack_end(self._build_menu_button())

        self._sort_btn = Adw.SplitButton(
            icon_name="view-sort-descending-symbolic",
            tooltip_text="Toggle sort direction",
            menu_model=self._build_sort_menu(),
        )
        self._sort_btn.connect("clicked", self._on_sort_direction_clicked)
        header.pack_end(self._sort_btn)

        self._search_btn = Adw.SplitButton(
            icon_name="edit-find-symbolic",
            tooltip_text="Search",
            menu_model=self._build_filter_menu(),
        )
        self._search_btn.connect("clicked", self._on_search_btn_clicked)
        header.pack_end(self._search_btn)

        toolbar.add_top_bar(header)

        # Search bar
        self._search_entry = Gtk.SearchEntry(
            placeholder_text="Search shows...",
            hexpand=True,
        )
        search_clamp = Adw.Clamp(maximum_size=600, child=self._search_entry)
        self._search_bar = Gtk.SearchBar(child=search_clamp)
        self._search_bar.connect_entry(self._search_entry)
        self._search_bar.connect(
            "notify::search-mode-enabled", self._on_search_mode_changed,
        )
        self._search_entry.connect("search-changed", self._on_search_changed)
        toolbar.add_top_bar(self._search_bar)

        # Data model: store → status filter → sort → search filter
        self._store = Gio.ListStore(item_type=ShowObject)

        self._status_filter = Gtk.CustomFilter.new(self._status_filter_func)
        status_filter_model = Gtk.FilterListModel(
            model=self._store, filter=self._status_filter,
        )

        self._sorter = Gtk.CustomSorter.new(self._sort_func)
        sort_model = Gtk.SortListModel(model=status_filter_model, sorter=self._sorter)

        self._search_query: str = ""
        self._search_filter = Gtk.CustomFilter.new(self._search_filter_func)
        self._filter_model = Gtk.FilterListModel(
            model=sort_model, filter=self._search_filter,
        )

        # List content
        scroll = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        clamp = Adw.Clamp(maximum_size=600)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)

        list_box_outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=24,
        )

        self._list_group = Adw.PreferencesGroup()
        self._listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._listbox.add_css_class("boxed-list")
        self._listbox.connect("row-activated", self._on_row_activated)
        self._list_group.add(self._listbox)
        list_box_outer.append(self._list_group)

        # Remote search results section (hidden by default)
        self._remote_group = Adw.PreferencesGroup(title="Online Results")
        self._remote_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._remote_listbox.add_css_class("boxed-list")
        self._remote_listbox.connect("row-activated", self._on_remote_row_activated)
        self._remote_group.add(self._remote_listbox)
        self._remote_group.set_visible(False)
        list_box_outer.append(self._remote_group)

        clamp.set_child(list_box_outer)
        scroll.set_child(clamp)

        self._empty_page = Adw.StatusPage(
            icon_name="view-list-symbolic",
            title="No Shows",
            description="",
        )

        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._content_stack.add_named(scroll, "list")
        self._content_stack.add_named(self._empty_page, "empty")

        self._filter_signal_id = self._filter_model.connect(
            "items-changed", self._on_filter_items_changed,
        )

        toolbar.set_content(self._content_stack)

        self._tracker_banner = Adw.Banner(title="Tracker: Listening", revealed=False)
        toolbar.add_bottom_bar(self._tracker_banner)

        self.set_child(toolbar)

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
        sync_section.append("Scan Library", "page.scan-library")
        menu.append_section(None, sync_section)

        app_section = Gio.Menu()
        app_section.append("Preferences", "app.preferences")
        app_section.append("About Trackma", "app.about")
        menu.append_section(None, app_section)

        return Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu,
        )

    def _build_filter_menu(self) -> Gio.Menu:
        """Build the status filter menu model for the split button dropdown."""
        menu = Gio.Menu()
        menu.append("All", "page.filter-status::all")
        for status_num, status_name in self._statuses.items():
            menu.append(status_name, f"page.filter-status::{status_num}")
        return menu

    def _build_sort_menu(self) -> Gio.Menu:
        """Build the sort-by menu model for the sort split button dropdown."""
        menu = Gio.Menu()
        menu.append("Title", "page.sort-by::title")
        if self._has_progress:
            menu.append("Progress", "page.sort-by::progress")
        if self._can_score:
            menu.append("Score", "page.sort-by::score")
        return menu

    def _sort_func(self, a: ShowObject, b: ShowObject, _data: Any = None) -> int:
        """Compare two ShowObjects using the current sort key and direction."""
        if self._sort_key == "title":
            va = a.title.casefold()
            vb = b.title.casefold()
        elif self._sort_key == "progress":
            va = a.progress
            vb = b.progress
        elif self._sort_key == "score":
            va = a.score
            vb = b.score
        else:
            va = a.title.casefold()
            vb = b.title.casefold()

        if va < vb:
            result = -1
        elif va > vb:
            result = 1
        else:
            result = 0

        return result if self._sort_ascending else -result

    def _on_sort_direction_clicked(self, _button: Adw.SplitButton) -> None:
        """Toggle sort direction and update icon."""
        self._sort_ascending = not self._sort_ascending
        self._sort_btn.set_icon_name(
            "view-sort-ascending-symbolic"
            if self._sort_ascending
            else "view-sort-descending-symbolic"
        )
        self._sorter.changed(Gtk.SorterChange.DIFFERENT)
        self._rebuild_listbox()

    def _on_sort_by_changed(
        self, action: Gio.SimpleAction, value: GLib.Variant,
    ) -> None:
        """Handle sort field selection from the dropdown menu."""
        action.set_state(value)
        self._sort_key = value.get_string()
        self._sorter.changed(Gtk.SorterChange.DIFFERENT)
        self._rebuild_listbox()

    def _on_search_btn_clicked(self, _button: Adw.SplitButton) -> None:
        """Toggle the search bar when the split button is clicked."""
        enabled = self._search_bar.get_search_mode()
        self._search_bar.set_search_mode(not enabled)

    def _on_page_shown(self, _page: Adw.NavigationPage) -> None:
        """Rebuild remote listbox if it was dirtied while off-screen."""
        if self._remote_dirty:
            self._remote_dirty = False
            self._rebuild_remote_listbox()

    def _on_search_mode_changed(
        self, search_bar: Gtk.SearchBar, _pspec: GObject.ParamSpec,
    ) -> None:
        """Focus the search entry when search mode is enabled; clear remote on close."""
        if search_bar.get_search_mode():
            self._search_entry.grab_focus()
        else:
            self._clear_remote_results()

    def _setup_actions(self) -> None:
        """Register page-level actions."""
        group = Gio.SimpleActionGroup()

        download_action = Gio.SimpleAction.new("download", None)
        download_action.connect("activate", self._on_download)
        group.add_action(download_action)

        upload_action = Gio.SimpleAction.new("upload", None)
        upload_action.connect("activate", self._on_upload)
        group.add_action(upload_action)

        scan_action = Gio.SimpleAction.new("scan-library", None)
        scan_action.connect("activate", self._on_scan_library)
        group.add_action(scan_action)

        filter_action = Gio.SimpleAction.new_stateful(
            "filter-status",
            GLib.VariantType.new("s"),
            GLib.Variant.new_string("all"),
        )
        filter_action.connect("change-state", self._on_filter_status_changed)
        group.add_action(filter_action)

        sort_action = Gio.SimpleAction.new_stateful(
            "sort-by",
            GLib.VariantType.new("s"),
            GLib.Variant.new_string("title"),
        )
        sort_action.connect("change-state", self._on_sort_by_changed)
        group.add_action(sort_action)

        self.insert_action_group("page", group)

    # -- Status filter ---------------------------------------------------------

    @staticmethod
    def _fuzzy_match(text: str, query: str) -> bool:
        """Check if all *query* chars appear in *text* in order (case-insensitive)."""
        text_lower = text.lower()
        idx = 0
        for ch in query:
            idx = text_lower.find(ch, idx)
            if idx == -1:
                return False
            idx += 1
        return True

    def _search_filter_func(self, item: ShowObject) -> bool:
        """Return True if *item* matches the current fuzzy search query."""
        if not self._search_query:
            return True
        query = self._search_query.lower()
        if self._fuzzy_match(item.title, query):
            return True
        for alias in item.get_data().get("aliases", []):
            if self._fuzzy_match(alias, query):
                return True
        return False

    def _status_filter_func(self, item: ShowObject) -> bool:
        """Return True if *item* passes the current status filter."""
        if self._current_status is None:
            return True
        return item.status == str(self._current_status)

    def _on_filter_status_changed(
        self, action: Gio.SimpleAction, value: GLib.Variant,
    ) -> None:
        """Handle status filter menu selection."""
        action.set_state(value)
        choice = value.get_string()

        if choice == "all":
            self._current_status = None
            self._header_title.set_title("Library")
            self._empty_page.set_description("")
        else:
            self._current_status = choice
            status_name = self._statuses.get(
                int(choice) if choice.lstrip("-").isdigit() else choice, choice,
            )
            self._header_title.set_title(f"Library \u2014 {status_name}")
            self._empty_page.set_description(
                f"No shows with status \u201c{status_name}\u201d"
            )

        self._status_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._scroll_to_top()

    def _scroll_to_top(self) -> None:
        """Scroll the list view back to the top after layout settles."""
        adj = self._listbox.get_adjustment()
        if adj is not None:
            adj.set_value(0)

    def _on_filter_items_changed(self, *_args: Any) -> None:
        """Rebuild the listbox rows from the filter model."""
        self._rebuild_listbox()

    def _rebuild_listbox(self) -> None:
        """Clear and repopulate the listbox from the filter model."""
        # Remove all existing rows
        while True:
            row = self._listbox.get_row_at_index(0)
            if row is None:
                break
            self._listbox.remove(row)

        n = self._filter_model.get_n_items()
        for i in range(n):
            show = self._filter_model.get_item(i)
            if isinstance(show, ShowObject):
                self._listbox.append(self._create_show_row(show))

        search_active = self._search_bar.get_search_mode()
        if n == 0 and not search_active:
            self._content_stack.set_visible_child_name("empty")
        else:
            self._content_stack.set_visible_child_name("list")
            self._list_group.set_visible(n > 0 or not search_active)

    # -- Row construction ------------------------------------------------------

    def _format_subtitle(self, show: ShowObject) -> str:
        """Build subtitle text from progress and score."""
        parts: list[str] = []

        if self._has_progress:
            if show.total > 0:
                parts.append(f"{show.progress}/{show.total}")
            else:
                parts.append(f"{show.progress}/?")

        if self._can_score and show.score > 0:
            score_step = self._mediainfo.get("score_step", 1)
            if isinstance(score_step, float) and score_step != int(score_step):
                parts.append(f"\u2605 {show.score:.1f}")
            else:
                parts.append(f"\u2605 {int(show.score)}")

        return " \u00b7 ".join(parts)

    def _create_show_row(self, show: ShowObject) -> Adw.ActionRow:
        """Create an ActionRow for a show."""
        row = Adw.ActionRow(
            title=GLib.markup_escape_text(show.title),
            subtitle=self._format_subtitle(show),
            activatable=True,
        )
        row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        row._show_obj = show  # type: ignore[attr-defined]

        # Live-update on property changes
        handler_id = show.connect("notify", self._on_show_prop_changed, row)
        row._handler_id = handler_id  # type: ignore[attr-defined]

        return row

    def _on_show_prop_changed(
        self,
        show: ShowObject,
        _pspec: GObject.ParamSpec,
        row: Adw.ActionRow,
    ) -> None:
        """Re-render row when a show property changes."""
        row.set_title(GLib.markup_escape_text(show.title))
        row.set_subtitle(self._format_subtitle(show))

    # -- Data population -------------------------------------------------------

    def _populate_store(self) -> None:
        """Fill the store from the engine's full show list."""
        # Block the items-changed handler to avoid O(n²) rebuilds
        self._filter_model.handler_block(self._filter_signal_id)
        self._store.remove_all()
        for show_data in self._engine.get_list():
            self._store.append(ShowObject.from_dict(show_data))
        self._filter_model.handler_unblock(self._filter_signal_id)
        self._rebuild_listbox()

    # -- Search ----------------------------------------------------------------

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Apply local filter and schedule debounced remote search."""
        query = entry.get_text().strip()
        self._search_query = query.lower() if query else ""
        self._search_filter.changed(Gtk.FilterChange.DIFFERENT)

        # Cancel pending remote search
        if self._remote_search_timeout_id:
            GLib.source_remove(self._remote_search_timeout_id)
            self._remote_search_timeout_id = 0

        if len(query) >= 3:
            self._remote_search_timeout_id = GLib.timeout_add(
                500, self._trigger_remote_search,
            )
        else:
            self._clear_remote_results()

    def _trigger_remote_search(self) -> bool:
        """GLib timeout callback: launch remote search in background thread."""
        self._remote_search_timeout_id = 0
        query = self._search_entry.get_text().strip()
        if len(query) < 3:
            return GLib.SOURCE_REMOVE

        # Show a "Searching..." placeholder
        self._clear_remote_listbox()
        spinner_row = Adw.ActionRow(title="Searching\u2026")
        spinner = Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER)
        spinner_row.add_prefix(spinner)
        self._remote_listbox.append(spinner_row)
        self._remote_group.set_visible(True)

        thread = threading.Thread(
            target=self._do_remote_search, args=(query,), daemon=True,
        )
        thread.start()
        return GLib.SOURCE_REMOVE

    def _do_remote_search(self, query: str) -> None:
        """Execute engine.search() in a background thread."""
        try:
            results = self._engine.search(query)
            GLib.idle_add(self._on_remote_search_complete, results)
        except Exception as e:
            GLib.idle_add(self._on_remote_search_error, str(e))

    def _on_remote_search_complete(self, results: list[dict[str, Any]]) -> bool:
        """Populate the remote listbox with search results."""
        from trackma.ui.gtk4.search import SearchResultObject

        self._remote_results = [
            SearchResultObject(data=d) for d in results
        ]
        self._rebuild_remote_listbox()
        return GLib.SOURCE_REMOVE

    def _on_remote_search_error(self, message: str) -> bool:
        """Hide remote section and show error toast."""
        self._remote_group.set_visible(False)
        self._show_toast(f"Search failed: {message}")
        return GLib.SOURCE_REMOVE

    def _rebuild_remote_listbox(self) -> None:
        """Clear and repopulate the remote listbox, excluding local shows."""
        self._clear_remote_listbox()

        local_ids: set[int] = set()
        for i in range(self._store.get_n_items()):
            obj = self._store.get_item(i)
            if isinstance(obj, ShowObject):
                local_ids.add(obj.show_id)

        visible_count = 0
        for result in self._remote_results:
            if result.get_data().get("id", 0) in local_ids:
                continue
            self._remote_listbox.append(self._create_remote_row(result))
            visible_count += 1

        self._remote_group.set_visible(visible_count > 0)

    def _create_remote_row(self, result: Any) -> Adw.ActionRow:
        """Create an ActionRow for a remote search result."""
        row = Adw.ActionRow(
            title=GLib.markup_escape_text(result.title),
            subtitle=result.subtitle,
            activatable=True,
        )
        row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        row._result_obj = result  # type: ignore[attr-defined]
        return row

    def _clear_remote_listbox(self) -> None:
        """Remove all rows from the remote listbox."""
        while True:
            row = self._remote_listbox.get_row_at_index(0)
            if row is None:
                break
            self._remote_listbox.remove(row)

    def _clear_remote_results(self) -> None:
        """Hide remote group, clear results, cancel pending timeout."""
        if self._remote_search_timeout_id:
            GLib.source_remove(self._remote_search_timeout_id)
            self._remote_search_timeout_id = 0
        self._remote_results = []
        self._remote_dirty = False
        self._clear_remote_listbox()
        self._remote_group.set_visible(False)

    def _on_remote_row_activated(
        self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow,
    ) -> None:
        """Push SearchDetailPage for the activated remote result."""
        result = getattr(row, "_result_obj", None)
        if result is None:
            return

        nav_view = self._find_nav_view()
        if nav_view is None:
            logger.warning("No AdwNavigationView found for detail push")
            return

        from trackma.ui.gtk4.search import SearchDetailPage

        detail_page = SearchDetailPage(
            engine=self._engine,
            show_data=result.get_data(),
        )
        nav_view.push(detail_page)

    # -- Row activation --------------------------------------------------------

    def _on_row_activated(
        self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow,
    ) -> None:
        """Open the detail page for the activated show."""
        show_obj: ShowObject | None = getattr(row, "_show_obj", None)
        if show_obj is None:
            return

        show_data = show_obj.get_data()
        if not show_data:
            return

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
        self._engine.connect_signal("tracker_state", self._on_tracker_state)
        self._engine.connect_signal("prompt_for_update", self._on_prompt_for_update)
        self._engine.connect_signal("prompt_for_add", self._on_prompt_for_add)

        # Set initial tracker state if tracker is already running
        status = self._engine.tracker_status()
        if status is not None:
            self._handle_tracker_state(status)

    def _find_show_object(self, show_id: int) -> tuple[int, ShowObject] | None:
        """Find a ShowObject by id in the store.

        Returns:
            Tuple of (position, show_object) or None.
        """
        for i in range(self._store.get_n_items()):
            obj = self._store.get_item(i)
            if isinstance(obj, ShowObject) and obj.show_id == show_id:
                return i, obj
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
            _pos, obj = result
            obj.update_from_dict(show)
        return GLib.SOURCE_REMOVE

    def _on_status_changed(self, show: dict[str, Any], _old_status: str | int) -> None:
        """Engine callback for status changes; marshals to main thread."""
        GLib.idle_add(self._handle_status_changed, show)

    def _handle_status_changed(self, show: dict[str, Any]) -> bool:
        """Update a show in-place; the status filter handles visibility."""
        result = self._find_show_object(show.get("id", 0))
        if result is not None:
            _pos, obj = result
            obj.update_from_dict(show)
            self._status_filter.changed(Gtk.FilterChange.DIFFERENT)
        return GLib.SOURCE_REMOVE

    def _on_show_added(self, show: dict[str, Any]) -> None:
        """Engine callback for show additions; marshals to main thread."""
        GLib.idle_add(self._handle_show_added, show)

    def _handle_show_added(self, show: dict[str, Any]) -> bool:
        """Append a new show to the store and update remote results."""
        self._store.append(ShowObject.from_dict(show))
        if self._remote_results:
            self._remote_dirty = True
        return GLib.SOURCE_REMOVE

    def _on_show_deleted(self, show: dict[str, Any]) -> None:
        """Engine callback for show deletions; marshals to main thread."""
        GLib.idle_add(self._handle_show_deleted, show)

    def _handle_show_deleted(self, show: dict[str, Any]) -> bool:
        """Remove a show from the store and update remote results."""
        result = self._find_show_object(show.get("id", 0))
        if result is not None:
            pos, _obj = result
            self._store.remove(pos)
        if self._remote_results:
            self._remote_dirty = True
        return GLib.SOURCE_REMOVE

    # -- Tracker ---------------------------------------------------------------

    def _on_tracker_state(self, status: dict[str, Any]) -> None:
        """Engine callback for tracker state changes; marshals to main thread."""
        logger.debug("tracker_state signal received: %s", status)
        GLib.idle_add(self._handle_tracker_state, status)

    def _handle_tracker_state(self, status: dict[str, Any]) -> bool:
        """Update the tracker banner from a tracker status dict."""
        state = status.get("state")
        if state is None:
            self._tracker_banner.set_revealed(False)
            return GLib.SOURCE_REMOVE

        show_tuple = status.get("show", (None, None))
        timer = status.get("timer", 0)
        paused = status.get("paused", False)

        if state == TrackerState.NOVIDEO:
            self._tracker_banner.set_title("Tracker: Listening")
        elif state == TrackerState.PLAYING:
            show, episode = show_tuple if show_tuple else (None, None)
            title = show.get("title", "Unknown") if show else "Unknown"
            minutes, seconds = divmod(timer, 60)
            pause_indicator = " \u23f8" if paused else ""
            prefix = "Paused" if paused else "Playing"
            self._tracker_banner.set_title(
                f"Tracker: {prefix} \u2014 {title} Ep. {episode} "
                f"\u2014 {minutes}:{seconds:02d}{pause_indicator}"
            )
        elif state == TrackerState.UNRECOGNIZED:
            self._tracker_banner.set_title("Tracker: Unrecognized file")
        elif state == TrackerState.NOT_FOUND:
            show, episode = show_tuple if show_tuple else (None, None)
            title = show.get("title", "Unknown") if show else "Unknown"
            self._tracker_banner.set_title(
                f"Tracker: {title} not in list"
            )
        elif state == TrackerState.IGNORED:
            show, episode = show_tuple if show_tuple else (None, None)
            title = show.get("title", "Unknown") if show else "Unknown"
            self._tracker_banner.set_title(
                f"Tracker: Ignored \u2014 {title} Ep. {episode}"
            )

        self._tracker_banner.set_revealed(True)
        return GLib.SOURCE_REMOVE

    def _on_prompt_for_update(self, show: dict[str, Any], episode: int) -> None:
        """Engine callback for tracker update prompt; marshals to main thread."""
        logger.debug("prompt_for_update signal: %s ep %d", show.get("title"), episode)
        GLib.idle_add(self._handle_prompt_for_update, show, episode)

    def _handle_prompt_for_update(
        self, show: dict[str, Any], episode: int,
    ) -> bool:
        """Show a dialog asking the user to confirm an episode update."""
        if self._prompt_active:
            return GLib.SOURCE_REMOVE

        self._prompt_active = True
        title = show.get("title", "Unknown")
        dialog = Adw.AlertDialog(
            heading="Update progress?",
            body=f"Update {title} to episode {episode}?",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("update", "Update")
        dialog.set_response_appearance("update", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("update")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_update_dialog_response, show, episode)

        parent = self.get_root()
        dialog.present(parent if isinstance(parent, Gtk.Widget) else None)
        return GLib.SOURCE_REMOVE

    def _on_update_dialog_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        show: dict[str, Any],
        episode: int,
    ) -> None:
        """Handle the update prompt dialog response."""
        self._prompt_active = False
        if response == "update":
            show_id = show.get("id", 0)

            def do_update() -> None:
                try:
                    self._engine.set_episode(show_id, episode)
                except Exception as e:
                    GLib.idle_add(self._show_toast, f"Update failed: {e}")

            threading.Thread(target=do_update, daemon=True).start()

    def _on_prompt_for_add(self, show: dict[str, Any], episode: int) -> None:
        """Engine callback for tracker add prompt; marshals to main thread."""
        logger.debug("prompt_for_add signal: %s ep %d", show.get("title"), episode)
        GLib.idle_add(self._handle_prompt_for_add, show, episode)

    def _handle_prompt_for_add(
        self, show: dict[str, Any], _episode: int,
    ) -> bool:
        """Show a dialog asking the user to add a show to their list."""
        if self._prompt_active:
            return GLib.SOURCE_REMOVE

        self._prompt_active = True
        title = show.get("title", "Unknown")
        dialog = Adw.AlertDialog(
            heading="Add show?",
            body=f"Add {title} to your list?",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("add")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_add_dialog_response, show)

        parent = self.get_root()
        dialog.present(parent if isinstance(parent, Gtk.Widget) else None)
        return GLib.SOURCE_REMOVE

    def _on_add_dialog_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        show: dict[str, Any],
    ) -> None:
        """Handle the add prompt dialog response."""
        self._prompt_active = False
        if response == "add":

            def do_add() -> None:
                try:
                    self._engine.add_show(show)
                except Exception as e:
                    GLib.idle_add(self._show_toast, f"Add failed: {e}")

            threading.Thread(target=do_add, daemon=True).start()

    # -- Sync actions ----------------------------------------------------------

    def _on_download(self, _action: Gio.SimpleAction, _param: Any) -> None:
        """Action handler for ``page.download``."""
        self._run_in_thread(self._do_download)

    def _on_upload(self, _action: Gio.SimpleAction, _param: Any) -> None:
        """Action handler for ``page.upload``."""
        self._run_in_thread(self._do_upload)

    def _on_scan_library(self, _action: Gio.SimpleAction, _param: Any) -> None:
        """Action handler for ``page.scan-library``."""
        self._run_in_thread(self._do_scan_library)

    def _do_download(self) -> None:
        """Download the remote list in a background thread."""
        try:
            self._engine.list_download()
            GLib.idle_add(self._on_download_complete)
        except Exception as e:
            GLib.idle_add(self._show_toast, f"Download failed: {e}")

    def _on_download_complete(self) -> bool:
        """Repopulate the store after a successful download."""
        self._populate_store()
        self._show_toast("List downloaded")
        return GLib.SOURCE_REMOVE

    def _do_scan_library(self) -> None:
        """Scan the library in a background thread."""
        try:
            self._engine.scan_library()
            GLib.idle_add(self._show_toast, "Library scan complete")
        except Exception as e:
            GLib.idle_add(self._show_toast, f"Library scan failed: {e}")

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
