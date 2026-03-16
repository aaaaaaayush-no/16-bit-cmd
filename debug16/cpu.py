"""
CPU emulation module using Unicorn Engine for real 8086 16-bit real-mode.

Provides a wrapper around the Unicorn Engine that manages CPU state,
memory mapping, and instruction execution for authentic 8086 behaviour.
"""

from unicorn import (
    Uc, UC_ARCH_X86, UC_MODE_16,
    UC_HOOK_INTR, UC_HOOK_CODE,
    UcError,
)
from unicorn.x86_const import (
    UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,
    UC_X86_REG_SP, UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI,
    UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_CS,
    UC_X86_REG_IP, UC_X86_REG_FLAGS,
    UC_X86_REG_AH, UC_X86_REG_AL,
    UC_X86_REG_DL, UC_X86_REG_DH,
)

# Total 8086 address space: 1 MB
MEMORY_SIZE = 1024 * 1024  # 1 MB

# Default segment values matching original DEBUG.COM
DEFAULT_CS = 0x073F
DEFAULT_DS = 0x073F
DEFAULT_ES = 0x073F
DEFAULT_SS = 0x073F
DEFAULT_SP = 0xFFFE
DEFAULT_IP = 0x0100

# 8086 FLAGS bit positions
FLAG_CF = 0   # Carry
FLAG_PF = 2   # Parity
FLAG_AF = 4   # Auxiliary carry
FLAG_ZF = 6   # Zero
FLAG_SF = 7   # Sign
FLAG_TF = 8   # Trap
FLAG_IF = 9   # Interrupt enable
FLAG_DF = 10  # Direction
FLAG_OF = 11  # Overflow

# Map of flag bits to their DEBUG-style display strings
# Format: (bit_position, set_string, clear_string)
FLAGS_DISPLAY = [
    (FLAG_OF, "OV", "NV"),  # Overflow
    (FLAG_DF, "DN", "UP"),  # Direction
    (FLAG_IF, "EI", "DI"),  # Interrupt
    (FLAG_SF, "NG", "PL"),  # Sign
    (FLAG_ZF, "ZR", "NZ"),  # Zero
    (FLAG_AF, "AC", "NA"),  # Auxiliary carry
    (FLAG_PF, "PE", "PO"),  # Parity
    (FLAG_CF, "CY", "NC"),  # Carry
]

# Register name to Unicorn constant mapping
REG_MAP = {
    "AX": UC_X86_REG_AX, "BX": UC_X86_REG_BX,
    "CX": UC_X86_REG_CX, "DX": UC_X86_REG_DX,
    "SP": UC_X86_REG_SP, "BP": UC_X86_REG_BP,
    "SI": UC_X86_REG_SI, "DI": UC_X86_REG_DI,
    "DS": UC_X86_REG_DS, "ES": UC_X86_REG_ES,
    "SS": UC_X86_REG_SS, "CS": UC_X86_REG_CS,
    "IP": UC_X86_REG_IP,
}

# Registers that are valid for the R command to set
SETTABLE_REGS = [
    "AX", "BX", "CX", "DX", "SP", "BP", "SI", "DI",
    "DS", "ES", "SS", "CS", "IP",
]

# Flag name to (bit_position, set_code, clear_code) for flag toggle
FLAG_NAMES = {
    "OV": (FLAG_OF, True),  "NV": (FLAG_OF, False),
    "DN": (FLAG_DF, True),  "UP": (FLAG_DF, False),
    "EI": (FLAG_IF, True),  "DI": (FLAG_IF, False),
    "NG": (FLAG_SF, True),  "PL": (FLAG_SF, False),
    "ZR": (FLAG_ZF, True),  "NZ": (FLAG_ZF, False),
    "AC": (FLAG_AF, True),  "NA": (FLAG_AF, False),
    "PE": (FLAG_PF, True),  "PO": (FLAG_PF, False),
    "CY": (FLAG_CF, True),  "NC": (FLAG_CF, False),
}


