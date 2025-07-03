import os
import random
import threading
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

import urllib3

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
    show_error,
)
from wallpaper import set_wallpaper


class WallpaperChanger:
    def __init__(self, config: Config):
        self.config = config
        self.config.wallpapers_folder_path.mkdir(exist_ok=True)

        self.threshold = int(config.max_images * config.old_images_threshold)

        self.paused = config.paused_on_startup
        self.enabled = config.enabled_on_startup

        self.current_wallpaper: Optional[str] = None

        self._lock = threading.Lock()
        self._exit_event = threading.Event()

        self._auto_image_switch_lock = threading.Lock()
        self._auto_image_switch_event = threading.Event()
        self._auto_image_switch_time: Optional[datetime] = None
        if self.enabled and not self.paused:
            self._set_auto_image_switch_event()

        self._fetch_event = threading.Event()
        self._fetch_event.set()

        self.downloaded_images: DownloadedImagesList[Tuple[str, str, str]] = (
            DownloadedImagesList()
        )

        self.image_queue: FixedSizeQueue[Tuple[str, str]] = FixedSizeQueue([])
        self._load_image_infos()

        if self.enabled:
            self.set_current_wallpaper()

        self._fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._fetch_thread.start()

        self._auto_image_switch_thread: Optional[threading.Thread] = None
        if config.image_switch_interval:
            self._auto_image_switch_thread = threading.Thread(
                target=self._auto_image_switch, daemon=True
            )
            self._auto_image_switch_thread.start()

    def _load_image_infos(self) -> None:
        cache_hash = get_queries_ratings_hash(
            self.config.queries,
            self.config.ratings,
            self.config.min_score,
            self.config.max_image_size,
        )

        cache = load_image_infos_cache()

        cache_expired = False
        if self.config.cache_refresh_interval:
            stored_timestamp = cache.get("timestamp")
            if stored_timestamp:
                current_time = datetime.now(timezone.utc)
                stored_time = datetime.fromtimestamp(stored_timestamp, tz=timezone.utc)
                cache_expired = (
                    current_time > stored_time + self.config.cache_refresh_interval
                )
            else:
                cache_expired = True

        if not cache_expired and cache.get("hash") == cache_hash:
            logger.info("Using cached image info")
            image_infos = cache.get("data", {})

            self._show_toast("Wallpaper changer started")
        else:
            logger.info("Fetching new image info...")
            self._show_toast(
                "Wallpaper changer started. Fetching new image info...",
                None,
            )

            image_infos = fetch_and_cache_all_image_infos(
                self.config.queries,
                self.config.ratings,
                self.config.min_score,
                self.config.max_pages_to_search,
                self.config.search_page_limit,
                self.config.max_image_size,
            )

            save_image_infos_cache(
                {
                    "hash": cache_hash,
                    "data": image_infos,
                    "timestamp": int(datetime.now(timezone.utc).timestamp()),
                }
            )

            self._show_toast("All image info fetched")

        logger.info(f"Total images: {len(image_infos)}")

        temp_images_list: List[Tuple[str, str, str, float]] = []
        for file in self.config.wallpapers_folder_path.iterdir():
            if file.is_file():
                image_hash = file.stem
                image_url = image_infos.get(image_hash)
                if image_url and len(temp_images_list) < self.config.max_images:
                    creation_time = file.stat().st_ctime
                    temp_images_list.append(
                        (image_hash, str(file), image_url, creation_time)
                    )
                    del image_infos[image_hash]
                else:
                    file.unlink()

        temp_images_list.sort(key=lambda x: x[3])

        self.downloaded_images = DownloadedImagesList()
        for image_hash, image_path, image_url, _ in temp_images_list:
            self.downloaded_images.append((image_hash, image_path, image_url))

        moves = min(len(temp_images_list) - 1, self.threshold + 1)
        for _ in range(moves):
            self.downloaded_images.move_next()

        image_info_list = list(image_infos.items())
        random.shuffle(image_info_list)

        self.image_queue = FixedSizeQueue(image_info_list)

        logger.debug(f"Loaded {len(self.downloaded_images)} images from folder")

    def _fetch_loop(self) -> None:
        delay = 1
        max_delay = 60

        http = urllib3.PoolManager()

        while True:
            self._fetch_event.wait()
            if self._exit_event.is_set():
                break

            current_size = len(self.downloaded_images)
            position = self.downloaded_images.position_from_start

            if current_size < self.config.max_images:
                to_fetch = self.config.max_images - current_size
                logger.debug("Not enough images, fetching image(s) to fill batch...")
            elif position > self.threshold:
                to_fetch = position - self.threshold
                logger.debug(
                    f"Index {position} > {self.threshold} (threshold of batch size), rotating image(s)..."
                )
            else:
                self._fetch_event.clear()
                continue

            for _ in range(min(to_fetch, self.image_queue.size)):
                if self._exit_event.is_set():
                    return

                download_success = False

                img_hash, img_url = self.image_queue.dequeue()
                ext = os.path.splitext(img_url)[1]
                img_path = os.path.join(
                    self.config.wallpapers_folder_path, f"{img_hash}{ext}"
                )
                logger.debug(f"Downloading image: {img_url}")
                try:
                    response: urllib3.HTTPResponse = http.request(
                        "GET", img_url, timeout=30, preload_content=False
                    )

                    if response.status == 200:
                        content_length = int(response.headers.get("Content-Length", 0))
                        downloaded = 0

                        with open(img_path, "wb") as f:
                            for chunk in response.stream(16384):
                                f.write(chunk)
                                downloaded += len(chunk)

                        if content_length and downloaded != content_length:
                            logger.error(
                                f"Incomplete download for {img_url}: {downloaded}/{content_length} bytes"
                            )
                            self.image_queue.enqueue((img_hash, img_url))

                            try:
                                if os.path.exists(img_path):
                                    os.remove(img_path)
                                    logger.debug(
                                        f"Removed incomplete downloaded image: {img_path}"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to remove incomplete downloaded image: {img_path} ({e})"
                                )
                        else:
                            download_success = True
                            logger.debug(f"Saved image: {img_path}")
                    else:
                        self.image_queue.enqueue((img_hash, img_url))
                        logger.error(
                            f"Failed to download image: {img_url} (status {response.status})"
                        )
                except Exception as e:
                    self.image_queue.enqueue((img_hash, img_url))
                    logger.error(f"Error downloading image: {img_url} ({e})")
                finally:
                    response.release_conn()

                if download_success:
                    delay = 1
                    with self._lock:
                        self.downloaded_images.append((img_hash, img_path, img_url))

                        while len(self.downloaded_images) > self.config.max_images:
                            old_img_hash, old_img_path, old_img_url = (
                                self.downloaded_images.pop()
                            )
                            self.image_queue.enqueue((old_img_hash, old_img_url))

                            try:
                                os.remove(old_img_path)
                                logger.debug(f"Removed old image: {old_img_path}")
                            except Exception as e:
                                logger.warning(
                                    f"Failed to remove image: {old_img_path} ({e})"
                                )
                else:
                    if self._exit_event.wait(timeout=delay):
                        return

                    delay = min(delay * 2, max_delay)

    def _set_wallpaper(self, img_path: str) -> None:
        if img_path == self.current_wallpaper:
            return

        is_first_change = self.current_wallpaper is None
        self.current_wallpaper = img_path

        logger.info(f"Setting wallpaper: {img_path}")

        if not set_wallpaper(img_path, is_first_change):
            show_error(
                "Failed to set wallpaper",
                "Please check the app.log file for more details.",
            )

    def set_current_wallpaper(self) -> None:
        if self.enabled and len(self.downloaded_images):
            current = self.downloaded_images.current()
            if current:
                self._set_wallpaper(current[1])
        elif not self.enabled and self.config.default_image:
            self._set_wallpaper(str(self.config.default_image))

    def _show_toast(self, message: str, duration: Optional[int] = 2000) -> None:
        if self.config.show_toasts:
            ToastManager.show(message, duration)

    def next_image(self) -> None:
        if not self.enabled:
            return

        with self._lock:
            if not len(self.downloaded_images):
                logger.warning("No images available")
                return

            logger.debug("Switching to next image")

            self.downloaded_images.move_next()
            self.set_current_wallpaper()
            self._fetch_event.set()

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

        with self._lock:
            if not len(self.downloaded_images):
                logger.warning("No images available")
                self._show_toast("No images available")
                return

            logger.debug("Switching to previous image")

            with self._auto_image_switch_lock:
                self._auto_image_switch_time = datetime.now()

            if self.downloaded_images.position_from_start:
                self.downloaded_images.move_prev()
                self.set_current_wallpaper()
                self._show_toast("Previous wallpaper")
                return

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

        self.set_current_wallpaper()
        self._show_toast("Enabled")

    def exit(self) -> None:
        self.enabled = False
        self._exit_event.set()
        self._fetch_event.set()
        self._auto_image_switch_event.set()

        self.set_current_wallpaper()

        if self._auto_image_switch_thread:
            self._auto_image_switch_thread.join()

        self._fetch_thread.join()

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
            if self._exit_event.is_set():
                break

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

            if self._exit_event.wait(timeout=sleep_time):
                break

            go_next = False
            with self._auto_image_switch_lock:
                if (
                    self._auto_image_switch_time is None
                    and self._auto_image_switch_event.is_set()
                ):
                    go_next = True

            if go_next:
                self.next_image()

    def setup_hotkeys(self, hotkey_actions: Dict[str, Callable[[], None]]) -> None:
        hk = self.config.hotkeys

        def _hotkey(func_name: str, action: Callable[[], None]) -> None:
            logger.debug(f"Hotkey: {func_name}")
            action()

        if hk.next:
            hotkey_actions[hk.next] = lambda: _hotkey("next", self.next_image_by_hotkey)

        if hk.back:
            hotkey_actions[hk.back] = lambda: _hotkey("back", self.prev_image)

        if hk.pause == hk.unpause and hk.pause:
            hotkey_actions[hk.pause] = lambda: _hotkey(
                "toggle pause", self.toggle_pause
            )
        else:
            if hk.pause:
                hotkey_actions[hk.pause] = lambda: _hotkey("pause", self.pause)

            if hk.unpause:
                hotkey_actions[hk.unpause] = lambda: _hotkey("unpause", self.unpause)

        if hk.disable == hk.enable and hk.disable:
            hotkey_actions[hk.disable] = lambda: _hotkey(
                "toggle enable", self.toggle_enable
            )
        else:
            if hk.disable:
                hotkey_actions[hk.disable] = lambda: _hotkey("disable", self.disable)

            if hk.enable:
                hotkey_actions[hk.enable] = lambda: _hotkey("enable", self.enable)
