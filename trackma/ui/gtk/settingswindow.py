# This file is part of Trackma.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os

from gi.repository import Gdk, Gtk, Pango

from trackma import utils
from trackma.ui.gtk import gtk_dir


@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/settingswindow.ui'))
class SettingsWindow(Gtk.Window):

    __gtype_name__ = 'SettingsWindow'

    btn_save = Gtk.Template.Child()
    switch_tracker = Gtk.Template.Child()

    radio_tracker_local = Gtk.Template.Child()
    radio_tracker_mpris = Gtk.Template.Child()
    entry_player_process = Gtk.Template.Child()
    file_dialog_player_executable = Gtk.Template.Child()
    label_player_executable = Gtk.Template.Child()
    btn_player_executable = Gtk.Template.Child()
    file_dialog_directory = Gtk.Template.Child()
    listbox_directories = Gtk.Template.Child()
    btn_add_directory = Gtk.Template.Child()
    checkbox_library_startup = Gtk.Template.Child()
    checkbox_library_entire_list = Gtk.Template.Child()
    checkbox_library_full_path = Gtk.Template.Child()

    radio_tracker_plex = Gtk.Template.Child()
    entry_plex_host = Gtk.Template.Child()
    spin_plex_port = Gtk.Template.Child()
    entry_plex_username = Gtk.Template.Child()
    entry_plex_password = Gtk.Template.Child()
    checkbox_plex_obey_wait = Gtk.Template.Child()
    checkbox_plex_ssl = Gtk.Template.Child()

    radio_tracker_jellyfin = Gtk.Template.Child()
    entry_jellyfin_host = Gtk.Template.Child()
    spin_jellyfin_port = Gtk.Template.Child()
    entry_jellyfin_username = Gtk.Template.Child()
    entry_jellyfin_apikey = Gtk.Template.Child()

    radio_tracker_kodi = Gtk.Template.Child()
    entry_kodi_host = Gtk.Template.Child()
    spin_kodi_port = Gtk.Template.Child()
    entry_kodi_username = Gtk.Template.Child()
    entry_kodi_password = Gtk.Template.Child()
    checkbox_kodi_obey_wait = Gtk.Template.Child()

    spin_tracker_update_wait = Gtk.Template.Child()
    checkbox_tracker_update_close = Gtk.Template.Child()
    checkbox_tracker_update_prompt = Gtk.Template.Child()
    checkbox_tracker_not_found_prompt = Gtk.Template.Child()

    radiobutton_download_days = Gtk.Template.Child()
    radiobutton_download_always = Gtk.Template.Child()
    radiobutton_download_off = Gtk.Template.Child()

    radiobutton_upload_minutes = Gtk.Template.Child()
    radiobutton_upload_size = Gtk.Template.Child()
    radiobutton_upload_always = Gtk.Template.Child()
    radiobutton_upload_off = Gtk.Template.Child()
    checkbox_upload_exit = Gtk.Template.Child()

    spinbutton_download_days = Gtk.Template.Child()
    spinbutton_upload_minutes = Gtk.Template.Child()
    spinbutton_upload_size = Gtk.Template.Child()

    checkbox_auto_status_change = Gtk.Template.Child()
    checkbox_auto_status_change_if_scored = Gtk.Template.Child()
    checkbox_auto_date_change = Gtk.Template.Child()

    checkbox_remember_geometry = Gtk.Template.Child()
    checkbox_classic_progress = Gtk.Template.Child()

    colorbutton_rows_playing = Gtk.Template.Child()
    colorbutton_rows_queued = Gtk.Template.Child()
    colorbutton_rows_new_episode = Gtk.Template.Child()
    colorbutton_rows_is_airing = Gtk.Template.Child()
    colorbutton_rows_not_aired = Gtk.Template.Child()

    colorbutton_progress_bg = Gtk.Template.Child()
    colorbutton_progress_fg = Gtk.Template.Child()
    colorbutton_progress_sub_bg = Gtk.Template.Child()
    colorbutton_progress_sub_fg = Gtk.Template.Child()
    colorbutton_progress_complete = Gtk.Template.Child()

    def __init__(self, engine, config, configfile, transient_for=None):
        super().__init__(transient_for=transient_for)
        self.init_template()

        self.engine = engine
        self.config = config
        self.configfile = configfile

        self._color_buttons = {
            'is_playing':        self.colorbutton_rows_playing,
            'is_queued':         self.colorbutton_rows_queued,
            'new_episode':       self.colorbutton_rows_new_episode,
            'is_airing':         self.colorbutton_rows_is_airing,
            'not_aired':         self.colorbutton_rows_not_aired,
            'progress_bg':       self.colorbutton_progress_bg,
            'progress_fg':       self.colorbutton_progress_fg,
            'progress_sub_bg':   self.colorbutton_progress_sub_bg,
            'progress_sub_fg':   self.colorbutton_progress_sub_fg,
            'progress_complete': self.colorbutton_progress_complete
        }

        if os.sys.platform == 'linux':
            self.radio_tracker_mpris.set_visible(True)

        self.radiobutton_download_days.connect(
            "toggled", self._button_toggled, self.spinbutton_download_days)
        self.radiobutton_upload_minutes.connect(
            "toggled", self._button_toggled, self.spinbutton_upload_minutes)
        self.radiobutton_upload_size.connect(
            "toggled", self._button_toggled, self.spinbutton_upload_size)
        self.checkbox_auto_status_change.connect(
            "toggled", self._button_toggled, self.checkbox_auto_status_change_if_scored)

        self._load_config()

    def _load_config(self):
        """Engine Configuration"""
        self.switch_tracker.set_active(
            self.engine.get_config('tracker_enabled'))

        if (self.engine.get_config('tracker_type') == 'auto' or
            self.engine.get_config('tracker_type') == 'local'):
            self.radio_tracker_local.set_active(True)
        elif self.engine.get_config('tracker_type') == 'mpris':
            self.radio_tracker_mpris.set_active(True)
        elif self.engine.get_config('tracker_type') == 'plex':
            self.radio_tracker_plex.set_active(True)
        elif self.engine.get_config('tracker_type') == 'kodi':
            self.radio_tracker_kodi.set_active(True)
        elif self.engine.get_config('tracker_type') == 'jellyfin':
            self.radio_tracker_jellyfin.set_active(True)

        self.entry_player_process.set_text(
            self.engine.get_config('tracker_process'))
        self.label_player_executable.set_label(
            self.engine.get_config('player'))
        self.checkbox_library_startup.set_active(
            self.engine.get_config('library_autoscan'))
        self.checkbox_library_entire_list.set_active(
            self.engine.get_config('scan_whole_list'))
        self.checkbox_library_full_path.set_active(
            self.engine.get_config('library_full_path'))
        self._load_directories(self.engine.get_config('searchdir'))

        self.entry_plex_host.set_text(self.engine.get_config('plex_host'))
        self.spin_plex_port.set_value(int(self.engine.get_config('plex_port')))
        self.checkbox_plex_ssl.set_active(self.engine.get_config('plex_ssl'))
        self.entry_plex_username.set_text(self.engine.get_config('plex_user'))
        self.entry_plex_password.set_text(
            self.engine.get_config('plex_passwd'))
        self.checkbox_plex_obey_wait.set_active(
            self.engine.get_config('plex_obey_update_wait_s'))

        self.entry_jellyfin_host.set_text(
            self.engine.get_config('jellyfin_host'))
        self.spin_jellyfin_port.set_value(
            int(self.engine.get_config('jellyfin_port')))
        self.entry_jellyfin_username.set_text(
            self.engine.get_config('jellyfin_user'))
        self.entry_jellyfin_apikey.set_text(
            self.engine.get_config('jellyfin_api_key'))

        self.spin_tracker_update_wait.set_value(
            self.engine.get_config('tracker_update_wait_s'))
        self.checkbox_tracker_update_close.set_active(
            self.engine.get_config('tracker_update_close'))
        self.checkbox_tracker_update_prompt.set_active(
            self.engine.get_config('tracker_update_prompt'))
        self.checkbox_tracker_not_found_prompt.set_active(
            self.engine.get_config('tracker_not_found_prompt'))

        if self.engine.get_config('autoretrieve') == 'always':
            self.radiobutton_download_always.set_active(True)
        elif self.engine.get_config('autoretrieve') == 'days':
            self.radiobutton_download_days.set_active(True)
        else:
            self.radiobutton_download_off.set_active(True)

        if self.engine.get_config('autosend') == 'always':
            self.radiobutton_upload_always.set_active(True)
        elif self.engine.get_config('autosend') in ('minutes', 'hours'):
            self.radiobutton_upload_minutes.set_active(True)
        elif self.engine.get_config('autosend') == 'size':
            self.radiobutton_upload_size.set_active(True)
        else:
            self.radiobutton_upload_off.set_active(True)

        self.checkbox_upload_exit.set_active(
            self.engine.get_config('autosend_at_exit'))

        self.spinbutton_download_days.set_value(
            self.engine.get_config('autoretrieve_days'))
        self.spinbutton_upload_minutes.set_value(
            self.engine.get_config('autosend_minutes'))
        self.spinbutton_upload_size.set_value(
            self.engine.get_config('autosend_size'))

        self.checkbox_auto_status_change.set_active(
            self.engine.get_config('auto_status_change'))
        self.checkbox_auto_status_change_if_scored.set_active(
            self.engine.get_config('auto_status_change_if_scored'))
        self.checkbox_auto_date_change.set_active(
            self.engine.get_config('auto_date_change'))

        """GTK Interface configuration"""
        self.checkbox_remember_geometry.set_active(
            self.config['remember_geometry'])
        self.checkbox_classic_progress.set_active(
            not self.config['episodebar_style'])

        for color_key, color_button in self._color_buttons.items():
            color = Gdk.RGBA()
            color.parse(self.config['colors'][color_key])
            color_button.set_rgba(color)

        self._set_tracker_radio_buttons()
        self._button_toggled(self.radiobutton_download_days,
                             self.spinbutton_download_days)
        self._button_toggled(self.radiobutton_upload_minutes,
                             self.spinbutton_upload_minutes)
        self._button_toggled(self.radiobutton_upload_size,
                             self.spinbutton_upload_size)
        self._button_toggled(self.checkbox_auto_status_change,
                             self.checkbox_auto_status_change_if_scored)

    def _button_toggled(self, widget, spin):
        spin.set_sensitive(widget.get_active())

    @Gtk.Template.Callback()
    def _on_btn_save_clicked(self, btn):
        self.save_config()
        self.destroy()

    @Gtk.Template.Callback()
    def _on_switch_tracker_state_set(self, switch, state):
        self.radio_tracker_local.set_sensitive(state)
        self.radio_tracker_mpris.set_sensitive(state)
        self.radio_tracker_plex.set_sensitive(state)
        self.radio_tracker_jellyfin.set_sensitive(state)

        if state:
            self._set_tracker_radio_buttons()
        else:
            self._enable_local_and_mpris(False)
            self._enable_plex(False)
            self._enable_kodi(False)
            self._enable_jellyfin(False)

        self.spin_tracker_update_wait.set_sensitive(state)
        self.checkbox_tracker_update_close.set_sensitive(state)
        self.checkbox_tracker_update_prompt.set_sensitive(state)
        self.checkbox_tracker_not_found_prompt.set_sensitive(state)

    @Gtk.Template.Callback()
    def _set_tracker_radio_buttons(self, radio_button=None):
        self._enable_local_and_mpris(self.radio_tracker_local.get_active() or self.radio_tracker_mpris.get_active())
        self._enable_plex(self.radio_tracker_plex.get_active())
        self._enable_kodi(self.radio_tracker_kodi.get_active())
        self._enable_jellyfin(self.radio_tracker_jellyfin.get_active())

    def _enable_local_and_mpris(self, enable):
        self.entry_player_process.set_sensitive(enable)
        self.btn_player_executable.set_sensitive(enable)
        self.checkbox_library_startup.set_sensitive(enable)
        self.checkbox_library_entire_list.set_sensitive(enable)
        self.checkbox_library_full_path.set_sensitive(enable)

    def _enable_plex(self, enable):
        self.entry_plex_host.set_sensitive(enable)
        self.spin_plex_port.set_sensitive(enable)
        self.entry_plex_username.set_sensitive(enable)
        self.entry_plex_password.set_sensitive(enable)
        self.checkbox_plex_obey_wait.set_sensitive(enable)
        self.checkbox_plex_ssl.set_sensitive(enable)

    def _enable_kodi(self, enable):
        self.entry_kodi_host.set_sensitive(enable)
        self.spin_kodi_port.set_sensitive(enable)
        self.entry_kodi_username.set_sensitive(enable)
        self.entry_kodi_password.set_sensitive(enable)
        self.checkbox_kodi_obey_wait.set_sensitive(enable)

    def _enable_jellyfin(self, enable):
        self.entry_jellyfin_host.set_sensitive(enable)
        self.spin_jellyfin_port.set_sensitive(enable)
        self.entry_jellyfin_username.set_sensitive(enable)
        self.entry_jellyfin_apikey.set_sensitive(enable)

    def _load_directories(self, paths):
        if isinstance(paths, str):
            paths = [paths]

        for path in paths:
            self._add_row_listbox_directory(path)

    def _add_row_listbox_directory(self, path):
        row = DirectoryRow(path)
        self.listbox_directories.append(row)

    @Gtk.Template.Callback()
    def _on_btn_player_executable(self, btn):
        def on_dialog_dismissed(file_dialog, gio_task):
            local_file = file_dialog.open_finish(gio_task)
            self.label_player_executable.set_label(local_file.get_path())

        self.file_dialog_player_executable.open(parent=self.get_transient_for(), callback=on_dialog_dismissed)

    @Gtk.Template.Callback()
    def _on_btn_add_directory_clicked(self, btn):
        def on_dialog_dismissed(file_dialog, gio_task):
            local_file = file_dialog.select_folder_finish(gio_task)
            self._add_row_listbox_directory(local_file.get_path())

        self.file_dialog_directory.select_folder(parent=self.get_transient_for(), callback=on_dialog_dismissed)

    def save_config(self):
        """Engine Configuration"""
        self.engine.set_config(
            'player', self.label_player_executable.get_label() or '')
        self.engine.set_config(
            'tracker_process', self.entry_player_process.get_text())
        self.engine.set_config('library_autoscan',
                               self.checkbox_library_startup.get_active())
        self.engine.set_config('scan_whole_list',
                               self.checkbox_library_entire_list.get_active())
        self.engine.set_config('library_full_path',
                               self.checkbox_library_full_path.get_active())
        self.engine.set_config('plex_host', self.entry_plex_host.get_text())
        self.engine.set_config('plex_port', str(
            int(self.spin_plex_port.get_value())))
        self.engine.set_config('plex_ssl',
                               self.checkbox_plex_ssl.get_active())
        self.engine.set_config('plex_obey_update_wait_s',
                               self.checkbox_plex_obey_wait.get_active())
        self.engine.set_config(
            'plex_user', self.entry_plex_username.get_text())
        self.engine.set_config(
            'plex_passwd', self.entry_plex_password.get_text())
        self.engine.set_config(
            'jellyfin_host', self.entry_jellyfin_host.get_text())
        self.engine.set_config('jellyfin_port', str(
            int(self.spin_jellyfin_port.get_value())))
        self.engine.set_config(
            'jellyfin_user', self.entry_jellyfin_username.get_text())
        self.engine.set_config(
            'jellyfin_api_key', self.entry_jellyfin_apikey.get_text())
        self.engine.set_config(
            'tracker_enabled', self.switch_tracker.get_active())
        self.engine.set_config(
            'autosend_at_exit', self.checkbox_upload_exit.get_active())
        self.engine.set_config('tracker_update_wait_s',
                               self.spin_tracker_update_wait.get_value_as_int())
        self.engine.set_config('tracker_update_close',
                               self.checkbox_tracker_update_close.get_active())
        self.engine.set_config('tracker_update_prompt',
                               self.checkbox_tracker_update_prompt.get_active())
        self.engine.set_config('tracker_not_found_prompt',
                               self.checkbox_tracker_not_found_prompt.get_active())

        self.engine.set_config(
            'searchdir', [row.directory for row in self.listbox_directories])

        # Tracker type
        if self.radio_tracker_local.get_active():
            self.engine.set_config('tracker_type', 'local')
        elif self.radio_tracker_mpris.get_active():
            self.engine.set_config('tracker_type', 'mpris')
        elif self.radio_tracker_plex.get_active():
            self.engine.set_config('tracker_type', 'plex')
        elif self.radio_tracker_jellyfin.get_active():
            self.engine.set_config('tracker_type', 'jellyfin')

        # Auto-retrieve
        if self.radiobutton_download_always.get_active():
            self.engine.set_config('autoretrieve', 'always')
        elif self.radiobutton_download_days.get_active():
            self.engine.set_config('autoretrieve', 'days')
        else:
            self.engine.set_config('autoretrieve', 'off')

        # Auto-send
        if self.radiobutton_upload_always.get_active():
            self.engine.set_config('autosend', 'always')
        elif self.radiobutton_upload_minutes.get_active():
            self.engine.set_config('autosend', 'minutes')
        elif self.radiobutton_upload_size.get_active():
            self.engine.set_config('autosend', 'size')
        else:
            self.engine.set_config('autosend', 'off')

        self.engine.set_config(
            'autoretrieve_days', self.spinbutton_download_days.get_value_as_int())
        self.engine.set_config(
            'autosend_minutes', self.spinbutton_upload_minutes.get_value_as_int())
        self.engine.set_config(
            'autosend_size', self.spinbutton_upload_size.get_value_as_int())

        self.engine.set_config('auto_status_change',
                               self.checkbox_auto_status_change.get_active())
        self.engine.set_config('auto_status_change_if_scored',
                               self.checkbox_auto_status_change_if_scored.get_active())
        self.engine.set_config(
            'auto_date_change', self.checkbox_auto_date_change.get_active())
        # self.engine.save_config()

        """GTK Interface configuration"""
        self.config['remember_geometry'] = self.checkbox_remember_geometry.get_active()
        self.config['episodebar_style'] = int(
            not self.checkbox_classic_progress.get_active())

        """Update Colors"""
        for key, col in self._color_buttons.items():
            self.config['colors'] = {key: col.get_rgba().to_string() for key, col in self._color_buttons.items()}

        utils.save_config(self.config, self.configfile)


class DirectoryRow(Gtk.ListBoxRow):
    def __init__(self, directory):
        super().__init__()

        self.directory = directory

        label = Gtk.Label(label=directory)
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        image_button = Gtk.Image.new_from_icon_name('window-close-symbolic')
        button_remove = Gtk.Button()
        button_remove.set_child(image_button)
        button_remove.connect('clicked', self._on_button_remove_click)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        box.append(label)
        box.append(button_remove)

        self.set_activatable(False)
        self.set_margin_bottom(5)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(5)

        self.set_child(box)

    def _on_button_remove_click(self, btn):
        self.get_parent().remove(self)
