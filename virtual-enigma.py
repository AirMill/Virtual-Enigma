#!/usr/bin/env python3
"""
enigma_m4_gui.py
Enigma M4 simulator (4-rotor). Tkinter GUI.
Export produces TWO files:
 - <chosen_filename>_message.txt  (ciphertext only)
 - <chosen_filename>_settings.json (all machine settings)

Features:
 - Rotors: I..VIII plus Beta/Gamma (fourth rotor)
 - Thin reflectors (B-thin, C-thin) supported
 - Ring settings, window/start positions
 - Plugboard (pairs)
 - Stepping: only the rightmost three rotors step (classic double-step applied to those three).
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import string, json, os

ALPHABET = string.ascii_uppercase

# Historical wirings (standard)
ROTOR_SPECS = {
    # name: (wiring, notch_letters)
    "I":   ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II":  ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV":  ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V":   ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
    "VI":  ("JPGVOUMFYQBENHZRDKASXLICTW", "ZM"),   # double-notch
    "VII": ("NZJHGRCXMYSWBOUFAIVLPEKQDT", "ZM"),
    "VIII":("FKQHTLXOCBJSPDZRAMEWNIUYGV", "ZM"),
    # thin / Zusatzwalzen for M4 (leftmost 4th rotor). They have index rings but NO notches.
    "BETA":  ("LEYJVCNIXWPBQMDRTAKZGFUHOS", ""),  # no notch
    "GAMMA": ("FSOKANUERHMBTIYCWLQPZXVGJD", ""),  # no notch
}

# Reflectors, include thin reflectors for M4
REFLECTORS = {
    "B":      "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C":      "FVPJIAOYEDRZXWGCTKUQSBNMHL",
    "B_THIN": "ENKQAUYWJICOPBLMDXZVFTHRGS",  # M4 only
    "C_THIN": "RDOBJNTKVEHMLFCWZAXGYIPSUQ",  # M4 only
}

def l2i(c): return ord(c) - 65
def i2l(i): return ALPHABET[i % 26]

class Rotor:
    def __init__(self, name, wiring, notch_letters, ring=1, pos='A'):
        self.name = name
        self.wiring = [l2i(c) for c in wiring]
        self.inverse = [0]*26
        for i,w in enumerate(self.wiring):
            self.inverse[w] = i
        self.notches = set(l2i(c) for c in notch_letters) if notch_letters else set()
        self.ring = (int(ring)-1) % 26
        self.pos = l2i(pos.upper()[0]) if pos else 0

    def step(self):
        self.pos = (self.pos + 1) % 26

    def at_notch(self):
        # notch is evaluated relative to current window letter (position)
        return self.pos in self.notches

    def forward(self, c):
        # right->left
        shifted = (c + self.pos - self.ring) % 26
        wired = self.wiring[shifted]
        out = (wired - self.pos + self.ring) % 26
        return out

    def backward(self, c):
        shifted = (c + self.pos - self.ring) % 26
        wired = self.inverse[shifted]
        out = (wired - self.pos + self.ring) % 26
        return out

class Reflector:
    def __init__(self, wiring):
        self.wiring = [l2i(c) for c in wiring]
    def reflect(self, c): return self.wiring[c]

class Plugboard:
    def __init__(self, pairs=None):
        self.map = list(range(26))
        if pairs:
            for p in pairs:
                a,l = p[0], p[1]
                ai, li = l2i(a), l2i(l)
                self.map[ai] = li
                self.map[li] = ai
    def swap(self, c): return self.map[c]

class EnigmaM4:
    def __init__(self, wheel_names, positions, rings, reflector, plug_pairs):
        """
        wheel_names: list of 4 names, left->right. Example: ['BETA','II','IV','I']
        positions: list of 4 letters left->right
        rings: list of 4 ints 1..26 left->right
        reflector: one of REFLECTORS keys; use 'B_THIN' or 'C_THIN' for M4 thin reflectors
        plug_pairs: ["AB","CD", ...]
        """
        self.rotors = []
        for name,pos,ring in zip(wheel_names, positions, rings):
            if name not in ROTOR_SPECS:
                raise ValueError("Unknown rotor: "+name)
            wiring, notch = ROTOR_SPECS[name]
            self.rotors.append(Rotor(name, wiring, notch, ring=ring, pos=pos))
        if reflector not in REFLECTORS:
            raise ValueError("Unknown reflector: "+reflector)
        self.reflector = Reflector(REFLECTORS[reflector])
        self.plugboard = Plugboard(plug_pairs)

    def step_rotors(self):
        """
        For M4: only the rightmost THREE rotors step (the leftmost 'Greek' rotor does not step).
        Implement classical double-stepping on the rightmost three (indexes 1,2,3 if rotors[0] is the fixed thin).
        Rotors are stored left->right in self.rotors.
        """
        # index: 0=thin (non-stepping), 1=left, 2=middle, 3=right
        left, middle, right = self.rotors[1], self.rotors[2], self.rotors[3]

        # double-step logic among these three:
        # if middle at notch OR right at notch => middle steps
        # if middle at notch (before stepping) => left steps
        mid_will_step = right.at_notch() or middle.at_notch()
        if mid_will_step:
            middle.step()
        if middle.at_notch():
            left.step()
        # right rotor always steps
        right.step()
        # leftmost rotor (rotors[0], Beta/Gamma) NEVER steps automatically

    def process_char(self, ch):
        if ch not in ALPHABET:
            return ch
        self.step_rotors()
        c = l2i(ch)
        c = self.plugboard.swap(c)
        # right->left through rotors
        for rotor in reversed(self.rotors):
            c = rotor.forward(c)
        c = self.reflector.reflect(c)
        # back left->right
        for rotor in self.rotors:
            c = rotor.backward(c)
        c = self.plugboard.swap(c)
        return i2l(c)

    def encrypt(self, text):
        res = []
        for ch in text.upper():
            if ch in ALPHABET:
                res.append(self.process_char(ch))
            else:
                res.append(ch)
        return ''.join(res)

    def get_settings_dict(self):
        # Export the settings necessary to reconstruct machine
        return {
            "wheels": [r.name for r in self.rotors],   # left->right
            "positions": [i2l(r.pos) for r in self.rotors],
            "rings": [(r.ring+1) for r in self.rotors],
            "reflector": next(k for k,v in REFLECTORS.items() if v==''.join(i2l(x) for x in self.reflector.wiring)) if True else None,
            "plugboard": [i2l(i)+i2l(self.plugboard.map[i]) for i in range(26) if i < self.plugboard.map[i]]
        }

    @classmethod
    def from_settings_dict(cls, d):
        wheels = d.get("wheels", ["BETA","I","II","III"])
        positions = d.get("positions", ["A","A","A","A"])
        rings = d.get("rings", [1,1,1,1])
        reflector = d.get("reflector", "B_THIN")
        plugs = d.get("plugboard", [])
        # normalize plug pairs like "AB"
        plugs_norm = []
        for p in plugs:
            if isinstance(p,str) and len(p)==2:
                plugs_norm.append(p.upper())
        return cls(wheels, positions, rings, reflector, plugs_norm)

# ---------------- GUI ----------------

class EnigmaM4GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Enigma M4 Simulator")
        self.available_wheels = ["BETA","GAMMA","I","II","III","IV","V","VI","VII","VIII"]
        self.available_reflectors = ["B_THIN","C_THIN","B","C"]

        # UI state variables
        self.w1 = tk.StringVar(value="BETA")
        self.w2 = tk.StringVar(value="I")
        self.w3 = tk.StringVar(value="II")
        self.w4 = tk.StringVar(value="III")
        self.p1 = tk.StringVar(value="A")
        self.p2 = tk.StringVar(value="A")
        self.p3 = tk.StringVar(value="A")
        self.p4 = tk.StringVar(value="A")
        self.r1 = tk.IntVar(value=1)
        self.r2 = tk.IntVar(value=1)
        self.r3 = tk.IntVar(value=1)
        self.r4 = tk.IntVar(value=1)
        self.reflector = tk.StringVar(value="B_THIN")
        self.plugboard = tk.StringVar(value="")  # e.g. "AT BS CM"
        self.create_widgets()

    def create_widgets(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.grid(row=0, column=0, sticky="nsew")

        rotor_frame = ttk.LabelFrame(frm, text="Wheels (left → right). Leftmost is Beta/Gamma (non-stepping).")
        rotor_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        # wheel selectors & pos/ring
        for i, (wvar, pvar, rvar, label) in enumerate([
            (self.w1, self.p1, self.r1, "4th (thin)"),
            (self.w2, self.p2, self.r2, "Left"),
            (self.w3, self.p3, self.r3, "Middle"),
            (self.w4, self.p4, self.r4, "Right"),
        ]):
            col = i
            ttk.Label(rotor_frame, text=label).grid(row=0, column=col)
            ttk.OptionMenu(rotor_frame, wvar, wvar.get(), *self.available_wheels).grid(row=1, column=col)
            ttk.Entry(rotor_frame, width=3, textvariable=pvar).grid(row=2, column=col)
            ttk.Spinbox(rotor_frame, from_=1, to=26, width=4, textvariable=rvar).grid(row=3, column=col)

        # reflector & plugboard
        cfg = ttk.Frame(frm)
        cfg.grid(row=1, column=0, sticky="ew", pady=(4,0))
        ttk.Label(cfg, text="Reflector").grid(row=0, column=0, sticky="w")
        ttk.OptionMenu(cfg, self.reflector, self.reflector.get(), *self.available_reflectors).grid(row=0, column=1, sticky="w")
        ttk.Label(cfg, text="Plugboard pairs (space/comma separated, e.g. AT BS CM)").grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Entry(cfg, width=50, textvariable=self.plugboard).grid(row=2, column=0, columnspan=2, sticky="w")

        # IO
        io = ttk.LabelFrame(frm, text="Input / Output")
        io.grid(row=2, column=0, sticky="nsew", pady=6)
        self.input_text = tk.Text(io, height=8, width=72)
        self.input_text.grid(row=0, column=0, padx=4, pady=4)
        self.output_text = tk.Text(io, height=8, width=72)
        self.output_text.grid(row=1, column=0, padx=4, pady=4)

        # buttons
        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, sticky="ew")
        ttk.Button(btns, text="Encrypt/Decrypt", command=self.encrypt_action).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Export (two files)", command=self.export_two_files).grid(row=0, column=1, padx=4)
        ttk.Button(btns, text="Import (two files)", command=self.import_two_files).grid(row=0, column=2, padx=4)
        ttk.Button(btns, text="Clear", command=self.clear_action).grid(row=0, column=3, padx=4)
        ttk.Button(btns, text="Randomize positions", command=self.randomize_positions).grid(row=0, column=4, padx=4)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(frm, textvariable=self.status).grid(row=4, column=0, sticky="w", pady=(6,0))

    def parse_plugs(self, txt):
        txt = txt.strip().upper()
        if not txt: return []
        for sep in [',',';','/']: txt = txt.replace(sep, ' ')
        parts = [p.strip() for p in txt.split() if p.strip()]
        pairs = []
        used = set()
        for p in parts:
            p = p.replace('-', '')
            if len(p)==2 and p[0]!=p[1] and p[0] not in used and p[1] not in used:
                pairs.append(p)
                used.add(p[0]); used.add(p[1])
        return pairs

    def build_machine_from_ui(self):
        wheels = [self.w1.get(), self.w2.get(), self.w3.get(), self.w4.get()]
        positions = [self.p1.get().upper()[:1] or 'A',
                     self.p2.get().upper()[:1] or 'A',
                     self.p3.get().upper()[:1] or 'A',
                     self.p4.get().upper()[:1] or 'A']
        rings = [int(self.r1.get()), int(self.r2.get()), int(self.r3.get()), int(self.r4.get())]
        reflector = self.reflector.get()
        plugs = self.parse_plugs(self.plugboard.get())
        return EnigmaM4(wheels, positions, rings, reflector, plugs)

    def encrypt_action(self):
        try:
            mach = self.build_machine_from_ui()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid configuration: {e}")
            return
        txt = self.input_text.get("1.0", tk.END).strip('\n')
        out = mach.encrypt(txt)
        self.output_text.delete("1.0", tk.END); self.output_text.insert(tk.END, out)
        self.status.set("Encrypted/Decrypted (rotors advanced).")

    def clear_action(self):
        self.input_text.delete("1.0", tk.END); self.output_text.delete("1.0", tk.END)
        self.status.set("Cleared")

    def randomize_positions(self):
        import random
        self.p1.set(random.choice(ALPHABET))
        self.p2.set(random.choice(ALPHABET))
        self.p3.set(random.choice(ALPHABET))
        self.p4.set(random.choice(ALPHABET))
        self.status.set("Randomized positions")

    def export_two_files(self):
        # Build machine and ensure output exists
        try:
            mach = self.build_machine_from_ui()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid configuration: {e}")
            return
        ciphertext = self.output_text.get("1.0", tk.END).strip()
        if not ciphertext:
            messagebox.showinfo("Nothing to export", "Run Encrypt/Decrypt first to produce ciphertext.")
            return

        # Ask user for base filename (we'll add suffixes)
        base = filedialog.asksaveasfilename(title="Choose base filename (no extension). We'll create *_message.txt and *_settings.json",
                                            defaultextension="", filetypes=[("Any files","*.*")])
        if not base:
            return
        # ensure no extension: strip extension if user provided
        base = os.path.splitext(base)[0]
        msg_path = base + "_message.txt"
        settings_path = base + "_settings.json"

        # write message file (ciphertext only)
        try:
            with open(msg_path, "w", encoding="utf-8") as f:
                f.write(ciphertext)
        except Exception as e:
            messagebox.showerror("Write error", f"Failed to write message file: {e}")
            return

        # write settings JSON with all necessary items
        settings = {
            "wheels": [r.name for r in mach.rotors],
            "positions": [i2l(r.pos) for r in mach.rotors],
            "rings": [(r.ring+1) for r in mach.rotors],
            "reflector": self.reflector.get(),
            "plugboard": self.parse_plugs(self.plugboard.get())
        }
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            messagebox.showerror("Write error", f"Failed to write settings file: {e}")
            return

        messagebox.showinfo("Exported", f"Two files created:\n\n{msg_path}\n{settings_path}")
        self.status.set(f"Exported message and settings to:\n{msg_path}\n{settings_path}")

    def import_two_files(self):
        # ask user to select settings json; then select message file (or vice versa)
        settings_file = filedialog.askopenfilename(title="Select settings JSON file", filetypes=[("JSON","*.json"),("All","*.*")])
        if not settings_file:
            return
        msg_file = filedialog.askopenfilename(title="Select message file (ciphertext)", filetypes=[("Text","*.txt;*.text"),("All","*.*")])
        if not msg_file:
            return

        # read settings
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception as e:
            messagebox.showerror("Read error", f"Failed to read settings JSON: {e}")
            return

        # validate and apply to UI
        try:
            wheels = settings["wheels"]
            positions = settings["positions"]
            rings = settings["rings"]
            reflector = settings.get("reflector", "B_THIN")
            plugs = settings.get("plugboard", [])
            # set UI (expect lists of length 4)
            if len(wheels) != 4 or len(positions) != 4 or len(rings) != 4:
                raise ValueError("Settings JSON must contain 4 wheels, 4 positions and 4 rings.")
            self.w1.set(wheels[0]); self.w2.set(wheels[1]); self.w3.set(wheels[2]); self.w4.set(wheels[3])
            self.p1.set(positions[0]); self.p2.set(positions[1]); self.p3.set(positions[2]); self.p4.set(positions[3])
            self.r1.set(int(rings[0])); self.r2.set(int(rings[1])); self.r3.set(int(rings[2])); self.r4.set(int(rings[3]))
            self.reflector.set(reflector)
            self.plugboard.set(' '.join(plugs))
        except Exception as e:
            messagebox.showerror("Settings error", f"Invalid settings JSON: {e}")
            return

        # read ciphertext into input box so user can press Encrypt/Decrypt to decode
        try:
            with open(msg_file, "r", encoding="utf-8") as f:
                ct = f.read()
        except Exception as e:
            messagebox.showerror("Read error", f"Failed to read message file: {e}")
            return

        self.input_text.delete("1.0", tk.END); self.input_text.insert(tk.END, ct)
        self.output_text.delete("1.0", tk.END)
        self.status.set("Imported settings and message. Press Encrypt/Decrypt to decode.")

def main():
    root = tk.Tk()
    app = EnigmaM4GUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
