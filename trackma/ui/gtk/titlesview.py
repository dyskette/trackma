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
from gi.repository import Adw, GLib, GObject, Gtk
from loguru import logger
from trackma import messenger
from trackma.engine import Engine
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.titledetails import TrackmaTitleDetails
from trackma.ui.gtk.titleslist import TrackmaTitlesList
from typing import Callable


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
        self._engine = None
        self._engine_thread = None

    def prepare_for(self, account: int, on_preparation_finished: Callable[[bool, str], None]) -> None:
        ''' Setup the titles view with all details from a specific account
        '''
        logger.debug('Preparing titles view for account {}', account)

        def callbacks(success: bool, engine: Engine = None, reason: str = None) -> None:
            if success:
                try:
                    self.titles_list.refresh(engine)
                except Exception as e:
                    logger.opt(exception=True).error('Unable to open account')
                    on_preparation_finished(False, str(e))
                    return

            on_preparation_finished(success, reason)

        def engine_start(engine: Engine) -> None:
            try:
                thread = threading.currentThread()

                if getattr(thread, 'canceled', False):
                    return

                engine.start()

                if getattr(thread, 'canceled', False):
                    return

                GLib.idle_add(
                    callbacks, True, engine,
                    priority=GLib.PRIORITY_LOW
                )
            except Exception as e:
                logger.opt(exception=True).error('Unable to open account')
                GLib.idle_add(
                    callbacks, False, None, str(e),
                    priority=GLib.PRIORITY_LOW
                )

        if self._engine_thread:
            self._engine_thread.canceled = True

        self._engine = Engine(
            message_handler=self._message_handler, accountnum=account)
        self._engine_thread = threading.Thread(
            target=engine_start, args=[self._engine])
        self._engine_thread.start()

    def _message_handler(self, classname: str, msgtype: int, msg: str) -> None:
        ''' Handle all messages incoming from the trackma engine class
        '''
        if msgtype == messenger.TYPE_WARN:
            logger.warning('Engine message: {}', msg)
        elif msgtype != messenger.TYPE_DEBUG:
            logger.info('Engine message: {}', msg)
        else:
            logger.debug('Engine message: {}', msg)
