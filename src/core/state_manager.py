from collections.abc import Callable

from src.core.states import AssistantState


class StateManager:
    def __init__(self):
        self._state = AssistantState.IDLE
        self._listeners = []

    @property
    def state(self):
        return self._state

    def add_listener(
        self,
        listener: Callable[
            [AssistantState],
            None,
        ],
    ):
        self._listeners.append(listener)

    def change_to(
        self,
        new_state: AssistantState,
    ):
        if new_state == self._state:
            return

        old_state = self._state
        self._state = new_state

        print(
            f"状态变化："
            f"{old_state.value}"
            f" -> "
            f"{new_state.value}"
        )

        for listener in self._listeners:
            listener(new_state)