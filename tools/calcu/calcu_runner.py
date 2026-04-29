import time
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY


HOLD_THRESHOLD = 0.6
HOLD_REPEAT = 0.12


class CalcuRunner:
    def __init__(self):
        self.grid = [
            ' 7 ', ' 8 ', ' 9 ', ' / ',
            ' 4 ', ' 5 ', ' 6 ', ' * ',
            ' 1 ', ' 2 ', ' 3 ', ' - ',
            ' 0 ', ' . ', ' = ', ' + '
        ]

        self.cols = 4
        self.rows = 4
        self.page_size = self.cols * self.rows
        self.cursor_index = 0

        self.input_expr = ""
        self.output = ""
        self.display = MenuDisplay()

        # cache de render
        self.last_grid_render = None

    # ---------------- RENDER ----------------

    def _render(self):
        visible_items = self.grid[:self.page_size]

        if self.output == "":
            display_line = (self.input_expr + "_")[:20]
        else:
            display_line = self.output[:20]

        self.display.draw_grid(
            grid_items=visible_items,
            cursor_index=self.cursor_index,
            input_expr=display_line,
            output_expr=None,
            cols=self.cols,
            rows=self.rows
        )

    def _render_if_changed(self):
        visible_items = self.grid[:self.page_size]

        if self.output == "":
            display_line = (self.input_expr + "_")[:20]
        else:
            display_line = self.output[:20]

        render_data = (tuple(visible_items), self.cursor_index, display_line)
        if render_data == self.last_grid_render:
            return

        self._render()
        self.last_grid_render = render_data

    # ---------------- LOGICA ----------------

    def _handle_action(self, action):
        action = action.strip()

        if action == "=":
            try:
                self.output = str(eval(self.input_expr))
                self.input_expr = self.output
            except Exception:
                self.output = "Err"
        elif action == "C":
            self.input_expr = ""
            self.output = ""
        elif action == "BK":
            self.input_expr = self.input_expr[:-1]
        elif action == "EXIT":
            self.display.show_message(["   SALIENDO.   "], center=True)
            time.sleep(1)
            return True
        else:
            self.input_expr += action
            self.output = ""
        return False

    def _show_action_menu(self):
        actions = ["C", "BK", "EXIT"]
        index = 0
        last_render = None

        while True:
            lines = ["Acciones:"] + [
                f"> {a}" if i == index else f"  {a}"
                for i, a in enumerate(actions)
            ]

            if lines != last_render:
                self.display.show_message(lines)
                last_render = lines

            btns = read_buttons()
            if btns["up"]:
                index = (index - 1) % len(actions)
            elif btns["down"]:
                index = (index + 1) % len(actions)
            elif btns["enter"]:
                return actions[index]

            time.sleep(REPEAT_DELAY)

    # ---------------- RUN ----------------

    def run(self):
        # render inicial (UNA SOLA VEZ)
        self._render()
        self.last_grid_render = (
            tuple(self.grid[:self.page_size]),
            self.cursor_index,
            (self.input_expr + "_")[:20],
        )

        while True:
            self._render_if_changed()
            btns = read_buttons()

            # -------- UP --------
            if btns["up"]:
                t0 = time.time()
                moved = False

                while read_buttons()["up"]:
                    if time.time() - t0 >= HOLD_THRESHOLD:
                        self.cursor_index = (self.cursor_index - 1) % len(self.grid)
                        self._render()  # SOLO HOLD
                        moved = True
                        time.sleep(HOLD_REPEAT)
                    else:
                        time.sleep(0.01)

                # TAP → derecha
                if not moved:
                    self.cursor_index = (self.cursor_index + 1) % len(self.grid)

                self.last_grid_render = None

            # -------- DOWN --------
            elif btns["down"]:
                t0 = time.time()
                moved = False

                while read_buttons()["down"]:
                    if time.time() - t0 >= HOLD_THRESHOLD:
                        self.cursor_index = (self.cursor_index - self.cols) % len(self.grid)
                        self._render()  # SOLO HOLD
                        moved = True
                        time.sleep(HOLD_REPEAT)
                    else:
                        time.sleep(0.01)

                # TAP → abajo
                if not moved:
                    self.cursor_index = (self.cursor_index + self.cols) % len(self.grid)

                self.last_grid_render = None

            # -------- ENTER --------
            elif btns["enter"]:
                t0 = time.time()
                while read_buttons()["enter"]:
                    time.sleep(0.01)

                if time.time() - t0 >= HOLD_THRESHOLD:
                    action = self._show_action_menu()
                    if self._handle_action(action):
                        return
                else:
                    val = self.grid[self.cursor_index]
                    self._handle_action(val)

                self.last_grid_render = None

            time.sleep(REPEAT_DELAY)
