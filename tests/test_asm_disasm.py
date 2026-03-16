"""Tests for the assembler and disassembler modules."""

import pytest
from debug16.assembler import Assembler
from debug16.disassembler import Disassembler


class TestAssembler:
    """Test the Keystone-based assembler."""

    def test_assemble_nop(self):
        asm = Assembler()
        data, count = asm.assemble("NOP")
        assert data == b'\x90'
        assert count == 1

    def test_assemble_mov_ax(self):
        asm = Assembler()
        data, _ = asm.assemble("MOV AX, 1234h")
        assert data == b'\xB8\x34\x12'

    def test_assemble_int_21(self):
        asm = Assembler()
        data, _ = asm.assemble("INT 21h")
        assert data == b'\xCD\x21'

    def test_assemble_invalid(self):
        asm = Assembler()
        with pytest.raises(ValueError):
            asm.assemble("INVALIDINSTRUCTION")

    def test_assemble_with_address(self):
        asm = Assembler()
        # JMP should encode relative to address
        data, _ = asm.assemble("JMP 0110h", address=0x0100)
        assert len(data) > 0

    def test_assemble_to_bytes(self):
        asm = Assembler()
        data = asm.assemble_to_bytes("MOV BX, 5678h")
        assert data == b'\xBB\x78\x56'


class TestDisassembler:
    """Test the Capstone-based disassembler."""

    def test_disassemble_nop(self):
        disasm = Disassembler()
        results = disasm.disassemble(b'\x90', address=0x0100)
        assert len(results) == 1
        assert results[0][2] == "NOP"

    def test_disassemble_mov_ax(self):
        disasm = Disassembler()
        results = disasm.disassemble(b'\xB8\x34\x12', address=0x0100)
        assert len(results) >= 1
        assert results[0][2] == "MOV"
        assert "AX" in results[0][3]

    def test_disassemble_count(self):
        disasm = Disassembler()
        # Two NOPs
        results = disasm.disassemble(b'\x90\x90\x90', address=0x0100, count=2)
        assert len(results) == 2

    def test_disassemble_one(self):
        disasm = Disassembler()
        result = disasm.disassemble_one(b'\xCD\x21', address=0x0100)
        assert result is not None
        assert result[2] == "INT"

    def test_format_instruction(self):
        disasm = Disassembler()
        line, size = disasm.format_instruction(0x073F, 0x0100, b'\xB8\x34\x12')
        assert "073F:0100" in line
        assert "MOV" in line
        assert size == 3

    def test_format_invalid(self):
        disasm = Disassembler()
        # Should handle gracefully (might show as DB or valid decode)
        line, size = disasm.format_instruction(0x073F, 0x0100, b'\xFF\xFF')
        assert "073F:0100" in line
        assert size > 0
