import random
from collections import deque
import pyglet
from pyglet import shapes
from pyglet.window import key


from DIPPID import SensorUDP


# Window and grid configuration.
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700
CELL_SIZE = 28
GRID_COLS = 24
GRID_ROWS = 20
GRID_OFFSET_X = (WINDOW_WIDTH - GRID_COLS * CELL_SIZE) // 2
GRID_OFFSET_Y = 70
INITIAL_SNAKE_LENGTH = 3
WIN_SCORE = GRID_COLS * GRID_ROWS - INITIAL_SNAKE_LENGTH

# Game tuning.
GAME_TICK_SECONDS = 0.2
DIPPID_PORT = 5700
TILT_DEADZONE = 2.0


# Color palette for a cleaner look.
BG_TOP = (10, 20, 28)
BG_BOTTOM = (22, 40, 52)
BOARD_DARK = (20, 32, 40)
BOARD_LIGHT = (27, 44, 54)
SNAKE_HEAD = (95, 244, 165)
SNAKE_BODY = (40, 201, 137)
FOOD_COLOR = (255, 114, 117)
GRID_LINE = (60, 84, 99)
TEXT_MAIN = (229, 241, 248, 255)
TEXT_SUB = (172, 202, 217, 255)


def grid_to_pixel(cell_x: int, cell_y: int) -> tuple[int, int]:
    """Convert board coordinates to the lower-left pixel of the cell."""
    px = GRID_OFFSET_X + cell_x * CELL_SIZE
    py = GRID_OFFSET_Y + cell_y * CELL_SIZE
    return px, py