class CPU:
    """8086 CPU emulator wrapping the Unicorn Engine."""

    def __init__(self):
        self._uc = Uc(UC_ARCH_X86, UC_MODE_16)
        # Map the full 1 MB address space
        self._uc.mem_map(0, MEMORY_SIZE)
        # Track whether execution was halted by an interrupt
        self._halted = False
        self._int_num = None
        self._stop_address = None
        self._single_step = False
        self._step_count = 0
        self._max_steps = 0
        # Hook for interrupts
        self._uc.hook_add(UC_HOOK_INTR, self._hook_interrupt)
        # Reset to default state
        self.reset()

    def reset(self):
        """Reset CPU to default DEBUG state."""
        self._uc.reg_write(UC_X86_REG_AX, 0x0000)
        self._uc.reg_write(UC_X86_REG_BX, 0x0000)
        self._uc.reg_write(UC_X86_REG_CX, 0x0000)
        self._uc.reg_write(UC_X86_REG_DX, 0x0000)
        self._uc.reg_write(UC_X86_REG_SP, DEFAULT_SP)
        self._uc.reg_write(UC_X86_REG_BP, 0x0000)
        self._uc.reg_write(UC_X86_REG_SI, 0x0000)
        self._uc.reg_write(UC_X86_REG_DI, 0x0000)
        self._uc.reg_write(UC_X86_REG_DS, DEFAULT_DS)
        self._uc.reg_write(UC_X86_REG_ES, DEFAULT_ES)
        self._uc.reg_write(UC_X86_REG_SS, DEFAULT_SS)
        self._uc.reg_write(UC_X86_REG_CS, DEFAULT_CS)
        self._uc.reg_write(UC_X86_REG_IP, DEFAULT_IP)
        self._uc.reg_write(UC_X86_REG_FLAGS, 0x7202)
        self._halted = False
        self._int_num = None

    def _hook_interrupt(self, uc, intno, user_data):
        """Handle CPU interrupts during emulation."""
        self._int_num = intno
        self._halted = True
        uc.emu_stop()

    def get_reg(self, name):
        """Get a register value by name."""
        name = name.upper()
        if name == "F" or name == "FLAGS":
            return self._uc.reg_read(UC_X86_REG_FLAGS)
        if name in REG_MAP:
            return self._uc.reg_read(REG_MAP[name])
        raise ValueError(f"Unknown register: {name}")

    def set_reg(self, name, value):
        """Set a register value by name."""
        name = name.upper()
        if name == "F" or name == "FLAGS":
            self._uc.reg_write(UC_X86_REG_FLAGS, value & 0xFFFF)
            return
        if name in REG_MAP:
            self._uc.reg_write(REG_MAP[name], value & 0xFFFF)
            return
        raise ValueError(f"Unknown register: {name}")

    def get_flags(self):
        """Get the FLAGS register value."""
        return self._uc.reg_read(UC_X86_REG_FLAGS)

    def set_flags(self, value):
        """Set the FLAGS register value."""
        self._uc.reg_write(UC_X86_REG_FLAGS, value & 0xFFFF)

    def get_flag_bit(self, bit):
        """Get a specific flag bit."""
        return (self.get_flags() >> bit) & 1

    def set_flag_bit(self, bit, value):
        """Set a specific flag bit."""
        flags = self.get_flags()
        if value:
            flags |= (1 << bit)
        else:
            flags &= ~(1 << bit)
        self.set_flags(flags)

    def flags_string(self):
        """Return flags in DEBUG display format: NV UP EI PL NZ NA PO NC"""
        flags = self.get_flags()
        parts = []
        for bit_pos, set_str, clr_str in FLAGS_DISPLAY:
            if (flags >> bit_pos) & 1:
                parts.append(set_str)
            else:
                parts.append(clr_str)
        return " ".join(parts)

    def linear_address(self, segment, offset):
        """Convert segment:offset to linear address."""
        return ((segment & 0xFFFF) << 4) + (offset & 0xFFFF)

    def read_memory(self, address, size):
        """Read bytes from memory at a linear address."""
        address = address & 0xFFFFF  # Wrap to 1 MB
        if address + size > MEMORY_SIZE:
            size = MEMORY_SIZE - address
        return bytes(self._uc.mem_read(address, size))

    def write_memory(self, address, data):
        """Write bytes to memory at a linear address."""
        address = address & 0xFFFFF
        self._uc.mem_write(address, bytes(data))

    def read_byte(self, segment, offset):
        """Read a single byte at segment:offset."""
        addr = self.linear_address(segment, offset)
        return self.read_memory(addr, 1)[0]

    def write_byte(self, segment, offset, value):
        """Write a single byte at segment:offset."""
        addr = self.linear_address(segment, offset)
        self.write_memory(addr, bytes([value & 0xFF]))

    def read_word(self, segment, offset):
        """Read a 16-bit word at segment:offset (little-endian)."""
        addr = self.linear_address(segment, offset)
        data = self.read_memory(addr, 2)
        return data[0] | (data[1] << 8)

    def write_word(self, segment, offset, value):
        """Write a 16-bit word at segment:offset (little-endian)."""
        addr = self.linear_address(segment, offset)
        self.write_memory(addr, bytes([value & 0xFF, (value >> 8) & 0xFF]))

    def execute(self, start_seg=None, start_off=None, stop_seg=None,
                stop_off=None, count=0, trace=False):
        """
        Execute instructions.

        Args:
            start_seg/start_off: Starting CS:IP (None = use current)
            stop_seg/stop_off: Stop address for G command (None = run until INT)
            count: Number of instructions for T/P command (0 = unlimited)
            trace: If True, single-step mode

        Returns:
            List of output strings describing execution state
        """
        if start_seg is not None:
            self.set_reg("CS", start_seg)
        if start_off is not None:
            self.set_reg("IP", start_off)

        cs = self.get_reg("CS")
        ip = self.get_reg("IP")
        self._halted = False
        self._int_num = None

        if count > 0:
            # Single-step / trace mode
            output = []
            for _ in range(count):
                cs = self.get_reg("CS")
                ip = self.get_reg("IP")
                start = self.linear_address(cs, ip)
                try:
                    self._uc.emu_start(start, 0, count=1)
                except UcError:
                    pass
                if self._halted:
                    break
            return output
        else:
            # Run until stop address or interrupt
            start = self.linear_address(cs, ip)
            if stop_seg is not None and stop_off is not None:
                stop = self.linear_address(stop_seg, stop_off)
            else:
                stop = 0  # Run until interrupt/error
            try:
                if stop:
                    self._uc.emu_start(start, stop)
                else:
                    self._uc.emu_start(start, MEMORY_SIZE)
            except UcError:
                pass
            return []

    @property
    def halted(self):
        """Whether execution was stopped by an interrupt."""
        return self._halted

    @property
    def int_num(self):
        """The interrupt number that caused the halt, if any."""
        return self._int_num

    def register_dump(self):
        """
        Return the full register dump string exactly like DEBUG.COM:
        AX=0000  BX=0000  CX=0000  DX=0000  SP=FFFE  BP=0000  SI=0000  DI=0000
        DS=073F  ES=073F  SS=073F  CS=073F  IP=0100   NV UP EI PL NZ NA PO NC
        """
        vals = {}
        for name in ["AX", "BX", "CX", "DX", "SP", "BP", "SI", "DI",
                      "DS", "ES", "SS", "CS", "IP"]:
            vals[name] = self.get_reg(name)

        line1 = (
            f"AX={vals['AX']:04X}  BX={vals['BX']:04X}  "
            f"CX={vals['CX']:04X}  DX={vals['DX']:04X}  "
            f"SP={vals['SP']:04X}  BP={vals['BP']:04X}  "
            f"SI={vals['SI']:04X}  DI={vals['DI']:04X}"
        )
        line2 = (
            f"DS={vals['DS']:04X}  ES={vals['ES']:04X}  "
            f"SS={vals['SS']:04X}  CS={vals['CS']:04X}  "
            f"IP={vals['IP']:04X}   {self.flags_string()}"
        )
        return line1 + "\n" + line2
