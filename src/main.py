from datetime import datetime
import sys
import threading
import time
from typing import Callable, Dict, Optional

from pynput import keyboard

from config import load_config
from constants import SINGLETON_LABEL
from logger import logger
from toasts import ToastManager
from utils import set_dpi_awareness, show_error, windows_console_exit_handler
from wallpaper_changer import WallpaperChanger
from singleton import SingleInstance, SingleInstanceException

if __name__ == "__main__":
    listener: Optional[keyboard.GlobalHotKeys] = None

    try:
        with SingleInstance(SINGLETON_LABEL):
            config = load_config()

            config.cached_wallpapers_path = config.cached_wallpapers_path.resolve()
            if config.default_image:
                config.default_image = config.default_image.resolve()

            if config.show_toasts:
                started_event = threading.Event()
                threading.Thread(
                    target=ToastManager.start_tk_loop,
                    args=(started_event,),
                    daemon=True,
                ).start()
                started_event.wait()

            hotkey_actions: Dict[str, Callable[[], None]] = {}

            changer = WallpaperChanger(config)
            changer.setup_hotkeys(hotkey_actions)

            exit_event = threading.Event()

            windows_console_exit_handler(exit_event)

            for exit_key in config.hotkeys.exit:
                hotkey_actions[exit_key] = exit_event.set

            listener = keyboard.GlobalHotKeys(hotkey_actions)
            listener.start()

            logger.info("Wallpaper changer running")

            try:
                exit_event.wait()
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt")

            logger.info("Exit wallpaper changer")

            listener.stop()
            listener = None

            exit_time = datetime.now()
            if config.show_toasts:
                time.sleep(0.05)
                ToastManager.show("Exit wallpaper changer...", None)

            changer.exit()

            if config.show_toasts:
                elapsed = (datetime.now() - exit_time).total_seconds()
                remaining = 2.05 - elapsed
                if remaining > 0:
                    time.sleep(remaining)

                ToastManager.hide()
    except SingleInstanceException:
        set_dpi_awareness()
        show_error("Already Running", "Konachan Wallpaper Changer is already running!")
        sys.exit(1)
    except Exception as e:
        logger.error(e, exc_info=True)
        set_dpi_awareness()
        show_error("Fatal Error", str(e))
        sys.exit(1)
    finally:
        if listener:
            listener.stop()

        ToastManager.stop_tk_loop()
