import tkinter as tk


WIDTH = 800
HEIGHT = 600
PADDLE_WIDTH = 110
PADDLE_HEIGHT = 14
BALL_RADIUS = 9
BRICK_COLUMNS = 10
BRICK_ROWS = 5
BRICK_WIDTH = 68
BRICK_HEIGHT = 22
BRICK_GAP = 7


class BreakoutGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("블럭깨기")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=WIDTH,
            height=HEIGHT,
            bg="#101827",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.score = 0
        self.lives = 3
        self.level = 1
        self.state = "ready"
        self.keys: set[str] = set()
        self.bricks: list[dict[str, object]] = []

        self.score_text = self.canvas.create_text(
            20, 20, anchor="nw", fill="white", font=("Arial", 15, "bold")
        )
        self.lives_text = self.canvas.create_text(
            WIDTH - 20, 20, anchor="ne", fill="white", font=("Arial", 15, "bold")
        )
        self.level_text = self.canvas.create_text(
            WIDTH / 2, 20, fill="#b9c9e8", font=("Arial", 13)
        )
        self.paddle = self.canvas.create_rectangle(
            0, 0, 0, 0, fill="#55d6be", outline=""
        )
        self.ball = self.canvas.create_oval(
            0, 0, 0, 0, fill="#ffd166", outline=""
        )
        self.message = self.canvas.create_text(
            WIDTH / 2,
            HEIGHT / 2,
            fill="white",
            font=("Arial", 22, "bold"),
            justify="center",
        )

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.canvas.bind("<Button-1>", self.start_game)

        self.create_bricks()
        self.reset_round()
        self.update_status()
        self.show_message("블럭깨기\n스페이스 또는 화면 클릭으로 시작")
        self.tick()

    def reset_round(self) -> None:
        self.canvas.coords(
            self.paddle,
            (WIDTH - PADDLE_WIDTH) / 2,
            HEIGHT - 48,
            (WIDTH + PADDLE_WIDTH) / 2,
            HEIGHT - 48 + PADDLE_HEIGHT,
        )
        self.ball_dx = 4.0
        self.ball_dy = -4.0
        self.attach_ball()

    def attach_ball(self) -> None:
        x1, y1, x2, _ = self.canvas.coords(self.paddle)
        x = (x1 + x2) / 2
        y = y1 - BALL_RADIUS - 1
        self.canvas.coords(
            self.ball,
            x - BALL_RADIUS,
            y - BALL_RADIUS,
            x + BALL_RADIUS,
            y + BALL_RADIUS,
        )

    def create_bricks(self) -> None:
        for brick in self.bricks:
            self.canvas.delete(brick["id"])
        self.bricks.clear()

        total_width = BRICK_COLUMNS * BRICK_WIDTH + (BRICK_COLUMNS - 1) * BRICK_GAP
        left = (WIDTH - total_width) / 2
        colors = ["#ff6b6b", "#f7a440", "#ffd166", "#70c1b3", "#5b8def"]

        for row in range(BRICK_ROWS):
            for column in range(BRICK_COLUMNS):
                x1 = left + column * (BRICK_WIDTH + BRICK_GAP)
                y1 = 70 + row * (BRICK_HEIGHT + BRICK_GAP)
                brick_id = self.canvas.create_rectangle(
                    x1,
                    y1,
                    x1 + BRICK_WIDTH,
                    y1 + BRICK_HEIGHT,
                    fill=colors[row],
                    outline="",
                )
                self.bricks.append(
                    {
                        "id": brick_id,
                        "x1": x1,
                        "y1": y1,
                        "x2": x1 + BRICK_WIDTH,
                        "y2": y1 + BRICK_HEIGHT,
                    }
                )

    def update_status(self) -> None:
        self.canvas.itemconfigure(self.score_text, text=f"점수: {self.score}")
        self.canvas.itemconfigure(self.lives_text, text=f"목숨: {self.lives}")
        self.canvas.itemconfigure(self.level_text, text=f"레벨 {self.level}")

    def show_message(self, text: str) -> None:
        self.canvas.itemconfigure(self.message, text=text)

    def start_game(self, event: tk.Event | None = None) -> None:
        if self.state in {"ready", "paused"}:
            self.state = "running"
            self.show_message("")

    def toggle_pause(self) -> None:
        if self.state == "running":
            self.state = "paused"
            self.show_message("일시 정지\n스페이스를 눌러 계속")
        elif self.state in {"ready", "paused"}:
            self.start_game()

    def restart(self) -> None:
        self.score = 0
        self.lives = 3
        self.level = 1
        self.state = "ready"
        self.create_bricks()
        self.reset_round()
        self.update_status()
        self.show_message("블럭깨기\n스페이스 또는 화면 클릭으로 시작")

    def on_key_press(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        self.keys.add(key)

        if key == "space":
            self.toggle_pause()
        elif key == "r":
            self.restart()

    def on_key_release(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def move_paddle(self) -> None:
        dx = 0
        if "left" in self.keys or "a" in self.keys:
            dx -= 7
        if "right" in self.keys or "d" in self.keys:
            dx += 7

        x1, _, x2, _ = self.canvas.coords(self.paddle)
        if x1 + dx < 0:
            dx = -x1
        elif x2 + dx > WIDTH:
            dx = WIDTH - x2

        self.canvas.move(self.paddle, dx, 0)
        if self.state != "running":
            self.attach_ball()

    def update_ball(self) -> None:
        x1, y1, x2, y2 = self.canvas.coords(self.ball)
        old_x = (x1 + x2) / 2
        old_y = (y1 + y2) / 2
        self.canvas.move(self.ball, self.ball_dx, self.ball_dy)
        x1, y1, x2, y2 = self.canvas.coords(self.ball)
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        if x1 <= 0 or x2 >= WIDTH:
            self.ball_dx = -self.ball_dx
        if y1 <= 42:
            self.ball_dy = abs(self.ball_dy)
        if y1 >= HEIGHT:
            self.lives -= 1
            self.update_status()
            if self.lives <= 0:
                self.state = "game_over"
                self.show_message(f"게임 오버\n최종 점수: {self.score}\nR 키로 다시 시작")
            else:
                self.state = "ready"
                self.reset_round()
                self.show_message("공을 놓쳤어요!\n스페이스를 눌러 계속")
            return

        px1, py1, px2, _ = self.canvas.coords(self.paddle)
        if (
            self.ball_dy > 0
            and y2 >= py1
            and y1 <= py1 + PADDLE_HEIGHT
            and x2 >= px1
            and x1 <= px2
        ):
            offset = (center_x - (px1 + px2) / 2) / (PADDLE_WIDTH / 2)
            self.ball_dx = offset * 5.5
            if abs(self.ball_dx) < 1:
                self.ball_dx = 1 if self.ball_dx >= 0 else -1
            self.ball_dy = -abs(self.ball_dy)
            self.canvas.coords(
                self.ball, x1, py1 - BALL_RADIUS * 2 - 1, x2, py1 - 1
            )

        for brick in self.bricks[:]:
            bx1 = float(brick["x1"])
            by1 = float(brick["y1"])
            bx2 = float(brick["x2"])
            by2 = float(brick["y2"])
            if x2 < bx1 or x1 > bx2 or y2 < by1 or y1 > by2:
                continue

            if old_x <= bx1 or old_x >= bx2:
                self.ball_dx = -self.ball_dx
            else:
                self.ball_dy = -self.ball_dy
            self.canvas.delete(brick["id"])
            self.bricks.remove(brick)
            self.score += 10
            self.update_status()
            break

        if not self.bricks:
            self.level += 1
            self.create_bricks()
            self.reset_round()
            self.state = "ready"
            self.ball_dx *= 1 + min(self.level * 0.05, 0.35)
            self.ball_dy *= 1 + min(self.level * 0.05, 0.35)
            self.update_status()
            self.show_message(f"레벨 {self.level}!\n스페이스를 눌러 계속")

    def tick(self) -> None:
        self.move_paddle()
        if self.state == "running":
            self.update_ball()
        self.root.after(16, self.tick)


def main() -> None:
    root = tk.Tk()
    BreakoutGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
