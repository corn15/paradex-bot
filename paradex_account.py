from utils import get_account
from typing import Dict

class ParadexAccount:
    def __init__(self, private_key: str, account_address: str, paradex_config: Dict):
        self.account = self._get_account(private_key, account_address, paradex_config)
        self.jwt = None

    def _get_account(self, private_key: str, account_address: str, paradex_config: Dict):
        return get_account(account_address, private_key, paradex_config)

    def update_jwt(self, jwt: str):
        self.jwt = jwt
