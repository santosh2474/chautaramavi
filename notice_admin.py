import os
import sys
import io
import re
import json
import shutil
import uuid
import socket
import hashlib
import threading
import socketserver
import http.server
import urllib.parse
import webbrowser
import subprocess
import platform
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image, ImageTk
from bs4 import BeautifulSoup

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import pillow_heif
    HAS_HEIF = True
except ImportError:
    HAS_HEIF = False


# ── File Paths & Constants ──────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, "notice.html")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "notices")
PREVIEW_PORT = 8082
MOBILE_UPLOAD_PORT = 8767

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.heic', '.heif'}
DOC_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'}

# Badge mapping configuration
BADGE_CONFIG = {
    "urgent": {
        "label": "Urgent",
        "icon": "🔥",
        "bg_class": "bg-red-100 text-red-800",
        "color": "#EF4444",
        "bg_pill": "#3B1822",
        "border_pill": "#EF4444"
    },
    "important": {
        "label": "Important",
        "icon": "⭐",
        "bg_class": "bg-blue-100 text-blue-800",
        "color": "#3B82F6",
        "bg_pill": "#152642",
        "border_pill": "#3B82F6"
    },
    "holiday": {
        "label": "Holiday",
        "icon": "🎉",
        "bg_class": "bg-green-100 text-green-800",
        "color": "#10B981",
        "bg_pill": "#0F2E23",
        "border_pill": "#10B981"
    },
    "normal": {
        "label": "Normal",
        "icon": "📌",
        "bg_class": "bg-yellow-100 text-yellow-800",
        "color": "#F59E0B",
        "bg_pill": "#33240F",
        "border_pill": "#F59E0B"
    }
}


def get_local_ip():
    """Detect local LAN IP address reliably."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def notice_row_id(title):
    """Stable HTML anchor id for a notice row (ASCII-safe for URL hashes)."""
    return "notice-" + hashlib.md5(title.encode("utf-8")).hexdigest()[:10]


def convert_heic_to_jpeg(heic_data):
    """Convert HEIC image data to JPEG bytes."""
    if not HAS_HEIF:
        return None
    try:
        heif_file = pillow_heif.read_heif(heic_data)
        img = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
            heif_file.mode,
            heif_file.stride
        )
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=92)
        return out.getvalue()
    except Exception as e:
        print(f"HEIC conversion error: {e}")
        return None


def parse_multipart(data, boundary):
    """Parse multipart/form-data bytes. Returns list of (name, filename, content) tuples."""
    parts = []
    boundary_bytes = ("--" + boundary).encode()
    raw_parts = data.split(boundary_bytes)

    for part in raw_parts:
        if not part or part == b"--\r\n" or part == b"--":
            continue
        part = part.lstrip(b"\r\n")
        if b"\r\n\r\n" not in part:
            continue
        headers_raw, _, body = part.partition(b"\r\n\r\n")
        body = body.rstrip(b"\r\n")

        name = None
        filename = None
        headers_str = headers_raw.decode("utf-8", errors="replace")
        for line in headers_str.splitlines():
            lower = line.lower()
            if "content-disposition" in lower:
                for seg in line.split(";"):
                    seg = seg.strip()
                    if seg.startswith("name="):
                        name = seg[5:].strip('"')
                    elif seg.startswith("filename="):
                        filename = seg[9:].strip('"')
        if name is not None:
            parts.append((name, filename, body))
    return parts


# ── Mobile Upload Server Handler ─────────────────────────────────────────────
class MobileNoticeUploadHandler(http.server.BaseHTTPRequestHandler):
    """Mobile-friendly web UI for uploading notice files/documents from smartphone."""

    app_ref = None

    def log_message(self, format, *args):
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/status":
            self.send_json({"status": "ok", "app": "NoticeAdmin"})
            return

        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Notice File Uploader | Shree Chautara Mavi</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0F121C;
    color: #E2E8F0;
    min-height: 100vh;
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .card {
    background: #181D2D;
    border: 1px solid #2E3852;
    border-radius: 16px;
    padding: 24px 20px;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  }
  .school-badge {
    display: inline-block;
    background: rgba(40,120,235,0.18);
    color: #58A6FF;
    border: 1px solid rgba(88,166,255,0.3);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.78rem;
    font-weight: 700;
    margin-bottom: 8px;
  }
  h1 { font-size: 1.35rem; font-weight: 800; color: #FFFFFF; margin-bottom: 6px; }
  p.sub { font-size: 0.85rem; color: #94A3B8; margin-bottom: 20px; line-height: 1.4; }
  .drop-zone {
    border: 2px dashed #2E3852;
    border-radius: 12px;
    padding: 28px 16px;
    text-align: center;
    background: #20273C;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 16px;
  }
  .drop-zone:active { border-color: #2878EB; background: rgba(40,120,235,0.1); }
  .drop-icon { font-size: 2.5rem; margin-bottom: 8px; }
  .drop-text { font-size: 0.95rem; font-weight: 600; color: #FFFFFF; }
  .drop-sub { font-size: 0.75rem; color: #94A3B8; margin-top: 4px; }
  input[type="file"] { display: none; }
  .btn {
    width: 100%;
    padding: 14px;
    border-radius: 10px;
    border: none;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    background: #2878EB;
    color: white;
    box-shadow: 0 4px 14px rgba(40,120,235,0.4);
    display: block;
  }
  .btn:active { transform: scale(0.98); }
  .btn:disabled { background: #374151; color: #6B7280; box-shadow: none; }
  .file-list { margin: 16px 0; max-height: 200px; overflow-y: auto; }
  .file-item {
    background: #20273C;
    border: 1px solid #2E3852;
    border-radius: 8px;
    padding: 8px 12px;
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    margin-bottom: 6px;
  }
  .progress-wrap {
    display: none;
    margin-top: 16px;
    background: #20273C;
    border-radius: 8px;
    overflow: hidden;
    height: 10px;
  }
  .progress-bar {
    width: 0%;
    height: 100%;
    background: linear-gradient(90deg, #2878EB, #10B981);
    transition: width 0.2s;
  }
  .msg {
    margin-top: 16px;
    padding: 12px;
    border-radius: 8px;
    font-size: 0.85rem;
    display: none;
    text-align: center;
    font-weight: 600;
  }
  .msg.success { background: rgba(16,185,129,0.2); border: 1px solid #10B981; color: #34D399; }
  .msg.error { background: rgba(239,68,68,0.2); border: 1px solid #EF4444; color: #F87171; }
</style>
</head>
<body>
<div class="card">
  <div class="school-badge">📢 Shree Chautara Mavi</div>
  <h1>Notice File Uploader</h1>
  <p class="sub">Select documents, notice photos, or PDFs from your smartphone to upload directly to the computer's Notice Manager.</p>

  <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
    <div class="drop-icon">📄</div>
    <div class="drop-text">Tap to Choose File or Take Photo</div>
    <div class="drop-sub">PDF, Word, Excel, JPG, PNG, HEIC from camera/gallery</div>
  </div>

  <input type="file" id="fileInput" multiple accept="*/*" onchange="handleFiles(this.files)">

  <div class="file-list" id="fileList"></div>

  <div class="progress-wrap" id="progressWrap">
    <div class="progress-bar" id="progressBar"></div>
  </div>

  <button class="btn" id="uploadBtn" disabled onclick="uploadFiles()">Upload to Notice Manager</button>

  <div class="msg" id="msgBox"></div>
</div>

<script>
let selectedFiles = [];

function handleFiles(files) {
  selectedFiles = Array.from(files);
  const listEl = document.getElementById('fileList');
  listEl.innerHTML = '';
  if (selectedFiles.length === 0) {
    document.getElementById('uploadBtn').disabled = true;
    return;
  }
  selectedFiles.forEach(f => {
    const item = document.createElement('div');
    item.className = 'file-item';
    const sz = (f.size / (1024*1024)).toFixed(2);
    item.innerHTML = '<span>📎 ' + f.name + '</span><span style="color:#94A3B8">' + sz + ' MB</span>';
    listEl.appendChild(item);
  });
  document.getElementById('uploadBtn').disabled = false;
}

function uploadFiles() {
  if (selectedFiles.length === 0) return;
  const btn = document.getElementById('uploadBtn');
  btn.disabled = true;
  btn.textContent = 'Uploading...';

  const pWrap = document.getElementById('progressWrap');
  const pBar = document.getElementById('progressBar');
  pWrap.style.display = 'block';
  pBar.style.width = '20%';

  const formData = new FormData();
  selectedFiles.forEach(f => formData.append('files', f));

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload', true);

  xhr.upload.onprogress = function(e) {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      pBar.style.width = pct + '%';
    }
  };

  xhr.onload = function() {
    pBar.style.width = '100%';
    const msg = document.getElementById('msgBox');
    msg.style.display = 'block';
    if (xhr.status === 200) {
      msg.className = 'msg success';
      msg.innerHTML = '✅ Successfully uploaded ' + selectedFiles.length + ' file(s)! Check your computer screen.';
      document.getElementById('fileList').innerHTML = '';
      selectedFiles = [];
      btn.textContent = 'Upload Complete';
    } else {
      msg.className = 'msg error';
      msg.textContent = '❌ Upload failed (' + xhr.status + '). Please try again.';
      btn.disabled = false;
      btn.textContent = 'Upload to Notice Manager';
    }
  };

  xhr.onerror = function() {
    const msg = document.getElementById('msgBox');
    msg.style.display = 'block';
    msg.className = 'msg error';
    msg.textContent = '❌ Network connection error.';
    btn.disabled = false;
    btn.textContent = 'Upload to Notice Manager';
  };

  xhr.send(formData);
}
</script>
</body>
</html>
"""
        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.path != "/upload":
            self.send_error(404, "Not Found")
            return

        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self.send_error(400, "Bad Request: Expected multipart")
            return

        boundary = None
        for seg in ctype.split(";"):
            seg = seg.strip()
            if seg.startswith("boundary="):
                boundary = seg[9:].strip('"')
                break

        if not boundary:
            self.send_error(400, "Bad Request: Missing boundary")
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)
            parts = parse_multipart(raw_body, boundary)

            uploaded_names = []
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)

            for name, filename, body in parts:
                if not filename or not body:
                    continue
                clean_name = os.path.basename(filename)
                ext = os.path.splitext(clean_name)[1].lower()

                # HEIC conversion
                if ext in {".heic", ".heif"}:
                    conv = convert_heic_to_jpeg(body)
                    if conv:
                        body = conv
                        clean_name = os.path.splitext(clean_name)[0] + ".jpg"
                        ext = ".jpg"

                base_name = os.path.splitext(clean_name)[0]
                safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                unique_fn = f"{safe_base}_{uuid.uuid4().hex[:8]}{ext}"
                dest_p = os.path.join(UPLOAD_FOLDER, unique_fn)

                with open(dest_p, "wb") as f:
                    f.write(body)

                uploaded_names.append(unique_fn)

            if self.app_ref and hasattr(self.app_ref, "on_mobile_upload_success"):
                self.app_ref.root.after(100, lambda: self.app_ref.on_mobile_upload_success(uploaded_names))

            self.send_json({"status": "ok", "uploaded": uploaded_names})
        except Exception as e:
            print(f"Mobile upload handler error: {e}")
            self.send_json({"status": "error", "message": str(e)}, 500)


