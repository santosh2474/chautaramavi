#!/usr/bin/env python3
"""
Soundboard Editor  -  Chautara Mavi Assembly Soundboard
=======================================================
A small GUI to manage the sound pads of soundboard.html.

You can:
  * See all current sound cards
  * Add a new card (with an icon/logo + category + optional song upload)
  * Edit an existing card  (rename, re-icon, re-categorise, swap the song)
  * Delete a card
  * Reorder cards (Move Up / Move Down) — list order is the left-to-right
    order shown on the board
  * Save - writes the changes straight into soundboard.html

Once saved, open/refresh soundboard.html in your browser and the pad
changes are live. Uploaded songs/music are copied into the sounds/
folder next to this file, and the card simply points to that file
(e.g. sounds/my-song.mp3), so the board still works fully offline.

Run with:  python soundboard_editor.py
"""
import base64
import html
import os
import re
import shutil
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "soundboard.html"
SOUNDS_DIR = BASE_DIR / "sounds"   # uploaded songs/music are copied here

CATEGORIES = ["drum", "bell", "song", "anthem", "transition", "applause", "custom"]
SYNTH_KEYS = [
    "drumroll", "snare", "kick", "bell", "chime",
    "morningSong", "nationalAnthem", "schoolSong", "transition",
    "applause", "attention", "rimshot", "custom",
]
ICON_PALETTE = [
    "🥁", "🔔", "✨", "🎵", "🎶", "🚩", "🎓", "🏫", "⏳", "👏",
    "📢", "🎯", "🔊", "📯", "🎺", "🎤", "🎻", "📣", "🎉", "🛎️",
    "🌅", "🇳🇵",
]
AUDIO_FILETYPES = [
    ("Audio files", "*.mp3 *.wav *.ogg *.oga *.m4a *.aac *.flac *.opus"),
    ("All files", "*.*"),
]

CARD_RE = re.compile(
    r'<div class="sound-card\s+([a-z-]+)" data-sound="([^"]*)" data-label="([^"]*)"'
    r'(?:\s+data-type="([^"]*)")?(?:\s+data-src="([^"]*)")?>\s*'
    r"<i>(.*?)</i>\s*"
    r'<span class="name">(.*?)</span>\s*'
    r"<small>(.*?)</small>\s*"
    r"</div>",
    re.S,
)
PAD_OPENER = '<section class="pad-grid" id="padGrid">'


# ======================================================================
#  HTML logic  (kept separate from the GUI so it is easy to test)
# ======================================================================

def parse_cards(html_text):
    """Return a list of card dicts found inside the pad-grid section."""
    cards = []
    for m in CARD_RE.finditer(html_text):
        cat, sound, label, ctype, src, icon, name, desc = [g or "" for g in m.groups()]
        cards.append({
            "cat": cat if cat in CATEGORIES else "custom",
            "sound": sound,
            "label": html.unescape(label),
            "desc": html.unescape(desc),
            "icon": html.unescape(icon),
            "type": ctype if ctype == "audio" else "synth",
            "src": src or None,
        })
    return cards


def _esc(value):
    return html.escape(value or "", quote=True)


def render_card(c):
    attrs = (
        f'class="sound-card {_esc(c["cat"])}" '
        f'data-sound="{_esc(c["sound"])}" '
        f'data-label="{_esc(c["label"])}"'
    )
    if c.get("type") == "audio" and c.get("src"):
        attrs += f' data-type="audio" data-src="{c["src"]}"'
    return (
        f'            <div {attrs}>\n'
        f'                <i>{_esc(c["icon"])}</i>\n'
        f'                <span class="name">{_esc(c["label"])}</span>\n'
        f'                <small>{_esc(c["desc"])}</small>\n'
        f"            </div>"
    )


def build_html(html_text, cards):
    """Replace the pad-grid contents of html_text with the given cards."""
    start = html_text.index(PAD_OPENER) + len(PAD_OPENER)
    end = html_text.index("</section>", start)
    body = "\n" + "\n".join(render_card(c) for c in cards) + "\n        "
    return html_text[:start] + body + html_text[end:]


