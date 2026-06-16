#!/usr/bin/env python3
"""戳戳悬浮球 v2.0 — Full-featured desktop companion.

Left-click: poke  |  Right-click: menu  |  Drag: move
Stats: hunger · happiness · energy
Evolves from 蛋 → 幼年 → 成年 → 完全体
"""

import tkinter as tk
import json
import random
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

API = "http://localhost:5200"

# ── Pixel patterns for display ──────────────────────────────────
PATTERNS = {
    "happy":  ["  ########  "," ##      ## ","##        ##","#  ##  ##  #","#          #","# ##    ## #","#   ####   #","#          #","# #      # #"," #        # "," ##  ##  ## ","  ##    ##  ","   #    #   ","  #      #  "," ##  ##  ## ","   ######   "],
    "sleepy": ["            ","            ","  ########  "," ##      ## ","##        ##","#          #","#   ####   #","#          #","#          #","#          #"," #   ##   # ","  #      #  ","   #    #   ","    #  #    ","     ##     ","            "],
    "excited":["  ########  "," ##      ## ","##        ##","# ##  ##  ##","# ##    ## #","#          #","#   ####   #","#  #    #  #","# ##    ## #","# #      # #","##        ##"," ##        ##"," ##  ##  ## ","  ##    ##  ","   #    #   ","    ####    "],
    "love":   ["            "," ##      ## ","####    ####","######  ####","##########  "," ########   ","  ######    ","   ####     ","    ##      ","    ##      ","    ##      ","    ##      ","    ##      ","   ## ##    ","  ##   ##   "," ##     ##  "],
    "hungry": ["   ######   ","  ##    ##  "," ##      ## ","##        ##","# ##  ##  ##","# ##    ## #","#          #","#  ######  #","#          #","# ##    ## #","##        ##"," ##      ## "," ##  ##  ## ","  ##    ##  ","  #  ##  #  ","   ##  ##   "],
    "surprised":["  ########  "," ##      ## ","##        ##","##        ##","# ##    ## #","# ##    ## #","#          #","#    ####  #","#   #    # #","#   #    # #","##        ##"," ##  #### ##"," ##      ## ","  ########  ","            ","            "],
}


