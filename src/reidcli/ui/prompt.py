"""Persistent chat input box (prompt_toolkit).

A Claude-Code-style rounded input box pinned at the bottom of the terminal:

    ╭────────────────────────────────────────────╮
    │ › take a full look at the readme            │
    ╰────────────────────────────────────────────╯
      balanced · gpt-5-5 · 1 tasks

Rendered as an inline Application (not full-screen), so AI output scrolls above
and native scrollback is preserved. The box erases on Enter; the REPL then echoes
the submitted line, so history stays clean instead of stacking boxes. Real line
editing + up/down history included. Falls back to a plain prompt with no TTY.
"""
from __future__ import annotations

import sys
from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.styles import Style

from reidcli.ui.theme import APP_NAME

# Map the red theme into prompt_toolkit style classes.
_STYLE = Style.from_dict(
    {
        "box": "#ff5f5f",            # rounded border, brand red
        "caret": "#ff5f5f bold",
        "status.brand": "#ff5f5f bold",
        "status.mode": "#ffd75f bold",
        "status.dim": "#9e9e9e",
        "status.sep": "#6c6c6c",
    }
)

# Status snapshot for the line under the box: (mode, model, task_count).
StatusFn = Callable[[], "tuple[str, str, int]"]


class ChatBar:
    """A persistent rounded input box with a status line beneath it."""

    def __init__(self, status_fn: StatusFn) -> None:
        self._status_fn = status_fn
        self._interactive = bool(getattr(sys.stdin, "isatty", lambda: False)())
        self._history = InMemoryHistory()

    def _status_fragments(self):  # type: ignore[no-untyped-def]
        mode, model, tasks = self._status_fn()
        sep = ("class:status.sep", "  ·  ")
        return [
            ("class:status.brand", f"  {APP_NAME}"),
            sep,
            ("class:status.mode", mode),
            sep,
            ("class:status.dim", model),
            sep,
            ("class:status.dim", f"{tasks} tasks"),
        ]

    def _build_app(self, *, input=None, output=None) -> Application:  # type: ignore[no-untyped-def]
        buf = Buffer(history=self._history, multiline=False)

        kb = KeyBindings()

        @kb.add("enter")
        def _(event) -> None:  # type: ignore[no-untyped-def]
            event.app.exit(result=buf.text)

        @kb.add("c-c")
        def _(event) -> None:  # type: ignore[no-untyped-def]
            event.app.exit(exception=KeyboardInterrupt)

        @kb.add("c-d")
        def _(event) -> None:  # type: ignore[no-untyped-def]
            event.app.exit(exception=EOFError)

        def corner(ch: str) -> Window:
            return Window(FormattedTextControl([("class:box", ch)]), width=1, height=1)

        def hline() -> Window:
            return Window(char="─", style="class:box", height=1)

        input_window = Window(BufferControl(buffer=buf), wrap_lines=False, height=1)

        root = HSplit(
            [
                VSplit([corner("╭"), hline(), corner("╮")], height=1),
                VSplit(
                    [
                        Window(FormattedTextControl([("class:box", "│")]), width=1, height=1),
                        Window(FormattedTextControl([("class:caret", " › ")]), width=3, height=1),
                        input_window,
                        Window(FormattedTextControl([("class:box", "│")]), width=1, height=1),
                    ],
                    height=1,
                ),
                VSplit([corner("╰"), hline(), corner("╯")], height=1),
                Window(FormattedTextControl(self._status_fragments), height=1),
            ]
        )

        return Application(
            layout=Layout(root, focused_element=input_window),
            key_bindings=kb,
            style=_STYLE,
            full_screen=False,
            erase_when_done=True,
            mouse_support=False,
            input=input,
            output=output,
        )

    def ask(self) -> str:
        """Read one line. Raises EOFError/KeyboardInterrupt like input()."""
        if not self._interactive:
            return input("> ")
        return self._build_app().run()
