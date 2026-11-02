import random
import tkinter as tk

CELL = 20
COLS, ROWS = 30, 20
WIDTH, HEIGHT = COLS * CELL, ROWS * CELL
SPEED_MS = 120

DIRECTIONS = {
    "Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0),
    "w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0),
}


class SnakeGame:
    def __init__(self, root):
        self.root = root
        root.title("Snake")
        root.resizable(False, False)

        self.score_var = tk.StringVar()
        tk.Label(root, textvariable=self.score_var, font=("Consolas", 14),
                 bg="#222", fg="white").pack(fill="x")
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT,
                                bg="black", highlightthickness=0)
        self.canvas.pack()

        root.bind("<Key>", self.on_key)
        self.after_id = None
        self.reset()

    def reset(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.next_direction = self.direction
        self.score = 0
        self.game_over = False
        self.paused = False
        self.food = self.spawn_food()
        self.update_score()
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.tick()

    def spawn_food(self):
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in self.snake]
        return random.choice(free) if free else None

    def update_score(self):
        self.score_var.set(f"Score: {self.score}   (방향키/WASD 이동, P 일시정지, R 재시작)")

    def on_key(self, event):
        key = event.keysym
        if key in ("r", "R"):
            self.reset()
            return
        if key in ("p", "P") and not self.game_over:
            self.paused = not self.paused
            self.draw()
            return
        if key in DIRECTIONS:
            dx, dy = DIRECTIONS[key]
            # 반대 방향으로 바로 꺾는 것 방지
            if (dx, dy) != (-self.direction[0], -self.direction[1]):
                self.next_direction = (dx, dy)

    def tick(self):
        if not self.game_over and not self.paused:
            self.step()
        self.draw()
        self.after_id = self.root.after(SPEED_MS, self.tick)

    def step(self):
        self.direction = self.next_direction
        hx, hy = self.snake[0]
        new_head = (hx + self.direction[0], hy + self.direction[1])

        out_of_bounds = not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS)
        # 꼬리는 이번 턴에 움직이므로 충돌 검사에서 제외
        hits_self = new_head in self.snake[:-1]
        if out_of_bounds or hits_self:
            self.game_over = True
            return

        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 10
            self.update_score()
            self.food = self.spawn_food()
            if self.food is None:  # 화면을 다 채움
                self.game_over = True
        else:
            self.snake.pop()

    def draw(self):
        c = self.canvas
        c.delete("all")
        if self.food:
            fx, fy = self.food
            c.create_oval(fx * CELL + 2, fy * CELL + 2,
                          (fx + 1) * CELL - 2, (fy + 1) * CELL - 2, fill="red", outline="")
        for i, (x, y) in enumerate(self.snake):
            color = "#7CFC00" if i == 0 else "#2E8B57"
            c.create_rectangle(x * CELL + 1, y * CELL + 1,
                               (x + 1) * CELL - 1, (y + 1) * CELL - 1, fill=color, outline="")
        if self.game_over:
            c.create_text(WIDTH // 2, HEIGHT // 2 - 15, text="GAME OVER",
                          fill="white", font=("Consolas", 32, "bold"))
            c.create_text(WIDTH // 2, HEIGHT // 2 + 25, text=f"점수: {self.score}  |  R 키로 재시작",
                          fill="white", font=("Consolas", 14))
        elif self.paused:
            c.create_text(WIDTH // 2, HEIGHT // 2, text="PAUSED",
                          fill="white", font=("Consolas", 32, "bold"))


if __name__ == "__main__":
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()
