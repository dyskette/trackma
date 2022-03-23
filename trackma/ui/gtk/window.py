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
from gi.repository import Gio, GLib, Gtk, Adw
from loguru import logger
from trackma import messenger
from trackma import utils
from trackma.accounts import AccountManager
from trackma.engine import Engine
from trackma.ui.gtk import gtk_dir, from_variant
from trackma.ui.gtk.accountsview import TrackmaAccountsView
from trackma.ui.gtk.newaccountview import TrackmaNewAccountView
from trackma.ui.gtk.providersview import TrackmaProvidersView
from trackma.ui.gtk.titlesview import TrackmaTitlesView

@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/window.ui'))
class TrackmaWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'TrackmaWindow'

    # All views
    leaflet = Gtk.Template.Child()
    providers_view = Gtk.Template.Child()
    new_account_view = Gtk.Template.Child()
    accounts_view = Gtk.Template.Child()
    titles_view = Gtk.Template.Child()

    def __init__(self, app: Adw.Application):
        ''' Trackma Window class

            Args:
                app (Adw.Application): the application instance
                debug (bool): flag to show debugging information
        '''
        super().__init__(application=app)

        self._window_actions = [
            ( 'accounts', self._on_accounts ),
            ( 'providers', self._on_providers ),
            ( 'new-account', self._on_new_account, 's' ),
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
            ( 'remove', self.accounts_view.remove_account, 'i' )
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
        self.activate_action('win.accounts')

    def _on_accounts(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Refresh the accounts view and show it
        '''
        self.accounts_view.refresh()
        self.leaflet.set_visible_child(self.accounts_view)

    def _on_providers(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Show the providers view
        '''
        self.leaflet.set_visible_child(self.providers_view)

    def _on_new_account(self, action: Gio.SimpleAction, provider_name: GLib.Variant, user_data=None) -> None:
        ''' Show the "new account" view
        '''
        succeeded = self.new_account_view.prepare_for(provider_name.get_string())

        if succeeded:
            self.leaflet.set_visible_child(self.new_account_view)

    def _on_titles(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Show the titles view
        '''
        self.leaflet.set_visible_child(self.titles_view)

    def _on_about(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Show the about window
        '''
        logger.error('On about action is not implemented')

    def _on_preferences(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Show the preferences window
        '''
        if self._engine is None:
            logger.error('Cannot open the preferences window because the engine has not been started')
        else:
            logger.debug('Here we will show the preferences window')

    def _on_action(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Action callback placeholder
            TODO: Delete this method when everything is implemented
        '''
        logger.error('On action callback is not implemented')

    def _error_dialog(error):
        dialog = Gtk.MessageDialog(
            transient_for=None,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            modal=False,
            text=str(error))
        dialog.connect('response', lambda _dialog, response: _dialog.destroy())
        dialog.show()

    def _message_handler(self, classname: str, msgtype: int, msg: str) -> None:
        ''' Handle all messages incoming from the trackma engine class
        '''
        if msgtype == messenger.TYPE_WARN:
            logger.warning('Engine message: {}', msg)
        elif msgtype != messenger.TYPE_DEBUG:
            logger.info('Engine message: {}', msg)
        else:
            logger.debug('Engine message: {}', msg)

    def _register_actions(self) -> None:
        ''' Register all possible actions for the current window
        '''
        self.add_action_entries(self._window_actions)

        list_actions = Gio.SimpleActionGroup()
        list_actions.add_action_entries(self._list_actions)
        self.insert_action_group('list', list_actions)

        show_actions = Gio.SimpleActionGroup()
        show_actions.add_action_entries(self._show_actions)
        self.insert_action_group('show', show_actions)

    def _create_help_overlay(self) -> None:
        ''' Get the help overlay template and attach it to the window
        '''
        builder = Gtk.Builder.new_from_file(
            os.path.join(gtk_dir, 'data/shortcuts.ui'))
        help_overlay = builder.get_object('shortcuts-window')
        self.set_help_overlay(help_overlay)
