from datetime import timedelta
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Optional, cast

import keyboard

from constants import IMAGE_INFOS_CACHE
from logger import logger
from toasts import ToastManager


if sys.platform == "win32":
    import ctypes


def set_dpi_awareness() -> None:
    if sys.platform == "win32":
        # PROCESS_SYSTEM_DPI_AWARE
        try:
            # Skip setting DPI awareness if running from a bundled .exe
            if getattr(sys, "frozen", False):
                return

            version = sys.getwindowsversion()
            if (version.major > 6) or (version.major == 6 and version.minor >= 3):
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        os.environ["GDK_SCALE"] = "1"
        os.environ["QT_SCALE_FACTOR"] = "1"


def start_tk_loop(started_event: threading.Event) -> None:
    try:
        set_dpi_awareness()
        root = ToastManager._get_root()
    except Exception as e:
        logger.error(f"Failed to start Tk loop: {e}")
    finally:
        started_event.set()

    try:
        root.mainloop()
    except Exception as e:
        logger.error(f"Tkinter mainloop error: {e}")


if sys.platform == "win32":

    def clear_keys() -> None:
        while True:
            # Hotkeys stop working after windows locks & unlocks
            # https://github.com/boppreh/keyboard/issues/223
            with keyboard._pressed_events_lock:
                for k in list(keyboard._pressed_events.keys()):
                    item = keyboard._pressed_events[k]
                    if time.time() - item.time > 4:
                        del keyboard._pressed_events[k]

            time.sleep(1)

else:
    # Dummy for non-Windows platforms
    def clear_keys() -> None:
        pass


def show_error(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()


def set_wallpaper(image_path: str) -> None:
    logger.info(f"Setting wallpaper: {image_path}")

    if sys.platform == "win32":
        ctypes.windll.user32.SystemParametersInfoW(0x14, 0, image_path, 0x01)
    elif sys.platform == "darwin":  # macOS
        try:
            script = f"""
            tell application "System Events"
                set picture of every desktop to "{image_path}"
            end tell
            """
            subprocess.run(["osascript", "-e", script], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set wallpaper on macOS: {e}")
    elif sys.platform.startswith("linux"):
        try:
            subprocess.run(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "picture-uri",
                    f"file://{image_path}",
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            logger.warning("Failed to set wallpaper using gsettings. Trying feh...")

            try:
                subprocess.run(["feh", "--bg-scale", image_path], check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to set wallpaper on Linux: {e}")
    else:
        logger.error(f"Unsupported platform: {sys.platform}")


def parse_duration(s: str) -> timedelta:
    pattern = r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$"
    match = re.fullmatch(pattern, s.strip())
    if not match:
        raise ValueError(f"Invalid duration format: {s}")

    days, hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def get_queries_ratings_hash(
    queries: List[str],
    ratings: List[str],
    min_score: Optional[int],
    max_image_size: Optional[int],
) -> str:
    key = {
        "queries": sorted(queries),
        "ratings": sorted(ratings),
        "min_score": min_score,
        "max_image_size": max_image_size,
    }

    return hashlib.md5(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()


def load_image_infos_cache() -> Dict[str, Any]:
    if not os.path.exists(IMAGE_INFOS_CACHE):
        logger.warning("No image info cache found")
        return {}

    logger.debug("Loading image info cache...")
    with open(IMAGE_INFOS_CACHE, "r", encoding="utf-8") as f:
        return cast(Dict[str, Any], json.load(f))


def save_image_infos_cache(cache: Dict[str, Any]) -> None:
    logger.debug("Saving image info cache...")
    with open(IMAGE_INFOS_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f)
