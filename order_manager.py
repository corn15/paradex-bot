from paradex_api_client import ParadexAPIClient
from paradex_account import ParadexAccount
from pair_order import PairOrder
import logging
import time
from typing import Dict, List, Optional
from decimal import Decimal
import asyncio
from helpers.account import Account
from shared.paradex_api_utils import Order, OrderSide, OrderType

def round_to_min_order_size(size: float, min_order_size: float) -> float:
    return round(size / min_order_size) * min_order_size

def flatten_signature(sig: list[str]) -> str:
    return f'["{sig[0]}","{sig[1]}"]'

def order_sign_message(chainId: int, o: Order):
    message = {
        "domain": {"name": "Paradex", "chainId": hex(chainId), "version": "1"},
        "primaryType": "Order",
        "types": {
            "StarkNetDomain": [
                {"name": "name", "type": "felt"},
                {"name": "chainId", "type": "felt"},
                {"name": "version", "type": "felt"},
            ],
            "Order": [
                {
                    "name": "timestamp",
                    "type": "felt",
                },  # Time of signature request in ms since epoch; Acts as a nonce;
                {"name": "market", "type": "felt"},  # E.g.: "ETH-USD-PERP"
                {"name": "side", "type": "felt"},  # Buy or Sell
                {"name": "orderType", "type": "felt"},  # Limit or Market
                {"name": "size", "type": "felt"},  # Quantum value with 8 decimals;
                {
                    "name": "price",
                    "type": "felt",
                },  # Quantum value with 8 decimals; Limit price or 0 at the moment of signature
            ],
        },
        "message": {
            "timestamp": str(o.signature_timestamp),
            "market": o.market,  # As encoded short string
            "side": o.order_side.chain_side(),  # 1: BUY, 2: SELL
            "orderType": o.order_type.value,  # As encoded short string
            "size": o.chain_size(),
            "price": o.chain_price(),
        },
    }
    return message


def sign_order(chain_id: int, account: Account, order: Order) -> str:
    message = order_sign_message(chain_id, order)
    sig = account.sign_message(message)
    flat_sig = flatten_signature(sig)
    return flat_sig

class OrderManager:
    def __init__(self, chain_id: int, api_client: ParadexAPIClient):
        self.chain_id = chain_id
        self.api_client = api_client
        self._market_cache = None

    async def _get_min_order_size(self, symbol: str) -> float:
        if not self._market_cache:
            self._market_cache = await self.api_client.get_markets()
        for market in self._market_cache:
            if market["symbol"] == symbol:
                return float(market["order_size_increment"])
        raise Exception(f"Symbol {symbol} not found in markets")

    async def create_and_submit_orders(self, long_acc: ParadexAccount, short_acc: ParadexAccount, symbol: str, value: int) -> Optional[PairOrder]:
        try:
            bid, ask = await self._get_valid_bid_ask(symbol)
            min_size = await self._get_min_order_size(symbol)
            long_size, short_size = self._calculate_order_size(bid, ask, value, min_size)
            long_order = self._build_signed_order(long_acc, OrderType.Market, OrderSide.Buy, Decimal(str(long_size)), symbol, "")
            long_order = self._build_signed_order(long_acc, OrderType.Market, OrderSide.Buy, Decimal(str(long_size)), symbol, "")
            short_order = self._build_signed_order(short_acc, OrderType.Market, OrderSide.Sell, Decimal(str(short_size)), symbol, "")
            await self._submit_orders([long_acc, short_acc], [long_order, short_order])
            pair_order = PairOrder(symbol)
            pair_order.add_account(long_acc)
            pair_order.add_account(short_acc)
            return pair_order

        except Exception as e:
            logging.error(f"Error creating and submitting orders: {str(e)}")
            return None

    async def _get_valid_bid_ask(self, symbol: str) -> tuple[float, float]:
        bbo = await self.api_client.get_bbo(symbol)
        bid, ask = float(bbo["bid"]), float(bbo["ask"])
        if (ask - bid) / bid > 0.005:
            raise Exception("The bid-ask spread is too wide")
        return bid, ask

    def _calculate_order_size(self, bid: float, ask: float, value: int, min_size: float) -> tuple[float, float]:
        if value < 100:
            return 0, 0
        return (
            round_to_min_order_size(value / bid, min_size),
            round_to_min_order_size(value / ask, min_size)
        )

    def _build_signed_order(self, account: ParadexAccount, order_type: OrderType, order_side: OrderSide, size: Decimal, market: str, client_id: str) -> Order:
        order = Order(
            market=market,
            order_type=order_type,
            order_side=order_side,
            size=size,
            client_id=client_id,
            signature_timestamp=int(time.time()*1000),
        )
        sig = sign_order(self.chain_id, account.account, order)
        order.signature = sig
        return order

    async def _submit_orders(self, accounts: List[ParadexAccount], orders: List[Order]) -> Dict:
        await asyncio.gather(
            *[self.api_client.post_order(account.jwt, order.dump_to_dict()) for account, order in zip(accounts, orders)]
        )

    def _build_close_order(self, account: ParadexAccount, positions: List[Dict], symbol: str) -> Order:
        for position in positions:
            if position["market"] == symbol and position["status"] == "OPEN":
                side = OrderSide.Sell if position["side"] == "LONG" else OrderSide.Buy
                size = Decimal(str(abs(float(position["size"]))))
                return self._build_signed_order(
                    account=account, 
                    order_type=OrderType.Market, 
                    order_side=side, 
                    size=size, 
                    market=symbol, 
                    client_id=""
                )
        return None

    async def create_and_submit_close_pair_order(self, pair_order: PairOrder) -> tuple[Order, Order]:
        try:
            close_orders = []
            close_accounts = []
            for account in pair_order.accounts:
                open_positions = await self.api_client.get_positions(account.jwt)
                close_order = self._build_close_order(account, open_positions, pair_order.symbol)
                if close_order:
                    close_orders.append(close_order)
                    close_accounts.append(account)
            await self._submit_orders(close_accounts, close_orders)
        except Exception as e:
            logging.error(f"Error creating and submitting close orders: {str(e)}")
            return None, None
