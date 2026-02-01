"""
Trackma GTK4 Search Components.

Provides ``SearchResultObject`` for wrapping remote search results and
``SearchDetailPage`` for viewing details and adding a show to the user's
list. Remote search is triggered from ``ShowListPage`` in ``show_view.py``.

All interaction with the Trackma core happens exclusively through
Engine methods.
"""

from __future__ import annotations

import datetime
import html
import logging
import re
import threading
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk

if TYPE_CHECKING:
    from trackma.engine import Engine

from trackma.ui.gtk4.show_detail import IMAGE_HEIGHT, IMAGE_WIDTH, load_show_image

logger = logging.getLogger(__name__)


class SearchResultObject(GObject.Object):
    """GObject wrapper for a search result show dictionary.

    Args:
        data: Show dictionary from engine.search().
    """

    __gtype_name__ = "TrackmaSearchResultObject"

    title = GObject.Property(type=str, default="")  # type: ignore[assignment]
    show_type = GObject.Property(type=str, default="")  # type: ignore[assignment]
    total = GObject.Property(type=int, default=0)  # type: ignore[assignment]
    score = GObject.Property(type=float, default=0.0)  # type: ignore[assignment]
    subtitle = GObject.Property(type=str, default="")  # type: ignore[assignment]

    def __init__(self, data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._data = data
        self.title = data.get("title", "")
        self.total = data.get("total", 0)

        # Build subtitle from selected extra fields
        extra = data.get("extra", [])
        extra_dict: dict[str, Any] = {}
        for item in extra:
            if len(item) >= 2:
                extra_dict[item[0]] = item[1]

        parts: list[str] = []
        # Show type (TV, OVA, Movie, etc.)
        show_type = extra_dict.get("Type")
        if show_type and isinstance(show_type, str):
            self.show_type = show_type.upper()
            parts.append(self.show_type)
        # Total episodes
        if self.total > 0:
            parts.append(f"{self.total} ep.")
        # Airing status
        for key in ("Status", "Airing status"):
            val = extra_dict.get(key)
            if val and isinstance(val, str):
                parts.append(val)
                break
        # Mean score
        mean = extra_dict.get("Mean score") or extra_dict.get("Average score")
        if mean is not None:
            try:
                self.score = float(str(mean).rstrip("%"))
            except (ValueError, TypeError):
                pass
            parts.append(f"Score: {mean}")

        self.subtitle = " · ".join(parts)

    def get_data(self) -> dict[str, Any]:
        """Return the underlying show dictionary."""
        return self._data


def _clean_html(text: str) -> str:
    """Strip HTML tags and decode entities from API text.

    Converts ``<br>`` sequences to newlines and removes all other tags.
    """
    # Multiple <br> → paragraph break, single <br> → line break
    text = re.sub(r"(<br\s*/?\s*>\s*){2,}", "\n\n", text)
    text = re.sub(r"<br\s*/?\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


class SearchDetailPage(Adw.NavigationPage):
    """Detail page for a search result, with editable fields and Add button.

    Mirrors the layout of ``ShowDetailPage`` but does not auto-save.
    Instead, all field values are collected in memory and applied in
    a single background operation when the user clicks Add.

    The engine call order is: ``add_show`` → ``set_episode`` →
    ``set_score`` → ``set_dates`` → ``set_tags`` → ``set_status``
    (status last so the user's explicit choice overrides any
    auto-status-change triggered by episode).

    Args:
        engine: Started Trackma Engine instance.
        show_data: Show dictionary from engine.search().
        **kwargs: Forwarded to ``Adw.NavigationPage``.
    """

    __gtype_name__ = "TrackmaSearchDetailPage"

    def __init__(self, engine: Engine, show_data: dict[str, Any], **kwargs: Any) -> None:
        title = show_data.get("title", "")
        super().__init__(title=title, **kwargs)
        self._engine = engine
        self._show = show_data
        self._mediainfo: dict[str, Any] = engine.mediainfo

        # Parse extra into a dict for easy access
        self._extra: dict[str, Any] = {}
        for item in show_data.get("extra", []):
            if len(item) >= 2:
                self._extra[item[0]] = item[1]

        # Pending date values (collected from calendar popovers)
        self._pending_start_date: datetime.date | None = None
        self._pending_finish_date: datetime.date | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the widget tree."""
        toolbar = Adw.ToolbarView()

        # Header bar with Add button
        header = Adw.HeaderBar()

        self._add_btn = Gtk.Button(label="Add")
        self._add_btn.add_css_class("suggested-action")
        self._add_btn.connect("clicked", self._on_add_clicked)
        header.pack_end(self._add_btn)

        toolbar.add_top_bar(header)

        # Scrollable content
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vexpand=True,
        )

        clamp = Adw.Clamp(maximum_size=600)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
        )
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self._build_image(box)
        self._build_actions_group(box)
        self._build_progress_group(box)
        self._build_dates_group(box)
        self._build_tags_group(box)
        self._build_synopsis_section(box)
        self._build_details_group(box)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        toolbar.set_content(scrolled)
        self.set_child(toolbar)

    def _build_image(self, parent: Gtk.Box) -> None:
        """Build a centered cover image widget."""
        self._picture = Gtk.Picture(
            content_fit=Gtk.ContentFit.CONTAIN,
            can_shrink=True,
            halign=Gtk.Align.CENTER,
        )
        self._picture.set_size_request(IMAGE_WIDTH, IMAGE_HEIGHT)

        api_info = self._engine.api_info
        mediatype = api_info.get("mediatype", "")
        load_show_image(self._show, self._picture, api_info, mediatype)

        parent.append(self._picture)

    def _build_actions_group(self, parent: Gtk.Box) -> None:
        """Build Open on Website action row if show has a URL."""
        url = self._show.get("url", "")
        if not url:
            return

        group = Adw.PreferencesGroup()
        website_row = Adw.ActionRow(
            title="Open on Website",
            subtitle=url,
            activatable=True,
        )
        website_row.add_prefix(
            Gtk.Image(icon_name="user-home-symbolic")
        )
        website_row.add_suffix(
            Gtk.Image(icon_name="external-link-symbolic")
        )
        website_row.connect("activated", self._on_open_url)
        group.add(website_row)
        parent.append(group)

    def _on_open_url(self, _row: Adw.ActionRow) -> None:
        """Open the show's URL in the default browser."""
        url = self._show.get("url", "")
        if url:
            launcher = Gtk.UriLauncher(uri=url)
            window = self.get_root()
            launcher.launch(
                window if isinstance(window, Gtk.Window) else None,
                None, None, None,
            )

    # -- Editable field groups (mirror ShowDetailPage) --------------------------

    def _build_progress_group(self, parent: Gtk.Box) -> None:
        """Build the Progress preferences group with episode, status, score."""
        group = Adw.PreferencesGroup(title="Progress")

        has_progress = self._mediainfo.get("has_progress", True)
        can_status = self._mediainfo.get("can_status", False)
        can_score = self._mediainfo.get("can_score", False)

        # Episode spin row
        if has_progress:
            total = self._show.get("total", 0)
            upper = float(total) if total > 0 else 9999.0
            adjustment = Gtk.Adjustment(
                value=0,
                lower=0,
                upper=upper,
                step_increment=1,
                page_increment=1,
            )
            self._episode_row = Adw.SpinRow(
                title="Episode",
                adjustment=adjustment,
            )
            group.add(self._episode_row)

        # Status combo row
        if can_status:
            statuses_dict = self._mediainfo.get("statuses_dict", {})
            self._status_keys: list[int | str] = list(statuses_dict.keys())
            status_names = list(statuses_dict.values())

            string_list = Gtk.StringList()
            for name in status_names:
                string_list.append(name)

            self._status_row = Adw.ComboRow(
                title="Status",
                model=string_list,
            )

            # Default to first "start" status
            statuses_start = self._mediainfo.get("statuses_start", [])
            default = statuses_start[0] if statuses_start else self._status_keys[0]
            if default in self._status_keys:
                self._status_row.set_selected(self._status_keys.index(default))

            group.add(self._status_row)

        # Score spin row
        if can_score:
            score_max = float(self._mediainfo.get("score_max", 10))
            score_step = float(self._mediainfo.get("score_step", 1))
            digits = 0
            if score_step != int(score_step):
                s = str(score_step)
                if "." in s:
                    digits = len(s.split(".")[1])

            adjustment = Gtk.Adjustment(
                value=0,
                lower=0,
                upper=score_max,
                step_increment=score_step,
                page_increment=score_step,
            )
            self._score_row = Adw.SpinRow(
                title="Score",
                adjustment=adjustment,
                digits=digits,
            )
            group.add(self._score_row)

        parent.append(group)

    def _build_dates_group(self, parent: Gtk.Box) -> None:
        """Build the Dates preferences group with calendar popovers."""
        if not self._mediainfo.get("can_date", False):
            return

        group = Adw.PreferencesGroup(title="Dates")

        self._start_date_row = self._make_date_row("Started", "start")
        group.add(self._start_date_row)

        self._finish_date_row = self._make_date_row("Finished", "finish")
        group.add(self._finish_date_row)

        parent.append(group)

    def _make_date_row(self, title: str, date_key: str) -> Adw.ActionRow:
        """Create a date row with a calendar popover button."""
        row = Adw.ActionRow(title=title)
        row.set_subtitle("Not set")

        calendar = Gtk.Calendar()
        calendar.connect("day-selected", self._on_date_selected, row, date_key)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.add_css_class("destructive-action")
        clear_btn.set_margin_top(6)

        cal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cal_box.append(calendar)
        cal_box.append(clear_btn)

        popover = Gtk.Popover(child=cal_box)
        clear_btn.connect("clicked", self._on_date_clear, row, popover, date_key)

        menu_btn = Gtk.MenuButton(
            icon_name="x-office-calendar-symbolic",
            popover=popover,
            valign=Gtk.Align.CENTER,
        )

        row.add_suffix(menu_btn)
        return row

    def _on_date_selected(
        self, calendar: Gtk.Calendar, row: Adw.ActionRow, date_key: str,
    ) -> None:
        """Store the selected date in memory."""
        gdt = calendar.get_date()
        date = datetime.date(gdt.get_year(), gdt.get_month(), gdt.get_day_of_month())
        row.set_subtitle(str(date))
        if date_key == "start":
            self._pending_start_date = date
        else:
            self._pending_finish_date = date

    def _on_date_clear(
        self,
        _button: Gtk.Button,
        row: Adw.ActionRow,
        popover: Gtk.Popover,
        date_key: str,
    ) -> None:
        """Clear a pending date."""
        popover.popdown()
        row.set_subtitle("Not set")
        if date_key == "start":
            self._pending_start_date = None
        else:
            self._pending_finish_date = None

    def _build_tags_group(self, parent: Gtk.Box) -> None:
        """Build the Tags preferences group."""
        if not self._mediainfo.get("can_tag", False):
            return

        group = Adw.PreferencesGroup(title="Tags")

        self._tags_row = Adw.EntryRow(title="Tags")
        group.add(self._tags_row)

        parent.append(group)

    # -- Read-only info groups -------------------------------------------------

    def _build_details_group(self, parent: Gtk.Box) -> None:
        """Build the Details preferences group with metadata rows."""
        group = Adw.PreferencesGroup(title="Details")
        has_rows = False

        # Total episodes as first row
        total = self._show.get("total", 0)
        total_text = str(total) if total > 0 else "Unknown"
        group.add(Adw.ActionRow(title="Total Episodes", subtitle=total_text))
        has_rows = True

        skip_keys = {"Synopsis", "Description"}
        for label, value in self._show.get("extra", []):
            if label in skip_keys:
                continue
            if value is None or value == "" or value == []:
                continue

            if isinstance(value, list):
                value = ", ".join(str(v) for v in value if v)
                if not value:
                    continue

            text = _clean_html(str(value))
            if not text:
                continue

            row = Adw.ActionRow()
            row.set_use_markup(False)
            row.set_title(str(label))
            row.set_subtitle(text)
            row.set_subtitle_lines(3)
            group.add(row)
            has_rows = True

        if has_rows:
            parent.append(group)

    def _build_synopsis_section(self, parent: Gtk.Box) -> None:
        """Build the Synopsis section if available."""
        synopsis = self._extra.get("Synopsis") or self._extra.get("Description")
        if not synopsis or not isinstance(synopsis, str):
            return

        text = _clean_html(synopsis)
        if not text:
            return

        group = Adw.PreferencesGroup(title="Synopsis")

        label = Gtk.Label(
            label=text,
            xalign=0,
            wrap=True,
            selectable=True,
        )
        label.add_css_class("body")
        label.set_margin_start(12)
        label.set_margin_end(12)
        label.set_margin_top(8)
        label.set_margin_bottom(8)

        group.add(label)
        parent.append(group)

    # -- Add action: collect all values and apply in background ----------------

    def _on_add_clicked(self, _button: Gtk.Button) -> None:
        """Collect field values and add the show in a background thread."""
        if getattr(self, "_adding", False):
            return
        self._adding = True

        # Collect all pending values from the UI
        values: dict[str, Any] = {}

        # Status
        if hasattr(self, "_status_row") and hasattr(self, "_status_keys"):
            idx = self._status_row.get_selected()
            if 0 <= idx < len(self._status_keys):
                values["status"] = self._status_keys[idx]

        # Episode
        if hasattr(self, "_episode_row"):
            ep = int(self._episode_row.get_value())
            if ep > 0:
                values["episode"] = ep

        # Score (only if user set a non-zero value)
        if hasattr(self, "_score_row"):
            score = self._score_row.get_value()
            score_step = self._mediainfo.get("score_step", 1)
            if score >= float(score_step):
                # Round to score_step to avoid floating-point precision
                # issues with the engine's Decimal modulo validation
                if isinstance(score_step, int):
                    values["score"] = int(round(score))
                else:
                    step_str = str(score_step)
                    decimals = len(step_str.split(".")[1]) if "." in step_str else 0
                    values["score"] = round(round(score / score_step) * score_step, decimals)

        # Dates
        if self._pending_start_date is not None:
            values["start_date"] = self._pending_start_date
        if self._pending_finish_date is not None:
            values["finish_date"] = self._pending_finish_date

        # Tags
        if hasattr(self, "_tags_row"):
            tags = self._tags_row.get_text().strip()
            if tags:
                values["tags"] = tags

        thread = threading.Thread(
            target=self._do_add_show, args=(values,), daemon=True,
        )
        thread.start()

    def _do_add_show(self, values: dict[str, Any]) -> None:
        """Add the show and apply all field values in a background thread.

        Call order: add_show → set_episode → set_score → set_dates →
        set_tags → set_status. Status is set last so the user's explicit
        choice overrides any auto-status-change from set_episode.
        """
        try:
            status = values.get("status")
            self._engine.add_show(self._show, status)

            # After add_show, the show has an ID in the local list
            show_id = self._show.get("id", 0)

            if "episode" in values:
                try:
                    self._engine.set_episode(show_id, values["episode"])
                except Exception as e:
                    logger.warning("Failed to set episode on add: %s", e)

            if "score" in values:
                try:
                    self._engine.set_score(show_id, values["score"])
                except Exception as e:
                    logger.warning("Failed to set score on add: %s", e)

            if "start_date" in values or "finish_date" in values:
                try:
                    self._engine.set_dates(
                        show_id,
                        start_date=values.get("start_date"),
                        finish_date=values.get("finish_date"),
                    )
                except Exception as e:
                    logger.warning("Failed to set dates on add: %s", e)

            if "tags" in values:
                try:
                    self._engine.set_tags(show_id, values["tags"])
                except Exception as e:
                    logger.warning("Failed to set tags on add: %s", e)

            # Re-apply status only if episode/score auto-changed it
            if status is not None and "episode" in values:
                try:
                    current = self._engine.get_show_info(showid=show_id)
                    if current is not None and current.get("my_status") != status:
                        self._engine.set_status(show_id, status)
                except Exception as e:
                    logger.warning("Failed to restore status on add: %s", e)

            title = self._show.get("title", "")
            GLib.idle_add(self._on_add_success, title)
        except Exception as e:
            GLib.idle_add(self._on_add_error, str(e))

    def _on_add_success(self, title: str) -> bool:
        """Handle successful add: pop back and show toast."""
        nav = self._find_nav_view()
        if nav is not None:
            nav.pop()
        self._show_toast(f"Added: {title}")
        return GLib.SOURCE_REMOVE

    def _on_add_error(self, message: str) -> bool:
        """Handle add failure: allow retry and show error toast."""
        self._adding = False
        self._show_toast(f"Failed to add: {message}")
        return GLib.SOURCE_REMOVE

    # -- Utilities -------------------------------------------------------------

    def _find_nav_view(self) -> Adw.NavigationView | None:
        """Walk up the widget tree to find the nearest NavigationView."""
        widget: Gtk.Widget | None = self.get_parent()
        while widget is not None:
            if isinstance(widget, Adw.NavigationView):
                return widget
            widget = widget.get_parent()
        return None

    def _show_toast(self, message: str) -> bool:
        """Show a toast via the nearest ToastOverlay ancestor."""
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
