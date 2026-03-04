#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║        BREAKOUT — Panda3D · Power Bricks Edition             ║
║   Controls: A/D or Arrows · SPACE launch · ESC pause · Q quit║
║   Music: M to mute/unmute                                    ║
╚══════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations
import json
import math
import sys
from typing import List, Optional, Tuple

# ── Panda3D bootstrap (before ShowBase import) ─────────────────
from panda3d.core import loadPrcFileData  # noqa: E402

loadPrcFileData("", "window-title BREAKOUT — Power Edition")
loadPrcFileData("", "win-size 800 600")
loadPrcFileData("", "sync-video 0")
# IMPORTANTE: Habilitar audio (cambiado de "null" a "p3openal_audio")
loadPrcFileData("", "audio-library-name p3openal_audio")

from direct.gui.DirectGui import DirectButton  # noqa: E402
from direct.gui.OnscreenText import OnscreenText  # noqa: E402
from direct.showbase.ShowBase import ShowBase  # noqa: E402
from direct.task import Task  # noqa: E402
from panda3d.core import (  # noqa: E402
    CardMaker,
    LColor,
    NodePath,
    TextNode,
    WindowProperties,
    AudioSound,
)

# ════════════════════════════════════════════════════════════════
#  SECTION 1 · CONFIG
#  All tunable constants live here.
# ════════════════════════════════════════════════════════════════
WIN_W: int = 800
WIN_H: int = 600

# Field boundaries in Panda3D aspect2d world-units.
F_LEFT:   float = -0.90
F_RIGHT:  float =  0.90
F_TOP:    float =  0.93
F_BOTTOM: float = -0.98
WALL_T:   float =  0.025

# Effective bounce boundaries for the ball centre
B_LEFT:  float = F_LEFT  + WALL_T * 2
B_RIGHT: float = F_RIGHT - WALL_T * 2
B_TOP:   float = F_TOP   - WALL_T * 2

# ── Paddle ──────────────────────────────────────────────────────
PAD_W:     float = 0.28
PAD_H:     float = 0.046
PAD_Y:     float = -0.83
PAD_SPEED: float = 1.90
PAD_MIN_X: float = B_LEFT  + PAD_W / 2
PAD_MAX_X: float = B_RIGHT - PAD_W / 2

# ── Ball ────────────────────────────────────────────────────────
BALL_R:       float = 0.028
BALL_SPD0:    float = 0.90
BALL_SPD_MAX: float = 2.20
BALL_ACCEL:   float = 0.022
MIN_VY:       float = 0.28
DT_CAP:       float = 0.05
SUBSTEPS:     int   = 4

# ── Bricks ──────────────────────────────────────────────────────
BRICK_W:    float = 0.162
BRICK_H:    float = 0.062
BRICK_PX:   float = 0.010
BRICK_PY:   float = 0.009
BRICK_COLS: int   = 10
BRICK_Y0:   float = 0.73

# ── Scoring ─────────────────────────────────────────────────────
LIVES0:    int = 3
PTS_NORM:  int = 10
PTS_HARD1: int = 5
PTS_HARD2: int = 25
PTS_POWER: int = 20   # points for destroying a power brick
SAVE_FILE: str = "save.json"

# ── Power bricks ────────────────────────────────────────────────
# Brick type IDs (used in LEVELS matrices)
BTYPE_MULTI:  int   = 7    # cyan   – splits into 3 balls
BTYPE_SLOW:   int   = 8    # purple – slows all balls temporarily
BTYPE_FAST:   int   = 10   # orange – speeds all balls temporarily
POWER_DUR:    float = 8.0  # seconds the slow/fast effect lasts
SLOW_FACTOR:  float = 0.55 # speed multiplier when SLOW is active
FAST_FACTOR:  float = 1.60 # speed multiplier when FAST is active
MULTI_CAP:    int   = 8    # maximum simultaneous balls (safety cap)
POWER_BTYPES        = {BTYPE_MULTI, BTYPE_SLOW, BTYPE_FAST}

# ── Colours ─────────────────────────────────────────────────────
C_BG     = LColor(0.04, 0.04, 0.12, 1)
C_WALL   = LColor(0.26, 0.29, 0.44, 1)
C_PADDLE = LColor(0.93, 0.93, 0.93, 1)
C_BALL   = LColor(1.00, 0.97, 0.58, 1)   # yellow – original ball
C_BALL_X = LColor(0.72, 1.00, 0.72, 1)   # pale green – extra balls
C_HARD   = LColor(0.66, 0.68, 0.75, 1)
C_HARD2  = LColor(0.93, 0.56, 0.18, 1)
C_MULTI  = LColor(0.10, 0.95, 0.95, 1)   # cyan   – multi-ball brick
C_SLOW   = LColor(0.62, 0.12, 0.95, 1)   # purple – slow brick
C_FAST   = LColor(1.00, 0.38, 0.05, 1)   # orange – fast brick

