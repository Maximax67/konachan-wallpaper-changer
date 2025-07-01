import sys
import threading
import time

import keyboard

from config import load_config
from constants import SINGLETON_LABEL
from logger import logger
from utils import set_dpi_awareness, show_error, start_tk_loop
from wallpaper_changer import WallpaperChanger
from singleton import SingleInstance, SingleInstanceException

if __name__ == "__main__":
    try:
        with SingleInstance(SINGLETON_LABEL):
            config = load_config()

            config.wallpapers_folder_path = config.wallpapers_folder_path.resolve()
            if config.default_image:
                config.default_image = config.default_image.resolve()

            if config.show_toasts:
                started_event = threading.Event()
                tk_thread = threading.Thread(
                    target=start_tk_loop, args=(started_event,), daemon=True
                )
                tk_thread.start()
                started_event.wait()

            changer = WallpaperChanger(config)

            exit_key = config.hotkeys.exit
            logger.info(f"Wallpaper changer running. Press {exit_key} to exit")

            try:
                keyboard.wait(exit_key)
            except KeyboardInterrupt:
                pass
            except Exception as e:
                logger.error(e)
                show_error("Fatal Error", str(e))
                sys.exit(1)

            changer.exit()

            if config.show_toasts:
                time.sleep(2)
    except SingleInstanceException:
        set_dpi_awareness()
        show_error("Already Running", "Konachan Wallpaper Changer is already running!")
        sys.exit(1)
    except Exception as e:
        logger.error(e, exc_info=True)
        set_dpi_awareness()
        show_error("Fatal Error", str(e))
        sys.exit(1)
