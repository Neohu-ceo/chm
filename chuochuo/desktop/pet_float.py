#!/usr/bin/env python3
"""戳戳悬浮球 — Native desktop floating pet.

Zero browser. Zero dependencies. Just a little friend on your desktop.
Start: python pet_float.py
"""

import tkinter as tk
import json
import time
import random
import threading
import urllib.request
from pathlib import Path

API = "http://localhost:5200"

# ── Pixel Pet Patterns (16×16) ──────────────────────────────────

PATTERNS = {
    "happy": [
        "........########..",
        "......##......##..",
        ".....##........##.",
        "....##..##..##..##",
        "...#.............#",
        "...#..##....##..#.",
        "...#....####....#.",
        "...#.............#",
        "...#..#......#..#.",
        "....#..........#..",
        ".....##..##..##...",
        "......##....##....",
        ".......#......#...",
        "......#........#..",
        ".....##..##..##...",
        ".......######.....",
    ],
    "sleepy": [
        "................",
        "................",
        "....########....",
        "...##......##...",
        "..##........##..",
        "..#..........#..",
        "..#...####...#..",
        "..#..........#..",
        "..#..........#..",
        "..#..........#..",
        "...#...##...#...",
        "....#......#....",
        ".....#....#.....",
        "......#..#......",
        ".......##.......",
        "................",
    ],
    "excited": [
        "....########....",
        "...##......##...",
        "..##........##..",
        ".##..##..##..##.",
        ".#..##....##..#.",
        ".#............#.",
        ".#....####....#.",
        ".#...#....#...#.",
        ".#..##....##..#.",
        ".#..#......#..#.",
        ".##..........##.",
        "..##........##..",
        "...##..##..##...",
        "....##....##....",
        ".....#....#.....",
        "......####......",
    ],
    "love": [
        "................",
        "..##........##..",
        ".####......####.",
        ".######..######.",
        ".############..",
        "..##########...",
        "...########....",
        "....######.....",
        ".....####......",
        "......##.......",
        "......##.......",
        "......##.......",
        "......##.......",
        ".....##.##.....",
        "....##...##....",
        "...##.....##...",
    ],
    "hungry": [
        ".....######.....",
        "....##....##....",
        "...##......##...",
        "..##........##..",
        ".##..##..##..##.",
        ".#..##....##..#.",
        ".#............#.",
        ".#...######...#.",
        ".#............#.",
        ".#..##....##..#.",
        ".##..........##.",
        "..##........##..",
        "...##..##..##...",
        "....##....##....",
        "....#..##..#....",
        ".....##..##.....",
    ],
    "surprised": [
        "....########....",
        "...##......##...",
        "..##........##..",
        ".##..........##.",
        ".#..##....##..#.",
        ".#..##....##..#.",
        ".#............#.",
        ".#.....####...#.",
        ".#....#....#..#.",
        ".#....#....#..#.",
        ".##..........##.",
        "..##..####..##..",
        "...##......##...",
        "....########....",
        "................",
        "................",
    ],
}

COLORS = {
    "#": "#ff6b35",  # Main body
    ".": None,       # Transparent
}

# ── API Helpers ──────────────────────────────────────────────────

def api_call(path, method="GET"):
    try:
        req = urllib.request.Request(f"{API}{path}", method=method)
        req.add_header("Content-Type", "application/json")
        if method == "POST":
            req.data = b"{}"
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return None

# ── Floating Pet Window ─────────────────────────────────────────

