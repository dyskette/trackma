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

from gi.repository import Adw, Gio, GLib, Gtk
from loguru import logger
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.accountsview import TrackmaAccountsView
from trackma.ui.gtk.newaccountview import TrackmaNewAccountView
from trackma.ui.gtk.providersview import TrackmaProvidersView
from trackma.ui.gtk.titlesview import TrackmaTitlesView


@Gtk.Template.from_file(get_resource_path('window.ui'))
class TrackmaWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'TrackmaWindow'

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    leaflet: Adw.Leaflet = Gtk.Template.Child()
    providers_view: TrackmaProvidersView = Gtk.Template.Child()
    new_account_view: TrackmaNewAccountView = Gtk.Template.Child()
    accounts_view: TrackmaAccountsView = Gtk.Template.Child()
    titles_view: TrackmaTitlesView = Gtk.Template.Child()

    def __init__(self, app: Adw.Application):
        ''' Trackma Window class

            Args:
                app (Adw.Application): the application instance
        '''
        super().__init__(application=app)

        self._window_actions = [
            ('accounts', self._on_accounts),
            ('providers', self._on_providers),
            ('new-account', self._on_new_account, 's'),
            ('titles', self._on_titles, "i"),
            ('preferences', self._on_preferences),
            ('about', self._on_about),
        ]

        self._list_actions = [
            ('search', self._on_action),
            ('syncronize', self._on_action),
            ('upload', self._on_action),
            ('download', self._on_action),
            ('scanfiles', self._on_action),
            ('remove', self.accounts_view.remove_account, 'i')
        ]

        self._show_actions = [
            ('play-next', self._on_action),
            ('play-episode', self._on_action),
            ('play-random', self._on_action),
            ('view-details', self._on_action),
            ('open-website', self._on_action),
            ('open-folder', self._on_action),
            ('copy-title', self._on_action),
            ('set-alternative-title', self._on_action),
            ('remove', self._on_action),
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
        succeeded = self.new_account_view.prepare_for(
            provider_name.get_string())

        if succeeded:
            self.leaflet.set_visible_child(self.new_account_view)

    def _on_titles(self, action: Gio.SimpleAction, account_index: GLib.Variant, user_data=None) -> None:
        ''' Show the titles view
        '''
        visible_child = self.leaflet.get_visible_child()

        if visible_child == self.accounts_view:
            self.accounts_view.set_spinning(account_index.get_int32(), True, 1)

        def on_preparation_finished(succeeded: bool, reason: str):
            ''' When the engine has loaded the account make the titles leaflet visible.
                Otherwise show a notification about the error.
            '''
            if succeeded:
                self.leaflet.set_visible_child(self.titles_view)
            else:
                self._show_notification("Unable to open your account", reason)

            if visible_child == self.accounts_view:
                self.accounts_view.set_spinning(
                    account_index.get_int32(), False)

        self.titles_view.prepare_for(
            account_index.get_int32(), on_preparation_finished)

    def _on_about(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Show the about window
        '''
        logger.error('On about action is not implemented')

    def _on_preferences(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Show the preferences window
        '''
        if self._engine is None:
            logger.error(
                'Cannot open the preferences window because the engine has not been started')
        else:
            logger.debug('Here we will show the preferences window')

    def _on_action(self, action: Gio.SimpleAction, parameter: GLib.Variant, user_data=None) -> None:
        ''' Action callback placeholder
            TODO: Delete this method when everything is implemented
        '''
        logger.error('On action callback is not implemented')

    def _show_notification(self, message: str, details: str) -> None:
        logger.error(message)
        toast = Adw.Toast.new(title=message)
        self.toast_overlay.add_toast(toast)

    def _error_dialog(error):
        dialog = Gtk.MessageDialog(
            transient_for=None,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            modal=False,
            text=str(error))
        dialog.connect('response', lambda _dialog, response: _dialog.destroy())
        dialog.show()

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
        builder = Gtk.Builder.new_from_file(get_resource_path('shortcuts.ui'))
        help_overlay = builder.get_object('shortcuts-window')
        self.set_help_overlay(help_overlay)
