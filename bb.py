"""버블 정원 — 비눗방울로 슬라임을 가두고 터뜨리는 한 화면 플랫포머 (pygame)

조작: ← → 이동 · Space/↑ 점프 · Z/X 비눗방울 · P/Esc 일시정지 · Enter 시작
떨어지면서 점프 키를 누르고 있으면 방울을 밟고 다시 튀어 오른다.
붙어 있는 방울은 함께 터지고, 갇힌 슬라임이 많을수록 점수가 두 배씩 오른다.
"""
import math
import random
import sys

import pygame

TILE = 32
COLS, ROWS = 20, 15
W, H = COLS * TILE, ROWS * TILE
HUD_H = 36
SCREEN_W, SCREEN_H = W, H + HUD_H
FPS = 60

GRAVITY = 0.45
MAX_FALL = 8
JUMP_V = -10.2  # 세 칸 위 발판까지 닿는 높이

# X: 벽, =: 발판(위에서만 밟힘), P: 플레이어 시작, E: 슬라임
LEVELS = [
    [
        "X======......======X",
        "X..................X",
        "X....E.......E.....X",
        "X...====....====...X",
        "X..................X",
        "X..E............E..X",
        "X======......======X",
        "X..................X",
        "X.........E........X",
        "X....==========....X",
        "X..................X",
        "X..................X",
        "X==....======....==X",
        "X.P................X",
        "X======......======X",
    ],
    [
        "X====..........====X",
        "X..................X",
        "X......E....E......X",
        "X..==..==..==..==..X",
        "X..................X",
        "X..E............E..X",
        "X=====........=====X",
        "X..................X",
        "X.........E........X",
        "X.......====.......X",
        "X..................X",
        "X........E.........X",
        "X===....====....===X",
        "X.P................X",
        "X=====........=====X",
    ],
    [
        "X.......====.......X",
        "X..................X",
        "X..E............E..X",
        "X=======....=======X",
        "X..................X",
        "X.......E...E......X",
        "X...============...X",
        "X..................X",
        "X.E..............E.X",
        "X==......==......==X",
        "X..................X",
        "X.....E............X",
        "X....====..====....X",
        "X.P................X",
        "X========..========X",
    ],
]

PLATFORM_COLORS = [
    ((255, 170, 90), (190, 105, 50)),
    ((110, 195, 255), (55, 120, 195)),
    ((205, 145, 255), (130, 80, 200)),
]

# (색, 점수) — 한 번에 많이 가둘수록 좋은 열매가 나온다
FRUIT_KINDS = [
    ((255, 95, 110), 500),
    ((255, 200, 70), 700),
    ((140, 230, 120), 900),
    ((190, 130, 255), 1200),
]


def load_font(size):
    return pygame.font.SysFont(
        "malgungothic,applesdgothicneo,nanumgothic,notosanscjkkr,arial", size, bold=True
    )


class Input:
    def __init__(self):
        self.left = self.right = self.jump_held = False
        self.jump = self.shoot = self.start = self.pause = False


class Level:
    def __init__(self, rows):
        self.grid = []
        self.player_spawn = (2, 13)
        self.enemy_spawns = []
        for r, line in enumerate(rows):
            assert len(line) == COLS, f"{r}번째 줄 길이가 {len(line)}"
            row = []
            for c, ch in enumerate(line):
                if ch == "P":
                    self.player_spawn = (c, r)
                elif ch == "E":
                    self.enemy_spawns.append((c, r))
                row.append(ch if ch in "=X" else ".")
            self.grid.append(row)
        assert len(self.grid) == ROWS

    def solid(self, col, row):
        return 0 <= row < ROWS and 0 <= col < COLS and self.grid[row][col] != "."


class Body:
    def __init__(self, x, y, w, h):
        self.x, self.y = float(x), float(y)
        self.w, self.h = w, h
        self.vx = self.vy = 0.0
        self.on_ground = False

    @classmethod
    def on_tile(cls, col, row, *args):
        body = cls(0, 0, *args)
        body.x = col * TILE + (TILE - body.w) / 2
        body.y = (row + 1) * TILE - body.h
        return body

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


