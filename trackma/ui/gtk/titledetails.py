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

import requests
from loguru import logger
from gi.repository import Adw, GdkPixbuf, Gio, GLib, Gtk
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.titledescription import TrackmaTitleDescription
from trackma.engine import Engine


@Gtk.Template.from_file(get_resource_path('titledetails.ui'))
class TrackmaTitleDetails(Gtk.Box):

    __gtype_name__ = 'TrackmaTitleDetails'

    header_bar: Gtk.HeaderBar = Gtk.Template.Child()
    back_button: Gtk.Button = Gtk.Template.Child()
    view_stack: Adw.ViewStack = Gtk.Template.Child()
    cover: Gtk.Picture = Gtk.Template.Child()
    title: Gtk.Label = Gtk.Template.Child()

    def __init__(self):
        super().__init__()
        self.description: TrackmaTitleDescription = None

    def prepare_for(self, engine: Engine, provider_id: int) -> None:
        logger.bind(**{
            'show': engine.get_show_info(provider_id),
            'details': engine.get_show_details(engine.get_show_info(provider_id))
            }).debug('Preparing details for show')
        self.description = TrackmaTitleDescription(engine.get_show_info(provider_id))
        self.title.set_label(self.description.title)
        self.cover.set_pixbuf(self._get_pixbuf(self._download_file(), 120))
        self.view_stack.set_visible_child_name('details')

    def _download_file(self) -> bytes:
        response = requests.get(self.description.image)

        if response.status_code != 200:
            logger.warn('Could not download image. Status {}',
                        response.status_code)
            return None

        return response.content

    def _get_pixbuf(self, image_bytes: bytes, width: int) -> GdkPixbuf.Pixbuf:
        if not image_bytes:
            return None

        glib_bytes = GLib.Bytes(image_bytes)
        memory_stream = Gio.MemoryInputStream.new_from_bytes(glib_bytes)

        return GdkPixbuf.Pixbuf.new_from_stream_at_scale(
            memory_stream,
            width,
            height=-1,
            preserve_aspect_ratio=True
        )
