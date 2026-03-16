"""
Command handler implementing all DEBUG.COM commands.

Parses user input and dispatches to the appropriate handler,
producing output that matches the original DEBUG.COM format exactly.

Supported commands:
  A [address]           - Assemble
  C range address       - Compare
  D [range]             - Dump memory
  E address [list]      - Enter data
  F range list          - Fill memory
  G [=address] [addrs]  - Go (execute)
  H value1 value2       - Hex arithmetic
  I port                - Input from port
  L [address]           - Load file
  M range address       - Move memory
  N filename            - Name file
  O port byte           - Output to port
  P [=address] [count]  - Proceed (step over)
  Q                     - Quit
  R [register]          - Display/modify registers
  S range list          - Search memory
  T [=address] [count]  - Trace (single step)
  U [range]             - Unassemble
  W [address]           - Write file
"""

import os

from .cpu import (
    CPU, DEFAULT_CS, DEFAULT_DS, DEFAULT_IP,
    FLAG_NAMES, SETTABLE_REGS,
)
from .assembler import Assembler
from .disassembler import Disassembler


def _parse_hex(s):
    """Parse a hex string, return int. Raises ValueError on failure."""
    return int(s, 16)


def _parse_address(s, default_seg=None):
    """
    Parse a segment:offset address or plain offset.
    Returns (segment, offset).
    """
    s = s.strip()
    if ":" in s:
        parts = s.split(":", 1)
        return _parse_hex(parts[0]), _parse_hex(parts[1])
    else:
        offset = _parse_hex(s)
        return default_seg, offset


def _parse_range(args, default_seg=None, default_length=128):
    """
    Parse a DEBUG range specification.
    Formats:
      address              -> (seg, start, start + default_length - 1)
      address L length     -> (seg, start, start + length - 1)
      address address      -> (seg, start, end)

    Returns (segment, start_offset, end_offset)
    """
    parts = args.strip().split()
    if not parts:
        return default_seg, 0, default_length - 1

    seg, start = _parse_address(parts[0], default_seg)

    if len(parts) >= 3 and parts[1].upper() == "L":
        length = _parse_hex(parts[2])
        return seg, start, start + length - 1
    elif len(parts) >= 2 and parts[1].upper() != "L":
        try:
            end = _parse_hex(parts[1])
            return seg, start, end
        except ValueError:
            pass

    return seg, start, start + default_length - 1


def _parse_byte_list(parts):
    """Parse a list of hex bytes and/or quoted strings."""
    result = []
    i = 0
    while i < len(parts):
        token = parts[i]
        if token.startswith('"') or token.startswith("'"):
            quote_char = token[0]
            # Collect until closing quote
            combined = token[1:]
            while i < len(parts) and not combined.endswith(quote_char):
                i += 1
                if i < len(parts):
                    combined += " " + parts[i]
            if combined.endswith(quote_char):
                combined = combined[:-1]
            for ch in combined:
                result.append(ord(ch) & 0xFF)
        else:
            result.append(_parse_hex(token) & 0xFF)
        i += 1
    return result


