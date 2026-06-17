#!/usr/bin/env python3
"""戳戳 Pro Max — Pygame 引擎桌面宠物。真正的动画、粒子、特效。"""

import pygame
import math, random, json, time, urllib.request, sys
from pathlib import Path

API = "http://localhost:5200"
W, H = 260, 400

class GamePet:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H), pygame.NOFRAME)
        pygame.display.set_caption("戳戳 Pro")
        self.clock = pygame.time.Clock()
        self.running = True
        try:
            self.font = pygame.font.Font(None, 24)
            self.small_font = pygame.font.Font(None, 16)
        except Exception:
            self.font = None
            self.small_font = None

        # State
        self.name = "戳戳"
        self.level = 1
        self.emotion = "happy"
        self.species = "cat"
        self.color = self._hex_to_rgb("#ff9c6e")
        self.msg = ""
        self.msg_timer = 0
        self.particles = []
        self.bob_offset = 0
        self.bob_dir = 1
        self.scale = 1.0
        self.drag = False

        self._load_state()
        self._run()

    def _hex_to_rgb(self, h):
        return (int(h[1:3],16), int(h[3:5],16), int(h[5:7],16))

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
                self.color = self._hex_to_rgb(sp.get("color", "#ff9c6e"))

    def _run(self):
        frame = 0
        while self.running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.poke()
                    elif event.button == 3:
                        self._show_context_menu()
                elif event.type == pygame.MOUSEMOTION and self.drag:
                    dx, dy = event.rel
                    pos = pygame.display.get_window_position()
                    pygame.display.set_window_position((pos[0]+dx, pos[1]+dy))

            # Idle animation
            self.bob_offset += self.bob_dir * 0.3
            if abs(self.bob_offset) > 5:
                self.bob_dir *= -1

            # Particles
            self.particles = [p for p in self.particles if p["life"] > 0]
            for p in self.particles:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["vy"] += 0.3  # gravity
                p["life"] -= 1

            # Render
            self.screen.fill((13, 13, 13))
            self._draw_character()
            self._draw_particles()
            if self.msg and self.msg_timer > 0:
                self._draw_msg()
                self.msg_timer -= 1

            pygame.display.flip()

            # Periodic
            frame += 1
            if frame % 600 == 0:
                self._load_state()

        pygame.quit()

    def _draw_character(self):
        cx, cy = W//2, 160 + int(self.bob_offset)

        # ── Shadow ──
        pygame.draw.ellipse(self.screen, (5,5,5),
                            (cx-60, cy+75, 120, 16))

        # ── Body ──
        body_rect = (cx-55, cy-25, 110, 105)
        pygame.draw.ellipse(self.screen, self.color, body_rect)
        # Highlight
        hl = self._lighten(self.color, 50)
        pygame.draw.ellipse(self.screen, hl, (cx-30, cy+15, 60, 50))
        # Top shine
        pygame.draw.ellipse(self.screen, (255,255,255,40),
                            (cx-20, cy-10, 35, 25), 2)

        # ── Ears ──
        dark = self._darken(self.color, 30)
        light = self._lighten(self.color, 40)
        # Left
        pygame.draw.polygon(self.screen, self.color,
                            [(cx-42,cy-18),(cx-30,cy-58),(cx-8,cy-18)])
        pygame.draw.polygon(self.screen, light,
                            [(cx-36,cy-20),(cx-28,cy-48),(cx-14,cy-20)])
        # Right
        pygame.draw.polygon(self.screen, self.color,
                            [(cx+42,cy-18),(cx+30,cy-58),(cx+8,cy-18)])
        pygame.draw.polygon(self.screen, light,
                            [(cx+36,cy-20),(cx+28,cy-48),(cx+14,cy-20)])

        # ── Eyes ──
        ey = cy - 5
        if self.emotion == "sleepy":
            pygame.draw.arc(self.screen, (20,20,20), (cx-32,ey-8,28,16), math.pi, 2*math.pi, 3)
            pygame.draw.arc(self.screen, (20,20,20), (cx+4,ey-8,28,16), math.pi, 2*math.pi, 3)
        else:
            pygame.draw.ellipse(self.screen, (255,255,255), (cx-32,ey-10,28,20))
            pygame.draw.ellipse(self.screen, (255,255,255), (cx+4,ey-10,28,20))
            pygame.draw.ellipse(self.screen, (10,10,10), (cx-22,ey-4,12,8))
            pygame.draw.ellipse(self.screen, (10,10,10), (cx+10,ey-4,12,8))
            if self.emotion == "excited":
                pygame.draw.ellipse(self.screen, (255,255,255), (cx-30,ey-12,6,6))
                pygame.draw.ellipse(self.screen, (255,255,255), (cx+24,ey-12,6,6))

        # ── Cheeks ──
        blush = self._lighten(self.color, 70)
        pygame.draw.ellipse(self.screen, blush, (cx-44,cy+14,18,12))
        pygame.draw.ellipse(self.screen, blush, (cx+26,cy+14,18,12))

        # ── Mouth ──
        my = cy + 20
        if self.emotion == "happy":
            pygame.draw.arc(self.screen, (10,10,10), (cx-14,my-5,28,16), 0, math.pi, 3)
        elif self.emotion == "surprised":
            pygame.draw.ellipse(self.screen, (10,10,10), (cx-6,my,12,14))

        # ── Arms ──
        pygame.draw.ellipse(self.screen, dark, (cx-65,cy+20,30,35))
        pygame.draw.ellipse(self.screen, dark, (cx+35,cy+20,30,35))
        # Feet
        pygame.draw.ellipse(self.screen, dark, (cx-38,cy+68,30,16))
        pygame.draw.ellipse(self.screen, dark, (cx+8,cy+68,30,16))

        # ── Name ──
        if self.font:
            name_surf = self.font.render(f"{self.name} Lv.{self.level}", True, (220,210,200))
            self.screen.blit(name_surf, (W//2 - name_surf.get_width()//2, cy+95))

    def _draw_particles(self):
        for p in self.particles:
            alpha = int(255 * p["life"] / p["max_life"])
            color = (*p["color"], alpha) if len(p["color"]) == 3 else p["color"]
            try:
                s = pygame.Surface((p["size"]*2, p["size"]*2), pygame.SRCALPHA)
                pygame.draw.circle(s, color + (alpha,), (p["size"], p["size"]), p["size"])
                self.screen.blit(s, (int(p["x"]-p["size"]), int(p["y"]-p["size"])))
            except: pass

    def _draw_msg(self):
        if not self.font: return
        alpha = min(255, self.msg_timer * 5)
        try:
            s = pygame.Surface((200, 40), pygame.SRCALPHA)
            s.fill((0,0,0,0))
            txt = self.font.render(self.msg, True, (255,255,255))
            s.blit(txt, (100 - txt.get_width()//2, 10))
            s.set_alpha(alpha)
            self.screen.blit(s, (W//2-100, 30))
        except: pass

    def _spawn_particles(self, count=12):
        for _ in range(count):
            self.particles.append({
                "x": W//2, "y": 160,
                "vx": random.uniform(-4, 4),
                "vy": random.uniform(-5, 1),
                "life": random.randint(15, 35),
                "max_life": 35,
                "size": random.randint(2, 6),
                "color": random.choice([(255,107,53),(251,191,36),(255,255,255)])
            })

    def _bounce(self):
        self.bob_offset = -12
        self.bob_dir = 1

    def poke(self):
        self._bounce()
        self._spawn_particles()
        d = self._api("/api/poke")
        if d:
            self.emotion = d.get("reaction", self.emotion)
            self.msg = d.get("message", "嘿嘿~")
            self.msg_timer = 60
            self._load_state()

    def _show_context_menu(self):
        pass  # Pygame has no native menu — we use gestures

    def _lighten(self, c, a):
        return tuple(min(255, x+a) for x in c)
    def _darken(self, c, a):
        return tuple(max(0, x-a) for x in c)


def start_server():
    import subprocess
    srv = Path(__file__).parent / "pet_server.py"
    subprocess.Popen([sys.executable, str(srv)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)


if __name__ == "__main__":
    try:
        urllib.request.urlopen("http://localhost:5200/api/state", timeout=1)
    except:
        start_server()
    GamePet()
