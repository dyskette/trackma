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
from typing import NamedTuple
from gi.repository import GObject, GLib
gtk_dir = os.path.dirname(__file__)

def main():
    import signal
    import sys
    from trackma import utils
    from .application import TrackmaApplication

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    print("Trackma GTK v{}".format(utils.VERSION))
    app = TrackmaApplication()
    sys.exit(app.run(sys.argv))

def get_resource_path(ending: str) -> str:
    ''' Get gtk resource path
    '''
    return os.path.join(os.path.dirname(__file__), 'data', ending)

def from_variant(value: GLib.Variant) -> any:
    ''' Get python real value from a GLib.Variant type
    '''
    glib_type_getters = {
        'd': GLib.Variant.get_double,
        'b': GLib.Variant.get_boolean,
        'x': GLib.Variant.get_int64,
        's': GLib.Variant.get_string,
    }

    if value is None:
        return None
    elif value.get_type() not in glib_type_getters.keys():
        raise ValueError(f'No mapping declared for value {value}')
    else:
        return glib_type_getters[value.get_type()](value)

def create_option_entry(option: dict) -> GLib.OptionEntry:
    ''' Create a GLib.OptionEntry using a dictionary description
    '''
    entry = GLib.OptionEntry()
    entry.long_name = option['long_name']
    entry.short_name = option['short_name']
    entry.flags = option['flags']
    entry.arg = option['arg']
    entry.arg_data = option['arg_data']
    entry.description = option['description']
    entry.arg_description = option['arg_description']
    return entry

