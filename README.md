# BREAKOUT — Panda3D Python Clone

A complete, single-file Breakout / Arkanoid clone built with **Panda3D** and
pure Python 3.  No external assets required — every visual is drawn with
coloured geometry.

---

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Tested on **Python 3.10 – 3.12** / **Panda3D 1.10.x** on Windows, macOS and Linux.

---

## Controls

| Key | Action |
|-----|--------|
| `A` / `←` | Move paddle left |
| `D` / `→` | Move paddle right |
| `SPACE` | Launch ball (when attached to paddle) |
| `ESC` | Pause / Resume |
| `R` | Restart current level |
| `Q` | Quit |
| `F1` | Toggle debug output (collision logs to console) |

---

## Features

* **3 levels** with distinct layouts (classic rainbow, diamond, hard-brick maze)
* **Hard bricks** (grey) require 2 hits; change colour after the first
* **Ball speed** increases gradually with each brick destroyed
* **Angle reflection** off paddle: hitting the edge sends the ball at a steeper angle
* **Persistent high score** stored in `save.json` (created automatically)
* Full **menu → gameplay → pause → game over / victory** state machine
* Live **HUD**: score, high score, level, lives

---

## Project Structure

```
breakout_panda3d/
├── main.py          ← entire game (600 lines)
├── requirements.txt
├── README.md
└── save.json        ← auto-created on first score
```

---

## Architecture (inside main.py)

| Section | Contents |
|---------|----------|
| **CONFIG** | All constants: window, field, paddle, ball, bricks, scoring |
| **LEVELS** | Level layouts as 2-D integer matrices |
| **UTILITIES** | `clamp`, `norm2`, `fix_vy`, `make_card`, save/load helpers |
| **ENTITIES** | `Paddle`, `Ball`, `Brick` — AABB boxes + visual NodePaths |
| **UI HELPERS** | `_btn`, `_txt` factory functions |
| **GAME** | `BreakoutGame(ShowBase)` — state machine, input, physics, rendering |
| **ENTRY POINT** | `if __name__ == "__main__":` |

---

## Collision System

Collisions are **manual AABB** (Section: `_collide_bricks`, `_physics_step`).

### Tunnelling prevention

The ball's movement is sub-stepped: each visual frame is divided into
`SUBSTEPS = 4` micro-steps.  Combined with a maximum dt cap of
`DT_CAP = 0.05 s` (~20 fps minimum), the maximum ball displacement per
micro-step is:

```
max_disp = BALL_SPD_MAX × DT_CAP / SUBSTEPS
         = 2.20 × 0.05 / 4
         = 0.0275 units
```

This is less than half of `BRICK_H = 0.062`, so the ball cannot skip through
a brick in a single step even at maximum speed.

### Axis selection

For each brick overlap, the **smaller penetration depth** determines the
collision axis:

* `ox < oy` → side hit → flip `vx`
* `oy ≤ ox` → top/bottom hit → flip `vy`

Only the **first** overlapping brick is resolved per sub-step to avoid
double-counting and velocity corruption.

### Paddle reflection

```
rel = (ball.x − paddle_centre) / (paddle_half_width)   # ∈ [-1, 1]
angle_from_vertical = rel × 60°                        # ∈ [-60°, 60°]
vx = speed × sin(angle)
vy = speed × cos(angle)   # always positive → upward
```

A guard (`fix_vy`) enforces `|vy| ≥ MIN_VY` to prevent horizontal loops.

---

## Extending the Game

* **Add a level**: append a 6×10 matrix to `LEVELS` in `main.py`.  
  Cells: `0` = empty, `1-6` = normal brick (picks row colour), `9` = hard brick.
* **Change difficulty**: edit `BALL_ACCEL`, `BALL_SPD_MAX`, `LIVES0` in the
  CONFIG section.
* **Add sounds**: Panda3D's `AudioManager` / `loader.loadSfx()` — hook into
  `Brick.hit()` and `Ball.launch()`.
