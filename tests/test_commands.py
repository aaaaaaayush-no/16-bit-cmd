"""Tests for the DEBUG command handler."""

import os
import tempfile
import pytest
from debug16.commands import DebugCommands


class TestCommandParsing:
    """Test basic command parsing and dispatch."""

    def test_empty_input(self):
        cmd = DebugCommands()
        result = cmd.execute("")
        assert result == []

    def test_invalid_command(self):
        cmd = DebugCommands()
        result = cmd.execute("Z")
        assert result == ["Error"]

    def test_quit(self):
        cmd = DebugCommands()
        cmd.execute("Q")
        assert not cmd.running


class TestHexCommand:
    """Test H (Hex arithmetic) command."""

    def test_hex_add_subtract(self):
        cmd = DebugCommands()
        result = cmd.execute("H FFFF 0001")
        assert len(result) == 1
        assert "0000" in result[0]
        assert "FFFE" in result[0]

    def test_hex_simple(self):
        cmd = DebugCommands()
        result = cmd.execute("H 10 5")
        assert len(result) == 1
        assert "0015" in result[0]
        assert "000B" in result[0]

    def test_hex_error(self):
        cmd = DebugCommands()
        result = cmd.execute("H")
        assert result == ["Error"]


class TestRegisterCommand:
    """Test R (Register) command."""

    def test_register_display(self):
        cmd = DebugCommands()
        result = cmd.execute("R")
        assert len(result) >= 2
        combined = "\n".join(result)
        assert "AX=0000" in combined
        assert "BX=0000" in combined
        assert "CS=" in combined

    def test_register_single(self):
        cmd = DebugCommands()
        result = cmd.execute("RAX")
        assert len(result) >= 1
        assert "AX" in result[0]

    def test_register_invalid(self):
        cmd = DebugCommands()
        result = cmd.execute("RXX")
        assert result == ["br"]

    def test_set_register(self):
        cmd = DebugCommands()
        cmd.set_register_value("AX", "1234")
        assert cmd.cpu.get_reg("AX") == 0x1234


class TestDumpCommand:
    """Test D (Dump) command."""

    def test_dump_default(self):
        cmd = DebugCommands()
        result = cmd.execute("D")
        assert len(result) > 0
        # Should contain segment:offset format
        assert ":" in result[0]

    def test_dump_address(self):
        cmd = DebugCommands()
        result = cmd.execute("D 073F:0100")
        assert len(result) > 0
        assert "073F:" in result[0]

    def test_dump_range(self):
        cmd = DebugCommands()
        result = cmd.execute("D 073F:0100 010F")
        assert len(result) > 0


class TestEnterCommand:
    """Test E (Enter) command."""

    def test_enter_bytes(self):
        cmd = DebugCommands()
        cmd.execute("E 073F:0100 90 90 90")
        # Verify bytes were written
        b = cmd.cpu.read_byte(0x073F, 0x0100)
        assert b == 0x90

    def test_enter_single(self):
        cmd = DebugCommands()
        result = cmd.execute("E 073F:0100")
        # Should show current byte value
        assert len(result) == 1
        assert "073F:0100" in result[0]


class TestFillCommand:
    """Test F (Fill) command."""

    def test_fill_range(self):
        cmd = DebugCommands()
        cmd.execute("F 073F:0100 010F FF")
        for i in range(16):
            b = cmd.cpu.read_byte(0x073F, 0x0100 + i)
            assert b == 0xFF

    def test_fill_pattern(self):
        cmd = DebugCommands()
        cmd.execute("F 073F:0100 0107 AA BB")
        assert cmd.cpu.read_byte(0x073F, 0x0100) == 0xAA
        assert cmd.cpu.read_byte(0x073F, 0x0101) == 0xBB
        assert cmd.cpu.read_byte(0x073F, 0x0102) == 0xAA
        assert cmd.cpu.read_byte(0x073F, 0x0103) == 0xBB


class TestUnassembleCommand:
    """Test U (Unassemble) command."""

    def test_unassemble_default(self):
        cmd = DebugCommands()
        # Write some NOPs
        for i in range(16):
            cmd.cpu.write_byte(0x073F, 0x0100 + i, 0x90)
        result = cmd.execute("U 073F:0100")
        assert len(result) > 0
        assert "NOP" in result[0]

    def test_unassemble_mov(self):
        cmd = DebugCommands()
        addr = cmd.cpu.linear_address(0x073F, 0x0100)
        cmd.cpu.write_memory(addr, b'\xB8\x34\x12')
        result = cmd.execute("U 073F:0100 0102")
        assert len(result) >= 1
        assert "MOV" in result[0]


