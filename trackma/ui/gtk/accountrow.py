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
from trackma.ui.gtk import gtk_dir

@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/accountrow.ui'))
class TrackmaAccountRow(Adw.ActionRow):

    __gtype_name__ = 'TrackmaAccountRow'

    click_gesture = Gtk.Template.Child()
    account_logo = Gtk.Template.Child()

    def __init__(self, id, username, libname, libimagepath):
        super().__init__()
        self.id = id
        self.set_title(username)
        self.set_subtitle(libname)
        self.account_logo.set_filename(libimagepath)

    @Gtk.Template.Callback()
    def _on_account_clicked(self, gesture, n_press, x, y):
        self.activate_action('win.titles', GLib.Variant.new_int32(self.id))

