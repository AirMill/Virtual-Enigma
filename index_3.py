#!/usr/bin/env python3
"""
enigma_machine_ui.py
Enigma-style GUI (macOS friendly) with:
- Rotor windows (live stepping)
- Ring settings
- Plugboard
- On-screen keyboard + lampboard
- Input + Output boxes
- Copy output, reset, clear
- "Process Pasted Text" (encrypt/decrypt entire input from start positions)

Enigma is reciprocal: same operation encrypts and decrypts with same settings.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import string
import re

ALPHABET = string.ascii_uppercase

ROTOR_SPECS = {
    "I":   ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II":  ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV":  ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V":   ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
}

REFLECTORS = {
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
}

def letter_to_index(c: str) -> int:
    return ord(c) - ord("A")

def index_to_letter(i: int) -> str:
    return ALPHABET[i % 26]

class Rotor:
    def __init__(self, name, wiring_str, notch_letters, ring_setting=1, position='A'):
        self.name = name
        self.wiring = [letter_to_index(c) for c in wiring_str]
        self.inverse_wiring = [0]*26
        for i, w in enumerate(self.wiring):
            self.inverse_wiring[w] = i

        self.notches = set(letter_to_index(c) for c in notch_letters)
        self.ring = (ring_setting - 1) % 26
        self.position = letter_to_index(position)

    def step(self):
        self.position = (self.position + 1) % 26

    def at_notch(self) -> bool:
        return self.position in self.notches

    def forward(self, c: int) -> int:
        shifted = (c + self.position - self.ring) % 26
        wired = self.wiring[shifted]
        return (wired - self.position + self.ring) % 26

    def backward(self, c: int) -> int:
        shifted = (c + self.position - self.ring) % 26
        wired = self.inverse_wiring[shifted]
        return (wired - self.position + self.ring) % 26

class Reflector:
    def __init__(self, wiring_str):
        self.wiring = [letter_to_index(c) for c in wiring_str]
    def reflect(self, c: int) -> int:
        return self.wiring[c]

class Plugboard:
    def __init__(self, pairs=None):
        self.mapping = list(range(26))
        if pairs:
            for p in pairs:
                a = letter_to_index(p[0])
                b = letter_to_index(p[1])
                self.mapping[a] = b
                self.mapping[b] = a
    def swap(self, c: int) -> int:
        return self.mapping[c]

class EnigmaMachine:
    def __init__(self, rotor_names, rotor_positions, ring_settings, reflector_name, plug_pairs):
        self.rotors = []
        for name, pos, ring in zip(rotor_names, rotor_positions, ring_settings):
            wiring, notch = ROTOR_SPECS[name]
            self.rotors.append(Rotor(name, wiring, notch, ring_setting=ring, position=pos))

        self.reflector_name = reflector_name
        self.reflector = Reflector(REFLECTORS[reflector_name])
        self.plugboard = Plugboard(plug_pairs)

    def step_rotors(self):
        # Correct Enigma I stepping (double-step):
        left, middle, right = self.rotors[0], self.rotors[1], self.rotors[2]
        middle_at_notch = middle.at_notch()
        right_at_notch = right.at_notch()

        if middle_at_notch:
            left.step()
        if right_at_notch or middle_at_notch:
            middle.step()
        right.step()

    def process_letter(self, ch: str) -> str:
        if ch not in ALPHABET:
            return ch
        self.step_rotors()
        c = letter_to_index(ch)
        c = self.plugboard.swap(c)
        for rotor in reversed(self.rotors):
            c = rotor.forward(c)
        c = self.reflector.reflect(c)
        for rotor in self.rotors:
            c = rotor.backward(c)
        c = self.plugboard.swap(c)
        return index_to_letter(c)

    def process_text(self, text: str, keep_nonletters=True) -> str:
        out = []
        for ch in text.upper():
            if ch in ALPHABET:
                out.append(self.process_letter(ch))
            else:
                if keep_nonletters:
                    out.append(ch)
        return ''.join(out)

# ---------------- GUI ----------------

KEYBOARD_ROWS = [
    "QWERTYUIOP",
    "ASDFGHJKL",
    "ZXCVBNM",
]

class EnigmaLikeGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Enigma Machine")
        self.root.geometry("1100x750")

        # Settings vars
        self.rotor_left = tk.StringVar(value="I")
        self.rotor_mid  = tk.StringVar(value="II")
        self.rotor_right= tk.StringVar(value="III")

        self.pos_left = tk.StringVar(value="A")
        self.pos_mid  = tk.StringVar(value="A")
        self.pos_right= tk.StringVar(value="A")

        self.ring_left = tk.IntVar(value=1)
        self.ring_mid  = tk.IntVar(value=1)
        self.ring_right= tk.IntVar(value=1)

        self.reflector = tk.StringVar(value="B")
        self.plugboard = tk.StringVar(value="")  # "AT BS CM"

        self.keep_nonletters = tk.BooleanVar(value=True)

        self.status = tk.StringVar(value="Ready")

        # Internal live machine (for button-typing)
        self.live_machine = None
        self.live_start_signature = None  # settings snapshot to know if reset needed

        self._build_ui()
        self.reset_machine()

    # ---------- parsing / validation ----------
    def _parse_plug_pairs(self, txt: str):
        t = (txt or "").strip().upper()
        if not t:
            return []
        t = t.replace("-", " ")
        t = re.sub(r"[;,/|]+", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        parts = [p for p in t.split(" ") if p]

        pairs = []
        invalid = []
        for p in parts:
            if len(p) != 2 or not p.isalpha() or p[0] == p[1]:
                invalid.append(p)
                continue
            pairs.append(p)

        if invalid:
            raise ValueError("Invalid plugboard pair(s): " + ", ".join(invalid))

        used = set()
        for p in pairs:
            a, b = p[0], p[1]
            if a in used or b in used:
                raise ValueError(f"Plugboard conflict (letter reused) in pair: {p}")
            used.add(a); used.add(b)

        # normalize order (AT == TA)
        norm = []
        seen = set()
        for p in pairs:
            a, b = sorted(p)
            k = a + b
            if k not in seen:
                seen.add(k)
                norm.append(k)
        return norm

    def _validate_pos(self, s: str) -> str:
        s = (s or "A").strip().upper()
        if not s or s[0] not in ALPHABET:
            return "A"
        return s[0]

    def _settings_signature(self):
        return (
            self.rotor_left.get(), self.rotor_mid.get(), self.rotor_right.get(),
            self._validate_pos(self.pos_left.get()),
            self._validate_pos(self.pos_mid.get()),
            self._validate_pos(self.pos_right.get()),
            int(self.ring_left.get()), int(self.ring_mid.get()), int(self.ring_right.get()),
            self.reflector.get(),
            (self.plugboard.get() or "").strip().upper(),
            bool(self.keep_nonletters.get())
        )

    def _build_machine_from_ui(self) -> EnigmaMachine:
        rotor_names = [self.rotor_left.get(), self.rotor_mid.get(), self.rotor_right.get()]
        positions = [
            self._validate_pos(self.pos_left.get()),
            self._validate_pos(self.pos_mid.get()),
            self._validate_pos(self.pos_right.get())
        ]
        rings = [int(self.ring_left.get()), int(self.ring_mid.get()), int(self.ring_right.get())]
        if any(r < 1 or r > 26 for r in rings):
            raise ValueError("Ring settings must be 1..26.")
        ref = self.reflector.get().strip().upper()
        if ref not in REFLECTORS:
            raise ValueError("Unknown reflector.")
        plugs = self._parse_plug_pairs(self.plugboard.get())
        return EnigmaMachine(rotor_names, positions, rings, ref, plugs)

    # ---------- UI ----------
    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        # Top: "machine head" (rotors + plugboard)
        head = ttk.LabelFrame(outer, text="Machine Settings")
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)

        row0 = ttk.Frame(head)
        row0.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        ttk.Label(row0, text="Rotors (L–M–R)").grid(row=0, column=0, sticky="w")
        ttk.OptionMenu(row0, self.rotor_left, self.rotor_left.get(), *ROTOR_SPECS.keys()).grid(row=0, column=1, padx=4)
        ttk.OptionMenu(row0, self.rotor_mid, self.rotor_mid.get(), *ROTOR_SPECS.keys()).grid(row=0, column=2, padx=4)
        ttk.OptionMenu(row0, self.rotor_right, self.rotor_right.get(), *ROTOR_SPECS.keys()).grid(row=0, column=3, padx=4)

        ttk.Label(row0, text="Positions").grid(row=0, column=4, padx=(16, 4))
        ttk.Entry(row0, width=3, textvariable=self.pos_left).grid(row=0, column=5, padx=2)
        ttk.Entry(row0, width=3, textvariable=self.pos_mid).grid(row=0, column=6, padx=2)
        ttk.Entry(row0, width=3, textvariable=self.pos_right).grid(row=0, column=7, padx=2)

        ttk.Label(row0, text="Rings").grid(row=0, column=8, padx=(16, 4))
        ttk.Spinbox(row0, from_=1, to=26, width=4, textvariable=self.ring_left).grid(row=0, column=9, padx=2)
        ttk.Spinbox(row0, from_=1, to=26, width=4, textvariable=self.ring_mid).grid(row=0, column=10, padx=2)
        ttk.Spinbox(row0, from_=1, to=26, width=4, textvariable=self.ring_right).grid(row=0, column=11, padx=2)

        row1 = ttk.Frame(head)
        row1.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        ttk.Label(row1, text="Plugboard (pairs like: AT BS CM)").grid(row=0, column=0, sticky="w")
        ttk.Entry(row1, width=40, textvariable=self.plugboard).grid(row=0, column=1, padx=6)
        ttk.Checkbutton(row1, text="Keep spaces/punctuation", variable=self.keep_nonletters).grid(row=0, column=2, padx=(14, 0))

        ttk.Button(row1, text="Reset", command=self.reset_machine).grid(row=0, column=3, padx=(18, 4))
        ttk.Button(row1, text="Clear", command=self.clear_all).grid(row=0, column=4, padx=4)
        ttk.Button(row1, text="Copy Output", command=self.copy_output).grid(row=0, column=5, padx=4)
        ttk.Button(row1, text="Process Pasted Text", command=self.process_pasted_text).grid(row=0, column=6, padx=(10, 0))

        # Middle: lampboard + rotor windows (live)
        mid = ttk.Frame(outer)
        mid.grid(row=1, column=0, sticky="ew", pady=(12, 8))
        mid.columnconfigure(0, weight=1)

        self._build_rotor_windows(mid)
        self._build_lampboard(mid)

        # Bottom: input/output + keyboard
        body = ttk.Frame(outer)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=0)

        self._build_io(body)
        self._build_keyboard(body)

        # Status
        ttk.Label(outer, textvariable=self.status).grid(row=3, column=0, sticky="w", pady=(10, 0))

    def _build_rotor_windows(self, parent):
        frame = ttk.LabelFrame(parent, text="Rotor Windows (live)")
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        inner = ttk.Frame(frame, padding=8)
        inner.grid(row=0, column=0, sticky="ew")

        self.win_left = tk.StringVar(value="A")
        self.win_mid  = tk.StringVar(value="A")
        self.win_right= tk.StringVar(value="A")

        big = ("Helvetica", 20, "bold")
        ttk.Label(inner, text="L").grid(row=0, column=0, padx=(4, 2))
        ttk.Label(inner, textvariable=self.win_left, width=3).grid(row=0, column=1, padx=6)
        ttk.Label(inner, text="M").grid(row=0, column=2, padx=(18, 2))
        ttk.Label(inner, textvariable=self.win_mid, width=3).grid(row=0, column=3, padx=6)
        ttk.Label(inner, text="R").grid(row=0, column=4, padx=(18, 2))
        ttk.Label(inner, textvariable=self.win_right, width=3).grid(row=0, column=5, padx=6)

        # Make them look bigger using a normal tk.Label (ttk ignores font sometimes)
        for var, col in [(self.win_left,1),(self.win_mid,3),(self.win_right,5)]:
            lab = tk.Label(inner, textvariable=var, font=big, width=2, relief="ridge", padx=10, pady=6)
            lab.grid(row=1, column=col, padx=6, pady=(2, 6))

    def _build_lampboard(self, parent):
        frame = ttk.LabelFrame(parent, text="Lampboard (output letter lights)")
        frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        self.lamps = {}
        inner = ttk.Frame(frame, padding=8)
        inner.grid(row=0, column=0, sticky="ew")

        # Layout similar-ish to keyboard rows
        lamp_rows = [
            "QWERTYUIOP",
            "ASDFGHJKL",
            "ZXCVBNM"
        ]

        for r, row in enumerate(lamp_rows):
            rowf = ttk.Frame(inner)
            rowf.grid(row=r, column=0, pady=4)
            for ch in row:
                lab = tk.Label(
                    rowf, text=ch, width=3, height=1,
                    font=("Helvetica", 14, "bold"),
                    relief="groove", bd=2,
                    bg="#222", fg="#ddd"
                )
                lab.pack(side="left", padx=3)
                self.lamps[ch] = lab

        self._lamp_off_all()

    def _build_io(self, parent):
        io = ttk.Frame(parent)
        io.grid(row=0, column=0, sticky="nsew")
        io.columnconfigure(0, weight=1)
        io.columnconfigure(1, weight=1)
        io.rowconfigure(1, weight=1)

        left = ttk.LabelFrame(io, text="Input (type or paste)")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.input_text = tk.Text(left, height=10, wrap="word", font=("Helvetica", 12))
        self.input_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        right = ttk.LabelFrame(io, text="Output (copy this)")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.output_text = tk.Text(right, height=10, wrap="word", font=("Helvetica", 12))
        self.output_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

    def _build_keyboard(self, parent):
        kb = ttk.LabelFrame(parent, text="Keyboard (click letters to encode/decode)")
        kb.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        inner = ttk.Frame(kb, padding=10)
        inner.grid(row=0, column=0, sticky="ew")

        # Note: for a more authentic Enigma feel, we don't support backspace
        # (because rotor stepping reversal isn't trivial). Use Clear/Reset.
        for r, row in enumerate(KEYBOARD_ROWS):
            rowf = ttk.Frame(inner)
            rowf.grid(row=r, column=0, pady=4)
            for ch in row:
                b = tk.Button(
                    rowf,
                    text=ch,
                    width=4,
                    height=2,
                    font=("Helvetica", 12, "bold"),
                    command=lambda c=ch: self.press_key(c)
                )
                b.pack(side="left", padx=3)

        extras = ttk.Frame(inner)
        extras.grid(row=3, column=0, pady=(10, 0))
        ttk.Button(extras, text="Space", command=lambda: self.press_key(" ")).grid(row=0, column=0, padx=4)
        ttk.Button(extras, text="Enter ↵", command=lambda: self.press_key("\n")).grid(row=0, column=1, padx=4)

    # ---------- behaviors ----------
    def reset_machine(self):
        """Rebuild the live machine from current UI settings and reset live output."""
        try:
            # also normalize displayed position entries
            self.pos_left.set(self._validate_pos(self.pos_left.get()))
            self.pos_mid.set(self._validate_pos(self.pos_mid.get()))
            self.pos_right.set(self._validate_pos(self.pos_right.get()))

            self.live_machine = self._build_machine_from_ui()
            self.live_start_signature = self._settings_signature()
            self._sync_rotor_windows()
            self._lamp_off_all()
            self.status.set("Machine reset. Ready to type.")
        except Exception as e:
            self.live_machine = None
            messagebox.showerror("Settings error", str(e))
            self.status.set("Fix settings, then Reset.")

    def clear_all(self):
        self.input_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
        self._lamp_off_all()
        self.status.set("Cleared. (Rotor state unchanged — hit Reset if needed.)")

    def copy_output(self):
        text = self.output_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Copy Output", "Output is empty.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self.status.set("Output copied to clipboard.")

    def _lamp_off_all(self):
        for lab in self.lamps.values():
            lab.configure(bg="#222", fg="#ddd")

    def _lamp_on(self, letter: str):
        self._lamp_off_all()
        if letter in self.lamps:
            self.lamps[letter].configure(bg="#ffd24a", fg="#000")

    def _sync_rotor_windows(self):
        if not self.live_machine:
            self.win_left.set("?"); self.win_mid.set("?"); self.win_right.set("?")
            return
        r0, r1, r2 = self.live_machine.rotors
        self.win_left.set(index_to_letter(r0.position))
        self.win_mid.set(index_to_letter(r1.position))
        self.win_right.set(index_to_letter(r2.position))

    def _ensure_live_machine_matches_settings(self):
        """If user changed settings but didn't reset, warn and auto-reset."""
        sig = self._settings_signature()
        if self.live_start_signature != sig:
            # Auto-reset for convenience
            self.reset_machine()

    def press_key(self, ch: str):
        """Live typing via Enigma keyboard."""
        self._ensure_live_machine_matches_settings()
        if not self.live_machine:
            return

        # Show input
        self.input_text.insert(tk.END, ch)

        # Process
        keep_nonletters = bool(self.keep_nonletters.get())
        if ch.upper() in ALPHABET:
            out_ch = self.live_machine.process_letter(ch.upper())
            self.output_text.insert(tk.END, out_ch)
            self._lamp_on(out_ch)
            self._sync_rotor_windows()
        else:
            if keep_nonletters:
                self.output_text.insert(tk.END, ch)
            self._lamp_off_all()

        self.status.set("Typing… (Reset to restart from initial positions)")

    def process_pasted_text(self):
        """
        Process the entire input box from the *start settings* (fresh machine),
        producing a full output (useful for paste-from-email decode).
        """
        try:
            machine = self._build_machine_from_ui()
        except Exception as e:
            messagebox.showerror("Settings error", str(e))
            return

        text = self.input_text.get("1.0", tk.END).rstrip("\n")
        if not text.strip():
            messagebox.showinfo("Process", "Input is empty.")
            return

        keep_nonletters = bool(self.keep_nonletters.get())
        out = machine.process_text(text, keep_nonletters=keep_nonletters)

        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, out)

        # Set lamp to last alpha char, if any
        last = None
        for c in reversed(out):
            if c in ALPHABET:
                last = c
                break
        if last:
            self._lamp_on(last)
        else:
            self._lamp_off_all()

        # Also reset live machine to keep things consistent after paste processing
        self.reset_machine()
        self.status.set("Processed full text from start settings. Output ready to copy.")


def main():
    root = tk.Tk()
    # ttk theme: mac usually looks fine by default
    try:
        style = ttk.Style()
        # style.theme_use("aqua")  # optional
    except Exception:
        pass
    EnigmaLikeGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()