# ── Main Notice Admin App ───────────────────────────────────────────────────
class NoticeAdminApp:
    """Modern, responsive, feature-rich admin suite for Shree Chautara Mavi Notice Portal."""

    def __init__(self, root):
        self.root = root
        self.root.title("Shree Chautara Mavi - Notice Management Suite")
        self.root.geometry("1280x760")
        self.root.minsize(980, 600)

        # State tracking
        self.notices = []
        self.selected_notice_tuple = None  # (title, date_bs)
        self.current_attached_file_path = None
        self.preview_thumbnail_photo = None
        self.qr_photo = None
        self.active_filter_badge = "all"

        # Servers
        self.preview_httpd = None
        self.preview_thread = None
        self.preview_running = False

        self.mobile_httpd = None
        self.mobile_thread = None
        self.mobile_running = False

        self.init_directories()
        self.setup_styles()
        self.create_widgets()
        self.setup_keyboard_shortcuts()
        self.refresh_notices()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_directories(self):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        if not os.path.exists(HTML_FILE):
            self.create_default_html_file()

    def create_default_html_file(self):
        default_html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Notice Portal | Chautara Mavi</title>
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet"/>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"/>
</head>
<body class="bg-gray-50">
<div class="container mx-auto p-4">
  <table id="noticeTable" class="w-full">
    <thead>
      <tr><th>Title</th><th>Content</th><th>Date (BS)</th></tr>
    </thead>
    <tbody></tbody>
  </table>
