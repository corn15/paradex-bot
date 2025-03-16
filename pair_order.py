from paradex_account import ParadexAccount

class PairOrder:
    def __init__(self, symbol: str):
        self.accounts = set()
        self.symbol = symbol

    def add_account(self, account: ParadexAccount):
        self.accounts.add(account)
