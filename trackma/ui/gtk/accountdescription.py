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
from loguru import logger
from trackma.accounts import AccountManager
from trackma.ui.gtk.providerdescription import ProviderDescription

class AccountDescription(GObject.Object):

    __gtype_name__ = 'AccountDescription'

    def __init__(self, index: int):
        super().__init__()

        self._index = index
        self._account = self._get_account_details(index)

        if isinstance(self._account, dict):
            self._provider = ProviderDescription(name=self.api)
            self._is_fine = bool(self._provider)
        else:
            self._is_fine = False

    def __bool__(self):
        return self._is_fine

    @property
    def index(self) -> int:
        return self._index

    @property
    def username(self) -> str:
        return self._account.get('username', None)

    @property
    def api(self) -> str:
        return self._account.get('api', None)

    @property
    def provider(self) -> ProviderDescription:
        return self._provider

    def _get_account_details(self, index: int) -> dict:
        account = None

        try:
            account = AccountManager().get_account(index)
        except KeyError:
            logger.error('Account {} does not exist', index)
            return None

        if not isinstance(account, dict):
            logger.error('Cannot read account entry {}, is type {}', index, type(account))
            return None

        return account