class FloatPet:
    def __init__(self):
        self.r = tk.Tk()
        self.r.title("戳戳")
        self.r.geometry("220x360+1000+400")
        self.r.attributes("-topmost", True)
        self.r.configure(bg="#1a1a1a")

        # State
        self.emotion = "happy"
        self.name = "戳戳"
        self.level = 1
        self.stage_name = "蛋"
        self.hunger = 80
        self.happiness = 80
        self.energy = 80
        self.xp = 0
        self.xp_to = 100
        self.coins = 0
        self.streak = 0
        self.total_pokes = 0
        self.species_id = None
        self.species = None
        self.shiny = False
        self.hatching = False
        self.msg_id = None
        self.drag_ox = 0
        self.drag_oy = 0

        # Canvas
        self.c = tk.Canvas(self.r, width=220, height=360, bg="#1a1a1a", highlightthickness=0)
        self.c.pack()

        # Click — poke
        self.c.bind("<Button-1>", lambda e: self.poke())
        self.r.bind("<Button-1>", lambda e: self.poke())

        # Drag
        self.c.bind("<ButtonPress-1>", self._drag_start)
        self.c.bind("<B1-Motion>", self._drag_move)

        # Right-click menu
        self._make_menu()

        # Render + start refresh loop
        self._load_state()
        self.render()
        self._auto_refresh()

        print(f"🖐️ {self.name} Lv.{self.level} ready — poke me!")
        self.r.mainloop()

    # ── Menu ─────────────────────────────────────────────────────

    def _make_menu(self):
        m = tk.Menu(self.r, tearoff=0)
        m.add_command(label="👆 戳一下 (+快乐)", command=self.poke)
        m.add_command(label="🍔 喂食 (-10🪙 +饱腹)", command=self.feed)
        m.add_command(label="🎮 玩耍 (+快乐 -体力)", command=self.play)
        m.add_command(label="💤 睡觉 (+体力)", command=self.sleep_pet)
        m.add_separator()
        m.add_command(label="📊 状态面板", command=self._show_stats)
        m.add_command(label="✏️ 改名", command=self._rename)
        m.add_separator()
        m.add_command(label="✕ 关闭", command=self._close)
        self.c.bind("<Button-2>", lambda e: m.post(e.x_root, e.y_root))
        self.c.bind("<Control-Button-1>", lambda e: m.post(e.x_root, e.y_root))

    # ── Rendering ───────────────────────────────────────────────

    def render(self):
        self.c.delete("all")
        self.c.create_rectangle(0, 0, 220, 360, fill="#1a1a1a", outline="")

        color = "#ff6b35"
        if self.species and self.species.get("color"):
            color = self.species["color"]

        ps, ox, oy = 12, 14, 8

        # Not yet hatched — show egg
        if not self.species_id:
            self._draw_egg(ox, oy, ps, color)
        else:
            # Draw species pixel art
            pat = PATTERNS.get(self.emotion, PATTERNS["happy"])
            for r in range(16):
                for c in range(16):
                    ch = pat[r][c] if r < len(pat) and c < len(pat[r]) else " "
                    if ch == "#":
                        self.c.create_rectangle(
                            ox + c*ps, oy + r*ps, ox + c*ps + ps-1, oy + r*ps + ps-1,
                            fill=color, outline=""
                        )

        # Name + species
        name_str = self.name
        if self.species:
            name_str = f"{self.species['name']} · {self.name}"
        self.c.create_text(110, 215, text=name_str[:14], fill="#e0d8d0",
                           font=("PingFang SC", 11, "bold"))

        type_str = self.species["type"] if self.species else "蛋"
        if self.shiny:
            type_str = "✨" + type_str
        stage_str = f"Lv.{self.level} · {type_str} · {self.stage_name}"
        self.c.create_text(110, 233, text=stage_str, fill=color,
                           font=("PingFang SC", 8))

        # Hatching animation message
        if self.hatching:
            self.c.create_text(110, 150, text="🥚 正在孵化...",
                               fill="#fbbf24", font=("PingFang SC", 13, "bold"))

        # Stat bars
        bar_y = 250
        self._bar(bar_y, "🍔", self.hunger, "#ff6b35")
        self._bar(bar_y+18, "😊", self.happiness, "#e8879a")
        self._bar(bar_y+36, "⚡", self.energy, "#5b9bd5")

        # XP bar
        xp_y = bar_y + 60
        xp_pct = min(100, self.xp / max(1, self.xp_to) * 100)
        self.c.create_rectangle(20, xp_y, 200, xp_y+4, fill="#333", outline="")
        if xp_pct > 0:
            self.c.create_rectangle(20, xp_y, 20+int(180*xp_pct/100), xp_y+4,
                                     fill="#ff6b35", outline="")

        # Streak fire
        if self.streak >= 3:
            self.c.create_text(110, xp_y+18, text=f"🔥 {self.streak}天连续",
                               fill="#f0c040", font=("PingFang SC", 8))
        # Coin
        self.c.create_text(110, xp_y+32, text=f"🪙 {self.coins}",
                           fill="#888", font=("PingFang SC", 8))

        # Poke count
        self.c.create_text(110, xp_y+48, text=f"今日 {self.total_pokes} 戳",
                           fill="#555", font=("PingFang SC", 7))

    def _bar(self, y, label, val, color):
        self.c.create_text(25, y+4, text=label, fill="#888",
                           font=("PingFang SC", 8), anchor="w")
        self.c.create_rectangle(52, y, 200, y+8, fill="#333", outline="")
        if val > 0:
            self.c.create_rectangle(52, y, 52+int(148*val/100), y+8,
                                     fill=color, outline="")

    def _draw_egg(self, ox, oy, ps, color):
        """Draw an egg that wobbles."""
        import time as _t
        wobble = int(_t.time() * 3) % 3 - 1  # subtle wobble
        # Egg shape
        egg_ox = ox + 14 + wobble
        egg_oy = oy + 14
        self.c.create_oval(egg_ox+8, egg_oy, egg_ox+64, egg_oy+72,
                           fill="#fef9ef", outline="#e8dcc8", width=2)
        # Warm glow inside
        self.c.create_oval(egg_ox+24, egg_oy+20, egg_ox+48, egg_oy+48,
                           fill=color, outline="")
        # Crack lines (subtle)
        self.c.create_line(egg_ox+30, egg_oy+10, egg_ox+20, egg_oy+40,
                           fill="#e8dcc8", width=1)
        # Label
        self.c.create_text(egg_ox+36, egg_oy+85, text="🥚 戳戳蛋",
                           fill=color, font=("PingFang SC", 10))

    # ── Messages ─────────────────────────────────────────────────

    def msg(self, text):
        if self.msg_id: self.c.delete(self.msg_id)
        self.msg_id = self.c.create_text(110, 215, text=text, fill="#fff",
                            font=("PingFang SC", 10, "bold"))
        self.r.after(2200, lambda: self.c.delete(self.msg_id) if self.msg_id else None)

    # ── API ──────────────────────────────────────────────────────

    def api(self, path):
        try:
            data = b"{}"
            req = urllib.request.Request(f"{API}{path}", data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read())
        except Exception:
            return None

    def api_get(self, path):
        try:
            req = urllib.request.Request(f"{API}{path}")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read())
        except Exception:
            return None

    def _load_state(self):
        d = self.api_get("/api/state")
        if d:
            self.name = d.get("name", self.name)
            self.level = d.get("level", 1)
            self.stage_name = d.get("stage_name", "蛋")
            self.hunger = d.get("hunger", 80)
            self.happiness = d.get("happiness", 80)
            self.energy = d.get("energy", 80)
            self.xp = d.get("xp", 0)
            self.xp_to = d.get("xp_to_next", 100)
            self.coins = d.get("coins", 0)
            self.streak = d.get("streak_days", 0)
            self.total_pokes = sum([
                d.get("total_pokes", 0), d.get("total_feed", 0),
                d.get("total_plays", 0), d.get("total_sleeps", 0),
            ])
            self.emotion = d.get("emotion", self.emotion)
            # Species
            old_species = self.species_id
            self.species_id = d.get("species_id")
            self.species = d.get("species")
            self.shiny = d.get("shiny", False)
            # Detect hatching
            if self.species_id and not old_species:
                self.hatching = True
                self.render()
                self.r.after(3000, self._hatch_complete)

    def _auto_refresh(self):
        self._load_state()
        self.render()
        self.r.after(10000, self._auto_refresh)

    # ── Interactions ─────────────────────────────────────────────

    def poke(self):
        self._animate("bounce")
        d = self.api("/api/poke")
        if d:
            self.emotion = d.get("reaction", self.emotion)
            self.msg(d.get("message", "嘿嘿~"))
            self._load_state()
            self.render()
            # Achievement/quest notifications
            for a in d.get("achievements_new", []):
                self.r.after(2500, lambda a=a: self.msg(f"🏆 {a}"))
            for q in d.get("quests_done", []):
                self.r.after(2800, lambda q=q: self.msg(f"✅ {q}"))
        else:
            self.msg("连接不上服务器~")

    def feed(self):
        d = self.api("/api/feed")
        if d and not d.get("error"):
            self.emotion = d.get("reaction", "love")
            self.msg(d.get("message", "好吃！"))
            self._load_state()
            self.render()
        elif d:
            self.msg(d["error"])
        else:
            self.msg("服务器未响应")

    def play(self):
        self._animate("spin")
        d = self.api("/api/play")
        if d:
            self.emotion = d.get("reaction", "excited")
            self.msg(d.get("message", "耶~"))
            self._load_state()
            self.render()

    def sleep_pet(self):
        self.emotion = "sleepy"
        self.render()
        d = self.api("/api/sleep")
        if d:
            self.msg(d.get("message", "zzZ..."))
            self._load_state()
            self.render()

    def _rename(self):
        d = tk.Toplevel(self.r)
        d.title("改名"); d.geometry("200x90+1100+500")
        d.attributes("-topmost", True)
        e = tk.Entry(d, font=("PingFang SC", 12)); e.insert(0, self.name)
        e.pack(pady=8); e.focus()
        def go():
            n = e.get().strip()
            if n:
                self.name = n
                self.render()
                # Also tell server
                try:
                    req = urllib.request.Request(f"{API}/api/rename", data=json.dumps({"name": n}).encode(), method="POST")
                    req.add_header("Content-Type", "application/json")
                    urllib.request.urlopen(req, timeout=2)
                except: pass
            d.destroy()
        e.bind("<Return>", lambda ev: go())
        tk.Button(d, text="确定", command=go).pack()

    def _show_stats(self):
        w = tk.Toplevel(self.r)
        w.title("📊 状态"); w.geometry("260x320+1100+450")
        w.attributes("-topmost", True); w.configure(bg="#1a1a1a")
        text = f"""
╔══════════════════╗
║  🖐️ {self.name}  Lv.{self.level}
║  {self.stage_name}
╠══════════════════╣
║  🍔 饱腹:   {self.hunger}/100
║  😊 快乐:   {self.happiness}/100
║  ⚡ 体力:   {self.energy}/100
║  ⭐ XP:     {self.xp}/{self.xp_to}
║  🪙 金币:   {self.coins}
║  🔥 连续:   {self.streak} 天
║  👆 今日:   {self.total_pokes} 戳
╚══════════════════╝
        """
        tk.Label(w, text=text, fg="#e0d8d0", bg="#1a1a1a",
                 font=("PingFang SC", 11), justify="left").pack(padx=10, pady=10)

    # ── Animations ──────────────────────────────────────────────

    def _animate(self, kind):
        ox, oy = self.r.winfo_x(), self.r.winfo_y()
        if kind == "bounce":
            steps = [-10, -5, -2, 0, 3, 0]
            self._anim_seq(ox, oy, 0, steps)
        elif kind == "shake":
            steps = [-8, 8, -6, 6, -3, 3, 0]
            self._anim_seq_x(ox, oy, 0, steps)
        elif kind == "spin":
            for i in range(5):
                self.r.after(i*35, lambda: self.r.geometry(
                    f"+{ox+random.randint(-5,5)}+{oy+random.randint(-3,3)}"))
            self.r.after(175, lambda: self.r.geometry(f"+{ox}+{oy}"))

    def _anim_seq(self, ox, oy, i, steps):
        if i >= len(steps): return
        self.r.geometry(f"+{ox}+{oy+steps[i]}")
        self.r.after(30, lambda: self._anim_seq(ox, oy, i+1, steps))

    def _anim_seq_x(self, ox, oy, i, steps):
        if i >= len(steps): return
        self.r.geometry(f"+{ox+steps[i]}+{oy}")
        self.r.after(30, lambda: self._anim_seq_x(ox, oy, i+1, steps))

    # ── Drag ────────────────────────────────────────────────────

    def _drag_start(self, e):
        self.drag_ox, self.drag_oy = e.x, e.y

    def _drag_move(self, e):
        self.r.geometry(f"+{e.x_root - self.drag_ox}+{e.y_root - self.drag_oy}")

    def _hatch_complete(self):
        self.hatching = False
        sp = self.species or {}
        hint = sp.get("egg_hint", "蛋孵化了！")
        self.msg(f"🎉 {sp.get('name','？')} 孵化了！\n{sp.get('desc','')}")
        self.render()

    def _close(self):
        self.r.destroy()


def start_server():
    import subprocess, sys, time
    server = Path(__file__).parent / "pet_server.py"
    subprocess.Popen([sys.executable, str(server)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)


if __name__ == "__main__":
    print("🖐️ 戳戳悬浮球 v2.0 启动...")
    try:
        urllib.request.urlopen("http://localhost:5200/api/state", timeout=1)
    except Exception:
        print("  启动后端...")
        start_server()
    FloatPet()
