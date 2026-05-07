import argparse
import json
import sys
import threading
import time

from src.core.logger import Logger
from src.core.plugin import Plugin


def main():
    Logger.info("TAUSIK Init plugin start")
    parser = argparse.ArgumentParser(description='TAUSIK Init StreamDock plugin')
    parser.add_argument('-port', type=int, required=True, help='WebSocket port')
    parser.add_argument('-pluginUUID', type=str, required=True, help='Plugin UUID')
    parser.add_argument('-registerEvent', type=str, required=True, help='Registration event')
    parser.add_argument('-info', type=str, required=True, help='Device/StreamDock JSON')
    args = parser.parse_args()

    try:
        info = json.loads(args.info) if args.info else {}
    except json.JSONDecodeError:
        info = {}

    try:
        time.sleep(1)
        plugin = Plugin(args.port, args.pluginUUID, args.registerEvent, info)
        stop_event = threading.Event()

        def on_close(ws, close_status_code, close_msg):
            plugin.stop()
            stop_event.set()
            Logger.info('Plugin stopped')

        plugin.ws.on_close = on_close
        stop_event.wait()
    except Exception as exc:
        Logger.error(f"Plugin crashed: {exc}")
        sys.exit(0)


if __name__ == '__main__':
    main()
