"""
Trackma GTK4 Show Detail Page.

Displays and allows editing of a single show's fields (episode, score,
status, dates, tags) with auto-save to the engine. Pushes onto the main
AdwNavigationView with a back button.

All interaction with the Trackma core happens exclusively through
Engine methods.
"""

from __future__ import annotations

import datetime
import html
import logging
import os
import re
import subprocess
import threading
import urllib.request
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk

from trackma import utils

if TYPE_CHECKING:
    from trackma.engine import Engine

logger = logging.getLogger(__name__)

IMAGE_WIDTH = 200
IMAGE_HEIGHT = 300


def load_show_image(
    show: dict[str, Any],
    picture: Gtk.Picture,
    api_info: dict[str, Any],
    mediatype: str,
) -> None:
    """Load a show's cover image into a Gtk.Picture, with caching.

    Downloads the image in a background thread, caches it to disk,
    and sets the texture on the main thread via ``GLib.idle_add``.
    """
    url = show.get("image") or show.get("image_thumb") or ""
    if not url:
        return

    show_id = show.get("id", 0)
    api_short = api_info.get("shortname", "unknown")
    cache_file = utils.to_cache_path(f"{api_short}_{mediatype}_{show_id}.jpg")

    def _apply_texture(path: str) -> bool:
        try:
            texture = Gdk.Texture.new_from_filename(path)
            picture.set_paintable(texture)
        except Exception as e:
            logger.debug("Failed to load texture from %s: %s", path, e)
        return GLib.SOURCE_REMOVE

    if os.path.isfile(cache_file):
        GLib.idle_add(_apply_texture, cache_file)
        return

    def _download() -> None:
        try:
            cache_dir = os.path.dirname(cache_file)
            os.makedirs(cache_dir, exist_ok=True)

            request = urllib.request.Request(url)
            request.add_header("User-Agent", f"TrackmaImage/{utils.VERSION}")
            data = urllib.request.urlopen(request).read()

            with open(cache_file, "wb") as f:
                f.write(data)

            GLib.idle_add(_apply_texture, cache_file)
        except Exception as e:
            logger.debug("Failed to download image %s: %s", url, e)

    thread = threading.Thread(target=_download, daemon=True)
    thread.start()


