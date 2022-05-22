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

from threading import Thread
import requests
from loguru import logger
from gi.repository import Gio, GLib, Gtk, GdkPixbuf
from trackma.ui.gtk import get_resource_path
from trackma.ui.gtk.titledescription import TrackmaTitleDescription


@Gtk.Template.from_file(get_resource_path('titlerow.ui'))
class TrackmaTitleRow(Gtk.ListBoxRow):

    __gtype_name__ = 'TrackmaTitleRow'

    title: Gtk.Label = Gtk.Template.Child()
    status: Gtk.Label = Gtk.Template.Child()
    cover_revealer: Gtk.Stack = Gtk.Template.Child()
    cover: Gtk.Picture = Gtk.Template.Child()
    progressbar: Gtk.ProgressBar = Gtk.Template.Child()

    def __init__(self, description: TrackmaTitleDescription, status_names: dict):
        ''' Trackma Title Row class
        '''
        super().__init__()
        self.description = description
        self.title.set_label(self.description.title)
        self.cover.set_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(
            get_resource_path('placeholder-no-image.png'),
            60,
            height=-1,
            preserve_aspect_ratio=True
        ))
        self.status.set_label(status_names[self.description.status])
        self.set_progress_bar()
        self.cover_thread = None
        self.cover_loaded = False

    def set_progress_bar(self) -> None:
        fraction = self.description.user_progress / self.description.total
        self.progressbar.set_fraction(fraction)

    def load_cover(self) -> None:
        ''' Load cover image in the title row
        '''
        def set_cover():
            try:
                pixbuf = self._get_pixbuf(self._download_thumbnail(), 60)

                if pixbuf:
                    GLib.idle_add(self.cover.set_pixbuf, pixbuf,
                                  priority=GLib.PRIORITY_LOW)
                    self.cover_loaded = True
            except Exception as e:
                logger.opt(exception=True).error(
                    'Failure for image {}', self.description.thumbnail)

            GLib.idle_add(self.cover_revealer.set_reveal_child, True,
                          priority=GLib.PRIORITY_LOW)

        if self.cover_thread is None:
            self.cover_thread = Thread(
                name="LoadCoverThread_" + self.description.title, target=set_cover, daemon=True)
            self.cover_thread.start()

    def _download_thumbnail(self) -> bytes:
        ''' Download the title's thumbnail file
        '''
        response = requests.get(self.description.thumbnail)

        if response.status_code != 200:
            logger.warn('Could not download image. Status {}',
                        response.status_code)
            return None

        return response.content

    def _get_pixbuf(self, image_bytes: bytes, width: int) -> GdkPixbuf.Pixbuf:
        ''' Convert a python image from bytes to a GdkPixbuf.Pixbuf
        '''
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

    def _save_image(self, img_bytes):
        if imaging_available:
            image = Image.open(img_bytes)
            image.thumbnail((self._width, self._height), Image.ANTIALIAS)
            image.convert("RGB").save(self._filename)
        else:
            with open(self._filename, 'wb') as img_file:
                img_file.write(img_bytes.read())
