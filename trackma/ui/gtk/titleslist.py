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

import threading
import queue
from gi.repository import Gio, Gtk
from loguru import logger
from trackma.engine import Engine
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.titledescription import TrackmaTitleDescription
from trackma.ui.gtk.titlerow import TrackmaTitleRow
from typing import List


class TrackmaTitlesListModel(Gtk.SortListModel):
    def __init__(self):
        self.list_store = Gio.ListStore(item_type=TrackmaTitleDescription)

        self.filter = Gtk.CustomFilter()
        self.filter.set_filter_func(self._filter_func)

        self.filter_store = Gtk.FilterListModel(
            model=self.list_store, filter=self.filter
        )

        self.sorter = Gtk.CustomSorter()
        self.sorter.set_sort_func(self._sort_func)

        super().__init__(model=self.filter_store, sorter=self.sorter)

    def _filter_func(self, item: TrackmaTitleDescription, user_data=None) -> bool:
        return True

    def _sort_func(self, item1: TrackmaTitleDescription, item2: TrackmaTitleDescription, user_data=None) -> int:
        if item1.title < item2.title:
            return -1
        elif item1.title == item2.title:
            return 0
        else:
            return 1

    def empty(self) -> None:
        self.list_store.remove_all()

    def add_items(self, items: List[TrackmaTitleDescription]) -> None:
        for item in items:
            if not item:
                logger.debug(
                    'Title description [{}] is bad, moving on', item.title)
                continue

            self.list_store.append(item)


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
        self._titles_model = TrackmaTitlesListModel()
        self.titles_list.bind_model(
            self._titles_model, self._create_title_row, None)
        self._queue = queue.Queue()
        self._thread = self._create_thread(self._queue)

    def refresh(self, engine: Engine) -> bool:
        ''' Takes an initialized engine and refreshes the list of titles
        '''
        logger.debug('Titlelist refresh called')
        if not engine.loaded:
            return False

        self._refresh_filters(engine)
        self._refresh_list(engine)

        return True

    def _refresh_filters(self, engine: Engine) -> None:
        logger.debug('Refresh filters called')
        self.statuses_num = engine.mediainfo['statuses'].copy()
        self.statuses_names = engine.mediainfo['statuses_dict'].copy()

    def _refresh_list(self, engine: Engine):
        logger.debug('Refresh list called')
        self._items = [TrackmaTitleDescription(
            item) for item in engine.get_list()]
        self._titles_model.empty()
        self._titles_model.add_items(self._items)
        for i in range(20):
            self._queue.put(self.titles_list.get_row_at_index(i))

    def _create_title_row(self, title: TrackmaTitleDescription, user_data=None):
        row = TrackmaTitleRow(title, self.statuses_names)
        return row

    def worker(self, q: queue.Queue):
        while True:
            row: TrackmaTitleRow = q.get()
            row.load_cover()
            q.task_done()

    def _create_thread(self, q: queue.Queue):
        thread = threading.Thread(target=self.worker, args=[q], daemon=True)
        thread.start()
        return thread
