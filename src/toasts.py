import sys
import tkinter as tk
from typing import Any, Optional


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
        window_width = t.winfo_width()
        window_height = t.winfo_height()
        x = t.winfo_screenwidth() - window_width - 20
        y = t.winfo_screenheight() - window_height - 100
        t.geometry(f"+{x}+{y}")

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
