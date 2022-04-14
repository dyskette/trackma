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

import time
import threading
from loguru import logger
from gi.repository import Adw, GLib, Gtk
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.accountdescription import AccountDescription


@Gtk.Template.from_file(get_resource_path('accountrow.ui'))
class TrackmaAccountRow(Adw.ActionRow):

    __gtype_name__ = 'TrackmaAccountRow'

    account_logo: Gtk.Picture = Gtk.Template.Child()
    spinner: Gtk.Spinner = Gtk.Template.Child()

    def __init__(self, account: AccountDescription):
        super().__init__()
        self.account = account
        self.set_title(account.username)
        self.set_subtitle(account.provider.title)
        self.account_logo.set_filename(account.provider.logo_path)
        self.spinner_thread = None

    def set_spinner_visible(self, visible: bool, sleep_seconds: int = None) -> None:
        def set_spinner():
            logger.debug('Spinner visible for this row {}',
                         self.account.username)
            self.spinner.set_visible(True)
            self.spinner.start()

        def sleep_spinner(sleep_seconds):
            time.sleep(sleep_seconds)
            current_thread = threading.currentThread()

            if getattr(current_thread, 'canceled', False):
                logger.debug('Spinner canceled for this row {}',
                             self.account.username)
                return

            GLib.idle_add(
                set_spinner,
                priority=GLib.PRIORITY_LOW)

        if visible:
            if not sleep_seconds:
                sleep_seconds = 0
            self.spinner_thread = threading.Thread(
                target=sleep_spinner, args=[sleep_seconds])
            self.spinner_thread.start()
        else:
            logger.debug('Spinner invisible for this row {}',
                         self.account.username)
            if self.spinner_thread:
                self.spinner_thread.canceled = True
            self.spinner.set_visible(False)
            self.spinner.stop()

    @Gtk.Template.Callback()
    def on_activated(self, row, user_data=None):
        self.activate_action(
            'win.titles', GLib.Variant.new_int32(self.account.index))

    @Gtk.Template.Callback()
    def on_remove_clicked(self, user_data=None):
        self.activate_action(
            'list.remove', GLib.Variant.new_int32(self.account.index))