ROW_COLORS: List[LColor] = [
    LColor(1.00, 0.18, 0.18, 1),   # 0 – red
    LColor(1.00, 0.52, 0.10, 1),   # 1 – orange
    LColor(1.00, 0.90, 0.10, 1),   # 2 – yellow
    LColor(0.18, 0.88, 0.20, 1),   # 3 – green
    LColor(0.12, 0.58, 1.00, 1),   # 4 – blue
    LColor(0.80, 0.18, 1.00, 1),   # 5 – purple
]

# ════════════════════════════════════════════════════════════════
#  SECTION 2 · LEVELS
#  0=empty   1-6=normal brick   7=multi-ball   8=slow
#  9=hard (2 hits)              10=fast
# ════════════════════════════════════════════════════════════════
LEVELS: List[List[List[int]]] = [
    # ── Level 1 · Classic rainbow (intro – no power bricks) ────
    [
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
        [3, 3, 3, 3, 3, 3, 3, 3, 3, 3],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [6, 6, 6, 6, 6, 6, 6, 6, 6, 6],
    ],
    # ── Level 2 · Diamond + first power bricks ─────────────────
    [
        [0, 0, 0, 1,  1,  1,  1, 0, 0, 0],
        [0, 0, 2, 2,  7,  2,  2, 2, 0, 0],   # 7=multi-ball
        [0, 3, 3, 3,  3,  3,  3, 3, 3, 0],
        [4, 4, 8, 0,  0,  0,  0,10, 4, 4],   # 8=slow, 10=fast
        [5, 5, 5, 5,  7,  7,  5, 5, 5, 5],   # 7=multi-ball x2
        [6, 0, 6, 0,  6,  6,  0, 6, 0, 6],
    ],
    # ── Level 3 · Hard bricks + power bricks ───────────────────
    [
        [9, 0, 9, 0,  9,  9,  0, 9, 0, 9],
        [0, 7, 0, 1,  0,  0,  1, 0, 7, 0],   # 7=multi-ball
        [2, 9, 2, 9,  8,  8,  9, 2, 9, 2],   # 8=slow x2
        [0, 3, 0, 3,  0,  0,  3, 0, 3, 0],
        [4, 9,10, 9,  4,  4,  9,10, 9, 4],   # 10=fast x2
        [5, 0, 5, 0,  5,  5,  0, 5, 0, 5],
    ],
    # ── Level 4 · Power brick chaos ────────────────────────────
    [
        [9, 7, 9, 7,  9,  9,  7, 9, 7, 9],
        [8, 1, 8, 1,  8,  8,  1, 8, 1, 8],
        [2,10, 2,10,  2,  2, 10, 2,10, 2],
        [9, 3, 9, 7,  9,  9,  7, 9, 3, 9],
        [7, 4, 8, 4,  7,  7,  4, 8, 4, 7],
        [5, 9,10, 9,  5,  5,  9,10, 9, 5],
    ],
]

# ════════════════════════════════════════════════════════════════
#  SECTION 3 · UTILITIES
# ════════════════════════════════════════════════════════════════

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def norm2(x: float, y: float):
    m = math.hypot(x, y)
    return (x / m, y / m) if m > 1e-9 else (0.0, 1.0)


def fix_vy(vx: float, vy: float, spd: Optional[float] = None):
    if spd is None:
        spd = math.hypot(vx, vy)
    if abs(vy) < MIN_VY:
        vy = math.copysign(MIN_VY, vy if vy != 0 else -1.0)
        vx = math.copysign(
            math.sqrt(max(0.0, spd * spd - vy * vy)),
            vx if vx != 0 else 1.0,
        )
    return vx, vy


def make_card(parent: NodePath, name: str, w: float, h: float,
              color: LColor) -> NodePath:
    cm = CardMaker(name)
    cm.setFrame(-w / 2, w / 2, -h / 2, h / 2)
    np = parent.attachNewNode(cm.generate())
    np.setColor(color)
    np.setDepthTest(False)
    np.setDepthWrite(False)
    np.setBin("fixed", 10)
    return np


def load_hs() -> int:
    try:
        with open(SAVE_FILE) as f:
            return int(json.load(f).get("high_score", 0))
    except Exception:
        return 0


def save_hs(score: int) -> None:
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump({"high_score": score}, f)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
#  SECTION 4 · SOUND MANAGER (Simple - 3 sounds only)
# ════════════════════════════════════════════════════════════════

