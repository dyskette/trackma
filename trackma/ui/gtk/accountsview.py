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

import logging
import os

from gi.repository import Gtk, Gio
from loguru import logger
from trackma import utils
from trackma.accounts import AccountManager
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.accountrow import TrackmaAccountRow

@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/accountsview.ui'))
class TrackmaAccountsView(Gtk.Box):

    __gtype_name__ = 'TrackmaAccountsView'

    accounts_list = Gtk.Template.Child()
    new_account_button = Gtk.Template.Child()

    def __init__(self):
        ''' Trackma Accounts View class
        '''
        super().__init__()

    def refresh(self):
        ''' Refresh the list of accounts
        '''
        # Remove anything leftover...
        while self.accounts_list.get_row_at_index(0) is not None:
            row = self.accounts_list.remove(self.accounts_list.get_row_at_index(0))

        # Adding everything...
        for i, account in AccountManager().get_accounts():
            if type(account) is not dict:
                logger.warning('Cannot read account entry {}, is type {}', i, type(account))
                continue

            api = utils.available_libs[account['api']] if account['api'] in utils.available_libs else None

            if api is None:
                logger.bind(**account).warning('Account has unsupported api')
                continue

            log = logger.bind(**{x: account[x] for x in account if x != 'password'})
            log.debug('Setting up row for account')

            row = TrackmaAccountRow(
                id=i,
                username=account['username'],
                libname=api[0],
                libimagepath='{0}/{1}-logo.png'.format(utils.DATADIR, account['api']))

            self.accounts_list.append(row)
