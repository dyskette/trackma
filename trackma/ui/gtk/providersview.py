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

from gi.repository import Gtk
from trackma import utils
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.providerdescription import ProviderDescription
from trackma.ui.gtk.providerrow import TrackmaProviderRow


@Gtk.Template.from_file(get_resource_path('providersview.ui'))
class TrackmaProvidersView(Gtk.Box):

    __gtype_name__ = 'TrackmaProvidersView'

    providers_listbox: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self):
        ''' Trackma New Account class
        '''
        super().__init__()

        for libname in sorted(utils.available_libs.keys()):
            provider = ProviderDescription(libname)

            if not provider:
                continue

            self.providers_listbox.append(TrackmaProviderRow(provider))
