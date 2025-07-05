from datetime import timedelta
import hashlib
import json
import os
import re
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Optional, cast

from constants import IMAGE_INFOS_CACHE
from logger import logger

if sys.platform == "win32":
    import ctypes


_is_dpi_awareness_set = False


def set_dpi_awareness() -> None:
    global _is_dpi_awareness_set

    if _is_dpi_awareness_set:
        return

    _is_dpi_awareness_set = True

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


_exit_handler_ref = None  # global reference to handler to prevent GC


def windows_console_exit_handler(exit_event: threading.Event) -> None:
    if sys.platform != "win32":
        return

    def console_ctrl_handler(ctrl_type: int) -> bool:
        if ctrl_type in (0, 1):  # CTRL_C_EVENT = 0, CTRL_BREAK_EVENT = 1
            logger.info("Console control event received")
            exit_event.set()
            return True

        return False

    kernel32 = ctypes.windll.kernel32
    HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
    handler = HandlerRoutine(console_ctrl_handler)
    kernel32.SetConsoleCtrlHandler(handler, True)

    global _exit_handler_ref
    _exit_handler_ref = handler


def show_error(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()


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
