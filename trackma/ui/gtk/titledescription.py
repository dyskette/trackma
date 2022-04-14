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

from gi.repository import GObject


class TrackmaTitleDescription(GObject.GObject):

    __gtype_name__ = 'TrackmaTitleDescription'

    def __init__(self, title: dict):
        ''' Trackma Title Description class
        '''
        super().__init__()
        self._title = title

    @property
    def provider_id(self):
        return self._title['id']

    @property
    def title(self):
        return self._title['title']

    @property
    def status(self):
        return self._title['my_status']

    @property
    def image(self):
        return self._title['image']

    @property
    def thumbnail(self):
        return self._title['image_thumb']

    @property
    def user_progress(self):
        return self._title['my_progress']

    @property
    def total(self):
        return self._title['total']

    def __bool__(self):
        return True

    def __eq__(self, other):
        if not isinstance(other, TrackmaTitleDescription):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self.provider_id == other.provider_id