def step_body(body, level):
    """중력과 발판 충돌을 처리한다. 좌우 벽에 부딪혔으면 True."""
    body.x += body.vx
    hit_wall = False
    if body.x < TILE:
        body.x, hit_wall = TILE, True
    elif body.x + body.w > W - TILE:
        body.x, hit_wall = W - TILE - body.w, True

    old_bottom = body.y + body.h
    body.vy = min(body.vy + GRAVITY, MAX_FALL)
    body.y += body.vy
    body.on_ground = False
    if body.vy >= 0:
        new_bottom = body.y + body.h
        row = int(new_bottom // TILE)
        top = row * TILE
        if old_bottom <= top + 0.001:
            for col in range(int(body.x) // TILE, int(body.x + body.w - 1) // TILE + 1):
                if level.solid(col, row):
                    body.y = top - body.h
                    body.vy = 0
                    body.on_ground = True
                    break

    # 바닥 틈으로 떨어지면 위에서, 천장 틈으로 올라가면 아래에서 나타난다
    if body.y > H:
        body.y = -body.h
    elif body.y + body.h < 0:
        body.y = H
    return hit_wall


class Player(Body):
    def __init__(self, x, y, w=26, h=28):
        super().__init__(x, y, w, h)
        self.facing = 1
        self.invuln = 120
        self.shoot_cd = 0
        self.anim = 0


class Enemy(Body):
    def __init__(self, x, y, w=28, h=24):
        super().__init__(x, y, w, h)
        self.dir = random.choice((-1, 1))
        self.speed = 1.3
        self.trapped = False
        self.angry = False
        self.walk_off = False
        self.jump_cd = random.randint(60, 180)


class Fruit(Body):
    def __init__(self, x, y, kind):
        super().__init__(x - 10, y - 10, 20, 20)
        self.color, self.points = FRUIT_KINDS[kind]
        self.timer = 600
        self.vy = -4


class Bubble:
    def __init__(self, x, y, direction):
        self.x, self.y = x, y
        self.vx = 7 * direction
        self.state = "shot"
        self.travel = 0
        self.timer = 0
        self.enemy = None
        self.phase = random.random() * math.tau

    @property
    def r(self):
        return 18 if self.enemy else 14

    def hits_rect(self, rect):
        nx = max(rect.left, min(self.x, rect.right))
        ny = max(rect.top, min(self.y, rect.bottom))
        return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2


def at_edge(e, level):
    front = e.x + e.w + 2 if e.dir > 0 else e.x - 2
    row = int((e.y + e.h + 1) // TILE)
    return not level.solid(int(front // TILE), row)


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.field = pygame.Surface((W, H))
        self.font = load_font(18)
        self.small = load_font(14)
        self.big = load_font(42)
        self.bg = self.make_background()
        self.hiscore = 0
        self.state = "title"
        self.paused = False
        self.reset()

    # ---------- 진행 ----------
    def reset(self):
        self.score = 0
        self.lives = 3
        self.stage = 0
        self.load_stage()

    def load_stage(self):
        self.level = Level(LEVELS[self.stage % len(LEVELS)])
        loop = self.stage // len(LEVELS)
        self.player = Player.on_tile(*self.level.player_spawn)
        self.enemies = []
        for c, r in self.level.enemy_spawns:
            e = Enemy.on_tile(c, r)
            e.speed = 1.3 + 0.25 * loop + random.uniform(-0.1, 0.2)
            self.enemies.append(e)
        self.bubbles = []
        self.fruits = []
        self.popups = []
        self.particles = []
        self.clear_timer = 0
        self.stage_banner = 90

    def add_score(self, pts):
        self.score += pts
        self.hiscore = max(self.hiscore, self.score)

    def popup(self, text, x, y, color=(255, 240, 150)):
        self.popups.append([text, x, y, 50, color])

    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.random() * math.tau
            s = random.uniform(1, 4)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, random.randint(15, 30), color])

    def lose_life(self):
        p = self.player
        self.burst(p.cx, p.cy, (120, 230, 255), 24)
        self.lives -= 1
        if self.lives <= 0:
            self.state = "over"
            return
        self.player = Player.on_tile(*self.level.player_spawn)

    def update(self, inp):
        if self.state in ("title", "over"):
            if inp.start:
                self.reset()
                self.state = "play"
            return
        if inp.pause:
            self.paused = not self.paused
        if self.paused:
            return

        if self.stage_banner > 0:
            self.stage_banner -= 1
        self.update_player(inp)
        if self.state != "play":
            return
        self.update_enemies()
        if self.state != "play":
            return
        self.update_bubbles(inp)
        self.update_fruits()
        self.update_effects()

        if not self.enemies:
            self.clear_timer += 1
            if self.clear_timer > 150:
                self.stage += 1
                self.load_stage()

    def update_player(self, inp):
        p = self.player
        p.vx = (inp.right - inp.left) * 2.8
        if p.vx:
            p.facing = 1 if p.vx > 0 else -1
            p.anim += 1
        if inp.jump and p.on_ground:
            p.vy = JUMP_V
        if p.shoot_cd > 0:
            p.shoot_cd -= 1
        if inp.shoot and p.shoot_cd == 0:
            self.bubbles.append(Bubble(p.cx + p.facing * 12, p.cy, p.facing))
            p.shoot_cd = 16
        step_body(p, self.level)
        if p.invuln > 0:
            p.invuln -= 1

    def update_enemies(self):
        p = self.player
        for e in self.enemies:
            if e.trapped:
                continue
            if e.on_ground:
                if at_edge(e, self.level):
                    # 발판 끝에서 절반은 돌아서고 절반은 뛰어내린다
                    if not e.walk_off:
                        if random.random() < 0.5:
                            e.dir = -e.dir
                        else:
                            e.walk_off = True
                else:
                    e.walk_off = False
                e.jump_cd -= 1
                if e.jump_cd <= 0 and p.y < e.y - TILE and abs(p.cx - e.cx) < 140:
                    e.vy = JUMP_V
                    e.jump_cd = random.randint(90, 200)
            e.vx = e.dir * e.speed * (1.6 if e.angry else 1)
            if step_body(e, self.level):
                e.dir = -e.dir
            if p.invuln == 0 and e.rect.inflate(-8, -8).colliderect(p.rect.inflate(-6, -4)):
                self.lose_life()
                return

    def update_bubbles(self, inp):
        p = self.player
        for b in self.bubbles[:]:
            if b not in self.bubbles:  # 연쇄로 이미 터진 방울
                continue
            b.timer += 1
            if b.state == "shot":
                b.x += b.vx
                b.travel += abs(b.vx)
                if b.x - b.r < TILE or b.x + b.r > W - TILE or b.travel > 130:
                    b.x = max(TILE + b.r, min(W - TILE - b.r, b.x))
                    b.state = "float"
                for e in self.enemies:
                    if not e.trapped and b.hits_rect(e.rect):
                        e.trapped = True
                        b.enemy = e
                        b.state = "float"
                        b.timer = 0
                        break
            else:
                b.y = max(TILE + b.r, b.y - 0.8)
                b.x += math.sin(b.timer * 0.05 + b.phase) * 0.5
                b.x = max(TILE + b.r, min(W - TILE - b.r, b.x))

            if b.enemy:
                b.enemy.x = b.x - b.enemy.w / 2
                b.enemy.y = b.y - b.enemy.h / 2
                if b.timer > 540:
                    # 너무 오래 두면 슬라임이 빠져나와 화가 난다
                    e = b.enemy
                    e.trapped, e.angry, e.vy = False, True, 0
                    self.bubbles.remove(b)
                    self.burst(b.x, b.y, (255, 140, 140), 10)
                    self.popup("화났다!", b.x, b.y - 20, (255, 140, 140))
                    continue
            elif b.timer > 420:
                self.bubbles.remove(b)
                self.burst(b.x, b.y, (180, 220, 255), 6)
                continue

            if b.state == "float" and b.hits_rect(p.rect):
                if p.vy > 0 and p.y + p.h < b.y and inp.jump_held:
                    p.vy = JUMP_V * 0.9
                else:
                    self.pop_chain(b)

    def pop_chain(self, first):
        chain = [first]
        i = 0
        while i < len(chain):
            cur = chain[i]
            for other in self.bubbles:
                if (other not in chain and other.state == "float"
                        and math.hypot(other.x - cur.x, other.y - cur.y) < cur.r + other.r + 6):
                    chain.append(other)
            i += 1

        caught = 0
        for b in chain:
            self.bubbles.remove(b)
            self.burst(b.x, b.y, (200, 240, 255), 8)
            if b.enemy:
                caught += 1
                pts = 1000 * 2 ** (caught - 1)
                self.add_score(pts)
                self.popup(f"+{pts}", b.x, b.y - 10)
                self.enemies.remove(b.enemy)
                self.burst(b.x, b.y, (150, 230, 120), 14)
                self.fruits.append(Fruit(b.x, b.y, min(caught - 1, len(FRUIT_KINDS) - 1)))
            else:
                self.add_score(10)
        if caught >= 2:
            self.popup(f"연쇄 x{caught}!", first.x, first.y - 34, (255, 180, 80))

    def update_fruits(self):
        p = self.player
        for f in self.fruits[:]:
            step_body(f, self.level)
            f.timer -= 1
            if f.rect.colliderect(p.rect):
                self.add_score(f.points)
                self.popup(f"+{f.points}", f.cx, f.y, f.color)
                self.fruits.remove(f)
            elif f.timer <= 0:
                self.fruits.remove(f)

    def update_effects(self):
        for pp in self.popups[:]:
            pp[2] -= 0.6
            pp[3] -= 1
            if pp[3] <= 0:
                self.popups.remove(pp)
        for pt in self.particles[:]:
            pt[0] += pt[2]
            pt[1] += pt[3]
            pt[3] += 0.12
            pt[4] -= 1
            if pt[4] <= 0:
                self.particles.remove(pt)

    # ---------- 그리기 ----------
    def make_background(self):
        bg = pygame.Surface((W, H))
        for y in range(H):
            t = y / H
            bg.fill((int(16 + 14 * t), int(26 + 34 * t), int(46 + 24 * t)), (0, y, W, 1))
        rng = random.Random(7)
        for _ in range(60):
            x, y = rng.randrange(W), rng.randrange(H)
            c = rng.randint(50, 90)
            pygame.draw.circle(bg, (c, c + 20, c + 30), (x, y), rng.choice((1, 1, 2)))
        return bg

    def draw_level(self, surf):
        base, dark = PLATFORM_COLORS[self.stage % len(PLATFORM_COLORS)]
        for r, row in enumerate(self.level.grid):
            for c, ch in enumerate(row):
                x, y = c * TILE, r * TILE
                if ch == "X":
                    pygame.draw.rect(surf, dark, (x, y, TILE, TILE))
                    pygame.draw.rect(surf, base, (x + 3, y + 3, TILE - 6, TILE - 6), 2, border_radius=4)
                elif ch == "=":
                    pygame.draw.rect(surf, dark, (x, y + 4, TILE, 12), border_radius=4)
                    pygame.draw.rect(surf, base, (x, y, TILE, 12), border_radius=4)

    def draw_player(self, surf, p):
        if p.invuln and (p.invuln // 4) % 2:
            return
        r = p.rect
        step = math.sin(p.anim * 0.35) * 2 if p.vx and p.on_ground else 0
        pygame.draw.rect(surf, (40, 90, 100), (r.x + 3, r.bottom - 5 - step, 8, 5), border_radius=2)
        pygame.draw.rect(surf, (40, 90, 100), (r.right - 11, r.bottom - 5 + step, 8, 5), border_radius=2)
        body = pygame.Rect(r.x, r.y + 6, r.w, r.h - 10)
        pygame.draw.rect(surf, (90, 210, 200), body, border_radius=8)
        visor = pygame.Rect(0, 0, 18, 9)
        visor.center = (r.centerx + p.facing * 3, r.y + 15)
        pygame.draw.rect(surf, (20, 40, 60), visor, border_radius=4)
        for dx in (-4, 4):
            pygame.draw.circle(surf, (160, 255, 250), (visor.centerx + dx + p.facing, visor.centery), 2)
        pygame.draw.line(surf, (200, 220, 230), (r.centerx, r.y + 6), (r.centerx, r.y + 1), 2)
        tip = (255, 120, 120) if (pygame.time.get_ticks() // 300) % 2 else (255, 220, 120)
        pygame.draw.circle(surf, tip, (r.centerx, r.y + 1), 3)

    def draw_enemy(self, surf, e):
        r = e.rect
        color = (255, 110, 110) if e.angry else (150, 230, 120)
        shade = (200, 70, 70) if e.angry else (90, 170, 80)
        pygame.draw.ellipse(surf, shade, (r.x, r.y + 6, r.w, r.h - 6))
        pygame.draw.ellipse(surf, color, (r.x + 2, r.y, r.w - 4, r.h - 4))
        d = e.dir
        for dx in (-6, 6):
            ex, ey = r.centerx + dx + d * 2, r.centery - 3
            pygame.draw.circle(surf, (255, 255, 255), (ex, ey), 4)
            pygame.draw.circle(surf, (20, 20, 30), (ex + d, ey), 2)
        if e.angry:
            pygame.draw.line(surf, (60, 10, 10), (r.centerx - 10, r.centery - 9), (r.centerx - 3, r.centery - 6), 2)
            pygame.draw.line(surf, (60, 10, 10), (r.centerx + 10, r.centery - 9), (r.centerx + 3, r.centery - 6), 2)

    def draw_bubble(self, surf, b):
        if b.enemy:
            self.draw_enemy(surf, b.enemy)
        R = b.r
        s = pygame.Surface((R * 2 + 4, R * 2 + 4), pygame.SRCALPHA)
        c = (R + 2, R + 2)
        expiring = b.timer > (440 if b.enemy else 340)
        tint = (255, 150, 150) if expiring and (b.timer // 6) % 2 else (150, 220, 255)
        pygame.draw.circle(s, (*tint, 55), c, R)
        pygame.draw.circle(s, (*tint, 210), c, R, 2)
        pygame.draw.circle(s, (255, 255, 255, 200), (c[0] - R // 3, c[1] - R // 3), 3)
        surf.blit(s, (b.x - R - 2, b.y - R - 2))

    def draw_fruit(self, surf, f):
        if f.timer < 120 and (f.timer // 5) % 2:
            return
        r = f.rect
        pygame.draw.circle(surf, f.color, r.center, 9)
        pygame.draw.circle(surf, (255, 255, 255), (r.centerx - 3, r.centery - 3), 2)
        pygame.draw.ellipse(surf, (90, 200, 90), (r.centerx, r.y - 2, 8, 5))

    def text(self, font, msg, center, color=(235, 240, 255)):
        img = font.render(msg, True, color)
        self.screen.blit(img, img.get_rect(center=center))

    def draw_hud(self):
        self.screen.blit(self.font.render(f"점수 {self.score}", True, (235, 240, 255)), (12, 8))
        self.text(self.font, f"최고 {self.hiscore}", (SCREEN_W // 2, HUD_H // 2), (255, 210, 120))
        stage_img = self.font.render(f"스테이지 {self.stage + 1}", True, (235, 240, 255))
        self.screen.blit(stage_img, (SCREEN_W - 140 - stage_img.get_width(), 8))
        for i in range(self.lives):
            x = SCREEN_W - 24 - i * 22
            pygame.draw.rect(self.screen, (90, 210, 200), (x - 8, 10, 16, 16), border_radius=5)
            pygame.draw.rect(self.screen, (20, 40, 60), (x - 5, 14, 10, 5), border_radius=2)

    def overlay(self, title, lines, color=(255, 200, 90)):
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((8, 10, 22, 190))
        self.screen.blit(dim, (0, 0))
        cy = SCREEN_H // 2 - 30 * len(lines) // 2 - 30
        self.text(self.big, title, (SCREEN_W // 2, cy), color)
        for i, line in enumerate(lines):
            self.text(self.font, line, (SCREEN_W // 2, cy + 60 + i * 30))

    def draw(self):
        f = self.field
        f.blit(self.bg, (0, 0))
        self.draw_level(f)
        for fr in self.fruits:
            self.draw_fruit(f, fr)
        for e in self.enemies:
            if not e.trapped:
                self.draw_enemy(f, e)
        if self.state == "play":
            self.draw_player(f, self.player)
        for b in self.bubbles:
            self.draw_bubble(f, b)
        for x, y, _, _, life, color in self.particles:
            pygame.draw.circle(f, color, (int(x), int(y)), 2 if life < 12 else 3)
        for msg, x, y, _, color in self.popups:
            img = self.small.render(msg, True, color)
            f.blit(img, img.get_rect(center=(x, y)))

        self.screen.fill((12, 16, 28))
        self.screen.blit(f, (0, HUD_H))
        self.draw_hud()

        mid = (SCREEN_W // 2, HUD_H + H // 2)
        if self.state == "title":
            self.overlay("버블 정원", [
                "꼬마 로봇 피프가 비눗방울로 슬라임을 가둬요",
                "← → 이동 · Space 점프 · Z 비눗방울",
                "점프 키를 누른 채 떨어지면 방울을 밟고 튀어 올라요",
                "붙어 있는 방울은 함께 터지고 점수가 두 배씩!",
                "Enter 를 눌러 시작",
            ], (140, 220, 255))
        elif self.state == "over":
            self.overlay("게임 오버", [f"점수 {self.score}  ·  스테이지 {self.stage + 1}", "Enter 로 다시 시작"])
        elif self.paused:
            self.overlay("일시정지", ["P 를 눌러 계속하기"])
        elif self.clear_timer:
            self.text(self.big, "스테이지 클리어!", mid, (255, 220, 120))
        elif self.stage_banner:
            self.text(self.big, f"스테이지 {self.stage + 1}", mid, (140, 220, 255))


def main():
    pygame.init()
    pygame.display.set_caption("버블 정원")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()
    game = Game(screen)

    while True:
        inp = Input()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_UP):
                    inp.jump = True
                elif event.key in (pygame.K_z, pygame.K_x):
                    inp.shoot = True
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    inp.start = True
                elif event.key in (pygame.K_p, pygame.K_ESCAPE):
                    inp.pause = True
        keys = pygame.key.get_pressed()
        inp.left = keys[pygame.K_LEFT]
        inp.right = keys[pygame.K_RIGHT]
        inp.jump_held = keys[pygame.K_SPACE] or keys[pygame.K_UP]

        game.update(inp)
        game.draw()
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
