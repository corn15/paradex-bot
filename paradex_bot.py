from typing import List, Dict
import logging
import time
import random
import aiohttp
import asyncio
from paradex_api_client import ParadexAPIClient
from paradex_account import ParadexAccount
from pair_order import PairOrder
from order_manager import OrderManager
from utils import int_from_bytes, build_auth_message, generate_paradex_account

class ParadexBot:
    def __init__(
            self,
            paradex_http_url: str,
            markets: List[str],
            order_size_range: List[int],
            cool_down_time_seconds_between_orders_range: List[int]
    ):
        self.paradex_http_url = paradex_http_url
        self.markets = markets
        self.order_size_range = order_size_range
        self.cool_down_time_seconds_between_orders_range = cool_down_time_seconds_between_orders_range
        self.accounts = []
        self.order_dict = {}

    # These will be initialized in setup()
        self.paradex_config = None
        self.chain_id = None
        self.api_client = None
        self.order_manager = None

    async def setup(self):
        self.api_client = ParadexAPIClient(self.paradex_http_url)
        self.paradex_config = await self.api_client.get_config()
        self.chain_id = int_from_bytes(self.paradex_config["starknet_chain_id"].encode())
        self.order_manager = OrderManager(self.chain_id, self.api_client)

    async def setup_accounts(self, private_keys: List[str]):
        for private_key in private_keys:
            paradex_account_address, paradex_account_private_key_hex = generate_paradex_account(
                self.paradex_config, private_key
            )
            account = ParadexAccount(paradex_account_private_key_hex, paradex_account_address, self.paradex_config)
            jwt = await self._get_jwt_token(account)
            account.update_jwt(jwt)
            self.accounts.append(account)

    async def update_jwt(self, account: ParadexAccount):
        jwt = await self._get_jwt_token(account)
        account.update_jwt(jwt)

    async def _get_jwt_token(self, account: ParadexAccount):
        now = int(time.time())
        expiry = now + 24 * 60 * 60
        message = build_auth_message(self.chain_id, now, expiry)
        sig = account.account.sign_message(message)

        headers: Dict = {
            "PARADEX-STARKNET-ACCOUNT": hex(account.account.address),
            "PARADEX-STARKNET-SIGNATURE": f'["{sig[0]}","{sig[1]}"]',
            "PARADEX-TIMESTAMP": str(now),
            "PARADEX-SIGNATURE-EXPIRATION": str(expiry),
        }

        url = self.paradex_http_url + '/auth'

        logging.info(f"POST {url}")
        logging.info(f"Headers: {headers}")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    logging.info(f"Success: {response}")
                    logging.info("Get JWT successful")
                else:
                    logging.error(f"Status Code: {status_code}")
                    logging.error(f"Response Text: {response}")
                    logging.error("Unable to POST /auth")
                token = response["jwt_token"]
        return token


    async def handle_account_balance(
            self,
            account: ParadexAccount,
            required_value: int
    ) -> None:
        try:
            balance = await self.order_manager.api_client.get_balance(account.jwt)
            # TODO: check this, next???
            usdc_balance = next(
                (float(item["size"]) for item in balance if item["token"] == "USDC"),
                0.0
            )
            if usdc_balance >= required_value:
                return

            logging.info(f"Insufficient USDC balance for account {hex(account.account.address)}, closing positions...")

            open_positions = await self.order_manager.api_client.get_positions(account.jwt)
            for position in open_positions:
                if position["status"] != "OPEN":
                    continue
                symbol = position["market"]
                order_key = f"{symbol}-{hex(account.account.address)}"
                if order_key not in self.order_dict:
                    continue
                order_pair = self.order_dict[order_key]

                try:
                    await self.order_manager.create_and_submit_close_pair_order(order_pair)
                    for account in order_pair.accounts:
                        del self.order_dict[f"{symbol}-{hex(account.account.address)}"]

                    logging.info(f"Closing position {symbol} for account {hex(account.account.address)} successfully")
                except Exception as e:
                    logging.error(f"Failed to close position {symbol} for account {hex(account.account.address)}")
        except Exception as e:
            logging.error(f"Error handling account balance for account {hex(account.account.address)}: {str(e)}")


    def _update_order_dict(self, pair_order: PairOrder) -> None:
        symbol = pair_order.symbol
        to_be_updated = PairOrder(symbol)
        for account in pair_order.accounts:
            if f"{symbol}-{hex(account.account.address)}" not in self.order_dict:
                continue
            to_be_updated = self.order_dict[f"{symbol}-{hex(account.account.address)}"]
        for account in pair_order.accounts:
            to_be_updated.add_account(account)
        for account in to_be_updated.accounts:
            self.order_dict[f"{symbol}-{hex(account.account.address)}"] = to_be_updated

    async def perform_cleanup(self) -> None:
        cleanup_tasks = []
        processed_pairs = set()
        for account in self.accounts:
            try:
                await self.update_jwt(account)
                # Cancel all open orders
                await self.api_client.cancel_orders(account.jwt)
                logging.info(f"Cancelled all open orders for account {hex(account.account.address)}")

                # Close all open positions
                positions = await self.api_client.get_positions(account.jwt)
                for position in positions:
                    if position["status"] != "OPEN":
                        continue

                    symbol = position["market"]
                    order_key = f"{symbol}-{hex(account.account.address)}"
                    if order_key not in self.order_dict:
                        continue
                    order_pair = self.order_dict[order_key]
                    pair_key = f"{symbol}"
                    for account in order_pair.accounts:
                        pair_key += f"-{hex(account.account.address)}"
                    if pair_key in processed_pairs:
                        continue
                    processed_pairs.add(pair_key)
                    cleanup_tasks.append(
                        self._close_position_pair(order_pair)
                    )

            except Exception as e:
                logging.error(f"Cleanup failed for account {hex(account.account.address)}, error: {str(e)}")
        # Execute all cleanup tasks concurrently
        await asyncio.gather(*cleanup_tasks)
        logging.info("Cleanup completed successfully")

    async def _close_position_pair(self, pair_order: PairOrder) -> None:
        try:
            await self.order_manager.create_and_submit_close_pair_order(pair_order)
            for account in pair_order.accounts:
                del self.order_dict[f"{pair_order.symbol}-{hex(account.account.address)}"]
            accounts_str = [hex(account.account.address) for account in pair_order.accounts]
            logging.info(f"Closing position {pair_order.symbol} for account {accounts_str} successfully")
        except Exception as e:
            accounts_str = [hex(account.account.address) for account in pair_order.accounts]
            logging.error(f"Failed to close position {pair_order.symbol} for account {accounts_str}")

    async def run(self, shutdown_event) -> None:
        while not shutdown_event.is_set():
            # randomly select 2 accounts and open long and short orders
            market = random.choice(self.markets)
            size = random.randint(self.order_size_range[0], self.order_size_range[1])
            long_account, short_account = random.sample(self.accounts, 2)
            logging.info(f"Long Account: {hex(long_account.account.address)}, Short Account: {hex(short_account.account.address)}")
            logging.info(f"market: {market}, size: {size}")

            await self.update_jwt(long_account)
            await self.update_jwt(short_account)
            await self.handle_account_balance(long_account, size)
            await self.handle_account_balance(short_account, size)

            pair_order = await self.order_manager.create_and_submit_orders(
                long_account,
                short_account,
                market,
                size
            )
            if pair_order:
                self._update_order_dict(pair_order)

            cool_down_time = random.randint(
                self.cool_down_time_seconds_between_orders_range[0],
                self.cool_down_time_seconds_between_orders_range[1]
            )
            logging.info(f"Cool down time: {cool_down_time} seconds")
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=cool_down_time
                )
            except asyncio.TimeoutError:
                pass

