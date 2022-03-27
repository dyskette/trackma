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

from gi.repository import Adw, GObject, Gtk
from loguru import logger
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.titledetails import TrackmaTitleDetails
from trackma.ui.gtk.titleslist import TrackmaTitlesList

@Gtk.Template.from_file(get_resource_path('titlesview.ui'))
class TrackmaTitlesView(Gtk.Box):

    __gtype_name__ = 'TrackmaTitlesView'

    leaflet: Adw.Leaflet = Gtk.Template.Child()
    titles_list: TrackmaTitlesList = Gtk.Template.Child()
    title_details: TrackmaTitleDetails = Gtk.Template.Child()

    def __init__(self):
        ''' Trackma Titles View
        '''
        super().__init__()

        self.leaflet.bind_property('folded',
            self.titles_list.header_bar, 'show-end-title-buttons',
            GObject.BindingFlags.DEFAULT)
        self.leaflet.bind_property('folded',
            self.title_details.back_button, 'visible',
            GObject.BindingFlags.DEFAULT)