class FloatingPet:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("戳戳")
        self.root.geometry("220x300+1000+400")
        self.root.overrideredirect(True)  # Frameless
        self.root.attributes("-topmost", True)  # Always on top
        self.root.configure(bg="#1a1a1a")

        # State
        self.emotion = "happy"
        self.pet_name = "戳戳"
        self.level = 1
        self.stats = {}
        self.bubble_id = None
        self.drag_x = 0
        self.drag_y = 0

        # Canvas
        self.canvas = tk.Canvas(self.root, width=220, height=300,
                                bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack()

        # Bind events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # Right-click menu
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="👆 戳一下", command=self.poke)
        self.menu.add_command(label="🍔 喂食", command=self.feed)
        self.menu.add_command(label="🎮 玩耍", command=self.play)
        self.menu.add_command(label="💤 睡觉", command=self.sleep_pet)
        self.menu.add_separator()
        self.menu.add_command(label="✏️ 改名", command=self.rename)
        self.menu.add_separator()
        self.menu.add_command(label="✕ 关闭", command=self.root.destroy)

        # Render
        self.render()
        self.update_stats()

        # Auto-refresh stats every 10s
        self.auto_refresh()

        self.root.mainloop()

    # ── Rendering ────────────────────────────────────────────────

    def render(self):
        self.canvas.delete("all")
        pat = PATTERNS.get(self.emotion, PATTERNS["happy"])

        # Background circle (subtle glow)
        self.canvas.create_oval(30, 20, 190, 200, fill="#1a1410",
                                outline="#2a2018", width=1)

        # Pixel grid
        pixel_size = 10
        start_x = 35
        start_y = 35

        for row in range(16):
            for col in range(16):
                char = pat[row][col]
                color = COLORS.get(char)
                if color:
                    x1 = start_x + col * pixel_size
                    y1 = start_y + row * pixel_size
                    x2 = x1 + pixel_size - 1
                    y2 = y1 + pixel_size - 1
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2, fill=color,
                        outline="", tags="pixel"
                    )

        # Name + level
        self.canvas.create_text(110, 225, text=f"{self.pet_name}",
                                fill="#e0d8d0", font=("PingFang SC", 14, "bold"))

        # Level badge
        stage_names = {0: "蛋", 1: "幼年", 2: "成年", 3: "完全体"}
        stage = {v: k for k, v in {0: 0, 1: 2, 2: 5, 3: 10}.items()}
        stage_id = 0
        if self.level >= 10: stage_id = 3
        elif self.level >= 5: stage_id = 2
        elif self.level >= 2: stage_id = 1
        stage_name = stage_names[stage_id]

        lv_text = f"Lv.{self.level} · {stage_name}"
        self.canvas.create_text(110, 248, text=lv_text,
                                fill="#ff6b35", font=("PingFang SC", 9))

        # Streak fire
        streak = self.stats.get("streak_days", 0)
        if streak >= 3:
            self.canvas.create_text(110, 268, text=f"🔥 {streak}天连续",
                                    fill="#f0c040", font=("PingFang SC", 8))

    def show_bubble(self, text):
        if self.bubble_id:
            self.canvas.delete(self.bubble_id)
        x, y = 110, 80
        self.bubble_id = self.canvas.create_text(
            x, y, text=text, fill="#fff",
            font=("PingFang SC", 10, "bold"),
            tags="bubble"
        )
        # Auto-fade
        self.root.after(2000, self.hide_bubble)

    def hide_bubble(self):
        if self.bubble_id:
            self.canvas.delete(self.bubble_id)
            self.bubble_id = None

    # ── Interactions ─────────────────────────────────────────────

    def on_click(self, event):
        """Click = poke"""
        self.poke()

    def on_drag_start(self, event):
        self.drag_x = event.x
        self.drag_y = event.y

    def on_drag(self, event):
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")

    def on_right_click(self, event):
        self.menu.post(event.x_root, event.y_root)

    def poke(self):
        self.animate("bounce")
        data = api_call("/api/poke", "POST")
        if data:
            self.emotion = data.get("reaction", self.emotion)
            self.show_bubble(data.get("message", "嘿嘿~"))
            self.render()
            self.update_stats()

    def feed(self):
        self.animate("shake")
        data = api_call("/api/feed", "POST")
        if data:
            self.emotion = data.get("reaction", self.emotion)
            self.show_bubble(data.get("message", data.get("error", "?")))
            self.render()
            self.update_stats()

    def play(self):
        self.animate("spin")
        data = api_call("/api/play", "POST")
        if data:
            self.emotion = data.get("reaction", self.emotion)
            self.show_bubble(data.get("message", "耶~"))
            self.render()
            self.update_stats()

    def sleep_pet(self):
        self.emotion = "sleepy"
        self.render()
        data = api_call("/api/sleep", "POST")
        if data:
            self.show_bubble(data.get("message", "zzZ..."))
            self.update_stats()

    def rename(self):
        # Simple dialog using tk
        dialog = tk.Toplevel(self.root)
        dialog.title("改名")
        dialog.geometry("200x100+1100+500")
        dialog.attributes("-topmost", True)
        entry = tk.Entry(dialog, width=20, font=("PingFang SC", 12))
        entry.insert(0, self.pet_name)
        entry.pack(pady=10)
        entry.focus()

        def do_rename():
            name = entry.get().strip()
            if name:
                self.pet_name = name
                self.render()
            dialog.destroy()

        entry.bind("<Return>", lambda e: do_rename())
        tk.Button(dialog, text="确定", command=do_rename).pack()
        dialog.mainloop()

    # ── Animations ───────────────────────────────────────────────

    def animate(self, kind):
        """Brief window animation."""
        ox, oy = self.root.winfo_x(), self.root.winfo_y()
        if kind == "bounce":
            for dy in [-8, -4, -2, 0, 2, 0]:
                self.root.geometry(f"+{ox}+{oy+dy}")
                self.root.update()
                time.sleep(0.03)
        elif kind == "shake":
            for dx in [-6, 6, -4, 4, -2, 2, 0]:
                self.root.geometry(f"+{ox+dx}+{oy}")
                self.root.update()
                time.sleep(0.03)
        elif kind == "spin":
            # Slight rotation simulation via geometry jitter
            for _ in range(6):
                dx = random.randint(-4, 4)
                dy = random.randint(-2, 2)
                self.root.geometry(f"+{ox+dx}+{oy+dy}")
                self.root.update()
                time.sleep(0.04)
            self.root.geometry(f"+{ox}+{oy}")

    # ── Data ─────────────────────────────────────────────────────

    def update_stats(self):
        data = api_call("/api/stats")
        if data:
            self.stats = data
            self.level = data.get("level", 1)
            self.pet_name = data.get("name", self.pet_name)

    def auto_refresh(self):
        self.update_stats()
        self.root.after(10000, self.auto_refresh)


def start_server():
    """Start the backend server in a daemon thread."""
    import subprocess
    import sys
    server_path = Path(__file__).parent / "pet_server.py"
    subprocess.Popen(
        [sys.executable, str(server_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


if __name__ == "__main__":
    print("🖐️ 戳戳悬浮球启动中...")
    # Start backend if not running
    try:
        urllib.request.urlopen("http://localhost:5200/api/stats", timeout=1)
    except Exception:
        start_server()
        time.sleep(2)

    FloatingPet()
