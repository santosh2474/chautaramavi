import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from bs4 import BeautifulSoup
import os
import shutil
import uuid
import webbrowser
import subprocess
import platform

HTML_FILE = "notice.html"
UPLOAD_FOLDER = "notices"

selected_notice = None
current_file_path = None
search_mode = "title"
is_maximized = True

# -------------------- Global Scaling Configuration --------------------
SCALING_SETTINGS = {
    "window_scale": 1.0,
    "font_scale": 1.0,
    "padding_scale": 1.0,
    "button_scale": 1.0,
    "card_scale": 1.4,
    "input_scale": 1.0,
}

# -------------------- Responsive Configuration --------------------
class ResponsiveConfig:
    def __init__(self, root):
        self.root = root
        self.base_width = 1366
        self.base_height = 768
        self.scale_factor = self.calculate_scale_factor()
        
    def calculate_scale_factor(self):
        """Calculate scale factor based on screen resolution"""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        width_scale = screen_width / self.base_width
        height_scale = screen_height / self.base_height
        
        scale = min(width_scale, height_scale)
        
        if scale < 0.7:
            scale = 0.7
        elif scale > 1.2:
            scale = 1.2
            
        return scale * SCALING_SETTINGS["window_scale"]
    
    def scale(self, value, scale_type="general"):
        """Scale a value based on screen resolution and scaling settings"""
        if scale_type == "font":
            return int(value * self.scale_factor * 0.85 * SCALING_SETTINGS["font_scale"])
        elif scale_type == "padding":
            return int(value * self.scale_factor * 0.9 * SCALING_SETTINGS["padding_scale"])
        elif scale_type == "button":
            return int(value * self.scale_factor * 0.9 * SCALING_SETTINGS["button_scale"])
        elif scale_type == "card":
            return int(value * self.scale_factor * 0.9 * SCALING_SETTINGS["card_scale"])
        elif scale_type == "input":
            return int(value * self.scale_factor * 0.9 * SCALING_SETTINGS["input_scale"])
        else:
            return int(value * self.scale_factor * 0.9)
    
    def font_size(self, base_size):
        """Get responsive font size"""
        scaled_size = base_size * self.scale_factor * 0.85 * SCALING_SETTINGS["font_scale"]
        return max(int(scaled_size), 9)

# Initialize responsive config early
temp_root = tk.Tk()
temp_root.withdraw()
resp = ResponsiveConfig(temp_root)
temp_root.destroy()

