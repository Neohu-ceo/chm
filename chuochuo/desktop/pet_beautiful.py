#!/usr/bin/env python3
"""戳戳 Pro — 矢量卡通桌面宠物。不再是像素块。"""

import tkinter as tk
import math, random, json, time, urllib.request
from pathlib import Path

API = "http://localhost:5200"

class SmoothPet:
    def __init__(self):
        self.r = tk.Tk()
        self.r.title("戳戳 Pro")
        self.r.geometry("240x380+1000+300")
        self.r.attributes("-topmost", True)
        self.r.configure(bg="#0d0d0d")

        self.c = tk.Canvas(self.r, width=240, height=380, bg="#0d0d0d", highlightthickness=0)
        self.c.pack()

        # State
        self.name = "戳戳"
        self.level = 1
        self.emotion = "happy"
        self.species = "cat"
        self.color = "#ff9c6e"
        self.msg_id = None
        self.anim_items = []
        self.particles = []

        # Click = poke
        self.c.bind("<Button-1>", lambda e: self.poke())
        self.r.bind("<Button-1>", lambda e: self.poke())

        # Drag
        self.c.bind("<ButtonPress-1>", self._drag_start)
        self.c.bind("<B1-Motion>", self._drag_move)

        # Right-click menu
        self._menu = tk.Menu(self.r, tearoff=0)
        self._menu.add_command(label="👆 戳一下", command=self.poke)
        self._menu.add_command(label="🍔 喂食", command=self.feed)
        self._menu.add_command(label="💤 睡觉", command=self.sleep_pet)
        self._menu.add_command(label="✏️ 改名", command=self._rename)
        self._menu.add_separator()
        self._menu.add_command(label="✕ 关闭", command=self.r.destroy)
        self.c.bind("<Button-2>", lambda e: self._menu.post(e.x_root, e.y_root))
        self.c.bind("<Button-3>", lambda e: self._menu.post(e.x_root, e.y_root))
        self.c.bind("<Control-Button-1>", lambda e: self._menu.post(e.x_root, e.y_root))

        self._load_state()
        self._render()
        self._animate_idle()
        self._auto_refresh()

        self.r.mainloop()

    # ── API ──────────────────────────────────────────────────────

    def _api(self, path):
        try:
            req = urllib.request.Request(f"{API}{path}", data=b"{}", method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=2) as r:
                return json.loads(r.read())
        except: return None

    def _api_get(self, path):
        try:
            req = urllib.request.Request(f"{API}{path}")
            with urllib.request.urlopen(req, timeout=2) as r:
                return json.loads(r.read())
        except: return None

    def _load_state(self):
        d = self._api_get("/api/state")
        if d:
            self.name = d.get("name", self.name)
            self.level = d.get("level", 1)
            self.emotion = d.get("emotion", "happy")
            sp = d.get("species")
            if sp:
                self.species = d.get("species_id", "cat")
                self.color = sp.get("color", self.color)

    def _auto_refresh(self):
        self._load_state()
        self._render()
        self.r.after(15000, self._auto_refresh)

    # ── Vector Character Rendering ──────────────────────────────

    def _render(self):
        self.c.delete("char")
        cx, cy = 120, 145  # center of character

        # ── Shadow ──
        self.c.create_oval(cx-55, cy+70, cx+55, cy+80, fill="#050505", outline="", tags="char")

        # ── Body (smooth blob) ──
        body_color = self.color
        # Main body
        self.c.create_oval(cx-50, cy-20, cx+50, cy+75, fill=body_color, outline="", tags="char")
        # Belly highlight
        self.c.create_oval(cx-25, cy+15, cx+25, cy+65, fill=self._lighten(body_color, 40), outline="", tags="char")
        # Top highlight
        self.c.create_oval(cx-20, cy-10, cx+15, cy+25, fill="white", outline="", stipple="gray25", tags="char")

        # ── Eyes ──
        eye_y = cy - 5
        if self.emotion == "sleepy":
            # Closed eyes (arcs)
            self.c.create_arc(cx-30, eye_y-8, cx-5, eye_y+8, start=0, extent=-180, fill="#1a1a1a", outline="#1a1a1a", width=3, style="chord", tags="char")
            self.c.create_arc(cx+5, eye_y-8, cx+30, eye_y+8, start=0, extent=-180, fill="#1a1a1a", outline="#1a1a1a", width=3, style="chord", tags="char")
        elif self.emotion == "excited":
            # Big sparkly eyes
            self.c.create_oval(cx-32, eye_y-12, cx-2, eye_y+12, fill="white", outline="#1a1a1a", width=2, tags="char")
            self.c.create_oval(cx+2, eye_y-12, cx+32, eye_y+12, fill="white", outline="#1a1a1a", width=2, tags="char")
            self.c.create_oval(cx-20, eye_y-5, cx-14, eye_y+5, fill="#1a1a1a", tags="char")
            self.c.create_oval(cx+14, eye_y-5, cx+20, eye_y+5, fill="#1a1a1a", tags="char")
            # Sparkle dots
            self.c.create_oval(cx-28, eye_y-10, cx-24, eye_y-6, fill="white", tags="char")
            self.c.create_oval(cx+24, eye_y-10, cx+28, eye_y-6, fill="white", tags="char")
        else:
            # Normal round eyes
            self.c.create_oval(cx-30, eye_y-10, cx-5, eye_y+10, fill="white", outline="#1a1a1a", width=2, tags="char")
            self.c.create_oval(cx+5, eye_y-10, cx+30, eye_y+10, fill="white", outline="#1a1a1a", width=2, tags="char")
            self.c.create_oval(cx-20, eye_y-4, cx-12, eye_y+4, fill="#1a1a1a", tags="char")
            self.c.create_oval(cx+12, eye_y-4, cx+20, eye_y+4, fill="#1a1a1a", tags="char")

        # ── Cheeks (blush) ──
        cheek_color = self._lighten(self.color, 60) if self.emotion != "love" else "#ff9999"
        self.c.create_oval(cx-42, cy+12, cx-28, cy+24, fill=cheek_color, outline="", stipple="gray50", tags="char")
        self.c.create_oval(cx+28, cy+12, cx+42, cy+24, fill=cheek_color, outline="", stipple="gray50", tags="char")

        # ── Mouth ──
        mouth_y = cy + 18
        if self.emotion == "happy":
            self.c.create_arc(cx-12, mouth_y-5, cx+12, mouth_y+12, start=0, extent=-180, fill="#1a1a1a", outline="", style="chord", tags="char")
        elif self.emotion == "sleepy":
            self.c.create_oval(cx-6, mouth_y, cx+6, mouth_y+8, fill="#1a1a1a", outline="", tags="char")
        elif self.emotion == "excited":
            self.c.create_oval(cx-8, mouth_y-2, cx+8, mouth_y+10, fill="#1a1a1a", outline="", tags="char")
        elif self.emotion == "surprised":
            self.c.create_oval(cx-5, mouth_y, cx+5, mouth_y+12, fill="#1a1a1a", outline="", tags="char")
        elif self.emotion == "love":
            # Heart mouth
            pts = [cx, mouth_y+14, cx-10, mouth_y, cx-3, mouth_y-7, cx, mouth_y+2, cx+3, mouth_y-7, cx+10, mouth_y]
            self.c.create_polygon(pts, fill="#ff6b6b", outline="", smooth=True, tags="char")

        # ── Ears (cat-like) ──
        if self.species in ("cat", "fox"):
            # Left ear
            self.c.create_polygon(cx-40, cy-15, cx-30, cy-50, cx-10, cy-15,
                                  fill=self.color, outline="", smooth=True, tags="char")
            self.c.create_polygon(cx-34, cy-18, cx-28, cy-42, cx-16, cy-18,
                                  fill=self._lighten(self.color, 30), outline="", smooth=True, tags="char")
            # Right ear
            self.c.create_polygon(cx+40, cy-15, cx+30, cy-50, cx+10, cy-15,
                                  fill=self.color, outline="", smooth=True, tags="char")
            self.c.create_polygon(cx+34, cy-18, cx+28, cy-42, cx+16, cy-18,
                                  fill=self._lighten(self.color, 30), outline="", smooth=True, tags="char")

        # ── Arms ──
        arm_color = self._darken(self.color, 20)
        # Left arm
        self.c.create_oval(cx-60, cy+20, cx-35, cy+55, fill=arm_color, outline="", tags="char")
        # Right arm
        self.c.create_oval(cx+35, cy+20, cx+60, cy+55, fill=arm_color, outline="", tags="char")

        # ── Feet ──
        self.c.create_oval(cx-35, cy+65, cx-10, cy+80, fill=arm_color, outline="", tags="char")
        self.c.create_oval(cx+10, cy+65, cx+35, cy+80, fill=arm_color, outline="", tags="char")

        # ── Info text ──
        self.c.create_text(cx, cy+105, text=self.name, fill="#e0d8d0",
                           font=("PingFang SC", 12, "bold"), tags="char")
        self.c.create_text(cx, cy+122, text=f"Lv.{self.level}",
                           fill=self.color, font=("PingFang SC", 9), tags="char")

    def _lighten(self, hex_color, amount):
        r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
        r, g, b = min(255, r+amount), min(255, g+amount), min(255, b+amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _darken(self, hex_color, amount):
        r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
        r, g, b = max(0, r-amount), max(0, g-amount), max(0, b-amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ── Idle Animation ──────────────────────────────────────────

    def _animate_idle(self):
        """Gentle bobbing animation."""
        # Subtle float
        items = self.c.find_withtag("char")
        for item in items:
            self.c.move(item, 0, -2)
        self.r.after(1200, self._animate_idle_return)

    def _animate_idle_return(self):
        items = self.c.find_withtag("char")
        for item in items:
            self.c.move(item, 0, 2)
        self.r.after(1200, self._animate_idle)

    # ── Interactions ────────────────────────────────────────────

    def poke(self):
        self._bounce_anim()
        d = self._api("/api/poke")
        if d:
            self.emotion = d.get("reaction", self.emotion)
            self._show_msg(d.get("message", "嘿嘿~"))
            self._spawn_particles()
            self._load_state()
            self._render()

    def feed(self):
        d = self._api("/api/feed")
        if d and not d.get("error"):
            self.emotion = d.get("reaction", "love")
            self._show_msg(d.get("message", "好吃！"))
            self._load_state()
            self._render()

    def sleep_pet(self):
        self.emotion = "sleepy"
        self._render()
        d = self._api("/api/sleep")
        if d: self._show_msg(d.get("message", "zzZ..."))
        self._load_state()

    def _rename(self):
        d = tk.Toplevel(self.r)
        d.title("改名"); d.geometry("200x90+1100+500"); d.attributes("-topmost", True)
        e = tk.Entry(d, font=("PingFang SC", 12)); e.insert(0, self.name)
        e.pack(pady=8); e.focus()
        def go():
            n = e.get().strip()
            if n:
                self.name = n; self._render()
                try:
                    req = urllib.request.Request(f"{API}/api/rename",
                        data=json.dumps({"name":n}).encode(), method="POST")
                    req.add_header("Content-Type", "application/json")
                    urllib.request.urlopen(req, timeout=2)
                except: pass
            d.destroy()
        e.bind("<Return>", lambda ev: go())
        tk.Button(d, text="确定", command=go).pack()

    # ── Effects ─────────────────────────────────────────────────

    def _show_msg(self, text):
        if self.msg_id: self.c.delete(self.msg_id)
        self.msg_id = self.c.create_text(120, 50, text=text, fill="#fff",
                            font=("PingFang SC", 11, "bold"))
        self.r.after(2000, lambda: self.c.delete(self.msg_id) if self.msg_id else None)

    def _spawn_particles(self):
        """Little sparkle particles that fly outward."""
        for _ in range(8):
            x, y = 120, 145
            dx = random.randint(-60, 60)
            dy = random.randint(-60, 20)
            size = random.randint(2, 5)
            color = random.choice(["#ff6b35", "#fbbf24", "#fff", "#ff9999"])
            pid = self.c.create_oval(x+dx, y+dy, x+dx+size, y+dy+size,
                                      fill=color, outline="")
            self.r.after(400, lambda p=pid: self.c.delete(p))

    def _bounce_anim(self):
        items = self.c.find_withtag("char")
        for step in [-12, -6, -3, 0, 4, 0]:
            for item in items:
                self.c.move(item, 0, step)
            self.r.update()
            time.sleep(0.02)

    # ── Drag ────────────────────────────────────────────────────

    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _drag_move(self, e):
        self.r.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")


def start_server():
    import subprocess, sys
    srv = Path(__file__).parent / "pet_server.py"
    subprocess.Popen([sys.executable, str(srv)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)


if __name__ == "__main__":
    try:
        urllib.request.urlopen("http://localhost:5200/api/state", timeout=1)
    except:
        start_server()
    SmoothPet()
