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

import gi  # nopep8
import sys

gi.require_version('Gtk', '4.0')  # nopep8
gi.require_version('Adw', '1')  # nopep8

from loguru import logger
from trackma import utils
from trackma.ui.gtk import GtkUtils
from trackma.ui.gtk.window import TrackmaWindow
from gi.repository import GLib, Gio, Adw

class TrackmaApplication(Adw.Application):
    __gtype_name__ = 'TrackmaApplication'

    def __init__(self):
        super().__init__(
            application_id='com.github.z411.TrackmaGtk.Devel',
            flags=Gio.ApplicationFlags.NON_UNIQUE
        )

        self._app_options = [
            { 'long_name': 'debug', 'short_name': ord('d'), 'flags': GLib.OptionFlags.NONE,
            'arg': GLib.OptionArg.NONE, 'arg_data': None,
            'description': 'Show debugging information', 'arg_description' : None }
        ]

        self._app_actions = [
            ( 'quit', self._on_quit_activate ),
        ]

        self._window_accelerators = [
            { 'action': 'win.show-help-overlay', 'accels': ['<Primary>question'] },
            { 'action': 'app.quit', 'accels': ['<Primary>Q'] },
        ]

        self._list_accelerators = [
            { 'action': 'list.search', 'accels': ['<Primary>F'] },
            { 'action': 'list.syncronize', 'accels': ['<Primary>S'] },
            { 'action': 'list.upload', 'accels': ['<Primary>E'] },
            { 'action': 'list.download', 'accels': ['<Primary>D'] },
            { 'action': 'list.scanfiles', 'accels': ['<Primary>L'] },
        ]

        self._show_accelerators = [
            { 'action': 'show.play-next', 'accels': ['<Primary>N'] },
            { 'action': 'show.play-random', 'accels': ['<Primary>R'] },
            { 'action': 'show.episode-add', 'accels': ['<Primary>Right'] },
            { 'action': 'show.episode-remove', 'accels': ['<Primary>Left'] },
            { 'action': 'show.copy-title', 'accels': ['<Primary>C'] },
            { 'action': 'show.remove', 'accels': ['Delete', 'KP_Delete'] },
        ]

        self.log_level = 'INFO'
        self._debug = False
        self._window = None
        self._register_options()
        self._register_actions()

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._register_accelerators()

    def do_activate(self):
        self._create_window()
        self._window.present()

    def do_handle_local_options(self, options: GLib.VariantDict) -> int:
        if options.contains('debug'):
            self.log_level = 'DEBUG'

        format = ('<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
            '<level>{level: <8}</level> | '
            '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n'
            '{extra}')

        logger.remove()
        logger.add(sys.stdout, format=format, level=self.log_level, colorize=True)
        return -1

    def _create_window(self):
        if not self._window:
            self._window = TrackmaWindow(self)

    def _on_quit_activate(self, action, parameter, user_data):
        self._window.quit()

    def _register_options(self):
        entries = [GtkUtils.create_option_entry(option) for option in self._app_options]
        self.add_main_option_entries(entries)

    def _register_actions(self):
        Gio.ActionMap.add_action_entries(self, self._app_actions)

    def _register_accelerators(self):
        for accel in self._window_accelerators:
            self.set_accels_for_action(accel['action'], accel['accels'])

        for accel in self._list_accelerators:
            self.set_accels_for_action(accel['action'], accel['accels'])

        for accel in self._show_accelerators:
            self.set_accels_for_action(accel['action'], accel['accels'])

