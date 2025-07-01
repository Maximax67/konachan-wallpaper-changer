import os
import random
import threading
import time
from datetime import datetime
from typing import Callable, List, Optional, Tuple

import keyboard
import requests

from api import fetch_and_cache_all_image_infos
from config import Config
from donwloaded_images_list import DownloadedImagesList
from fixed_size_queue import FixedSizeQueue
from logger import logger
from toasts import ToastManager
from utils import (
    get_queries_ratings_hash,
    load_image_infos_cache,
    save_image_infos_cache,
    set_wallpaper,
)


class WallpaperChanger:
    def __init__(self, config: Config):
        self.config = config
        self.config.wallpapers_folder_path.mkdir(exist_ok=True)

        self.threshold = max(1, int(config.max_images * config.old_images_threshold))

        self.paused = config.paused_on_startup
        self.enabled = config.enabled_on_startup

        self.current_wallpaper: Optional[str] = None

        self.lock = threading.Lock()

        self._auto_image_switch_lock = threading.Lock()
        self._auto_image_switch_event = threading.Event()
        self._auto_image_switch_time: Optional[datetime] = None
        if self.enabled and not self.paused:
            self._set_auto_image_switch_event()

        self.fetch_event = threading.Event()
        self.fetch_event.set()

        self.downloaded_images: DownloadedImagesList[Tuple[str, str, str]] = (
            DownloadedImagesList()
        )

        self.image_queue: FixedSizeQueue[Tuple[str, str]] = FixedSizeQueue([])
        self.full_update_requred = True

        self._load_image_infos()
        self._setup_hotkeys()

        self.thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.thread.start()

        if config.image_switch_interval:
            self.thread = threading.Thread(target=self._auto_image_switch, daemon=True)
            self.thread.start()

    def _load_image_infos(self) -> None:
        self.cache_hash = get_queries_ratings_hash(
            self.config.queries, self.config.ratings, self.config.min_score
        )
        cache = load_image_infos_cache()
        if cache.get("hash") == self.cache_hash:
            logger.info("Using cached image info")
            image_infos = cache.get("data", {})

            self._show_toast("Wallpaper changer started")
        else:
            logger.info(
                "Cache is missing or config changed, fetching new image info..."
            )
            self._show_toast(
                "Wallpaper changer started. Fetching image info...",
                None,
            )
            image_infos = fetch_and_cache_all_image_infos(
                self.config.queries,
                self.config.ratings,
                self.config.min_score,
                self.config.max_pages_to_search,
                self.config.search_page_limit,
            )

            save_image_infos_cache({"hash": self.cache_hash, "data": image_infos})

            self._show_toast("All image info fetched")

        logger.info(f"Total images: {len(image_infos)}")

        temp_images_list: List[Tuple[str, str, str]] = []
        for file in self.config.wallpapers_folder_path.iterdir():
            if file.is_file():
                img_hash = file.stem
                image_url = image_infos.get(img_hash)
                if image_url and len(temp_images_list) < self.config.max_images:
                    temp_images_list.append((img_hash, str(file), image_url))
                    del image_infos[img_hash]
                else:
                    file.unlink()

        random.shuffle(temp_images_list)

        self.downloaded_images = DownloadedImagesList.from_iterable(temp_images_list)

        image_info_list = list(image_infos.items())
        random.shuffle(image_info_list)

        self.image_queue = FixedSizeQueue(image_info_list)

        logger.debug(f"Loaded {len(self.downloaded_images)} images from folder")

    def _fetch_loop(self) -> None:
        while True:
            self.fetch_event.wait()

            current_size = len(self.downloaded_images)
            position = self.downloaded_images.position_from_start

            if current_size < self.config.max_images:
                to_fetch = self.config.max_images - current_size
                logger.debug(
                    f"Not enough images, fetching {to_fetch} image(s) to fill batch..."
                )
            elif position >= self.threshold:
                to_fetch = position - self.threshold + 1
                logger.debug(
                    f"Index {position} >= {self.threshold} (threshold of batch size), rotating {to_fetch} image(s)..."
                )
            else:
                self.fetch_event.clear()
                continue

            for _ in range(min(to_fetch, self.image_queue.size)):
                img_hash, img_url = self.image_queue.dequeue()
                ext = os.path.splitext(img_url)[1]
                img_path = os.path.join(
                    self.config.wallpapers_folder_path, f"{img_hash}{ext}"
                )
                try:
                    logger.debug(f"Downloading image: {img_url}")
                    img_data = requests.get(img_url, timeout=10)
                    if img_data.status_code == 200:
                        with open(img_path, "wb") as f:
                            f.write(img_data.content)
                        logger.debug(f"Saved image: {img_path}")
                    else:
                        self.image_queue.enqueue((img_hash, img_url))
                        logger.error(
                            f"Failed to download image: {img_url} (status {img_data.status_code})"
                        )
                        continue
                except Exception as e:
                    self.image_queue.enqueue((img_hash, img_url))
                    logger.error(f"Error downloading image: {img_url} ({e})")
                    continue

                with self.lock:
                    self.downloaded_images.append((img_hash, img_path, img_url))

                    while len(self.downloaded_images) > self.config.max_images:
                        old_img_hash, old_img_path, old_img_url = (
                            self.downloaded_images.pop_left()
                        )
                        self.image_queue.enqueue((old_img_hash, old_img_url))

                        try:
                            os.remove(old_img_path)
                            logger.debug(f"Removed old image: {old_img_path}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to remove image: {old_img_path} ({e})"
                            )

    def _set_wallpaper(self, img_path: str) -> bool:
        if img_path == self.current_wallpaper:
            return False

        set_wallpaper(img_path)
        self.current_wallpaper = img_path

        return True

    def set_current_wallpaper(self) -> bool:
        if self.enabled and len(self.downloaded_images):
            current = self.downloaded_images.current()
            if current:
                return self._set_wallpaper(current[1])
        elif not self.enabled and self.config.default_image:
            return self._set_wallpaper(str(self.config.default_image))

        return False

    def _show_toast(self, message: str, duration: Optional[int] = 2000) -> None:
        if self.config.show_toasts:
            ToastManager.show(message, duration)

    def next_image(self) -> None:
        if not self.enabled:
            return

        with self.lock:
            if not len(self.downloaded_images):
                logger.warning("No images available")
                return

            logger.debug("Switching to next image")

            self.downloaded_images.move_next()
            self.set_current_wallpaper()
            self.fetch_event.set()

    def next_image_by_hotkey(self) -> None:
        if not self.enabled:
            return

        if not len(self.downloaded_images):
            logger.warning("No images available")
            self._show_toast("No images available")
            return

        with self._auto_image_switch_lock:
            self._auto_image_switch_time = datetime.now()

        self.next_image()
        self._show_toast("Next wallpaper")

    def prev_image(self) -> None:
        if not self.enabled:
            return

        with self.lock:
            if not len(self.downloaded_images):
                logger.warning("No images available")
                self._show_toast("No images available")
                return

            logger.debug("Switching to previous image")

            with self._auto_image_switch_lock:
                self._auto_image_switch_time = datetime.now()

            self.downloaded_images.move_prev()

            if self.set_current_wallpaper():
                self._show_toast("Previous wallpaper")
            else:
                self._show_toast("No previous wallpaper")

    def pause(self) -> None:
        if not self.enabled:
            return

        logger.info("Pausing wallpaper changer")
        self.paused = True
        self._auto_image_switch_event.clear()
        self._show_toast("Paused")

    def unpause(self) -> None:
        if not self.enabled:
            return

        logger.info("Unpausing wallpaper changer")
        self.paused = False
        if self.enabled:
            self._set_auto_image_switch_event(datetime.now())
        self._show_toast("Unpaused")

    def disable(self) -> None:
        logger.info("Disabling wallpaper changer")
        self.enabled = False
        self._auto_image_switch_event.clear()
        self.set_current_wallpaper()
        self._show_toast("Disabled")

    def enable(self) -> None:
        logger.info("Enabling wallpaper changer")
        self.enabled = True
        if not self.paused:
            self._set_auto_image_switch_event(datetime.now())
        self._show_toast("Enabled")

    def exit(self) -> None:
        logger.info("Exit wallpaper changer")
        self.enabled = False
        self.set_current_wallpaper()
        self._show_toast("Exit wallpaper changer")

    def toggle_pause(self) -> None:
        if not self.enabled:
            return

        if self.paused:
            logger.info("Toggling: unpausing")
            self.unpause()
        else:
            logger.info("Toggling: pausing")
            self.pause()

    def toggle_enable(self) -> None:
        if self.enabled:
            logger.info("Toggling: disabling")
            self.disable()
        else:
            logger.info("Toggling: enabling")
            self.enable()

    def _set_auto_image_switch_event(
        self, switch_time: Optional[datetime] = None
    ) -> None:
        with self._auto_image_switch_lock:
            self._auto_image_switch_time = switch_time

        self._auto_image_switch_event.set()

    def _auto_image_switch(self) -> None:
        if not self.config.image_switch_interval:
            return

        while True:
            self._auto_image_switch_event.wait()

            with self._auto_image_switch_lock:
                if self._auto_image_switch_time:
                    now = datetime.now()
                    delta = (
                        self.config.image_switch_interval
                        - (now - self._auto_image_switch_time).total_seconds()
                    )
                    sleep_time = max(0, delta)
                    self._auto_image_switch_time = None
                else:
                    sleep_time = self.config.image_switch_interval

            time.sleep(sleep_time)

            go_next = False
            with self._auto_image_switch_lock:
                if (
                    self._auto_image_switch_time is None
                    and self._auto_image_switch_event.is_set()
                ):
                    go_next = True

            if go_next:
                self.next_image()

    def _setup_hotkeys(self) -> None:
        hk = self.config.hotkeys

        def _hotkey(func_name: str, action: Callable[[], None]) -> None:
            logger.debug(f"Hotkey: {func_name}")
            action()

        keyboard.add_hotkey(hk.next, lambda: _hotkey("next", self.next_image_by_hotkey))
        keyboard.add_hotkey(hk.back, lambda: _hotkey("back", self.prev_image))

        if hk.pause == hk.unpause:
            keyboard.add_hotkey(
                hk.pause, lambda: _hotkey("toggle pause", self.toggle_pause)
            )
        else:
            keyboard.add_hotkey(hk.pause, lambda: _hotkey("pause", self.pause))
            keyboard.add_hotkey(hk.unpause, lambda: _hotkey("unpause", self.unpause))

        if hk.disable == hk.enable:
            keyboard.add_hotkey(
                hk.disable, lambda: _hotkey("toggle enable", self.toggle_enable)
            )
        else:
            keyboard.add_hotkey(hk.disable, lambda: _hotkey("disable", self.disable))
            keyboard.add_hotkey(hk.enable, lambda: _hotkey("enable", self.enable))
