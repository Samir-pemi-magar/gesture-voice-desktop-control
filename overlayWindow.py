import tkinter as tk
from PIL import Image, ImageTk
import threading

ICON_SIZE = 64
SPACING_X = 130
SPACING_Y = 90
START_X = 10
START_Y = 10


class AppGridOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GestureOverlay")

        # Make fullscreen, transparent, always-on-top, click-through
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)          # Start hidden
        self.root.configure(bg="black")
        self.root.overrideredirect(True)             # No title bar

        # Make the window click-through on Windows
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            # WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00080000 | 0x00000020)
        except Exception as e:
            print(f"Click-through setup warning: {e}")

        self.canvas = tk.Canvas(
            self.root,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        self.visible = False
        self.app_icons = []       # list of (app_path, pil_icon, name)
        self.current_page = 0
        self.hovered_idx = -1
        self._tk_icons = []       # keep references so GC doesn't kill them

        # Page label
        self.page_label = self.canvas.create_text(
            self.screen_w - 80, self.screen_h - 30,
            text="", fill="white",
            font=("Segoe UI", 12, "bold")
        )

        # Run tkinter loop in background thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self.root.mainloop()

    # ── public API (called from gesture thread) ──────────────────────────────

    def show(self):
        self.root.after(0, self._show)

    def hide(self):
        self.root.after(0, self._hide)

    def set_apps(self, app_icons):
        """Pass the full app list (path, pil_icon, name)."""
        self.app_icons = app_icons
        self.root.after(0, self._redraw)

    def set_page(self, page):
        self.current_page = page
        self.root.after(0, self._redraw)

    def set_hovered(self, idx):
        if self.hovered_idx != idx:
            self.hovered_idx = idx
            self.root.after(0, self._redraw)

    # ── internal ─────────────────────────────────────────────────────────────

    def _show(self):
        self.root.attributes("-alpha", 0.88)
        self.visible = True
        self._redraw()

    def _hide(self):
        self.root.attributes("-alpha", 0.0)
        self.visible = False

    def _get_page_layout(self):
        icons_per_row = max(1, (self.screen_w - START_X) // SPACING_X)
        rows_per_page = max(1, (self.screen_h - START_Y) // SPACING_Y)
        apps_per_page = icons_per_row * rows_per_page
        max_page = max(0, (len(self.app_icons) - 1) // apps_per_page) if self.app_icons else 0
        page_apps = self.app_icons[
            self.current_page * apps_per_page:
            (self.current_page + 1) * apps_per_page
        ]
        return icons_per_row, apps_per_page, max_page, page_apps

    def _redraw(self):
        self.canvas.delete("icon")
        self._tk_icons.clear()

        icons_per_row, _, max_page, page_apps = self._get_page_layout()

        for idx, (app_path, pil_icon, name) in enumerate(page_apps):
            col = idx % icons_per_row
            row = idx // icons_per_row
            x = START_X + col * SPACING_X
            y = START_Y + row * SPACING_Y

            if y + ICON_SIZE > self.screen_h or x + ICON_SIZE > self.screen_w:
                continue

            # Convert PIL image → PhotoImage (RGBA for transparency)
            img_rgba = pil_icon.convert("RGBA").resize((ICON_SIZE, ICON_SIZE))
            tk_img = ImageTk.PhotoImage(img_rgba)
            self._tk_icons.append(tk_img)

            self.canvas.create_image(x, y, anchor=tk.NW, image=tk_img, tags="icon")

            # Hover highlight
            if idx == self.hovered_idx:
                self.canvas.create_rectangle(
                    x - 3, y - 3,
                    x + ICON_SIZE + 3, y + ICON_SIZE + 3,
                    outline="#00FFFF", width=2, tags="icon"
                )
                # Show name in bigger text when hovered
                self.canvas.create_text(
                    x + ICON_SIZE // 2, y + ICON_SIZE + 16,
                    text=name, fill="#00FFFF",
                    font=("Segoe UI", 9, "bold"), tags="icon"
                )
            else:
                self.canvas.create_text(
                    x + ICON_SIZE // 2, y + ICON_SIZE + 10,
                    text=name, fill="#EDC67D",
                    font=("Segoe UI", 7), tags="icon"
                )

        # Page indicator
        self.canvas.itemconfig(
            self.page_label,
            text=f"Page {self.current_page + 1}/{max_page + 1}"
        )

    def get_hovered_for_cursor(self, cursor_x, cursor_y):
        """Given a cursor position, return the hovered app index (-1 if none)."""
        icons_per_row, _, _, page_apps = self._get_page_layout()
        for idx, _ in enumerate(page_apps):
            col = idx % icons_per_row
            row = idx // icons_per_row
            x = START_X + col * SPACING_X
            y = START_Y + row * SPACING_Y
            if x <= cursor_x <= x + ICON_SIZE and y <= cursor_y <= y + ICON_SIZE:
                return idx
        return -1