</div>
</body>
</html>"""
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(default_html)

    def setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Color Theme: Deep dark obsidian & modern sapphire
        self.c_bg = "#0F121C"
        self.c_panel = "#181D2D"
        self.c_card = "#20273C"
        self.c_card_active = "#26324D"
        self.c_border = "#2E3852"
        self.c_text = "#E2E8F0"
        self.c_muted = "#94A3B8"
        self.c_primary = "#2878EB"
        self.c_primary_hover = "#1C62C9"
        self.c_success = "#10B981"
        self.c_danger = "#EF4444"
        self.c_warning = "#F59E0B"
        self.c_purple = "#8B5CF6"

        self.root.configure(bg=self.c_bg)

        # Scrollbar Styling
        self.style.configure(
            "Notice.Vertical.TScrollbar",
            background=self.c_card,
            troughcolor=self.c_panel,
            bordercolor=self.c_panel,
            arrowcolor=self.c_muted
        )

    def create_widgets(self):
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header Toolbar ───────────────────────────────────────────
        self.header_frame = tk.Frame(self.root, bg=self.c_panel, height=65, padx=20, pady=10)
        self.header_frame.grid(row=0, column=0, sticky="ew")

        title_box = tk.Frame(self.header_frame, bg=self.c_panel)
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        lbl_school = tk.Label(
            title_box,
            text="📢 Shree Chautara Secondary School",
            font=("Segoe UI", 13, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        )
        lbl_school.pack(anchor="w")

        lbl_sub = tk.Label(
            title_box,
            text="Notice & Announcement Portal Management Suite (HTML & DataTables)",
            font=("Segoe UI", 9),
            fg=self.c_muted,
            bg=self.c_panel
        )
        lbl_sub.pack(anchor="w")

        btn_box = tk.Frame(self.header_frame, bg=self.c_panel)
        btn_box.pack(side=tk.RIGHT, fill=tk.Y)

        self.btn_preview_srv = tk.Button(
            btn_box,
            text="🌐 Launch Live Website Preview",
            bg=self.c_primary,
            fg="#FFFFFF",
            activebackground=self.c_primary_hover,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.toggle_preview_server
        )
        self.btn_preview_srv.pack(side=tk.LEFT, padx=6)

        self.btn_mobile_srv = tk.Button(
            btn_box,
            text="📱 Mobile QR Upload",
            bg="#3B82F6",
            fg="#FFFFFF",
            activebackground="#2563EB",
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.open_mobile_upload_dialog
        )
        self.btn_mobile_srv.pack(side=tk.LEFT, padx=6)

        # ── 2. Main Paned Window (Left Notices, Right Form) ─────────────────
        self.paned = tk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL,
            bg=self.c_border,
            sashwidth=6,
            relief="flat"
        )
        self.paned.grid(row=1, column=0, sticky="nsew")

        self.left_frame = tk.Frame(self.paned, bg=self.c_bg, padx=14, pady=14)
        self.paned.add(self.left_frame, minsize=520, width=680)

        self.right_frame = tk.Frame(self.paned, bg=self.c_panel, padx=16, pady=14)
        self.paned.add(self.right_frame, minsize=420)

        self.build_left_panel()
        self.build_right_panel()

        # ── 3. Status Bar ───────────────────────────────────────────────────
        self.status_bar = tk.Frame(self.root, bg=self.c_panel, height=28, padx=16)
        self.status_bar.grid(row=2, column=0, sticky="ew")

        self.lbl_status = tk.Label(
            self.status_bar,
            text="✅ Ready | Select or create a notice to manage",
            font=("Segoe UI", 9),
            fg=self.c_muted,
            bg=self.c_panel
        )
        self.lbl_status.pack(side=tk.LEFT, pady=4)

        self.lbl_count = tk.Label(
            self.status_bar,
            text="0 Notices",
            font=("Segoe UI", 9, "bold"),
            fg="#58A6FF",
            bg=self.c_panel
        )
        self.lbl_count.pack(side=tk.RIGHT, pady=4)

    # ── Left Panel: Notices Search, Filter Pills & List ──────────────────────
    def build_left_panel(self):
        # Top bar of Left Panel
        top_bar = tk.Frame(self.left_frame, bg=self.c_bg)
        top_bar.pack(fill=tk.X, pady=(0, 10))

        lbl_list_title = tk.Label(
            top_bar,
            text="📋 All Published Notices",
            font=("Segoe UI", 12, "bold"),
            fg="#FFFFFF",
            bg=self.c_bg
        )
        lbl_list_title.pack(side=tk.LEFT)

        btn_refresh = tk.Button(
            top_bar,
            text="🔄 Refresh",
            bg=self.c_card,
            fg=self.c_text,
            activebackground=self.c_panel,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=self.c_border,
            command=self.refresh_notices
        )
        btn_refresh.pack(side=tk.RIGHT)

        # Search Bar Frame
        search_wrap = tk.Frame(
            self.left_frame,
            bg=self.c_card,
            padx=10,
            pady=6,
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        search_wrap.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            search_wrap,
            text="🔍",
            font=("Segoe UI", 10),
            bg=self.c_card,
            fg=self.c_muted
        ).pack(side=tk.LEFT, padx=(2, 6))

        self.ent_search = tk.Entry(
            search_wrap,
            font=("Segoe UI", 10),
            bg=self.c_card,
            fg="#FFFFFF",
            insertbackground="#58A6FF",
            relief="flat",
            highlightthickness=0
        )
        self.ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ent_search.bind("<KeyRelease>", lambda e: self.filter_and_render_notices())
        self.setup_entry_context_menu(self.ent_search)

        btn_clear_search = tk.Button(
            search_wrap,
            text="✕",
            bg=self.c_card,
            fg=self.c_muted,
            activebackground=self.c_card,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.clear_search
        )
        btn_clear_search.pack(side=tk.RIGHT)

        # Quick Filter Pills Bar
        pill_bar = tk.Frame(self.left_frame, bg=self.c_bg)
        pill_bar.pack(fill=tk.X, pady=(0, 10))

        self.filter_buttons = {}
        pills = [
            ("all", "All"),
            ("urgent", "🔥 Urgent"),
            ("important", "⭐ Important"),
            ("holiday", "🎉 Holiday"),
            ("normal", "📌 Normal"),
            ("file", "📎 With Attachment")
        ]

        for p_key, p_label in pills:
            btn = tk.Button(
                pill_bar,
                text=p_label,
                font=("Segoe UI", 8, "bold"),
                relief="flat",
                padx=8,
                pady=3,
                cursor="hand2",
                bg=self.c_primary if p_key == "all" else self.c_panel,
                fg="#FFFFFF" if p_key == "all" else self.c_muted,
                activebackground=self.c_primary,
                activeforeground="#FFFFFF",
                command=lambda k=p_key: self.set_badge_filter(k)
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.filter_buttons[p_key] = btn

        # Scrollable Notices List Canvas
        list_container = tk.Frame(self.left_frame, bg=self.c_bg)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.notices_canvas = tk.Canvas(list_container, bg=self.c_bg, highlightthickness=0)
        self.notices_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.notices_canvas.yview
        )
        self.notices_scrollable_frame = tk.Frame(self.notices_canvas, bg=self.c_bg)

        self.notices_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.notices_canvas.configure(scrollregion=self.notices_canvas.bbox("all"))
        )

        self.canvas_window_id = self.notices_canvas.create_window(
            (0, 0),
            window=self.notices_scrollable_frame,
            anchor="nw"
        )

        def _on_canvas_configure(e):
            self.notices_canvas.itemconfig(self.canvas_window_id, width=e.width)

        self.notices_canvas.bind("<Configure>", _on_canvas_configure)
        self.notices_canvas.configure(yscrollcommand=self.notices_scrollbar.set)

        self.notices_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.notices_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel support
        def _on_wheel(e):
            if self.notices_canvas.winfo_exists():
                self.notices_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        self.notices_canvas.bind_all("<MouseWheel>", _on_wheel)

    # ── Right Panel: Notice Edit Form & Live Preview Card ────────────────────
    def build_right_panel(self):
        # Scrollable right panel so no field gets cut off on 1366x768
        canvas_r = tk.Canvas(self.right_frame, bg=self.c_panel, highlightthickness=0)
        scrollbar_r = ttk.Scrollbar(self.right_frame, orient="vertical", command=canvas_r.yview)
        scroll_r = tk.Frame(canvas_r, bg=self.c_panel)

        scroll_r.bind(
            "<Configure>",
            lambda e: canvas_r.configure(scrollregion=canvas_r.bbox("all"))
        )

        r_win_id = canvas_r.create_window((0, 0), window=scroll_r, anchor="nw")

        def _on_r_config(e):
            canvas_r.itemconfig(r_win_id, width=e.width)

        canvas_r.bind("<Configure>", _on_r_config)
        canvas_r.configure(yscrollcommand=scrollbar_r.set)

        canvas_r.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_r.pack(side=tk.RIGHT, fill=tk.Y)

        # Header of right panel
        r_header = tk.Frame(scroll_r, bg=self.c_panel)
        r_header.pack(fill=tk.X, pady=(0, 8))

        self.lbl_form_mode = tk.Label(
            r_header,
            text="📝 Create / Edit Notice",
            font=("Segoe UI", 12, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        )
        self.lbl_form_mode.pack(side=tk.LEFT)

        btn_new = tk.Button(
            r_header,
            text="➕ New Notice",
            bg=self.c_success,
            fg="#FFFFFF",
            activebackground="#059669",
            activeforeground="#FFFFFF",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.clear_form
        )
        btn_new.pack(side=tk.RIGHT)

        # 1. Attachment Visual Preview Card
        self.preview_card = tk.Frame(
            scroll_r,
            bg=self.c_card,
            padx=12,
            pady=10,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        self.preview_card.pack(fill=tk.X, pady=(0, 12))

        self.lbl_preview_media = tk.Label(
            self.preview_card,
            text="📁 No Attachment Preview\nAttach an image or document to see preview here",
            font=("Segoe UI", 9),
            fg=self.c_muted,
            bg=self.c_card,
            height=6
        )
        self.lbl_preview_media.pack(fill=tk.BOTH, expand=True)

        self.lbl_file_meta = tk.Label(
            self.preview_card,
            text="No file attached",
            font=("Segoe UI", 8),
            fg=self.c_muted,
            bg=self.c_card,
            anchor="w",
            wraplength=400
        )
        self.lbl_file_meta.pack(fill=tk.X, pady=(4, 0))

        # 2. Form Fields Card
        form_card = tk.Frame(
            scroll_r,
            bg=self.c_card,
            padx=14,
            pady=12,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        form_card.pack(fill=tk.X, pady=(0, 12))

        def create_field_label(parent, text):
            l = tk.Label(
                parent,
                text=text,
                font=("Segoe UI", 9, "bold"),
                fg="#FFFFFF",
                bg=self.c_card,
                anchor="w"
            )
            l.pack(fill=tk.X, pady=(6, 3))
            return l

        # Title Field
        create_field_label(form_card, "Notice Title *")
        self.ent_title = tk.Entry(
            form_card,
            font=("Segoe UI", 10),
            bg=self.c_panel,
            fg="#FFFFFF",
            insertbackground="#58A6FF",
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        self.ent_title.pack(fill=tk.X, ipady=5, pady=(0, 6))
        self.setup_entry_context_menu(self.ent_title)

        # Content Field
        create_field_label(form_card, "Notice Content / Details *")
        content_wrap = tk.Frame(form_card, bg=self.c_border, padx=1, pady=1)
        content_wrap.pack(fill=tk.X, pady=(0, 6))

        self.txt_content = tk.Text(
            content_wrap,
            font=("Segoe UI", 9),
            bg=self.c_panel,
            fg="#FFFFFF",
            insertbackground="#58A6FF",
            relief="flat",
            height=5,
            wrap="word",
            padx=8,
            pady=6
        )
        self.txt_content.pack(fill=tk.BOTH, expand=True)
        self.setup_entry_context_menu(self.txt_content)

        # Date & Badge Container (2 columns)
        date_badge_frame = tk.Frame(form_card, bg=self.c_card)
        date_badge_frame.pack(fill=tk.X, pady=(0, 8))
        date_badge_frame.columnconfigure(0, weight=1)
        date_badge_frame.columnconfigure(1, weight=1)

        # Column 0: Date (BS)
        col_date = tk.Frame(date_badge_frame, bg=self.c_card)
        col_date.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        date_lbl_row = tk.Frame(col_date, bg=self.c_card)
        date_lbl_row.pack(fill=tk.X)
        tk.Label(
            date_lbl_row,
            text="Date (BS) *",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg=self.c_card
        ).pack(side=tk.LEFT)

        btn_today = tk.Button(
            date_lbl_row,
            text="📅 Auto Today",
            font=("Segoe UI", 7, "bold"),
            bg=self.c_panel,
            fg="#58A6FF",
            activebackground=self.c_primary,
            activeforeground="#FFFFFF",
            relief="flat",
            padx=6,
            pady=1,
            cursor="hand2",
            command=self.fill_today_bs
        )
        btn_today.pack(side=tk.RIGHT)

        self.ent_date = tk.Entry(
            col_date,
            font=("Segoe UI", 10),
            bg=self.c_panel,
            fg="#FFFFFF",
            insertbackground="#58A6FF",
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        self.ent_date.pack(fill=tk.X, ipady=5, pady=(4, 2))
        self.setup_entry_context_menu(self.ent_date)

        tk.Label(
            col_date,
            text="Format: YYYY/MM/DD (e.g. 2083/05/26)",
            font=("Segoe UI", 7),
            fg=self.c_muted,
            bg=self.c_card,
            anchor="w"
        ).pack(fill=tk.X)

        # Column 1: Badge Selector
        col_badge = tk.Frame(date_badge_frame, bg=self.c_card)
        col_badge.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        tk.Label(
            col_badge,
            text="Badge Category",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg=self.c_card,
            anchor="w"
        ).pack(fill=tk.X)

        self.cbo_badge = ttk.Combobox(
            col_badge,
            values=["Normal", "Urgent", "Important", "Holiday"],
            font=("Segoe UI", 9),
            state="readonly"
        )
        self.cbo_badge.set("Normal")
        self.cbo_badge.pack(fill=tk.X, ipady=3, pady=(4, 2))

        tk.Label(
            col_badge,
            text="Sets badge color & icon tag",
            font=("Segoe UI", 7),
            fg=self.c_muted,
            bg=self.c_card,
            anchor="w"
        ).pack(fill=tk.X)

        # Attachment Controls
        create_field_label(form_card, "Attachment File (Optional)")
        attach_box = tk.Frame(form_card, bg=self.c_card)
        attach_box.pack(fill=tk.X, pady=(2, 6))

        btn_browse = tk.Button(
            attach_box,
            text="📁 Browse File",
            bg=self.c_primary,
            fg="#FFFFFF",
            activebackground=self.c_primary_hover,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.browse_file
        )
        btn_browse.pack(side=tk.LEFT, padx=(0, 6))

        btn_mobile_attach = tk.Button(
            attach_box,
            text="📱 QR Upload",
            bg="#3B82F6",
            fg="#FFFFFF",
            activebackground="#2563EB",
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.open_mobile_upload_dialog
        )
        btn_mobile_attach.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_open_file = tk.Button(
            attach_box,
            text="📂 Open",
            bg=self.c_panel,
            fg=self.c_text,
            activebackground=self.c_card_active,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
            state="disabled",
            command=self.open_current_attached_file
        )
        self.btn_open_file.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_remove_file = tk.Button(
            attach_box,
            text="✕ Remove",
            bg=self.c_panel,
            fg=self.c_danger,
            activebackground=self.c_card_active,
            activeforeground=self.c_danger,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
            state="disabled",
            command=self.remove_attached_file
        )
        self.btn_remove_file.pack(side=tk.LEFT)

        # 3. Action Buttons Card
        action_card = tk.Frame(scroll_r, bg=self.c_panel)
        action_card.pack(fill=tk.X, pady=(4, 16))

        self.btn_save = tk.Button(
            action_card,
            text="💾 Save / Publish Notice",
            bg=self.c_primary,
            fg="#FFFFFF",
            activebackground=self.c_primary_hover,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=10,
            cursor="hand2",
            command=self.submit_notice
        )
        self.btn_save.pack(fill=tk.X, pady=(0, 8))

        sub_btns = tk.Frame(action_card, bg=self.c_panel)
        sub_btns.pack(fill=tk.X)

        btn_folder = tk.Button(
            sub_btns,
            text="📂 Open 'notices/' Folder",
            bg=self.c_card,
            fg=self.c_text,
            activebackground=self.c_panel,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=self.c_border,
            command=self.open_notices_folder
        )
        btn_folder.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.btn_delete = tk.Button(
            sub_btns,
            text="🗑 Delete Notice",
            bg=self.c_card,
            fg=self.c_danger,
            activebackground=self.c_panel,
            activeforeground=self.c_danger,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
            state="disabled",
            highlightthickness=1,
            highlightbackground=self.c_border,
            command=self.delete_selected_notice
        )
        self.btn_delete.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0))

    # ── Context Menu (Copy/Paste/Cut) ────────────────────────────────────────
    def setup_entry_context_menu(self, widget):
        menu = tk.Menu(widget, tearoff=0, bg=self.c_card, fg="#FFFFFF", activebackground=self.c_primary)
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(
            label="Select All",
            command=lambda: widget.select_range(0, tk.END) if isinstance(widget, tk.Entry) else widget.tag_add("sel", "1.0", tk.END)
        )

        def _show_menu(e):
            menu.tk_popup(e.x_root, e.y_root)

        widget.bind("<Button-3>", _show_menu)

    # ── Keyboard Shortcuts ───────────────────────────────────────────────────
    def setup_keyboard_shortcuts(self):
        self.root.bind("<F5>", lambda e: self.refresh_notices())
        self.root.bind("<Escape>", lambda e: self.clear_form())
        self.root.bind("<Control-s>", lambda e: self.submit_notice())
        self.root.bind("<Control-S>", lambda e: self.submit_notice())
        self.root.bind("<Control-f>", lambda e: self.ent_search.focus_set())
        self.root.bind("<Control-F>", lambda e: self.ent_search.focus_set())

    # ── HTML Data Persistence (BeautifulSoup) ────────────────────────────────
    def load_table(self):
        try:
            if not os.path.exists(HTML_FILE):
                self.create_default_html_file()

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
            messagebox.showerror("HTML Load Error", f"Failed to parse {HTML_FILE}:\n{str(e)}")
            return None

    def save_table(self, soup):
        try:
            with open(HTML_FILE, "w", encoding="utf-8") as file:
                file.write(str(soup.prettify() if soup else ""))
            self.sync_ticker_snapshot(soup)
            return True
        except Exception as e:
            messagebox.showerror("HTML Save Error", f"Failed to save {HTML_FILE}:\n{str(e)}")
            return False

    def collect_notices(self, soup):
        """Read every notice row from the table, newest first."""
        table = soup.find("table", id="noticeTable") if soup else None
        tbody = table.find("tbody") if table else None
        if not tbody:
            return []
        rows = []
        for tr in tbody.find_all("tr", recursive=False):
            title_td = tr.find("td", attrs={"data-label": "Title"})
            if not title_td:
                continue
            title = title_td.get_text(" ", strip=True)
            if not title:
                continue
            date_td = tr.find("td", attrs={"data-label": "Date"})
            content_el = tr.find("div", class_="notice-content")
            badge_el = tr.find("span", class_="badge")
            file_el = tr.find("a", class_="download-link")
            rows.append({
                "id": tr.get("id", "") or notice_row_id(title),
                "title": title,
                "content": content_el.get_text(" ", strip=True) if content_el else "",
                "date": (date_td.get("data-date", "") if date_td else ""),
                "badge": badge_el.get_text(" ", strip=True) if badge_el else "",
                "file": (file_el.get("href", "") if file_el else ""),
                "sort": (date_td.get("data-sort", "") if date_td else ""),
            })
        rows.sort(key=lambda r: r["sort"], reverse=True)
        return rows

    def sync_ticker_snapshot(self, soup):
        """Rewrite the embedded snapshot inside ticker/ticker.js so the marquee
        reflects the latest notices even when index.html is opened via file://
        (where the live fetch of notice.html is blocked by the browser)."""
        try:
            top = [
                {k: r[k] for k in ("id", "title", "content", "date", "badge", "file")}
                for r in self.collect_notices(soup)[:3]
            ]
            self.write_ticker_snapshot(top)
        except Exception as e:
            print(f"Ticker snapshot sync skipped: {e}")

    def write_ticker_snapshot(self, items):
        path = os.path.join(BASE_DIR, "ticker", "ticker.js")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        marker = "var FALLBACK_NOTICES = ["
        start = src.find(marker)
        if start == -1:
            return
        open_end = start + len(marker)
        close = src.find("];", open_end)
        if close == -1:
            return
        blocks = [json.dumps(it, ensure_ascii=False, indent=4) for it in items]
        body = ",\n".join(blocks)
        indented = "\n".join("        " + line for line in body.splitlines())
        new_src = src[:open_end] + "\n" + indented + "\n    " + src[close:]
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_src)

    def create_row_tag(self, title, content, date_bs, badge, badge_class, file_link):
        parts = date_bs.split("/")
        year = parts[0]
        month = parts[1].zfill(2) if len(parts) > 1 else "01"
        day = parts[2].zfill(2) if len(parts) > 2 else "01"
        sort_date = f"{year}{month}{day}"

        notice_id = notice_row_id(title)

        file_name = os.path.basename(file_link) if file_link else ""
        badge_lower = badge.lower().replace("🔥", "").replace("⭐", "").replace("🎉", "").replace("📌", "").strip()

        cfg = BADGE_CONFIG.get(badge_lower, BADGE_CONFIG["normal"])
        badge_icon = cfg["icon"]
        clean_badge_text = cfg["label"] if badge_lower in BADGE_CONFIG else badge

        row_html = f"""
