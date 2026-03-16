"""
Windows 7-style GUI for the DEBUG.COM replica using tkinter.

Provides a graphical windowed interface with:
- Register display panel
- Memory dump viewer
- Disassembly viewer
- Command input and output area
- Menu bar for file operations
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys
from .commands import DebugCommands


class DebugGUI:
    """Graphical user interface for the DEBUG replica."""

    def __init__(self, filename=None, color="green"):
        self.debug = DebugCommands()
        self.color = color
        self.filename = filename

        # Color schemes (DOS-style)
        if color == "green":
            self.fg_color = "#00ff00"
            self.bg_color = "#000000"
        else:  # amber
            self.fg_color = "#ffbf00"
            self.bg_color = "#000000"

        # Create the main window
        self.root = tk.Tk()
        self.root.title("DEBUG.COM - 16-bit Debugger")
        self.root.geometry("1200x800")
        self.root.configure(bg=self.bg_color)

        # Create UI components
        self._create_menu()
        self._create_widgets()

        # If a filename was provided, load it
        if filename:
            self._load_file(filename)

        # Initial display
        self._update_all_displays()

    def _create_menu(self):
        """Create the menu bar."""
        menubar = tk.Menu(self.root, bg=self.bg_color, fg=self.fg_color)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.bg_color, fg=self.fg_color)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load File (L)...", command=self._menu_load_file)
        file_menu.add_command(label="Save File (W)...", command=self._menu_save_file)
        file_menu.add_separator()
        file_menu.add_command(label="Quit (Q)", command=self._quit)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0, bg=self.bg_color, fg=self.fg_color)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh All", command=self._update_all_displays)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0, bg=self.bg_color, fg=self.fg_color)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Commands (?)", command=self._show_help)

    def _create_widgets(self):
        """Create all the GUI widgets."""
        # Main container with three panels
        main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=self.bg_color)
        main_paned.pack(fill=tk.BOTH, expand=1)

        # Left panel: Registers and Flags
        left_frame = tk.Frame(main_paned, bg=self.bg_color, width=300)
        main_paned.add(left_frame, minsize=250)

        # Right panel: split into upper (memory/disassembly) and lower (command I/O)
        right_paned = tk.PanedWindow(main_paned, orient=tk.VERTICAL, bg=self.bg_color)
        main_paned.add(right_paned)

        # Create register display
        self._create_register_panel(left_frame)

        # Create memory and disassembly viewers
        upper_frame = tk.Frame(right_paned, bg=self.bg_color)
        right_paned.add(upper_frame, minsize=300)
        self._create_memory_disasm_panel(upper_frame)

        # Create command I/O area
        lower_frame = tk.Frame(right_paned, bg=self.bg_color)
        right_paned.add(lower_frame, minsize=200)
        self._create_command_panel(lower_frame)

    def _create_register_panel(self, parent):
        """Create the register display panel."""
        # Title
        title = tk.Label(parent, text="REGISTERS", bg=self.bg_color, fg=self.fg_color,
                        font=("Courier", 12, "bold"))
        title.pack(pady=5)

        # Register display text area
        self.register_text = tk.Text(parent, bg=self.bg_color, fg=self.fg_color,
                                     font=("Courier", 10), height=20, width=30,
                                     relief=tk.SUNKEN, bd=2)
        self.register_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.register_text.config(state=tk.DISABLED)

        # Buttons for register operations
        btn_frame = tk.Frame(parent, bg=self.bg_color)
        btn_frame.pack(pady=5)

        tk.Button(btn_frame, text="Refresh (R)", command=self._update_register_display,
                 bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=2)

    def _create_memory_disasm_panel(self, parent):
        """Create the memory dump and disassembly viewers."""
        # Notebook (tabs) for memory and disassembly
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Style for notebook
        style = ttk.Style()
        style.configure('TNotebook', background=self.bg_color)
        style.configure('TNotebook.Tab', background=self.bg_color, foreground=self.fg_color)

        # Memory dump tab
        memory_frame = tk.Frame(notebook, bg=self.bg_color)
        notebook.add(memory_frame, text="Memory Dump (D)")

        mem_control_frame = tk.Frame(memory_frame, bg=self.bg_color)
        mem_control_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(mem_control_frame, text="Address:", bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT)
        self.mem_addr_entry = tk.Entry(mem_control_frame, bg=self.bg_color, fg=self.fg_color,
                                       insertbackground=self.fg_color, width=10)
        self.mem_addr_entry.pack(side=tk.LEFT, padx=5)
        self.mem_addr_entry.insert(0, "100")

        tk.Button(mem_control_frame, text="Dump", command=self._update_memory_display,
                 bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=2)

        self.memory_text = scrolledtext.ScrolledText(memory_frame, bg=self.bg_color, fg=self.fg_color,
                                                     font=("Courier", 9), height=15,
                                                     relief=tk.SUNKEN, bd=2)
        self.memory_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.memory_text.config(state=tk.DISABLED)

        # Disassembly tab
        disasm_frame = tk.Frame(notebook, bg=self.bg_color)
        notebook.add(disasm_frame, text="Disassembly (U)")

        disasm_control_frame = tk.Frame(disasm_frame, bg=self.bg_color)
        disasm_control_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(disasm_control_frame, text="Address:", bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT)
        self.disasm_addr_entry = tk.Entry(disasm_control_frame, bg=self.bg_color, fg=self.fg_color,
                                          insertbackground=self.fg_color, width=10)
        self.disasm_addr_entry.pack(side=tk.LEFT, padx=5)
        self.disasm_addr_entry.insert(0, "100")

        tk.Button(disasm_control_frame, text="Unassemble", command=self._update_disasm_display,
                 bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=2)

        self.disasm_text = scrolledtext.ScrolledText(disasm_frame, bg=self.bg_color, fg=self.fg_color,
                                                     font=("Courier", 9), height=15,
                                                     relief=tk.SUNKEN, bd=2)
        self.disasm_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.disasm_text.config(state=tk.DISABLED)

    def _create_command_panel(self, parent):
        """Create the command input and output area."""
        # Title
        title = tk.Label(parent, text="COMMAND OUTPUT", bg=self.bg_color, fg=self.fg_color,
                        font=("Courier", 12, "bold"))
        title.pack(pady=5)

        # Output display
        self.output_text = scrolledtext.ScrolledText(parent, bg=self.bg_color, fg=self.fg_color,
                                                     font=("Courier", 9), height=8,
                                                     relief=tk.SUNKEN, bd=2)
        self.output_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.output_text.config(state=tk.DISABLED)

        # Command input
        input_frame = tk.Frame(parent, bg=self.bg_color)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(input_frame, text="-", bg=self.bg_color, fg=self.fg_color,
                font=("Courier", 10)).pack(side=tk.LEFT)

        self.command_entry = tk.Entry(input_frame, bg=self.bg_color, fg=self.fg_color,
                                      insertbackground=self.fg_color, font=("Courier", 10))
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.command_entry.bind("<Return>", lambda e: self._execute_command())
        self.command_entry.focus_set()

        tk.Button(input_frame, text="Execute", command=self._execute_command,
                 bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT)

    def _output(self, text):
        """Add text to the output display."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def _clear_output(self):
        """Clear the output display."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

    def _execute_command(self):
        """Execute a DEBUG command."""
        command = self.command_entry.get().strip()
        if not command:
            return

        # Display the command
        self._output(f"-{command}")

        # Clear the entry
        self.command_entry.delete(0, tk.END)

        # Execute the command
        result = self.debug.execute(command)

        # Display the result
        for line in result:
            self._output(line)

        # Update displays if needed
        if command and command[0].upper() in ['R', 'T', 'P', 'G', 'A', 'E', 'F', 'M', 'L', 'W']:
            self._update_all_displays()

        # Check if quit was requested
        if not self.debug.running:
            self._quit()

    def _update_register_display(self):
        """Update the register display."""
        result = self.debug.cmd_register("")

        self.register_text.config(state=tk.NORMAL)
        self.register_text.delete(1.0, tk.END)

        for line in result:
            self.register_text.insert(tk.END, line + "\n")

        self.register_text.config(state=tk.DISABLED)

    def _update_memory_display(self):
        """Update the memory dump display."""
        addr = self.mem_addr_entry.get().strip()
        if not addr:
            addr = "100"

        result = self.debug.cmd_dump(addr)

        self.memory_text.config(state=tk.NORMAL)
        self.memory_text.delete(1.0, tk.END)

        for line in result:
            self.memory_text.insert(tk.END, line + "\n")

        self.memory_text.config(state=tk.DISABLED)

    def _update_disasm_display(self):
        """Update the disassembly display."""
        addr = self.disasm_addr_entry.get().strip()
        if not addr:
            addr = "100"

        result = self.debug.cmd_unassemble(addr)

        self.disasm_text.config(state=tk.NORMAL)
        self.disasm_text.delete(1.0, tk.END)

        for line in result:
            self.disasm_text.insert(tk.END, line + "\n")

        self.disasm_text.config(state=tk.DISABLED)

    def _update_all_displays(self):
        """Update all display panels."""
        self._update_register_display()
        self._update_memory_display()
        self._update_disasm_display()

    def _load_file(self, filename):
        """Load a file into memory."""
        try:
            self.debug.cmd_name(filename)
            result = self.debug.cmd_load("")
            for line in result:
                self._output(line)
            self._update_all_displays()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")

    def _menu_load_file(self):
        """Handle File > Load File menu item."""
        filename = filedialog.askopenfilename(
            title="Load File",
            filetypes=[("COM files", "*.com"), ("All files", "*.*")]
        )
        if filename:
            self._load_file(filename)

    def _menu_save_file(self):
        """Handle File > Save File menu item."""
        filename = filedialog.asksaveasfilename(
            title="Save File",
            defaultextension=".com",
            filetypes=[("COM files", "*.com"), ("All files", "*.*")]
        )
        if filename:
            try:
                self.debug.cmd_name(filename)
                result = self.debug.cmd_write("")
                for line in result:
                    self._output(line)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")

    def _show_help(self):
        """Show help dialog."""
        help_text = """DEBUG.COM Commands:

A [address]         - Assemble instructions
C range address     - Compare memory blocks
D [range]           - Dump memory (hex + ASCII)
E address [list]    - Enter data into memory
F range list        - Fill memory with pattern
G [=address] [bp]   - Go (execute program)
H value1 value2     - Hex arithmetic
I port              - Input from port
L [address]         - Load file
M range address     - Move memory block
N filename          - Name file for Load/Write
O port byte         - Output to port
P [=address] [cnt]  - Proceed (step over)
Q                   - Quit
R [register]        - Display/modify registers
S range list        - Search memory
T [=address] [cnt]  - Trace (single step)
U [range]           - Unassemble (disassemble)
W [address]         - Write memory to file
?                   - Display help"""

        messagebox.showinfo("DEBUG Commands", help_text)

    def _quit(self):
        """Quit the application."""
        self.root.quit()
        self.root.destroy()

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def main():
    """Entry point for the GUI version of DEBUG."""
    import argparse

    parser = argparse.ArgumentParser(
        description="16-bit DEBUG.COM replica - GUI version"
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

    gui = DebugGUI(filename=args.filename, color=args.color)
    gui.run()


if __name__ == "__main__":
    main()
