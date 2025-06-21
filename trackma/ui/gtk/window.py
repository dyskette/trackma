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
import subprocess
import sys
import threading

from gi.repository import GLib, Gdk, Gio, Gtk, GObject

from trackma import messenger
from trackma import utils
from trackma.accounts import AccountManager
from trackma.engine import Engine
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.accountswindow import AccountsWindow
from trackma.ui.gtk.mainview import MainView
from trackma.ui.gtk.searchwindow import SearchWindow
from trackma.ui.gtk.settingswindow import SettingsWindow
from trackma.ui.gtk.showeventtype import ShowEventType
from trackma.ui.gtk.showinfowindow import ShowInfoWindow


@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/window.ui'))
class TrackmaWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'TrackmaWindow'

    btn_mediatype: Gtk.MenuButton = Gtk.Template.Child()
    header_bar: Gtk.HeaderBar = Gtk.Template.Child()
    subtitle_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, app, debug=False):
        Gtk.ApplicationWindow.__init__(self, application=app)
        self.init_template()

        self._debug = debug
        self._configfile = utils.to_config_path('ui-Gtk.json')
        self._config = utils.parse_config(self._configfile, utils.gtk_defaults)

        self._main_view = None
        self._modals = []

        self._account = None
        self._engine = None
        self.close_thread = None

        self._init_widgets()

    def init_account_selection(self):
        manager = AccountManager()

        # Use the remembered account if there's one
        if manager.get_default():
            self._create_engine(manager.get_default())
        else:
            self._show_accounts(switch=False)

    def _init_widgets(self):
        Gtk.Window.set_default_icon_name("trackma")
        self.set_default_size(600, 600)
        self.set_title('Trackma')

        if self._config['remember_geometry']:
            self.resize(self._config['last_width'],
                        self._config['last_height'])

        if not self._main_view:
            self._main_view = MainView(self._config)
            self._main_view.connect('error', self._on_main_view_error)
            self._main_view.connect(
                'success', lambda x: self._set_buttons_sensitive(True))
            self._main_view.connect(
                'error-fatal', self._on_main_view_error_fatal)
            self._main_view.connect('show-action', self._on_show_action)
            self.set_child(self._main_view)

        self.connect('close-request', self._on_close_request)

        self.present()

    def _on_close_request(self, widget):
        self._quit()
        return True

    def _create_engine(self, account):
        self._engine = Engine(account, self._message_handler)

        self._main_view.load_engine_account(self._engine, account)
        self._set_mediatypes_menu()
        self._update_widgets(account)
        self._set_buttons_sensitive(True)

        def add_action(name, callback):
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', callback)
            self.add_action(action)

        add_action('search', self._on_search)
        add_action('synchronize', self._on_synchronize)
        add_action('upload', self._on_upload)
        add_action('download', self._on_download)
        add_action('scanfiles', self._on_scanfiles)
        add_action('accounts', self._on_accounts)
        add_action('preferences', self._on_preferences)
        add_action('about', self._on_about)
        add_action('show-help-overlay', self._on_show_help_overlay)

        add_action('play_next', self._on_action_play_next)
        add_action('play_random', self._on_action_play_random)
        add_action('episode_add', self._on_action_episode_add)
        add_action('episode_remove', self._on_action_episode_remove)
        add_action('delete', self._on_action_delete)
        add_action('copy', self._on_action_copy)

    def _set_mediatypes_action(self):
        action_name = 'change-mediatype'
        if self.has_action(action_name):
            self.remove_action(action_name)

        state = GLib.Variant.new_string(self._engine.api_info['mediatype'])
        action = Gio.SimpleAction.new_stateful(action_name,
                                               state.get_type(),
                                               state)
        action.connect('change-state', self._on_change_mediatype)
        self.add_action(action)

    def _set_mediatypes_menu(self):
        self._set_mediatypes_action()
        menu = Gio.Menu()

        for mediatype in self._engine.api_info['supported_mediatypes']:
            variant = GLib.Variant.new_string(mediatype)
            menu_item = Gio.MenuItem()
            menu_item.set_label(mediatype)
            menu_item.set_action_and_target_value(
                'win.change-mediatype', variant)
            menu.append_item(menu_item)

        self.btn_mediatype.set_menu_model(menu)

        if len(self._engine.api_info['supported_mediatypes']) <= 1:
            self.btn_mediatype.hide()

    def _update_widgets(self, account):
        current_api = utils.available_libs[account['api']]
        api_iconpath = 1
        api_iconfile = current_api[api_iconpath]

        # Update the subtitle label with API info
        subtitle_text = self._engine.api_info['name'] + " (" + self._engine.api_info['mediatype'] + ")"
        self.subtitle_label.set_text(subtitle_text)

    def _on_change_mediatype(self, action, value):
        action.set_state(value)
        mediatype = value.get_string()
        self._set_buttons_sensitive(False)
        self._main_view.load_account_mediatype(
            None, mediatype, self.subtitle_label)

    def _on_search(self, action, param):
        current_status = self._main_view.get_current_status()
        win = SearchWindow(
            self._engine, self._config['colors'], current_status, transient_for=self)
        win.connect('search-error', self._on_search_error)
        win.connect('destroy', self._on_modal_destroy)
        win.present()
        self._modals.append(win)

    def _on_search_error(self, search_window, error_msg):
        print(error_msg)

    def _on_synchronize(self, action, param):
        threading.Thread(target=self._synchronization_task,
                         args=(True, True)).start()

    def _on_upload(self, action, param):
        threading.Thread(target=self._synchronization_task,
                         args=(True, False)).start()

    def _on_download(self, action, param):
        def _download_lists():
            self._synchronization_task(False, True)

        def _on_download_response(_dialog, response):
            _dialog.destroy()
            if response == Gtk.ResponseType.YES:
                _download_lists()

        queue = self._engine.get_queue()
        if queue:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="There are %d queued changes in your list. If you retrieve the remote list now you will lose your queued changes. Are you sure you want to continue?" % len(queue))
            dialog.connect("response", _on_download_response)
            dialog.present()
        else:
            # If the user doesn't have any queued changes
            # just go ahead
            _download_lists()

    def _synchronization_task(self, send, retrieve):
        self._set_buttons_sensitive_idle(False)

        try:
            if send:
                self._engine.list_upload()
            if retrieve:
                self._engine.list_download()

            # GLib.idle_add(self._set_score_ranges)
            GLib.idle_add(self._main_view.populate_all_pages)
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)
        except utils.TrackmaFatal as e:
            self._show_accounts_idle(switch=False, forget=True)
            self._error_dialog_idle("Fatal engine error: %s" % e)
            return

        self._main_view.set_status_idle("Ready.")
        self._set_buttons_sensitive_idle(True)

    def _on_scanfiles(self, action, param):
        threading.Thread(target=self._scanfiles_task).start()

    def _scanfiles_task(self):
        self._set_buttons_sensitive_idle(False)
        try:
            self._engine.scan_library(rescan=True)
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)

        GLib.idle_add(self._main_view.populate_all_pages)

        self._main_view.set_status_idle("Ready.")
        self._set_buttons_sensitive_idle(True)

    def _on_accounts(self, action, param):
        self._show_accounts()

    def _show_accounts_idle(self, switch=True, forget=False):
        GLib.idle_add(self._show_accounts, switch, forget)

    def _show_accounts(self, switch=True, forget=False):
        manager = AccountManager()

        if forget:
            manager.set_default(None)

        accountsel = AccountsWindow(manager, transient_for=self)
        accountsel.connect('account-open', self._on_account_open)
        accountsel.connect('account-cancel', self._on_account_cancel, switch)
        accountsel.connect('destroy', self._on_modal_destroy)
        accountsel.present()
        self._modals.append(accountsel)

    def _on_account_open(self, accounts_window, account_num, remember):
        manager = AccountManager()
        account = manager.get_account(account_num)

        if remember:
            manager.set_default(account_num)
        else:
            manager.set_default(None)

        # Reload the engine if already started,
        # start it otherwise
        self._set_buttons_sensitive(False)
        if self._engine and self._engine.loaded:
            self._main_view.load_account_mediatype(account, None, None)
        else:
            self._create_engine(account)

    def _on_account_cancel(self, _accounts_window, switch):
        manager = AccountManager()

        if not switch or not manager.get_accounts():
            self._quit()

    def _on_preferences(self, _action, _param):
        win = SettingsWindow(self._engine, self._config,
                             self._configfile, transient_for=self)
        win.connect('settings-saved', self._on_settings_saved)
        win.connect('destroy', self._on_modal_destroy)
        win.present()
        self._modals.append(win)

    def _on_settings_saved(self, settings_window):
        """Called when settings are saved"""
        # Reload config from file to get updated colors
        self._config = utils.parse_config(self._configfile, utils.gtk_defaults)
        self._refresh_colors()

    def _refresh_colors(self):
        """Refresh colors in all UI components after settings change"""
        if self._main_view:
            self._main_view.refresh_colors(self._config['colors'])
        
        # Refresh any open search windows
        for modal in self._modals[:]:  # Copy list to avoid modification during iteration
            if hasattr(modal, 'refresh_colors'):
                modal.refresh_colors(self._config['colors'])

    def _on_about(self, _action, _param):
        about = Gtk.AboutDialog()
        about.set_modal(True)
        about.set_transient_for(self)
        about.set_program_name("Trackma GTK")
        about.set_version(utils.VERSION)
        about.set_license_type(Gtk.License.GPL_3_0_ONLY)
        about.set_comments(
            "Trackma is an open source client for media tracking websites.\nThanks to all contributors.")
        about.set_website("https://github.com/z411/trackma")
        about.set_copyright("© z411, et al.")
        about.set_authors(["See AUTHORS file"])
        about.set_artists(["shuuichi"])
        about.connect('destroy', self._on_modal_destroy)
        
        about.present()
        self._modals.append(about)

    def _on_modal_destroy(self, modal_window):
        self._modals.remove(modal_window)

    def _quit(self):
        if self._config['remember_geometry']:
            self._store_geometry()

        if not self._engine:
            self.get_application().quit()
            return

        if self.close_thread is None:
            self._set_buttons_sensitive_idle(False)
            self.close_thread = threading.Thread(target=self._unload_task)
            self.close_thread.start()

    def _unload_task(self):
        self._engine.unload()
        GLib.idle_add(self.get_application().quit)

    def _store_geometry(self):
        (width, height) = self.get_size()
        self._config['last_width'] = width
        self._config['last_height'] = height
        utils.save_config(self._config, self._configfile)

    def _message_handler(self, classname, msgtype, msg):
        # Thread safe
        # print("%s: %s" % (classname, msg))
        if msgtype == messenger.TYPE_WARN:
            self._main_view.set_status_idle(
                "%s warning: %s" % (classname, msg))
        elif msgtype != messenger.TYPE_DEBUG:
            self._main_view.set_status_idle("%s: %s" % (classname, msg))
        elif self._debug:
            print('[D] {}: {}'.format(classname, msg))

    def _on_main_view_error(self, main_view, error_msg):
        self._error_dialog_idle(error_msg)

    def _on_main_view_error_fatal(self, main_view, error_msg):
        self._show_accounts_idle(switch=False, forget=True)
        self._error_dialog_idle(error_msg)

    def _error_dialog_idle(self, msg, icon=Gtk.MessageType.ERROR):
        # Thread safe
        GLib.idle_add(self._error_dialog, msg, icon)

    def _error_dialog(self, msg, icon=Gtk.MessageType.ERROR):
        def error_dialog_response(widget, response_id):
            widget.destroy()

        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=icon,
            buttons=Gtk.ButtonsType.OK,
            text=str(msg))
        dialog.connect("response", error_dialog_response)
        dialog.present()
        print('Error: {}'.format(msg))

    def _on_action_play_next(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._play_next(selected_show)

    def _on_action_play_random(self, action, param):
        self._play_random()

    def _on_action_episode_add(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._episode_add(selected_show)

    def _on_action_episode_remove(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._episode_remove(selected_show)

    def _on_action_delete(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._remove_show(selected_show)

    def _on_action_copy(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._copy_title(selected_show)

    def _on_show_action(self, main_view, event_type, data):
        if event_type == ShowEventType.PLAY_NEXT:
            self._play_next(*data)
        elif event_type == ShowEventType.PLAY_EPISODE:
            self._play_episode(*data)
        elif event_type == ShowEventType.EPISODE_REMOVE:
            self._episode_remove(*data)
        elif event_type == ShowEventType.EPISODE_SET:
            self._episode_set(*data)
        elif event_type == ShowEventType.EPISODE_ADD:
            self._episode_add(*data)
        elif event_type == ShowEventType.SET_SCORE:
            self._set_score(*data)
        elif event_type == ShowEventType.SET_STATUS:
            self._set_status(*data)
        elif event_type == ShowEventType.DETAILS:
            self._open_details(*data)
        elif event_type == ShowEventType.OPEN_WEBSITE:
            self._open_website(*data)
        elif event_type == ShowEventType.OPEN_FOLDER:
            self._open_folder(*data)
        elif event_type == ShowEventType.COPY_TITLE:
            self._copy_title(*data)
        elif event_type == ShowEventType.CHANGE_ALTERNATIVE_TITLE:
            self._change_alternative_title(*data)
        elif event_type == ShowEventType.REMOVE:
            self._remove_show(*data)

    def _play_next(self, show_id):
        show = self._engine.get_show_info(show_id)
        try:
            args = self._engine.play_episode(show)
            utils.spawn_process(args)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _play_episode(self, show_id, episode):
        show = self._engine.get_show_info(show_id)
        try:
            if not episode:
                episode = self.show_ep_num.get_value_as_int()
            args = self._engine.play_episode(show, episode)
            utils.spawn_process(args)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _play_random(self):
        try:
            args = self._engine.play_random()
            utils.spawn_process(args)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _episode_add(self, show_id):
        show = self._engine.get_show_info(show_id)
        self._episode_set(show_id, show['my_progress'] + 1)

    def _episode_remove(self, show_id):
        show = self._engine.get_show_info(show_id)
        self._episode_set(show_id, show['my_progress'] - 1)

    def _episode_set(self, show_id, episode):
        try:
            self._engine.set_episode(show_id, episode)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _set_score(self, show_id, score):
        try:
            self._engine.set_score(show_id, score)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _set_status(self, show_id, status):
        try:
            self._engine.set_status(show_id, status)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _open_details(self, show_id):
        show = self._engine.get_show_info(show_id)
        win = ShowInfoWindow(self._engine, show, transient_for=self)
        win.connect('destroy', self._on_modal_destroy)
        win.present()
        self._modals.append(win)

    def _open_website(self, show_id):
        show = self._engine.get_show_info(show_id)
        if show['url']:
            Gtk.show_uri(None, show['url'], Gdk.CURRENT_TIME)

    def _open_folder(self, show_id):
        try:
            self._engine.open_show_folder(show_id)
        except utils.EngineError as e:
            self._error_dialog_idle(e.args[0])

    def _copy_title(self, show_id):
        show = self._engine.get_show_info(show_id)
        value = GObject.Value(GObject.TYPE_STRING, show['title'])
        content = Gdk.ContentProvider.new_for_value(value)
        clipboard = self.get_display().get_clipboard()
        clipboard.set_content(content)

        self._main_view.set_status_idle('Title copied to clipboard.')

    def _change_alternative_title(self, show_id):
        show = self._engine.get_show_info(show_id)
        current_altname = self._engine.altname(show_id)

        dialog = Gtk.Dialog(
            transient_for=self,
            modal=True)
        dialog.set_title("Set Alternate Title")

        header_bar = Gtk.HeaderBar()
        header_bar.set_show_title_buttons(False)
        dialog.set_titlebar(header_bar)

        cancel_button = Gtk.Button.new_with_label("Cancel")
        cancel_button.connect("clicked", lambda w: dialog.response(Gtk.ResponseType.CANCEL))
        header_bar.pack_start(cancel_button)

        set_button = Gtk.Button.new_with_label("Set")
        set_button.get_style_context().add_class("suggested-action")
        set_button.connect("clicked", lambda w: dialog.response(Gtk.ResponseType.OK))
        header_bar.pack_end(set_button)

        content_area = dialog.get_content_area()

        desc_label = Gtk.Label()
        desc_label.set_markup('Set the <b>alternate title</b> for the show.')
        desc_label.set_margin_start(12)
        desc_label.set_margin_end(12)
        desc_label.set_margin_top(12)
        content_area.append(desc_label)

        sec_label = Gtk.Label()
        sec_label.set_markup("Use this if the tracker is unable to find this show. Leave blank to disable.")
        sec_label.set_margin_start(12)
        sec_label.set_margin_end(12)
        content_area.append(sec_label)

        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        entry_box.set_margin_start(12)
        entry_box.set_margin_end(12)
        entry_box.set_margin_top(12)
        entry_box.set_margin_bottom(12)
        entry_box.set_spacing(12)

        label = Gtk.Label(label="Alternate Title:")
        entry = Gtk.Entry()
        entry.set_text(current_altname)
        entry.set_hexpand(True)

        entry_box.append(label)
        entry_box.append(entry)
        content_area.append(entry_box)

        entry.connect("activate", lambda w: dialog.response(Gtk.ResponseType.OK))

        def on_response(d, response):
            if response == Gtk.ResponseType.OK:
                text = entry.get_text()
                self._engine.altname(show_id, text)
                self._main_view.change_show_title_idle(show, text)
            d.destroy()

        dialog.connect('response', on_response)
        dialog.present()
        entry.grab_focus()

    def _remove_show(self, show_id):
        try:
            show = self._engine.get_show_info(show_id)
            self._engine.delete_show(show)
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)

    def _set_buttons_sensitive_idle(self, sensitive):
        GLib.idle_add(self._set_buttons_sensitive, sensitive)
        self._main_view.set_buttons_sensitive_idle(sensitive)

    def _set_buttons_sensitive(self, sensitive):
        actions_names = ['search',
                         'synchronize',
                         'upload',
                         'download',
                         'scanfiles',
                         'accounts',
                         'play_next',
                         'play_random',
                         'episode_add',
                         'episode_remove',
                         'delete',
                         'copy']

        for action_name in actions_names:
            action = self.lookup_action(action_name)

            if action is not None:
                action.set_enabled(sensitive)

    def _on_show_help_overlay(self, action, param):
        builder = Gtk.Builder.new_from_file(
            os.path.join(gtk_dir, 'data/shortcuts.ui'))
        help_overlay = builder.get_object('shortcuts-window')
        help_overlay.set_transient_for(self)
        help_overlay.present()