class SimpleSoundManager:
    """Gestor simple de sonidos - fondo, perder vida y game over."""
    
    def __init__(self, base):
        self.base = base
        self.sounds = {}
        self.muted = False
        self.music_volume = 0.3  # Volumen moderado
        
        # Cargar solo los 3 sonidos necesarios
        
        self._load_sound("background", "sounds/background.wav", is_music=True)
        self._load_sound("life_lost", "sounds/life_lost.wav")
        self._load_sound("game_over", "sounds/game_over.wav")
        
        # Iniciar música de fondo
        self.play_music()
    
    def _load_sound(self, name, path, is_music=False):
        """Carga un archivo de sonido."""
        try:
            sound = self.base.loader.loadSfx(path)
            if is_music:
                sound.setLoop(True)
                sound.setVolume(self.music_volume)
            self.sounds[name] = sound
            print(f"✅ Sonido cargado: {path}")
        except Exception as e:
            print(f"⚠️ No se pudo cargar {path}: {e}")
            self.sounds[name] = None
    
    def play(self, name):
        """Reproduce un efecto de sonido."""
        if self.muted:
            return
        sound = self.sounds.get(name)
        if sound:
            sound.play()
    
    def play_music(self):
        """Inicia la música de fondo."""
        if self.muted:
            return
        music = self.sounds.get("background")
        if music and music.status() != AudioSound.PLAYING:
            music.play()
    
    def stop_music(self):
        """Detiene la música."""
        music = self.sounds.get("background")
        if music:
            music.stop()
    
    def pause_music(self):
        """Pausa la música."""
        music = self.sounds.get("background")
        if music:
            music.pause()
    
    def resume_music(self):
        """Reanuda la música."""
        if self.muted:
            return
        music = self.sounds.get("background")
        if music:
            music.resume()
    
    def toggle_mute(self):
        """Activa/desactiva el mute con M."""
        self.muted = not self.muted
        music = self.sounds.get("background")
        if music:
            if self.muted:
                music.setVolume(0)
            else:
                music.setVolume(self.music_volume)
        return self.muted


# ════════════════════════════════════════════════════════════════
#  SECTION 5 · ENTITIES
# ════════════════════════════════════════════════════════════════

class Paddle:
    """Player-controlled paddle."""

    def __init__(self, root: NodePath) -> None:
        self.np: NodePath = make_card(root, "paddle", PAD_W, PAD_H, C_PADDLE)
        self.x:  float    = 0.0
        self.ml: bool     = False
        self.mr: bool     = False
        self.np.setPos(0, 0, PAD_Y)

    @property
    def left(self)   -> float: return self.x - PAD_W / 2
    @property
    def right(self)  -> float: return self.x + PAD_W / 2
    @property
    def top(self)    -> float: return PAD_Y + PAD_H / 2
    @property
    def bottom(self) -> float: return PAD_Y - PAD_H / 2

    def update(self, dt: float) -> None:
        dx = (PAD_SPEED if self.mr else 0.0) - (PAD_SPEED if self.ml else 0.0)
        self.x = clamp(self.x + dx * dt, PAD_MIN_X, PAD_MAX_X)
        self.np.setPos(self.x, 0, PAD_Y)

    def reset(self) -> None:
        self.x = 0.0
        self.ml = self.mr = False
        self.np.setPos(0, 0, PAD_Y)


class Ball:
    """The game ball.  `extra=True` gives it a green tint so players can
    distinguish original ball from multi-ball clones."""

    def __init__(self, root: NodePath, extra: bool = False) -> None:
        side = BALL_R * 2
        col  = C_BALL_X if extra else C_BALL
        self.np:        NodePath = make_card(root, "ball", side, side, col)
        self.x:         float    = 0.0
        self.y:         float    = PAD_Y + PAD_H / 2 + BALL_R + 0.004
        self.vx:        float    = 0.0
        self.vy:        float    = 0.0
        self.spd:       float    = BALL_SPD0
        self.on_paddle: bool     = True
        self.np.setPos(self.x, 0, self.y)

    def attach_to(self, px: float) -> None:
        self.x = px
        self.y = PAD_Y + PAD_H / 2 + BALL_R + 0.004
        self.on_paddle = True
        self.np.setPos(self.x, 0, self.y)

    def launch(self) -> None:
        if not self.on_paddle:
            return
        self.on_paddle = False
        angle_from_vert = math.radians(18)
        self.vx = self.spd * math.sin(angle_from_vert)
        self.vy = self.spd * math.cos(angle_from_vert)
        self.vx, self.vy = fix_vy(self.vx, self.vy, self.spd)


class Brick:
    """A single brick in the grid, including power-brick variants."""

    # (color, hits) for special brick types
    _SPECIAL: dict = {
        9:            (None,    2),   # hard – color set below
        BTYPE_MULTI:  (C_MULTI, 1),
        BTYPE_SLOW:   (C_SLOW,  1),
        BTYPE_FAST:   (C_FAST,  1),
    }

    def __init__(self, root: NodePath, col: int, row: int, btype: int) -> None:
        self.col:     int   = col
        self.row:     int   = row
        self.btype:   int   = btype
        self.alive:   bool  = True
        self.flash_t: float = 0.0

        if btype in self._SPECIAL:
            init_color, self.hits = self._SPECIAL[btype]
            if btype == 9:
                init_color = C_HARD
        else:
            init_color = ROW_COLORS[(btype - 1) % len(ROW_COLORS)]
            self.hits  = 1

        self.np = make_card(root, f"b{row}_{col}", BRICK_W, BRICK_H, init_color)

        total_w = BRICK_COLS * BRICK_W + (BRICK_COLS - 1) * BRICK_PX
        x0 = -total_w / 2 + BRICK_W / 2
        self.cx: float = x0 + col * (BRICK_W + BRICK_PX)
        self.cy: float = BRICK_Y0 - row * (BRICK_H + BRICK_PY)
        self.np.setPos(self.cx, 0, self.cy)

    @property
    def left(self)   -> float: return self.cx - BRICK_W / 2
    @property
    def right(self)  -> float: return self.cx + BRICK_W / 2
    @property
    def top(self)    -> float: return self.cy + BRICK_H / 2
    @property
    def bottom(self) -> float: return self.cy - BRICK_H / 2

    def hit(self) -> int:
        self.hits -= 1
        self.flash_t = 0.15
        if self.hits <= 0:
            self.alive = False
            self.np.hide()
            if self.btype == 9:
                return PTS_HARD2
            if self.btype in POWER_BTYPES:
                return PTS_POWER
            return PTS_NORM
        # Hard brick survived first hit
        self.np.setColor(C_HARD2)
        return PTS_HARD1

    def tick(self, dt: float) -> None:
        """Animate the hit-flash (brief scale-up then back to 1)."""
        if self.flash_t <= 0:
            return
        self.flash_t -= dt
        t = self.flash_t / 0.15
        self.np.setScale(1.0 + 0.20 * t)
        if self.flash_t <= 0:
            self.np.setScale(1.0)