# -------------------- Scaling Settings Dialog --------------------
def show_scaling_dialog():
    """Show dialog to adjust scaling settings"""
    scaling_window = tk.Toplevel(root)
    scaling_window.title("⚙️ UI Scaling Settings")
    scaling_window.geometry(f"{resp.scale(500)}x{resp.scale(500)}")
    scaling_window.configure(bg=COLORS["light"])
    scaling_window.transient(root)
    scaling_window.grab_set()
    
    scaling_window.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (resp.scale(500) // 2)
    y = (root.winfo_screenheight() // 2) - (resp.scale(500) // 2)
    scaling_window.geometry(f'{resp.scale(500)}x{resp.scale(500)}+{x}+{y}')
    
    # Header
    header = tk.Frame(scaling_window, bg=COLORS["primary"], height=resp.scale(70))
    header.pack(fill="x")
    header.pack_propagate(False)
    
    tk.Label(header, text="⚙️ UI Scaling Settings", bg=COLORS["primary"], fg="white",
             font=("Segoe UI", resp.font_size(16), "bold")).pack(expand=True)
    
    # Content
    content = tk.Frame(scaling_window, bg=COLORS["light"], padx=resp.scale(30), pady=resp.scale(20))
    content.pack(fill="both", expand=True)
    
    # Scaling controls
    tk.Label(content, text="Adjust UI element sizes:", bg=COLORS["light"], fg=COLORS["dark"],
             font=("Segoe UI", resp.font_size(12), "bold")).pack(anchor="w", pady=(0, resp.scale(20)))
    
    # Create sliders for each scaling setting
    sliders = {}
    slider_frame = tk.Frame(content, bg=COLORS["light"])
    slider_frame.pack(fill="both", expand=True)
    
    settings_info = {
        "window_scale": ("Window Size", 0.5, 1.5, 0.1),
        "font_scale": ("Font Size", 0.5, 2.0, 0.1),
        "padding_scale": ("Padding", 0.5, 2.0, 0.1),
        "button_scale": ("Buttons", 0.5, 2.0, 0.1),
        "card_scale": ("Notice Cards", 0.5, 2.0, 0.1),
        "input_scale": ("Input Fields", 0.5, 2.0, 0.1),
    }
    
    for i, (key, (label, min_val, max_val, resolution)) in enumerate(settings_info.items()):
        frame = tk.Frame(slider_frame, bg=COLORS["light"])
        frame.pack(fill="x", pady=resp.scale(10))
        
        # Label and current value
        label_frame = tk.Frame(frame, bg=COLORS["light"])
        label_frame.pack(fill="x")
        
        tk.Label(label_frame, text=label, bg=COLORS["light"], fg=COLORS["dark"],
                 font=("Segoe UI", resp.font_size(10), "bold"), width=15).pack(side="left")
        
        value_label = tk.Label(label_frame, text=f"{SCALING_SETTINGS[key]:.1f}x", 
                              bg=COLORS["light"], fg=COLORS["primary"],
                              font=("Segoe UI", resp.font_size(10), "bold"))
        value_label.pack(side="right")
        
        # Slider
        slider = tk.Scale(frame, from_=min_val, to=max_val, resolution=resolution,
                         orient=tk.HORIZONTAL, length=resp.scale(300),
                         bg=COLORS["light"], fg=COLORS["dark"],
                         highlightthickness=0, troughcolor=COLORS["border"],
                         command=lambda val, k=key, vl=value_label: update_slider_value(k, float(val), vl))
        slider.set(SCALING_SETTINGS[key])
        slider.pack(fill="x")
        sliders[key] = slider
        
        # Min/Max labels
        minmax_frame = tk.Frame(frame, bg=COLORS["light"])
        minmax_frame.pack(fill="x")
        
        tk.Label(minmax_frame, text=f"{min_val:.1f}x", bg=COLORS["light"], fg=COLORS["text_secondary"],
                 font=("Segoe UI", resp.font_size(8))).pack(side="left")
        tk.Label(minmax_frame, text=f"{max_val:.1f}x", bg=COLORS["light"], fg=COLORS["text_secondary"],
                 font=("Segoe UI", resp.font_size(8))).pack(side="right")
    
    def update_slider_value(key, value, value_label):
        SCALING_SETTINGS[key] = value
        value_label.config(text=f"{value:.1f}x")
    
    # Preview button
    def preview_changes():
        messagebox.showinfo("Preview", "Apply settings to see changes in the main window.")
    
    # Apply button
    def apply_scaling():
        # Update responsive config with new scaling
        resp.scale_factor = resp.calculate_scale_factor()
        
        # Rebuild UI with new scaling
        refresh_ui_scaling()
        scaling_window.destroy()
        messagebox.showinfo("Success", "UI scaling applied successfully!")
    
    # Reset button
    def reset_scaling():
        for key in SCALING_SETTINGS:
            SCALING_SETTINGS[key] = 1.0
            sliders[key].set(1.0)
    
    # Button frame
    button_frame = tk.Frame(content, bg=COLORS["light"])
    button_frame.pack(fill="x", pady=resp.scale(20))
    
    create_modern_button(button_frame, "🔍 Preview", preview_changes, COLORS["info"]).pack(side="left", padx=resp.scale(5))
    create_modern_button(button_frame, "🔄 Reset", reset_scaling, COLORS["warning"]).pack(side="left", padx=resp.scale(5))
    create_modern_button(button_frame, "✅ Apply", apply_scaling, COLORS["success"]).pack(side="left", padx=resp.scale(5))
    create_modern_button(button_frame, "❌ Cancel", scaling_window.destroy, COLORS["danger"]).pack(side="left", padx=resp.scale(5))

# -------------------- Modern Color Scheme --------------------
COLORS = {
    "primary": "#4F46E5",      # Indigo
    "primary_light": "#6366F1",
    "primary_dark": "#4338CA",
    "secondary": "#EC4899",    # Pink
    "success": "#10B981",      # Emerald
    "warning": "#F59E0B",      # Amber
    "danger": "#EF4444",       # Red
    "info": "#3B82F6",         # Blue
    "dark": "#1F2937",         # Gray-800
    "dark_light": "#374151",   # Gray-700
    "light": "#F9FAFB",        # Gray-50
    "light_dark": "#F3F4F6",   # Gray-100
    "border": "#E5E7EB",       # Gray-200
    "text_primary": "#111827", # Gray-900
    "text_secondary": "#6B7280", # Gray-500
    "text_light": "#9CA3AF",   # Gray-400
    "white": "#FFFFFF",
    "card_bg": "#FFFFFF",
    "sidebar_bg": "#F8FAFC",
    "header_bg": "#4F46E5",
    "header_light": "#5E56F0",
    "white_transparent": "#FFFFFF",
}

# Badge colors mapping
BADGE_COLORS = {
    "urgent": ("#EF4444", "#FEE2E2", "white"),
    "important": ("#3B82F6", "#DBEAFE", "white"),
    "holiday": ("#10B981", "#D1FAE5", "white"),
    "normal": ("#F59E0B", "#FEF3C7", "#92400E"),
}

# -------------------- UI Refresh Function --------------------
def refresh_ui_scaling():
    """Refresh UI with new scaling settings"""
    # Destroy current main container
    global main_container, header, content_frame, left_column, right_column, status_bar
    main_container.destroy()
    
    # Recreate UI with new scaling
    create_main_ui()

# -------------------- Main UI Creation Function --------------------
def create_main_ui():
    """Create the main UI with current scaling settings"""
    global main_container, header, content_frame, left_column, right_column, status_bar
    global entry_title, text_content, entry_date, entry_badge, file_info_label, remove_file_btn
    global count_label, status_label, notices_canvas_frame, notices_canvas
    
    # Main container with reduced padding for 1366x768
    main_container = tk.Frame(root, bg=COLORS["light"])
    main_container.pack(fill="both", expand=True, 
                       padx=resp.scale(8, "padding"), 
                       pady=resp.scale(8, "padding"))

    # Header with gradient effect
    header = tk.Frame(main_container, bg=COLORS["header_bg"], height=resp.scale(80, "card"))
    header.pack(fill="x", pady=(0, resp.scale(15, "padding")))

    header_content = tk.Frame(header, bg=COLORS["header_bg"])
    header_content.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(
        header_content,
        text="📢 NOTICE MANAGEMENT SYSTEM",
        bg=COLORS["header_bg"],
        fg="white",
        font=("Segoe UI", resp.font_size(18), "bold")
    ).pack()

    tk.Label(
        header_content,
        text="Professional Notice Management Solution",
        bg=COLORS["header_bg"],
        fg="#E0E7FF",
        font=("Segoe UI", resp.font_size(10))
    ).pack(pady=(3, 0))

    # Settings button in header
    settings_btn = tk.Button(header, text="⚙️", command=show_scaling_dialog,
                           bg=COLORS["primary_light"], fg="white",
                           font=("Segoe UI", resp.font_size(12), "bold"),
                           bd=0, relief="flat", cursor="hand2",
                           padx=resp.scale(10, "button"), pady=resp.scale(5, "button"))
    settings_btn.place(relx=0.95, rely=0.5, anchor="e")

    # Content frame with two columns
    content_frame = tk.Frame(main_container, bg=COLORS["light"])
    content_frame.pack(fill="both", expand=True)

    # Left column - Form
    left_column = create_card(content_frame)
    left_column.pack(side="left", fill="both", expand=True, padx=(0, resp.scale(10, "padding")))
    left_column.pack_propagate(False)
    left_column.configure(width=resp.scale(400, "card"))  # Adjustable width

    # Left column header
    left_header = tk.Frame(left_column, bg=COLORS["primary_light"], height=resp.scale(45, "card"))
    left_header.pack(fill="x")

    tk.Label(
        left_header,
        text="📝 Create / Edit Notice",
        bg=COLORS["primary_light"],
        fg="white",
        font=("Segoe UI", resp.font_size(14), "bold")
    ).pack(expand=True)

    # Form container with scrollbar
    form_container = tk.Frame(left_column, bg=COLORS["white"])
    form_container.pack(fill="both", expand=True, 
                       padx=resp.scale(20, "padding"), 
                       pady=resp.scale(15, "padding"))

    form_canvas = tk.Canvas(form_container, bg=COLORS["white"], highlightthickness=0)
    form_scrollbar = ttk.Scrollbar(form_container, orient="vertical", command=form_canvas.yview)
    form_scrollable = tk.Frame(form_canvas, bg=COLORS["white"])

    form_scrollable.bind(
        "<Configure>",
        lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all"))
    )

    form_canvas.create_window((0, 0), window=form_scrollable, anchor="nw")
    form_canvas.configure(yscrollcommand=form_scrollbar.set)

    form_canvas.pack(side="left", fill="both", expand=True)
    form_scrollbar.pack(side="right", fill="y")

    # Form fields
    def create_form_label(text):
        return tk.Label(
            form_scrollable,
            text=text,
            bg=COLORS["white"],
            fg=COLORS["dark"],
            font=("Segoe UI", resp.font_size(10), "bold"),
            anchor="w"
        )

    def create_form_entry():
        entry = tk.Entry(
            form_scrollable,
            font=("Segoe UI", resp.font_size(10)),
            bd=1,
            relief="solid",
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            highlightcolor=COLORS["primary"],
            bg=COLORS["light"],
            fg=COLORS["dark"],
            insertbackground=COLORS["primary"]
        )
        enable_paste(entry)
        return entry

    # Title
    create_form_label("Notice Title").pack(fill="x", 
                                          pady=(resp.scale(8, "padding"), resp.scale(4, "padding")))
    entry_title = create_form_entry()
    entry_title.pack(fill="x", pady=(0, resp.scale(12, "padding")), 
                    ipady=resp.scale(6, "input"))

    # Content
    create_form_label("Notice Content").pack(fill="x", 
                                            pady=(resp.scale(8, "padding"), resp.scale(4, "padding")))
    text_content = tk.Text(
        form_scrollable,
        height=5,
        font=("Segoe UI", resp.font_size(10)),
        bd=1,
        relief="solid",
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        highlightcolor=COLORS["primary"],
        bg=COLORS["light"],
        fg=COLORS["dark"],
        wrap="word",
        insertbackground=COLORS["primary"]
    )
    text_content.pack(fill="x", pady=(0, resp.scale(12, "padding")))
    enable_paste(text_content)

    # Date
    create_form_label("Date (BS Format)").pack(fill="x", 
                                              pady=(resp.scale(8, "padding"), resp.scale(4, "padding")))
    tk.Label(
        form_scrollable,
        text="Format: YYYY/MM/DD",
        bg=COLORS["white"],
        fg=COLORS["text_light"],
        font=("Segoe UI", resp.font_size(8))
    ).pack(anchor="w")
    entry_date = create_form_entry()
    entry_date.pack(fill="x", 
                   pady=(resp.scale(4, "padding"), resp.scale(12, "padding")), 
                   ipady=resp.scale(6, "input"))

    # Badge
    create_form_label("Badge Type").pack(fill="x", 
                                        pady=(resp.scale(8, "padding"), resp.scale(4, "padding")))
    entry_badge = create_form_entry()
    entry_badge.pack(fill="x", pady=(0, resp.scale(4, "padding")), 
                    ipady=resp.scale(6, "input"))
    entry_badge.insert(0, "Normal")
    tk.Label(
        form_scrollable,
        text="Options: Urgent, Holiday, Important, Normal",
        bg=COLORS["white"],
        fg=COLORS["text_light"],
        font=("Segoe UI", resp.font_size(8))
    ).pack(anchor="w")

    # File Upload Section
    create_form_label("Attach File (Optional)").pack(fill="x", 
                                                    pady=(resp.scale(20, "padding"), resp.scale(4, "padding")))

    file_upload_frame = tk.Frame(form_scrollable, bg=COLORS["white"])
    file_upload_frame.pack(fill="x", pady=(0, resp.scale(8, "padding")))

    upload_btn = create_modern_button(file_upload_frame, "📁 Choose File", browse_file, COLORS["primary"])
    upload_btn.config(padx=resp.scale(12, "button"), pady=resp.scale(6, "button"), 
                     font=("Segoe UI", resp.font_size(9), "bold"))
    upload_btn.pack(side="left")

    remove_file_btn = tk.Button(
        file_upload_frame,
        text="Remove",
        command=remove_selected_file,
        bg=COLORS["danger"],
        fg="white",
        font=("Segoe UI", resp.font_size(9), "bold"),
        padx=resp.scale(12, "button"),
        pady=resp.scale(5, "button"),
        relief="flat",
        cursor="hand2",
        state="disabled",
        bd=0
    )
    remove_file_btn.pack(side="left", padx=(resp.scale(8, "padding"), 0))

    file_info_label = tk.Label(
        form_scrollable,
        text="📁 No file selected",
        bg=COLORS["white"],
        fg=COLORS["text_light"],
        font=("Segoe UI", resp.font_size(9)),
        anchor="w"
    )
    file_info_label.pack(fill="x", pady=(resp.scale(4, "padding"), resp.scale(20, "padding")))

    # Action buttons grid - compact for 1366x768
    action_frame = tk.Frame(left_column, bg=COLORS["white"])
    action_frame.pack(fill="x", pady=(0, resp.scale(20, "padding")), 
                     padx=resp.scale(20, "padding"))

    btn_grid = tk.Frame(action_frame, bg=COLORS["white"])
    btn_grid.pack(fill="x")

    buttons = [
        ("➕ Add", submit_notice, COLORS["success"]),
        ("🔍 Search", show_search_dialog, COLORS["primary"]),
        ("✏️ Edit", edit_notice, COLORS["warning"]),
        ("🗑 Delete", remove_notice, COLORS["danger"]),
        ("🔄 Refresh", refresh_notices_list, COLORS["info"]),
        ("🧹 Clear", clear_form, COLORS["text_secondary"]),
    ]

    for i, (text, command, color) in enumerate(buttons):
        btn = create_modern_button(btn_grid, text, command, color)
        btn.config(padx=resp.scale(12, "button"), pady=resp.scale(8, "button"), 
                  font=("Segoe UI", resp.font_size(9), "bold"))
        btn.grid(row=i//2, column=i%2, 
                padx=resp.scale(3, "padding"), pady=resp.scale(3, "padding"), 
                sticky="nsew")
        btn_grid.grid_columnconfigure(i%2, weight=1)
        btn_grid.grid_rowconfigure(i//2, weight=1)

    # Folder info
    folder_info = tk.Frame(left_column, bg=COLORS["sidebar_bg"], height=resp.scale(60, "card"))
    folder_info.pack(fill="x", side="bottom")

    folder_path = os.path.abspath(UPLOAD_FOLDER)
    tk.Label(
        folder_info,
        text=f"📁 Files are saved to:\n{folder_path}",
        bg=COLORS["sidebar_bg"],
        fg=COLORS["text_secondary"],
        font=("Segoe UI", resp.font_size(8)),
        wraplength=resp.scale(350, "card"),
        justify="left"
    ).pack(pady=resp.scale(12, "padding"), padx=resp.scale(15, "padding"))

    # Right column - Notices List
    right_column = create_card(content_frame)
    right_column.pack(side="right", fill="both", expand=True)

    # Right column header
    right_header = tk.Frame(right_column, bg=COLORS["sidebar_bg"], height=resp.scale(70, "card"))
    right_header.pack(fill="x")

    header_content = tk.Frame(right_header, bg=COLORS["sidebar_bg"])
    header_content.pack(expand=True, padx=resp.scale(25, "padding"))

    tk.Label(
        header_content,
        text="📋 All Notices",
        bg=COLORS["sidebar_bg"],
        fg=COLORS["dark"],
        font=("Segoe UI", resp.font_size(14), "bold")
    ).pack(side="left")

    count_label = tk.Label(
        header_content,
        text="(0 notices)",
        bg=COLORS["sidebar_bg"],
        fg=COLORS["text_secondary"],
        font=("Segoe UI", resp.font_size(10))
    )
    count_label.pack(side="left", padx=(resp.scale(8, "padding"), 0))

    # Filter frame
    filter_frame = tk.Frame(right_header, bg=COLORS["sidebar_bg"])
    filter_frame.pack(fill="x", padx=resp.scale(25, "padding"), pady=(0, resp.scale(8, "padding")))

    tk.Label(
        filter_frame,
        text="Click on any notice to edit | Double-click to open files",
        bg=COLORS["sidebar_bg"],
        fg=COLORS["text_secondary"],
        font=("Segoe UI", resp.font_size(9))
    ).pack(side="left")

    # Mini refresh button
    refresh_mini = create_modern_button(filter_frame, "🔄 Refresh", refresh_notices_list, COLORS["primary_light"])
    refresh_mini.config(padx=resp.scale(8, "button"), pady=resp.scale(3, "button"), 
                       font=("Segoe UI", resp.font_size(8), "bold"))
    refresh_mini.pack(side="right")

    # Notices container
    notices_container = tk.Frame(right_column, bg=COLORS["white"])
    notices_container.pack(fill="both", expand=True, 
                          padx=resp.scale(25, "padding"), 
                          pady=(0, resp.scale(20, "padding")))

    notices_canvas = tk.Canvas(notices_container, bg=COLORS["white"], highlightthickness=0)
    notices_scrollbar = ttk.Scrollbar(notices_container, orient="vertical", command=notices_canvas.yview)
    notices_canvas_frame = tk.Frame(notices_canvas, bg=COLORS["white"])

    notices_canvas_frame.bind(
        "<Configure>",
        lambda e: notices_canvas.configure(scrollregion=notices_canvas.bbox("all"))
    )

    notices_canvas.create_window((0, 0), window=notices_canvas_frame, anchor="nw")
    notices_canvas.configure(yscrollcommand=notices_scrollbar.set)

    notices_canvas.pack(side="left", fill="both", expand=True)
    notices_scrollbar.pack(side="right", fill="y")

    # Mousewheel scrolling
    def on_mousewheel(event, canvas):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    notices_canvas.bind_all("<MouseWheel>", lambda e: on_mousewheel(e, notices_canvas))
    form_canvas.bind_all("<MouseWheel>", lambda e: on_mousewheel(e, form_canvas))

    notices_canvas_frame.bind("<Enter>", lambda e: notices_canvas.bind_all("<MouseWheel>", lambda ev: on_mousewheel(ev, notices_canvas)))
    notices_canvas_frame.bind("<Leave>", lambda e: notices_canvas.unbind_all("<MouseWheel>"))

    form_scrollable.bind("<Enter>", lambda e: form_canvas.bind_all("<MouseWheel>", lambda ev: on_mousewheel(ev, form_canvas)))
    form_scrollable.bind("<Leave>", lambda e: form_canvas.unbind_all("<MouseWheel>"))

    # Status bar
    status_bar = tk.Frame(root, bg=COLORS["dark"], height=resp.scale(35, "card"))
    status_bar.pack(side="bottom", fill="x")

    status_label = tk.Label(
        status_bar,
        text="✅ Ready | Create, edit, and manage notices efficiently",
        bg=COLORS["dark"],
        fg="#D1D5DB",
        font=("Segoe UI", resp.font_size(9))
    )
    status_label.pack(side="left", padx=resp.scale(15, "padding"))

    # Version label with scaling info
    scaling_info = f"UI Scale: {SCALING_SETTINGS['window_scale']:.1f}x"
    tk.Label(
        status_bar,
        text=f"Notice Manager v2.0 | {scaling_info}",
        bg=COLORS["dark"],
        fg="#9CA3AF",
        font=("Segoe UI", resp.font_size(8))
    ).pack(side="right", padx=resp.scale(15, "padding"))

    # Refresh notices list
    refresh_notices_list()
    update_count()

# -------------------- Paste Functionality --------------------
def enable_paste(widget):
    """Enable Ctrl+V/Cmd+V paste functionality for a widget"""
    def paste_text(event=None):
        try:
            clipboard_text = widget.clipboard_get()
            
            if isinstance(widget, tk.Entry):
                if widget.selection_present():
                    widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                widget.insert(tk.INSERT, clipboard_text)
            
            elif isinstance(widget, tk.Text):
                try:
                    if widget.tag_ranges(tk.SEL):
                        widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                except:
                    pass
                widget.insert(tk.INSERT, clipboard_text)
            
            return "break"
            
        except tk.TclError:
            pass
        except Exception as e:
            print(f"Paste error: {e}")
    
    # Only bind the Ctrl/Cmd+V combinations
    widget.bind('<Control-v>', paste_text)
    widget.bind('<Command-v>', paste_text)
    
    if isinstance(widget, tk.Entry) or isinstance(widget, tk.Text):
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cut", 
                        command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", 
                        command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", 
                        command=paste_text)
        menu.add_separator()
        menu.add_command(label="Select All", 
                        command=lambda: widget.select_range(0, tk.END) if isinstance(widget, tk.Entry) else widget.tag_add(tk.SEL, "1.0", tk.END))
        
        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)
        
        widget.bind("<Button-3>", show_menu)

# -------------------- Core Functions --------------------
def ensure_upload_folder():
    """Create upload folder if it doesn't exist"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

def save_uploaded_file(file_path):
    """Save uploaded file to notices folder and return the relative path"""
    ensure_upload_folder()
    
    if not file_path or not os.path.exists(file_path):
        return ""
    
    file_ext = os.path.splitext(file_path)[1]
    original_name = os.path.splitext(os.path.basename(file_path))[0]
    safe_name = "".join(c for c in original_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    unique_filename = f"{safe_name}_{uuid.uuid4().hex[:8]}{file_ext}"
    destination_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    
    try:
        shutil.copy2(file_path, destination_path)
        relative_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        return relative_path.replace("\\", "/")
    except Exception as e:
        messagebox.showerror("Upload Error", f"Failed to save file: {str(e)}")
        return ""

def open_file(file_path):
    """Open file using default system application"""
    if not file_path or not os.path.exists(file_path):
        messagebox.showwarning("File Not Found", f"The file does not exist or has been deleted.\nPath: {file_path}")
        return False
    
    try:
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        if platform.system() == 'Darwin':
            subprocess.call(('open', file_path))
        elif platform.system() == 'Windows':
            os.startfile(file_path)
        else:
            subprocess.call(('xdg-open', file_path))
        return True
    except Exception as e:
        try:
            webbrowser.open(f"file://{file_path}")
            return True
        except:
            messagebox.showerror("Error", f"Cannot open file: {str(e)}")
            return False

def load_table():
    try:
        if not os.path.exists(HTML_FILE):
            with open(HTML_FILE, "w", encoding="utf-8") as f:
                f.write("""<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .badge { 
            padding: 4px 12px; 
            border-radius: 20px; 
            font-size: 12px; 
            font-weight: bold; 
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .bg-red-100 { background-color: #fee2e2; } .text-red-800 { color: #991b1b; }
        .bg-blue-100 { background-color: #dbeafe; } .text-blue-800 { color: #1e40af; }
        .bg-green-100 { background-color: #d1fae5; } .text-green-800 { color: #065f46; }
        .bg-yellow-100 { background-color: #fef3c7; } .text-yellow-800 { color: #92400e; }
        .bg-gray-100 { background-color: #f3f4f6; } .text-gray-800 { color: #374151; }
        .notice-content { 
            margin-bottom: 10px; 
            line-height: 1.5;
        }
        .download-link { 
            margin-right: 12px; 
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
            transition: color 0.2s;
        }
        .download-link:hover {
            color: #3b82f6;
        }
    </style>
</head>
<body>
    <table id="noticeTable">
        <thead><tr><th>Title</th><th>Content</th><th>Date</th></tr></thead>
        <tbody></tbody>
    </table>
</body>
</html>""")
            
        with open(HTML_FILE, "r", encoding="utf-8") as file:
            soup = BeautifulSoup(file, "html.parser")
        
        table = soup.find("table", id="noticeTable")
        if not table:
            table = soup.new_tag("table", id="noticeTable")
            thead = soup.new_tag("thead")
            tr = soup.new_tag("tr")
            for header in ["Title", "Content", "Date"]:
                th = soup.new_tag("th")
                th.string = header
                tr.append(th)
            thead.append(tr)
            table.append(thead)
            tbody = soup.new_tag("tbody")
            table.append(tbody)
            soup.body.append(table)
            
        tbody = table.find("tbody")
        if not tbody:
            tbody = soup.new_tag("tbody")
            table.append(tbody)
            
        return soup, tbody
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load HTML: {str(e)}")
        return None

def save_table(soup):
    try:
        with open(HTML_FILE, "w", encoding="utf-8") as file:
            file.write(str(soup.prettify() if soup else ""))
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save: {str(e)}")

def create_row(title, content, date_bs, badge, badge_class, file_link):
    year, month, day = date_bs.split("/")
    sort_date = f"{year}{month.zfill(2)}{day.zfill(2)}"
    
    file_name = os.path.basename(file_link) if file_link else ""
    
    badge_icon = ""
    if badge.lower() == "urgent":
        badge_icon = "🔥"
    elif badge.lower() == "important":
        badge_icon = "⭐"
    elif badge.lower() == "holiday":
        badge_icon = "🎉"
    else:
        badge_icon = "📌"
    
    row_html = f"""
<tr>
<td class="font-medium text-gray-900" data-label="Title">{title}</td>
<td class="text-gray-700" data-label="Content">
    <div class="notice-content">{content}</div>
    {"<a href='" + file_link + "' target='_blank' class='download-link text-blue-600'><i class='fas fa-paperclip'></i> " + file_name + "</a>" if file_link else ""}
    <span class="badge {badge_class}">{badge_icon} {badge}</span>
</td>
<td class="text-gray-600" data-label="Date" data-sort="{sort_date}" data-date="{date_bs}">
    <div class="font-medium"><i class="far fa-calendar-alt"></i> {date_bs}</div>
</td>
</tr>
"""
    return BeautifulSoup(row_html, "html.parser").tr

def insert_notice(title, content, date_bs, badge, badge_class, file_link):
    result = load_table()
    if not result:
        return False
    soup, tbody = result
    new_row = create_row(title, content, date_bs, badge, badge_class, file_link)
    tbody.insert(0, new_row)
    save_table(soup)
    return True

def find_notice(search_term, search_by="title"):
    result = load_table()
    if not result:
        return []
    _, tbody = result
    rows = tbody.find_all("tr")
    matches = []
    
    for row in rows:
        if search_by == "title":
            title_cell = row.find("td", {"data-label": "Title"})
            if title_cell:
                title = title_cell.text.strip()
                if search_term.lower() in title.lower():
                    matches.append(row)
        elif search_by == "date":
            date_cell = row.find("td", {"data-label": "Date"})
            if date_cell:
                date = date_cell.get("data-date", "").strip()
                if search_term in date:
                    matches.append(row)
        elif search_by == "badge":
            badge_span = row.find("span", class_="badge")
            if badge_span:
                badge = badge_span.text.strip()
                if search_term.lower() in badge.lower():
                    matches.append(row)
        elif search_by == "content":
            content_div = row.find("div", class_="notice-content")
            if content_div:
                content = content_div.text.strip()
                if search_term.lower() in content.lower():
                    matches.append(row)
    
    return matches

def delete_notice_by_identifier(title, date_bs):
    result = load_table()
    if not result:
        return False
    soup, tbody = result
    rows = tbody.find_all("tr")
    for row in rows:
        title_cell = row.find("td", {"data-label": "Title"})
        date_cell = row.find("td", {"data-label": "Date"})
        
        if title_cell and date_cell:
            t = title_cell.text.strip()
            d = date_cell.get("data-date", "").strip()
            if t == title and d == date_bs:
                download_link = row.find("a", class_="download-link")
                if download_link:
                    file_path = download_link.get("href", "")
                    if file_path:
                        if not os.path.isabs(file_path):
                            file_path = os.path.abspath(file_path)
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                print(f"Error deleting file: {e}")
                row.decompose()
                save_table(soup)
                return True
    return False

def update_notice_by_identifier(old_title, old_date, new_title, content, date_bs, badge, badge_class, file_link):
    result = load_table()
    if not result:
        return False
    soup, tbody = result
    rows = tbody.find_all("tr")
    for row in rows:
        title_cell = row.find("td", {"data-label": "Title"})
        date_cell = row.find("td", {"data-label": "Date"})
        
        if title_cell and date_cell:
            t = title_cell.text.strip()
            d = date_cell.get("data-date", "").strip()
            if t == old_title and d == old_date:
                download_link = row.find("a", class_="download-link")
                if download_link:
                    old_file_path = download_link.get("href", "")
                    if old_file_path and file_link != old_file_path:
                        if not os.path.isabs(old_file_path):
                            old_file_path = os.path.abspath(old_file_path)
                        if os.path.exists(old_file_path):
                            try:
                                os.remove(old_file_path)
                            except Exception as e:
                                print(f"Error deleting old file: {e}")
                
                new_row = create_row(new_title, content, date_bs, badge, badge_class, file_link)
                row.replace_with(new_row)
                save_table(soup)
                return True
    return False

def get_all_notices():
    result = load_table()
    if not result:
        return []
    _, tbody = result
    rows = tbody.find_all("tr")
    notices = []
    for row in rows:
        title_cell = row.find("td", {"data-label": "Title"})
        content_div = row.find("div", class_="notice-content")
        date_cell = row.find("td", {"data-label": "Date"})
        badge_span = row.find("span", class_="badge")
        
        if all([title_cell, content_div, date_cell, badge_span]):
            title = title_cell.text.strip()
            content = content_div.text.strip()
            date = date_cell.get("data-date", "").strip()
            badge = badge_span.text.strip()
            
            download_link = row.find("a", class_="download-link")
            has_file = bool(download_link)
            file_link = download_link.get("href", "") if download_link else ""
            file_name = os.path.basename(file_link) if download_link else ""
            
            file_exists = False
            if file_link:
                if not os.path.isabs(file_link):
                    file_path = os.path.abspath(file_link)
                else:
                    file_path = file_link
                file_exists = os.path.exists(file_path)
            
            notices.append({
                "title": title,
                "content": content,
                "date": date,
                "badge": badge,
                "has_file": has_file,
                "file_exists": file_exists,
                "file_name": file_name,
                "file_link": file_link
            })
    return sorted(notices, key=lambda x: x["date"], reverse=True)

def get_notice_file(title, date_bs):
    notices = get_all_notices()
    for notice in notices:
        if notice["title"] == title and notice["date"] == date_bs:
            return notice.get("file_link", "")
    return ""

# -------------------- Enhanced UI Functions --------------------
def create_modern_button(parent, text, command, color=COLORS["primary"], hover_color=None):
    if hover_color is None:
        hover_color = COLORS["primary_light"]
    
    btn = tk.Button(
        parent, text=text, command=command,
        bg=color, fg="white", font=("Segoe UI", resp.font_size(10), "bold"),
        padx=resp.scale(20, "button"), pady=resp.scale(8, "button"), 
        relief="flat", cursor="hand2",
        activebackground=hover_color, bd=0,
        highlightthickness=0
    )
    
    def on_enter(e):
        if btn['state'] == 'normal':
            btn['background'] = hover_color
    
    def on_leave(e):
        if btn['state'] == 'normal':
            btn['background'] = color
    
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    
    return btn

def create_card(parent, **kwargs):
    card = tk.Frame(
        parent, 
        bg=COLORS["card_bg"],
        bd=0,
        relief="flat",
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        **kwargs
    )
    return card

def create_section_label(parent, text, icon="🔹"):
    frame = tk.Frame(parent, bg=COLORS["white"])
    frame.pack(fill="x", pady=(resp.scale(15, "padding"), resp.scale(8, "padding")), 
              padx=resp.scale(15, "padding"))
    
    tk.Label(
        frame, 
        text=f"{icon}  {text}",
        bg=COLORS["white"],
        fg=COLORS["dark"],
        font=("Segoe UI", resp.font_size(11), "bold"),
        anchor="w"
    ).pack(fill="x")
    
    sep = tk.Frame(frame, height=2, bg=COLORS["primary_light"])
    sep.pack(fill="x", pady=(5, 0))
    
    return frame

def browse_file():
    global current_file_path
    file_path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[
            ("All files", "*.*"),
            ("PDF files", "*.pdf"),
            ("Word documents", "*.doc *.docx"),
            ("Excel files", "*.xls *.xlsx"),
            ("Image files", "*.jpg *.jpeg *.png *.gif"),
        ]
    )
    
    if file_path:
        current_file_path = file_path
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        
        file_info_label.config(
            text=f"📎 {file_name} ({file_size:.2f} MB)",
            fg=COLORS["primary"]
        )
        remove_file_btn.config(state="normal")

def remove_selected_file():
    global current_file_path
    current_file_path = None
    file_info_label.config(text="📁 No file selected", fg=COLORS["text_light"])
    remove_file_btn.config(state="disabled")

def submit_notice():
    global current_file_path
    
    title = entry_title.get().strip()
    content = text_content.get("1.0", tk.END).strip()
    date_bs = entry_date.get().strip()
    badge = entry_badge.get().strip() or "Normal"
    
    if not title or not content or not date_bs:
        messagebox.showwarning("Input Error", "📝 Title, Content, and Date are required")
        return
    
    try:
        parts = date_bs.split("/")
        if len(parts) != 3:
            raise ValueError
        year, month, day = parts
        if len(year) != 4 or len(month) != 2 or len(day) != 2:
            raise ValueError
        int(year), int(month), int(day)
    except:
        messagebox.showwarning("Input Error", "📅 Date must be in YYYY/MM/DD format")
        return
    
    file_link = ""
    if current_file_path:
        file_link = save_uploaded_file(current_file_path)
        if not file_link:
            return
    
    badge_lower = badge.lower()
    if badge_lower == "urgent":
        badge_class = "bg-red-100 text-red-800"
    elif badge_lower == "holiday":
        badge_class = "bg-green-100 text-green-800"
    elif badge_lower == "important":
        badge_class = "bg-blue-100 text-blue-800"
    else:
        badge_class = "bg-yellow-100 text-yellow-800"
    
    if insert_notice(title, content, date_bs, badge, badge_class, file_link):
        status_label.config(text=f"✅ Notice added successfully! | {len(get_all_notices())} total notices", fg=COLORS["success"])
        
        if file_link:
            messagebox.showinfo("Success", f"✅ Notice added!\n📎 File: {os.path.basename(file_link)}")
        else:
            messagebox.showinfo("Success", "✅ Notice added successfully!")
        
        clear_form()
        refresh_notices_list()
        update_count()
    else:
        messagebox.showerror("Error", "❌ Failed to add notice")

def clear_form():
    global selected_notice, current_file_path
    selected_notice = None
    current_file_path = None
    
    entry_title.delete(0, tk.END)
    text_content.delete("1.0", tk.END)
    entry_date.delete(0, tk.END)
    entry_badge.delete(0, tk.END)
    entry_badge.insert(0, "Normal")
    
    file_info_label.config(text="📁 No file selected", fg=COLORS["text_light"])
    remove_file_btn.config(state="disabled")
    
    refresh_notices_list()
    status_label.config(text="📝 Form cleared | Ready to create new notice", fg=COLORS["info"])

def show_search_dialog():
    search_window = tk.Toplevel(root)
    search_window.title("🔍 Search Notice")
    search_window.geometry(f"{resp.scale(450)}x{resp.scale(350)}")
    search_window.configure(bg=COLORS["light"])
    search_window.transient(root)
    search_window.grab_set()
    
    search_window.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (resp.scale(450) // 2)
    y = (root.winfo_screenheight() // 2) - (resp.scale(350) // 2)
    search_window.geometry(f'{resp.scale(450)}x{resp.scale(350)}+{x}+{y}')
    
    header = tk.Frame(search_window, bg=COLORS["primary"], height=resp.scale(70))
    header.pack(fill="x")
    header.pack_propagate(False)
    
    tk.Label(header, text="🔍 Search Notices", bg=COLORS["primary"], fg="white",
             font=("Segoe UI", resp.font_size(14), "bold")).pack(expand=True)
    
    content = tk.Frame(search_window, bg=COLORS["light"], padx=resp.scale(25), pady=resp.scale(15))
    content.pack(fill="both", expand=True)
    
    tk.Label(content, text="Search by:", bg=COLORS["light"], fg=COLORS["dark"],
             font=("Segoe UI", resp.font_size(10), "bold")).pack(anchor="w", pady=(0, resp.scale(8)))
    
    mode_frame = tk.Frame(content, bg=COLORS["light"])
    mode_frame.pack(fill="x", pady=(0, resp.scale(15)))
    
    search_var = tk.StringVar(value="title")
    
    modes = [
        ("🔤 Title", "title"),
        ("📅 Date", "date"),
        ("🏷️ Badge", "badge"),
        ("📝 Content", "content")
    ]
    
    for text, mode in modes:
        btn = tk.Radiobutton(
            mode_frame, text=text, variable=search_var, value=mode,
            bg=COLORS["light"], fg=COLORS["dark_light"], font=("Segoe UI", resp.font_size(9)),
            selectcolor=COLORS["primary_light"], indicatoron=0,
            width=10, height=1, relief="solid", bd=1,
            activebackground=COLORS["primary_light"]
        )
        btn.pack(side="left", padx=resp.scale(2))
    
    input_frame = tk.Frame(content, bg=COLORS["light"])
    input_frame.pack(fill="x", pady=resp.scale(15))
    
    tk.Label(input_frame, text="Search term:", bg=COLORS["light"], fg=COLORS["dark"],
             font=("Segoe UI", resp.font_size(10))).pack(side="left", padx=(0, resp.scale(8)))
    
    search_entry = tk.Entry(
        input_frame, font=("Segoe UI", resp.font_size(10)), width=22,
        bd=1, relief="solid", highlightthickness=1,
        highlightcolor=COLORS["primary"]
    )
    search_entry.pack(side="left")
    enable_paste(search_entry)
    search_entry.focus()
    
    def perform_search():
        search_term = search_entry.get().strip()
        if not search_term:
            messagebox.showwarning("Search", "🔍 Please enter a search term")
            return
        
        mode = search_var.get()
        matches = find_notice(search_term, mode)
        
        if not matches:
            messagebox.showinfo("Search Result", "📭 No matching notice found")
            return
        
        results_window = tk.Toplevel(search_window)
        results_window.title(f"Search Results ({len(matches)} found)")
        results_window.geometry(f"{resp.scale(600)}x{resp.scale(400)}")
        results_window.configure(bg="white")
        
        results_header = tk.Frame(results_window, bg=COLORS["primary"], height=resp.scale(50))
        results_header.pack(fill="x")
        results_header.pack_propagate(False)
        
        tk.Label(results_header, text=f"🔍 Found {len(matches)} result(s)", 
                 bg=COLORS["primary"], fg="white", font=("Segoe UI", resp.font_size(12), "bold")).pack(expand=True)
        
        results_container = tk.Frame(results_window, bg="white")
        results_container.pack(fill="both", expand=True, padx=resp.scale(15), pady=resp.scale(15))
        
        results_canvas = tk.Canvas(results_container, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=results_canvas.yview)
        results_content = tk.Frame(results_canvas, bg="white")
        
        results_content.bind(
            "<Configure>",
            lambda e: results_canvas.configure(scrollregion=results_canvas.bbox("all"))
        )
        
        results_canvas.create_window((0, 0), window=results_content, anchor="nw")
        results_canvas.configure(yscrollcommand=scrollbar.set)
        
        results_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        for i, match in enumerate(matches):
            title = match.find("td", {"data-label": "Title"}).text.strip()
            date = match.find("td", {"data-label": "Date"}).get("data-date", "").strip()
            badge = match.find("span", class_="badge").text.strip()
            
            result_card = create_card(results_content, padx=resp.scale(12), pady=resp.scale(10))
            result_card.pack(fill="x", padx=resp.scale(5), pady=resp.scale(5))
            
            header_frame = tk.Frame(result_card, bg=COLORS["card_bg"])
            header_frame.pack(fill="x", pady=(0, resp.scale(6)))
            
            tk.Label(header_frame, text=f"{i+1}. {title}", bg=COLORS["card_bg"],
                     fg=COLORS["dark"], font=("Segoe UI", resp.font_size(10), "bold")).pack(side="left")
            
            badge_lower = badge.lower().replace("🔥", "").replace("⭐", "").replace("🎉", "").replace("📌", "").strip()
            badge_color, bg_color, text_color = BADGE_COLORS.get(badge_lower, (COLORS["warning"], COLORS["light"], COLORS["dark"]))
            
            badge_label = tk.Label(header_frame, text=badge,
                                   bg=bg_color, fg=text_color,
                                   font=("Segoe UI", resp.font_size(8), "bold"),
                                   padx=resp.scale(10), pady=resp.scale(2), bd=0, relief="flat")
            badge_label.pack(side="right")
            
            footer_frame = tk.Frame(result_card, bg=COLORS["card_bg"])
            footer_frame.pack(fill="x")
            
            tk.Label(footer_frame, text=f"📅 {date}", bg=COLORS["card_bg"],
                     fg=COLORS["text_secondary"], font=("Segoe UI", resp.font_size(8))).pack(side="left")
            
            tk.Button(footer_frame, text="📝 Load", 
                     command=lambda t=title, d=date: load_and_close(t, d, search_window, results_window),
                     bg=COLORS["primary"], fg="white", font=("Segoe UI", resp.font_size(8), "bold"),
                     padx=resp.scale(12), pady=resp.scale(3), relief="flat").pack(side="right")
        
        def load_and_close(title, date, *windows):
            load_notice_for_editing(title, date)
            for window in windows:
                window.destroy()
        
        results_window.mainloop()
    
    button_frame = tk.Frame(content, bg=COLORS["light"])
    button_frame.pack(pady=resp.scale(15))
    
    create_modern_button(button_frame, "🔍 Search", perform_search, COLORS["primary"]).pack(side="left", padx=resp.scale(5))
    
    tk.Button(button_frame, text="Cancel", command=search_window.destroy,
              bg=COLORS["text_light"], fg="white", font=("Segoe UI", resp.font_size(10)),
              padx=resp.scale(15), pady=resp.scale(6), relief="flat").pack(side="left", padx=resp.scale(5))
    
    search_entry.bind('<Return>', lambda e: perform_search())

def load_notice_for_editing(title, date_bs):
    global selected_notice
    selected_notice = (title, date_bs)
    
    result = load_table()
    if not result:
        return
    
    _, tbody = result
    rows = tbody.find_all("tr")
    
    for row in rows:
        title_cell = row.find("td", {"data-label": "Title"})
        date_cell = row.find("td", {"data-label": "Date"})
        
        if title_cell and date_cell:
            t = title_cell.text.strip()
            d = date_cell.get("data-date", "").strip()
            
            if t == title and d == date_bs:
                entry_title.delete(0, tk.END)
                entry_title.insert(0, title)
                
                content_div = row.find("div", class_="notice-content")
                text_content.delete("1.0", tk.END)
                if content_div:
                    text_content.insert(tk.END, content_div.text.strip())
                
                badge_span = row.find("span", class_="badge")
                entry_badge.delete(0, tk.END)
                if badge_span:
                    badge_text = badge_span.text.strip()
                    for emoji in ["🔥", "⭐", "🎉", "📌"]:
                        badge_text = badge_text.replace(emoji, "").strip()
                    entry_badge.insert(0, badge_text)
                
                entry_date.delete(0, tk.END)
                entry_date.insert(0, date_bs)
                
                download_link = row.find("a", class_="download-link")
                if download_link:
                    file_path = download_link.get("href", "")
                    if file_path:
                        if not os.path.isabs(file_path):
                            file_path = os.path.abspath(file_path)
                        if os.path.exists(file_path):
                            file_info_label.config(
                                text=f"📎 {os.path.basename(file_path)}",
                                fg=COLORS["success"]
                            )
                        else:
                            file_info_label.config(text="⚠ File not found", fg=COLORS["danger"])
                else:
                    file_info_label.config(text="📁 No file attached", fg=COLORS["text_light"])
                
                refresh_notices_list()
                status_label.config(text=f"📝 Editing: {title}", fg=COLORS["info"])
                return

def edit_notice():
    global selected_notice, current_file_path
    
    if not selected_notice:
        messagebox.showwarning("Warning", "📝 Please select a notice to edit")
        return
    
    old_title, old_date = selected_notice
    new_title = entry_title.get().strip()
    content = text_content.get("1.0", tk.END).strip()
    date_bs = entry_date.get().strip()
    badge = entry_badge.get().strip() or "Normal"
    
    if not new_title or not content or not date_bs:
        messagebox.showwarning("Input Error", "📝 Title, Content, and Date are required")
        return
    
    try:
        parts = date_bs.split("/")
        if len(parts) != 3:
            raise ValueError
        year, month, day = parts
        if len(year) != 4 or len(month) != 2 or len(day) != 2:
            raise ValueError
        int(year), int(month), int(day)
    except:
        messagebox.showwarning("Input Error", "📅 Date must be in YYYY/MM/DD format")
        return
    
    file_link = ""
    if current_file_path:
        file_link = save_uploaded_file(current_file_path)
        if not file_link:
            return
    
    if not file_link:
        result = load_table()
        if result:
            _, tbody = result
            rows = tbody.find_all("tr")
            for row in rows:
                title_cell = row.find("td", {"data-label": "Title"})
                date_cell = row.find("td", {"data-label": "Date"})
                if title_cell and date_cell:
                    if title_cell.text.strip() == old_title and date_cell.get("data-date", "").strip() == old_date:
                        download_link = row.find("a", class_="download-link")
                        if download_link:
                            file_link = download_link.get("href", "")
    
    badge_lower = badge.lower()
    if badge_lower == "urgent":
        badge_class = "bg-red-100 text-red-800"
    elif badge_lower == "holiday":
        badge_class = "bg-green-100 text-green-800"
    elif badge_lower == "important":
        badge_class = "bg-blue-100 text-blue-800"
    else:
        badge_class = "bg-yellow-100 text-yellow-800"
    
    if update_notice_by_identifier(old_title, old_date, new_title, content, date_bs, badge, badge_class, file_link):
        messagebox.showinfo("Success", "✅ Notice updated successfully!")
        status_label.config(text=f"✅ Notice '{new_title}' updated successfully!", fg=COLORS["success"])
        clear_form()
        refresh_notices_list()
        update_count()
    else:
        messagebox.showerror("Error", "❌ Failed to update notice")

def remove_notice():
    global selected_notice
    
    if not selected_notice:
        messagebox.showwarning("Warning", "📝 Please select a notice to delete")
        return
    
    title, date_bs = selected_notice
    
    if messagebox.askyesno("Confirm Delete", f"🗑️ Are you sure you want to delete:\n\n'{title}'\n📅 ({date_bs})?"):
        if delete_notice_by_identifier(title, date_bs):
            messagebox.showinfo("Success", "✅ Notice deleted successfully!")
            status_label.config(text="✅ Notice deleted successfully!", fg=COLORS["success"])
            clear_form()
            refresh_notices_list()
            update_count()
        else:
            messagebox.showerror("Error", "❌ Failed to delete notice")

def view_notice_file(title, date_bs):
    file_path = get_notice_file(title, date_bs)
    if not file_path:
        messagebox.showinfo("No File", "📭 This notice doesn't have an attached file.")
        return
    
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        messagebox.showwarning("File Not Found", f"❌ The attached file no longer exists.")
        return
    
    if open_file(file_path):
        file_name = os.path.basename(file_path)
        status_label.config(text=f"📂 Opened: {file_name}", fg=COLORS["info"])
    else:
        messagebox.showerror("Error", "❌ Failed to open the file")

def refresh_notices_list():
    for widget in notices_canvas_frame.winfo_children():
        widget.destroy()
    
    notices = get_all_notices()
    
    if not notices:
        empty_frame = tk.Frame(notices_canvas_frame, bg=COLORS["white"], height=resp.scale(150, "card"))
        empty_frame.pack(fill="both", expand=True)
        
        tk.Label(empty_frame, text="📭 No notices found", 
                 bg=COLORS["white"], fg=COLORS["text_light"], font=("Segoe UI", resp.font_size(12), "bold"),
                 pady=resp.scale(15, "padding")).pack(expand=True)
        
        tk.Label(empty_frame, text="Create your first notice using the form", 
                 bg=COLORS["white"], fg=COLORS["text_secondary"], font=("Segoe UI", resp.font_size(10))).pack()
        return
    
    for i, notice in enumerate(notices):
        card_bg = COLORS["card_bg"]
        border_color = COLORS["border"]
        
        if selected_notice and notice["title"] == selected_notice[0] and notice["date"] == selected_notice[1]:
            card_bg = "#F0F9FF"
            border_color = COLORS["primary"]
        
        notice_card = create_card(
            notices_canvas_frame,
            padx=resp.scale(15, "card"),
            pady=resp.scale(12, "card")
        )
        notice_card.pack(fill="x", padx=resp.scale(6, "padding"), pady=resp.scale(6, "padding"))
        
        header_frame = tk.Frame(notice_card, bg=card_bg)
        header_frame.pack(fill="x", pady=(0, resp.scale(10, "padding")))
        
        title_text = notice["title"]
        if len(title_text) > 40:
            title_text = title_text[:37] + "..."
        
        title_label = tk.Label(
            header_frame,
            text=title_text,
            bg=card_bg,
            fg=COLORS["dark"],
            font=("Segoe UI", resp.font_size(11), "bold"),
            anchor="w",
            cursor="hand2"
        )
        title_label.pack(side="left", fill="x", expand=True)
        title_label.bind("<Button-1>", lambda e, t=notice["title"], d=notice["date"]: load_notice_for_editing(t, d))
        
        badge_lower = notice["badge"].lower().replace("🔥", "").replace("⭐", "").replace("🎉", "").replace("📌", "").strip()
        badge_color, bg_color, text_color = BADGE_COLORS.get(badge_lower, (COLORS["warning"], COLORS["light"], COLORS["dark"]))
        
        badge_label = tk.Label(
            header_frame,
            text=notice["badge"],
            bg=bg_color,
            fg=text_color,
            font=("Segoe UI", resp.font_size(8), "bold"),
            padx=resp.scale(12, "button"),
            pady=resp.scale(3, "button"),
            bd=0,
            relief="flat"
        )
        badge_label.pack(side="right")
        
        content_frame = tk.Frame(notice_card, bg=card_bg)
        content_frame.pack(fill="x", pady=(0, resp.scale(12, "padding")))
        
        content_text = notice["content"]
        if len(content_text) > 120:
            content_text = content_text[:117] + "..."
        
        content_label = tk.Label(
            content_frame,
            text=content_text,
            bg=card_bg,
            fg=COLORS["text_secondary"],
            font=("Segoe UI", resp.font_size(10)),
            wraplength=resp.scale(400, "card"),
            anchor="w",
            justify="left"
        )
        content_label.pack(fill="x")
        
        footer_frame = tk.Frame(notice_card, bg=card_bg)
        footer_frame.pack(fill="x")
        
        meta_frame = tk.Frame(footer_frame, bg=card_bg)
        meta_frame.pack(side="left", fill="x", expand=True)
        
        date_icon = tk.Label(meta_frame, text="📅", bg=card_bg, font=("Segoe UI", resp.font_size(9)))
        date_icon.pack(side="left")
        
        date_label = tk.Label(
            meta_frame,
            text=f" {notice['date']}",
            bg=card_bg,
            fg=COLORS["text_secondary"],
            font=("Segoe UI", resp.font_size(9))
        )
        date_label.pack(side="left", padx=(0, resp.scale(15, "padding")))
        
        if notice["has_file"]:
            file_color = COLORS["primary"] if notice.get("file_exists", True) else COLORS["danger"]
            file_icon = tk.Label(meta_frame, text="📎", bg=card_bg, font=("Segoe UI", resp.font_size(9)), fg=file_color)
            file_icon.pack(side="left")
            
            file_name = notice["file_name"]
            if len(file_name) > 20:
                file_name = file_name[:17] + "..."
            
            file_label = tk.Label(
                meta_frame,
                text=f" {file_name}",
                bg=card_bg,
                fg=file_color,
                font=("Segoe UI", resp.font_size(9))
            )
            file_label.pack(side="left")
        
        action_frame = tk.Frame(footer_frame, bg=card_bg)
        action_frame.pack(side="right")
        
        if notice["has_file"]:
            file_btn = create_modern_button(
                action_frame,
                "📂 Open",
                lambda t=notice["title"], d=notice["date"]: view_notice_file(t, d),
                color=COLORS["secondary"]
            )
            file_btn.config(padx=resp.scale(10, "button"), pady=resp.scale(4, "button"), 
                          font=("Segoe UI", resp.font_size(8), "bold"))
            file_btn.pack(side="left", padx=(resp.scale(3, "padding"), 0))
        
        view_btn = create_modern_button(
            action_frame,
            "👁 View",
            lambda t=notice["title"], d=notice["date"]: load_notice_for_editing(t, d),
            color=COLORS["primary"]
        )
        view_btn.config(padx=resp.scale(10, "button"), pady=resp.scale(4, "button"), 
                       font=("Segoe UI", resp.font_size(8), "bold"))
        view_btn.pack(side="left", padx=(resp.scale(3, "padding"), 0))
        
        delete_btn = create_modern_button(
            action_frame,
            "🗑 Delete",
            lambda t=notice["title"], d=notice["date"]: delete_selected_notice(t, d),
            color=COLORS["danger"]
        )
        delete_btn.config(padx=resp.scale(10, "button"), pady=resp.scale(4, "button"), 
                         font=("Segoe UI", resp.font_size(8), "bold"))
        delete_btn.pack(side="left", padx=(resp.scale(3, "padding"), 0))
    
    notices_canvas.configure(scrollregion=notices_canvas.bbox("all"))

def delete_selected_notice(title, date):
    if messagebox.askyesno("Confirm Delete", f"🗑️ Delete notice '{title}'?\n📅 {date}"):
        if delete_notice_by_identifier(title, date):
            messagebox.showinfo("Success", "✅ Notice deleted successfully!")
            status_label.config(text="✅ Notice deleted successfully!", fg=COLORS["success"])
            clear_form()
            refresh_notices_list()
            update_count()
        else:
            messagebox.showerror("Error", "❌ Failed to delete notice")

def update_count():
    notices = get_all_notices()
    count = len(notices)
    count_label.config(text=f"📊 {count} notice{'s' if count != 1 else ''}")
    root.after(5000, update_count)

def toggle_maximize():
    global is_maximized
    if is_maximized:
        root.state('normal')
        is_maximized = False
    else:
        root.state('zoomed')
        is_maximized = True

# -------------------- Keyboard Shortcuts --------------------
def setup_keyboard_shortcuts():
    """Set up proper keyboard shortcuts without interfering with normal typing"""
    
    # F11 for maximize
    root.bind("<F11>", lambda e: toggle_maximize())
    
    # Escape to clear form
    root.bind("<Escape>", lambda e: clear_form())
    
    # F5 to refresh
    root.bind("<F5>", lambda e: refresh_notices_list())
    
    # Ctrl+Alt+S for scaling settings
    root.bind("<Control-Alt-s>", lambda e: show_scaling_dialog())
    root.bind("<Control-Alt-S>", lambda e: show_scaling_dialog())

# -------------------- Responsive UI Setup --------------------
root = tk.Tk()
root.title("📢 Notice Management System")

# Initialize responsive configuration for main window
resp = ResponsiveConfig(root)

# Set window size for 1366x768
window_width = resp.scale(1100)
window_height = resp.scale(650)
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

# Set minimum size for 1366x768
min_width = resp.scale(600)
min_height = resp.scale(450)
root.minsize(min_width, min_height)

root.configure(bg=COLORS["light"])

try:
    root.iconbitmap("icon.ico")
except:
    pass

# Create main UI
create_main_ui()

# Set up keyboard shortcuts
setup_keyboard_shortcuts()

# Set focus to title field
entry_title.focus_set()

# Start the main loop
root.mainloop()