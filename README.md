# Konachan Wallpaper Changer

A Python application that automatically fetches, caches, and rotates wallpapers from the [Konachan](https://konachan.com/) image board based on your filters.

## Features

- **Automatic wallpaper rotation**: Changes your desktop wallpaper at configurable intervals.
- **Konachan integration**: Downloads and caches high-quality wallpapers from [Konachan](https://konachan.com/) based on your search queries, tags, ratings, and score filters.
- **Hotkey support**: Instantly switch to the next/previous wallpaper, pause/unpause, enable/disable, or exit the app using customizable hotkeys.
- **Toast notifications**: Get instant feedback for actions and status changes.
- **Configurable**: All settings are easily managed via `config.json` (auto-generated on first run).
- **Single-instance enforcement**: Prevents multiple instances from running simultaneously.

## Requirements

- Python 3.8 or higher
- Windows OS (should also work on Linux/macOS, but not tested)

## Usage

1. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

   > **Note for Linux users**: You may also need to install `tkinter` separately. On Debian-based systems:

   ```sh
   sudo apt-get install python3-tk
   ```
2. Configure your preferences in `config.json` (auto-generated on first run).
3. Run the application:
   ```sh
   python src/main.py
   ```

## Building an Executable

You can build a standalone executable using [PyInstaller](https://pyinstaller.org/). A `main.spec` file is provided for convenience.

To build:

```sh
pyinstaller main.spec
```

This will generate a single-file executable in the created `dist/` directory.

## Configuration

The application is configured via a `config.json` file. Here are the available options:


| Key                            | Type                | Description                                                                  |
|--------------------------------|---------------------|------------------------------------------------------------------------------|
| `enabled_on_startup`           | `bool`              | Start the app enabled (wallpaper changing active)                            |
| `paused_on_startup`            | `bool`              | Start the app paused (no auto wallpaper switching)                           |
| `show_toasts`                  | `bool`              | Show toast notifications for actions                                         |
| `max_pages_to_search`          | `int`               | Max pages to fetch from Konachan per query                                   |
| `search_page_limit`            | `int`               | Number of images per page to fetch (max 100)                                 |
| `queries`                      | `list[str]`         | List of search queries for wallpapers                                        |
| `max_images`                   | `int`               | Maximum number of wallpapers to keep (rotated automatically)                 |
| `old_images_threshold`         | `float`             | Fraction (0-1) of old images to keep in cache before fetching new ones       |
| `image_switch_interval`        | `int \| null`       | Seconds between automatic wallpaper changes (`null` disables auto-switching) |
| `cached_wallpapers_path`       | `str`               | Path to the folder for cached or rotating wallpapers (auto-managed)          |
| `user_saved_wallpapers_path`   | `str`               | Path to the folder where wallpapers saved via hotkey are stored              |
| `hotkeys`                      | `object`            | Hotkey configuration (see below)                                             |
| `default_image`                | `str \| null`       | Path to a default image to use when disabled (optional)                      |
| `ratings`                      | `list[str] \| null` | List of allowed ratings: `s` (safe), `q` (questionable), `e` (explicit)      |
| `min_score`                    | `int \| null`       | Minimum score for images to be downloaded (`null` disables score filtering)  |
| `max_image_size`               | `int \| null`       | Maximum file size for images to be downloaded (`null` downloads all)         |
| `cache_refresh_interval`       | `str \| null`       | Time interval between cache refreshes (`null` disables cache refresh)        |

**Note:** `cache_refresh_interval` supports durations like `"1d"`, `"12h30m"`, etc. Uses days (`d`), hours (`h`), minutes (`m`), and seconds (`s`). Cache refresh only occurs at application startup.


#### Default config file:

```json
{
    "enabled_on_startup": true,
    "paused_on_startup": false,
    "show_toasts": true,
    "max_pages_to_search": 10,
    "search_page_limit": 100,
    "queries": [
        "*"
    ],
    "max_images": 20,
    "old_images_threshold": 0.2,
    "image_switch_interval": 300,
    "cached_wallpapers_path": "wallpapers/cached",
    "user_saved_wallpapers_path": "wallpapers",
    "hotkeys": {
        "next": [
            "<ctrl>+<alt>+i"
        ],
        "back": [
            "<ctrl>+<alt>+u"
        ],
        "pause": [
            "<ctrl>+<alt>+p"
        ],
        "unpause": [
            "<ctrl>+<alt>+p"
        ],
        "disable": [
            "<ctrl>+<alt>+e"
        ],
        "enable": [
            "<ctrl>+<alt>+e"
        ],
        "exit": [
            "<ctrl>+<shift>+<alt>+e"
        ],
        "save": [
            "<ctrl>+<alt>+l"
        ],
        "delete": [
            "<ctrl>+<alt>+l"
        ]
    },
    "default_image": null,
    "ratings": [
        "s"
    ],
    "min_score": null,
    "max_image_size": 20971520,
    "cache_refresh_interval": "7d"
}
```

### Hotkey Configuration

The default `hotkeys` object contains the following keys:

| Key       | Default Value            | Description               |
|-----------|--------------------------|---------------------------|
| `next`    | `<ctrl>+<alt>+i`         | Next wallpaper            |
| `back`    | `<ctrl>+<alt>+u`         | Previous wallpaper        |
| `pause`   | `<ctrl>+<alt>+p`         | Pause auto-switching      |
| `unpause` | `<ctrl>+<alt>+p`         | Unpause auto-switching    |
| `disable` | `<ctrl>+<alt>+e`         | Disable wallpaper changer |
| `enable`  | `<ctrl>+<alt>+e`         | Enable wallpaper changer  |
| `exit`    | `<ctrl>+<shift>+<alt>+e` | Exit the application      |
| `save`    | `<ctrl>+<alt>+l`         | Save current image        |
| `delete`  | `<ctrl>+<alt>+l`         | Delete image              |

Each hotkey value can also be set to null to disable that particular hotkey. Hotkey values can be specified as a list of hotkey strings instead of a single string. This allows binding multiple shortcuts to the same action.

#### Save and Delete

- **Save:** Copies the current wallpaper image to the configured `user_saved_wallpapers_path` for later use or backup.
- **Delete:** Removes the saved copy of the current wallpaper from the `user_saved_wallpapers_path`.

These actions help you manage your favorite wallpapers easily — use save to archive a wallpaper, and delete to remove it from the saved set.

#### Hotkey Pairing Rules

Only specific *paired actions* are allowed to share the same hotkey:

* `pause` / `unpause`
* `enable` / `disable`
* `save` / `delete`

Each pair represents toggling or opposite actions, so they intentionally use the same key combination. All **other actions must have unique hotkeys** to avoid conflicts. Make sure your custom hotkey configuration follows this rule.

#### Multiple Keyboard Layouts

If you use multiple keyboard layouts (e.g., English and Cyrillic) where the same physical key corresponds to different letters, **you should provide multiple hotkeys** — one for each layout — to ensure consistent behavior across layouts.

**Example if you have Russian/Ukrainian and English keyboard layouts:**

```json
"hotkeys": {
    "next": [
        "<ctrl>+<alt>+i",
        "<ctrl>+<alt>+ш"
    ],
    "back": [
        "<ctrl>+<alt>+u",
        "<ctrl>+<alt>+г"
    ],
    "pause": [
        "<ctrl>+<alt>+p",
        "<ctrl>+<alt>+з"
    ],
    "unpause": [
        "<ctrl>+<alt>+p",
        "<ctrl>+<alt>+з"
    ],
    "disable": [
        "<ctrl>+<alt>+e",
        "<ctrl>+<alt>+у"
    ],
    "enable": [
        "<ctrl>+<alt>+e",
        "<ctrl>+<alt>+у"
    ],
    "exit": [
        "<ctrl>+<shift>+<alt>+e",
        "<ctrl>+<shift>+<alt>+у"
    ],
    "save": [
        "<ctrl>+<alt>+l",
        "<ctrl>+<alt>+д"
    ],
    "delete": [
        "<ctrl>+<alt>+l",
        "<ctrl>+<alt>+д"
    ]
}
```

## Adding to Startup (Windows)

To launch the wallpaper changer automatically on system startup:

1. Build the executable with PyInstaller (see above), or use a shortcut to `python main.py`.
2. Press `Win + R`, type `shell:startup`, and press Enter. This opens the Startup folder.
3. Copy your executable or shortcut into this folder.
   - If using a Python script, create a shortcut with the target:
     ```
     pythonw.exe "C:\path\to\main.py"
     ```
   - For the PyInstaller build, copy the generated `.exe` file.
4. The app will now launch automatically when you log in.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