def read_html():
    with open(HTML_PATH, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_html(html_text):
    with open(HTML_PATH, "w", encoding="utf-8", newline="") as fh:
        fh.write(html_text)


def sanitize_filename(name):
    """Make a safe file name, e.g. 'My Song (v2).mp3' -> 'my-song-v2.mp3'."""
    parts = name.rsplit(".", 1)
    if len(parts) == 2 and parts[1]:
        stem, ext = parts
    else:
        stem, ext = name, ""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._") or "song"
    safe = safe.lower()
    return f"{safe}.{ext}" if ext else safe


def _unique_path(path):
    """Return the path, adding _2, _3, ... when the file already exists."""
    if not path.exists():
        return path
    stem, ext = os.path.splitext(path.name)
    for i in range(2, 1000):
        cand = path.with_name(f"{stem}_{i}{ext}")
        if not cand.exists():
            return cand
    raise OSError(f"Too many files with the same name: {path.name}")


def import_audio_file(file_path):
    """Copy an audio file into the sounds/ folder next to the HTML.

    Returns (relative_path, size_bytes), e.g. ('sounds/my-song.mp3', 2812340).
    A file that already lives inside sounds/ is used as-is (no duplicate copy).
    """
    src = Path(file_path)
    if src.parent.resolve() == SOUNDS_DIR.resolve():
        return f"sounds/{src.name}", src.stat().st_size
    SOUNDS_DIR.mkdir(exist_ok=True)
    dest = _unique_path(SOUNDS_DIR / sanitize_filename(src.name))
    shutil.copyfile(src, dest)
    return f"sounds/{dest.name}", dest.stat().st_size


EXT_BY_MIME = {
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3",
    "audio/wav": ".wav", "audio/x-wav": ".wav",
    "audio/ogg": ".ogg", "audio/oga": ".ogg", "audio/opus": ".opus",
    "audio/mp4": ".m4a", "audio/aac": ".aac", "audio/flac": ".flac",
}


def migrate_audio_to_file(data_uri, base_name):
    """Save an embedded base64 song from an old save into sounds/.

    Returns the relative path (e.g. 'sounds/national-anthem.mp3').
    """
    m = re.match(r"^data:([^;,]+);base64,(.+)$", data_uri, re.S)
    if not m:
        raise ValueError("Invalid embedded audio data (not a base64 data URI).")
    mime, b64 = m.group(1), m.group(2)
    data = base64.b64decode(b64)
    ext = EXT_BY_MIME.get(mime.lower(), ".mp3")
    SOUNDS_DIR.mkdir(exist_ok=True)
    dest = _unique_path(SOUNDS_DIR / (sanitize_filename(base_name) + ext))
    dest.write_bytes(data)
    return f"sounds/{dest.name}"


def fmt_size(nbytes):
    mb = nbytes / (1024.0 * 1024.0)
    return f"{mb:.1f} MB" if mb >= 1 else f"{nbytes / 1024.0:.0f} KB"


# ======================================================================
#  GUI
# ======================================================================

class SoundboardEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Soundboard Editor - Chautara Mavi")
        self.geometry("900x720")
        self.minsize(780, 620)

        self.cards = []          # all cards (list order == pad order in the HTML)
        self.editing_index = None  # None while adding a brand-new card
        self.pending_audio = None  # (relative_path, size_bytes, filename) chosen in the dialog

        self.var_icon = tk.StringVar(value="🎵")
        self.var_label = tk.StringVar()
        self.var_cat = tk.StringVar(value="custom")
        self.var_desc = tk.StringVar()
        self.var_type = tk.StringVar(value="synth")
        self.var_synth = tk.StringVar(value="custom")
        self.audio_info = tk.StringVar(value="No audio file attached")

        self._build_ui()
        self.reload_from_file()

    # ----------------------------------------------------------------
    #  UI construction
    # ----------------------------------------------------------------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        head = ttk.Frame(self, padding=(12, 10, 12, 6))
        head.grid(row=0, column=0, sticky="ew")
        ttk.Label(head, text="🎛️  Assembly Soundboard — pad manager",
                  font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Label(head, text="Edits are written straight into soundboard.html",
                  foreground="#666").pack(side="right")

        main = ttk.Frame(self, padding=(12, 6))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        # ---- left: card list ----
        left = ttk.LabelFrame(main, text=" Sound cards (pad order) ", padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(left, activestyle="dotbox", exportselection=False)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.listbox.bind("<Double-Button-1>", lambda e: self.edit_selected())
        self.listbox.bind("<Alt-Up>", lambda e: self._move_and_break(-1))
        self.listbox.bind("<Alt-Down>", lambda e: self._move_and_break(1))

        btns = ttk.Frame(left)
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for i, (txt, cmd) in enumerate([
            ("＋  Add New", self.start_new),
            ("✎  Edit", self.edit_selected),
            ("🗑  Delete", self.delete_selected),
            ("↻  Reload", self.reload_from_file),
        ]):
            b = ttk.Button(btns, text=txt, command=cmd)
            b.grid(row=0, column=i, sticky="ew", padx=2)
            btns.columnconfigure(i, weight=1)

        move_row = ttk.Frame(left)
        move_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(move_row, text="▲  Move Up",
                   command=self.move_up).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ttk.Button(move_row, text="▼  Move Down",
                   command=self.move_down).grid(row=0, column=1, sticky="ew", padx=(2, 0))
        move_row.columnconfigure(0, weight=1)
        move_row.columnconfigure(1, weight=1)
        ttk.Label(left, text="Order = left-to-right on the board (first cards get hotkeys 1–0,-,=)",
                  foreground="#777").grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # ---- right: card form ----
        form = ttk.LabelFrame(main, text=" Card details ", padding=10)
        form.grid(row=0, column=1, sticky="nsew")
        form.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(form, text="Card name:").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self.var_label, width=30).grid(row=r, column=1, sticky="ew", pady=3)
        r += 1

        ttk.Label(form, text="Category:").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Combobox(form, textvariable=self.var_cat, values=CATEGORIES,
                     state="readonly").grid(row=r, column=1, sticky="ew", pady=3)
        r += 1

        ttk.Label(form, text="Description:").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self.var_desc, width=30).grid(row=r, column=1, sticky="ew", pady=3)
        r += 1

        # icon row
        ttk.Label(form, text="Icon / logo:").grid(row=r, column=0, sticky="nw", pady=(6, 0))
        icon_box = ttk.Frame(form)
        icon_box.grid(row=r, column=1, sticky="ew", pady=3)
        icon_box.columnconfigure(1, weight=1)
        self.icon_preview = ttk.Label(icon_box, text="🎵", font=("Segoe UI Emoji", 22),
                                      anchor="center", relief="groove", width=4)
        self.icon_preview.grid(row=0, column=0, rowspan=2, padx=(0, 8))
        ttk.Entry(icon_box, textvariable=self.var_icon, width=12).grid(row=0, column=1, sticky="ew")
        ttk.Label(icon_box, text="type any emoji, or pick one below", foreground="#888").grid(row=1, column=1, sticky="w")
        palette = ttk.Frame(form)
        palette.grid(row=r + 1, column=1, sticky="ew", pady=(0, 4))
        for i, emoji in enumerate(ICON_PALETTE):
            b = tk.Button(palette, text=emoji, width=3, relief="flat", overrelief="raised",
                          font=("Segoe UI Emoji", 11),
                          command=lambda e=emoji: self._pick_icon(e))
            b.grid(row=i // 11, column=i % 11, padx=1, pady=1, sticky="nsew")
            palette.columnconfigure(i % 11, weight=1, uniform="ico")
        r += 2

        # sound type
        ttk.Separator(form, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1
        ttk.Label(form, text="Sound source:").grid(row=r, column=0, sticky="nw", pady=3)

        type_box = ttk.Frame(form)
        type_box.grid(row=r, column=1, sticky="ew", pady=3)
        ttk.Radiobutton(type_box, text="Synth sound (built-in)",
                        variable=self.var_type, value="synth",
                        command=self._sync_audio_ui).pack(anchor="w")
        self.synth_combo = ttk.Combobox(type_box, textvariable=self.var_synth,
                                        values=SYNTH_KEYS, state="readonly", width=20)
        self.synth_combo.pack(anchor="w", padx=(18, 0), pady=(2, 6))
        ttk.Radiobutton(type_box, text="Uploaded music / song",
                        variable=self.var_type, value="audio",
                        command=self._sync_audio_ui).pack(anchor="w")

        audio_row = ttk.Frame(type_box)
        audio_row.pack(anchor="w", fill="x", padx=(18, 0), pady=(2, 0))
        audio_row.columnconfigure(2, weight=1)
        ttk.Button(audio_row, text="Browse…", command=self.browse_audio).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(audio_row, text="Clear", command=self.clear_audio).grid(row=0, column=1, padx=(0, 6))
        ttk.Label(audio_row, textvariable=self.audio_info, foreground="#333",
                  wraplength=260).grid(row=0, column=2, sticky="w")
        r += 1

        # save
        ttk.Separator(form, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1
        save_row = ttk.Frame(form)
        save_row.grid(row=r, column=0, columnspan=2, sticky="ew")
        self.save_btn = ttk.Button(save_row, text="💾  Save to soundboard.html",
                                   command=self.save_cards, style="Accent.TButton")
        self.save_btn.pack(side="left")
        self.status = ttk.Label(self, text="Ready", relief="sunken", anchor="w", padding=(8, 4))
        self.status.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 6))

        # accent style for the save button
        ttk.Style(self).configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    # ----------------------------------------------------------------
    #  helpers
    # ----------------------------------------------------------------
    def _pick_icon(self, emoji):
        self.var_icon.set(emoji)
        self.icon_preview.configure(text=emoji)

    def _sync_audio_ui(self):
        """Enable/disable the right controls while switching sound type."""
        is_audio = self.var_type.get() == "audio"
        self.synth_combo.state(["disabled" if is_audio else "!disabled"])

    def _list_text(self, c):
        kind = "audio" if c.get("type") == "audio" else "synth"
        return f'{c.get("icon", "🎵")}  {c.get("label", "?")}   [{kind}]'

    def refresh_list(self):
        self.listbox.delete(0, "end")
        for c in self.cards:
            self.listbox.insert("end", self._list_text(c))
        if self.editing_index is not None and self.editing_index < len(self.cards):
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(self.editing_index)
            self.listbox.see(self.editing_index)

    def set_status(self, msg):
        self.status.configure(text=msg)

    def _clear_form(self):
        self.var_label.set("")
        self.var_cat.set("custom")
        self.var_desc.set("")
        self.var_icon.set("🎵")
        self.icon_preview.configure(text="🎵")
        self.var_type.set("synth")
        self.var_synth.set("custom")
        self.pending_audio = None
        self.audio_info.set("No audio file attached")
        self._sync_audio_ui()

    def _selected_index(self):
        sel = self.listbox.curselection()
        if not sel:
            return None
        # prefer the actively focused item; fall back to the last selected
        active = self.listbox.index("active")
        return active if active in sel else sel[-1]

    def _form_to_card(self, existing):
        """Build a card dict from the current form. Raises ValueError if invalid."""
        label = self.var_label.get().strip()
        if not label:
            raise ValueError("Please enter a card name.")

        stype = self.var_type.get()
        icon = self.var_icon.get().strip() or "🎵"

        if stype == "audio":
            if self.pending_audio:
                src = self.pending_audio[0]
                sound = "audio_" + uuid.uuid4().hex[:6]
            elif existing and existing.get("type") == "audio" and existing.get("src"):
                src = existing["src"]
                sound = existing.get("sound") or ("audio_" + uuid.uuid4().hex[:6])
            else:
                raise ValueError("Upload a music/song file, or switch to a synth sound.")
        else:
            src = None
            sound = self.var_synth.get() or "custom"

        return {
            "cat": self.var_cat.get() or "custom",
            "sound": sound,
            "label": label,
            "desc": self.var_desc.get().strip(),
            "icon": icon,
            "type": stype,
            "src": src,
        }

    def _save_to_file(self, message):
        try:
            # any song still embedded as base64 (e.g. from an older save)
            # is moved into the sounds/ folder on the next save
            converted = 0
            for c in self.cards:
                if c.get("type") == "audio" and c.get("src") and c["src"].startswith("data:"):
                    c["src"] = migrate_audio_to_file(c["src"], c.get("label") or "song")
                    converted += 1
            write_html(build_html(read_html(), self.cards))
            suffix = f"  (moved {converted} embedded song into sounds/)" if converted else ""
            self.set_status(
                f"{message}  →  saved to soundboard.html{suffix} (refresh the browser tab to see it)")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save failed", str(exc))
            self.set_status("Save failed")

    # ----------------------------------------------------------------
    #  actions
    # ----------------------------------------------------------------
    def reload_from_file(self):
        if not HTML_PATH.exists():
            messagebox.showerror("Missing file",
                                 f"Could not find soundboard.html next to this editor:\n{HTML_PATH}")
            return
        try:
            self.cards = parse_cards(read_html())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Read failed", str(exc))
            self.cards = []
        self.editing_index = None
        self._clear_form()
        self.refresh_list()
        self.set_status(f"Loaded {len(self.cards)} sound cards · {HTML_PATH.name}")

    def start_new(self):
        self.editing_index = None
        self._clear_form()
        self.set_status("Adding a new card — fill in the details and press Save.")
        self.listbox.selection_clear(0, "end")

    def edit_selected(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.cards):
            messagebox.showinfo("Edit", "Select a card from the list first.")
            return
        c = self.cards[idx]
        self.editing_index = idx
        self.var_label.set(c["label"])
        self.var_cat.set(c["cat"])
        self.var_desc.set(c["desc"])
        self.var_icon.set(c["icon"])
        self.icon_preview.configure(text=c["icon"])
        self.var_type.set("audio" if c.get("type") == "audio" else "synth")
        self.var_synth.set(c["sound"] if c.get("type") != "audio" else "custom")
        self.pending_audio = None
        if c.get("type") == "audio" and c.get("src"):
            self.audio_info.set("Uploaded song is attached (keep it, or Browse to replace / Clear to remove).")
        else:
            self.audio_info.set("No audio file attached")
        self._sync_audio_ui()
        self.set_status(f"Editing: {self._list_text(c)}")

    def delete_selected(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.cards):
            messagebox.showinfo("Delete", "Select a card from the list first.")
            return
        name = self.cards[idx]["label"]
        if not messagebox.askyesno("Delete card", f'Remove "{name}" from the soundboard?'):
            return
        del self.cards[idx]
        self.editing_index = None
        self._clear_form()
        self.refresh_list()
        self._save_to_file(f'Deleted "{name}".')

    def _move_card(self, delta):
        """Move the selected card up (-1) or down (+1) and save the new order."""
        idx = self._selected_index()
        if idx is None or idx >= len(self.cards):
            messagebox.showinfo("Reorder", "Select a card from the list first.")
            return
        new = idx + delta
        if new < 0 or new >= len(self.cards):
            self.set_status("Already at the top/bottom of the list.")
            return
        self.cards[idx], self.cards[new] = self.cards[new], self.cards[idx]
        if self.editing_index == idx:
            self.editing_index = new
        elif self.editing_index == new:
            self.editing_index = idx
        moved = self.cards[new]["label"]
        self.refresh_list()
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(new)
        self.listbox.see(new)
        self._save_to_file(f'Moved "{moved}" {"up" if delta < 0 else "down"}.')

    def move_up(self):
        self._move_card(-1)

    def move_down(self):
        self._move_card(1)

    def _move_and_break(self, delta):
        """Keyboard handler: Alt+Up / Alt+Down, returns 'break' to stop default."""
        self._move_card(delta)
        return "break"

    def save_cards(self):
        if self.editing_index is None:
            try:
                card = self._form_to_card(None)
            except ValueError as exc:
                messagebox.showerror("Save", str(exc))
                return
            self.cards.append(card)
            self.editing_index = len(self.cards) - 1
            self.refresh_list()
            self._save_to_file(f'Added "{card["label"]}".')
        else:
            idx = self.editing_index
            existing = self.cards[idx]
            try:
                card = self._form_to_card(existing)
            except ValueError as exc:
                messagebox.showerror("Save", str(exc))
                return
            self.cards[idx] = card
            self.refresh_list()
            self._save_to_file(f'Updated "{card["label"]}".')

    def browse_audio(self):
        initial = SOUNDS_DIR if SOUNDS_DIR.exists() else BASE_DIR
        path = filedialog.askopenfilename(
            title="Choose a music / song file (it is copied into the sounds/ folder)",
            initialdir=str(initial),
            filetypes=AUDIO_FILETYPES,
        )
        if not path:
            return
        try:
            rel, size = import_audio_file(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Import failed", str(exc))
            return
        self.pending_audio = (rel, size, os.path.basename(path))
        self.audio_info.set(f"{os.path.basename(path)}  ·  {fmt_size(size)}  (saved into sounds/)")
        self.set_status("Song copied into the sounds/ folder — press Save to attach it.")

    def clear_audio(self):
        self.pending_audio = None
        self.audio_info.set("No audio file attached")


def main():
    app = SoundboardEditor()
    app.mainloop()


if __name__ == "__main__":
    main()