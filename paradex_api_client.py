import aiohttp
from typing import Dict, List
import logging

class ParadexAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def _request(
            self, method: str, endpoint: str,
            jwt: str = None, payload: Dict = None
    ) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, json=payload) as response:
                return await response.json()

    async def get_config(self) -> Dict:
        return await self._request("GET", "system/config", None, None)

    async def post_order(self, jwt: str, payload: Dict) -> Dict:
        return await self._request("POST", "orders", jwt, payload)

    async def get_positions(self, jwt: str) -> Dict:
        response = await self._request("GET", "positions", jwt, None)
        return response["results"]

    async def get_account(self, jwt: str) -> Dict:
        return await self._request("GET", "account", jwt, None)

    async def get_bbo(self, symbol: str) -> Dict:
        return await self._request("GET", f"bbo/{symbol}", None, None)

    async def get_markets(self) -> List[Dict]:
        response = await self._request("GET", "markets", None, None)
        return response["results"]

    async def get_balance(self, jwt: str) -> Dict:
        response = await self._request("GET", "balance", jwt, None)
        logging.debug(f"response: {response}")
        return response["results"]

    async def cancel_orders(self, jwt: str) -> Dict:
        return await self._request("DELETE", "orders", jwt, None)

    async def get_free_collateral(self, jwt: str) -> float:
        balance = await self.get_balance(jwt)
        for item in balance:
            if item["token"] == "USDC":
                return float(item["size"])
        return 0
