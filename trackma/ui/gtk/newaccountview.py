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

from gi.repository import Gtk, Gio, GObject
from loguru import logger
from trackma import utils
from trackma.ui.gtk import gtk_dir

class ProviderDescription():
    def __init__(self, libname: str, libimagepath: str):
        ''' Provider Description
        '''
        self.libname = libname
        self.libimagepath = libimagepath

class TrackmaProviderRow(Gtk.ListBoxRow):

    __gtype_name__ = 'TrackmaProviderRow'

    def __init__(self, provider: ProviderDescription):
        ''' Trackma Provider Row
        '''
        super().__init__()
        self.provider = provider

@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/newaccountview.ui'))
class TrackmaNewAccountView(Gtk.Box):

    __gtype_name__ = 'TrackmaNewAccountView'

    offline_label = Gtk.Template.Child()
    providers_listbox = Gtk.Template.Child()

    def __init__(self):
        ''' Trackma New Account class
        '''
        super().__init__()

        for (libname, api) in sorted(utils.available_libs.items()):
            logger.bind(libname=libname, api=api).debug('Appending library')
            self.providers_listbox.append(TrackmaProviderRow(ProviderDescription(
                libname=api[0],
                libimagepath=f'{utils.DATADIR}/{libname}-logo.png'
                )))

        monitor = Gio.NetworkMonitor.get_default()
        monitor.connect('network-changed', self._on_network_changed)

    def _on_network_changed(self, monitor: Gio.NetworkMonitor, available: bool) -> None:
        ''' Change widgets based on network status
        '''
        logger.info('Network status changed to {}', Gio.NetworkConnectivity(monitor.props.connectivity).value_nick)

        self.offline_label.set_visible(available)
        self.providers_listbox.set_sensitive(available)