class TestAssembleCommand:
    """Test A (Assemble) command."""

    def test_assemble_nop(self):
        cmd = DebugCommands()
        cmd.execute("A 073F:0100")
        assert cmd.assembling
        result = cmd.execute("NOP")
        assert "Error" not in str(result)
        # Exit assemble mode
        cmd.execute("")
        assert not cmd.assembling
        # Check NOP was written
        b = cmd.cpu.read_byte(0x073F, 0x0100)
        assert b == 0x90


class TestCompareCommand:
    """Test C (Compare) command."""

    def test_compare_equal(self):
        cmd = DebugCommands()
        # Fill two regions with same data
        for i in range(16):
            cmd.cpu.write_byte(0x073F, 0x0100 + i, 0xAA)
            cmd.cpu.write_byte(0x073F, 0x0200 + i, 0xAA)
        result = cmd.execute("C 073F:0100 010F 0200")
        assert result == []

    def test_compare_different(self):
        cmd = DebugCommands()
        cmd.cpu.write_byte(0x073F, 0x0100, 0xAA)
        cmd.cpu.write_byte(0x073F, 0x0200, 0xBB)
        result = cmd.execute("C 073F:0100 0100 0200")
        assert len(result) == 1
        assert "AA" in result[0]
        assert "BB" in result[0]


class TestMoveCommand:
    """Test M (Move) command."""

    def test_move_memory(self):
        cmd = DebugCommands()
        for i in range(4):
            cmd.cpu.write_byte(0x073F, 0x0100 + i, 0x10 + i)
        cmd.execute("M 073F:0100 0103 0200")
        for i in range(4):
            assert cmd.cpu.read_byte(0x073F, 0x0200 + i) == 0x10 + i


class TestSearchCommand:
    """Test S (Search) command."""

    def test_search_found(self):
        cmd = DebugCommands()
        cmd.cpu.write_byte(0x073F, 0x0105, 0xAB)
        result = cmd.execute("S 073F:0100 010F AB")
        assert len(result) >= 1
        assert "0105" in result[0]


class TestFileCommands:
    """Test N (Name), L (Load), W (Write) commands."""

    def test_name_command(self):
        cmd = DebugCommands()
        cmd.execute("N test.com")
        assert cmd._filename == "test.com"

    def test_load_file(self):
        cmd = DebugCommands()
        # Create a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".com") as f:
            f.write(b'\x90\x90\x90\xCD\x20')
            tmpfile = f.name
        try:
            cmd.execute(f"N {tmpfile}")
            result = cmd.execute("L")
            assert result == []
            # Verify file was loaded
            assert cmd.cpu.get_reg("CX") == 5
            b = cmd.cpu.read_byte(0x073F, 0x0100)
            assert b == 0x90
        finally:
            os.unlink(tmpfile)

    def test_load_nonexistent(self):
        cmd = DebugCommands()
        cmd.execute("N nonexistent_file_xyz.com")
        result = cmd.execute("L")
        assert "File not found" in result[0]

    def test_write_file(self):
        cmd = DebugCommands()
        # Write some data to memory
        for i in range(4):
            cmd.cpu.write_byte(0x073F, 0x0100 + i, 0x90)
        cmd.cpu.set_reg("BX", 0)
        cmd.cpu.set_reg("CX", 4)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".com") as f:
            tmpfile = f.name
        try:
            cmd.execute(f"N {tmpfile}")
            result = cmd.execute("W")
            assert any("Writing" in r for r in result)
            # Verify file was written
            with open(tmpfile, "rb") as f:
                data = f.read()
            assert data == b'\x90\x90\x90\x90'
        finally:
            os.unlink(tmpfile)


class TestTraceCommand:
    """Test T (Trace) command."""

    def test_trace_single(self):
        cmd = DebugCommands()
        cs = cmd.cpu.get_reg("CS")
        ip = cmd.cpu.get_reg("IP")
        addr = cmd.cpu.linear_address(cs, ip)
        cmd.cpu.write_memory(addr, b'\x90')  # NOP
        result = cmd.execute("T")
        assert len(result) > 0
        # Should show register dump
        combined = "\n".join(result)
        assert "AX=" in combined


class TestGoCommand:
    """Test G (Go) command."""

    def test_go_to_address(self):
        cmd = DebugCommands()
        cs = cmd.cpu.get_reg("CS")
        ip = cmd.cpu.get_reg("IP")
        addr = cmd.cpu.linear_address(cs, ip)
        # Write NOPs and then INT 20h at 0103
        cmd.cpu.write_memory(addr, b'\x90\x90\x90\xCD\x20')
        result = cmd.execute("G =0100 0103")
        combined = "\n".join(result)
        assert "AX=" in combined


class TestHelpCommand:
    """Test ? (Help) command."""

    def test_help(self):
        cmd = DebugCommands()
        result = cmd.execute("?")
        assert len(result) > 0
        combined = "\n".join(result)
        assert "assemble" in combined
        assert "dump" in combined
        assert "quit" in combined
