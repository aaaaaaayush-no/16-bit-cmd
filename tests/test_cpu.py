"""Tests for the CPU emulation module."""

import pytest
from debug16.cpu import CPU, DEFAULT_CS, DEFAULT_DS, DEFAULT_SP, DEFAULT_IP


class TestCPUInit:
    """Test CPU initialization and reset."""

    def test_default_registers(self):
        cpu = CPU()
        assert cpu.get_reg("AX") == 0x0000
        assert cpu.get_reg("BX") == 0x0000
        assert cpu.get_reg("CX") == 0x0000
        assert cpu.get_reg("DX") == 0x0000
        assert cpu.get_reg("SP") == DEFAULT_SP
        assert cpu.get_reg("BP") == 0x0000
        assert cpu.get_reg("SI") == 0x0000
        assert cpu.get_reg("DI") == 0x0000

    def test_default_segments(self):
        cpu = CPU()
        assert cpu.get_reg("CS") == DEFAULT_CS
        assert cpu.get_reg("DS") == DEFAULT_DS
        assert cpu.get_reg("ES") == DEFAULT_DS
        assert cpu.get_reg("SS") == DEFAULT_DS
        assert cpu.get_reg("IP") == DEFAULT_IP

    def test_reset(self):
        cpu = CPU()
        cpu.set_reg("AX", 0x1234)
        cpu.set_reg("BX", 0x5678)
        cpu.reset()
        assert cpu.get_reg("AX") == 0x0000
        assert cpu.get_reg("BX") == 0x0000


class TestCPURegisters:
    """Test register read/write operations."""

    def test_set_get_reg(self):
        cpu = CPU()
        cpu.set_reg("AX", 0x1234)
        assert cpu.get_reg("AX") == 0x1234

    def test_reg_16bit_wrap(self):
        cpu = CPU()
        cpu.set_reg("AX", 0x1FFFF)
        assert cpu.get_reg("AX") == 0xFFFF

    def test_invalid_register(self):
        cpu = CPU()
        with pytest.raises(ValueError):
            cpu.get_reg("XX")

    def test_flags_register(self):
        cpu = CPU()
        cpu.set_flags(0x0000)
        # Bit 1 is reserved and always set by the 8086 / Unicorn Engine
        assert cpu.get_flags() & ~0x0002 == 0x0000
        cpu.set_flag_bit(0, True)  # Set CF
        assert cpu.get_flag_bit(0) == 1

    def test_flags_string(self):
        cpu = CPU()
        # Set known flag state: all flags clear
        cpu.set_flags(0x0002)  # Reserved bit 1 always set
        result = cpu.flags_string()
        assert "NV" in result
        assert "UP" in result
        assert "NZ" in result
        assert "NC" in result


class TestCPUMemory:
    """Test memory read/write operations."""

    def test_write_read_byte(self):
        cpu = CPU()
        cpu.write_byte(0x073F, 0x0100, 0xAB)
        assert cpu.read_byte(0x073F, 0x0100) == 0xAB

    def test_write_read_word(self):
        cpu = CPU()
        cpu.write_word(0x073F, 0x0100, 0x1234)
        assert cpu.read_word(0x073F, 0x0100) == 0x1234

    def test_linear_address(self):
        cpu = CPU()
        # segment 0x073F, offset 0x0100
        # linear = 0x073F * 16 + 0x0100 = 0x073F0 + 0x100 = 0x074F0
        assert cpu.linear_address(0x073F, 0x0100) == 0x074F0

    def test_memory_bulk(self):
        cpu = CPU()
        data = bytes([0xDE, 0xAD, 0xBE, 0xEF])
        addr = cpu.linear_address(0x073F, 0x0100)
        cpu.write_memory(addr, data)
        result = cpu.read_memory(addr, 4)
        assert result == data

    def test_register_dump_format(self):
        cpu = CPU()
        dump = cpu.register_dump()
        assert "AX=0000" in dump
        assert "BX=0000" in dump
        assert "CS=" in dump
        assert "IP=" in dump


class TestCPUExecution:
    """Test CPU instruction execution."""

    def test_execute_nop(self):
        """Test executing a NOP instruction."""
        cpu = CPU()
        cs = cpu.get_reg("CS")
        ip = cpu.get_reg("IP")
        addr = cpu.linear_address(cs, ip)
        cpu.write_memory(addr, b'\x90')  # NOP
        cpu.execute(count=1)
        assert cpu.get_reg("IP") == ip + 1

    def test_execute_mov_ax(self):
        """Test MOV AX, imm16."""
        cpu = CPU()
        cs = cpu.get_reg("CS")
        ip = cpu.get_reg("IP")
        addr = cpu.linear_address(cs, ip)
        # MOV AX, 0x1234 -> B8 34 12
        cpu.write_memory(addr, b'\xB8\x34\x12')
        cpu.execute(count=1)
        assert cpu.get_reg("AX") == 0x1234
        assert cpu.get_reg("IP") == ip + 3

    def test_execute_add(self):
        """Test ADD instruction."""
        cpu = CPU()
        cs = cpu.get_reg("CS")
        ip = cpu.get_reg("IP")
        addr = cpu.linear_address(cs, ip)
        # MOV AX, 5; MOV BX, 3; ADD AX, BX
        code = b'\xB8\x05\x00\xBB\x03\x00\x01\xD8'
        cpu.write_memory(addr, code)
        cpu.execute(count=3)
        assert cpu.get_reg("AX") == 8

    def test_execute_int_halts(self):
        """Test that INT instruction halts execution."""
        cpu = CPU()
        cs = cpu.get_reg("CS")
        ip = cpu.get_reg("IP")
        addr = cpu.linear_address(cs, ip)
        # INT 20h
        cpu.write_memory(addr, b'\xCD\x20')
        cpu.execute(count=1)
        assert cpu.halted
        assert cpu.int_num == 0x20
