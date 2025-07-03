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
from utils import set_dpi_awareness, show_error
from wallpaper_changer import WallpaperChanger
from singleton import SingleInstance, SingleInstanceException

if __name__ == "__main__":
    listener: Optional[keyboard.GlobalHotKeys] = None

    try:
        with SingleInstance(SINGLETON_LABEL):
            config = load_config()

            config.wallpapers_folder_path = config.wallpapers_folder_path.resolve()
            if config.default_image:
                config.default_image = config.default_image.resolve()

            exit_event = threading.Event()

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

            exit_key = config.hotkeys.exit
            hotkey_actions[exit_key] = lambda: exit_event.set()

            listener = keyboard.GlobalHotKeys(hotkey_actions)
            listener.start()

            logger.info(f"Wallpaper changer running. Press {exit_key} to exit")

            try:
                exit_event.wait()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                logger.error(e)
                show_error("Fatal Error", str(e))
                sys.exit(1)

            exit_time = datetime.now()
            changer.exit()

            if config.show_toasts:
                elapsed = (datetime.now() - exit_time).total_seconds()
                remaining = 2 - elapsed
                if remaining > 0:
                    time.sleep(remaining)
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
