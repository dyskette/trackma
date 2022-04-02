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

from gi.repository import Gio, Gtk
from loguru import logger
from trackma.engine import Engine
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.titledescription import TrackmaTitleDescription
from trackma.ui.gtk.titlerow import TrackmaTitleRow

@Gtk.Template.from_file(get_resource_path('titleslist.ui'))
class TrackmaTitlesList(Gtk.Box):

    __gtype_name__ = 'TrackmaTitlesList'

    header_bar: Gtk.HeaderBar = Gtk.Template.Child()
    titles_list: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self):
        ''' Trackma Titles List widget
        '''
        super().__init__()
        self._library = None
        self._titles = []
        self._model = Gio.ListStore.new(TrackmaTitleDescription)
        self.titles_list.bind_model(self._model, self._create_title_row)

    def refresh(self, engine: Engine) -> bool:
        ''' Takes an initialized engine and refreshes the list of titles
        '''
        if not engine.loaded:
            return False

        self._refresh_filters(engine)
        self._refresh_list(engine)

        return True

    def _refresh_filters(self, engine: Engine) -> None:
        self.statuses_num = engine.mediainfo['statuses'].copy()
        self.statuses_names = engine.mediainfo['statuses_dict'].copy()

    def _refresh_list(self, engine: Engine):
        self._items = [TrackmaTitleDescription(item) for item in engine.get_list()]
        self._items.sort(key=lambda item: (item.title.casefold(), item.title))
        self._model.remove_all()

        for item in self._items:
            if not item:
                logger.debug('Title description [{}] is bad, moving on', item.title)
                continue

            self._model.append(item)

        self.titles_list.set_filter_func(self._filter_func, None, self._destroy_notif)

    def _filter_func(self, row: TrackmaTitleRow, user_data=None, titles_list=None) -> bool:
        return True

    def _destroy_notif(self, data=None) -> None:
        pass

    def _create_title_row(self, title: TrackmaTitleDescription):
        return TrackmaTitleRow(title)
