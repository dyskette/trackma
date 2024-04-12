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
import threading
import requests
from collections.abc import Callable
from gi.repository import GLib, Gtk, Gdk
from trackma import utils
from trackma.ui.gtk import gtk_dir


@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/imagebox.ui'))
class ImageBox(Gtk.Box):
    __gtype_name__ = 'ImageBox'

    label: Gtk.Label = Gtk.Template.Child()
    image: Gtk.Picture = Gtk.Template.Child()

    def __init__(self) -> None:
        super().__init__()

        self._image_thread = None

    def do_realize(self) -> None:
        width, height = self.get_size_request()
        self.label.set_size_request(width, height)
        self.image.set_size_request(width, height)

    def reset(self) -> None:
        self.set_image(utils.DATADIR + '/icon.png')

    def set_text(self, text: str) -> None:
        self.label.set_text(text)
        self.label.set_visible(True)
        self.image.set_visible(False)

    def set_image(self, filename: str) -> None:
        texture = Gdk.Texture.new_from_filename(filename)
        self.image.set_paintable(texture)
        self.image.set_visible(True)
        self.label.set_visible(False)

    def set_image_remote(self, url: str, filename: str) -> None:
        if self._image_thread:
            self._image_thread.stop()

        self.set_text("Loading...")
        self._image_thread = ImageThread(url, filename, self.set_image)
        self._image_thread.start()


class ImageThread(threading.Thread):
    def __init__(self, url: str, filename: str, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._url = url
        self._headers = {"user-agent": "TrackmaImage/{}".format(utils.VERSION)}
        self._filename = filename
        self._callback = callback
        self._stop_request = threading.Event()

    def run(self) -> None:
        self._download_file()

        if self._stop_request.is_set():
            return

        if os.path.exists(self._filename):
            GLib.idle_add(self._callback, self._filename)

    def _download_file(self) -> None:
        r = requests.get(self._url, self._headers)

        with open(self._filename, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=128):
                fd.write(chunk)

    def stop(self) -> None:
        self._stop_request.set()
