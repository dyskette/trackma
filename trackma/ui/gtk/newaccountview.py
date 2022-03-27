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

from gi.repository import Adw, Gtk, Gdk, Gio, GLib
from loguru import logger
from trackma.accounts import AccountManager
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.providerdescription import ProviderDescription

@Gtk.Template.from_file(get_resource_path('newaccountview.ui'))
class TrackmaNewAccountView(Gtk.Box):

    __gtype_name__ = 'TrackmaNewAccountView'

    save_button: Gtk.Button = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()
    standard_username: Gtk.Entry = Gtk.Template.Child()
    standard_password: Gtk.Entry = Gtk.Template.Child()
    oauth_username: Gtk.Entry = Gtk.Template.Child()
    oauth_pin: Gtk.Entry = Gtk.Template.Child()
    oauth_pin_url: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self):
        ''' Trackma New Account View class
        '''
        super().__init__()

    def prepare_for(self, libname: str) -> bool:
        ''' Prepare the new account view for the library specified
        '''
        self.provider = ProviderDescription(libname)

        if not self.provider:
            return False

        self.clear_all_fields()

        if self.provider.is_oauth():
            self.auth = self.provider.get_auth()

            if self.auth is not None:
                self.oauth_pin_url.set_subtitle(GLib.markup_escape_text(self.auth.url))

            self.stack.set_visible_child_name('oauth-page')
        else:
            self.stack.set_visible_child_name('password-page')

        return True

    def clear_all_fields(self) -> None:
        ''' Clear all fields in the view
        '''
        self.standard_username.set_text('')
        self.standard_password.set_text('')
        self.oauth_username.set_text('')
        self.oauth_pin.set_text('')

    @Gtk.Template.Callback()
    def on_pin_url_activated(self, row: Adw.ActionRow) -> None:
        Gtk.show_uri(Gio.Application.get_default().get_active_window(), self.auth.url, Gdk.CURRENT_TIME)

    @Gtk.Template.Callback()
    def on_entry_changed(self, entry: Gtk.Entry, user_data=None) -> None:
        ''' Callback for changed signal for all entries in the view
        '''
        has_content = False

        if self.provider.is_oauth():
            has_content = len(self.oauth_username.get_text()) > 0 and len(self.oauth_pin.get_text()) > 0
        else:
            has_content = len(self.standard_username.get_text()) > 0 and len(self.standard_password.get_text()) > 0

        self.save_button.set_sensitive(has_content)

    @Gtk.Template.Callback()
    def on_save_button_clicked(self, button: Gtk.Button, user_data=None) -> None:
        logger.debug('Save button clicked')

        if self.provider.is_oauth():
            AccountManager().add_account(
                self.oauth_username.get_text().strip(),
                self.oauth_pin.get_text(),
                self.provider.name,
                { 'code_verifier': self.auth.code_verifier })
        else:
            AccountManager().add_account(
                self.standard_username.get_text().strip(),
                self.standard_password.get_text(),
                self.provider.name,
                {})

        self.activate_action('win.accounts')
