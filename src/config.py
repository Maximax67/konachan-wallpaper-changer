import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from constants import CONFIG_PATH
from logger import logger
from utils import parse_duration


class Hotkeys:
    next: Optional[str]
    back: Optional[str]
    pause: Optional[str]
    unpause: Optional[str]
    disable: Optional[str]
    enable: Optional[str]
    exit: Optional[str]

    DEFAULTS = {
        "next": "<ctrl>+<alt>+i",
        "back": "<ctrl>+<alt>+u",
        "pause": "<ctrl>+<alt>+p",
        "unpause": "<ctrl>+<alt>+p",
        "disable": "<ctrl>+<alt>+e",
        "enable": "<ctrl>+<alt>+e",
        "exit": "<ctrl>+<shift>+<alt>+e",
    }

    ALLOWED_PAIRS = {frozenset(["pause", "unpause"]), frozenset(["enable", "disable"])}

    def __init__(self, **kwargs: Optional[str]) -> None:
        invalid_keys = set(kwargs) - self.DEFAULTS.keys()
        if invalid_keys:
            raise ValueError(
                f"Invalid config hotkey name{'' if len(invalid_keys) == 1 else 's'}: {', '.join(invalid_keys)}. Allowed keys are: {', '.join(self.DEFAULTS.keys())}"
            )

        keys = {**self.DEFAULTS, **kwargs}

        seen: Dict[str, str] = {}
        for action, hotkey in keys.items():
            if hotkey is None:
                continue

            if hotkey in seen:
                prev_action = seen[hotkey]
                pair = frozenset([prev_action, action])
                if pair not in self.ALLOWED_PAIRS:
                    raise ValueError(
                        f"Duplicate hotkey '{hotkey}' for '{prev_action}' and '{action}' is not allowed."
                    )
            else:
                seen[hotkey] = action

        for action, hotkey in keys.items():
            setattr(self, action, hotkey)

    def to_dict(self) -> Dict[str, str]:
        return self.__dict__

    @staticmethod
    def from_dict(data: Dict[str, str]) -> "Hotkeys":
        return Hotkeys(**data)


class Config:
    def __init__(
        self,
        enabled_on_startup: bool = True,
        paused_on_startup: bool = False,
        show_toasts: bool = True,
        max_pages_to_search: int = 10,
        search_page_limit: int = 100,
        queries: Optional[List[str]] = None,
        max_images: int = 20,
        old_images_threshold: float = 0.2,
        image_switch_interval: Optional[int] = 300,
        wallpapers_folder_path: Path = Path("./wallpapers"),
        hotkeys: Optional[Hotkeys] = None,
        default_image: Optional[Path] = None,
        ratings: Optional[List[str]] = None,
        min_score: Optional[int] = None,
        max_image_size: Optional[int] = None,
        cache_refresh_interval: Optional[str] = "7d",
        **kwargs: Any,
    ) -> None:
        if kwargs:
            raise ValueError(
                f"Unexpected config param{'' if len(kwargs) == 1 else 's'}: {', '.join(kwargs.keys())}"
            )

        self.enabled_on_startup = enabled_on_startup
        self.paused_on_startup = paused_on_startup
        self.show_toasts = show_toasts

        if max_pages_to_search <= 1:
            raise ValueError("max_pages_to_search must be > 1")

        self.max_pages_to_search = max_pages_to_search

        if not (1 < search_page_limit <= 100):
            raise ValueError("search_page_limit must be > 1 and <= 100")

        self.search_page_limit = search_page_limit

        if queries is None:
            queries = ["*"]
        elif len(queries) < 1:
            raise ValueError("queries must contain at least one entry")

        self.queries = queries

        if max_images <= 0:
            raise ValueError("max_images must be > 0")

        self.max_images = max_images

        if not (0.0 < old_images_threshold < 1.0):
            raise ValueError("old_images_threshold must be between 0 and 1")

        self.old_images_threshold = old_images_threshold

        if image_switch_interval is not None and image_switch_interval <= 0:
            raise ValueError("image_switch_interval must be > 0 if provided")

        self.image_switch_interval = image_switch_interval

        self.wallpapers_folder_path = wallpapers_folder_path
        self.hotkeys = hotkeys if hotkeys else Hotkeys()
        self.default_image = default_image

        self.ratings = self._validate_ratings(ratings or ["s"])

        if min_score is not None and min_score < 0:
            raise ValueError("min_score must be >= 0")

        self.min_score = min_score

        if max_image_size is not None and max_image_size < 0:
            raise ValueError("max_image_size must be >= 0")

        self.max_image_size = max_image_size

        self.cache_refresh_interval = (
            parse_duration(cache_refresh_interval) if cache_refresh_interval else None
        )

    def _validate_ratings(self, ratings: List[str]) -> List[str]:
        allowed = {"s", "q", "e"}
        if not all(r in allowed for r in ratings):
            raise ValueError(f"All ratings must be in {allowed}")

        return ratings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled_on_startup": self.enabled_on_startup,
            "paused_on_startup": self.paused_on_startup,
            "show_toasts": self.show_toasts,
            "max_pages_to_search": self.max_pages_to_search,
            "search_page_limit": self.search_page_limit,
            "queries": self.queries,
            "max_images": self.max_images,
            "old_images_threshold": self.old_images_threshold,
            "image_switch_interval": self.image_switch_interval,
            "wallpapers_folder_path": str(self.wallpapers_folder_path),
            "hotkeys": self.hotkeys.to_dict(),
            "default_image": str(self.default_image) if self.default_image else None,
            "ratings": self.ratings,
            "min_score": self.min_score,
            "max_image_size": self.max_image_size,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Config":
        data["wallpapers_folder_path"] = Path(
            data.get("wallpapers_folder_path", "./wallpapers")
        )
        default_image = data.get("default_image")
        data["default_image"] = Path(default_image) if default_image else None
        data["hotkeys"] = Hotkeys.from_dict(data.get("hotkeys", {}))

        return Config(**data)


def load_config() -> Config:
    logger.debug("Loading config...")

    if not Path(CONFIG_PATH).exists():
        logger.warning("Config file not found. Writing default config")
        return write_default_config()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        config = Config.from_dict(data)
    except Exception as e:
        logger.error(f"Config validation error: {e}")
        raise

    return config


def write_default_config() -> Config:
    default_config = Config()
    Path(CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(default_config.to_dict(), f, indent=4)

    logger.debug(f"Default config written to {CONFIG_PATH}")

    return default_config
