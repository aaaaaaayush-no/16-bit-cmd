# 16-bit-cmd — MS-DOS DEBUG.COM Replica

A faithful replica of the classic 16-bit **MS-DOS DEBUG.COM** debugger,
built with real 8086 CPU emulation. Runs natively on modern systems
(Windows, Linux, macOS) with an authentic DOS-style terminal interface.

## Features

- **Real 8086 Emulation** — [Unicorn Engine](https://www.unicorn-engine.org/) provides cycle-accurate 16-bit real-mode CPU execution
- **Full Assembler** — [Keystone Engine](https://www.keystone-engine.org/) powers the `A` (assemble) command
- **Full Disassembler** — [Capstone](https://www.capstone-engine.org/) powers the `U` (unassemble) command
- **Complete Command Set** — All original DEBUG.COM commands: `A C D E F G H I L M N O P Q R S T U W ?`
- **Authentic UI** — Green-on-black (or amber) monospace terminal using prompt_toolkit
- **File I/O** — Load and save `.COM` files directly from the filesystem
- **1 MB Address Space** — Full 8086 memory with segment:offset addressing

## Supported Commands

| Command | Description |
|---------|-------------|
| `A [address]` | Assemble instructions into memory |
| `C range address` | Compare two memory blocks |
| `D [range]` | Dump memory in hex + ASCII |
| `E address [list]` | Enter data into memory |
| `F range list` | Fill memory with a byte pattern |
| `G [=address] [breakpoints]` | Go — execute program |
| `H value1 value2` | Hex arithmetic (sum and difference) |
| `I port` | Input from I/O port (simulated) |
| `L [address]` | Load file into memory |
| `M range address` | Move (copy) memory block |
| `N filename` | Name a file for Load/Write |
| `O port byte` | Output to I/O port (simulated) |
| `P [=address] [count]` | Proceed — step over calls |
| `Q` | Quit |
| `R [register]` | Display/modify registers |
| `S range list` | Search memory for bytes |
| `T [=address] [count]` | Trace — single-step instructions |
| `U [range]` | Unassemble (disassemble) memory |
| `W [address]` | Write memory to file |
| `?` | Display help |

## Installation

### Prerequisites

- Python 3.8 or newer

### Install from source

```bash
git clone https://github.com/aaaaaaayush-no/16-bit-cmd.git
cd 16-bit-cmd
pip install -r requirements.txt
```

### Run directly

```bash
python -m debug16
```

### Install as a package

```bash
pip install -e .
debug16
```

### Build a standalone `.exe` (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --name debug16 --console debug16/__main__.py
```

The executable will be in the `dist/` folder.

## Quick Start

```
$ python -m debug16
-R
AX=0000  BX=0000  CX=0000  DX=0000  SP=FFFE  BP=0000  SI=0000  DI=0000
DS=073F  ES=073F  SS=073F  CS=073F  IP=0100   NV UP EI PL NZ NA PO NC
073F:0100 0000          ADD     [BX+SI],AL
-A 100
073F:0100 MOV AX, 1234
073F:0103 MOV BX, 5678
073F:0106 ADD AX, BX
073F:0108
-U 100
073F:0100 B83412        MOV     AX,1234
073F:0103 BB7856        MOV     BX,5678
073F:0106 01D8          ADD     AX,BX
-T
AX=1234  BX=0000  CX=0000  DX=0000  SP=FFFE  BP=0000  SI=0000  DI=0000
DS=073F  ES=073F  SS=073F  CS=073F  IP=0103   NV UP EI PL NZ NA PO NC
073F:0103 BB7856        MOV     BX,5678
-H FFFF 1
0000  FFFE
-D 100
073F:0100  B8 34 12 BB 78 56 01 D8-00 00 00 00 00 00 00 00  .4..xV..........
-Q
```

## Loading a Sample .COM File

A sample `hello.com` is included in the `samples/` directory:

```
$ python -m debug16 samples/hello.com
-U 100
073F:0100 BA0901        MOV     DX,0109
073F:0103 B409          MOV     AH,09
073F:0105 CD21          INT     21
073F:0107 CD20          INT     20
-D 100 10F
073F:0100  BA 09 01 B4 09 CD 21 CD-20 48 65 6C 6C 6F 21 24  ......!. Hello!$
-R
AX=0000  BX=0000  CX=0010  DX=0000  SP=FFFE  BP=0000  SI=0000  DI=0000
DS=073F  ES=073F  SS=073F  CS=073F  IP=0100   NV UP EI PL NZ NA PO NC
073F:0100 BA0901        MOV     DX,0109
-Q
```

## Colour Modes

```bash
python -m debug16 --color green   # Classic green phosphor (default)
python -m debug16 --color amber   # Amber CRT style
```

## Project Structure

```
16-bit-cmd/
├── debug16/
│   ├── __init__.py          # Package metadata
│   ├── __main__.py          # Entry point (python -m debug16)
│   ├── cli.py               # DOS-style terminal interface
│   ├── cpu.py               # Unicorn Engine 8086 emulator wrapper
│   ├── assembler.py         # Keystone Engine assembler wrapper
│   ├── disassembler.py      # Capstone disassembler wrapper
│   └── commands.py          # All DEBUG command implementations
├── tests/
│   ├── test_cpu.py          # CPU emulation tests
│   ├── test_asm_disasm.py   # Assembler/disassembler tests
│   └── test_commands.py     # Command handler tests
├── samples/
│   └── hello.com            # Sample 8086 .COM program
├── requirements.txt
├── setup.py
└── README.md
```

## Architecture

- **CPU Module** (`cpu.py`) — Wraps Unicorn Engine in 16-bit real mode
  (`UC_MODE_16`) with full 1 MB memory, all 8086 registers, and FLAGS
  display in the authentic `NV UP EI PL NZ NA PO NC` format.

- **Assembler** (`assembler.py`) — Wraps Keystone Engine for x86 16-bit
  assembly, used by the `A` command.

- **Disassembler** (`disassembler.py`) — Wraps Capstone for x86 16-bit
  disassembly, used by the `U` command and instruction display.

- **Commands** (`commands.py`) — Implements every DEBUG command with
  identical syntax and output format to the original.

- **CLI** (`cli.py`) — Uses prompt_toolkit for the DOS-style `"-"` prompt
  with green/amber colour schemes.

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## License

This project is open source.