class SnakeGame:
    def __init__(self, game_window) -> None:
        self.window = game_window

        # Try to connect to DIPPID UDP sensor.
        self.sensor = SensorUDP(DIPPID_PORT)

        # Track button edges so one press triggers one action.
        self.last_button_state = 0

        self.score = 0
        self.game_over = False
        self.game_won = False
        self.paused = False

        # Direction vectors are grid steps per tick.
        self.direction = (1, 0)
        self.pending_direction = (1, 0)

        self.snake: deque[tuple[int, int]] = deque()
        self.food = (0, 0)
        self.restart()

        self.score_label = pyglet.text.Label(
            "",
            x=GRID_OFFSET_X,
            y=WINDOW_HEIGHT - 36,
            color=TEXT_MAIN,
            font_size=16,
        )
        self.info_label = pyglet.text.Label(
            "",
            x=GRID_OFFSET_X,
            y=30,
            color=TEXT_SUB,
            font_size=13,
        )

    def restart(self) -> None:
        """Reset game state for a fresh round."""
        center_x = GRID_COLS // 2
        center_y = GRID_ROWS // 2
        self.snake = deque(
            [
                (center_x - 1, center_y),
                (center_x, center_y),
                (center_x + 1, center_y),
            ]
        )
        self.direction = (1, 0)
        self.pending_direction = (1, 0)
        self.score = 0
        self.game_over = False
        self.game_won = False
        self.paused = False
        self.spawn_food()

    def spawn_food(self) -> None:
        """Place food on any free grid cell not occupied by the snake."""
        snake_cells = set(self.snake)
        free_cells = [
            (x, y)
            for x in range(GRID_COLS)
            for y in range(GRID_ROWS)
            if (x, y) not in snake_cells
        ]
        self.food = random.choice(free_cells)

    def set_direction(self, new_direction: tuple[int, int]) -> None:
        """Queue a direction change unless it would reverse into the neck."""
        if new_direction == (0, 0):
            return

        opposite = (-self.direction[0], -self.direction[1])
        if new_direction != opposite:
            self.pending_direction = new_direction

    def direction_from_vector(
        self, vector_data: dict
    ) -> tuple[int, int] | None:
        """Map a sensor vector to a cardinal direction with deadzone."""
        if not isinstance(vector_data, dict):
            return None

        x_val = float(vector_data.get("x", 0.0))
        y_val = float(vector_data.get("y", 0.0))

        if abs(x_val) < TILT_DEADZONE and abs(y_val) < TILT_DEADZONE:
            return None

        if abs(x_val) >= abs(y_val):
            return (-1, 0) if x_val > 0 else (1, 0)
        return (0, -1) if y_val > 0 else (0, 1)

    def handle_dippid_input(self) -> None:
        """Use gravity tilt for steering and button_1 for pause/restart."""
        gravity = self.sensor.get_value("gravity")
        tilt_direction = self.direction_from_vector(gravity)

        if tilt_direction is not None:
            self.set_direction(tilt_direction)

        button_state = int(self.sensor.get_value("button_1") or 0)
        rising_edge = button_state == 1 and self.last_button_state == 0
        self.last_button_state = button_state

        if not rising_edge:
            return

        if self.game_over:
            self.restart()
        else:
            self.paused = not self.paused

    def update(self, _delta_time: float) -> None:
        """Advance game state on a fixed tick."""
        self.handle_dippid_input()

        if self.game_over or self.paused:
            return

        self.direction = self.pending_direction
        head_x, head_y = self.snake[-1]
        next_head = (head_x + self.direction[0], head_y + self.direction[1])

        # End game if the snake leaves the board.
        if not (
            0 <= next_head[0] < GRID_COLS and 0 <= next_head[1] < GRID_ROWS
        ):
            self.game_over = True
            return

        # End game on self-collision.
        if next_head in self.snake:
            self.game_over = True
            return

        self.snake.append(next_head)

        # Eat food to grow, otherwise move by removing tail.
        if next_head == self.food:
            self.score += 1
            if self.score >= WIN_SCORE:
                self.game_over = True
                self.game_won = True
                return
            self.spawn_food()
        else:
            self.snake.popleft()

    def draw_background(self) -> None:
        """Draw a two-tone background and a subtle board frame."""
        top_rect = shapes.Rectangle(
            0,
            WINDOW_HEIGHT // 2,
            WINDOW_WIDTH,
            WINDOW_HEIGHT // 2,
            color=BG_TOP,
        )
        bottom_rect = shapes.Rectangle(
            0, 0, WINDOW_WIDTH, WINDOW_HEIGHT // 2, color=BG_BOTTOM
        )
        top_rect.draw()
        bottom_rect.draw()

        frame = shapes.BorderedRectangle(
            GRID_OFFSET_X - 6,
            GRID_OFFSET_Y - 6,
            GRID_COLS * CELL_SIZE + 12,
            GRID_ROWS * CELL_SIZE + 12,
            border=2,
            color=(15, 24, 31),
            border_color=(102, 147, 168),
        )
        frame.draw()

    def draw_board(self) -> None:
        """Draw checkerboard cells and light grid lines."""
        for x in range(GRID_COLS):
            for y in range(GRID_ROWS):
                cell_color = BOARD_LIGHT if (x + y) % 2 == 0 else BOARD_DARK
                px, py = grid_to_pixel(x, y)
                shapes.Rectangle(
                    px, py, CELL_SIZE, CELL_SIZE, color=cell_color
                ).draw()

        for x in range(GRID_COLS + 1):
            line_x = GRID_OFFSET_X + x * CELL_SIZE
            shapes.Line(
                line_x,
                GRID_OFFSET_Y,
                line_x,
                GRID_OFFSET_Y + GRID_ROWS * CELL_SIZE,
                thickness=1,
                color=GRID_LINE,
            ).draw()
        for y in range(GRID_ROWS + 1):
            line_y = GRID_OFFSET_Y + y * CELL_SIZE
            shapes.Line(
                GRID_OFFSET_X,
                line_y,
                GRID_OFFSET_X + GRID_COLS * CELL_SIZE,
                line_y,
                thickness=1,
                color=GRID_LINE,
            ).draw()

    def draw_food(self) -> None:
        """Draw food as a smaller square centered in the cell."""
        food_x, food_y = self.food
        px, py = grid_to_pixel(food_x, food_y)
        padding = CELL_SIZE // 6
        shapes.Rectangle(
            px + padding,
            py + padding,
            CELL_SIZE - 2 * padding,
            CELL_SIZE - 2 * padding,
            color=FOOD_COLOR,
        ).draw()

    def draw_snake(self) -> None:
        """Draw body and highlight the head with a brighter color."""
        for i, (x, y) in enumerate(self.snake):
            px, py = grid_to_pixel(x, y)
            color = SNAKE_HEAD if i == len(self.snake) - 1 else SNAKE_BODY
            inset = 2
            shapes.Rectangle(
                px + inset,
                py + inset,
                CELL_SIZE - 2 * inset,
                CELL_SIZE - 2 * inset,
                color=color,
            ).draw()

    def draw_hud(self) -> None:
        """Draw score and contextual help/status text."""
        self.score_label.text = f"Score: {self.score}"
        self.score_label.draw()

        if self.game_over and self.game_won:
            self.info_label.text = (
                "You Win - press SPACE or DIPPID button_1 to restart"
            )
        elif self.game_over:
            self.info_label.text = (
                "Game Over - press SPACE or DIPPID button_1 to restart"
            )
        elif self.paused:
            self.info_label.text = (
                "Paused - press SPACE or DIPPID button_1 to resume"
            )
        else:
            self.info_label.text = (
                "Tilt device (gravity) to steer | SPACE toggles pause"
            )
        self.info_label.draw()

    def on_draw(self) -> None:
        self.window.clear()
        self.draw_background()
        self.draw_board()
        self.draw_food()
        self.draw_snake()
        self.draw_hud()

    def on_key_press(self, symbol: int, _modifiers: int) -> None:
        """Keyboard fallback for local testing and debugging."""
        if symbol == key.UP:
            self.set_direction((0, 1))
        elif symbol == key.DOWN:
            self.set_direction((0, -1))
        elif symbol == key.LEFT:
            self.set_direction((-1, 0))
        elif symbol == key.RIGHT:
            self.set_direction((1, 0))
        elif symbol == key.SPACE:
            if self.game_over:
                self.restart()
            else:
                self.paused = not self.paused
        elif symbol == key.R:
            self.restart()

    def disconnect(self) -> None:
        """Stop DIPPID receiver thread before process exit."""
        self.sensor.disconnect()


def main() -> None:
    game_window = pyglet.window.Window(
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        caption="Snake + DIPPID",
    )
    game = SnakeGame(game_window)

    @game_window.event
    def on_draw() -> None:
        game.on_draw()

    @game_window.event
    def on_key_press(symbol: int, modifiers: int) -> None:
        game.on_key_press(symbol, modifiers)

    @game_window.event
    def on_close() -> None:
        game.disconnect()
        game_window.close()

    pyglet.clock.schedule_interval(game.update, GAME_TICK_SECONDS)
    pyglet.app.run()


if __name__ == "__main__":
    main()
