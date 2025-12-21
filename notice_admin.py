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
    "header_light": "#5E56F0",  # Lighter version for text
    "white_transparent": "#FFFFFF",  # Solid white instead of RGBA
}

# Badge colors mapping
BADGE_COLORS = {
    "urgent": ("#EF4444", "#FEE2E2", "white"),
    "important": ("#3B82F6", "#DBEAFE", "white"),
    "holiday": ("#10B981", "#D1FAE5", "white"),
    "normal": ("#F59E0B", "#FEF3C7", "#92400E"),
}

# -------------------- Paste Functionality --------------------
def enable_paste(widget):
    """Enable Ctrl+V/Cmd+V paste functionality for a widget"""
    def paste_text(event=None):
        try:
            # Get clipboard content
            clipboard_text = widget.clipboard_get()
            
            # Check if widget is Entry
            if isinstance(widget, tk.Entry):
                # Delete selected text if any
                if widget.selection_present():
                    widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                # Insert at cursor position
                widget.insert(tk.INSERT, clipboard_text)
            
            # Check if widget is Text
            elif isinstance(widget, tk.Text):
                # Delete selected text if any
                try:
                    if widget.tag_ranges(tk.SEL):
                        widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                except:
                    pass
                # Insert at cursor position
                widget.insert(tk.INSERT, clipboard_text)
            
            return "break"  # Prevent default behavior
            
        except tk.TclError:
            # Clipboard might be empty or contain non-text
            pass
        except Exception as e:
            print(f"Paste error: {e}")
    
    # Bind Ctrl+V (Windows/Linux) and Cmd+V (Mac)
    widget.bind('<Control-v>', paste_text)
    widget.bind('<Command-v>', paste_text)  # For Mac
    
    # Also allow right-click paste context menu
    if isinstance(widget, tk.Entry) or isinstance(widget, tk.Text):
        # Create right-click menu
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
        
        # Bind right-click to show menu
        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)
        
        widget.bind("<Button-3>", show_menu)  # Right-click

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
    
    # Add icon based on badge type
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
        bg=color, fg="white", font=("Segoe UI", 11, "bold"),
        padx=24, pady=10, relief="flat", cursor="hand2",
        activebackground=hover_color, bd=0,
        highlightthickness=0
    )
    
    # Add hover effect
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
    frame.pack(fill="x", pady=(20, 10), padx=20)
    
    tk.Label(
        frame, 
        text=f"{icon}  {text}",
        bg=COLORS["white"],
        fg=COLORS["dark"],
        font=("Segoe UI", 12, "bold"),
        anchor="w"
    ).pack(fill="x")
    
    # Separator line
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
        # Show success animation
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
    search_window.geometry("500x400")
    search_window.configure(bg=COLORS["light"])
    search_window.transient(root)
    search_window.grab_set()
    
    # Center the search window
    search_window.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (500 // 2)
    y = (root.winfo_screenheight() // 2) - (400 // 2)
    search_window.geometry(f'500x400+{x}+{y}')
    
    # Header
    header = tk.Frame(search_window, bg=COLORS["primary"], height=80)
    header.pack(fill="x")
    header.pack_propagate(False)
    
    tk.Label(header, text="🔍 Search Notices", bg=COLORS["primary"], fg="white",
             font=("Segoe UI", 16, "bold")).pack(expand=True)
    
    # Content
    content = tk.Frame(search_window, bg=COLORS["light"], padx=30, pady=20)
    content.pack(fill="both", expand=True)
    
    # Search mode selection
    tk.Label(content, text="Search by:", bg=COLORS["light"], fg=COLORS["dark"],
             font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
    
    mode_frame = tk.Frame(content, bg=COLORS["light"])
    mode_frame.pack(fill="x", pady=(0, 20))
    
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
            bg=COLORS["light"], fg=COLORS["dark_light"], font=("Segoe UI", 10),
            selectcolor=COLORS["primary_light"], indicatoron=0,
            width=12, height=2, relief="solid", bd=1,
            activebackground=COLORS["primary_light"]
        )
        btn.pack(side="left", padx=2)
    
    # Search input
    input_frame = tk.Frame(content, bg=COLORS["light"])
    input_frame.pack(fill="x", pady=20)
    
    tk.Label(input_frame, text="Search term:", bg=COLORS["light"], fg=COLORS["dark"],
             font=("Segoe UI", 11)).pack(side="left", padx=(0, 10))
    
    search_entry = tk.Entry(
        input_frame, font=("Segoe UI", 11), width=25,
        bd=1, relief="solid", highlightthickness=1,
        highlightcolor=COLORS["primary"]
    )
    search_entry.pack(side="left")
    enable_paste(search_entry)  # Enable paste for search entry
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
        results_window.geometry("700x500")
        results_window.configure(bg="white")
        
        # Results header
        results_header = tk.Frame(results_window, bg=COLORS["primary"], height=60)
        results_header.pack(fill="x")
        results_header.pack_propagate(False)
        
        tk.Label(results_header, text=f"🔍 Found {len(matches)} result(s)", 
                 bg=COLORS["primary"], fg="white", font=("Segoe UI", 14, "bold")).pack(expand=True)
        
        # Results content
        results_container = tk.Frame(results_window, bg="white")
        results_container.pack(fill="both", expand=True, padx=20, pady=20)
        
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
            
            result_card = create_card(results_content, padx=15, pady=12)
            result_card.pack(fill="x", padx=5, pady=5)
            
            # Header with index
            header_frame = tk.Frame(result_card, bg=COLORS["card_bg"])
            header_frame.pack(fill="x", pady=(0, 8))
            
            tk.Label(header_frame, text=f"{i+1}. {title}", bg=COLORS["card_bg"],
                     fg=COLORS["dark"], font=("Segoe UI", 11, "bold")).pack(side="left")
            
            # Badge
            badge_lower = badge.lower().replace("🔥", "").replace("⭐", "").replace("🎉", "").replace("📌", "").strip()
            badge_color, bg_color, text_color = BADGE_COLORS.get(badge_lower, (COLORS["warning"], COLORS["light"], COLORS["dark"]))
            
            badge_label = tk.Label(header_frame, text=badge,
                                   bg=bg_color, fg=text_color,
                                   font=("Segoe UI", 9, "bold"),
                                   padx=12, pady=3, bd=0, relief="flat")
            badge_label.pack(side="right")
            
            # Footer with date and load button
            footer_frame = tk.Frame(result_card, bg=COLORS["card_bg"])
            footer_frame.pack(fill="x")
            
            tk.Label(footer_frame, text=f"📅 {date}", bg=COLORS["card_bg"],
                     fg=COLORS["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
            
            tk.Button(footer_frame, text="📝 Load", 
                     command=lambda t=title, d=date: load_and_close(t, d, search_window, results_window),
                     bg=COLORS["primary"], fg="white", font=("Segoe UI", 9, "bold"),
                     padx=15, pady=4, relief="flat").pack(side="right")
        
        def load_and_close(title, date, *windows):
            load_notice_for_editing(title, date)
            for window in windows:
                window.destroy()
        
        results_window.mainloop()
    
    # Buttons
    button_frame = tk.Frame(content, bg=COLORS["light"])
    button_frame.pack(pady=20)
    
    create_modern_button(button_frame, "🔍 Search", perform_search, COLORS["primary"]).pack(side="left", padx=5)
    
    tk.Button(button_frame, text="Cancel", command=search_window.destroy,
              bg=COLORS["text_light"], fg="white", font=("Segoe UI", 11),
              padx=20, pady=8, relief="flat").pack(side="left", padx=5)
    
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
                    # Remove emoji from badge text
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
        empty_frame = tk.Frame(notices_canvas_frame, bg=COLORS["white"], height=200)
        empty_frame.pack(fill="both", expand=True)
        
        tk.Label(empty_frame, text="📭 No notices found", 
                 bg=COLORS["white"], fg=COLORS["text_light"], font=("Segoe UI", 14, "bold"),
                 pady=20).pack(expand=True)
        
        tk.Label(empty_frame, text="Create your first notice using the form", 
                 bg=COLORS["white"], fg=COLORS["text_secondary"], font=("Segoe UI", 11)).pack()
        return
    
    for i, notice in enumerate(notices):
        card_bg = COLORS["card_bg"]
        border_color = COLORS["border"]
        
        if selected_notice and notice["title"] == selected_notice[0] and notice["date"] == selected_notice[1]:
            card_bg = "#F0F9FF"
            border_color = COLORS["primary"]
        
        notice_card = create_card(
            notices_canvas_frame,
            padx=20,
            pady=16
        )
        notice_card.pack(fill="x", padx=8, pady=8)
        
        # Header with title and badge
        header_frame = tk.Frame(notice_card, bg=card_bg)
        header_frame.pack(fill="x", pady=(0, 12))
        
        title_text = notice["title"]
        if len(title_text) > 50:
            title_text = title_text[:47] + "..."
        
        title_label = tk.Label(
            header_frame,
            text=title_text,
            bg=card_bg,
            fg=COLORS["dark"],
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            cursor="hand2"
        )
        title_label.pack(side="left", fill="x", expand=True)
        title_label.bind("<Button-1>", lambda e, t=notice["title"], d=notice["date"]: load_notice_for_editing(t, d))
        
        # Badge
        badge_lower = notice["badge"].lower().replace("🔥", "").replace("⭐", "").replace("🎉", "").replace("📌", "").strip()
        badge_color, bg_color, text_color = BADGE_COLORS.get(badge_lower, (COLORS["warning"], COLORS["light"], COLORS["dark"]))
        
        badge_label = tk.Label(
            header_frame,
            text=notice["badge"],
            bg=bg_color,
            fg=text_color,
            font=("Segoe UI", 9, "bold"),
            padx=15,
            pady=4,
            bd=0,
            relief="flat"
        )
        badge_label.pack(side="right")
        
        # Content
        content_frame = tk.Frame(notice_card, bg=card_bg)
        content_frame.pack(fill="x", pady=(0, 15))
        
        content_text = notice["content"]
        if len(content_text) > 180:
            content_text = content_text[:177] + "..."
        
        content_label = tk.Label(
            content_frame,
            text=content_text,
            bg=card_bg,
            fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            wraplength=550,
            anchor="w",
            justify="left"
        )
        content_label.pack(fill="x")
        
        # Footer
        footer_frame = tk.Frame(notice_card, bg=card_bg)
        footer_frame.pack(fill="x")
        
        # Metadata
        meta_frame = tk.Frame(footer_frame, bg=card_bg)
        meta_frame.pack(side="left", fill="x", expand=True)
        
        # Date
        date_icon = tk.Label(meta_frame, text="📅", bg=card_bg, font=("Segoe UI", 10))
        date_icon.pack(side="left")
        
        date_label = tk.Label(
            meta_frame,
            text=f" {notice['date']}",
            bg=card_bg,
            fg=COLORS["text_secondary"],
            font=("Segoe UI", 10)
        )
        date_label.pack(side="left", padx=(0, 20))
        
        # File indicator
        if notice["has_file"]:
            file_color = COLORS["primary"] if notice.get("file_exists", True) else COLORS["danger"]
            file_icon = tk.Label(meta_frame, text="📎", bg=card_bg, font=("Segoe UI", 10), fg=file_color)
            file_icon.pack(side="left")
            
            file_name = notice["file_name"]
            if len(file_name) > 25:
                file_name = file_name[:22] + "..."
            
            file_label = tk.Label(
                meta_frame,
                text=f" {file_name}",
                bg=card_bg,
                fg=file_color,
                font=("Segoe UI", 10)
            )
            file_label.pack(side="left")
        
        # Action buttons
        action_frame = tk.Frame(footer_frame, bg=card_bg)
        action_frame.pack(side="right")
        
        # File button
        if notice["has_file"]:
            file_btn = create_modern_button(
                action_frame,
                "📂 Open File",
                lambda t=notice["title"], d=notice["date"]: view_notice_file(t, d),
                color=COLORS["secondary"]
            )
            file_btn.config(padx=12, pady=5, font=("Segoe UI", 9, "bold"))
            file_btn.pack(side="left", padx=(5, 0))
        
        # View button
        view_btn = create_modern_button(
            action_frame,
            "👁 View",
            lambda t=notice["title"], d=notice["date"]: load_notice_for_editing(t, d),
            color=COLORS["primary"]
        )
        view_btn.config(padx=12, pady=5, font=("Segoe UI", 9, "bold"))
        view_btn.pack(side="left", padx=(5, 0))
        
        # Delete button
        delete_btn = create_modern_button(
            action_frame,
            "🗑 Delete",
            lambda t=notice["title"], d=notice["date"]: delete_selected_notice(t, d),
            color=COLORS["danger"]
        )
        delete_btn.config(padx=12, pady=5, font=("Segoe UI", 9, "bold"))
        delete_btn.pack(side="left", padx=(5, 0))
    
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

# -------------------- Modern UI Setup --------------------
root = tk.Tk()
root.title("📢 Notice Management System")
root.state('zoomed')
root.configure(bg=COLORS["light"])

try:
    root.iconbitmap("icon.ico")
except:
    pass

# Main container
main_container = tk.Frame(root, bg=COLORS["light"])
main_container.pack(fill="both", expand=True, padx=20, pady=20)

# Header with gradient effect
header = tk.Frame(main_container, bg=COLORS["header_bg"], height=100)
header.pack(fill="x", pady=(0, 20))
header.pack_propagate(False)

header_content = tk.Frame(header, bg=COLORS["header_bg"])
header_content.place(relx=0.5, rely=0.5, anchor="center")

tk.Label(
    header_content,
    text="📢 NOTICE MANAGEMENT SYSTEM",
    bg=COLORS["header_bg"],
    fg="white",
    font=("Segoe UI", 24, "bold")
).pack()

tk.Label(
    header_content,
    text="Professional Notice Management Solution",
    bg=COLORS["header_bg"],
    fg="#E0E7FF",  # Lighter color for subtitle
    font=("Segoe UI", 12)
).pack(pady=(5, 0))

# Two column layout
content_frame = tk.Frame(main_container, bg=COLORS["light"])
content_frame.pack(fill="both", expand=True)

# Left column - Form
left_column = create_card(content_frame)
left_column.pack(side="left", fill="both", expand=True, padx=(0, 15))
left_column.pack_propagate(False)
left_column.configure(width=500)

# Left column header
left_header = tk.Frame(left_column, bg=COLORS["primary_light"], height=50)
left_header.pack(fill="x")
left_header.pack_propagate(False)

tk.Label(
    left_header,
    text="📝 Create / Edit Notice",
    bg=COLORS["primary_light"],
    fg="white",
    font=("Segoe UI", 18, "bold")
).pack(expand=True)

# Form container with scrollbar
form_container = tk.Frame(left_column, bg=COLORS["white"])
form_container.pack(fill="both", expand=True, padx=25, pady=20)

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
        font=("Segoe UI", 11, "bold"),
        anchor="w"
    )

def create_form_entry():
    entry = tk.Entry(
        form_scrollable,
        font=("Segoe UI", 11),
        bd=1,
        relief="solid",
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        highlightcolor=COLORS["primary"],
        bg=COLORS["light"],
        fg=COLORS["dark"],
        insertbackground=COLORS["primary"]
    )
    enable_paste(entry)  # Enable paste for all Entry widgets
    return entry

# Title
create_form_label("Notice Title").pack(fill="x", pady=(10, 5))
entry_title = create_form_entry()
entry_title.pack(fill="x", pady=(0, 15), ipady=8)

# Content
create_form_label("Notice Content").pack(fill="x", pady=(10, 5))
text_content = tk.Text(
    form_scrollable,
    height=6,
    font=("Segoe UI", 11),
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
text_content.pack(fill="x", pady=(0, 15))
enable_paste(text_content)  # Enable paste for Text widget

# Date
create_form_label("Date (BS Format)").pack(fill="x", pady=(10, 5))
tk.Label(
    form_scrollable,
    text="Format: YYYY/MM/DD",
    bg=COLORS["white"],
    fg=COLORS["text_light"],
    font=("Segoe UI", 9)
).pack(anchor="w")
entry_date = create_form_entry()
entry_date.pack(fill="x", pady=(5, 15), ipady=8)

# Badge
create_form_label("Badge Type").pack(fill="x", pady=(10, 5))
entry_badge = create_form_entry()
entry_badge.pack(fill="x", pady=(0, 5), ipady=8)
entry_badge.insert(0, "Normal")
tk.Label(
    form_scrollable,
    text="Options: Urgent, Holiday, Important, Normal",
    bg=COLORS["white"],
    fg=COLORS["text_light"],
    font=("Segoe UI", 9)
).pack(anchor="w")

# File Upload Section
create_form_label("Attach File (Optional)").pack(fill="x", pady=(25, 5))

file_upload_frame = tk.Frame(form_scrollable, bg=COLORS["white"])
file_upload_frame.pack(fill="x", pady=(0, 10))

upload_btn = create_modern_button(file_upload_frame, "📁 Choose File", browse_file, COLORS["primary"])
upload_btn.config(padx=15, pady=8, font=("Segoe UI", 10, "bold"))
upload_btn.pack(side="left")

remove_file_btn = tk.Button(
    file_upload_frame,
    text="Remove",
    command=remove_selected_file,
    bg=COLORS["danger"],
    fg="white",
    font=("Segoe UI", 10, "bold"),
    padx=15,
    pady=6,
    relief="flat",
    cursor="hand2",
    state="disabled",
    bd=0
)
remove_file_btn.pack(side="left", padx=(10, 0))

file_info_label = tk.Label(
    form_scrollable,
    text="📁 No file selected",
    bg=COLORS["white"],
    fg=COLORS["text_light"],
    font=("Segoe UI", 10),
    anchor="w"
)
file_info_label.pack(fill="x", pady=(5, 25))

# Action buttons grid
action_frame = tk.Frame(left_column, bg=COLORS["white"])
action_frame.pack(fill="x", pady=(0, 25), padx=25)

btn_grid = tk.Frame(action_frame, bg=COLORS["white"])
btn_grid.pack(fill="x")

buttons = [
    ("➕ Add Notice", submit_notice, COLORS["success"]),
    ("🔍 Search", show_search_dialog, COLORS["primary"]),
    ("✏️ Edit Notice", edit_notice, COLORS["warning"]),
    ("🗑 Delete Notice", remove_notice, COLORS["danger"]),
    ("🔄 Refresh", refresh_notices_list, COLORS["info"]),
    ("🧹 Clear", clear_form, COLORS["text_secondary"]),
]

for i, (text, command, color) in enumerate(buttons):
    btn = create_modern_button(btn_grid, text, command, color)
    btn.config(padx=15, pady=10, font=("Segoe UI", 10, "bold"))
    btn.grid(row=i//2, column=i%2, padx=5, pady=5, sticky="nsew")
    btn_grid.grid_columnconfigure(i%2, weight=1)
    btn_grid.grid_rowconfigure(i//2, weight=1)

# Folder info
folder_info = tk.Frame(left_column, bg=COLORS["sidebar_bg"], height=70)
folder_info.pack(fill="x", side="bottom")
folder_info.pack_propagate(False)

folder_path = os.path.abspath(UPLOAD_FOLDER)
tk.Label(
    folder_info,
    text=f"📁 Files are saved to:\n{folder_path}",
    bg=COLORS["sidebar_bg"],
    fg=COLORS["text_secondary"],
    font=("Segoe UI", 9),
    wraplength=400,
    justify="left"
).pack(pady=15, padx=20)

# Right column - Notices List
right_column = create_card(content_frame)
right_column.pack(side="right", fill="both", expand=True)

# Right column header
right_header = tk.Frame(right_column, bg=COLORS["sidebar_bg"], height=90)
right_header.pack(fill="x")
right_header.pack_propagate(False)

header_content = tk.Frame(right_header, bg=COLORS["sidebar_bg"])
header_content.pack(expand=True, padx=30)

tk.Label(
    header_content,
    text="📋 All Notices",
    bg=COLORS["sidebar_bg"],
    fg=COLORS["dark"],
    font=("Segoe UI", 18, "bold")
).pack(side="left")

count_label = tk.Label(
    header_content,
    text="(0 notices)",
    bg=COLORS["sidebar_bg"],
    fg=COLORS["text_secondary"],
    font=("Segoe UI", 12)
)
count_label.pack(side="left", padx=(10, 0))

# Filter frame
filter_frame = tk.Frame(right_header, bg=COLORS["sidebar_bg"])
filter_frame.pack(fill="x", padx=30, pady=(0, 10))

tk.Label(
    filter_frame,
    text="Click on any notice to edit | Double-click to open files",
    bg=COLORS["sidebar_bg"],
    fg=COLORS["text_secondary"],
    font=("Segoe UI", 10)
).pack(side="left")

# Mini refresh button
refresh_mini = create_modern_button(filter_frame, "🔄 Refresh", refresh_notices_list, COLORS["primary_light"])
refresh_mini.config(padx=10, pady=4, font=("Segoe UI", 9, "bold"))
refresh_mini.pack(side="right")

# Notices container
notices_container = tk.Frame(right_column, bg=COLORS["white"])
notices_container.pack(fill="both", expand=True, padx=30, pady=(0, 25))

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
status_bar = tk.Frame(root, bg=COLORS["dark"], height=40)
status_bar.pack(side="bottom", fill="x")
status_bar.pack_propagate(False)

status_label = tk.Label(
    status_bar,
    text="✅ Ready | Create, edit, and manage notices efficiently",
    bg=COLORS["dark"],
    fg="#D1D5DB",  # Light gray for better readability
    font=("Segoe UI", 10)
)
status_label.pack(side="left", padx=20)

# Version label
tk.Label(
    status_bar,
    text="Notice Manager v2.0",
    bg=COLORS["dark"],
    fg="#9CA3AF",  # Gray-400 for subtle version text
    font=("Segoe UI", 9)
).pack(side="right", padx=20)

# Add global paste shortcuts
def global_paste(event):
    """Global paste to focused widget"""
    focused_widget = root.focus_get()
    if focused_widget:
        # Check if it's an Entry or Text widget
        if isinstance(focused_widget, (tk.Entry, tk.Text)):
            # Try to paste
            try:
                clipboard_text = root.clipboard_get()
                if isinstance(focused_widget, tk.Entry):
                    if focused_widget.selection_present():
                        focused_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                    focused_widget.insert(tk.INSERT, clipboard_text)
                elif isinstance(focused_widget, tk.Text):
                    try:
                        if focused_widget.tag_ranges(tk.SEL):
                            focused_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                    except:
                        pass
                    focused_widget.insert(tk.INSERT, clipboard_text)
            except:
                pass
    return "break"

# Bind global paste shortcuts
root.bind('<Control-v>', global_paste)
root.bind('<Command-v>', global_paste)  # For Mac

# Also add other useful global shortcuts
def global_select_all(event):
    focused = root.focus_get()
    if isinstance(focused, tk.Entry):
        focused.select_range(0, tk.END)
    elif isinstance(focused, tk.Text):
        focused.tag_add(tk.SEL, "1.0", tk.END)
        focused.mark_set(tk.INSERT, "1.0")
        focused.see(tk.INSERT)
    return "break"

def global_copy(event):
    focused = root.focus_get()
    if isinstance(focused, (tk.Entry, tk.Text)):
        root.clipboard_clear()
        try:
            text = focused.selection_get()
            root.clipboard_append(text)
        except:
            pass
    return "break"

def global_cut(event):
    focused = root.focus_get()
    if isinstance(focused, (tk.Entry, tk.Text)):
        root.clipboard_clear()
        try:
            text = focused.selection_get()
            root.clipboard_append(text)
            focused.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except:
            pass
    return "break"

root.bind('<Control-a>', global_select_all)
root.bind('<Command-a>', global_select_all)  # For Mac
root.bind('<Control-c>', global_copy)
root.bind('<Command-c>', global_copy)  # For Mac
root.bind('<Control-x>', global_cut)
root.bind('<Command-x>', global_cut)  # For Mac

# Make sure the Text widget also has standard copy/cut shortcuts
text_content.bind('<Control-a>', lambda e: text_content.tag_add(tk.SEL, "1.0", tk.END))
text_content.bind('<Command-a>', lambda e: text_content.tag_add(tk.SEL, "1.0", tk.END))

# Initial setup
refresh_notices_list()
update_count()

# Center window
root.update_idletasks()

# Make window resizable
root.minsize(1200, 700)

# Bind F11 to toggle maximize
root.bind("<F11>", lambda e: toggle_maximize())

# Bind Escape to clear selection
root.bind("<Escape>", lambda e: clear_form())

root.mainloop()