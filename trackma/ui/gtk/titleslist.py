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
import time
from gi.repository import Gio, GObject, Gtk
from collections import deque
from loguru import logger
from trackma.engine import Engine
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.titledescription import TrackmaTitleDescription
from trackma.ui.gtk.titlerow import TrackmaTitleRow
from typing import List


class TrackmaTitlesListModel(Gtk.SortListModel):

    __gtype_name__ = 'TrackmaTitlesListModel'

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
        ''' Filter titles based on its attributes (status, search, etc..)
        '''
        return True

    def _sort_func(self, item1: TrackmaTitleDescription, item2: TrackmaTitleDescription, user_data=None) -> int:
        ''' Sort titles based on their title text
        '''
        if item1.title < item2.title:
            return -1
        elif item1.title == item2.title:
            return 0
        else:
            return 1

    def empty(self) -> None:
        self.list_store.remove_all()

    def add_items(self, items: List[TrackmaTitleDescription]) -> None:
        ''' Append more titles into the store
        '''
        for item in items:
            if not item:
                logger.debug(
                    'Title description [{}] is bad, moving on', item.title)
                continue

            self.list_store.append(item)


class LazyLoadingThread(threading.Thread):
    ''' Thread used to load all titles thumbnails

        1. Create an instance and set a timeout
        2. Run the thread
        3. Replace the queue with new items when needed.
        They will be executed after the timeout one by one, first in first out.
    '''

    def __init__(self, timeout: float = None):
        super(LazyLoadingThread, self).__init__()
        self.name = "LazyLoadingThread"
        self.interruption_ocurred = threading.Event()
        self.timeout = 1 if float is None else timeout
        self.queue: deque[TrackmaTitleRow] = deque([])
        self.daemon = True

    def replace(self, rows: List[TrackmaTitleRow]) -> None:
        ''' Replace current queue with a new one
        '''
        self.interruption_ocurred.set()
        self.queue.clear()
        self.queue.extend(rows)

    def run(self):
        ''' Start the thread
        '''
        while True:
            if self.interruption_ocurred.wait(self.timeout):
                self.interruption_ocurred.clear()
            elif len(self.queue) > 0:
                self._execute_queue()

    def _execute_queue(self) -> None:
        ''' Process the current queue
        '''
        while len(self.queue) > 0 and not self.interruption_ocurred.is_set():
            row = self.queue.popleft()
            row.load_cover()


@Gtk.Template.from_file(get_resource_path('titleslist.ui'))
class TrackmaTitlesList(Gtk.Box):

    __gtype_name__ = 'TrackmaTitlesList'

    __gsignals__ = {
        'title-selected': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_INT64,)),
    }

    header_bar: Gtk.HeaderBar = Gtk.Template.Child()
    titles_list: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self):
        ''' Trackma Titles List widget
        '''
        super().__init__()
        self._titles_model = TrackmaTitlesListModel()
        self.titles_list.bind_model(
            self._titles_model, self._create_title_row, None)

        self._covers_thread = LazyLoadingThread(0.2)
        self._covers_thread.start()
        self.titles_list.get_adjustment().connect(
            'value-changed', self._on_user_scroll)
        self.titles_list.connect('row-selected', self._on_title_row_selected)

    def _on_title_row_selected(self, list: Gtk.ListBox, row: TrackmaTitleRow, user_data=None) -> None:
        if row is None:
            return

        self.emit('title-selected', row.description.provider_id)

    def _on_user_scroll(self, adjustment: Gtk.Adjustment, user_data=None) -> None:
        ''' Callback for user scroll
        '''
        self.load_cover_for_visible_rows()

    def load_cover_for_visible_rows(self) -> None:
        ''' Get all visible rows and replace the current queue in the lazy loading thread
        '''
        rows = self.get_visible_rows()
        self._covers_thread.replace(rows)

    def get_visible_rows(self) -> List[TrackmaTitleRow]:
        ''' Lazy loading of visible title rows' covers

            1. Get the first row that is visible, using the scroll position
            3. Iterate for every row and add it to the list that will load images 
               until we get to the last visible row or we are out of rows
        '''
        adjustment = self.titles_list.get_adjustment()
        current_height = adjustment.get_value()
        viewable_end_height = current_height + adjustment.get_page_size()
        end_height = adjustment.get_upper()
        row: TrackmaTitleRow = self.titles_list.get_row_at_y(current_height)

        if row is None:
            logger.debug('No rows at position {} of {}',
                         current_height, end_height)
            return

        current_index = row.get_index()
        rows = []

        while True:
            if not row.cover_loaded:
                rows.append(row)

            if current_height > end_height or current_height > viewable_end_height:
                # This row is the last one visible
                break

            current_height = current_height + row.get_height()
            current_index += 1

            if current_index >= len(self._titles_model):
                # We are out of rows
                break

            row = self.titles_list.get_row_at_index(current_index)

        return rows

    def refresh(self, engine: Engine) -> bool:
        ''' Takes an initialized engine and refreshes the list of titles
        '''
        logger.debug('Titlelist refresh called')
        if not engine.loaded:
            return False

        self._refresh_filters(engine)
        self._refresh_list(engine)

        def start_loading():
            ''' This is sad and has a race condition with the loading of the
                rows widgets in the list

                TODO: Find a way to know when the list is actually showing the
                title rows, either every single row that is shown or everything.
                It doesn't matter.
            '''
            time.sleep(1)
            logger.debug('Here come the row cover')
            self.load_cover_for_visible_rows()

        thread = threading.Thread(target=start_loading, daemon=True)
        thread.start()

        return True

    def _refresh_filters(self, engine: Engine) -> None:
        logger.debug('Refresh filters called')
        self.statuses_num = engine.mediainfo['statuses'].copy()
        self.statuses_names = engine.mediainfo['statuses_dict'].copy()

    def _refresh_list(self, engine: Engine):
        logger.debug('Refresh list called')
        self._titles_model.empty()
        self._titles_model.add_items(
            TrackmaTitleDescription(item) for item in engine.get_list()
        )

    def _create_title_row(self, title: TrackmaTitleDescription, user_data=None):
        return TrackmaTitleRow(title, self.statuses_names)
