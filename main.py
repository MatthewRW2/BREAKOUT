#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║              BREAKOUT — Panda3D Single-File Clone            ║
║   Controls: A/D or Arrows · SPACE launch · ESC pause · Q quit║
╚══════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations
import json
import math
import os
import sys
from typing import List, Optional

# ── Panda3D bootstrap (before ShowBase import) ─────────────────
from panda3d.core import loadPrcFileData  # noqa: E402

loadPrcFileData("", "window-title BREAKOUT")
loadPrcFileData("", "win-size 800 600")
loadPrcFileData("", "sync-video 0")
loadPrcFileData("", "audio-library-name null")   # skip audio init warnings

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
)

# ════════════════════════════════════════════════════════════════
#  SECTION 1 · CONFIG
#  All tunable constants live here.
# ════════════════════════════════════════════════════════════════
WIN_W: int = 800
WIN_H: int = 600

# Field boundaries in Panda3D aspect2d world-units.
# aspect2d: x ∈ [-4/3, 4/3], y ∈ [-1, 1] for an 800×600 window.
F_LEFT:   float = -0.90    # left wall inner edge (game units)
F_RIGHT:  float =  0.90    # right wall inner edge
F_TOP:    float =  0.93    # top wall inner edge
F_BOTTOM: float = -0.98    # y below this → ball lost
WALL_T:   float =  0.025   # wall half-thickness (visual only)

# Effective bounce boundaries for the ball centre
B_LEFT:  float = F_LEFT  + WALL_T * 2
B_RIGHT: float = F_RIGHT - WALL_T * 2
B_TOP:   float = F_TOP   - WALL_T * 2

# ── Paddle ──────────────────────────────────────────────────────
PAD_W:     float = 0.28     # paddle full width
PAD_H:     float = 0.046    # paddle full height
PAD_Y:     float = -0.83    # paddle vertical centre (fixed)
PAD_SPEED: float = 1.90     # horizontal speed (units/s)
PAD_MIN_X: float = B_LEFT  + PAD_W / 2
PAD_MAX_X: float = B_RIGHT - PAD_W / 2

# ── Ball ────────────────────────────────────────────────────────
BALL_R:       float = 0.028  # ball "radius" (half-side of square visual)
BALL_SPD0:    float = 0.90   # initial speed (units/s)
BALL_SPD_MAX: float = 2.20   # maximum speed
BALL_ACCEL:   float = 0.022  # speed gain per brick destroyed
MIN_VY:       float = 0.28   # minimum |vy| to avoid near-horizontal flight
DT_CAP:       float = 0.05   # dt cap (30 fps minimum) — prevents tunnelling
SUBSTEPS:     int   = 4      # physics sub-steps per visual frame

# ── Bricks ──────────────────────────────────────────────────────
BRICK_W:    float = 0.162   # brick full width
BRICK_H:    float = 0.062   # brick full height
BRICK_PX:   float = 0.010   # horizontal gap between bricks
BRICK_PY:   float = 0.009   # vertical gap between rows
BRICK_COLS: int   = 10      # columns per row
BRICK_Y0:   float = 0.73    # y centre of the topmost brick row

# ── Game ────────────────────────────────────────────────────────
LIVES0:    int = 3
PTS_NORM:  int = 10    # points for a normal brick
PTS_HARD1: int = 5     # points for first hit on a hard brick (not destroyed)
PTS_HARD2: int = 25    # points for second hit on a hard brick (destroyed)
SAVE_FILE: str = "save.json"