class DebugCommands:
    """Implements all DEBUG.COM commands."""

    def __init__(self):
        self.cpu = CPU()
        self.asm = Assembler()
        self.disasm = Disassembler()
        # Current dump/unassemble address tracking
        self._dump_segment = DEFAULT_DS
        self._dump_offset = DEFAULT_IP
        self._unasm_segment = DEFAULT_CS
        self._unasm_offset = DEFAULT_IP
        self._asm_segment = DEFAULT_CS
        self._asm_offset = DEFAULT_IP
        # Named file
        self._filename = ""
        # Running flag
        self.running = True
        # Assemble mode flag
        self.assembling = False

    def execute(self, line):
        """
        Parse and execute a DEBUG command line.
        Returns list of output strings.
        """
        line = line.strip()

        # If in assemble mode, handle assembly input (including empty line to exit)
        if self.assembling:
            return self._handle_asm_input(line)

        if not line:
            return []

        cmd = line[0].upper()
        args = line[1:].strip()

        dispatch = {
            "A": self.cmd_assemble,
            "C": self.cmd_compare,
            "D": self.cmd_dump,
            "E": self.cmd_enter,
            "F": self.cmd_fill,
            "G": self.cmd_go,
            "H": self.cmd_hex,
            "I": self.cmd_input_port,
            "L": self.cmd_load,
            "M": self.cmd_move,
            "N": self.cmd_name,
            "O": self.cmd_output_port,
            "P": self.cmd_proceed,
            "Q": self.cmd_quit,
            "R": self.cmd_register,
            "S": self.cmd_search,
            "T": self.cmd_trace,
            "U": self.cmd_unassemble,
            "W": self.cmd_write,
            "?": self.cmd_help,
        }

        handler = dispatch.get(cmd)
        if handler is None:
            return ["Error"]

        try:
            return handler(args)
        except (ValueError, IndexError, OverflowError):
            return ["Error"]

    # ── A (Assemble) ─────────────────────────────────────────────────

    def cmd_assemble(self, args):
        """Start assembly mode at the specified address."""
        if args:
            seg, off = _parse_address(args, self.cpu.get_reg("CS"))
            if seg is not None:
                self._asm_segment = seg
            self._asm_offset = off

        self.assembling = True
        return []

    def get_asm_prompt(self):
        """Return the current assembly prompt like '073F:0100 '."""
        return f"{self._asm_segment:04X}:{self._asm_offset:04X} "

    def _handle_asm_input(self, line):
        """Handle input while in assemble mode."""
        if not line.strip():
            self.assembling = False
            return []

        try:
            data = self.asm.assemble_to_bytes(line, self._asm_offset)
            addr = self.cpu.linear_address(self._asm_segment, self._asm_offset)
            self.cpu.write_memory(addr, data)
            self._asm_offset += len(data)
            return []
        except ValueError as e:
            return [f"^ Error: {e}"]

    # ── C (Compare) ──────────────────────────────────────────────────

    def cmd_compare(self, args):
        """Compare two blocks of memory."""
        parts = args.split()
        if len(parts) < 2:
            return ["Error"]

        # Parse: C range address
        # Try to find the destination address (last token)
        dest_str = parts[-1]
        range_str = " ".join(parts[:-1])

        ds = self.cpu.get_reg("DS")
        seg, start, end = _parse_range(range_str, ds)
        if seg is None:
            seg = ds

        dest_seg, dest_off = _parse_address(dest_str, ds)
        if dest_seg is None:
            dest_seg = ds

        output = []
        length = end - start + 1
        for i in range(length):
            b1 = self.cpu.read_byte(seg, (start + i) & 0xFFFF)
            b2 = self.cpu.read_byte(dest_seg, (dest_off + i) & 0xFFFF)
            if b1 != b2:
                output.append(
                    f"{seg:04X}:{(start + i) & 0xFFFF:04X}  {b1:02X}  "
                    f"{b2:02X}  {dest_seg:04X}:{(dest_off + i) & 0xFFFF:04X}"
                )
        return output

    # ── D (Dump) ─────────────────────────────────────────────────────

    def cmd_dump(self, args):
        """Dump memory in hex + ASCII format."""
        ds = self.cpu.get_reg("DS")

        if args:
            seg, start, end = _parse_range(args, ds)
            if seg is None:
                seg = ds
            self._dump_segment = seg
        else:
            seg = self._dump_segment
            start = self._dump_offset
            end = start + 127

        output = []
        addr = start
        while addr <= end:
            # Align to 16-byte boundary for display
            row_start = addr & 0xFFF0 if addr == start else addr
            if addr == start:
                row_start = addr

            row_end = min(((addr | 0xF)), end)
            line_offset = addr & 0xF

            hex_part = ""
            ascii_part = ""

            # Build the full 16-byte row
            row_base = addr & 0xFFF0
            for col in range(16):
                current = row_base + col
                if current < start or current > end:
                    hex_part += "   "
                    ascii_part += " "
                else:
                    b = self.cpu.read_byte(seg, current & 0xFFFF)
                    hex_part += f"{b:02X} "
                    ascii_part += chr(b) if 0x20 <= b < 0x7F else "."

                if col == 7:
                    hex_part += "-" if (start <= row_base + 7 <= end and
                                        start <= row_base + 8 <= end) else " "

            line = f"{seg:04X}:{row_base:04X}  {hex_part} {ascii_part}"
            output.append(line)
            addr = row_base + 16

        self._dump_offset = (end + 1) & 0xFFFF
        return output

    # ── E (Enter) ─────────────────────────────────────────────────────

    def cmd_enter(self, args):
        """Enter data into memory."""
        parts = args.split(None, 1)
        if not parts:
            return ["Error"]

        ds = self.cpu.get_reg("DS")
        seg, off = _parse_address(parts[0], ds)
        if seg is None:
            seg = ds

        if len(parts) > 1:
            # Direct entry: E address byte-list
            byte_tokens = parts[1].split()
            byte_list = _parse_byte_list(byte_tokens)
            for i, b in enumerate(byte_list):
                self.cpu.write_byte(seg, (off + i) & 0xFFFF, b)
            return []
        else:
            # Interactive entry not implemented in batch mode
            # Show current byte
            b = self.cpu.read_byte(seg, off)
            return [f"{seg:04X}:{off:04X}  {b:02X}."]

    # ── F (Fill) ──────────────────────────────────────────────────────

    def cmd_fill(self, args):
        """Fill a memory range with a byte pattern."""
        parts = args.split()
        if len(parts) < 2:
            return ["Error"]

        ds = self.cpu.get_reg("DS")

        # Find where the range ends and the fill list begins
        # The fill list starts after the range specification
        # Range can be: addr addr, addr L len, or just addr
        # We need to parse this carefully

        # Try parsing with L syntax first
        range_end_idx = None
        for i, p in enumerate(parts):
            if p.upper() == "L" and i >= 1:
                range_end_idx = i + 1
                break

        if range_end_idx is None:
            # Check if second token is an address (part of range)
            # or a fill byte. Heuristic: if there are 3+ tokens and
            # second looks like part of a range, treat first two as range
            if len(parts) >= 3:
                try:
                    _parse_hex(parts[1])
                    range_end_idx = 1
                except ValueError:
                    range_end_idx = 0
            else:
                return ["Error"]

        range_str = " ".join(parts[:range_end_idx + 1])
        fill_tokens = parts[range_end_idx + 1:]

        if not fill_tokens:
            return ["Error"]

        seg, start, end = _parse_range(range_str, ds)
        if seg is None:
            seg = ds

        fill_bytes = _parse_byte_list(fill_tokens)
        if not fill_bytes:
            return ["Error"]

        length = end - start + 1
        for i in range(length):
            b = fill_bytes[i % len(fill_bytes)]
            self.cpu.write_byte(seg, (start + i) & 0xFFFF, b)

        return []

    # ── G (Go) ────────────────────────────────────────────────────────

    def cmd_go(self, args):
        """Execute program (Go command)."""
        parts = args.split()
        cs = self.cpu.get_reg("CS")

        start_seg = None
        start_off = None
        stop_seg = None
        stop_off = None

        idx = 0
        # Parse =address for start
        if parts and parts[0].startswith("="):
            addr_str = parts[0][1:]
            start_seg, start_off = _parse_address(addr_str, cs)
            if start_seg is None:
                start_seg = cs
            idx = 1

        # Parse breakpoint addresses
        if idx < len(parts):
            stop_seg, stop_off = _parse_address(parts[idx], cs)
            if stop_seg is None:
                stop_seg = cs

        self.cpu.execute(start_seg, start_off, stop_seg, stop_off)

        output = []
        if self.cpu.halted and self.cpu.int_num is not None:
            if self.cpu.int_num == 0x20:
                output.append("")
                output.append("Program terminated normally")
        output.append("")
        output.append(self.cpu.register_dump())
        # Show instruction at current CS:IP
        cs_val = self.cpu.get_reg("CS")
        ip_val = self.cpu.get_reg("IP")
        addr = self.cpu.linear_address(cs_val, ip_val)
        data = self.cpu.read_memory(addr, 16)
        line, _ = self.disasm.format_instruction(cs_val, ip_val, data)
        output.append(line)
        return output

    # ── H (Hex) ───────────────────────────────────────────────────────

    def cmd_hex(self, args):
        """Hex arithmetic: display sum and difference of two values."""
        parts = args.split()
        if len(parts) < 2:
            return ["Error"]

        val1 = _parse_hex(parts[0])
        val2 = _parse_hex(parts[1])

        sum_val = (val1 + val2) & 0xFFFF
        diff_val = (val1 - val2) & 0xFFFF

        return [f"{sum_val:04X}  {diff_val:04X}"]

    # ── I (Input) ─────────────────────────────────────────────────────

    def cmd_input_port(self, args):
        """Input from port (simulated, returns FF)."""
        parts = args.split()
        if not parts:
            return ["Error"]
        _parse_hex(parts[0])  # Validate port number
        return ["FF"]

    # ── L (Load) ──────────────────────────────────────────────────────

    def cmd_load(self, args):
        """Load a file into memory."""
        parts = args.split()
        ds = self.cpu.get_reg("DS")

        if parts:
            seg, off = _parse_address(parts[0], ds)
            if seg is None:
                seg = ds
        else:
            seg = self.cpu.get_reg("CS")
            off = 0x0100  # Default load address for .COM files

        if not self._filename:
            return ["File not found"]

        try:
            with open(self._filename, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            return ["File not found"]
        except OSError:
            return ["File not found"]

        # Write data to memory
        addr = self.cpu.linear_address(seg, off)
        self.cpu.write_memory(addr, data)

        # Set BX:CX to file size (as original DEBUG does)
        size = len(data)
        self.cpu.set_reg("CX", size & 0xFFFF)
        self.cpu.set_reg("BX", (size >> 16) & 0xFFFF)

        return []

    # ── M (Move) ──────────────────────────────────────────────────────

    def cmd_move(self, args):
        """Move (copy) a block of memory."""
        parts = args.split()
        if len(parts) < 2:
            return ["Error"]

        ds = self.cpu.get_reg("DS")
        dest_str = parts[-1]
        range_str = " ".join(parts[:-1])

        seg, start, end = _parse_range(range_str, ds)
        if seg is None:
            seg = ds

        dest_seg, dest_off = _parse_address(dest_str, ds)
        if dest_seg is None:
            dest_seg = ds

        length = end - start + 1
        # Read source data
        data = []
        for i in range(length):
            data.append(self.cpu.read_byte(seg, (start + i) & 0xFFFF))

        # Handle overlapping regions by direction
        if dest_off > start:
            # Copy backwards
            for i in range(length - 1, -1, -1):
                self.cpu.write_byte(
                    dest_seg, (dest_off + i) & 0xFFFF, data[i]
                )
        else:
            for i in range(length):
                self.cpu.write_byte(
                    dest_seg, (dest_off + i) & 0xFFFF, data[i]
                )

        return []

    # ── N (Name) ──────────────────────────────────────────────────────

    def cmd_name(self, args):
        """Set the filename for Load/Write commands."""
        self._filename = args.strip()
        return []

    # ── O (Output) ────────────────────────────────────────────────────

    def cmd_output_port(self, args):
        """Output to port (simulated, no-op)."""
        parts = args.split()
        if len(parts) < 2:
            return ["Error"]
        _parse_hex(parts[0])  # Validate port
        _parse_hex(parts[1])  # Validate byte
        return []

    # ── P (Proceed) ───────────────────────────────────────────────────

    def cmd_proceed(self, args):
        """Proceed (step over CALL/INT/REP, like T but skips subroutines)."""
        parts = args.split()
        cs = self.cpu.get_reg("CS")
        ip = self.cpu.get_reg("IP")
        count = 1

        idx = 0
        if parts and parts[0].startswith("="):
            addr_str = parts[0][1:]
            seg, off = _parse_address(addr_str, cs)
            if seg is not None:
                self.cpu.set_reg("CS", seg)
            self.cpu.set_reg("IP", off)
            cs = self.cpu.get_reg("CS")
            ip = self.cpu.get_reg("IP")
            idx = 1

        if idx < len(parts):
            count = _parse_hex(parts[idx])

        output = []
        for _ in range(count):
            cs = self.cpu.get_reg("CS")
            ip = self.cpu.get_reg("IP")
            addr = self.cpu.linear_address(cs, ip)
            data = self.cpu.read_memory(addr, 16)

            # Check if current instruction is CALL, INT, or REP prefix
            opcode = data[0]
            skip = False
            skip_size = 0

            if opcode == 0xE8:      # CALL near
                skip = True
                skip_size = 3
            elif opcode == 0x9A:    # CALL far
                skip = True
                skip_size = 5
            elif opcode == 0xCD:    # INT
                skip = True
                skip_size = 2
            elif opcode == 0xCC:    # INT 3
                skip = True
                skip_size = 1
            elif opcode in (0xF2, 0xF3):  # REP/REPZ/REPNZ
                skip = True
                # Need to figure out size of REP + instruction
                insn = self.disasm.disassemble_one(data, ip)
                if insn:
                    skip_size = insn[1]
                else:
                    skip_size = 2
            elif opcode == 0xFF:
                # CALL indirect - check ModR/M byte
                if len(data) > 1:
                    modrm = data[1]
                    reg_field = (modrm >> 3) & 7
                    if reg_field in (2, 3):  # CALL near/far indirect
                        skip = True
                        insn = self.disasm.disassemble_one(data, ip)
                        if insn:
                            skip_size = insn[1]
                        else:
                            skip_size = 2

            if skip and skip_size > 0:
                # Set breakpoint after the instruction and run
                next_ip = (ip + skip_size) & 0xFFFF
                self.cpu.execute(cs, ip, cs, next_ip)
            else:
                # Normal single-step
                self.cpu.execute(count=1)

            if self.cpu.halted:
                break

        # Show register state
        output.append("")
        output.append(self.cpu.register_dump())
        cs_val = self.cpu.get_reg("CS")
        ip_val = self.cpu.get_reg("IP")
        addr = self.cpu.linear_address(cs_val, ip_val)
        data = self.cpu.read_memory(addr, 16)
        line, _ = self.disasm.format_instruction(cs_val, ip_val, data)
        output.append(line)
        return output

    # ── Q (Quit) ──────────────────────────────────────────────────────

    def cmd_quit(self, args):
        """Quit the debugger."""
        self.running = False
        return []

    # ── R (Register) ──────────────────────────────────────────────────

    def cmd_register(self, args):
        """Display or modify registers."""
        if not args:
            # Display all registers + current instruction
            output = [self.cpu.register_dump()]
            cs = self.cpu.get_reg("CS")
            ip = self.cpu.get_reg("IP")
            addr = self.cpu.linear_address(cs, ip)
            data = self.cpu.read_memory(addr, 16)
            line, _ = self.disasm.format_instruction(cs, ip, data)
            output.append(line)
            return output

        reg_name = args.strip().upper()

        if reg_name == "F":
            # Display flags and prompt for new flag values
            flags_str = self.flags_string_for_prompt()
            return [flags_str]

        if reg_name in SETTABLE_REGS:
            val = self.cpu.get_reg(reg_name)
            return [f"{reg_name} {val:04X}", ":"]
        else:
            return ["br"]

    def flags_string_for_prompt(self):
        """Return flags string for the R F command."""
        return self.cpu.flags_string() + " -"

    def set_register_value(self, reg_name, value_str):
        """Set a register value from user input (for R command interaction)."""
        value = _parse_hex(value_str)
        self.cpu.set_reg(reg_name, value)

    def set_flags_from_string(self, flags_str):
        """Set individual flags from a string like 'OV ZR CY'."""
        tokens = flags_str.upper().split()
        for token in tokens:
            if token in FLAG_NAMES:
                bit_pos, set_val = FLAG_NAMES[token]
                self.cpu.set_flag_bit(bit_pos, set_val)

    # ── S (Search) ────────────────────────────────────────────────────

    def cmd_search(self, args):
        """Search memory for a byte pattern."""
        parts = args.split()
        if len(parts) < 2:
            return ["Error"]

        ds = self.cpu.get_reg("DS")

        # Find where range ends and search pattern begins
        # Heuristic: first two or three tokens are the range, rest is pattern
        range_end_idx = 1
        for i, p in enumerate(parts):
            if p.upper() == "L" and i >= 1:
                range_end_idx = i + 1
                break
            if i >= 1:
                range_end_idx = i
                break

        range_str = " ".join(parts[:range_end_idx + 1])
        search_tokens = parts[range_end_idx + 1:]

        if not search_tokens:
            return ["Error"]

        seg, start, end = _parse_range(range_str, ds)
        if seg is None:
            seg = ds

        search_bytes = _parse_byte_list(search_tokens)
        if not search_bytes:
            return ["Error"]

        output = []
        length = end - start + 1
        pattern_len = len(search_bytes)

        for i in range(length - pattern_len + 1):
            match = True
            for j in range(pattern_len):
                b = self.cpu.read_byte(seg, (start + i + j) & 0xFFFF)
                if b != search_bytes[j]:
                    match = False
                    break
            if match:
                output.append(f"{seg:04X}:{(start + i) & 0xFFFF:04X}")

        return output

    # ── T (Trace) ─────────────────────────────────────────────────────

    def cmd_trace(self, args):
        """Trace (single-step) one or more instructions."""
        parts = args.split()
        count = 1
        cs = self.cpu.get_reg("CS")

        idx = 0
        if parts and parts[0].startswith("="):
            addr_str = parts[0][1:]
            seg, off = _parse_address(addr_str, cs)
            if seg is not None:
                self.cpu.set_reg("CS", seg)
            self.cpu.set_reg("IP", off)
            idx = 1

        if idx < len(parts):
            count = _parse_hex(parts[idx])

        output = []
        for _ in range(count):
            self.cpu.execute(count=1)
            if self.cpu.halted:
                break

            # Show register state after each step
            output.append("")
            output.append(self.cpu.register_dump())
            cs_val = self.cpu.get_reg("CS")
            ip_val = self.cpu.get_reg("IP")
            addr = self.cpu.linear_address(cs_val, ip_val)
            data = self.cpu.read_memory(addr, 16)
            line, _ = self.disasm.format_instruction(cs_val, ip_val, data)
            output.append(line)

        return output

    # ── U (Unassemble) ───────────────────────────────────────────────

    def cmd_unassemble(self, args):
        """Unassemble (disassemble) memory."""
        cs = self.cpu.get_reg("CS")

        if args:
            seg, start, end = _parse_range(args, cs, default_length=32)
            if seg is None:
                seg = cs
            self._unasm_segment = seg
            self._unasm_offset = start
        else:
            seg = self._unasm_segment
            start = self._unasm_offset
            end = start + 31

        output = []
        offset = start
        while offset <= end:
            addr = self.cpu.linear_address(seg, offset)
            data = self.cpu.read_memory(addr, 16)
            line, size = self.disasm.format_instruction(seg, offset, data)
            output.append(line)
            offset += size

        self._unasm_segment = seg
        self._unasm_offset = offset & 0xFFFF
        return output

    # ── W (Write) ─────────────────────────────────────────────────────

    def cmd_write(self, args):
        """Write memory to a file."""
        parts = args.split()
        cs = self.cpu.get_reg("CS")

        if parts:
            seg, off = _parse_address(parts[0], cs)
            if seg is None:
                seg = cs
        else:
            seg = self.cpu.get_reg("CS")
            off = 0x0100

        if not self._filename:
            return ["File not found"]

        # Get size from BX:CX
        bx = self.cpu.get_reg("BX")
        cx = self.cpu.get_reg("CX")
        size = (bx << 16) | cx

        if size == 0:
            return ["Error"]

        addr = self.cpu.linear_address(seg, off)
        data = self.cpu.read_memory(addr, size)

        try:
            with open(self._filename, "wb") as f:
                f.write(data)
        except OSError:
            return ["Error"]

        return [f"Writing {size:05X} bytes"]

    # ── ? (Help) ──────────────────────────────────────────────────────

    def cmd_help(self, args):
        """Display help (not in original DEBUG, but useful)."""
        return [
            "assemble     A [address]",
            "compare      C range address",
            "dump         D [range]",
            "enter        E address [list]",
            "fill         F range list",
            "go           G [=address] [addresses]",
            "hex          H value1 value2",
            "input        I port",
            "load         L [address]",
            "move         M range address",
            "name         N [pathname]",
            "output       O port byte",
            "proceed      P [=address] [number]",
            "quit         Q",
            "register     R [register]",
            "search       S range list",
            "trace        T [=address] [value]",
            "unassemble   U [range]",
            "write        W [address]",
        ]
