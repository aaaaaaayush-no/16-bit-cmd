"""
DOS-style command-line interface using prompt_toolkit.

Provides the authentic DEBUG.COM experience: black background, green/amber
monospace text, "-" prompt, with output scrolling upward exactly like the
original DOS debugger.
"""

import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

from .commands import DebugCommands

# DOS-style colour scheme
STYLE_GREEN = Style.from_dict({
    "prompt": "#00ff00",
    "": "#00ff00 bg:#000000",
    "output": "#00ff00",
})

STYLE_AMBER = Style.from_dict({
    "prompt": "#ffbf00",
    "": "#ffbf00 bg:#000000",
    "output": "#ffbf00",
})


class DebugCLI:
    """Interactive CLI replicating the DOS DEBUG.COM interface."""

    def __init__(self, filename=None, color="green"):
        self.debug = DebugCommands()
        self._style = STYLE_GREEN if color == "green" else STYLE_AMBER
        self._session = PromptSession(style=self._style)
        self._reg_prompt_name = None  # Set when R <reg> needs a value

        # If a filename was provided on the command line, load it
        if filename:
            self.debug.cmd_name(filename)
            result = self.debug.cmd_load("")
            for line in result:
                self._print(line)

    def _print(self, text):
        """Print text in the DOS style."""
        print(text)

    def _get_prompt(self):
        """Return the current prompt string."""
        if self.debug.assembling:
            return self.debug.get_asm_prompt()
        if self._reg_prompt_name:
            return ":"
        return "-"

    def run(self):
        """Main input loop."""
        while self.debug.running:
            try:
                prompt_text = self._get_prompt()
                line = self._session.prompt(prompt_text)
            except (EOFError, KeyboardInterrupt):
                break

            # Handle register value input
            if self._reg_prompt_name:
                reg = self._reg_prompt_name
                self._reg_prompt_name = None
                line = line.strip()
                if line:
                    try:
                        if reg == "F":
                            self.debug.set_flags_from_string(line)
                        else:
                            self.debug.set_register_value(reg, line)
                    except (ValueError, OverflowError):
                        self._print("Error")
                continue

            # Execute the command
            result = self.debug.execute(line)

            # Check if this was a Register command that needs follow-up input
            if result and not self.debug.assembling:
                cmd = line.strip()
                if cmd and cmd[0].upper() == "R" and len(cmd.strip()) > 1:
                    reg_name = cmd[1:].strip().upper()
                    if reg_name == "F":
                        # Print flags line, then prompt for new flags
                        self._print(result[0])
                        self._reg_prompt_name = "F"
                        continue
                    elif reg_name in [
                        "AX", "BX", "CX", "DX", "SP", "BP", "SI", "DI",
                        "DS", "ES", "SS", "CS", "IP",
                    ]:
                        # Print current value, then prompt for new value
                        self._print(result[0])
                        self._reg_prompt_name = reg_name
                        continue

            for line_out in result:
                self._print(line_out)


def main():
    """Entry point for the DEBUG replica."""
    import argparse

    parser = argparse.ArgumentParser(
        description="16-bit DEBUG.COM replica - an authentic 8086 debugger"
    )
    parser.add_argument(
        "filename", nargs="?", default=None,
        help="File to load (.COM, .EXE, or binary)"
    )
    parser.add_argument(
        "--color", choices=["green", "amber"], default="green",
        help="Text colour scheme (default: green)"
    )
    args = parser.parse_args()

    cli = DebugCLI(filename=args.filename, color=args.color)
    cli.run()
