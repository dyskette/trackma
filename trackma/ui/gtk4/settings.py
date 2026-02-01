"""
Trackma GTK4 Settings Dialog.

Presents all Trackma configuration options in an Adw.PreferencesDialog
with four pages: Media, Tracker, Sync, and Automation.

All interaction with the Trackma core happens exclusively through
Engine methods (get_config, set_config, save_config).
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

logger = logging.getLogger(__name__)

# Tracker types available in config
_TRACKER_TYPES = ["auto", "mpris", "inotify", "polling", "plex", "jellyfin", "kodi"]

# Tracker types that use the process regex setting
_PROCESS_TRACKER_TYPES = {"auto", "mpris", "inotify", "polling"}

# Tracker types that use the polling interval setting
_POLLING_TRACKER_TYPES = {"auto", "polling", "plex", "jellyfin", "kodi"}

# Auto-retrieve strategies
_AUTORETRIEVE_OPTIONS = ["always", "days", "off"]

# Auto-send strategies
_AUTOSEND_OPTIONS = ["always", "minutes", "size", "off"]


class SettingsDialog(Adw.PreferencesDialog):
    """Preferences dialog for Trackma configuration.

    Reads config values from the engine on construction and writes
    changed values back on close.

    Args:
        engine: Started Trackma Engine instance.
    """

    __gtype_name__ = "TrackmaSettingsDialog"

    def __init__(self, engine: Engine, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._engine = engine
        self.set_title("Preferences")

        self._build_media_page()
        self._build_tracker_page()
        self._build_sync_page()
        self._build_automation_page()

        self._load()
        self._initial_tracker_config = self._snapshot_tracker_config()

        self.connect("closed", self._on_closed)

    # -- Page builders --------------------------------------------------------

    def _build_media_page(self) -> None:
        """Build the Media page: player command, search dirs, library options."""
        page = Adw.PreferencesPage(title="Media", icon_name="folder-videos-symbolic")

        # Playback group
        playback_group = Adw.PreferencesGroup(title="Playback")
        self._player_row = Adw.EntryRow(title="Player command")
        playback_group.add(self._player_row)
        page.add(playback_group)

        # Search directories group
        searchdir_group = Adw.PreferencesGroup(
            title="Search Directories",
            description="Directories to scan for media files",
        )

        add_btn = Gtk.Button(
            icon_name="list-add-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Add search directory",
        )
        add_btn.add_css_class("flat")
        add_btn.connect("clicked", self._on_add_searchdir)
        searchdir_group.set_header_suffix(add_btn)

        self._searchdir_rows: list[Adw.ActionRow] = []
        self._searchdir_group = searchdir_group

        page.add(searchdir_group)

        # Library options group
        library_group = Adw.PreferencesGroup(title="Library")

        self._autoscan_row = Adw.SwitchRow(title="Auto-scan on startup")
        library_group.add(self._autoscan_row)

        self._fullpath_row = Adw.SwitchRow(
            title="Use full path matching",
            subtitle="Match using the path relative to the search directory",
        )
        library_group.add(self._fullpath_row)

        self._scan_whole_row = Adw.SwitchRow(
            title="Scan whole list",
            subtitle="Also match files for Completed and Dropped shows",
        )
        library_group.add(self._scan_whole_row)

        page.add(library_group)
        self.add(page)

    def _build_tracker_page(self) -> None:
        """Build the Tracker page: general settings and Plex/Jellyfin/Kodi groups."""
        page = Adw.PreferencesPage(title="Tracker", icon_name="media-playback-start-symbolic")

        # General group
        general_group = Adw.PreferencesGroup(title="General")

        self._tracker_enabled_row = Adw.SwitchRow(title="Enable tracker")
        general_group.add(self._tracker_enabled_row)

        self._tracker_type_row = Adw.ComboRow(title="Tracker type")
        self._tracker_type_model = Gtk.StringList.new(_TRACKER_TYPES)
        self._tracker_type_row.set_model(self._tracker_type_model)
        self._tracker_type_row.connect("notify::selected", self._on_tracker_type_changed)
        general_group.add(self._tracker_type_row)

        self._tracker_process_row = Adw.EntryRow(title="Player process regex")
        general_group.add(self._tracker_process_row)

        self._tracker_wait_row = Adw.SpinRow.new_with_range(0, 3600, 10)
        self._tracker_wait_row.set_title("Update wait time (seconds)")
        self._tracker_wait_row.set_subtitle("Seconds to wait before auto-updating")
        general_group.add(self._tracker_wait_row)

        self._tracker_close_row = Adw.SwitchRow(
            title="Wait for player close",
            subtitle="Update only after the player exits",
        )
        general_group.add(self._tracker_close_row)

        self._tracker_prompt_row = Adw.SwitchRow(title="Prompt before updating")
        general_group.add(self._tracker_prompt_row)

        self._tracker_notfound_row = Adw.SwitchRow(title="Prompt for unrecognized files")
        general_group.add(self._tracker_notfound_row)

        self._tracker_ignore_row = Adw.SwitchRow(
            title="Ignore non-next episodes",
            subtitle="Only track the next expected episode",
        )
        general_group.add(self._tracker_ignore_row)

        self._tracker_interval_row = Adw.SpinRow.new_with_range(1, 120, 1)
        self._tracker_interval_row.set_title("Polling interval (seconds)")
        general_group.add(self._tracker_interval_row)

        page.add(general_group)

        # Plex group
        self._plex_group = Adw.PreferencesGroup(title="Plex")
        self._plex_host_row = Adw.EntryRow(title="Host")
        self._plex_port_row = Adw.EntryRow(title="Port")
        self._plex_user_row = Adw.EntryRow(title="Username")
        self._plex_passwd_row = Adw.PasswordEntryRow(title="Password")
        self._plex_ssl_row = Adw.SwitchRow(title="Use SSL")
        self._plex_obey_row = Adw.SwitchRow(
            title="Obey update wait time",
            subtitle="Use configured wait time instead of 80% video duration",
        )
        for row in (
            self._plex_host_row, self._plex_port_row, self._plex_user_row,
            self._plex_passwd_row, self._plex_ssl_row, self._plex_obey_row,
        ):
            self._plex_group.add(row)
        page.add(self._plex_group)

        # Jellyfin group
        self._jellyfin_group = Adw.PreferencesGroup(title="Jellyfin")
        self._jellyfin_host_row = Adw.EntryRow(title="Host")
        self._jellyfin_port_row = Adw.EntryRow(title="Port")
        self._jellyfin_user_row = Adw.EntryRow(title="Username")
        self._jellyfin_apikey_row = Adw.EntryRow(title="API Key")
        for row in (
            self._jellyfin_host_row, self._jellyfin_port_row,
            self._jellyfin_user_row, self._jellyfin_apikey_row,
        ):
            self._jellyfin_group.add(row)
        page.add(self._jellyfin_group)

        # Kodi group
        self._kodi_group = Adw.PreferencesGroup(title="Kodi")
        self._kodi_host_row = Adw.EntryRow(title="Host")
        self._kodi_port_row = Adw.EntryRow(title="Port")
        self._kodi_user_row = Adw.EntryRow(title="Username")
        self._kodi_passwd_row = Adw.PasswordEntryRow(title="Password")
        self._kodi_obey_row = Adw.SwitchRow(
            title="Obey update wait time",
            subtitle="Use configured wait time instead of 80% video duration",
        )
        for row in (
            self._kodi_host_row, self._kodi_port_row,
            self._kodi_user_row, self._kodi_passwd_row, self._kodi_obey_row,
        ):
            self._kodi_group.add(row)
        page.add(self._kodi_group)

        self.add(page)

    def _build_sync_page(self) -> None:
        """Build the Sync page: auto-retrieve and auto-send strategies."""
        page = Adw.PreferencesPage(title="Sync", icon_name="mail-send-receive-symbolic")

        # Download group
        download_group = Adw.PreferencesGroup(title="Download")

        self._autoretrieve_row = Adw.ComboRow(title="Auto-retrieve strategy")
        self._autoretrieve_model = Gtk.StringList.new(_AUTORETRIEVE_OPTIONS)
        self._autoretrieve_row.set_model(self._autoretrieve_model)
        self._autoretrieve_row.connect("notify::selected", self._on_autoretrieve_changed)
        download_group.add(self._autoretrieve_row)

        self._autoretrieve_days_row = Adw.SpinRow.new_with_range(1, 30, 1)
        self._autoretrieve_days_row.set_title("Retrieve interval (days)")
        download_group.add(self._autoretrieve_days_row)

        page.add(download_group)

        # Upload group
        upload_group = Adw.PreferencesGroup(title="Upload")

        self._autosend_row = Adw.ComboRow(title="Auto-send strategy")
        self._autosend_model = Gtk.StringList.new(_AUTOSEND_OPTIONS)
        self._autosend_row.set_model(self._autosend_model)
        self._autosend_row.connect("notify::selected", self._on_autosend_changed)
        upload_group.add(self._autosend_row)

        self._autosend_minutes_row = Adw.SpinRow.new_with_range(1, 1440, 5)
        self._autosend_minutes_row.set_title("Send interval (minutes)")
        upload_group.add(self._autosend_minutes_row)

        self._autosend_size_row = Adw.SpinRow.new_with_range(1, 100, 1)
        self._autosend_size_row.set_title("Queue size threshold")
        upload_group.add(self._autosend_size_row)

        self._autosend_exit_row = Adw.SwitchRow(title="Send at exit")
        upload_group.add(self._autosend_exit_row)

        page.add(upload_group)
        self.add(page)

    def _build_automation_page(self) -> None:
        """Build the Automation page: status changes, dates, and hooks."""
        page = Adw.PreferencesPage(title="Automation", icon_name="system-run-symbolic")

        # Status changes group
        status_group = Adw.PreferencesGroup(title="Status Changes")

        self._auto_status_row = Adw.SwitchRow(
            title="Auto-change status on progress",
            subtitle="Automatically set status to watching/completed",
        )
        status_group.add(self._auto_status_row)

        self._auto_status_scored_row = Adw.SwitchRow(
            title="Only complete if scored",
            subtitle="Defer completion until a score is set",
        )
        status_group.add(self._auto_status_scored_row)

        page.add(status_group)

        # Dates group
        dates_group = Adw.PreferencesGroup(title="Dates")

        self._auto_date_row = Adw.SwitchRow(
            title="Auto-set dates",
            subtitle="Set start/finish dates automatically on progress",
        )
        dates_group.add(self._auto_date_row)

        page.add(dates_group)

        # Extensions group
        extensions_group = Adw.PreferencesGroup(title="Extensions")

        self._hooks_row = Adw.SwitchRow(
            title="Enable hooks",
            subtitle="Load Python hooks from config directory",
        )
        extensions_group.add(self._hooks_row)

        page.add(extensions_group)
        self.add(page)

    # -- Load / Save ----------------------------------------------------------

    def _get(self, key: str) -> Any:
        """Read a config value from the engine."""
        try:
            return self._engine.get_config(key)
        except KeyError:
            logger.warning("Config key not found: %s", key)
            return None

    def _load(self) -> None:
        """Populate all widgets from engine config."""
        # Media
        self._player_row.set_text(str(self._get("player") or ""))
        self._load_searchdirs()
        self._autoscan_row.set_active(bool(self._get("library_autoscan")))
        self._fullpath_row.set_active(bool(self._get("library_full_path")))
        self._scan_whole_row.set_active(bool(self._get("scan_whole_list")))

        # Tracker
        self._tracker_enabled_row.set_active(bool(self._get("tracker_enabled")))

        tracker_type = str(self._get("tracker_type") or "auto")
        if tracker_type in _TRACKER_TYPES:
            self._tracker_type_row.set_selected(_TRACKER_TYPES.index(tracker_type))

        self._tracker_process_row.set_text(str(self._get("tracker_process") or ""))
        self._tracker_wait_row.set_value(float(self._get("tracker_update_wait_s") or 120))
        self._tracker_close_row.set_active(bool(self._get("tracker_update_close")))
        self._tracker_prompt_row.set_active(bool(self._get("tracker_update_prompt")))
        self._tracker_notfound_row.set_active(bool(self._get("tracker_not_found_prompt")))
        self._tracker_ignore_row.set_active(bool(self._get("tracker_ignore_not_next")))
        self._tracker_interval_row.set_value(float(self._get("tracker_interval") or 10))

        # Plex
        self._plex_host_row.set_text(str(self._get("plex_host") or ""))
        self._plex_port_row.set_text(str(self._get("plex_port") or ""))
        self._plex_user_row.set_text(str(self._get("plex_user") or ""))
        self._plex_passwd_row.set_text(str(self._get("plex_passwd") or ""))
        self._plex_ssl_row.set_active(bool(self._get("plex_ssl")))
        self._plex_obey_row.set_active(bool(self._get("plex_obey_update_wait_s")))

        # Jellyfin
        self._jellyfin_host_row.set_text(str(self._get("jellyfin_host") or ""))
        self._jellyfin_port_row.set_text(str(self._get("jellyfin_port") or ""))
        self._jellyfin_user_row.set_text(str(self._get("jellyfin_user") or ""))
        self._jellyfin_apikey_row.set_text(str(self._get("jellyfin_api_key") or ""))

        # Kodi
        self._kodi_host_row.set_text(str(self._get("kodi_host") or ""))
        self._kodi_port_row.set_text(str(self._get("kodi_port") or ""))
        self._kodi_user_row.set_text(str(self._get("kodi_user") or ""))
        self._kodi_passwd_row.set_text(str(self._get("kodi_passwd") or ""))
        self._kodi_obey_row.set_active(bool(self._get("kodi_obey_update_wait_s")))

        # Sync
        autoretrieve = str(self._get("autoretrieve") or "days")
        if autoretrieve in _AUTORETRIEVE_OPTIONS:
            self._autoretrieve_row.set_selected(_AUTORETRIEVE_OPTIONS.index(autoretrieve))
        self._autoretrieve_days_row.set_value(float(self._get("autoretrieve_days") or 3))

        autosend = str(self._get("autosend") or "minutes")
        if autosend in _AUTOSEND_OPTIONS:
            self._autosend_row.set_selected(_AUTOSEND_OPTIONS.index(autosend))
        self._autosend_minutes_row.set_value(float(self._get("autosend_minutes") or 60))
        self._autosend_size_row.set_value(float(self._get("autosend_size") or 5))
        self._autosend_exit_row.set_active(bool(self._get("autosend_at_exit")))

        # Automation
        self._auto_status_row.set_active(bool(self._get("auto_status_change")))
        self._auto_status_scored_row.set_active(bool(self._get("auto_status_change_if_scored")))
        self._auto_date_row.set_active(bool(self._get("auto_date_change")))
        self._hooks_row.set_active(bool(self._get("use_hooks")))

        # Update conditional visibility
        self._update_tracker_group_visibility()
        self._update_autoretrieve_visibility()
        self._update_autosend_visibility()

    def _save(self) -> None:
        """Write all widget values back to the engine config."""
        self._engine.set_config("player", self._player_row.get_text())
        self._engine.set_config("searchdir", self._collect_searchdirs())
        self._engine.set_config("library_autoscan", self._autoscan_row.get_active())
        self._engine.set_config("library_full_path", self._fullpath_row.get_active())
        self._engine.set_config("scan_whole_list", self._scan_whole_row.get_active())

        self._engine.set_config("tracker_enabled", self._tracker_enabled_row.get_active())
        selected = self._tracker_type_row.get_selected()
        if 0 <= selected < len(_TRACKER_TYPES):
            self._engine.set_config("tracker_type", _TRACKER_TYPES[selected])
        self._engine.set_config("tracker_process", self._tracker_process_row.get_text())
        self._engine.set_config("tracker_update_wait_s", int(self._tracker_wait_row.get_value()))
        self._engine.set_config("tracker_update_close", self._tracker_close_row.get_active())
        self._engine.set_config("tracker_update_prompt", self._tracker_prompt_row.get_active())
        self._engine.set_config("tracker_not_found_prompt", self._tracker_notfound_row.get_active())
        self._engine.set_config("tracker_ignore_not_next", self._tracker_ignore_row.get_active())
        self._engine.set_config("tracker_interval", int(self._tracker_interval_row.get_value()))

        self._engine.set_config("plex_host", self._plex_host_row.get_text())
        self._engine.set_config("plex_port", self._plex_port_row.get_text())
        self._engine.set_config("plex_user", self._plex_user_row.get_text())
        self._engine.set_config("plex_passwd", self._plex_passwd_row.get_text())
        self._engine.set_config("plex_ssl", self._plex_ssl_row.get_active())
        self._engine.set_config("plex_obey_update_wait_s", self._plex_obey_row.get_active())

        self._engine.set_config("jellyfin_host", self._jellyfin_host_row.get_text())
        self._engine.set_config("jellyfin_port", self._jellyfin_port_row.get_text())
        self._engine.set_config("jellyfin_user", self._jellyfin_user_row.get_text())
        self._engine.set_config("jellyfin_api_key", self._jellyfin_apikey_row.get_text())

        self._engine.set_config("kodi_host", self._kodi_host_row.get_text())
        self._engine.set_config("kodi_port", self._kodi_port_row.get_text())
        self._engine.set_config("kodi_user", self._kodi_user_row.get_text())
        self._engine.set_config("kodi_passwd", self._kodi_passwd_row.get_text())
        self._engine.set_config("kodi_obey_update_wait_s", self._kodi_obey_row.get_active())

        selected = self._autoretrieve_row.get_selected()
        if 0 <= selected < len(_AUTORETRIEVE_OPTIONS):
            self._engine.set_config("autoretrieve", _AUTORETRIEVE_OPTIONS[selected])
        self._engine.set_config("autoretrieve_days", int(self._autoretrieve_days_row.get_value()))

        selected = self._autosend_row.get_selected()
        if 0 <= selected < len(_AUTOSEND_OPTIONS):
            self._engine.set_config("autosend", _AUTOSEND_OPTIONS[selected])
        self._engine.set_config("autosend_minutes", int(self._autosend_minutes_row.get_value()))
        self._engine.set_config("autosend_size", int(self._autosend_size_row.get_value()))
        self._engine.set_config("autosend_at_exit", self._autosend_exit_row.get_active())

        self._engine.set_config("auto_status_change", self._auto_status_row.get_active())
        self._engine.set_config("auto_status_change_if_scored", self._auto_status_scored_row.get_active())
        self._engine.set_config("auto_date_change", self._auto_date_row.get_active())
        self._engine.set_config("use_hooks", self._hooks_row.get_active())

        self._engine.save_config()

    def _on_closed(self, _dialog: Adw.PreferencesDialog) -> None:
        """Save configuration when the dialog is closed.

        If tracker-related settings changed, the tracker is stopped and
        restarted so the new configuration takes effect immediately.
        """
        self._save()

        if self._initial_tracker_config != self._snapshot_tracker_config():
            self._restart_tracker()

    def _snapshot_tracker_config(self) -> dict[str, Any]:
        """Capture tracker-relevant config values for change detection."""
        keys = [
            "tracker_enabled", "tracker_type", "tracker_process",
            "tracker_update_wait_s", "tracker_update_close",
            "tracker_update_prompt", "tracker_not_found_prompt",
            "tracker_ignore_not_next", "tracker_interval",
            "plex_host", "plex_port", "plex_user", "plex_passwd",
            "plex_ssl", "plex_obey_update_wait_s",
            "jellyfin_host", "jellyfin_port", "jellyfin_user", "jellyfin_api_key",
            "kodi_host", "kodi_port", "kodi_user", "kodi_passwd",
            "kodi_obey_update_wait_s",
        ]
        return {k: self._get(k) for k in keys}

    def _restart_tracker(self) -> None:
        """Stop and re-create the tracker with current config."""
        import threading

        def worker() -> None:
            try:
                if self._engine.tracker:
                    # Nullify signal callbacks before disabling so the dying
                    # async loop can't emit stale events to the UI.
                    for key in self._engine.tracker.signals:
                        self._engine.tracker.signals[key] = None
                    self._engine.tracker.disable()
                    self._engine.tracker = None

                if (
                    self._engine.mediainfo.get("can_play")
                    and self._engine.config.get("tracker_enabled")
                ):
                    TrackerClass = self._engine._get_tracker_class(
                        self._engine.config["tracker_type"]
                    )
                    self._engine.tracker = TrackerClass(
                        self._engine.msg,
                        self._engine._get_tracker_list(),
                        self._engine.config,
                        self._engine.searchdirs,
                        self._engine.redirections,
                    )
                    self._engine.tracker.connect_signal("detected", self._engine._tracker_detected)
                    self._engine.tracker.connect_signal("removed", self._engine._tracker_removed)
                    self._engine.tracker.connect_signal("playing", self._engine._tracker_playing)
                    self._engine.tracker.connect_signal("update", self._engine._tracker_update)
                    self._engine.tracker.connect_signal("unrecognised", self._engine._tracker_unrecognised)
                    self._engine.tracker.connect_signal("state", self._engine._tracker_state)
                    logger.info("Tracker restarted with new configuration")
                    GLib.idle_add(
                        self._engine._emit_signal,
                        "tracker_state",
                        self._engine.tracker.get_status(),
                    )
                else:
                    logger.info("Tracker disabled")
                    GLib.idle_add(self._engine._emit_signal, "tracker_state", {
                        "state": None,
                        "timer": None,
                        "viewOffset": None,
                        "paused": False,
                        "show": None,
                        "filename": None,
                    })
            except ImportError:
                logger.warning("Couldn't import specified tracker: %s",
                               self._engine.config.get("tracker_type"))

        threading.Thread(target=worker, daemon=True).start()

    # -- Search directories management ----------------------------------------

    def _load_searchdirs(self) -> None:
        """Populate the search directories list from config."""
        self._clear_searchdir_rows()
        dirs = self._get("searchdir") or []
        if isinstance(dirs, str):
            dirs = [dirs]
        for d in dirs:
            self._add_searchdir_row(str(d))

    def _clear_searchdir_rows(self) -> None:
        """Remove all search directory rows."""
        for row in self._searchdir_rows:
            self._searchdir_group.remove(row)
        self._searchdir_rows.clear()

    def _add_searchdir_row(self, path: str) -> None:
        """Add a single search directory row."""
        row = Adw.ActionRow(title=path)

        remove_btn = Gtk.Button(
            icon_name="edit-delete-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Remove directory",
        )
        remove_btn.add_css_class("flat")
        remove_btn.connect("clicked", self._on_remove_searchdir, row)
        row.add_suffix(remove_btn)

        self._searchdir_group.add(row)
        self._searchdir_rows.append(row)

    def _collect_searchdirs(self) -> list[str]:
        """Collect all search directory paths from the current rows."""
        return [row.get_title() for row in self._searchdir_rows]

    def _on_add_searchdir(self, _button: Gtk.Button) -> None:
        """Open a folder chooser to add a search directory."""
        dialog = Gtk.FileDialog(title="Select Search Directory")
        parent = self.get_root()
        dialog.select_folder(
            parent if isinstance(parent, Gtk.Window) else None,
            None,
            self._on_folder_selected,
        )

    def _on_folder_selected(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult,
    ) -> None:
        """Handle the folder chooser result."""
        try:
            folder = dialog.select_folder_finish(result)
            if folder is not None:
                path = folder.get_path()
                if path:
                    self._add_searchdir_row(path)
        except GLib.Error:
            pass  # User cancelled

    def _on_remove_searchdir(self, _button: Gtk.Button, row: Adw.ActionRow) -> None:
        """Remove a search directory row."""
        if row in self._searchdir_rows:
            self._searchdir_rows.remove(row)
            self._searchdir_group.remove(row)

    # -- Conditional visibility -----------------------------------------------

    def _on_tracker_type_changed(self, _row: Adw.ComboRow, _pspec: Any) -> None:
        """Show/hide Plex/Jellyfin/Kodi groups based on tracker type."""
        self._update_tracker_group_visibility()

    def _update_tracker_group_visibility(self) -> None:
        """Update visibility of tracker-specific groups and rows."""
        selected = self._tracker_type_row.get_selected()
        tracker_type = _TRACKER_TYPES[selected] if 0 <= selected < len(_TRACKER_TYPES) else "auto"
        self._tracker_process_row.set_visible(tracker_type in _PROCESS_TRACKER_TYPES)
        self._tracker_interval_row.set_visible(tracker_type in _POLLING_TRACKER_TYPES)
        self._plex_group.set_visible(tracker_type == "plex")
        self._jellyfin_group.set_visible(tracker_type == "jellyfin")
        self._kodi_group.set_visible(tracker_type == "kodi")

    def _on_autoretrieve_changed(self, _row: Adw.ComboRow, _pspec: Any) -> None:
        """Show/hide days spin row based on autoretrieve strategy."""
        self._update_autoretrieve_visibility()

    def _update_autoretrieve_visibility(self) -> None:
        """Show the days spin row only when strategy is ``days``."""
        selected = self._autoretrieve_row.get_selected()
        strategy = _AUTORETRIEVE_OPTIONS[selected] if 0 <= selected < len(_AUTORETRIEVE_OPTIONS) else "days"
        self._autoretrieve_days_row.set_visible(strategy == "days")

    def _on_autosend_changed(self, _row: Adw.ComboRow, _pspec: Any) -> None:
        """Show/hide minutes/size spin rows based on autosend strategy."""
        self._update_autosend_visibility()

    def _update_autosend_visibility(self) -> None:
        """Show minutes or size spin row based on the selected strategy."""
        selected = self._autosend_row.get_selected()
        strategy = _AUTOSEND_OPTIONS[selected] if 0 <= selected < len(_AUTOSEND_OPTIONS) else "minutes"
        self._autosend_minutes_row.set_visible(strategy == "minutes")
        self._autosend_size_row.set_visible(strategy == "size")
