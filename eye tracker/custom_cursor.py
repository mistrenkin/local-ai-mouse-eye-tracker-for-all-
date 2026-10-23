from talon import Module, ctrl

mod = Module()

@mod.action_class
class Actions:
    def custom_cursor_move(x: float, y: float):
        """Triggers a hardware mouse click based on the specified type."""
        # map readable text to Talon button codes (0 = left, 1 = right)
        button_code = 1 if button_type == "right" else 0

        # execute the click at thetactive cursor position
        ctrl.mouse_click(button_code, hold=16000)
        