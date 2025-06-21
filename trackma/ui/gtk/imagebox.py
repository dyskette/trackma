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
import urllib.request
from io import BytesIO

from gi.repository import GLib, Gtk

from trackma import utils

class ImageThread(threading.Thread):
    def __init__(self, url, filename, callback):
        threading.Thread.__init__(self)
        self._url = url
        self._filename = filename
        self._callback = callback
        self._stop_request = threading.Event()

    def run(self):
        img_bytes = self._download_file()

        with open(self._filename, 'wb') as img_file:
            img_file.write(img_bytes.read())

        if self._stop_request.is_set():
            return

        if os.path.exists(self._filename):
            GLib.idle_add(self._callback, self._filename)

    def _download_file(self):
        request = urllib.request.Request(self._url)
        request.add_header(
            "User-Agent", "TrackmaImage/{}".format(utils.VERSION))
        return BytesIO(urllib.request.urlopen(request).read())

    def stop(self):
        self._stop_request.set()


class ImageBox(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self._image_thread = None
        self._image = Gtk.Picture()
        self._label_holder = Gtk.Label()

        self.append(self._label_holder)
        self.append(self._image)

        self.reset()

    def reset(self):
        self.set_image(utils.DATADIR + '/icon.png')

    def set_text(self, text):
        self._label_holder.set_text(text)
        self._label_holder.set_visible(True)
        self._image.set_visible(False)

    def set_image(self, filename):
        self._image.set_filename(filename)
        self._image.set_visible(True)
        self._label_holder.set_visible(False)

    def set_image_remote(self, url, filename):
        if self._image_thread:
            self._image_thread.stop()

        self.set_text("Loading...")
        self._image_thread = ImageThread(
            url, filename, self.set_image)
        self._image_thread.start()

def scale(w, h, x, y, maximum=True):
    nw = y * w / h
    nh = x * h / w
    if maximum ^ (nw >= x):
        return nw or 1, y
    return x, nh or 1
