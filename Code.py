import asyncio
import random
import ssl
import json
import time
import uuid
import signal
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent
import websockets

# Global variable to signal shutdown
stop_event = asyncio.Event()

async def connect_to_wss(socks5_proxy, user_id):
    user_agent = UserAgent(os=["windows", "macos", "linux"], browsers="chrome")
    random_user_agent = user_agent.random
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(f"Generated Device ID: {device_id}")

    urilist = ["wss://proxy2.wynd.network:4444/", "wss://proxy2.wynd.network:4650/"]
    server_hostname = "proxy2.wynd.network"

    while not stop_event.is_set():
        try:
            await asyncio.sleep(random.uniform(0.1, 1))  # Random delay before connecting
            custom_headers = {"User-Agent": random_user_agent}
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            uri = random.choice(urilist)
            proxy = Proxy.from_url(socks5_proxy)

            async with proxy_connect(
                uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname, extra_headers=custom_headers
            ) as websocket:
                logger.info(f"Connected to WebSocket: {uri}")

                while not stop_event.is_set():
                    try:
                        response = await websocket.recv()
                        message = json.loads(response)
                        logger.info(f"Received message: {message}")

                        if message.get("action") == "AUTH":
                            auth_response = {
                                "id": message["id"],
                                "origin_action": "AUTH",
                                "result": {
                                    "browser_id": device_id,
                                    "user_id": user_id,
                                    "user_agent": custom_headers["User-Agent"],
                                    "timestamp": int(time.time()),
                                    "device_type": "desktop",
                                    "version": "4.29.0",
                                },
                            }
                            logger.debug(f"Sending AUTH response: {auth_response}")
                            await websocket.send(json.dumps(auth_response))

                        elif message.get("action") == "PONG":
                            pong_response = {"id": message["id"], "origin_action": "PONG"}
                            logger.debug(f"Sending PONG response: {pong_response}")
                            await websocket.send(json.dumps(pong_response))

                    except websockets.ConnectionClosedError as e:
                        logger.warning(f"WebSocket connection closed: {e}")
                        break
                    except asyncio.CancelledError:
                        logger.warning("Task was cancelled.")
                        break
                    except Exception as e:
                        logger.error(f"Unexpected error in WebSocket loop: {e}")
                        break

        except websockets.InvalidStatusCode as e:
            logger.error(f"WebSocket handshake failed with status code: {e.status_code}")
            await asyncio.sleep(5)  # Retry delay
        except Exception as e:
            logger.error(f"Error during WebSocket connection: {e}")
            await asyncio.sleep(5)  # Retry delay


async def main():
    user_id = input("Please Enter your User ID: ")
    try:
        with open("proxies.txt", "r") as file:
            proxies = file.read().splitlines()

        if not proxies:
            logger.error("No proxies found in 'proxies.txt'. Exiting.")
            return

        tasks = [connect_to_wss(proxy, user_id) for proxy in proxies]

        # Run all tasks until stop_event is set
        await asyncio.gather(*tasks)

    except FileNotFoundError:
        logger.error("The 'proxies.txt' file was not found.")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")


def handle_shutdown():
    """Set the stop_event and stop all tasks."""
    logger.info("Received exit signal. Shutting down...")
    stop_event.set()


if __name__ == "__main__":
    logger.add("debug.log", level="DEBUG")

    # Setup signal handlers for Ctrl+C and termination signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown)

    try:
        loop.run_until_complete(main())
    finally:
        # Cancel all tasks and clean up
        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.close()
        logger.info("Program terminated cleanly.")
