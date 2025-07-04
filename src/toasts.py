import sys
import threading
import tkinter as tk
from typing import Any, Optional

from logger import logger
from utils import set_dpi_awareness


class ToastManager:
    _root = None
    _toast = None
    _label = None
    _counter_label = None
    _after_id = None
    _last_message = None
    _repeat_count = 1

    @classmethod
    def _get_root(cls) -> tk.Tk:
        if cls._root is None:
            cls._root = tk.Tk()
            cls._root.withdraw()
            cls._root.overrideredirect(True)

        return cls._root

    @staticmethod
    def _calculate_toast_geometry(t: tk.Toplevel) -> str:
        window_width = t.winfo_width()
        window_height = t.winfo_height()

        if window_width <= 1 or window_height <= 1:
            t.update_idletasks()
            window_width = t.winfo_width()
            window_height = t.winfo_height()

        margin_x = 50
        margin_y = 100

        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                # Get the work area of the screen (screen size minus taskbar and dock)
                rect = wintypes.RECT()
                res = ctypes.windll.user32.SystemParametersInfoW(
                    0x0030, 0, ctypes.byref(rect), 0
                )
                if res:
                    work_width = rect.right - rect.left
                    work_height = rect.bottom - rect.top

                    x = work_width - window_width
                    y = work_height - window_height

                    return f"+{x}+{y}"
            except Exception:
                pass

        screen_width = t.winfo_screenwidth()
        screen_height = t.winfo_screenheight()

        x = screen_width - window_width - margin_x
        y = screen_height - window_height - margin_y

        return f"+{x}+{y}"

    @classmethod
    def _create_toast_window(cls) -> None:
        root = cls._get_root()
        cls._toast = tk.Toplevel(root)
        t = cls._toast
        t.withdraw()
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.attributes("-alpha", 0.8)

        if sys.platform == "win32":
            t.attributes("-toolwindow", True)

        frame = tk.Frame(t, bg="black", cursor="hand2")
        frame.pack()

        cls._counter_label = tk.Label(
            frame, text="", bg="black", fg="lightblue", padx=5, pady=5, cursor="hand2"
        )
        cls._label = tk.Label(
            frame, text="", bg="black", fg="white", padx=5, pady=5, cursor="hand2"
        )
        cls._label.pack(side="left")

        def hide_toast(event: Any = None) -> None:
            cls.hide()

        t.bind("<Button-1>", hide_toast)
        cls._label.bind("<Button-1>", hide_toast)
        cls._counter_label.bind("<Button-1>", hide_toast)

    @classmethod
    def show(cls, message: str, duration: Optional[int] = None) -> None:
        if duration and duration <= 0:
            raise ValueError("duration <= 0")

        if cls._toast is None or not cls._toast.winfo_exists():
            cls._create_toast_window()

        t = cls._toast

        # type safety
        assert t is not None
        assert cls._label is not None
        assert cls._counter_label is not None

        if message == cls._last_message:
            cls._repeat_count += 1
        else:
            cls._repeat_count = 1
            cls._last_message = message

        cls._label.config(text=message)

        if cls._repeat_count > 1:
            cls._counter_label.config(text=str(cls._repeat_count))
            if not cls._counter_label.winfo_ismapped():
                cls._counter_label.pack(side="right")
        else:
            cls._counter_label.pack_forget()

        t.update_idletasks()

        t.deiconify()

        t.update_idletasks()

        new_geometry = ToastManager._calculate_toast_geometry(t)
        t.geometry(new_geometry)

        if cls._after_id:
            try:
                t.after_cancel(cls._after_id)
            except tk.TclError:
                pass

        if duration:
            cls._after_id = t.after(duration, cls.hide)

    @classmethod
    def hide(cls) -> None:
        if cls._toast is not None:
            cls._toast.withdraw()

        cls._after_id = None
        cls._last_message = None
        cls._repeat_count = 1

    @staticmethod
    def start_tk_loop(started_event: threading.Event) -> None:
        root: Optional[tk.Tk] = None

        try:
            set_dpi_awareness()
            root = ToastManager._get_root()
        except Exception as e:
            logger.error(f"Failed to start Tk loop: {e}", stack_info=True)
        finally:
            started_event.set()

        if root is not None:
            try:
                root.mainloop()
            except Exception as e:
                logger.error(f"Tkinter mainloop error: {e}", stack_info=True)

    @classmethod
    def stop_tk_loop(cls) -> None:
        if cls._root is not None:
            cls._root.quit()
            cls._root = None