# ── Colours ─────────────────────────────────────────────────────
C_BG     = LColor(0.04, 0.04, 0.12, 1)
C_WALL   = LColor(0.26, 0.29, 0.44, 1)
C_PADDLE = LColor(0.93, 0.93, 0.93, 1)
C_BALL   = LColor(1.00, 0.97, 0.58, 1)
C_HARD   = LColor(0.66, 0.68, 0.75, 1)     # hard brick (full)
C_HARD2  = LColor(0.93, 0.56, 0.18, 1)     # hard brick (damaged)

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
#  0 = empty   1-6 = normal brick (row colour index)   9 = hard (2 hits)
# ════════════════════════════════════════════════════════════════
LEVELS: List[List[List[int]]] = [
    # ── Level 1 · Classic rainbow ──────────────────────────────
    [
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
        [3, 3, 3, 3, 3, 3, 3, 3, 3, 3],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [6, 6, 6, 6, 6, 6, 6, 6, 6, 6],
    ],
    # ── Level 2 · Diamond + gaps ───────────────────────────────
    [
        [0, 0, 0, 1, 1, 1, 1, 0, 0, 0],
        [0, 0, 2, 2, 2, 2, 2, 2, 0, 0],
        [0, 3, 3, 3, 3, 3, 3, 3, 3, 0],
        [4, 4, 4, 0, 0, 0, 0, 4, 4, 4],
        [5, 5, 5, 5, 0, 0, 5, 5, 5, 5],
        [6, 0, 6, 0, 6, 6, 0, 6, 0, 6],
    ],
    # ── Level 3 · Hard bricks + alternating gaps ───────────────
    [
        [9, 0, 9, 0, 9, 9, 0, 9, 0, 9],
        [0, 1, 0, 1, 0, 0, 1, 0, 1, 0],
        [2, 9, 2, 9, 2, 2, 9, 2, 9, 2],
        [0, 3, 0, 3, 0, 0, 3, 0, 3, 0],
        [4, 9, 4, 9, 4, 4, 9, 4, 9, 4],
        [5, 0, 5, 0, 5, 5, 0, 5, 0, 5],
    ],
]

# ════════════════════════════════════════════════════════════════
#  SECTION 3 · UTILITIES
# ════════════════════════════════════════════════════════════════

def clamp(v: float, lo: float, hi: float) -> float:
    """Clamp v to [lo, hi]."""
    return max(lo, min(hi, v))


def norm2(x: float, y: float):
    """Return normalised (x, y); returns (0, 1) for a zero vector."""
    m = math.hypot(x, y)
    return (x / m, y / m) if m > 1e-9 else (0.0, 1.0)


def fix_vy(vx: float, vy: float, spd: Optional[float] = None):
    """
    Ensure |vy| >= MIN_VY while preserving `spd` (current speed if None).
    Prevents near-horizontal loops that last forever.
    """
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
    """Create a solid-colour rectangle centred at the parent origin."""
    cm = CardMaker(name)
    cm.setFrame(-w / 2, w / 2, -h / 2, h / 2)
    np = parent.attachNewNode(cm.generate())
    np.setColor(color)
    np.setDepthTest(False)
    np.setDepthWrite(False)
    np.setBin("fixed", 10)
    return np


def load_hs() -> int:
    """Load high score from SAVE_FILE; return 0 if missing/corrupt."""
    try:
        with open(SAVE_FILE) as f:
            return int(json.load(f).get("high_score", 0))
    except Exception:
        return 0


def save_hs(score: int) -> None:
    """Persist high score to SAVE_FILE."""
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump({"high_score": score}, f)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
#  SECTION 4 · ENTITIES
# ════════════════════════════════════════════════════════════════

class Paddle:
    """Player-controlled paddle."""

    def __init__(self, root: NodePath) -> None:
        self.np: NodePath = make_card(root, "paddle", PAD_W, PAD_H, C_PADDLE)
        self.x: float     = 0.0
        self.ml: bool     = False   # move-left key held?
        self.mr: bool     = False   # move-right key held?
        self.np.setPos(0, 0, PAD_Y)

    # ── AABB edges ──────────────────────────────────────────────
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
    """The game ball."""

    def __init__(self, root: NodePath) -> None:
        side = BALL_R * 2
        self.np:        NodePath = make_card(root, "ball", side, side, C_BALL)
        self.x:         float    = 0.0
        self.y:         float    = PAD_Y + PAD_H / 2 + BALL_R + 0.004
        self.vx:        float    = 0.0
        self.vy:        float    = 0.0
        self.spd:       float    = BALL_SPD0
        self.on_paddle: bool     = True
        self.np.setPos(self.x, 0, self.y)

    def attach_to(self, px: float) -> None:
        """Stick ball on top of paddle at horizontal position px."""
        self.x = px
        self.y = PAD_Y + PAD_H / 2 + BALL_R + 0.004
        self.on_paddle = True
        self.np.setPos(self.x, 0, self.y)

    def launch(self) -> None:
        """Detach ball and fire upward at a slight angle."""
        if not self.on_paddle:
            return
        self.on_paddle = False
        # Small rightward bias; angle from vertical = 18°
        angle_from_vert = math.radians(18)
        self.vx = self.spd * math.sin(angle_from_vert)
        self.vy = self.spd * math.cos(angle_from_vert)
        self.vx, self.vy = fix_vy(self.vx, self.vy, self.spd)