<tr id="{notice_id}">
<td class="font-medium text-gray-900" data-label="Title">{title}</td>
<td class="text-gray-700" data-label="Content">
    <div class="notice-content">{content}</div>
    {"<a href='" + file_link + "' target='_blank' class='download-link text-blue-600'><i class='fas fa-paperclip'></i> " + file_name + "</a>" if file_link else ""}
    <span class="badge {badge_class}">{badge_icon} {clean_badge_text}</span>
</td>
<td class="text-gray-600" data-label="Date" data-sort="{sort_date}" data-date="{date_bs}">
    <div class="font-medium"><i class="far fa-calendar-alt"></i> {date_bs}</div>
</td>
</tr>
"""
        return BeautifulSoup(row_html, "html.parser").tr

    def parse_all_notices_from_soup(self):
        res = self.load_table()
        if not res:
            return []
        _, tbody = res
        rows = tbody.find_all("tr")
        notices = []

        for row in rows:
            title_cell = row.find("td", {"data-label": "Title"})
            content_div = row.find("div", class_="notice-content")
            date_cell = row.find("td", {"data-label": "Date"})
            badge_span = row.find("span", class_="badge")

            if title_cell and date_cell:
                title = title_cell.text.strip()
                content = content_div.text.strip() if content_div else ""
                date = date_cell.get("data-date", "").strip() or date_cell.text.strip()
                badge_raw = badge_span.text.strip() if badge_span else "Normal"

                # Extract file link
                download_link = row.find("a", class_="download-link")
                file_link = download_link.get("href", "").strip() if download_link else ""
                has_file = bool(file_link)
                file_name = os.path.basename(file_link) if has_file else ""

                file_exists = False
                if has_file:
                    full_p = os.path.join(BASE_DIR, file_link) if not os.path.isabs(file_link) else file_link
                    file_exists = os.path.exists(full_p)

                notices.append({
                    "title": title,
                    "content": content,
                    "date": date,
                    "badge": badge_raw,
                    "has_file": has_file,
                    "file_link": file_link,
                    "file_name": file_name,
                    "file_exists": file_exists
                })

        # Sort newest first by BS date
        return sorted(notices, key=lambda x: x["date"], reverse=True)

    # ── Notice Rendering & Filtering ─────────────────────────────────────────
    def refresh_notices(self):
        self.notices = self.parse_all_notices_from_soup()
        self.filter_and_render_notices()
        self.lbl_count.config(text=f"{len(self.notices)} Notice{'s' if len(self.notices) != 1 else ''}")

    def set_badge_filter(self, badge_key):
        self.active_filter_badge = badge_key
        for k, btn in self.filter_buttons.items():
            if k == badge_key:
                btn.config(bg=self.c_primary, fg="#FFFFFF")
            else:
                btn.config(bg=self.c_panel, fg=self.c_muted)
        self.filter_and_render_notices()

    def clear_search(self):
        self.ent_search.delete(0, tk.END)
        self.filter_and_render_notices()

    def filter_and_render_notices(self):
        for w in self.notices_scrollable_frame.winfo_children():
            w.destroy()

        query = self.ent_search.get().strip().lower()
        filter_type = self.active_filter_badge

        filtered = []
        for n in self.notices:
            # Query match
            if query:
                in_title = query in n["title"].lower()
                in_content = query in n["content"].lower()
                in_date = query in n["date"].lower()
                in_badge = query in n["badge"].lower()
                in_file = query in n["file_name"].lower()
                if not (in_title or in_content or in_date or in_badge or in_file):
                    continue

            # Badge filter match
            if filter_type != "all":
                if filter_type == "file":
                    if not n["has_file"]:
                        continue
                else:
                    b_clean = n["badge"].lower()
                    if filter_type not in b_clean:
                        continue

            filtered.append(n)

        if not filtered:
            empty_box = tk.Frame(self.notices_scrollable_frame, bg=self.c_bg, pady=40)
            empty_box.pack(fill=tk.BOTH, expand=True)

            tk.Label(
                empty_box,
                text="📭 No matching notices found",
                font=("Segoe UI", 12, "bold"),
                fg=self.c_muted,
                bg=self.c_bg
            ).pack()

            tk.Label(
                empty_box,
                text="Try changing your search query or filter tab, or create a new notice.",
                font=("Segoe UI", 9),
                fg=self.c_muted,
                bg=self.c_bg,
                pady=6
            ).pack()
            return

        for idx, notice in enumerate(filtered):
            self.create_notice_card(self.notices_scrollable_frame, notice, idx)

    def create_notice_card(self, parent, notice, idx):
        is_selected = (
            self.selected_notice_tuple and
            self.selected_notice_tuple[0] == notice["title"] and
            self.selected_notice_tuple[1] == notice["date"]
        )

        card_bg = self.c_card_active if is_selected else self.c_card
        border_col = self.c_primary if is_selected else self.c_border

        card = tk.Frame(
            parent,
            bg=card_bg,
            padx=14,
            pady=12,
            relief="flat",
            highlightthickness=1,
            highlightbackground=border_col
        )
        card.pack(fill=tk.X, pady=(0, 8))

        # Click card to load
        card.bind("<Button-1>", lambda e, n=notice: self.load_notice_for_editing(n["title"], n["date"]))

        # Top row of card (Badge, Date, Index)
        top_row = tk.Frame(card, bg=card_bg)
        top_row.pack(fill=tk.X, pady=(0, 6))
        top_row.bind("<Button-1>", lambda e, n=notice: self.load_notice_for_editing(n["title"], n["date"]))

        # Badge pill
        b_clean = notice["badge"].lower().replace("🔥", "").replace("⭐", "").replace("🎉", "").replace("📌", "").strip()
        b_cfg = BADGE_CONFIG.get(b_clean, BADGE_CONFIG["normal"])

        pill = tk.Label(
            top_row,
            text=f"{b_cfg['icon']} {b_cfg['label']}",
            font=("Segoe UI", 8, "bold"),
            fg=b_cfg["color"],
            bg=b_cfg["bg_pill"],
            padx=8,
            pady=2,
            relief="flat",
            highlightthickness=1,
            highlightbackground=b_cfg["border_pill"]
        )
        pill.pack(side=tk.LEFT)

        # Date pill
        date_lbl = tk.Label(
            top_row,
            text=f"📅 {notice['date']}",
            font=("Segoe UI", 8),
            fg=self.c_muted,
            bg=card_bg
        )
        date_lbl.pack(side=tk.LEFT, padx=10)

        # Title
        title_lbl = tk.Label(
            card,
            text=notice["title"],
            font=("Segoe UI", 10, "bold"),
            fg="#FFFFFF",
            bg=card_bg,
            anchor="w",
            justify="left",
            wraplength=480,
            cursor="hand2"
        )
        title_lbl.pack(fill=tk.X, pady=(0, 4))
        title_lbl.bind("<Button-1>", lambda e, n=notice: self.load_notice_for_editing(n["title"], n["date"]))

        # Content snippet
        c_snippet = notice["content"].replace("\n", " ").strip()
        if len(c_snippet) > 130:
            c_snippet = c_snippet[:127] + "..."

        if c_snippet:
            cnt_lbl = tk.Label(
                card,
                text=c_snippet,
                font=("Segoe UI", 8),
                fg=self.c_muted,
                bg=card_bg,
                anchor="w",
                justify="left",
                wraplength=480
            )
            cnt_lbl.pack(fill=tk.X, pady=(0, 6))
            cnt_lbl.bind("<Button-1>", lambda e, n=notice: self.load_notice_for_editing(n["title"], n["date"]))

        # Bottom row of card (Attachment info + Action Buttons)
        btm_row = tk.Frame(card, bg=card_bg)
        btm_row.pack(fill=tk.X, pady=(2, 0))
        btm_row.bind("<Button-1>", lambda e, n=notice: self.load_notice_for_editing(n["title"], n["date"]))

        if notice["has_file"]:
            f_color = "#58A6FF" if notice.get("file_exists", True) else self.c_danger
            fn_trunc = notice["file_name"]
            if len(fn_trunc) > 28:
                fn_trunc = fn_trunc[:25] + "..."

            f_lbl = tk.Label(
                btm_row,
                text=f"📎 {fn_trunc}",
                font=("Segoe UI", 8),
                fg=f_color,
                bg=card_bg
            )
            f_lbl.pack(side=tk.LEFT)
        else:
            no_f = tk.Label(
                btm_row,
                text="Text notice",
                font=("Segoe UI", 8),
                fg=self.c_muted,
                bg=card_bg
            )
            no_f.pack(side=tk.LEFT)

        # Card action buttons
        actions = tk.Frame(btm_row, bg=card_bg)
        actions.pack(side=tk.RIGHT)

        if notice["has_file"]:
            btn_view = tk.Button(
                actions,
                text="📂 View File",
                font=("Segoe UI", 8, "bold"),
                bg=self.c_panel,
                fg="#58A6FF",
                activebackground=self.c_primary,
                activeforeground="#FFFFFF",
                relief="flat",
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda t=notice["title"], d=notice["date"]: self.open_notice_file_by_name(t, d)
            )
            btn_view.pack(side=tk.LEFT, padx=(0, 4))

        btn_edit = tk.Button(
            actions,
            text="✏️ Edit",
            font=("Segoe UI", 8, "bold"),
            bg=self.c_panel,
            fg="#FFFFFF",
            activebackground=self.c_primary,
            activeforeground="#FFFFFF",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=lambda n=notice: self.load_notice_for_editing(n["title"], n["date"])
        )
        btn_edit.pack(side=tk.LEFT, padx=(0, 4))

        btn_del = tk.Button(
            actions,
            text="🗑",
            font=("Segoe UI", 8, "bold"),
            bg=self.c_panel,
            fg=self.c_danger,
            activebackground=self.c_danger,
            activeforeground="#FFFFFF",
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=lambda t=notice["title"], d=notice["date"]: self.delete_notice_prompt(t, d)
        )
        btn_del.pack(side=tk.LEFT)

    # ── Form Operations: Load, Save, Delete, Clear ───────────────────────────
    def load_notice_for_editing(self, title, date_bs):
        self.selected_notice_tuple = (title, date_bs)
        self.lbl_form_mode.config(text="✏️ Edit Notice")
        self.btn_save.config(text="💾 Update Notice", bg=self.c_warning)
        self.btn_delete.config(state="normal")

        # Find in notices
        target = None
        for n in self.notices:
            if n["title"] == title and n["date"] == date_bs:
                target = n
                break

        if not target:
            return

        # Populate fields
        self.ent_title.delete(0, tk.END)
        self.ent_title.insert(0, target["title"])

        self.txt_content.delete("1.0", tk.END)
        self.txt_content.insert(tk.END, target["content"])

        self.ent_date.delete(0, tk.END)
        self.ent_date.insert(0, target["date"])

        # Badge
        b_clean = target["badge"].lower().replace("🔥", "").replace("⭐", "").replace("🎉", "").replace("📌", "").strip()
        matched_badge = "Normal"
        for b_name in ["Urgent", "Important", "Holiday", "Normal"]:
            if b_name.lower() == b_clean:
                matched_badge = b_name
                break
        self.cbo_badge.set(matched_badge)

        # File
        if target["has_file"] and target["file_link"]:
            full_p = os.path.join(BASE_DIR, target["file_link"]) if not os.path.isabs(target["file_link"]) else target["file_link"]
            self.current_attached_file_path = full_p
            self.update_file_preview(full_p)
        else:
            self.current_attached_file_path = None
            self.update_file_preview(None)

        self.filter_and_render_notices()
        self.lbl_status.config(text=f"📝 Editing notice: '{title}'")

    def clear_form(self):
        self.selected_notice_tuple = None
        self.current_attached_file_path = None

        self.lbl_form_mode.config(text="📝 Create New Notice")
        self.btn_save.config(text="💾 Save / Publish Notice", bg=self.c_primary)
        self.btn_delete.config(state="disabled")

        self.ent_title.delete(0, tk.END)
        self.txt_content.delete("1.0", tk.END)
        self.ent_date.delete(0, tk.END)
        self.cbo_badge.set("Normal")

        self.update_file_preview(None)
        self.filter_and_render_notices()
        self.lbl_status.config(text="✨ Form cleared. Ready for new notice.")
        self.ent_title.focus_set()

    def fill_today_bs(self):
        """Auto-computes an approximate current BS year/date template."""
        now = datetime.now()
        approx_bs_year = now.year + 57
        month_str = str(now.month).zfill(2)
        day_str = str(now.day).zfill(2)

        val = f"{approx_bs_year}/{month_str}/{day_str}"
        self.ent_date.delete(0, tk.END)
        self.ent_date.insert(0, val)

    def submit_notice(self):
        title = self.ent_title.get().strip()
        content = self.txt_content.get("1.0", tk.END).strip()
        date_bs = self.ent_date.get().strip()
        badge = self.cbo_badge.get().strip() or "Normal"

        if not title or not content or not date_bs:
            messagebox.showwarning("Incomplete Form", "Please fill in Notice Title, Content, and Date (BS).")
            return

        # Validate date format YYYY/MM/DD
        parts = date_bs.split("/")
        if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit() or not parts[2].isdigit():
            messagebox.showwarning("Invalid Date", "Date must be in BS format: YYYY/MM/DD\nExample: 2083/05/26")
            return

        year = parts[0]
        month = parts[1].zfill(2)
        day = parts[2].zfill(2)
        normalized_date = f"{year}/{month}/{day}"

        # Resolve badge class
        badge_key = badge.lower()
        cfg = BADGE_CONFIG.get(badge_key, BADGE_CONFIG["normal"])
        badge_class = cfg["bg_class"]

        # Handle attachment copy if new file selected
        file_link = ""
        if self.current_attached_file_path and os.path.exists(self.current_attached_file_path):
            abs_curr = os.path.abspath(self.current_attached_file_path)
            abs_upload = os.path.abspath(UPLOAD_FOLDER)

            if abs_curr.startswith(abs_upload):
                rel = os.path.relpath(abs_curr, BASE_DIR).replace("\\", "/")
                file_link = rel
            else:
                ext = os.path.splitext(abs_curr)[1].lower()
                base_name = os.path.splitext(os.path.basename(abs_curr))[0]
                safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                unique_fn = f"{safe_base}_{uuid.uuid4().hex[:8]}{ext}"
                dest_p = os.path.join(UPLOAD_FOLDER, unique_fn)
                try:
                    shutil.copy2(abs_curr, dest_p)
                    file_link = f"notices/{unique_fn}"
                except Exception as e:
                    messagebox.showerror("File Error", f"Could not copy attachment file:\n{e}")
                    return

        res = self.load_table()
        if not res:
            return
        soup, tbody = res

        if self.selected_notice_tuple:
            # UPDATE EXISTING NOTICE
            old_title, old_date = self.selected_notice_tuple
            rows = tbody.find_all("tr")
            updated = False

            for row in rows:
                t_cell = row.find("td", {"data-label": "Title"})
                d_cell = row.find("td", {"data-label": "Date"})
                if t_cell and d_cell:
                    if t_cell.text.strip() == old_title and d_cell.get("data-date", "").strip() == old_date:
                        # Clean up old file if replaced
                        d_link = row.find("a", class_="download-link")
                        if d_link:
                            old_f = d_link.get("href", "").strip()
                            if old_f and old_f != file_link:
                                old_full = os.path.join(BASE_DIR, old_f) if not os.path.isabs(old_f) else old_f
                                if os.path.exists(old_full):
                                    try:
                                        os.remove(old_full)
                                    except Exception:
                                        pass

                        new_row = self.create_row_tag(title, content, normalized_date, badge, badge_class, file_link)
                        row.replace_with(new_row)
                        updated = True
                        break

            if updated and self.save_table(soup):
                messagebox.showinfo("Success", f"✅ Notice '{title}' updated successfully!")
                self.clear_form()
                self.refresh_notices()
            else:
                messagebox.showerror("Error", "Could not locate the existing notice to update.")
        else:
            # CREATE NEW NOTICE (insert at top of tbody)
            new_row = self.create_row_tag(title, content, normalized_date, badge, badge_class, file_link)
            tbody.insert(0, new_row)

            if self.save_table(soup):
                messagebox.showinfo("Published", f"🎉 Notice '{title}' published successfully to notice.html!")
                self.clear_form()
                self.refresh_notices()
            else:
                messagebox.showerror("Error", "Failed to write notice to HTML file.")

    def delete_selected_notice(self):
        if not self.selected_notice_tuple:
            return
        t, d = self.selected_notice_tuple
        self.delete_notice_prompt(t, d)

    def delete_notice_prompt(self, title, date_bs):
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete this notice?\n\n📢 Title: {title}\n📅 Date: {date_bs}\n\nAny attached file in notices/ will also be deleted.",
            icon="warning"
        )
        if not confirm:
            return

        res = self.load_table()
        if not res:
            return
        soup, tbody = res

        deleted = False
        for row in tbody.find_all("tr"):
            t_cell = row.find("td", {"data-label": "Title"})
            d_cell = row.find("td", {"data-label": "Date"})
            if t_cell and d_cell:
                if t_cell.text.strip() == title and d_cell.get("data-date", "").strip() == date_bs:
                    # Remove attached file if present
                    d_link = row.find("a", class_="download-link")
                    if d_link:
                        f_path = d_link.get("href", "").strip()
                        if f_path:
                            full_p = os.path.join(BASE_DIR, f_path) if not os.path.isabs(f_path) else f_path
                            if os.path.exists(full_p):
                                try:
                                    os.remove(full_p)
                                except Exception as e:
                                    print(f"Error removing file: {e}")
                    row.decompose()
                    deleted = True
                    break

        if deleted and self.save_table(soup):
            messagebox.showinfo("Deleted", f"Notice '{title}' deleted successfully.")
            self.clear_form()
            self.refresh_notices()
        else:
            messagebox.showerror("Error", "Could not delete notice.")

    # ── File Attachment & Visual Preview Card ────────────────────────────────
    def browse_file(self):
        filetypes = [
            ("All Supported Files", "*.pdf;*.jpg;*.jpeg;*.png;*.webp;*.doc;*.docx;*.xls;*.xlsx;*.txt;*.heic"),
            ("PDF Documents (*.pdf)", "*.pdf"),
            ("Images (*.jpg, *.png, *.webp, etc.)", "*.jpg;*.jpeg;*.png;*.webp;*.heic"),
            ("Office Documents (*.doc, *.docx, *.xls)", "*.doc;*.docx;*.xls;*.xlsx"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Attachment File", filetypes=filetypes)
        if chosen:
            self.current_attached_file_path = chosen
            self.update_file_preview(chosen)

    def remove_attached_file(self):
        self.current_attached_file_path = None
        self.update_file_preview(None)

    def open_current_attached_file(self):
        if self.current_attached_file_path and os.path.exists(self.current_attached_file_path):
            self.open_file_in_system(self.current_attached_file_path)
        else:
            messagebox.showwarning("File Missing", "The attached file cannot be found on disk.")

    def open_notice_file_by_name(self, title, date_bs):
        for n in self.notices:
            if n["title"] == title and n["date"] == date_bs:
                if n["has_file"] and n["file_link"]:
                    full_p = os.path.join(BASE_DIR, n["file_link"]) if not os.path.isabs(n["file_link"]) else n["file_link"]
                    if os.path.exists(full_p):
                        self.open_file_in_system(full_p)
                    else:
                        messagebox.showwarning("File Missing", f"File '{n['file_name']}' does not exist in notices/ folder.")
                return

    def open_file_in_system(self, file_path):
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", file_path])
            else:
                subprocess.call(["xdg-open", file_path])
        except Exception as e:
            try:
                webbrowser.open(f"file://{file_path}")
            except Exception:
                messagebox.showerror("Open Error", f"Could not open file:\n{e}")

    def open_notices_folder(self):
        try:
            if platform.system() == "Windows":
                os.startfile(UPLOAD_FOLDER)
            elif platform.system() == "Darwin":
                subprocess.call(["open", UPLOAD_FOLDER])
            else:
                subprocess.call(["xdg-open", UPLOAD_FOLDER])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def update_file_preview(self, file_path):
        if not file_path or not os.path.exists(file_path):
            self.lbl_preview_media.config(
                image="",
                text="📁 No Attachment Preview\nAttach an image or document to see preview here",
                font=("Segoe UI", 9),
                fg=self.c_muted,
                height=6
            )
            self.lbl_file_meta.config(text="No file attached", fg=self.c_muted)
            self.btn_open_file.config(state="disabled")
            self.btn_remove_file.config(state="disabled")
            self.preview_thumbnail_photo = None
            return

        self.btn_open_file.config(state="normal")
        self.btn_remove_file.config(state="normal")

        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_name)[1].lower()
        sz = os.path.getsize(file_path)
        sz_str = f"{sz / (1024*1024):.2f} MB" if sz > 1024*1024 else f"{sz / 1024:.1f} KB"

        self.lbl_file_meta.config(
            text=f"📎 {file_name}  •  {sz_str}  •  {ext.upper()}",
            fg="#58A6FF"
        )

        # Image thumbnail preview
        if ext in IMAGE_EXTENSIONS:
            try:
                img = Image.open(file_path)
                img.thumbnail((320, 180), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.ANTIALIAS)
                self.preview_thumbnail_photo = ImageTk.PhotoImage(img)
                self.lbl_preview_media.config(image=self.preview_thumbnail_photo, text="", height=0)
                return
            except Exception as e:
                print(f"Thumbnail error: {e}")

        # PDF or Document icon preview
        doc_icon = "📕 PDF Document" if ext == ".pdf" else "📄 Office Document" if ext in {".doc", ".docx", ".xls", ".xlsx"} else "📎 Attached File"
        self.lbl_preview_media.config(
            image="",
            text=f"{doc_icon}\n{file_name}\n({sz_str})",
            font=("Segoe UI", 10, "bold"),
            fg="#FFFFFF",
            height=6
        )

    # ── Mobile QR Upload Integration ─────────────────────────────────────────
    def open_mobile_upload_dialog(self):
        self.start_mobile_server_if_needed()

        local_ip = get_local_ip()
        upload_url = f"http://{local_ip}:{MOBILE_UPLOAD_PORT}"

        dlg = tk.Toplevel(self.root)
        dlg.title("📱 Mobile QR Notice Uploader")
        dlg.geometry("480x580")
        dlg.minsize(440, 520)
        dlg.configure(bg=self.c_panel)
        dlg.transient(self.root)
        dlg.grab_set()

        header = tk.Frame(dlg, bg=self.c_panel, padx=20, pady=16)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="📱 Mobile QR Notice Uploader",
            font=("Segoe UI", 14, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Scan with your smartphone camera on the same Wi-Fi network to upload photos of notices, documents, or PDFs directly to this computer.",
            font=("Segoe UI", 9),
            fg=self.c_muted,
            bg=self.c_panel,
            wraplength=420,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        # QR Code Display
        qr_card = tk.Frame(dlg, bg=self.c_card, padx=20, pady=20, relief="flat", highlightthickness=1, highlightbackground=self.c_border)
        qr_card.pack(padx=20, pady=10)

        lbl_qr = tk.Label(qr_card, bg="#FFFFFF", padx=10, pady=10)
        lbl_qr.pack()

        if HAS_QRCODE:
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(upload_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            self.qr_photo = ImageTk.PhotoImage(qr_img)
            lbl_qr.config(image=self.qr_photo)
        else:
            lbl_qr.config(
                text=f"QR Code library not installed.\nOpen this link on your phone:\n{upload_url}",
                fg="#000000",
                bg="#FFFFFF",
                font=("Segoe UI", 10)
            )

        # URL display & copy button
        url_box = tk.Frame(dlg, bg=self.c_panel, padx=20, pady=6)
        url_box.pack(fill=tk.X)

        ent_url = tk.Entry(url_box, font=("Segoe UI", 10, "bold"), bg=self.c_card, fg="#58A6FF", justify="center", relief="flat")
        ent_url.insert(0, upload_url)
        ent_url.pack(fill=tk.X, ipady=6, pady=(0, 6))

        btn_row = tk.Frame(dlg, bg=self.c_panel, padx=20, pady=10)
        btn_row.pack(fill=tk.X)

        def _copy_url():
            self.root.clipboard_clear()
            self.root.clipboard_append(upload_url)
            messagebox.showinfo("Copied", f"Link copied to clipboard:\n{upload_url}", parent=dlg)

        def _open_browser():
            webbrowser.open(upload_url)

        tk.Button(btn_row, text="📋 Copy Link", bg=self.c_card, fg=self.c_text, font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=6, cursor="hand2", command=_copy_url).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        tk.Button(btn_row, text="🌐 Test in Browser", bg=self.c_primary, fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=6, cursor="hand2", command=_open_browser).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

    def start_mobile_server_if_needed(self):
        if self.mobile_running:
            return
        try:
            MobileNoticeUploadHandler.app_ref = self
            server_address = ("0.0.0.0", MOBILE_UPLOAD_PORT)

            class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
                daemon_threads = True

            self.mobile_httpd = ThreadedHTTPServer(server_address, MobileNoticeUploadHandler)
            self.mobile_thread = threading.Thread(target=self.mobile_httpd.serve_forever, daemon=True)
            self.mobile_thread.start()
            self.mobile_running = True
            print(f"Mobile Notice Upload server started on port {MOBILE_UPLOAD_PORT}")
        except Exception as e:
            print(f"Could not start mobile server: {e}")

    def on_mobile_upload_success(self, uploaded_names):
        if not uploaded_names:
            return
        last_file = uploaded_names[-1]
        full_p = os.path.join(UPLOAD_FOLDER, last_file)
        self.current_attached_file_path = full_p
        self.update_file_preview(full_p)
        self.lbl_status.config(text=f"📱 Received {len(uploaded_names)} file(s) from phone! Auto-attached '{last_file}'.")
        messagebox.showinfo(
            "Phone Upload Received",
            f"📱 Received {len(uploaded_names)} file(s) from mobile!\n\nAuto-attached to current notice:\n📎 {last_file}"
        )

    # ── Live Website Preview Server ──────────────────────────────────────────
    def toggle_preview_server(self):
        if not self.preview_running:
            self.start_preview_server()
        target_url = f"http://localhost:{PREVIEW_PORT}/notice.html"
        webbrowser.open(target_url)
        self.lbl_status.config(text=f"🌐 Live Website Preview opened at {target_url}")

    def start_preview_server(self):
        if self.preview_running:
            return
        try:
            class QuietHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=BASE_DIR, **kwargs)

                def log_message(self, format, *args):
                    pass

            class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
                daemon_threads = True

            self.preview_httpd = ThreadedHTTPServer(("127.0.0.1", PREVIEW_PORT), QuietHandler)
            self.preview_thread = threading.Thread(target=self.preview_httpd.serve_forever, daemon=True)
            self.preview_thread.start()
            self.preview_running = True
            self.btn_preview_srv.config(
                text="🌐 Live Preview: ACTIVE (Click to Open)",
                bg=self.c_success,
                activebackground="#059669"
            )
            print(f"Notice Portal Preview Server started on http://localhost:{PREVIEW_PORT}/notice.html")
        except Exception as e:
            print(f"Preview server notice error: {e}")

    def on_closing(self):
        """Cleanly shutdown servers and close window."""
        try:
            if self.preview_httpd:
                self.preview_httpd.shutdown()
                self.preview_httpd.server_close()
        except Exception:
            pass
        try:
            if self.mobile_httpd:
                self.mobile_httpd.shutdown()
                self.mobile_httpd.server_close()
        except Exception:
            pass
        self.root.destroy()


# ── Application Entry Point ──────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = NoticeAdminApp(root)
    root.mainloop()