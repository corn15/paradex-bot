import asyncio
import logging
import os
import traceback
from typing import Dict
import json
from paradex_bot import ParadexBot
import signal

def read_config(file_path: str) -> Dict:
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def read_private_keys(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        # Strip whitespace and newline characters from each line
        return [line.strip() for line in file.readlines() if line.strip()]

def signal_handler(shutdown_event):
    shutdown_event.set()

async def main():
    logging.basicConfig(
        level=os.getenv("LOGGING_LEVEL", "INFO"),
        format="%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = read_config('config.json')
    private_keys = read_private_keys('.secrets')

    bot = ParadexBot(
        paradex_http_url=config['paradex_http_url'],
        markets=config['markets'],
        order_size_range=config['order_size_range'],
        cool_down_time_seconds_between_orders_range=config['cool_down_time_seconds_between_orders_range']
    )
    await bot.setup()
    await bot.setup_accounts(private_keys)

    shutdown_event = asyncio.Event()

    # Set up signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT):
        loop.add_signal_handler(sig, shutdown_event.set)

    try:
        await bot.run(shutdown_event)
    except Exception as e:
        logging.error("Main Error")
        logging.error(e)
        traceback.print_exc()
    finally:
        await bot.perform_cleanup()

if __name__ == "__main__":
    asyncio.run(main())
