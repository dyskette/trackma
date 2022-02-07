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
from gi.repository import GObject
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

class ColumnDescription(NamedTuple):
    name: str
    description: str
    type: type
    is_available: bool
    order: int

class TrackmaColumns(object):

    @property
    def ID(self):
        return ColumnDescription(
            name='id',
            description=None,
            type=int,
            is_available=False,
            order=0
        )

    @property
    def TITLE(self):
        return ColumnDescription(
            name='title',
            description='Title',
            type=str,
            is_available=True,
            order=1
        )

    @property
    def PROGRESS(self):
        return ColumnDescription(
            name='progress',
            description='Progress',
            type=int,
            is_available=True,
            order=2
        )

    @property
    def SCORE(self):
        return ColumnDescription(
            name='score',
            description='Score',
            type=float,
            is_available=True,
            order=3
        )

    @property
    def STAT_TEXT(self):
        return ColumnDescription(
            name='stat-text',
            description=None,
            type=str,
            is_available=False,
            order=4
        )

    @property
    def SCORE_TEXT(self):
        return ColumnDescription(
        name='score-text',
        description=None,
        type=str,
        is_available=False,
        order=5
    )

    @property
    def TOTAL_EPISODES(self):
        return ColumnDescription(
            name='total-episodes',
            description=None,
            type=int,
            is_available=False,
            order=6
        )

    @property
    def SUBVALUE(self):
        return ColumnDescription(
        name='subvalue',
        description=None,
        type=int,
        is_available=False,
        order=7
    )

    @property
    def AVAILABLE_EPISODES(self):
        return ColumnDescription(
            name='available-episodes',
            description=None,
            type=GObject.TYPE_PYOBJECT,
            is_available=False,
            order=8
        )

    @property
    def COLOR(self):
        return ColumnDescription(
        name='color',
        description=None,
        type=str,
        is_available=False,
        order=9
    )

    @property
    def STAT_PERCENTAGE(self):
        return ColumnDescription(
            name='stat-percentage',
            description='Percent',
            type=int,
            is_available=True,
            order=10
        )

    @property
    def START(self):
        return ColumnDescription(
            name='start',
            description='Start',
            type=str,
            is_available=True,
            order=11
        )

    @property
    def END(self):
        return ColumnDescription(
            name='end',
            description='End',
            type=str,
            is_available=True,
            order=12
        )

    @property
    def MY_START(self):
        return ColumnDescription(
            name='my-start',
            description='My start',
            type=str,
            is_available=True,
            order=13
        )

    @property
    def MY_END(self):
        return ColumnDescription(
            name='my-end',
            description='My end',
            type=str,
            is_available=True,
            order=14
        )

    @property
    def MY_STATUS(self):
        return ColumnDescription(
            name='my-status',
            description=None,
            type=int,
            is_available=False,
            order=15
        )

    @property
    def STATUS(self):
        return ColumnDescription(
            name='status',
            description=None,
            type=int,
            is_available=False,
            order=16
        )

    @property
    def ALL_COLUMNS(self):
        return (
            self.ID,
            self.TITLE,
            self.PROGRESS,
            self.SCORE,
            self.STAT_TEXT,
            self.SCORE_TEXT,
            self.TOTAL_EPISODES,
            self.SUBVALUE,
            self.AVAILABLE_EPISODES,
            self.COLOR,
            self.STAT_PERCENTAGE,
            self.START,
            self.END,
            self.MY_START,
            self.MY_END,
            self.MY_STATUS,
            self.STATUS
        )

    @property
    def AVAILABLE_COLUMNS(self):
        return (col for col in self.ALL_COLUMNS if col.is_available)

class TrackmaShowAction(object):
    DETAILS = 'details'
    OPEN_WEBSITE = 'open-website'
    OPEN_FOLDER = 'open-folder'
    COPY_TITLE = 'copy-title'
    CHANGE_ALTERNATIVE_TITLE = 'change-alternative-title'
    REMOVE = 'remove'
    PLAY_NEXT = 'play-next'
    PLAY_EPISODE = 'play-episode'
    PLAY_RANDOM = 'play-random'
    EPISODE_ADD = 'episode-add'
    EPISODE_SET = 'episode-set'
    EPISODE_REMOVE = 'episode-remove'
    SET_SCORE = 'set-score'
    SET_STATUS = 'set-status'

