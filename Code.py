import asyncio
import random
import ssl
import json
import time
import uuid
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent
import websockets  


async def connect_to_wss(socks5_proxy, user_id):
    user_agent = UserAgent(os=["windows", "macos", "linux"], browsers="chrome")
    random_user_agent = user_agent.random
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))

    urilist = ["wss://proxy2.wynd.network:4444/", "wss://proxy2.wynd.network:4650/"]
    server_hostname = "proxy2.wynd.network"

    while True:
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

                ping_task = asyncio.create_task(send_ping(websocket))
                ping_task.add_done_callback(handle_task_exception)

                while True:
                    try:
                        if websocket.closed:
                            break

                        response = await websocket.recv()
                        message = json.loads(response)

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
                            await websocket.send(json.dumps(auth_response))

                        elif message.get("action") == "PONG":
                            pong_response = {"id": message["id"], "origin_action": "PONG"}
                            await websocket.send(json.dumps(pong_response))

                    except websockets.ConnectionClosedError:
                        break
                    except asyncio.exceptions.CancelledError:
                        break
                    except Exception:
                        break

        except websockets.InvalidStatusCode:
            await asyncio.sleep(5)  # Retry delay
        except Exception:
            await asyncio.sleep(5)  # Retry delay


async def send_ping(websocket):
    try:
        while True:
            send_message = json.dumps(
                {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}}
            )
            await websocket.send(send_message)
            await asyncio.sleep(5)  # Ping interval
    except websockets.ConnectionClosedError:
        pass
    except asyncio.exceptions.CancelledError:
        pass
    except Exception:
        pass


def handle_task_exception(task):
    try:
        task.result()
    except Exception:
        pass


async def main():
    user_id = input("Please Enter your User ID: ")
    try:
        with open("proxies.txt", "r") as file:
            proxies = file.read().splitlines()

        if not proxies:
            return

        tasks = [
            asyncio.create_task(connect_to_wss(proxy, user_id)) for proxy in proxies
        ]
        await asyncio.gather(*tasks)

    except FileNotFoundError:
        pass
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