class ShowDetailPage(Adw.NavigationPage):
    """Detail/edit page for a single show.

    Displays editable fields (progress, score, status, dates, tags)
    with auto-save to the engine. Read-only metadata is shown in a
    Details group, populated asynchronously via ``get_show_details``.

    Args:
        engine: Started Trackma Engine instance.
        show_data: Show dictionary from the engine.
        **kwargs: Forwarded to ``Adw.NavigationPage``.
    """

    __gtype_name__ = "TrackmaShowDetailPage"

    def __init__(self, engine: Engine, show_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(title=show_data.get("title", ""), **kwargs)
        self._engine = engine
        self._show = show_data
        self._show_id: int = show_data.get("id", 0)
        self._mediainfo: dict[str, Any] = engine.mediainfo
        self._applying = False

        self._build_ui()
        self._fetch_details()

    # -- UI construction -------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the widget tree."""
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        if self._mediainfo.get("can_delete", False):
            delete_btn = Gtk.Button(
                icon_name="user-trash-symbolic",
                tooltip_text="Delete Show",
            )
            delete_btn.add_css_class("flat")
            delete_btn.connect("clicked", lambda _: self._on_delete())
            header.pack_end(delete_btn)
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
        self._build_synopsis_group(box)
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
        mediatype = self._engine.api_info.get("mediatype", "")
        load_show_image(self._show, self._picture, api_info, mediatype)

        parent.append(self._picture)

    def _build_actions_group(self, parent: Gtk.Box) -> None:
        """Build quick-action rows: Play, Open Folder, Open on Website."""
        library = self._engine.library()
        in_library = self._show_id in library

        has_any = False
        group = Adw.PreferencesGroup()

        if in_library:
            next_ep = self._show.get("my_progress", 0) + 1
            total = self._show.get("total", 0)
            if total > 0 and next_ep > total:
                subtitle = "All episodes watched"
                sensitive = False
            else:
                subtitle = f"Episode {next_ep}"
                sensitive = True

            play_row = Adw.ActionRow(
                title="Play Next Episode",
                subtitle=subtitle,
                activatable=sensitive,
            )
            play_row.add_prefix(
                Gtk.Image(icon_name="media-playback-start-symbolic")
            )
            if sensitive:
                play_row.connect("activated", self._on_play_episode)
            group.add(play_row)
            has_any = True

            folder_row = Adw.ActionRow(
                title="Open Folder",
                activatable=True,
            )
            folder_row.add_prefix(
                Gtk.Image(icon_name="folder-open-symbolic")
            )
            folder_row.connect("activated", self._on_open_folder)
            group.add(folder_row)
            has_any = True

        url = self._show.get("url", "")
        if url:
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
            website_row.connect("activated", self._on_open_url_row)
            group.add(website_row)
            has_any = True

        if has_any:
            parent.append(group)

    def _on_play_episode(self, _row: Adw.ActionRow) -> None:
        """Play the next unwatched episode."""
        try:
            args = self._engine.play_episode(self._show)
            if args:
                subprocess.Popen(args)
            else:
                self._show_toast("Episode not found in library")
        except Exception as e:
            self._show_toast(f"Play failed: {e}")

    def _on_open_folder(self, _row: Adw.ActionRow) -> None:
        """Open the show's folder in the file manager."""
        try:
            self._engine.open_show_folder(self._show_id)
        except Exception as e:
            self._show_toast(f"Open folder failed: {e}")

    def _on_open_url_row(self, _row: Adw.ActionRow) -> None:
        """Open the show's URL in the default browser."""
        url = self._show.get("url", "")
        if url:
            launcher = Gtk.UriLauncher(uri=url)
            launcher.launch(self._get_window(), None, None, None)

    def _build_progress_group(self, parent: Gtk.Box) -> None:
        """Build the Progress preferences group."""
        group = Adw.PreferencesGroup(title="Progress")

        has_progress = self._mediainfo.get("has_progress", True)
        can_status = self._mediainfo.get("can_status", False)
        can_score = self._mediainfo.get("can_score", False)

        # Episode spin row
        if has_progress:
            total = self._show.get("total", 0)
            upper = float(total) if total > 0 else 9999.0
            adjustment = Gtk.Adjustment(
                value=float(self._show.get("my_progress", 0)),
                lower=0,
                upper=upper,
                step_increment=1,
                page_increment=1,
            )
            self._episode_row = Adw.SpinRow(
                title="Episode",
                adjustment=adjustment,
            )
            self._episode_row.connect("notify::value", self._on_episode_changed)
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

            # Set current status
            current_status = self._show.get("my_status", 0)
            if current_status in self._status_keys:
                self._status_row.set_selected(self._status_keys.index(current_status))

            self._status_row.connect("notify::selected", self._on_status_changed)
            group.add(self._status_row)

        # Score spin row
        if can_score:
            score_max = float(self._mediainfo.get("score_max", 10))
            score_step = float(self._mediainfo.get("score_step", 1))
            digits = 0
            if score_step != int(score_step):
                # Count decimal places
                s = str(score_step)
                if "." in s:
                    digits = len(s.split(".")[1])

            adjustment = Gtk.Adjustment(
                value=float(self._show.get("my_score", 0)),
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
            self._score_row.connect("notify::value", self._on_score_changed)
            group.add(self._score_row)

        parent.append(group)

    def _build_dates_group(self, parent: Gtk.Box) -> None:
        """Build the Dates preferences group."""
        if not self._mediainfo.get("can_date", False):
            return

        group = Adw.PreferencesGroup(title="Dates")

        self._start_date_row = self._make_date_row(
            "Started", self._show.get("my_start_date"), self._on_start_date_selected,
        )
        group.add(self._start_date_row)

        self._finish_date_row = self._make_date_row(
            "Finished", self._show.get("my_finish_date"), self._on_finish_date_selected,
        )
        group.add(self._finish_date_row)

        parent.append(group)

    def _make_date_row(
        self,
        title: str,
        date_value: datetime.date | None,
        on_selected: Any,
    ) -> Adw.ActionRow:
        """Create a date row with a calendar popover button."""
        row = Adw.ActionRow(title=title)
        row.set_subtitle(str(date_value) if date_value else "Not set")

        calendar = Gtk.Calendar()
        if date_value is not None:
            gdt = GLib.DateTime.new_local(
                date_value.year, date_value.month, date_value.day, 0, 0, 0,
            )
            if gdt is not None:
                calendar.select_day(gdt)
        calendar.connect("day-selected", on_selected, row)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.add_css_class("destructive-action")
        clear_btn.set_margin_top(6)

        cal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cal_box.append(calendar)
        cal_box.append(clear_btn)

        popover = Gtk.Popover(child=cal_box)
        clear_btn.connect("clicked", self._on_date_clear, row, popover, title)

        menu_btn = Gtk.MenuButton(
            icon_name="x-office-calendar-symbolic",
            popover=popover,
            valign=Gtk.Align.CENTER,
        )

        row.add_suffix(menu_btn)
        return row

    def _build_tags_group(self, parent: Gtk.Box) -> None:
        """Build the Tags preferences group."""
        if not self._mediainfo.get("can_tag", False):
            return

        group = Adw.PreferencesGroup(title="Tags")

        self._tags_row = Adw.EntryRow(title="Tags")
        self._tags_row.set_text(self._show.get("my_tags", "") or "")
        self._tags_row.connect("apply", self._on_tags_apply)
        self._tags_row.set_show_apply_button(True)
        group.add(self._tags_row)

        parent.append(group)

    def _build_synopsis_group(self, parent: Gtk.Box) -> None:
        """Build the Synopsis preferences group, populated async."""
        self._synopsis_group = Adw.PreferencesGroup(title="Synopsis")
        self._synopsis_group.set_visible(False)
        parent.append(self._synopsis_group)

    def _build_details_group(self, parent: Gtk.Box) -> None:
        """Build the read-only Details preferences group."""
        self._details_group = Adw.PreferencesGroup(title="Details")

        total = self._show.get("total", 0)
        total_text = str(total) if total > 0 else "Unknown"
        self._details_group.add(
            Adw.ActionRow(title="Total Episodes", subtitle=total_text)
        )

        parent.append(self._details_group)

    # -- Auto-save handlers ----------------------------------------------------

    def _on_episode_changed(self, row: Adw.SpinRow, _pspec: GObject.ParamSpec) -> None:
        """Save episode progress to the engine."""
        if self._applying:
            return
        new_ep = int(row.get_value())
        if new_ep == self._show.get("my_progress", 0):
            return
        try:
            self._engine.set_episode(self._show_id, new_ep)
        except Exception as e:
            self._show_toast(f"Failed to set episode: {e}")
            self._applying = True
            row.set_value(float(self._show.get("my_progress", 0)))
            self._applying = False

    def _on_score_changed(self, row: Adw.SpinRow, _pspec: GObject.ParamSpec) -> None:
        """Save score to the engine."""
        if self._applying:
            return
        raw_score = row.get_value()
        # Round to score_step to avoid floating-point precision
        # issues with the engine's Decimal modulo validation
        score_step = self._mediainfo.get("score_step", 1)
        if isinstance(score_step, int):
            new_score = int(round(raw_score))
        else:
            # Snap to nearest step then round to the step's decimal places
            step_str = str(score_step)
            decimals = len(step_str.split(".")[1]) if "." in step_str else 0
            new_score = round(round(raw_score / score_step) * score_step, decimals)
        if new_score == float(self._show.get("my_score", 0)):
            return
        try:
            self._engine.set_score(self._show_id, new_score)
        except Exception as e:
            self._show_toast(f"Failed to set score: {e}")
            self._applying = True
            row.set_value(float(self._show.get("my_score", 0)))
            self._applying = False

    def _on_status_changed(self, row: Adw.ComboRow, _pspec: GObject.ParamSpec) -> None:
        """Save status to the engine."""
        if self._applying:
            return
        idx = row.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION or idx >= len(self._status_keys):
            return
        new_status = self._status_keys[idx]
        if new_status == self._show.get("my_status", 0):
            return
        try:
            self._engine.set_status(self._show_id, new_status)
        except Exception as e:
            self._show_toast(f"Failed to set status: {e}")
            # Revert
            current = self._show.get("my_status", 0)
            self._applying = True
            if current in self._status_keys:
                row.set_selected(self._status_keys.index(current))
            self._applying = False

    def _on_start_date_selected(
        self, calendar: Gtk.Calendar, row: Adw.ActionRow,
    ) -> None:
        """Save start date to the engine."""
        if self._applying:
            return
        gdt = calendar.get_date()
        date = datetime.date(gdt.get_year(), gdt.get_month(), gdt.get_day_of_month())
        try:
            self._engine.set_dates(self._show_id, start_date=date)
            row.set_subtitle(str(date))
            self._show["my_start_date"] = date
        except Exception as e:
            self._show_toast(f"Failed to set start date: {e}")

    def _on_finish_date_selected(
        self, calendar: Gtk.Calendar, row: Adw.ActionRow,
    ) -> None:
        """Save finish date to the engine."""
        if self._applying:
            return
        gdt = calendar.get_date()
        date = datetime.date(gdt.get_year(), gdt.get_month(), gdt.get_day_of_month())
        try:
            self._engine.set_dates(self._show_id, finish_date=date)
            row.set_subtitle(str(date))
            self._show["my_finish_date"] = date
        except Exception as e:
            self._show_toast(f"Failed to set finish date: {e}")

    def _on_date_clear(
        self,
        _button: Gtk.Button,
        row: Adw.ActionRow,
        popover: Gtk.Popover,
        _title: str,
    ) -> None:
        """Clear a date field."""
        popover.popdown()
        row.set_subtitle("Not set")
        # The engine's set_dates skips None values, so clearing isn't
        # directly supported. We just update the display for now.

    def _on_tags_apply(self, row: Adw.EntryRow) -> None:
        """Save tags to the engine on Enter key."""
        if self._applying:
            return
        new_tags = row.get_text().strip()
        try:
            self._engine.set_tags(self._show_id, new_tags)
            self._show["my_tags"] = new_tags
        except Exception as e:
            self._show_toast(f"Failed to set tags: {e}")

    def _on_delete(self) -> None:
        """Confirm and delete the show."""
        dialog = Adw.AlertDialog(
            heading="Delete Show?",
            body=f"Remove \u201c{self._show.get('title', '')}\u201d from your list?",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response)
        dialog.present(self._get_window())

    def _on_delete_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        """Handle the delete confirmation dialog response."""
        if response != "delete":
            return
        try:
            self._engine.delete_show(self._show)
            # Pop this page from the navigation view
            nav = self._get_nav_view()
            if nav is not None:
                nav.pop()
        except Exception as e:
            self._show_toast(f"Failed to delete: {e}")

    # -- Async details fetch ---------------------------------------------------

    def _fetch_details(self) -> None:
        """Fetch extended show details in a background thread."""
        def worker() -> None:
            try:
                details = self._engine.get_show_details(self._show)
                GLib.idle_add(self._apply_details, details)
            except Exception as e:
                logger.debug("Could not fetch show details: %s", e)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _apply_details(self, details: dict[str, Any]) -> bool:
        """Populate the Synopsis and Details groups with extended metadata."""
        extra = details.get("extra", [])
        synopsis_keys = {"Synopsis", "Description"}

        for label, value in extra:
            if value is None or value == "":
                continue

            if isinstance(value, list):
                value = ", ".join(str(v) for v in value if v)
                if not value:
                    continue

            text = self._clean_html(str(value))
            if not text:
                continue

            if label in synopsis_keys:
                # Show as a wrapping label in the synopsis group
                synopsis_label = Gtk.Label(
                    label=text,
                    xalign=0,
                    wrap=True,
                    selectable=True,
                )
                synopsis_label.add_css_class("body")
                synopsis_label.set_margin_start(12)
                synopsis_label.set_margin_end(12)
                synopsis_label.set_margin_top(8)
                synopsis_label.set_margin_bottom(8)
                self._synopsis_group.add(synopsis_label)
                self._synopsis_group.set_visible(True)
            else:
                row = Adw.ActionRow()
                row.set_use_markup(False)
                row.set_title(str(label))
                row.set_subtitle(text)
                row.set_subtitle_lines(5)
                self._details_group.add(row)

        return GLib.SOURCE_REMOVE

    @staticmethod
    def _clean_html(text: str) -> str:
        """Strip HTML tags and decode entities from API text."""
        text = re.sub(r"(<br\s*/?\s*>\s*){2,}", "\n\n", text)
        text = re.sub(r"<br\s*/?\s*>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        return html.unescape(text).strip()

    # -- Utilities -------------------------------------------------------------

    def _get_window(self) -> Gtk.Window | None:
        """Walk up to find the toplevel window."""
        widget: Gtk.Widget | None = self
        while widget is not None:
            if isinstance(widget, Gtk.Window):
                return widget
            widget = widget.get_parent()
        return None

    def _get_nav_view(self) -> Adw.NavigationView | None:
        """Walk up to find the NavigationView."""
        widget: Gtk.Widget | None = self.get_parent()
        while widget is not None:
            if isinstance(widget, Adw.NavigationView):
                return widget
            widget = widget.get_parent()
        return None

    def _show_toast(self, message: str) -> bool:
        """Show a toast via the nearest ToastOverlay."""
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
