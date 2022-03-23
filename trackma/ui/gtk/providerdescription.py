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

from loguru import logger
from trackma import utils

class ProviderAuth():
    def __init__(self, url: str, code_verifier: str = None):
        self.url = url
        self.code_verifier = code_verifier

class ProviderDescription():
    def __init__(self, name: str):
        ''' Provider Description
        '''
        if name is None:
            logger.error('The name is empty, please provide a valid library name')
            self._is_fine = False
            return

        if name not in utils.available_libs.keys():
            logger.error('The api {} is not registered in the available libs. Please verify the library name', name)
            self._is_fine = False
            return

        self._name = name
        self._api = utils.available_libs[name]
        self._is_fine = True

    def __bool__(self):
        return self._is_fine

    @property
    def name(self) -> str:
        return self._name

    @property
    def title(self) -> str:
        return self._api[0]

    @property
    def icon_path(self) -> str:
        return self._api[1]

    @property
    def logo_path(self) -> str:
        return '{basedir}/{libname}-logo.png'.format(basedir=utils.DATADIR, libname=self._name)

    @property
    def login_type(self) -> int:
        return self._api[2]

    def get_auth(self) -> ProviderAuth:
        if not self.is_oauth():
            logger.warning('Library is not oauth, as such it cannot have an auth url')
            return None

        auth_url = self._api[3] if len(self._api) > 3 else None

        if auth_url is None:
            logger.error('Auth url is not defined in library')

            return None

        if self.login_type == utils.LOGIN_OAUTH_PKCE:
            code_verifier = utils.oauth_generate_pkce()
            auth_url = auth_url % code_verifier
            return ProviderAuth(auth_url, code_verifier)

        return ProviderAuth(auth_url)

    def is_oauth(self) -> bool:
        return self.login_type in [utils.LOGIN_OAUTH, utils.LOGIN_OAUTH_PKCE]
