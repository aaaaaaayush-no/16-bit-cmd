"""
Disassembler module using Capstone for 16-bit x86 disassembly.

Translates machine code bytes into human-readable assembly instructions,
used by the U (unassemble) command in DEBUG.

Output is formatted to match original DEBUG.COM style: plain hex values
without 0x prefixes, uppercase, and fixed-width columns.
"""

import re

from capstone import Cs, CS_ARCH_X86, CS_MODE_16


def _clean_operand(op_str):
    """
    Convert Capstone operand output to DEBUG.COM style.

    Removes '0x' prefixes and cleans up formatting to match the original
    DEBUG output (e.g., '0x1234' -> '1234', 'byte ptr' -> 'BYTE PTR').
    """
    # Remove 0x/0X prefix from hex numbers
    cleaned = re.sub(r'0[xX]([0-9A-Fa-f]+)', r'\1', op_str)
    return cleaned.upper()


class Disassembler:
    """16-bit x86 disassembler using Capstone."""

    def __init__(self):
        self._cs = Cs(CS_ARCH_X86, CS_MODE_16)

    def disassemble(self, data, address=0, count=0):
        """
        Disassemble binary data into instructions.

        Args:
            data: Bytes to disassemble
            address: Starting address for display
            count: Maximum number of instructions (0 = all)

        Returns:
            List of (address, size, mnemonic, op_str, raw_bytes) tuples
        """
        results = []
        for insn in self._cs.disasm(data, address):
            raw = data[insn.address - address:insn.address - address + insn.size]
            results.append((
                insn.address,
                insn.size,
                insn.mnemonic.upper(),
                _clean_operand(insn.op_str),
                raw,
            ))
            if count and len(results) >= count:
                break
        return results

    def disassemble_one(self, data, address=0):
        """Disassemble a single instruction."""
        results = self.disassemble(data, address, count=1)
        if results:
            return results[0]
        return None

    def format_instruction(self, segment, offset, data, max_bytes=16):
        """
        Format a disassembled instruction in DEBUG style.

        Returns: (formatted_string, instruction_size)
        Example: "073F:0100 B83412        MOV     AX,1234"
        """
        result = self.disassemble_one(data, offset)
        if result is None:
            # If disassembly fails, show as DB
            byte_val = data[0] if data else 0
            line = (f"{segment:04X}:{offset:04X} {byte_val:02X}"
                    + " " * 14 + f"DB      {byte_val:02X}")
            return line, 1

        addr, size, mnemonic, op_str, raw = result
        hex_bytes = "".join(f"{b:02X}" for b in raw)
        # Pad hex bytes to fixed width (like original DEBUG)
        hex_padded = f"{hex_bytes:<14s}"

        if op_str:
            line = f"{segment:04X}:{offset:04X} {hex_padded}{mnemonic:<8s}{op_str}"
        else:
            line = f"{segment:04X}:{offset:04X} {hex_padded}{mnemonic}"
        return line, size
