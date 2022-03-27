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
from trackma.accounts import AccountManager
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.accountdescription import AccountDescription
from trackma.ui.gtk.accountrow import TrackmaAccountRow

@Gtk.Template.from_file(get_resource_path('accountsview.ui'))
class TrackmaAccountsView(Gtk.Box):

    __gtype_name__ = 'TrackmaAccountsView'

    view_stack: Adw.ViewStack = Gtk.Template.Child()
    accounts_list: Gtk.ListBox = Gtk.Template.Child()
    new_account_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self):
        ''' Trackma Accounts View class
        '''
        super().__init__()
        self._model = Gio.ListStore.new(AccountDescription)
        self.accounts_list.bind_model(self._model, self._create_account_row)


    def refresh(self):
        ''' Refresh the list of accounts
        '''
        # Reset state...
        self._model.remove_all()

        # Add everything...
        for i, account_dict in AccountManager().get_accounts():
            account = AccountDescription(i)

            if not account:
                continue

            self._model.append(account)

        if self._model.get_n_items() > 0:
            self.view_stack.set_visible_child_name('accounts-page')
        else:
            self.view_stack.set_visible_child_name('welcome-page')

    def remove_account(self, action: Gio.SimpleAction, account_index: GLib.Variant, user_data=None) -> None:
        ''' Callback for remove account action
        '''
        window = Gio.Application.get_default().get_active_window()
        dialog = Gtk.MessageDialog(
            transient_for=window,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text='Remove account?',
            secondary_text='This action will remove your account from Trackma. You can login again later.')
        dialog.add_button('_Cancel', -1)
        dialog.add_button('_Accept', 0)

        def on_response(_dialog: Gtk.MessageDialog, response_id: int, user_data=None) -> None:
            ''' Callback for response dialog signal
            '''
            if response_id == 0:
                AccountManager().delete_account(account_index.get_int32())
                self.refresh()

            dialog.close()

        dialog.connect('response', on_response)
        dialog.show()

    def _create_account_row(self, account):
        return TrackmaAccountRow(account)