class Brick:
    """A single brick in the grid."""

    def __init__(self, root: NodePath, col: int, row: int, btype: int) -> None:
        self.col:    int   = col
        self.row:    int   = row
        self.btype:  int   = btype
        self.hits:   int   = 2 if btype == 9 else 1
        self.alive:  bool  = True
        self.flash_t: float = 0.0

        init_color: LColor = (
            C_HARD if btype == 9
            else ROW_COLORS[(btype - 1) % len(ROW_COLORS)]
        )
        self.np = make_card(root, f"b{row}_{col}", BRICK_W, BRICK_H, init_color)

        # Compute grid position (centred around x=0)
        total_w = BRICK_COLS * BRICK_W + (BRICK_COLS - 1) * BRICK_PX
        x0 = -total_w / 2 + BRICK_W / 2
        self.cx: float = x0 + col * (BRICK_W + BRICK_PX)
        self.cy: float = BRICK_Y0 - row * (BRICK_H + BRICK_PY)
        self.np.setPos(self.cx, 0, self.cy)

    # ── AABB edges ──────────────────────────────────────────────
    @property
    def left(self)   -> float: return self.cx - BRICK_W / 2
    @property
    def right(self)  -> float: return self.cx + BRICK_W / 2
    @property
    def top(self)    -> float: return self.cy + BRICK_H / 2
    @property
    def bottom(self) -> float: return self.cy - BRICK_H / 2

    def hit(self) -> int:
        """
        Register a hit.  Returns points earned:
          - Normal brick destroyed → PTS_NORM
          - Hard brick first hit   → PTS_HARD1 (not destroyed)
          - Hard brick second hit  → PTS_HARD2 (destroyed)
        """
        self.hits -= 1
        self.flash_t = 0.15
        if self.hits <= 0:
            self.alive = False
            self.np.hide()
            return PTS_HARD2 if self.btype == 9 else PTS_NORM
        # Hard brick survived; change colour to show damage
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
#  SECTION 5 · UI HELPERS
# ════════════════════════════════════════════════════════════════

_BTN_FRAME  = (-0.22, 0.22, -0.046, 0.066)
_BTN_COLOR  = (0.13, 0.23, 0.46, 0.94)
_BTN_HOVER  = (0.25, 0.42, 0.72, 0.94)
_BTN_CLICK  = (0.08, 0.14, 0.32, 0.94)


def _btn(text: str, pos, cmd, parent=None) -> DirectButton:
    """Create a styled DirectButton."""
    kw = dict(
        text=text,
        pos=pos,
        text_scale=0.062,
        frameSize=_BTN_FRAME,
        frameColor=_BTN_COLOR,
        text_fg=(1, 1, 1, 1),
        text_shadow=(0, 0, 0, 0.5),
        text_shadowOffset=(0.05, 0.05),
        rolloverSound=None,
        clickSound=None,
        command=cmd,
    )
    if parent is not None:
        kw["parent"] = parent
    return DirectButton(**kw)


def _txt(text: str, pos, scale: float = 0.07,
         fg=(1, 1, 1, 1), **kw) -> OnscreenText:
    """Create centred OnscreenText."""
    return OnscreenText(
        text=text, pos=pos, scale=scale, fg=fg,
        align=TextNode.ACenter, mayChange=False, **kw
    )


