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

from gi.repository import Adw, GLib, Gtk
from loguru import logger
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.accountdescription import AccountDescription

@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/accountrow.ui'))
class TrackmaAccountRow(Adw.ActionRow):

    __gtype_name__ = 'TrackmaAccountRow'

    account_logo = Gtk.Template.Child()
    remove_button = Gtk.Template.Child()

    def __init__(self, account: AccountDescription):
        super().__init__()
        self.account = account
        self.set_title(account.username)
        self.set_subtitle(account.provider.title)
        self.account_logo.set_filename(account.provider.logo_path)

    @Gtk.Template.Callback()
    def on_activated(self, row, user_data=None):
        self.activate_action('win.titles', GLib.Variant.new_int32(self.account.index))

    @Gtk.Template.Callback()
    def on_remove_clicked(self, user_data=None):
        self.activate_action('list.remove', GLib.Variant.new_int32(self.account.index))

