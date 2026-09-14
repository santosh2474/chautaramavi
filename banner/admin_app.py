import os
import sys
import io
import re
import json
import shutil
import socket
import threading
import socketserver
import http.server
import urllib.parse
import webbrowser
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image, ImageTk

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

BANNER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BANNER_DIR)
MEDIA_DIR = os.path.join(BANNER_DIR, 'banner_img')
CONFIG_JS = os.path.join(BANNER_DIR, 'banner-config.js')
BANNER_META_JSON = os.path.join(BANNER_DIR, 'banner_meta.json')
INDEX_HTML = os.path.join(PROJECT_ROOT, 'index.html')

PREVIEW_PORT = 8080
MOBILE_UPLOAD_PORT = 8766

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.heic', '.heif'}
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.ogg', '.mov'}
DOC_EXTENSIONS = {'.pdf'}
ALL_ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | DOC_EXTENSIONS


def get_local_ip():
    """Detect local LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in DOC_EXTENSIONS:
        return "pdf"
    return "other"


def convert_heic_to_jpeg(heic_data):
    """Convert HEIC image data from iPhone/Apple devices to JPEG bytes."""
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


class MobileUploadHandler(http.server.BaseHTTPRequestHandler):
    """Mobile web interface for wireless banner media uploads."""

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

    def send_html(self, html, code=200):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "" or path == "/upload":
            self.serve_upload_page()
        elif path == "/api/status":
            self.send_json({"status": "ok", "app": "BannerAdminApp"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path != "/api/upload":
            self.send_response(404)
            self.end_headers()
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type or "boundary=" not in content_type:
            self.send_json({"error": "Invalid Content-Type"}, 400)
            return

        boundary = content_type.split("boundary=")[1].strip()
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)
            parts = parse_multipart(raw_body, boundary)
        except Exception as e:
            self.send_json({"error": f"Failed to read upload: {e}"}, 400)
            return

        uploaded_files = []
        errors = []

        if not os.path.exists(MEDIA_DIR):
            os.makedirs(MEDIA_DIR, exist_ok=True)

        for name, filename, content in parts:
            if not filename or not content:
                continue

            raw_name = os.path.basename(filename)
            ext = os.path.splitext(raw_name)[1].lower()

            if ext not in ALL_ALLOWED_EXTENSIONS:
                errors.append(f"Unsupported format: {raw_name}")
                continue

            if ext in {".heic", ".heif"}:
                conv = convert_heic_to_jpeg(content)
                if conv:
                    content = conv
                    raw_name = os.path.splitext(raw_name)[0] + ".jpg"
                    ext = ".jpg"
                else:
                    errors.append(f"Could not convert {raw_name} (HEIC unsupported)")
                    continue

            safe_name = re.sub(r"[^\w\-_.]", "_", raw_name)
            target_path = os.path.join(MEDIA_DIR, safe_name)
            counter = 1
            base_n, ext_n = os.path.splitext(safe_name)
            while os.path.exists(target_path):
                safe_name = f"{base_n}_{counter}{ext_n}"
                target_path = os.path.join(MEDIA_DIR, safe_name)
                counter += 1

            try:
                with open(target_path, "wb") as f:
                    f.write(content)
                uploaded_files.append(safe_name)
            except Exception as e:
                errors.append(f"Write error for {raw_name}: {e}")

        if uploaded_files and self.app_ref:
            try:
                self.app_ref.root.after(0, self.app_ref.sync_and_refresh)
            except Exception:
                pass

        self.send_json({
            "success": True,
            "uploaded": uploaded_files,
            "errors": errors,
            "count": len(uploaded_files)
        })

    def serve_upload_page(self):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Mobile Banner Upload</title>
<style>
  :root {
    --primary: #2878EB;
    --primary-dark: #1b5bb5;
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --heading: #58a6ff;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text); padding: 16px; min-height: 100vh;
  }
  .header { text-align: center; margin-bottom: 20px; }
  .header h1 { margin: 6px 0 2px 0; color: #fff; font-size: 1.35rem; }
  .header p { margin: 0; font-size: 0.85rem; color: #8b949e; }
  .badge { display: inline-block; background: var(--primary); color: #fff; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 700; margin-bottom: 6px; }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }
  .card-title { font-size: 0.95rem; font-weight: 700; color: #fff; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
  .source-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
  .btn {
    background: rgba(255,255,255,0.06); border: 1px solid var(--border); color: #fff;
    padding: 12px 10px; border-radius: 10px; font-weight: 600; font-size: 0.88rem;
    cursor: pointer; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 4px;
    transition: all 0.2s ease;
  }
  .btn:active { transform: scale(0.97); background: rgba(255,255,255,0.12); }
  .btn-primary {
    background: var(--primary); border-color: var(--primary); color: #fff;
    width: 100%; padding: 14px; font-size: 1rem; border-radius: 10px; margin-top: 10px;
  }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .drop-zone {
    border: 2px dashed #388bfd; border-radius: 10px; padding: 20px 10px;
    text-align: center; background: rgba(56,139,253,0.04); cursor: pointer;
  }
  .preview-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(75px, 1fr)); gap: 8px; margin-top: 12px;
  }
  .preview-item {
    position: relative; aspect-ratio: 1; border-radius: 8px; overflow: hidden; background: #000; border: 1px solid #30363d;
  }
  .preview-item img, .preview-item video { width: 100%; height: 100%; object-fit: cover; }
  .preview-item .doc-tag { display: flex; align-items: center; justify-content: center; height: 100%; font-size: 0.75rem; color: #ff7b72; font-weight: bold; }
  .progress-wrap { height: 6px; background: #21262d; border-radius: 3px; overflow: hidden; margin-top: 14px; display: none; }
  .progress-bar { height: 100%; width: 0%; background: #2ea043; transition: width 0.2s; }
  .status { margin-top: 14px; padding: 12px; border-radius: 8px; font-size: 0.85rem; display: none; }
  .status.ok { background: rgba(46,160,67,0.15); border: 1px solid #2ea043; color: #3fb950; }
  .status.err { background: rgba(248,81,73,0.15); border: 1px solid #f85149; color: #ff7b72; }
</style>
</head>
<body>
  <div class="header">
    <span class="badge">Shree Chautara Secondary School</span>
    <h1>📢 Banner Media Upload</h1>
    <p>Upload Images, Videos, or PDFs directly to Website Banners</p>
  </div>

  <div class="card">
    <div class="card-title">📁 Choose Files to Upload</div>
    <div class="source-btns">
      <button class="btn" onclick="document.getElementById('fileInputGallery').click()">
        <span>🖼️ Photo / Video</span>
        <small style="color:#8b949e">Choose from Library</small>
      </button>
      <button class="btn" onclick="document.getElementById('fileInputDoc').click()">
        <span>📄 PDF Notice</span>
        <small style="color:#8b949e">Files & Docs</small>
      </button>
    </div>

    <input type="file" id="fileInputGallery" accept="image/*,video/*" multiple style="display:none">
    <input type="file" id="fileInputDoc" accept=".pdf" multiple style="display:none">

    <div class="drop-zone" onclick="document.getElementById('fileInputGallery').click()">
      <div style="font-size: 1.5rem; margin-bottom: 4px;">⬆️</div>
      <div style="font-size: 0.88rem; font-weight: 600;">Tap to select or take photos/videos</div>
      <div style="font-size: 0.75rem; color: #8b949e; margin-top: 4px;">Supports JPG, PNG, WEBP, MP4, WEBM, PDF</div>
    </div>

    <div class="preview-grid" id="previewGrid"></div>
  </div>

  <button class="btn btn-primary" id="uploadBtn" disabled onclick="uploadFiles()">
    📤 Upload to School Banners
  </button>

  <div class="progress-wrap" id="progressWrap">
    <div class="progress-bar" id="progressBar"></div>
  </div>

  <div class="status" id="statusBox"></div>

  <script>
    let filesList = [];
    const previewGrid = document.getElementById('previewGrid');
    const uploadBtn = document.getElementById('uploadBtn');
    const progressWrap = document.getElementById('progressWrap');
    const progressBar = document.getElementById('progressBar');
    const statusBox = document.getElementById('statusBox');

    function handleFiles(newFiles) {
      for (const f of newFiles) {
        if (!filesList.some(x => x.name === f.name && x.size === f.size)) {
          filesList.push(f);
        }
      }
      renderPreviews();
    }

    document.getElementById('fileInputGallery').addEventListener('change', e => handleFiles(e.target.files));
    document.getElementById('fileInputDoc').addEventListener('change', e => handleFiles(e.target.files));

    function renderPreviews() {
      previewGrid.innerHTML = '';
      filesList.forEach((file, idx) => {
        const item = document.createElement('div');
        item.className = 'preview-item';

        if (file.type.startsWith('image/')) {
          const img = document.createElement('img');
          img.src = URL.createObjectURL(file);
          item.appendChild(img);
        } else if (file.type.startsWith('video/')) {
          const vid = document.createElement('video');
          vid.src = URL.createObjectURL(file);
          item.appendChild(vid);
        } else {
          item.innerHTML = '<div class="doc-tag">PDF</div>';
        }

        previewGrid.appendChild(item);
      });
      uploadBtn.disabled = filesList.length === 0;
      uploadBtn.textContent = filesList.length > 0
        ? `📤 Upload ${filesList.length} Item${filesList.length > 1 ? 's' : ''}`
        : '📤 Upload to School Banners';
    }

    async function uploadFiles() {
      if (filesList.length === 0) return;
      uploadBtn.disabled = true;
      progressWrap.style.display = 'block';
      progressBar.style.width = '20%';
      statusBox.style.display = 'none';

      const formData = new FormData();
      filesList.forEach(file => formData.append('files', file));

      try {
        progressBar.style.width = '60%';
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        progressBar.style.width = '100%';
        const data = await res.json();

        if (data.success) {
          statusBox.className = 'status ok';
          statusBox.innerHTML = `✅ Successfully uploaded <strong>${data.uploaded.length}</strong> media file(s) to Website Banners!`;
          statusBox.style.display = 'block';
          filesList = [];
          renderPreviews();
        } else {
          statusBox.className = 'status err';
          statusBox.textContent = '❌ Upload failed: ' + (data.error || 'Unknown error');
          statusBox.style.display = 'block';
        }
      } catch (err) {
        statusBox.className = 'status err';
        statusBox.textContent = '❌ Network error: ' + err.message;
        statusBox.style.display = 'block';
      } finally {
        setTimeout(() => { progressWrap.style.display = 'none'; progressBar.style.width = '0%'; }, 1500);
      }
    }
  </script>
</body>
</html>"""
        self.send_html(html)


class BannerAdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shree Chautara Mavi - Banner & Popup Media Manager")
        self.root.geometry("1180x760")
        self.root.minsize(920, 560)

        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.preview_httpd = None
        self.preview_thread = None
        self.preview_running = False

        self.mobile_httpd = None
        self.mobile_thread = None
        self.mobile_running = False
        self.qr_photo = None
        self.current_preview_photo = None

        self.media_items = []
        self.media_titles = {}       # rel_path -> title string
        self.current_selected_rel_path = None
        self.var_banner_enabled = tk.BooleanVar(value=True)
        self.settings = {
            "enabled": True,
            "autoOpen": True,
            "slideshow": False,
            "slideshowInterval": 5000,
            "rememberClosed": False,
            "autoDetectPhp": True
        }

        self.init_directories()
        self.setup_styles()
        self.create_widgets()
        self.var_banner_enabled.trace_add("write", lambda *args: self.update_banner_toggle_ui())
        self.load_settings()
        self.refresh_all()

    def init_directories(self):
        if not os.path.exists(MEDIA_DIR):
            os.makedirs(MEDIA_DIR, exist_ok=True)

    def setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.c_bg = "#0F121C"
        self.c_panel = "#181D2D"
        self.c_card = "#20273C"
        self.c_border = "#2E3852"
        self.c_text = "#E2E8F0"
        self.c_muted = "#94A3B8"
        self.c_primary = "#2878EB"
        self.c_primary_hover = "#1C62C9"
        self.c_success = "#10B981"
        self.c_danger = "#EF4444"

        self.root.configure(bg=self.c_bg)

        self.style.configure(
            "Banner.Treeview",
            background=self.c_card,
            foreground=self.c_text,
            fieldbackground=self.c_card,
            font=("Segoe UI", 10),
            rowheight=32,
            borderwidth=0
        )
        self.style.configure(
            "Banner.Treeview.Heading",
            background=self.c_panel,
            foreground="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=8
        )
        self.style.map(
            "Banner.Treeview",
            background=[("selected", self.c_primary)],
            foreground=[("selected", "#FFFFFF")]
        )

    def create_widgets(self):
        # 1. Top Header Toolbar
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
            text="Banner & Popup Media Management Suite (Images, Videos, PDFs)",
            font=("Segoe UI", 9),
            fg=self.c_muted,
            bg=self.c_panel
        )
        lbl_sub.pack(anchor="w")

        btn_box = tk.Frame(self.header_frame, bg=self.c_panel)
        btn_box.pack(side=tk.RIGHT, fill=tk.Y)

        self.btn_master_toggle = tk.Button(
            btn_box,
            text="🟢 Banner: ENABLED",
            bg=self.c_success,
            fg="#FFFFFF",
            activebackground="#059669",
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.toggle_banner_feature
        )
        self.btn_master_toggle.pack(side=tk.LEFT, padx=6)

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

        # 2. Main Body Split Area
        self.paned = tk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL,
            bg=self.c_border,
            sashwidth=5,
            relief="flat"
        )
        self.paned.grid(row=1, column=0, sticky="nsew")

        self.left_frame = tk.Frame(self.paned, bg=self.c_bg, padx=16, pady=16)
        self.paned.add(self.left_frame, minsize=460, width=640)

        self.right_frame = tk.Frame(self.paned, bg=self.c_panel, padx=16, pady=16)
        self.paned.add(self.right_frame, minsize=420)

        self.build_left_panel()
        self.build_right_panel()

        # 3. Status Bar
        self.status_bar = tk.Frame(self.root, bg=self.c_panel, height=26, padx=16)
        self.status_bar.grid(row=2, column=0, sticky="ew")

        self.lbl_status = tk.Label(
            self.status_bar,
            text="Ready",
            font=("Segoe UI", 9),
            fg=self.c_muted,
            bg=self.c_panel
        )
        self.lbl_status.pack(side=tk.LEFT, pady=3)

        self.lbl_count = tk.Label(
            self.status_bar,
            text="0 Banner Items",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        )
        self.lbl_count.pack(side=tk.RIGHT, pady=3)

    def build_left_panel(self):
        top_bar = tk.Frame(self.left_frame, bg=self.c_bg)
        top_bar.pack(fill=tk.X, pady=(0, 10))

        lbl_section = tk.Label(
            top_bar,
            text="📁 Current Banner Media Sequence",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg=self.c_bg
        )
        lbl_section.pack(side=tk.LEFT)

        btn_add = tk.Button(
            top_bar,
            text="➕ Add Media Files",
            bg=self.c_success,
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.add_media_files
        )
        btn_add.pack(side=tk.RIGHT, padx=4)

        btn_refresh = tk.Button(
            top_bar,
            text="🔄 Refresh",
            bg=self.c_card,
            fg=self.c_text,
            font=("Segoe UI", 9),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.refresh_all
        )
        btn_refresh.pack(side=tk.RIGHT, padx=4)

        tree_container = tk.Frame(self.left_frame, bg=self.c_card)
        tree_container.pack(fill=tk.BOTH, expand=True)

        columns = ("pos", "name", "type", "size", "modified")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Banner.Treeview",
            selectmode="browse"
        )

        self.tree.heading("pos", text="#")
        self.tree.heading("name", text="File Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="File Size")
        self.tree.heading("modified", text="Date Modified")

        self.tree.column("pos", width=45, anchor="center")
        self.tree.column("name", width=260, anchor="w")
        self.tree.column("type", width=90, anchor="center")
        self.tree.column("size", width=90, anchor="center")
        self.tree.column("modified", width=140, anchor="center")

        scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_item_select)
        self.tree.bind("<Double-1>", self.on_double_click_item)

        bottom_bar = tk.Frame(self.left_frame, bg=self.c_bg)
        bottom_bar.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            bottom_bar,
            text="⬆️ Move Up",
            bg=self.c_card,
            fg=self.c_text,
            font=("Segoe UI", 9),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.move_up
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            bottom_bar,
            text="⬇️ Move Down",
            bg=self.c_card,
            fg=self.c_text,
            font=("Segoe UI", 9),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.move_down
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            bottom_bar,
            text="✏️ Rename",
            bg=self.c_card,
            fg=self.c_text,
            font=("Segoe UI", 9),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.rename_selected
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            bottom_bar,
            text="🗑️ Delete",
            bg="#991B1B",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.delete_selected
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            bottom_bar,
            text="📂 Open banner_img Folder",
            bg=self.c_card,
            fg=self.c_text,
            font=("Segoe UI", 9),
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.open_media_folder
        ).pack(side=tk.RIGHT)

    def build_right_panel(self):
        # Create a scrollable container for the right panel so options never get cut off
        canvas = tk.Canvas(self.right_frame, bg=self.c_panel, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(self.right_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.c_panel)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_frame_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def on_canvas_configure(event):
            canvas.itemconfig(canvas_frame_id, width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel support on scrollable frame
        def _on_mousewheel(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 1. Preview Box
        lbl_prev_title = tk.Label(
            scrollable_frame,
            text="👁️ Media Preview & Details",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        )
        lbl_prev_title.pack(anchor="w", pady=(0, 6))

        self.preview_card = tk.Frame(
            scrollable_frame,
            bg=self.c_card,
            height=210,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        self.preview_card.pack(fill=tk.X)
        self.preview_card.pack_propagate(False)

        self.lbl_preview_canvas = tk.Label(
            self.preview_card,
            text="Select an item from the list to preview",
            font=("Segoe UI", 9),
            fg=self.c_muted,
            bg=self.c_card
        )
        self.lbl_preview_canvas.pack(fill=tk.BOTH, expand=True)

        self.lbl_preview_info = tk.Label(
            scrollable_frame,
            text="No item selected",
            font=("Segoe UI", 8),
            fg=self.c_muted,
            bg=self.c_panel,
            anchor="w",
            wraplength=420,
            justify="left"
        )
        self.lbl_preview_info.pack(fill=tk.X, pady=(4, 8))

        # ── Caption / Title Card ──────────────────────────────────────────────
        caption_header = tk.Frame(scrollable_frame, bg=self.c_panel)
        caption_header.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            caption_header,
            text="✏️ Media Caption / Title",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        ).pack(side=tk.LEFT)

        caption_card = tk.Frame(
            scrollable_frame,
            bg=self.c_card,
            padx=14,
            pady=12,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        caption_card.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            caption_card,
            text="Displayed caption for the currently selected media item:",
            font=("Segoe UI", 8),
            fg=self.c_muted,
            bg=self.c_card,
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 6))

        caption_entry_wrap = tk.Frame(
            caption_card,
            bg=self.c_border,
            padx=1,
            pady=1,
        )
        caption_entry_wrap.pack(fill=tk.X)

        self.ent_caption = tk.Entry(
            caption_entry_wrap,
            font=("Segoe UI", 10),
            bg=self.c_panel,
            fg="#FFFFFF",
            insertbackground="#58A6FF",
            relief="flat",
            highlightthickness=0,
        )
        self.ent_caption.pack(fill=tk.X, ipady=7, padx=1, pady=1)
        self.ent_caption.insert(0, "Select a media item to edit its caption")
        self.ent_caption.config(fg=self.c_muted)
        self.ent_caption.config(state="disabled")

        def _on_caption_focus_in(event):
            if self.ent_caption.cget("fg") == self.c_muted:
                self.ent_caption.delete(0, tk.END)
                self.ent_caption.config(fg="#FFFFFF")

        def _on_caption_key_release(event):
            if self.current_selected_rel_path:
                val = self.ent_caption.get().strip()
                self.media_titles[self.current_selected_rel_path] = val

        self.ent_caption.bind("<FocusIn>", _on_caption_focus_in)
        self.ent_caption.bind("<KeyRelease>", _on_caption_key_release)

        tk.Label(
            caption_card,
            text="💡 Tip: Caption is shown at the footer of the media viewer for visitors.",
            font=("Segoe UI", 7, "italic"),
            fg="#58A6FF",
            bg=self.c_card,
            anchor="w"
        ).pack(fill=tk.X, pady=(6, 0))

        # ── Master Enable / Disable Feature Card ─────────────────────────────
        lbl_master_title = tk.Label(
            scrollable_frame,
            text="🛡️ Master Banner Feature Switch",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        )
        lbl_master_title.pack(anchor="w", pady=(4, 6))

        self.card_master = tk.Frame(
            scrollable_frame,
            bg=self.c_card,
            padx=14,
            pady=12,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#10B981"
        )
        self.card_master.pack(fill=tk.X, pady=(0, 10))

        master_top_row = tk.Frame(self.card_master, bg=self.c_card)
        master_top_row.pack(fill=tk.X)

        self.lbl_master_status = tk.Label(
            master_top_row,
            text="🟢 Banner Viewer: ACTIVE",
            font=("Segoe UI", 10, "bold"),
            fg="#10B981",
            bg=self.c_card
        )
        self.lbl_master_status.pack(side=tk.LEFT)

        self.btn_card_toggle = tk.Button(
            master_top_row,
            text="🔴 Turn OFF Banner",
            bg="#EF4444",
            fg="#FFFFFF",
            activebackground="#DC2626",
            activeforeground="#FFFFFF",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.toggle_banner_feature
        )
        self.btn_card_toggle.pack(side=tk.RIGHT)

        self.lbl_master_desc = tk.Label(
            self.card_master,
            text="When enabled, the popup and floating notice icon appear on the website. Turn OFF to completely disable and hide the entire banner viewer from visitors.",
            font=("Segoe UI", 8),
            fg=self.c_muted,
            bg=self.c_card,
            justify="left",
            anchor="w",
            wraplength=420
        )
        self.lbl_master_desc.pack(fill=tk.X, pady=(6, 0))

        # 2. Banner Behavior Settings Card Header
        lbl_cfg_title = tk.Label(
            scrollable_frame,
            text="⚙️ Banner Behavior Settings",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        )
        lbl_cfg_title.pack(anchor="w", pady=(4, 6))

        cfg_card = tk.Frame(
            scrollable_frame,
            bg=self.c_card,
            padx=14,
            pady=12,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        cfg_card.pack(fill=tk.X)

        def create_option_row(parent, title_text, desc_text, var_obj):
            row = tk.Frame(parent, bg=self.c_card, pady=6)
            row.pack(fill=tk.X)

            chk = tk.Checkbutton(
                row,
                text=title_text,
                variable=var_obj,
                bg=self.c_card,
                fg="#FFFFFF",
                activebackground=self.c_card,
                activeforeground="#FFFFFF",
                selectcolor=self.c_panel,
                font=("Segoe UI", 9, "bold"),
                anchor="w"
            )
            chk.pack(fill=tk.X)

            desc = tk.Label(
                row,
                text=desc_text,
                font=("Segoe UI", 8),
                fg=self.c_muted,
                bg=self.c_card,
                justify="left",
                anchor="w",
                padx=24
            )
            desc.pack(fill=tk.X)
            return chk

        # Option 0: Master Feature Enable
        self.chk_master = create_option_row(
            cfg_card,
            "0. Master Feature Switch (enabled)",
            "Enable or disable the entire banner media viewer and floating notice icon on the website.",
            self.var_banner_enabled
        )

        # Option 1: Auto Open
        self.var_auto_open = tk.BooleanVar(value=True)
        self.chk_auto_open = create_option_row(
            cfg_card,
            "1. Auto Open Popup (autoOpen)",
            "Opens the banner popup automatically when visitors land on index.html.",
            self.var_auto_open
        )

        # Option 2: Slideshow Auto-advance
        self.var_slideshow = tk.BooleanVar(value=False)
        self.chk_slideshow = create_option_row(
            cfg_card,
            "2. Auto Slideshow (slideshow)",
            "Automatically transitions from slide to slide without clicking.",
            self.var_slideshow
        )

        # Option 3: Slideshow Interval
        interval_box = tk.Frame(cfg_card, bg=self.c_card, pady=6)
        interval_box.pack(fill=tk.X)

        int_top = tk.Frame(interval_box, bg=self.c_card)
        int_top.pack(fill=tk.X)

        tk.Label(
            int_top,
            text="3. Slideshow Interval (seconds):",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg=self.c_card
        ).pack(side=tk.LEFT)

        self.ent_interval = tk.Entry(
            int_top,
            width=7,
            font=("Segoe UI", 9, "bold"),
            bg=self.c_panel,
            fg="#58A6FF",
            insertbackground="#FFFFFF",
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border
        )
        self.ent_interval.insert(0, "5")
        self.ent_interval.pack(side=tk.LEFT, padx=10)

        tk.Label(
            interval_box,
            text="How many seconds each banner image or notice is displayed.",
            font=("Segoe UI", 8),
            fg=self.c_muted,
            bg=self.c_card,
            anchor="w",
            padx=4
        ).pack(fill=tk.X, pady=(2, 0))

        # Option 4: Remember Closed
        self.var_remember_closed = tk.BooleanVar(value=False)
        self.chk_remember = create_option_row(
            cfg_card,
            "4. Remember Dismissal (rememberClosed)",
            "Hides the popup for the current browser session after a visitor clicks Close.",
            self.var_remember_closed
        )

        # Option 5: Auto-detect PHP
        self.var_auto_php = tk.BooleanVar(value=True)
        self.chk_php = create_option_row(
            cfg_card,
            "5. Server-side PHP Scanner (autoDetectPhp)",
            "Automatically detects new files in banner/banner_img/ on your live server.",
            self.var_auto_php
        )

        # Save Button
        btn_save_cfg = tk.Button(
            scrollable_frame,
            text="💾 Save Settings to banner-config.js",
            bg=self.c_primary,
            fg="#FFFFFF",
            activebackground=self.c_primary_hover,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=10,
            cursor="hand2",
            command=self.save_settings
        )
        btn_save_cfg.pack(fill=tk.X, pady=(12, 16))

    def update_banner_toggle_ui(self):
        is_enabled = self.var_banner_enabled.get()
        if is_enabled:
            if hasattr(self, 'btn_master_toggle'):
                self.btn_master_toggle.config(
                    text="🟢 Banner: ENABLED",
                    bg=self.c_success,
                    activebackground="#059669"
                )
            if hasattr(self, 'lbl_master_status'):
                self.lbl_master_status.config(
                    text="🟢 Banner Viewer: ACTIVE",
                    fg="#10B981"
                )
            if hasattr(self, 'btn_card_toggle'):
                self.btn_card_toggle.config(
                    text="🔴 Turn OFF Banner",
                    bg="#EF4444",
                    activebackground="#DC2626"
                )
            if hasattr(self, 'card_master'):
                self.card_master.config(highlightbackground="#10B981")
        else:
            if hasattr(self, 'btn_master_toggle'):
                self.btn_master_toggle.config(
                    text="🔴 Banner: DISABLED",
                    bg=self.c_danger,
                    activebackground="#DC2626"
                )
            if hasattr(self, 'lbl_master_status'):
                self.lbl_master_status.config(
                    text="🔴 Banner Viewer: DISABLED",
                    fg="#EF4444"
                )
            if hasattr(self, 'btn_card_toggle'):
                self.btn_card_toggle.config(
                    text="🟢 Turn ON Banner",
                    bg="#10B981",
                    activebackground="#059669"
                )
            if hasattr(self, 'card_master'):
                self.card_master.config(highlightbackground="#EF4444")

    def toggle_banner_feature(self):
        new_state = not self.var_banner_enabled.get()
        self.var_banner_enabled.set(new_state)
        self.update_banner_toggle_ui()
        self.save_settings(silent=True)
        if new_state:
            self.lbl_status.config(text="✅ Banner Media Viewer ENABLED on website.")
            messagebox.showinfo(
                "Banner Feature Enabled",
                "✅ Banner Media Viewer is now ENABLED.\n\nVisitors on www.chautaramavi.edu.np will see the announcement popup and floating notice icon."
            )
        else:
            self.lbl_status.config(text="⛔ Banner Media Viewer DISABLED on website.")
            messagebox.showinfo(
                "Banner Feature Disabled",
                "⛔ Banner Media Viewer is now DISABLED.\n\nThe entire banner viewer, popup modal, and floating notice icon are now completely hidden from website visitors."
            )

    def load_settings(self):
        if not os.path.exists(CONFIG_JS):
            return

        try:
            with open(CONFIG_JS, "r", encoding="utf-8") as f:
                content = f.read()

            m_enabled = re.search(r"enabled\s*:\s*(true|false)", content)
            if m_enabled:
                self.var_banner_enabled.set(m_enabled.group(1) == "true")
            else:
                self.var_banner_enabled.set(True)

            m_auto = re.search(r"autoOpen\s*:\s*(true|false)", content)
            if m_auto:
                self.var_auto_open.set(m_auto.group(1) == "true")

            m_slide = re.search(r"slideshow\s*:\s*(true|false)", content)
            if m_slide:
                self.var_slideshow.set(m_slide.group(1) == "true")

            m_rem = re.search(r"rememberClosed\s*:\s*(true|false)", content)
            if m_rem:
                self.var_remember_closed.set(m_rem.group(1) == "true")

            m_php = re.search(r"autoDetectPhp\s*:\s*(true|false)", content)
            if m_php:
                self.var_auto_php.set(m_php.group(1) == "true")

            m_sec = re.search(r"slideshowInterval\s*:\s*(\d+)", content)
            if m_sec:
                sec_val = int(int(m_sec.group(1)) / 1000)
                self.ent_interval.delete(0, tk.END)
                self.ent_interval.insert(0, str(sec_val))

            self.update_banner_toggle_ui()
        except Exception as e:
            print(f"Error loading settings: {e}")

        # Load media titles from banner_meta.json
        try:
            if os.path.exists(BANNER_META_JSON):
                with open(BANNER_META_JSON, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.media_titles = {k: v.get("title", "") for k, v in meta.items() if isinstance(v, dict)}
        except Exception as e:
            print(f"Error loading banner_meta.json: {e}")

    def save_settings(self, silent=False):
        if not os.path.exists(CONFIG_JS):
            messagebox.showerror("Error", f"Could not find configuration file:\n{CONFIG_JS}")
            return

        try:
            sec_str = self.ent_interval.get().strip()
            sec_int = int(sec_str) if sec_str.isdigit() else 5
            ms_val = max(1, sec_int) * 1000

            with open(CONFIG_JS, "r", encoding="utf-8") as f:
                content = f.read()

            if re.search(r"enabled\s*:\s*(true|false)", content):
                content = re.sub(
                    r"enabled\s*:\s*(true|false)",
                    f"enabled: {'true' if self.var_banner_enabled.get() else 'false'}",
                    content
                )
            else:
                content = re.sub(
                    r"const bannerSettings\s*=\s*\{",
                    f"const bannerSettings = {{\n    enabled: {'true' if self.var_banner_enabled.get() else 'false'},",
                    content
                )

            content = re.sub(
                r"autoOpen\s*:\s*(true|false)",
                f"autoOpen: {'true' if self.var_auto_open.get() else 'false'}",
                content
            )
            content = re.sub(
                r"slideshow\s*:\s*(true|false)",
                f"slideshow: {'true' if self.var_slideshow.get() else 'false'}",
                content
            )
            content = re.sub(
                r"rememberClosed\s*:\s*(true|false)",
                f"rememberClosed: {'true' if self.var_remember_closed.get() else 'false'}",
                content
            )
            content = re.sub(
                r"autoDetectPhp\s*:\s*(true|false)",
                f"autoDetectPhp: {'true' if self.var_auto_php.get() else 'false'}",
                content
            )
            content = re.sub(
                r"slideshowInterval\s*:\s*\d+",
                f"slideshowInterval: {ms_val}",
                content
            )

            now_ms = int(datetime.now().timestamp() * 1000)
            if re.search(r"lastUpdated\s*:\s*\d+", content):
                content = re.sub(r"lastUpdated\s*:\s*\d+", f"lastUpdated: {now_ms}", content)
            else:
                content = re.sub(
                    r"const bannerSettings\s*=\s*\{",
                    f"const bannerSettings = {{\n    lastUpdated: {now_ms},",
                    content
                )

            media_lines = ",\n".join([f'    "{item["rel_path"]}"' for item in self.media_items])
            replacement_array = f"const bannerMedia = [\n{media_lines}\n];"
            content = re.sub(r"const bannerMedia\s*=\s*\[[\s\S]*?\];", replacement_array, content)

            # Build bannerMeta block (only include items that have a non-empty title)
            non_empty_titles = {k: v for k, v in self.media_titles.items() if v.strip()}
            meta_pairs = ",\n".join(
                [f'    "{k}": {{"title": "{v}"}}' for k, v in non_empty_titles.items()]
            )
            meta_block = f"const bannerMeta = {{\n{meta_pairs}\n}};"
            # Replace existing bannerMeta block or insert before bannerMedia
            if re.search(r"const bannerMeta\s*=\s*\{[\s\S]*?\};", content):
                content = re.sub(r"const bannerMeta\s*=\s*\{[\s\S]*?\};", meta_block, content)
            else:
                content = content.replace("const bannerMedia =", f"{meta_block}\n\nconst bannerMedia =")

            with open(CONFIG_JS, "w", encoding="utf-8") as f:
                f.write(content)

            # Save banner_meta.json as well
            meta_json = {k: {"title": v} for k, v in self.media_titles.items() if v.strip()}
            with open(BANNER_META_JSON, "w", encoding="utf-8") as f:
                json.dump(meta_json, f, ensure_ascii=False, indent=2)

            self.update_banner_toggle_ui()
            self.lbl_status.config(text="✅ Settings & media sequence saved to banner-config.js")
            if not silent:
                messagebox.showinfo("Success", "Settings and media items saved successfully to banner-config.js!")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save settings:\n{e}")

    def sync_and_refresh(self):
        if not os.path.exists(MEDIA_DIR):
            os.makedirs(MEDIA_DIR, exist_ok=True)

        disk_files = set(os.listdir(MEDIA_DIR))
        existing_names = set()
        new_items = []

        for item in self.media_items:
            fn = item["filename"]
            if fn in disk_files:
                full_p = os.path.join(MEDIA_DIR, fn)
                ext = os.path.splitext(fn)[1].lower()
                if ext in ALL_ALLOWED_EXTENSIONS:
                    size = os.path.getsize(full_p)
                    mtime = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%Y-%m-%d %H:%M")
                    new_items.append({
                        "filename": fn,
                        "rel_path": f"banner/banner_img/{fn}",
                        "type": get_file_type(fn).upper(),
                        "size": f"{size / (1024*1024):.2f} MB" if size > 1024*1024 else f"{size / 1024:.1f} KB",
                        "modified": mtime
                    })
                    existing_names.add(fn)

        for fn in sorted(disk_files):
            if fn not in existing_names:
                ext = os.path.splitext(fn)[1].lower()
                if ext in ALL_ALLOWED_EXTENSIONS:
                    full_p = os.path.join(MEDIA_DIR, fn)
                    size = os.path.getsize(full_p)
                    mtime = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%Y-%m-%d %H:%M")
                    new_items.append({
                        "filename": fn,
                        "rel_path": f"banner/banner_img/{fn}",
                        "type": get_file_type(fn).upper(),
                        "size": f"{size / (1024*1024):.2f} MB" if size > 1024*1024 else f"{size / 1024:.1f} KB",
                        "modified": mtime
                    })

        self.media_items = new_items
        self.render_table()
        self.write_media_to_config_js()

    def refresh_all(self):
        config_order = []
        if os.path.exists(CONFIG_JS):
            try:
                with open(CONFIG_JS, "r", encoding="utf-8") as f:
                    txt = f.read()
                m = re.search(r"const bannerMedia\s*=\s*\[([\s\S]*?)\];", txt)
                if m:
                    for line in m.group(1).splitlines():
                        line = line.strip().strip(',"\'')
                        if line:
                            filename = os.path.basename(line)
                            config_order.append(filename)
            except Exception:
                pass

        disk_files = set()
        if os.path.exists(MEDIA_DIR):
            for fn in os.listdir(MEDIA_DIR):
                ext = os.path.splitext(fn)[1].lower()
                if ext in ALL_ALLOWED_EXTENSIONS:
                    disk_files.add(fn)

        self.media_items = []
        added = set()

        for fn in config_order:
            if fn in disk_files and fn not in added:
                full_p = os.path.join(MEDIA_DIR, fn)
                size = os.path.getsize(full_p)
                mtime = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%Y-%m-%d %H:%M")
                self.media_items.append({
                    "filename": fn,
                    "rel_path": f"banner/banner_img/{fn}",
                    "type": get_file_type(fn).upper(),
                    "size": f"{size / (1024*1024):.2f} MB" if size > 1024*1024 else f"{size / 1024:.1f} KB",
                    "modified": mtime
                })
                added.add(fn)

        for fn in sorted(disk_files):
            if fn not in added:
                full_p = os.path.join(MEDIA_DIR, fn)
                size = os.path.getsize(full_p)
                mtime = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%Y-%m-%d %H:%M")
                self.media_items.append({
                    "filename": fn,
                    "rel_path": f"banner/banner_img/{fn}",
                    "type": get_file_type(fn).upper(),
                    "size": f"{size / (1024*1024):.2f} MB" if size > 1024*1024 else f"{size / 1024:.1f} KB",
                    "modified": mtime
                })
                added.add(fn)

        self.render_table()
        self.write_media_to_config_js()
        self.load_settings()
        self.lbl_status.config(text=f"Loaded {len(self.media_items)} media items.")

    def render_table(self):
        selected_id = self.tree.selection()
        selected_idx = None
        if selected_id:
            try:
                selected_idx = int(self.tree.item(selected_id[0], "values")[0]) - 1
            except Exception:
                pass

        self.tree.delete(*self.tree.get_children())
        for idx, item in enumerate(self.media_items, 1):
            row_id = self.tree.insert("", tk.END, values=(
                idx,
                item["filename"],
                item["type"],
                item["size"],
                item["modified"]
            ))

        self.lbl_count.config(text=f"{len(self.media_items)} Banner Item{'s' if len(self.media_items) != 1 else ''}")

        if selected_idx is not None and selected_idx < len(self.media_items):
            children = self.tree.get_children()
            if children:
                target = children[selected_idx]
                self.tree.selection_set(target)
                self.tree.see(target)

    def write_media_to_config_js(self):
        if not os.path.exists(CONFIG_JS):
            return
        try:
            with open(CONFIG_JS, "r", encoding="utf-8") as f:
                content = f.read()

            media_lines = ",\n".join([f'    "{item["rel_path"]}"' for item in self.media_items])
            replacement_array = f"const bannerMedia = [\n{media_lines}\n];"
            content = re.sub(r"const bannerMedia\s*=\s*\[[\s\S]*?\];", replacement_array, content)

            # Also ensure bannerMeta block is synchronized
            non_empty_titles = {k: v for k, v in self.media_titles.items() if v.strip()}
            meta_pairs = ",\n".join(
                [f'    "{k}": {{"title": "{v}"}}' for k, v in non_empty_titles.items()]
            )
            meta_block = f"const bannerMeta = {{\n{meta_pairs}\n}};"
            if re.search(r"const bannerMeta\s*=\s*\{[\s\S]*?\};", content):
                content = re.sub(r"const bannerMeta\s*=\s*\{[\s\S]*?\};", meta_block, content)
            else:
                content = content.replace("const bannerMedia =", f"{meta_block}\n\nconst bannerMedia =")

            now_ms = int(datetime.now().timestamp() * 1000)
            if re.search(r"lastUpdated\s*:\s*\d+", content):
                content = re.sub(r"lastUpdated\s*:\s*\d+", f"lastUpdated: {now_ms}", content)
            else:
                content = re.sub(
                    r"const bannerSettings\s*=\s*\{",
                    f"const bannerSettings = {{\n    lastUpdated: {now_ms},",
                    content
                )

            with open(CONFIG_JS, "w", encoding="utf-8") as f:
                f.write(content)

            meta_json = {k: {"title": v} for k, v in self.media_titles.items() if v.strip()}
            with open(BANNER_META_JSON, "w", encoding="utf-8") as f:
                json.dump(meta_json, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error writing to config: {e}")

    def on_item_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        values = self.tree.item(selected[0], "values")
        idx = int(values[0]) - 1
        item = self.media_items[idx]
        self.current_selected_rel_path = item["rel_path"]
        self.show_preview(item)

        # Populate the caption entry
        title_val = self.media_titles.get(item["rel_path"], "")
        self.ent_caption.config(state="normal")
        self.ent_caption.delete(0, tk.END)
        if title_val:
            self.ent_caption.insert(0, title_val)
            self.ent_caption.config(fg="#FFFFFF")
        else:
            self.ent_caption.insert(0, "")
            self.ent_caption.config(fg="#FFFFFF")

    def show_preview(self, item):
        fn = item["filename"]
        mtype = item["type"]
        full_p = os.path.join(MEDIA_DIR, fn)

        self.lbl_preview_info.config(
            text=f"📄 {fn}\nType: {mtype}   •   Size: {item['size']}   •   Modified: {item['modified']}"
        )

        if not os.path.exists(full_p):
            self.lbl_preview_canvas.config(image="", text="File not found on disk")
            return

        if mtype == "IMAGE":
            try:
                img = Image.open(full_p)
                w, h = img.size
                card_w = self.preview_card.winfo_width() or 340
                card_h = self.preview_card.winfo_height() or 240
                img.thumbnail((card_w - 20, card_h - 20), Image.Resampling.LANCZOS)
                self.current_preview_photo = ImageTk.PhotoImage(img)
                self.lbl_preview_canvas.config(image=self.current_preview_photo, text="")
            except Exception as e:
                self.lbl_preview_canvas.config(image="", text=f"Could not render image:\n{e}")
        elif mtype == "VIDEO":
            self.current_preview_photo = None
            self.lbl_preview_canvas.config(
                image="",
                text=f"🎬 HTML5 Video Player\n\nFile: {fn}\nDouble-click row to play in default media player"
            )
        elif mtype == "PDF":
            self.current_preview_photo = None
            self.lbl_preview_canvas.config(
                image="",
                text=f"📄 PDF Document\n\nFile: {fn}\nDouble-click row to open in PDF reader"
            )
        else:
            self.current_preview_photo = None
            self.lbl_preview_canvas.config(image="", text=f"File: {fn}")

    def on_double_click_item(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        idx = int(values[0]) - 1
        item = self.media_items[idx]
        full_p = os.path.join(MEDIA_DIR, item["filename"])

        if os.path.exists(full_p):
            try:
                if sys.platform.startswith("win"):
                    os.startfile(full_p)
                elif sys.platform.startswith("darwin"):
                    subprocess.call(["open", full_p])
                else:
                    subprocess.call(["xdg-open", full_p])
            except Exception as e:
                messagebox.showerror("Open Error", f"Could not open file:\n{e}")

    def add_media_files(self):
        filetypes = [
            ("All Supported Media", "*.jpg;*.jpeg;*.png;*.webp;*.gif;*.pdf;*.mp4;*.webm;*.ogg;*.heic;*.heif"),
            ("Images (*.jpg, *.png, *.webp, etc.)", "*.jpg;*.jpeg;*.png;*.webp;*.gif;*.heic;*.heif"),
            ("Videos (*.mp4, *.webm, *.ogg)", "*.mp4;*.webm;*.ogg;*.mov"),
            ("Documents (*.pdf)", "*.pdf"),
            ("All Files", "*.*")
        ]

        paths = filedialog.askopenfilenames(
            title="Select Banner Media Files",
            filetypes=filetypes
        )

        if not paths:
            return

        added_count = 0
        for src_path in paths:
            raw_fn = os.path.basename(src_path)
            ext = os.path.splitext(raw_fn)[1].lower()

            if ext not in ALL_ALLOWED_EXTENSIONS:
                continue

            if ext in {".heic", ".heif"}:
                try:
                    with open(src_path, "rb") as f:
                        data = f.read()
                    conv = convert_heic_to_jpeg(data)
                    if conv:
                        raw_fn = os.path.splitext(raw_fn)[0] + ".jpg"
                        ext = ".jpg"
                        dest_fn = self.get_unique_filename(raw_fn)
                        dest_p = os.path.join(MEDIA_DIR, dest_fn)
                        with open(dest_p, "wb") as f:
                            f.write(conv)
                        added_count += 1
                        continue
                except Exception as e:
                    print(f"Failed converting HEIC: {e}")

            dest_fn = self.get_unique_filename(raw_fn)
            dest_p = os.path.join(MEDIA_DIR, dest_fn)
            try:
                shutil.copy2(src_path, dest_p)
                added_count += 1
            except Exception as e:
                messagebox.showerror("Copy Error", f"Could not copy {raw_fn}:\n{e}")

        if added_count > 0:
            self.sync_and_refresh()
            self.lbl_status.config(text=f"✅ Added {added_count} media item(s).")
            messagebox.showinfo("Media Added", f"Successfully imported {added_count} media file(s) into banners!")

    def get_unique_filename(self, filename):
        safe = re.sub(r"[^\w\-_.]", "_", filename)
        base, ext = os.path.splitext(safe)
        dest = os.path.join(MEDIA_DIR, safe)
        counter = 1
        while os.path.exists(dest):
            safe = f"{base}_{counter}{ext}"
            dest = os.path.join(MEDIA_DIR, safe)
            counter += 1
        return safe

    def move_up(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(self.tree.item(selected[0], "values")[0]) - 1
        if idx > 0:
            self.media_items[idx], self.media_items[idx - 1] = self.media_items[idx - 1], self.media_items[idx]
            self.render_table()
            self.write_media_to_config_js()
            new_target = self.tree.get_children()[idx - 1]
            self.tree.selection_set(new_target)
            self.tree.see(new_target)
            self.lbl_status.config(text=f"Moved '{self.media_items[idx-1]['filename']}' up.")

    def move_down(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(self.tree.item(selected[0], "values")[0]) - 1
        if idx < len(self.media_items) - 1:
            self.media_items[idx], self.media_items[idx + 1] = self.media_items[idx + 1], self.media_items[idx]
            self.render_table()
            self.write_media_to_config_js()
            new_target = self.tree.get_children()[idx + 1]
            self.tree.selection_set(new_target)
            self.tree.see(new_target)
            self.lbl_status.config(text=f"Moved '{self.media_items[idx+1]['filename']}' down.")

    def rename_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an item to rename.")
            return

        idx = int(self.tree.item(selected[0], "values")[0]) - 1
        item = self.media_items[idx]
        old_fn = item["filename"]
        base, ext = os.path.splitext(old_fn)

        new_base = simpledialog.askstring(
            "Rename Media Item",
            f"Enter new name for '{old_fn}':",
            initialvalue=base,
            parent=self.root
        )

        if not new_base or new_base.strip() == base:
            return

        safe_base = re.sub(r"[^\w\-_]", "_", new_base.strip())
        new_fn = f"{safe_base}{ext}"
        old_p = os.path.join(MEDIA_DIR, old_fn)
        new_p = os.path.join(MEDIA_DIR, new_fn)

        if os.path.exists(new_p):
            messagebox.showerror("Error", f"A file named '{new_fn}' already exists.")
            return

        try:
            os.rename(old_p, new_p)
            self.media_items[idx]["filename"] = new_fn
            self.media_items[idx]["rel_path"] = f"banner/banner_img/{new_fn}"
            self.render_table()
            self.write_media_to_config_js()
            self.show_preview(self.media_items[idx])
            self.lbl_status.config(text=f"Renamed '{old_fn}' to '{new_fn}'.")
        except Exception as e:
            messagebox.showerror("Rename Error", f"Could not rename file:\n{e}")

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an item to delete.")
            return

        idx = int(self.tree.item(selected[0], "values")[0]) - 1
        item = self.media_items[idx]
        fn = item["filename"]

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete:\n\n'{fn}'\n\nThis will remove it from the banner slideshow and disk.",
            icon="warning",
            parent=self.root
        )

        if not confirm:
            return

        full_p = os.path.join(MEDIA_DIR, fn)
        try:
            if os.path.exists(full_p):
                os.remove(full_p)
            self.media_items.pop(idx)
            self.render_table()
            self.write_media_to_config_js()
            self.lbl_preview_canvas.config(image="", text="Item deleted")
            self.lbl_preview_info.config(text="No item selected")
            self.lbl_status.config(text=f"Deleted '{fn}'.")
        except Exception as e:
            messagebox.showerror("Delete Error", f"Could not delete file:\n{e}")

    def open_media_folder(self):
        if not os.path.exists(MEDIA_DIR):
            os.makedirs(MEDIA_DIR, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(MEDIA_DIR)
            elif sys.platform.startswith("darwin"):
                subprocess.call(["open", MEDIA_DIR])
            else:
                subprocess.call(["xdg-open", MEDIA_DIR])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open directory:\n{e}")

    def toggle_preview_server(self):
        """Starts or stops a local HTTP server serving the school website."""
        if self.preview_running:
            self.stop_preview_server()
        else:
            self.start_preview_server()

    def start_preview_server(self):
        try:
            handler = http.server.SimpleHTTPRequestHandler
            os.chdir(PROJECT_ROOT)
            self.preview_httpd = socketserver.TCPServer(("", PREVIEW_PORT), handler)
            self.preview_thread = threading.Thread(target=self.preview_httpd.serve_forever, daemon=True)
            self.preview_thread.start()
            self.preview_running = True

            self.btn_preview_srv.config(text="⏹️ Stop Web Preview", bg="#EF4444")
            self.lbl_status.config(text=f"🌐 Preview server running at http://localhost:{PREVIEW_PORT}")

            webbrowser.open(f"http://localhost:{PREVIEW_PORT}/index.html")
        except Exception as e:
            messagebox.showerror("Server Error", f"Could not start preview server on port {PREVIEW_PORT}:\n{e}")

    def stop_preview_server(self):
        if self.preview_httpd:
            try:
                self.preview_httpd.shutdown()
                self.preview_httpd.server_close()
            except Exception:
                pass
        self.preview_running = False
        self.btn_preview_srv.config(text="🌐 Launch Live Website Preview", bg=self.c_primary)
        self.lbl_status.config(text="Preview server stopped.")

    def open_mobile_upload_dialog(self):
        """Launches the Mobile Upload Server and displays QR Code."""
        if not self.mobile_running:
            self.start_mobile_server()

        win = tk.Toplevel(self.root)
        win.title("Mobile Upload Scanner - Shree Chautara Mavi")
        win.geometry("480x560")
        win.resizable(False, False)
        win.configure(bg=self.c_panel)
        win.transient(self.root)
        win.grab_set()

        lan_ip = get_local_ip()
        upload_url = f"http://{lan_ip}:{self.mobile_port}"

        lbl_hdr = tk.Label(
            win,
            text="📱 Mobile Phone Upload Portal",
            font=("Segoe UI", 13, "bold"),
            fg="#FFFFFF",
            bg=self.c_panel
        )
        lbl_hdr.pack(pady=(16, 4))

        lbl_desc = tk.Label(
            win,
            text="Connect your phone to the same Wi-Fi and scan QR code:\nPhotos, videos, and PDFs upload straight to Website Banners!",
            font=("Segoe UI", 9),
            fg=self.c_muted,
            bg=self.c_panel,
            justify="center"
        )
        lbl_desc.pack(padx=20, pady=(0, 12))

        qr_frame = tk.Frame(win, bg="#FFFFFF", padx=10, pady=10, relief="flat")
        qr_frame.pack(pady=6)

        qr_label = tk.Label(qr_frame, bg="#FFFFFF")
        qr_label.pack()

        if HAS_QRCODE:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=6,
                border=2,
            )
            qr.add_data(upload_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="#000000", back_color="#FFFFFF")
            self.qr_photo = ImageTk.PhotoImage(qr_img)
            qr_label.config(image=self.qr_photo)
        else:
            qr_label.config(
                text="[qrcode module not installed]\nRun: pip install qrcode\n\nOr open URL manually below:",
                fg="#000000",
                padx=20,
                pady=40
            )

        url_box = tk.Frame(win, bg=self.c_card, padx=12, pady=8)
        url_box.pack(fill=tk.X, padx=24, pady=(12, 16))

        ent_url = tk.Entry(
            url_box,
            font=("Segoe UI", 10, "bold"),
            bg=self.c_card,
            fg="#58A6FF",
            justify="center",
            relief="flat"
        )
        ent_url.insert(0, upload_url)
        ent_url.configure(state="readonly")
        ent_url.pack(fill=tk.X)

        tk.Button(
            win,
            text="🌐 Open Upload Page in Browser",
            bg=self.c_primary,
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=lambda: webbrowser.open(upload_url)
        ).pack(pady=4)

        tk.Button(
            win,
            text="Close Window",
            bg=self.c_card,
            fg=self.c_text,
            font=("Segoe UI", 9),
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=win.destroy
        ).pack(pady=(4, 16))

    def start_mobile_server(self):
        self.mobile_port = MOBILE_UPLOAD_PORT
        MobileUploadHandler.app_ref = self

        for port in range(MOBILE_UPLOAD_PORT, MOBILE_UPLOAD_PORT + 10):
            try:
                self.mobile_httpd = socketserver.TCPServer(("", port), MobileUploadHandler)
                self.mobile_port = port
                break
            except OSError:
                continue

        if self.mobile_httpd:
            self.mobile_thread = threading.Thread(target=self.mobile_httpd.serve_forever, daemon=True)
            self.mobile_thread.start()
            self.mobile_running = True
            print(f"Mobile server listening at port {self.mobile_port}")

    def on_close(self):
        if self.preview_httpd:
            try:
                self.preview_httpd.shutdown()
                self.preview_httpd.server_close()
            except Exception:
                pass

        if self.mobile_httpd:
            try:
                self.mobile_httpd.shutdown()
                self.mobile_httpd.server_close()
            except Exception:
                pass

        self.root.destroy()


def main():
    root = tk.Tk()
    app = BannerAdminApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()

