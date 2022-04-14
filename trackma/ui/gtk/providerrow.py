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

from gi.repository import Adw, GLib, Gtk
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.providerdescription import ProviderDescription


@Gtk.Template.from_file(get_resource_path('providerrow.ui'))
class TrackmaProviderRow(Adw.ActionRow):

    __gtype_name__ = 'TrackmaProviderRow'

    provider_logo: Gtk.Picture = Gtk.Template.Child()

    def __init__(self, api: ProviderDescription):
        super().__init__()
        self.api = api
        self.set_title(api.title)
        self.provider_logo.set_filename(api.logo_path)
        self.connect('activated', self._on_activated)

    def _on_activated(self, row, user_data=None):
        self.activate_action(
            'win.new-account', GLib.Variant.new_string(self.api.name))