# ════════════════════════════════════════════════════════════════
#  SECTION 6 · GAME
# ════════════════════════════════════════════════════════════════

class BreakoutGame(ShowBase):
    """
    Main application class.

    State machine:
      MENU → PLAYING ⟷ PAUSED
                ↓
           GAME_OVER / VICTORY → MENU
    """

    def __init__(self) -> None:
        super().__init__()

        # ── window ──────────────────────────────────────────────
        wp = WindowProperties()
        wp.setSize(WIN_W, WIN_H)
        wp.setTitle("BREAKOUT")
        wp.setFixedSize(True)
        self.win.requestProperties(wp)

        self.disableMouse()
        self.setBackgroundColor(*C_BG)

        # ── persistent data ─────────────────────────────────────
        self.high_score: int = load_hs()

        # ── state ───────────────────────────────────────────────
        self.state: str = "MENU"
        self.score: int = 0
        self.lives: int = LIVES0
        self.lvl:   int = 0
        self._dbg:  bool = False

        # ── scene root (all game objects attach here) ────────────
        self.gr: NodePath = self.aspect2d.attachNewNode("game_root")

        # Static walls (visual only; bounce logic uses B_* constants)
        wall_h = abs(F_TOP - F_BOTTOM) + 0.2
        wall_w = abs(F_RIGHT - F_LEFT) + 0.2
        wl = make_card(self.gr, "wl", WALL_T * 2, wall_h, C_WALL)
        wr = make_card(self.gr, "wr", WALL_T * 2, wall_h, C_WALL)
        wt = make_card(self.gr, "wt", wall_w, WALL_T * 2, C_WALL)
        wl.setPos(F_LEFT  + WALL_T, 0, (F_TOP + F_BOTTOM) / 2)
        wr.setPos(F_RIGHT - WALL_T, 0, (F_TOP + F_BOTTOM) / 2)
        wt.setPos(0, 0, F_TOP - WALL_T)
        self.gr.hide()

        # ── entity handles ───────────────────────────────────────
        self.paddle: Optional[Paddle] = None
        self.ball:   Optional[Ball]   = None
        self.bricks: List[Brick]      = []

        # ── UI widget lists ──────────────────────────────────────
        self._ui:  List = []     # overlay screens
        self._hud: dict = {}     # in-game HUD texts

        # ── input bindings ───────────────────────────────────────
        for key, direction in (("a", "l"), ("arrow_left", "l"),
                               ("d", "r"), ("arrow_right", "r")):
            self.accept(key,          self._key, [direction, True])
            self.accept(key + "-up",  self._key, [direction, False])
        self.accept("space",  self._space)
        self.accept("escape", self._esc)
        self.accept("r",      self._restart_key)
        self.accept("q",      sys.exit)
        self.accept("f1",     self._toggle_dbg)

        # ── start ────────────────────────────────────────────────
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
        if self.state == "PLAYING" and self.ball and self.ball.on_paddle:
            self.ball.launch()

    def _esc(self) -> None:
        if   self.state == "PLAYING": self._show_pause()
        elif self.state == "PAUSED":  self._resume()

    def _restart_key(self) -> None:
        if self.state in ("PLAYING", "PAUSED"):
            self._load_level()

    def _toggle_dbg(self) -> None:
        self._dbg = not self._dbg
        state_str = "ON" if self._dbg else "OFF"
        print(f"[DEBUG] hitbox logging {state_str}")

    # ── UI helpers ───────────────────────────────────────────────

    def _clear_ui(self) -> None:
        for w in self._ui:
            try:
                w.destroy()
            except Exception:
                pass
        self._ui.clear()

    def _clear_hud(self) -> None:
        for w in self._hud.values():
            try:
                w.destroy()
            except Exception:
                pass
        self._hud.clear()

    def _add(self, widget) -> None:
        self._ui.append(widget)

    # ── Screens ──────────────────────────────────────────────────

    def _show_menu(self) -> None:
        self.state = "MENU"
        self.gr.hide()
        self._clear_ui()
        self._clear_hud()

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
            "A / Arrow-Left     Move paddle left\n"
            "D / Arrow-Right    Move paddle right\n"
            "SPACE              Launch ball\n"
            "ESC                Pause / Resume\n"
            "R                  Restart current level\n"
            "Q                  Quit game\n"
            "F1                 Toggle debug output\n\n"
            "Clear every brick to advance!\n"
            "Grey bricks take 2 hits.\n"
            "The ball speeds up as you score.\n\n"
            "Good luck!"
        )
        self._add(_txt(instructions, (0, 0.29), scale=0.052))
        self._add(_btn("BACK", (0, 0, -0.72), self._show_menu))

    def _show_pause(self) -> None:
        self.state = "PAUSED"
        if self.paddle:
            self.paddle.ml = self.paddle.mr = False
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

    def _tick_hud(self) -> None:
        if not self._hud:
            return
        self._hud["sc"].setText(f"SCORE: {self.score}")
        self._hud["hs"].setText(f"HI: {self.high_score}")
        self._hud["lv"].setText(f"LVL {self.lvl + 1}")
        self._hud["li"].setText(f"LIVES: {self.lives}")

    # ── Game-flow methods ────────────────────────────────────────

    def _start_game(self) -> None:
        self.score = 0
        self.lives = LIVES0
        self.lvl   = 0
        self._load_level()

    def _resume(self) -> None:
        self._clear_ui()
        self.state = "PLAYING"

    def _load_level(self) -> None:
        """(Re)build the current level: create paddle, ball, bricks."""
        self._clear_ui()
        self.gr.show()

        # destroy previous bricks
        for b in self.bricks:
            b.np.removeNode()
        self.bricks.clear()

        # destroy previous entities
        if self.paddle:
            self.paddle.np.removeNode()
        if self.ball:
            self.ball.np.removeNode()

        self.paddle = Paddle(self.gr)
        self.ball   = Ball(self.gr)
        self.ball.attach_to(0.0)

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
            self._show_victory()
        else:
            self._load_level()

    # ── Main update task ─────────────────────────────────────────

    def _update(self, task) -> int:
        if self.state != "PLAYING":
            return Task.cont

        dt = min(globalClock.getDt(), DT_CAP)

        # paddle moves every frame
        self.paddle.update(dt)

        if self.ball.on_paddle:
            self.ball.attach_to(self.paddle.x)
            return Task.cont

        # ── Sub-stepped physics ──────────────────────────────────
        # Dividing dt into SUBSTEPS guarantees the ball never moves
        # more than spd*DT_CAP/SUBSTEPS ≈ 0.028 units per step,
        # which is safely less than BRICK_H (0.062).  This prevents
        # tunnelling without requiring a full broad-phase sweep.
        sub = dt / SUBSTEPS
        ball_lost = False
        for _ in range(SUBSTEPS):
            if not self._physics_step(sub):
                ball_lost = True
                break

        if ball_lost:
            self._handle_ball_lost()
            return Task.cont

        # check level clear (all alive bricks gone)
        if self.bricks and all(not b.alive for b in self.bricks):
            self._advance_level()
            return Task.cont

        # flash-animation tick for bricks
        for b in self.bricks:
            if b.alive:
                b.tick(dt)

        self._tick_hud()
        return Task.cont

    # ── Physics ──────────────────────────────────────────────────

    def _physics_step(self, dt: float) -> bool:
        """
        Advance ball by dt seconds, resolve walls / paddle / bricks.
        Returns True if ball is still in play, False if it's lost.
        """
        bl = self.ball
        pd = self.paddle

        bl.x += bl.vx * dt
        bl.y += bl.vy * dt

        # ── left / right walls ──────────────────────────────────
        if bl.x - BALL_R < B_LEFT:
            bl.x  = B_LEFT + BALL_R
            bl.vx = abs(bl.vx)
        elif bl.x + BALL_R > B_RIGHT:
            bl.x  = B_RIGHT - BALL_R
            bl.vx = -abs(bl.vx)

        # ── top wall ────────────────────────────────────────────
        if bl.y + BALL_R > B_TOP:
            bl.y  = B_TOP - BALL_R
            bl.vy = -abs(bl.vy)

        # ── ball lost (fell below field) ─────────────────────────
        if bl.y < F_BOTTOM:
            return False

        # ── paddle collision ─────────────────────────────────────
        if (bl.vy < 0
                and bl.y - BALL_R <= pd.top
                and bl.y + BALL_R >= pd.bottom
                and bl.x + BALL_R >= pd.left - BALL_R
                and bl.x - BALL_R <= pd.right + BALL_R):

            # rel ∈ [-1, 1]: -1 = far left, 0 = centre, +1 = far right
            rel = clamp((bl.x - pd.x) / (PAD_W / 2), -1.0, 1.0)

            # Map to outgoing angle (measured from vertical):
            #   rel = 0   → straight up   (0°)
            #   rel = ±1  → ±60° from vertical
            angle = math.radians(rel * 60)
            spd = bl.spd
            bl.vx = spd * math.sin(angle)
            bl.vy = spd * math.cos(angle)   # always positive → upward
            bl.vx, bl.vy = fix_vy(bl.vx, bl.vy, spd)
            bl.y = pd.top + BALL_R + 0.001  # depenetrate

            if self._dbg:
                print(f"[DEBUG] paddle hit rel={rel:.2f}  "
                      f"vx={bl.vx:.3f} vy={bl.vy:.3f}")

        # ── brick collisions ─────────────────────────────────────
        self._collide_bricks()

        bl.np.setPos(bl.x, 0, bl.y)
        return True

    def _collide_bricks(self) -> None:
        """
        AABB collision between ball and bricks.
        Only one brick is resolved per sub-step (break after first hit)
        to avoid double-counting and velocity-direction chaos.
        The correct axis is determined by comparing the X and Y penetration
        depths: the smaller depth indicates the axis of collision.
        """
        bl = self.ball

        for brick in self.bricks:
            if not brick.alive:
                continue

            # Minkowski-sum half-extents
            hx = BRICK_W / 2 + BALL_R
            hy = BRICK_H / 2 + BALL_R

            ox = hx - abs(bl.x - brick.cx)   # x overlap (penetration)
            oy = hy - abs(bl.y - brick.cy)   # y overlap

            if ox <= 0 or oy <= 0:
                continue    # no intersection

            # ── resolve collision ───────────────────────────────
            if ox < oy:
                # Horizontal penetration is smaller → side hit
                direction = math.copysign(1.0, bl.x - brick.cx)
                bl.vx = direction * abs(bl.vx)
                bl.x += direction * ox
            else:
                # Vertical penetration is smaller → top/bottom hit
                direction = math.copysign(1.0, bl.y - brick.cy)
                bl.vy = direction * abs(bl.vy)
                bl.y += direction * oy

            # ── score & speed ───────────────────────────────────
            pts = brick.hit()
            self.score += pts
            if self.score > self.high_score:
                self.high_score = self.score

            if not brick.alive:
                # Accelerate ball on destroy
                bl.spd = min(bl.spd + BALL_ACCEL, BALL_SPD_MAX)
                nx, ny = norm2(bl.vx, bl.vy)
                bl.vx = nx * bl.spd
                bl.vy = ny * bl.spd
                bl.vx, bl.vy = fix_vy(bl.vx, bl.vy, bl.spd)

            if self._dbg:
                print(f"[DEBUG] brick({brick.row},{brick.col}) hit  "
                      f"ox={ox:.4f} oy={oy:.4f}  "
                      f"vx={bl.vx:.3f} vy={bl.vy:.3f}  pts={pts}")

            break   # one brick per sub-step

    def _handle_ball_lost(self) -> None:
        self.lives -= 1
        self._tick_hud()
        if self.lives <= 0:
            self._show_gameover()
        else:
            self.ball.spd = BALL_SPD0          # reset speed
            self.ball.attach_to(self.paddle.x)  # re-attach


# ════════════════════════════════════════════════════════════════
#  SECTION 7 · ENTRY POINT
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    game = BreakoutGame()
    game.run()
