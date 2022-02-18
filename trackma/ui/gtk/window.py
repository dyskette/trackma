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
from gi.repository import GLib, Gio, Gtk, Gdk, Adw
from loguru import logger
from trackma import messenger
from trackma import utils
from trackma.accounts import AccountManager
from trackma.ui.gtk.accountsview import TrackmaAccountsView
from trackma.ui.gtk.newaccountview import TrackmaNewAccountView
from trackma.ui.gtk.titlesview import TrackmaTitlesView
from trackma.engine import Engine
from trackma.ui.gtk import gtk_dir

@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/window.ui'))
class TrackmaWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'TrackmaWindow'

    # All views
    leaflet = Gtk.Template.Child()
    home = Gtk.Template.Child()
    new_account_view = Gtk.Template.Child()
    accounts_view = Gtk.Template.Child()
    titles_view = Gtk.Template.Child()

    def __init__(self, app):
        ''' Trackma Window class

            Args:
                app (Adw.Application): the application instance
                debug (bool): flag to show debugging information
        '''
        super().__init__(application=app)

        self._window_actions = [
            ( 'new-account', self._on_home ),
            ( 'home', self._on_accounts ),
            ( 'titles', self._on_titles, "i" ),
            ( 'preferences', self._on_preferences ),
            ( 'about', self._on_about ),
        ]

        self._list_actions = [
            ( 'search', self._on_action ),
            ( 'syncronize', self._on_action ),
            ( 'upload', self._on_action ),
            ( 'download', self._on_action ),
            ( 'scanfiles', self._on_action ),
        ]

        self._show_actions = [
            ( 'play-next', self._on_action ),
            ( 'play-episode', self._on_action ),
            ( 'play-random', self._on_action ),
            ( 'view-details', self._on_action ),
            ( 'open-website', self._on_action ),
            ( 'open-folder', self._on_action ),
            ( 'copy-title', self._on_action ),
            ( 'set-alternative-title', self._on_action ),
            ( 'remove', self._on_action ),
        ]

        self._register_actions()
        self._create_help_overlay()
        self.activate_action('win.home')

    def _on_home(self, action, parameter, user_data):
        if len(AccountManager().get_accounts()) > 0:
            self.leaflet.set_visible_child(self.new_account_view)
        else:
            self.leaflet.set_visible_child(self.home)

    def _on_accounts(self, action, parameter, user_data):
        self.accounts_view.refresh()
        self.leaflet.set_visible_child(self.accounts_view)

    def _on_titles(self, action, parameter, account_id):
        self.leaflet.set_visible_child(self.titles_view)

    def _on_account_list(self, action, parameter):
        raise NotImplementedError('Account list action callback is not implemented yet')

    def _on_account_content(self, action, parameter):
        self._engine = Engine(account, self._message_handler)

    def _on_about(self, action, parameter):
        raise NotImplementedError('On about action is not implemented')

    def _on_preferences(self, action, parameter):
        raise NotImplementedError('On preferences action is not implemented')

    def _on_action(self, action, parameter):
        raise NotImplementedError('On action callback is not implemented')

    def _error_dialog(error):
        dialog = Gtk.MessageDialog(
            transient_for=None,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            modal=False,
            text=str(error))
        dialog.connect('response', lambda _dialog, response: _dialog.destroy())
        dialog.show()

    def _message_handler(self, classname, msgtype, msg):
        if msgtype == messenger.TYPE_WARN:
            logger.warning('Engine message: {}', msg)
        elif msgtype != messenger.TYPE_DEBUG:
            logger.info('Engine message: {}', msg)
        else:
            logger.debug('Engine message: {}', msg)

    def quit(self):
        self.get_application().quit()

    def _register_actions(self):
        self.add_action_entries(self._window_actions)

        list_actions = Gio.SimpleActionGroup()
        list_actions.add_action_entries(self._list_actions)
        self.insert_action_group('list', list_actions)

        show_actions = Gio.SimpleActionGroup()
        show_actions.add_action_entries(self._show_actions)
        self.insert_action_group('show', show_actions)

    def _create_help_overlay(self):
        builder = Gtk.Builder.new_from_file(
            os.path.join(gtk_dir, 'data/shortcuts.ui'))
        help_overlay = builder.get_object('shortcuts-window')
        self.set_help_overlay(help_overlay)
