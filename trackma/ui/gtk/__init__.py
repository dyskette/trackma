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

class GtkUtils(object):
    @staticmethod
    def create_option_entry(option):
        entry = GLib.OptionEntry()
        entry.long_name = option['long_name']
        entry.short_name = option['short_name']
        entry.flags = option['flags']
        entry.arg = option['arg']
        entry.arg_data = option['arg_data']
        entry.description = option['description']
        entry.arg_description = option['arg_description']
        return entry

    def from_variant(value: GLib.Variant):
        if value is None:
            return None
        if VARIANT_TYPE_INT64.equal(value.get_type()):
            return value.get_int64()
        if VARIANT_TYPE_TUPLE.equal(value.get_type()):
            return (value.get_child_value(0).get_int64(), value.get_child_value(1).get_int64())
        else:
            raise ValueError(f'No mapping declared for value {value}')
