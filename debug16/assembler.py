"""
Assembler module using Keystone Engine for 16-bit x86 assembly.

Translates assembly mnemonics into machine code bytes for the 8086 processor,
used by the A (assemble) command in DEBUG.

In original DEBUG.COM, all numeric literals are hexadecimal by default.
This module preprocesses instructions to convert bare hex numbers to the
0x-prefixed format that Keystone Engine expects.
"""

import re

from keystone import Ks, KS_ARCH_X86, KS_MODE_16, KsError

# 8086 register names that should NOT be treated as hex numbers
_REGISTER_NAMES = {
    "AX", "BX", "CX", "DX", "SP", "BP", "SI", "DI",
    "DS", "ES", "SS", "CS", "IP",
    "AH", "AL", "BH", "BL", "CH", "CL", "DH", "DL",
    "CS", "DS", "ES", "SS",
}

# Pattern matching bare hex numbers (1-4 hex digits, not already prefixed)
_HEX_TOKEN = re.compile(r'\b([0-9][0-9A-Fa-f]*)\b')


def _convert_hex_literals(instruction):
    """
    Convert bare hex numbers in DEBUG-style assembly to 0x-prefixed format.

    In DEBUG.COM, all numbers are hex: 'MOV AX, 1234' means 0x1234.
    Keystone needs the 0x prefix, so we add it to bare numeric tokens.
    Numbers already ending in 'h' or starting with '0x' are left unchanged.
    """
    # If user already uses h suffix or 0x prefix, leave it alone
    if "0x" in instruction.lower() or "0X" in instruction:
        return instruction

    def replace_token(match):
        token = match.group(1)
        # Don't convert register names
        if token.upper() in _REGISTER_NAMES:
            return token
        # Check if it's a valid hex number
        try:
            int(token, 16)
            # If it ends with 'h'/'H', Keystone already understands it
            if token.upper().endswith("H"):
                return token
            return "0x" + token
        except ValueError:
            return token

    return _HEX_TOKEN.sub(replace_token, instruction)


class Assembler:
    """16-bit x86 assembler using Keystone Engine."""

    def __init__(self):
        self._ks = Ks(KS_ARCH_X86, KS_MODE_16)

    def assemble(self, instruction, address=0):
        """
        Assemble a single instruction.

        Args:
            instruction: Assembly instruction string (e.g., "MOV AX, 1234")
            address: Address at which the instruction will be placed

        Returns:
            Tuple of (bytes, instruction_count) or raises ValueError on error
        """
        # Convert DEBUG-style hex literals to 0x format for Keystone
        converted = _convert_hex_literals(instruction)
        try:
            encoding, count = self._ks.asm(converted, address)
            if encoding is None:
                raise ValueError(f"Could not assemble: {instruction}")
            return bytes(encoding), count
        except KsError as e:
            raise ValueError(str(e))

    def assemble_to_bytes(self, instruction, address=0):
        """Assemble and return just the bytes."""
        data, _ = self.assemble(instruction, address)
        return data