# ════════════════════════════════════════════════════════════════
#  SECTION 6 · UI HELPERS
# ════════════════════════════════════════════════════════════════

_BTN_FRAME  = (-0.22, 0.22, -0.046, 0.066)
_BTN_COLOR  = (0.13, 0.23, 0.46, 0.94)


def _btn(text: str, pos, cmd, parent=None) -> DirectButton:
    kw = dict(
        text=text, pos=pos, text_scale=0.062,
        frameSize=_BTN_FRAME, frameColor=_BTN_COLOR,
        text_fg=(1, 1, 1, 1),
        text_shadow=(0, 0, 0, 0.5),
        text_shadowOffset=(0.05, 0.05),
        rolloverSound=None, clickSound=None,
        command=cmd,
    )
    if parent is not None:
        kw["parent"] = parent
    return DirectButton(**kw)


def _txt(text: str, pos, scale: float = 0.07,
         fg=(1, 1, 1, 1), **kw) -> OnscreenText:
    return OnscreenText(
        text=text, pos=pos, scale=scale, fg=fg,
        align=TextNode.ACenter, mayChange=False, **kw
    )


# ════════════════════════════════════════════════════════════════
#  SECTION 7 · GAME
# ════════════════════════════════════════════════════════════════

class BreakoutGame(ShowBase):
    """
    Main application class.

    State machine:
      MENU → PLAYING ⟷ PAUSED
                ↓
           GAME_OVER / VICTORY → MENU

    Multi-ball is supported via self.balls (List[Ball]).
    Power events are queued in self._power_events and resolved
    once per visual frame after all sub-step physics complete.
    """

    def __init__(self) -> None:
        super().__init__()

        wp = WindowProperties()
        wp.setSize(WIN_W, WIN_H)
        wp.setTitle("BREAKOUT — Power Edition")
        wp.setFixedSize(True)
        self.win.requestProperties(wp)

        self.disableMouse()
        self.setBackgroundColor(*C_BG)

        self.high_score: int = load_hs()

        self.state: str = "MENU"
        self.score: int = 0
        self.lives: int = LIVES0
        self.lvl:   int = 0
        self._dbg:  bool = False

        # ── Power state ─────────────────────────────────────────
        self.power_type:         str   = ""
        self.power_timer:        float = 0.0
        self.power_applied_mult: float = 1.0
        self._power_events: List[Tuple[str, Ball]] = []

        # ── Sound Manager ───────────────────────────────────────
        self.sound_mgr = SimpleSoundManager(self)

        # ── Scene root ───────────────────────────────────────────
        self.gr: NodePath = self.aspect2d.attachNewNode("game_root")

        wall_h = abs(F_TOP - F_BOTTOM) + 0.2
        wall_w = abs(F_RIGHT - F_LEFT) + 0.2
        wl = make_card(self.gr, "wl", WALL_T * 2, wall_h, C_WALL)
        wr = make_card(self.gr, "wr", WALL_T * 2, wall_h, C_WALL)
        wt = make_card(self.gr, "wt", wall_w, WALL_T * 2, C_WALL)
        wl.setPos(F_LEFT  + WALL_T, 0, (F_TOP + F_BOTTOM) / 2)
        wr.setPos(F_RIGHT - WALL_T, 0, (F_TOP + F_BOTTOM) / 2)
        wt.setPos(0, 0, F_TOP - WALL_T)
        self.gr.hide()

        # ── Entity handles ───────────────────────────────────────
        self.paddle: Optional[Paddle] = None
        self.balls:  List[Ball]       = []
        self.bricks: List[Brick]      = []

        # ── UI widget lists ──────────────────────────────────────
        self._ui:  List = []
        self._hud: dict = {}

        # ── Input bindings ───────────────────────────────────────
        for key, direction in (("a", "l"), ("arrow_left", "l"),
                               ("d", "r"), ("arrow_right", "r")):
            self.accept(key,          self._key, [direction, True])
            self.accept(key + "-up",  self._key, [direction, False])
        self.accept("space",  self._space)
        self.accept("escape", self._esc)
        self.accept("r",      self._restart_key)
        self.accept("q",      sys.exit)
        self.accept("m",      self._toggle_mute)
        self.accept("M",      self._toggle_mute)
        self.accept("f1",     self._toggle_dbg)

        self._show_menu()
        self.taskMgr.add(self._update, "main_update")

    # ── Input callbacks ─────────────────────────────────────────

    def _key(self, direction: str, pressed: bool) -> None:
        if self.paddle and self.state == "PLAYING":
            if direction == "l":
                self.paddle.ml = pressed
            else:
                self.paddle.mr = pressed

    def _space(self) -> None:
        """Launch every ball currently resting on the paddle."""
        if self.state == "PLAYING":
            for b in self.balls:
                if b.on_paddle:
                    b.launch()

    def _esc(self) -> None:
        if   self.state == "PLAYING": self._show_pause()
        elif self.state == "PAUSED":  self._resume()

    def _restart_key(self) -> None:
        if self.state in ("PLAYING", "PAUSED"):
            self._load_level()

    def _toggle_mute(self) -> None:
        muted = self.sound_mgr.toggle_mute()
        print(f"[AUDIO] {'Mute activado' if muted else 'Mute desactivado'}")

    def _toggle_dbg(self) -> None:
        self._dbg = not self._dbg
        print(f"[DEBUG] hitbox logging {'ON' if self._dbg else 'OFF'}")

    # ── UI helpers ───────────────────────────────────────────────

    def _clear_ui(self) -> None:
        for w in self._ui:
            try: w.destroy()
            except Exception: pass
        self._ui.clear()

    def _clear_hud(self) -> None:
        for w in self._hud.values():
            try: w.destroy()
            except Exception: pass
        self._hud.clear()

    def _add(self, widget) -> None:
        self._ui.append(widget)

    # ── Screens ──────────────────────────────────────────────────

    def _show_menu(self) -> None:
        self.state = "MENU"
        self.gr.hide()
        self._clear_ui()
        self._clear_hud()
        self.sound_mgr.play_music()

        self._add(_txt("BREAKOUT", (0, 0.52), scale=0.19,
                       fg=(1.0, 0.88, 0.16, 1),
                       shadow=(0.40, 0.22, 0.0, 0.8)))
        self._add(_txt(f"HIGH SCORE: {self.high_score}",
                       (0, 0.31), scale=0.062, fg=(0.55, 0.88, 1.0, 1)))
        self._add(_btn("START GAME",  (0, 0,  0.12), self._start_game))
        self._add(_btn("HOW TO PLAY", (0, 0, -0.05), self._show_howto))
        self._add(_btn("QUIT",        (0, 0, -0.22), sys.exit))

    def _show_howto(self) -> None:
        self.state = "HOW_TO_PLAY"
        self._clear_ui()
        instructions = (
            "HOW TO PLAY\n\n"
            "A / Arrow-Left    Move paddle left\n"
            "D / Arrow-Right   Move paddle right\n"
            "SPACE             Launch ball\n"
            "ESC               Pause / Resume\n"
            "R                 Restart current level\n"
            "M                 Mute / Unmute music\n"
            "Q                 Quit\n\n"
            "Clear every brick to advance!\n"
            "Grey bricks require 2 hits.\n\n"
            "POWER BRICKS:\n"
            "  CYAN   = Multi-Ball  (+2 extra balls!)\n"
            "  PURPLE = Slow Ball   (slows for 8 s)\n"
            "  ORANGE = Fast Ball   (speeds up for 8 s)\n"
        )
        self._add(_txt(instructions, (0, 0.28), scale=0.048))
        self._add(_btn("BACK", (0, 0, -0.72), self._show_menu))

    def _show_pause(self) -> None:
        self.state = "PAUSED"
        if self.paddle:
            self.paddle.ml = self.paddle.mr = False
        self.sound_mgr.pause_music()
        self._clear_ui()
        self._add(_txt("PAUSED", (0, 0.30), scale=0.14, fg=(1, 1, 0.3, 1)))
        self._add(_btn("RESUME",        (0, 0,  0.06), self._resume))
        self._add(_btn("RESTART LEVEL", (0, 0, -0.11), self._load_level))
        self._add(_btn("MAIN MENU",     (0, 0, -0.28), self._show_menu))

    def _show_gameover(self) -> None:
        self.state = "GAME_OVER"
        self.gr.hide()
        self._clear_hud()

        is_new_hs = self.score > self.high_score
        if is_new_hs:
            self.high_score = self.score
            save_hs(self.high_score)

        self._clear_ui()
        self._add(_txt("GAME  OVER", (0, 0.40), scale=0.14, fg=(1, 0.2, 0.2, 1)))
        hs_line = "-- NEW HIGH SCORE! --" if is_new_hs else f"HIGH SCORE: {self.high_score}"
        self._add(_txt(f"SCORE: {self.score}\n{hs_line}",
                       (0, 0.14), scale=0.068, fg=(1, 0.90, 0.44, 1)))
        self._add(_btn("RETRY",      (0, 0, -0.10), self._start_game))
        self._add(_btn("MAIN MENU",  (0, 0, -0.27), self._show_menu))

    def _show_victory(self) -> None:
        self.state = "VICTORY"
        self.gr.hide()
        self._clear_hud()

        is_new_hs = self.score > self.high_score
        if is_new_hs:
            self.high_score = self.score
            save_hs(self.high_score)

        self._clear_ui()
        self._add(_txt("YOU  WIN!", (0, 0.42), scale=0.15, fg=(0.3, 1, 0.3, 1)))
        hs_line = "-- NEW HIGH SCORE! --" if is_new_hs else f"HIGH SCORE: {self.high_score}"
        self._add(_txt(f"FINAL SCORE: {self.score}\n{hs_line}",
                       (0, 0.16), scale=0.068, fg=(1, 0.94, 0.44, 1)))
        self._add(_btn("MAIN MENU", (0, 0, -0.08), self._show_menu))

    # ── HUD ──────────────────────────────────────────────────────

    def _build_hud(self) -> None:
        self._clear_hud()
        ar  = self.getAspectRatio()
        s   = 0.055
        lft = -ar + 0.08
        rgt =  ar - 0.08

        self._hud["sc"] = OnscreenText(
            text=f"SCORE: {self.score}", pos=(lft, -0.94),
            scale=s, fg=(1, 1, 1, 1),
            align=TextNode.ALeft, mayChange=True)
        self._hud["hs"] = OnscreenText(
            text=f"HI: {self.high_score}", pos=(0, -0.94),
            scale=s, fg=(1, 0.88, 0.18, 1),
            align=TextNode.ACenter, mayChange=True)
        self._hud["lv"] = OnscreenText(
            text=f"LVL {self.lvl + 1}", pos=(rgt - 0.18, -0.94),
            scale=s, fg=(0.68, 0.88, 1, 1),
            align=TextNode.ALeft, mayChange=True)
        self._hud["li"] = OnscreenText(
            text=f"LIVES: {self.lives}", pos=(rgt, -0.94),
            scale=s, fg=(1, 0.34, 0.34, 1),
            align=TextNode.ARight, mayChange=True)
        self._hud["pw"] = OnscreenText(
            text="", pos=(0, -0.87),
            scale=0.062, fg=(1, 1, 1, 1),
            align=TextNode.ACenter, mayChange=True)
        self._hud["mute"] = OnscreenText(
            text="", pos=(rgt - 0.05, 0.92),
            scale=0.05, fg=(0.8, 0.8, 0.8, 0.7),
            align=TextNode.ARight, mayChange=True)

    def _tick_hud(self) -> None:
        if not self._hud:
            return
        self._hud["sc"].setText(f"SCORE: {self.score}")
        self._hud["hs"].setText(f"HI: {self.high_score}")
        self._hud["lv"].setText(f"LVL {self.lvl + 1}")

        ball_ct = len(self.balls)
        suffix  = f"  x{ball_ct}" if ball_ct > 1 else ""
        self._hud["li"].setText(f"LIVES: {self.lives}{suffix}")

        if self.power_type == "slow":
            self._hud["pw"]["fg"] = (0.78, 0.35, 1.0, 1.0)
            self._hud["pw"].setText(f"SLOW  {self.power_timer:.1f}s")
        elif self.power_type == "fast":
            self._hud["pw"]["fg"] = (1.0, 0.55, 0.10, 1.0)
            self._hud["pw"].setText(f"FAST  {self.power_timer:.1f}s")
        else:
            self._hud["pw"].setText("")
        
        if self.sound_mgr.muted:
            self._hud["mute"].setText("🔇 MUTE")
        else:
            self._hud["mute"].setText("")

    # ── Game-flow methods ────────────────────────────────────────

    def _start_game(self) -> None:
        self.score = 0
        self.lives = LIVES0
        self.lvl   = 0
        self._load_level()

    def _resume(self) -> None:
        self._clear_ui()
        self.state = "PLAYING"
        self.sound_mgr.resume_music()

    def _load_level(self) -> None:
        """(Re)build the current level."""
        self._clear_ui()
        self.gr.show()

        # Destroy previous bricks
        for b in self.bricks:
            b.np.removeNode()
        self.bricks.clear()

        # Destroy previous entities
        if self.paddle:
            self.paddle.np.removeNode()
        for b in self.balls:
            b.np.removeNode()
        self.balls.clear()

        # Reset power state
        self.power_type         = ""
        self.power_timer        = 0.0
        self.power_applied_mult = 1.0
        self._power_events.clear()

        self.paddle = Paddle(self.gr)
        first_ball  = Ball(self.gr, extra=False)
        first_ball.attach_to(0.0)
        self.balls.append(first_ball)

        layout = LEVELS[self.lvl % len(LEVELS)]
        for ri, row in enumerate(layout):
            for ci, cell in enumerate(row):
                if cell:
                    self.bricks.append(Brick(self.gr, ci, ri, cell))

        self._build_hud()
        self.state = "PLAYING"

    def _advance_level(self) -> None:
        self.lvl += 1
        if self.lvl >= len(LEVELS):
            self.sound_mgr.stop_music()
            self._show_victory()
        else:
            self._load_level()

    # ── Main update task ─────────────────────────────────────────

    def _update(self, task) -> int:
        if self.state != "PLAYING":
            return Task.cont

        dt = min(globalClock.getDt(), DT_CAP)

        self.paddle.update(dt)

        # ── Tick power timer ─────────────────────────────────────
        if self.power_timer > 0:
            self.power_timer -= dt
            if self.power_timer <= 0:
                self._expire_power()

        # ── Attach on-paddle balls to moving paddle ───────────────
        for b in self.balls:
            if b.on_paddle:
                b.attach_to(self.paddle.x)

        # Nothing to simulate if all balls are waiting on paddle
        if all(b.on_paddle for b in self.balls):
            self._tick_hud()
            return Task.cont

        # ── Sub-stepped physics ──────────────────────────────────
        sub = dt / SUBSTEPS
        lost_balls: List[Ball] = []
        self._power_events.clear()

        for b in self.balls:
            if b.on_paddle:
                continue
            for _ in range(SUBSTEPS):
                if not self._physics_step(b, sub):
                    lost_balls.append(b)
                    break

        # ── Resolve power events ─────────────────────────────────
        for ptype, src in self._power_events:
            self._handle_power(ptype, src)

        # ── Remove balls that fell below the field ───────────────
        for b in lost_balls:
            self._handle_ball_lost(b)

        if self.state != "PLAYING":
            return Task.cont

        # ── Level clear ──────────────────────────────────────────
        if self.bricks and all(not b.alive for b in self.bricks):
            self._advance_level()
            return Task.cont

        # Tick brick hit-flash animations
        for b in self.bricks:
            if b.alive:
                b.tick(dt)

        self._tick_hud()
        return Task.cont

    # ── Physics ──────────────────────────────────────────────────

    def _physics_step(self, ball: Ball, dt: float) -> bool:
        """
        Advance `ball` by dt seconds; resolve walls / paddle / bricks.
        Returns True if ball is still in play, False if it fell below the field.
        """
        bl = ball
        pd = self.paddle

        bl.x += bl.vx * dt
        bl.y += bl.vy * dt

        # Left / right walls
        if bl.x - BALL_R < B_LEFT:
            bl.x  = B_LEFT + BALL_R;  bl.vx = abs(bl.vx)
        elif bl.x + BALL_R > B_RIGHT:
            bl.x  = B_RIGHT - BALL_R; bl.vx = -abs(bl.vx)

        # Top wall
        if bl.y + BALL_R > B_TOP:
            bl.y  = B_TOP - BALL_R;   bl.vy = -abs(bl.vy)

        # Ball lost
        if bl.y < F_BOTTOM:
            return False

        # Paddle collision
        if (bl.vy < 0
                and bl.y - BALL_R <= pd.top
                and bl.y + BALL_R >= pd.bottom
                and bl.x + BALL_R >= pd.left - BALL_R
                and bl.x - BALL_R <= pd.right + BALL_R):

            rel   = clamp((bl.x - pd.x) / (PAD_W / 2), -1.0, 1.0)
            angle = math.radians(rel * 60)
            spd   = bl.spd
            bl.vx = spd * math.sin(angle)
            bl.vy = spd * math.cos(angle)
            bl.vx, bl.vy = fix_vy(bl.vx, bl.vy, spd)
            bl.y = pd.top + BALL_R + 0.001

            if self._dbg:
                print(f"[DEBUG] paddle hit rel={rel:.2f}  "
                      f"vx={bl.vx:.3f} vy={bl.vy:.3f}")

        self._collide_bricks(bl)
        bl.np.setPos(bl.x, 0, bl.y)
        return True

    def _collide_bricks(self, ball: Ball) -> None:
        """
        AABB collision between ball and all alive bricks.
        Resolves the first overlap found (one brick per sub-step).
        """
        bl = ball
        for brick in self.bricks:
            if not brick.alive:
                continue

            hx = BRICK_W / 2 + BALL_R
            hy = BRICK_H / 2 + BALL_R
            ox = hx - abs(bl.x - brick.cx)
            oy = hy - abs(bl.y - brick.cy)

            if ox <= 0 or oy <= 0:
                continue

            # Axis selection: smaller penetration depth = collision axis
            if ox < oy:
                direction = math.copysign(1.0, bl.x - brick.cx)
                bl.vx = direction * abs(bl.vx)
                bl.x += direction * ox
            else:
                direction = math.copysign(1.0, bl.y - brick.cy)
                bl.vy = direction * abs(bl.vy)
                bl.y += direction * oy

            pts = brick.hit()
            self.score += pts
            if self.score > self.high_score:
                self.high_score = self.score

            if not brick.alive:
                # Normal acceleration only for non-power bricks
                if brick.btype not in POWER_BTYPES:
                    bl.spd = min(bl.spd + BALL_ACCEL, BALL_SPD_MAX)
                    nx, ny = norm2(bl.vx, bl.vy)
                    bl.vx  = nx * bl.spd
                    bl.vy  = ny * bl.spd
                    bl.vx, bl.vy = fix_vy(bl.vx, bl.vy, bl.spd)

                # Queue power event
                if brick.btype == BTYPE_MULTI:
                    self._power_events.append(("multi", bl))
                elif brick.btype == BTYPE_SLOW:
                    self._power_events.append(("slow", bl))
                elif brick.btype == BTYPE_FAST:
                    self._power_events.append(("fast", bl))

            if self._dbg:
                print(f"[DEBUG] brick({brick.row},{brick.col}) hit  "
                      f"ox={ox:.4f} oy={oy:.4f}  "
                      f"vx={bl.vx:.3f} vy={bl.vy:.3f}  pts={pts}")
            break  # one brick per sub-step

    # ── Power system ─────────────────────────────────────────────

    def _handle_power(self, ptype: str, source: Ball) -> None:
        """Dispatch a power event to the right handler."""
        if ptype == "multi":
            self._spawn_multi_balls(source)
        elif ptype in ("slow", "fast"):
            self._apply_power_effect(ptype)

    def _spawn_multi_balls(self, source: Ball) -> None:
        """
        Spawn 2 extra balls diverging ±30° from the source ball's
        current direction.  Capped at MULTI_CAP total balls.
        """
        if len(self.balls) >= MULTI_CAP:
            return
        cur_angle = math.atan2(source.vx, source.vy)
        for offset_deg in (-30, 30):
            if len(self.balls) >= MULTI_CAP:
                break
            new_angle = cur_angle + math.radians(offset_deg)
            b = Ball(self.gr, extra=True)
            b.x  = source.x
            b.y  = source.y
            b.on_paddle = False
            b.spd = source.spd
            b.vx  = source.spd * math.sin(new_angle)
            b.vy  = source.spd * math.cos(new_angle)
            b.vx, b.vy = fix_vy(b.vx, b.vy, b.spd)
            b.np.setPos(b.x, 0, b.y)
            self.balls.append(b)

        if self._dbg:
            print(f"[DEBUG] multi-ball!  total balls = {len(self.balls)}")

    def _apply_power_effect(self, ptype: str) -> None:
        """
        Apply slow or fast to all active (non-paddle) balls.
        """
        self._expire_power(quiet=True)

        mult = SLOW_FACTOR if ptype == "slow" else FAST_FACTOR
        self.power_type         = ptype
        self.power_timer        = POWER_DUR
        self.power_applied_mult = mult

        for b in self.balls:
            if not b.on_paddle:
                b.spd = clamp(b.spd * mult,
                              BALL_SPD0 * 0.30,
                              BALL_SPD_MAX * 1.50)
                nx, ny = norm2(b.vx, b.vy)
                b.vx, b.vy = nx * b.spd, ny * b.spd
                b.vx, b.vy = fix_vy(b.vx, b.vy, b.spd)

        if self._dbg:
            print(f"[DEBUG] power '{ptype}'  mult={mult:.2f}  "
                  f"duration={POWER_DUR}s")

    def _expire_power(self, quiet: bool = False) -> None:
        """
        Undo the current speed multiplier and reset power state.
        """
        if self.power_type in ("slow", "fast") and self.power_applied_mult != 1.0:
            inv = 1.0 / self.power_applied_mult
            for b in self.balls:
                b.spd = clamp(b.spd * inv, BALL_SPD0 * 0.5, BALL_SPD_MAX)
                if not b.on_paddle:
                    nx, ny = norm2(b.vx, b.vy)
                    b.vx, b.vy = nx * b.spd, ny * b.spd
                    b.vx, b.vy = fix_vy(b.vx, b.vy, b.spd)

        self.power_type         = ""
        self.power_timer        = 0.0
        self.power_applied_mult = 1.0
        if not quiet and self._dbg:
            print("[DEBUG] power effect expired")

    def _handle_ball_lost(self, ball: Ball) -> None:
        """
        Remove a single lost ball.  A life is only deducted when the
        LAST active ball falls below the field.
        """
        if ball not in self.balls:
            return

        ball.np.removeNode()
        self.balls.remove(ball)

        if self.balls:
            # Other balls still active — no life lost, keep playing
            return

        # ── All balls gone ────────────────────────────────────────
        self._expire_power()
        self.lives -= 1
        
        # Sonido al perder vida (excepto si ya no quedan vidas)
        if self.lives > 0:
            self.sound_mgr.play("life_lost")
        
        self._tick_hud()

        if self.lives <= 0:
            self.sound_mgr.play("game_over")
            self.sound_mgr.stop_music()
            self._show_gameover()
            return

        # Respawn a fresh ball on the paddle
        new_ball = Ball(self.gr, extra=False)
        new_ball.spd = BALL_SPD0
        new_ball.attach_to(self.paddle.x)
        self.balls.append(new_ball)


# ════════════════════════════════════════════════════════════════
#  SECTION 8 · ENTRY POINT
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    game = BreakoutGame()
    game.run()