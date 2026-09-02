import os
import sys
import io
import json
import shutil
import socket
import threading
import socketserver
import http.server
import urllib.parse
import webbrowser
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

# Directory configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORIES_DIR = os.path.join(SCRIPT_DIR, "categories")
MANIFEST_FILE = os.path.join(SCRIPT_DIR, "categories.json")
DATA_JS_FILE = os.path.join(SCRIPT_DIR, "categories-data.js")
METADATA_FILE = os.path.join(SCRIPT_DIR, "categories_metadata.json")
DEFAULT_PORT = 8000
MOBILE_UPLOAD_PORT = 8765

# Supported image extensions (including HEIC)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".heic"}


def get_local_ip():
    """Detect the machine's LAN IP address reliably."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


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
        # Strip trailing boundary delimiter
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
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=92)
        return output.getvalue()
    except Exception as e:
        print(f"HEIC conversion error: {e}")
        return None


class MobileUploadHandler(http.server.BaseHTTPRequestHandler):
    """Handles mobile upload requests with a beautiful mobile-first web UI."""

    app_ref = None  # Will be set to the GalleryAdminApp instance

    def log_message(self, format, *args):
        pass  # Suppress console noise

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
        elif path == "/api/categories":
            self.serve_categories()
        else:
            self.send_response(404)
            self.end_headers()

    def serve_categories(self):
        cats = []
        if os.path.exists(CATEGORIES_DIR):
            cats = sorted([
                d for d in os.listdir(CATEGORIES_DIR)
                if os.path.isdir(os.path.join(CATEGORIES_DIR, d))
            ])
        self.send_json({"categories": cats})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip("/") != "/api/upload":
            self.send_json({"error": "Not Found"}, 404)
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_json({"error": "Expected multipart/form-data"}, 400)
            return

        # Extract boundary
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[len("boundary="):].strip('"')
                break

        if not boundary:
            self.send_json({"error": "No boundary in Content-Type"}, 400)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        parts = parse_multipart(body, boundary)
        category = None
        uploaded_files = []
        errors = []
        converted_heic = False

        for name, filename, content in parts:
            if name == "category":
                category = content.decode("utf-8", errors="replace").strip()
            elif name == "files" and filename:
                uploaded_files.append((filename, content))

        if not category:
            self.send_json({"error": "No category specified"}, 400)
            return

        # Security: sanitize category name
        safe_category = os.path.basename(category)
        cat_path = os.path.join(CATEGORIES_DIR, safe_category)
        if not os.path.exists(cat_path):
            self.send_json({"error": f"Category '{safe_category}' not found"}, 404)
            return

        today_str = datetime.now().strftime("%Y/%m/%d")
        saved_names = []

        for filename, content in uploaded_files:
            ext = os.path.splitext(filename)[1].lower()
            
            # Check if it's a supported image format
            if ext not in IMAGE_EXTENSIONS:
                errors.append(f"Skipped '{filename}' (unsupported format)")
                continue
            
            # Handle HEIC files
            if ext == ".heic":
                if HAS_HEIF:
                    try:
                        # Convert HEIC to JPEG
                        jpeg_data = convert_heic_to_jpeg(content)
                        if jpeg_data:
                            content = jpeg_data
                            filename = os.path.splitext(filename)[0] + ".jpg"
                            converted_heic = True
                        else:
                            errors.append(f"Failed to convert HEIC '{filename}'")
                            continue
                    except Exception as e:
                        errors.append(f"Failed to convert HEIC '{filename}': {str(e)}")
                        continue
                else:
                    # Try to save HEIC as-is if library not available
                    # but warn that it won't display properly
                    errors.append(f"HEIC support not installed. Install pillow-heif: pip install pillow-heif")
                    # Still save it but warn
                    pass

            safe_name = os.path.basename(filename)
            dest_path = os.path.join(cat_path, safe_name)
            base, file_ext = os.path.splitext(safe_name)
            counter = 1
            while os.path.exists(dest_path):
                safe_name = f"{base}_{counter}{file_ext}"
                dest_path = os.path.join(cat_path, safe_name)
                counter += 1

            try:
                with open(dest_path, "wb") as f:
                    f.write(content)

                # Save metadata with upload date via the app reference
                app = MobileUploadHandler.app_ref
                if app is not None:
                    if safe_category not in app.metadata:
                        app.metadata[safe_category] = {}
                    app.metadata[safe_category][safe_name] = {"date": today_str}
                    app.save_metadata()
                    # Schedule a UI refresh on the main thread
                    app.root.after(0, lambda: app.refresh_all())

                saved_names.append(safe_name)
            except Exception as e:
                errors.append(f"Failed to save '{filename}': {str(e)}")

        response = {
            "success": True,
            "category": safe_category,
            "uploaded": saved_names,
            "errors": errors,
            "date": today_str
        }
        
        if converted_heic:
            response["message"] = "HEIC files were converted to JPEG for compatibility"
        
        self.send_json(response)

    def serve_upload_page(self):
        """Serve the beautiful mobile-first upload page."""
        cats = []
        if os.path.exists(CATEGORIES_DIR):
            cats = sorted([
                d for d in os.listdir(CATEGORIES_DIR)
                if os.path.isdir(os.path.join(CATEGORIES_DIR, d))
            ])

        cat_options = "\n".join(
            f'<option value="{c}">{c}</option>' for c in cats
        ) if cats else '<option value="" disabled>No categories found</option>'

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>📱 Mobile Upload — Gallery Admin</title>
<style>
  :root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --card: #0f172a;
    --border: rgba(255,255,255,0.1);
    --primary: #3b82f6;
    --primary-dark: #2563eb;
    --success: #10b981;
    --danger: #ef4444;
    --gold: #f59e0b;
    --text: #f8fafc;
    --muted: #94a3b8;
    --radius: 14px;
    --radius-sm: 8px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }}
  .header {{
    background: linear-gradient(135deg, #0b2b64 0%, #1e3a8a 100%);
    padding: 1.2rem 1.25rem 1rem;
    border-bottom: 3px solid var(--gold);
    text-align: center;
  }}
  .header-logo {{ font-size: 2rem; margin-bottom: 0.2rem; }}
  .header h1 {{ font-size: 1.15rem; font-weight: 800; color: #fff; letter-spacing: -0.02em; }}
  .header p {{ font-size: 0.8rem; color: #93c5fd; margin-top: 0.2rem; }}
  .container {{ flex: 1; padding: 1.25rem; max-width: 520px; margin: 0 auto; width: 100%; }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem;
    margin-bottom: 1rem;
  }}
  .card-title {{ font-size: 0.88rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem; }}
  label {{ display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.4rem; color: var(--text); }}
  select, .drop-zone {{
    width: 100%;
    background: var(--card);
    border: 1.5px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: 1rem;
    font-family: inherit;
    padding: 0.75rem 1rem;
    outline: none;
    transition: border-color 0.2s;
    appearance: none;
    -webkit-appearance: none;
  }}
  select:focus {{ border-color: var(--primary); }}
  .select-wrap {{ position: relative; }}
  .select-wrap::after {{ content: '▾'; position: absolute; right: 1rem; top: 50%; transform: translateY(-50%); color: var(--muted); pointer-events: none; }}
  .drop-zone {{
    min-height: 140px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    cursor: pointer;
    border-style: dashed;
    border-color: rgba(59,130,246,0.45);
    text-align: center;
    position: relative;
    transition: all 0.2s;
  }}
  .drop-zone.dragging {{ border-color: var(--primary); background: rgba(59,130,246,0.08); }}
  .drop-zone.has-files {{ border-color: var(--success); background: rgba(16,185,129,0.06); border-style: solid; }}
  .drop-icon {{ font-size: 2.2rem; }}
  .drop-text {{ font-size: 0.9rem; color: var(--muted); }}
  .drop-hint {{ font-size: 0.75rem; color: var(--muted); opacity: 0.7; }}
  .drop-zone input[type=file] {{ position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; }}
  .source-btns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.65rem;
    margin-bottom: 0.75rem;
  }}
  .source-btn {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.2rem;
    padding: 0.85rem 0.5rem;
    background: var(--surface);
    border: 1.5px solid rgba(59,130,246,0.45);
    border-radius: var(--radius-sm);
    color: #93c5fd;
    font-size: 1.05rem;
    font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.18s, border-color 0.18s, transform 0.1s;
  }}
  .source-btn:hover, .source-btn:active {{ background: rgba(59,130,246,0.12); border-color: var(--primary); transform: scale(0.98); }}
  .source-btn-cam {{ border-color: rgba(16,185,129,0.45); color: #6ee7b7; }}
  .source-btn-cam:hover, .source-btn-cam:active {{ background: rgba(16,185,129,0.1); border-color: var(--success); }}
  .source-hint {{ font-size: 0.7rem; font-weight: 500; opacity: 0.75; }}
  .preview-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    gap: 0.5rem;
    margin-top: 0.85rem;
  }}
  .preview-item {{
    aspect-ratio: 1;
    border-radius: var(--radius-sm);
    overflow: hidden;
    background: var(--card);
    border: 1px solid var(--border);
    position: relative;
  }}
  .preview-item img {{ width: 100%; height: 100%; object-fit: cover; }}
  .preview-item .remove-btn {{
    position: absolute;
    top: 2px; right: 2px;
    width: 18px; height: 18px;
    background: rgba(239,68,68,0.9);
    color: #fff;
    border: none; border-radius: 50%;
    font-size: 0.7rem;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700;
  }}
  .file-count-badge {{
    display: inline-flex; align-items: center; gap: 0.3rem;
    background: rgba(16,185,129,0.15);
    color: var(--success);
    border: 1px solid rgba(16,185,129,0.3);
    border-radius: 999px;
    padding: 0.2rem 0.65rem;
    font-size: 0.78rem; font-weight: 700;
    margin-top: 0.6rem;
  }}
  .btn-upload {{
    width: 100%;
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: var(--radius-sm);
    padding: 0.9rem 1rem;
    font-size: 1.05rem;
    font-weight: 800;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    display: flex; align-items: center; justify-content: center; gap: 0.5rem;
  }}
  .btn-upload:hover {{ background: var(--primary-dark); }}
  .btn-upload:active {{ transform: scale(0.98); }}
  .btn-upload:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; }}
  .progress-bar-wrap {{
    background: rgba(255,255,255,0.08);
    border-radius: 999px;
    height: 8px;
    overflow: hidden;
    margin-top: 0.85rem;
    display: none;
  }}
  .progress-bar {{
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--success));
    border-radius: 999px;
    width: 0%;
    transition: width 0.3s;
  }}
  .result-box {{
    border-radius: var(--radius-sm);
    padding: 0.85rem 1rem;
    font-size: 0.88rem;
    font-weight: 600;
    display: none;
    margin-top: 0.75rem;
    line-height: 1.5;
  }}
  .result-success {{ background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); color: #6ee7b7; }}
  .result-error {{ background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; }}
  .footer {{ text-align: center; padding: 1rem; color: var(--muted); font-size: 0.76rem; }}
  .spinner {{ display: inline-block; width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<div class="header">
  <div class="header-logo">📱</div>
  <h1>Mobile Photo Upload</h1>
  <p>श्री चौतारा माध्यमिक विद्यालय — Gallery Admin</p>
</div>

<div class="container">
  <div class="card">
    <div class="card-title">📁 Step 1 — Choose Category</div>
    <div class="select-wrap">
      <select id="categorySelect">
        <option value="" disabled selected>Select a category…</option>
        {cat_options}
      </select>
    </div>
  </div>

  <div class="card">
    <div class="card-title">🖼️ Step 2 — Pick Photos</div>
    <div class="source-btns">
      <button class="source-btn" id="btnGallery" onclick="document.getElementById('fileInputGallery').click()">
        🖼️ From Gallery
        <span class="source-hint">Photo Library</span>
      </button>
      <button class="source-btn source-btn-cam" id="btnCamera" onclick="document.getElementById('fileInputCamera').click()">
        📷 Take Photo
        <span class="source-hint">Open Camera</span>
      </button>
    </div>
    <!-- Gallery picker — no capture, lets user browse phone library -->
    <input type="file" id="fileInputGallery" accept="image/*" multiple style="display:none">
    <!-- Camera picker — capture forces camera directly -->
    <input type="file" id="fileInputCamera" accept="image/*" multiple capture="environment" style="display:none">
    <div class="drop-zone" id="dropZone" style="margin-top:0.75rem; min-height:90px;">
      <div class="drop-icon" style="font-size:1.5rem;">📂</div>
      <div class="drop-text">Or drag &amp; drop images here</div>
      <div class="drop-hint">Selected photos will preview below</div>
    </div>
    <div id="previewGrid" class="preview-grid"></div>
    <div id="fileCountBadge" class="file-count-badge" style="display:none;">
      <span>✅</span> <span id="fileCountText">0 photos selected</span>
    </div>
  </div>

  <button class="btn-upload" id="uploadBtn" disabled>
    <span id="uploadBtnLabel">📤 Upload to Gallery</span>
  </button>

  <div class="progress-bar-wrap" id="progressWrap">
    <div class="progress-bar" id="progressBar"></div>
  </div>

  <div class="result-box" id="resultBox"></div>
</div>

<div class="footer">
  🔒 Connected to Gallery Admin on your computer<br>
  Photos go directly into the selected category folder
</div>

<script>
  let selectedFiles = [];

  const dropZone = document.getElementById('dropZone');
  const fileInputGallery = document.getElementById('fileInputGallery');
  const fileInputCamera  = document.getElementById('fileInputCamera');
  const previewGrid = document.getElementById('previewGrid');
  const fileCountBadge = document.getElementById('fileCountBadge');
  const fileCountText = document.getElementById('fileCountText');
  const uploadBtn = document.getElementById('uploadBtn');
  const uploadBtnLabel = document.getElementById('uploadBtnLabel');
  const progressWrap = document.getElementById('progressWrap');
  const progressBar = document.getElementById('progressBar');
  const resultBox = document.getElementById('resultBox');
  const categorySelect = document.getElementById('categorySelect');

  function updateUI() {{
    const count = selectedFiles.length;
    const hasCat = categorySelect.value !== '';
    if (count > 0) {{
      dropZone.classList.add('has-files');
      fileCountBadge.style.display = 'inline-flex';
      fileCountText.textContent = count + ' photo' + (count > 1 ? 's' : '') + ' selected';
    }} else {{
      dropZone.classList.remove('has-files');
      fileCountBadge.style.display = 'none';
    }}
    uploadBtn.disabled = !(count > 0 && hasCat);
  }}

  function addFiles(newFiles) {{
    // Merge, deduplicate by name+size
    const existing = new Set(selectedFiles.map(f => f.name + f.size));
    const toAdd = Array.from(newFiles).filter(f =>
      f.type.startsWith('image/') && !existing.has(f.name + f.size)
    );
    selectedFiles = [...selectedFiles, ...toAdd];
    renderPreviews();
  }}

  function renderPreviews() {{
    previewGrid.innerHTML = '';
    selectedFiles.forEach((file, idx) => {{
      const reader = new FileReader();
      reader.onload = (e) => {{
        const item = document.createElement('div');
        item.className = 'preview-item';
        item.innerHTML = `
          <img src="${{e.target.result}}" alt="${{file.name}}">
          <button class="remove-btn" data-idx="${{idx}}">✕</button>
        `;
        item.querySelector('.remove-btn').addEventListener('click', (ev) => {{
          ev.stopPropagation();
          const i = parseInt(ev.target.dataset.idx);
          selectedFiles.splice(i, 1);
          renderPreviews();
          updateUI();
        }});
        previewGrid.appendChild(item);
      }};
      reader.readAsDataURL(file);
    }});
    updateUI();
  }}

  // Gallery input (photo library on phone)
  fileInputGallery.addEventListener('change', () => {{
    addFiles(fileInputGallery.files);
    fileInputGallery.value = '';  // reset so same files can be re-added
  }});

  // Camera input (direct camera capture)
  fileInputCamera.addEventListener('change', () => {{
    addFiles(fileInputCamera.files);
    fileInputCamera.value = '';
  }});

  categorySelect.addEventListener('change', updateUI);

  // Drag & drop (desktop / PC browser test)
  dropZone.addEventListener('dragover', (e) => {{ e.preventDefault(); dropZone.classList.add('dragging'); }});
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));
  dropZone.addEventListener('drop', (e) => {{
    e.preventDefault();
    dropZone.classList.remove('dragging');
    addFiles(e.dataTransfer.files);
  }});

  function showResult(msg, isError) {{
    resultBox.className = 'result-box ' + (isError ? 'result-error' : 'result-success');
    resultBox.innerHTML = msg;
    resultBox.style.display = 'block';
    resultBox.scrollIntoView({{ behavior: 'smooth' }});
  }}

  uploadBtn.addEventListener('click', async () => {{
    if (selectedFiles.length === 0 || !categorySelect.value) return;

    uploadBtn.disabled = true;
    uploadBtnLabel.innerHTML = '<span class="spinner"></span> Uploading…';
    progressWrap.style.display = 'block';
    progressBar.style.width = '10%';
    resultBox.style.display = 'none';

    const formData = new FormData();
    formData.append('category', categorySelect.value);
    selectedFiles.forEach((file) => {{
      formData.append('files', file, file.name);
    }});

    progressBar.style.width = '40%';

    try {{
      const res = await fetch('/api/upload', {{
        method: 'POST',
        body: formData
      }});
      progressBar.style.width = '90%';
      const data = await res.json();
      progressBar.style.width = '100%';

      if (data.success) {{
        const count = data.uploaded.length;
        let msg = `✅ <strong>${{count}} photo${{count !== 1 ? 's' : ''}}</strong> uploaded to <strong>${{data.category}}</strong> (📅 ${{data.date}})`;
        if (data.message) {{
          msg += '<br>💡 ' + data.message;
        }}
        if (data.errors && data.errors.length > 0) {{
          msg += '<br>⚠️ ' + data.errors.join('<br>⚠️ ');
        }}
        showResult(msg, false);
        // Reset after success
        selectedFiles = [];
        previewGrid.innerHTML = '';
        updateUI();
      }} else {{
        showResult('❌ ' + (data.error || 'Upload failed'), true);
      }}
    }} catch (err) {{
      progressBar.style.width = '100%';
      showResult('❌ Network error: ' + err.message, true);
    }} finally {{
      uploadBtnLabel.innerHTML = '📤 Upload to Gallery';
      uploadBtn.disabled = false;
      setTimeout(() => {{ progressWrap.style.display = 'none'; progressBar.style.width = '0%'; }}, 1500);
    }}
  }});
</script>
</body>
</html>"""
        self.send_html(html)


class GalleryAdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Developer Admin Panel - Category Image Gallery")

        self.root.geometry("1100x720")
        self.root.minsize(800, 500)

        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.server_thread = None
        self.httpd = None
        self.server_running = False
        self.current_preview_photo = None
        self.metadata = {}

        # Mobile upload server
        self.mobile_httpd = None
        self.mobile_thread = None
        self.mobile_running = False
        self.mobile_port = MOBILE_UPLOAD_PORT
        self.qr_photo = None  # Keep reference to prevent GC

        self.init_directories()
        self.setup_styles()
        self.create_widgets()
        self.refresh_all()

    def init_directories(self):
        if not os.path.exists(CATEGORIES_DIR):
            os.makedirs(CATEGORIES_DIR)
        self.load_metadata()
        self.sync_manifest()

    def load_metadata(self):
        self.metadata = {}
        if os.path.exists(METADATA_FILE):
            try:
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception as e:
                print(f"Error loading metadata: {e}")
                self.metadata = {}

    def save_metadata(self):
        try:
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving metadata: {e}")

    def sync_manifest(self):
        manifest_data = []
        today_str = datetime.now().strftime("%Y/%m/%d")

        if os.path.exists(CATEGORIES_DIR):
            categories = sorted([
                d for d in os.listdir(CATEGORIES_DIR)
                if os.path.isdir(os.path.join(CATEGORIES_DIR, d))
            ])

            for cat in categories:
                cat_path = os.path.join(CATEGORIES_DIR, cat)
                images = sorted([
                    f for f in os.listdir(cat_path)
                    if os.path.isfile(os.path.join(cat_path, f))
                    and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
                ])

                if cat not in self.metadata:
                    self.metadata[cat] = {}

                cat_images_data = []
                for img in images:
                    img_path = os.path.join(cat_path, img)
                    if img in self.metadata[cat] and "date" in self.metadata[cat][img]:
                        img_date = self.metadata[cat][img]["date"]
                    else:
                        try:
                            mtime = os.path.getmtime(img_path)
                            img_date = datetime.fromtimestamp(mtime).strftime("%Y/%m/%d")
                        except Exception:
                            img_date = today_str
                        self.metadata[cat][img] = {"date": img_date}

                    cat_images_data.append({"name": img, "date": img_date})

                manifest_data.append({"category": cat, "images": cat_images_data})

        self.save_metadata()

        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        with open(DATA_JS_FILE, "w", encoding="utf-8") as f:
            f.write("// Auto-generated by admin_app.py - Allows index.html to run directly via file://\n")
            f.write(f"window.GALLERY_DATA = {json.dumps(manifest_data, indent=2)};\n")

        return manifest_data

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        BG_COLOR = "#0f172a"
        PANEL_BG = "#1e293b"
        CARD_BG = "#0f172a"
        PRIMARY = "#3b82f6"
        PRIMARY_HOVER = "#2563eb"
        DANGER = "#ef4444"
        DANGER_HOVER = "#dc2626"
        SUCCESS = "#10b981"
        AMBER = "#f59e0b"
        TEXT_MAIN = "#f8fafc"
        TEXT_MUTED = "#94a3b8"

        self.root.configure(bg=BG_COLOR)

        self.style.configure(".", background=BG_COLOR, foreground=TEXT_MAIN, font=("Segoe UI", 10))
        self.style.configure("TFrame", background=BG_COLOR)
        self.style.configure("Panel.TFrame", background=PANEL_BG, relief="flat")
        self.style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        self.style.configure("Status.TFrame", background="#0b0f19")
        self.style.configure("Notebook.TFrame", background=PANEL_BG)
        self.style.configure("TNotebook", background=BG_COLOR, borderwidth=0, tabmargins=0)
        self.style.configure("TNotebook.Tab",
                             background="#1e293b",
                             foreground=TEXT_MUTED,
                             padding=[14, 6],
                             font=("Segoe UI", 9, "bold"))
        self.style.map("TNotebook.Tab",
                       background=[("selected", PRIMARY)],
                       foreground=[("selected", "white")])

        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=TEXT_MAIN, background=BG_COLOR)
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 11, "bold"), foreground=PRIMARY, background=PANEL_BG)
        self.style.configure("Muted.TLabel", font=("Segoe UI", 9), foreground=TEXT_MUTED, background=BG_COLOR)
        self.style.configure("PanelMuted.TLabel", font=("Segoe UI", 9), foreground=TEXT_MUTED, background=PANEL_BG)
        self.style.configure("CardMuted.TLabel", font=("Segoe UI", 9), foreground=TEXT_MUTED, background=CARD_BG)
        self.style.configure("CardHeader.TLabel", font=("Segoe UI", 10, "bold"), foreground=TEXT_MAIN, background=CARD_BG)
        self.style.configure("Status.TLabel", font=("Segoe UI", 9, "italic"), foreground=TEXT_MUTED, background="#0b0f19")
        self.style.configure("URL.TLabel", font=("Segoe UI", 11, "bold"), foreground=PRIMARY, background=PANEL_BG)
        self.style.configure("Amber.TLabel", font=("Segoe UI", 9), foreground=AMBER, background=PANEL_BG)
        self.style.configure("Success.TLabel", font=("Segoe UI", 10, "bold"), foreground=SUCCESS, background=PANEL_BG)

        self.style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=7, relief="flat", borderwidth=0)
        self.style.configure("Primary.TButton", background=PRIMARY, foreground="white")
        self.style.map("Primary.TButton", background=[("active", PRIMARY_HOVER)])
        self.style.configure("Danger.TButton", background=DANGER, foreground="white")
        self.style.map("Danger.TButton", background=[("active", DANGER_HOVER)])
        self.style.configure("Secondary.TButton", background="#334155", foreground=TEXT_MAIN)
        self.style.map("Secondary.TButton", background=[("active", "#475569")])
        self.style.configure("Server.TButton", background=SUCCESS, foreground="white")
        self.style.map("Server.TButton", background=[("active", "#059669")])
        self.style.configure("Amber.TButton", background=AMBER, foreground="white")
        self.style.map("Amber.TButton", background=[("active", "#d97706")])

        self.style.configure("Treeview",
                             background=PANEL_BG, foreground=TEXT_MAIN,
                             fieldbackground=PANEL_BG, rowheight=30,
                             font=("Segoe UI", 10), borderwidth=0)
        self.style.configure("Treeview.Heading",
                             font=("Segoe UI", 10, "bold"), background="#334155",
                             foreground=TEXT_MAIN, relief="flat")
        self.style.map("Treeview",
                       background=[("selected", PRIMARY)],
                       foreground=[("selected", "white")])

    def create_widgets(self):
        # Top Header
        header_frame = ttk.Frame(self.root)
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))

        ttk.Label(header_frame, text="⚡ Gallery Developer Dashboard", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Manage categories, upload dates & mobile upload", style="Muted.TLabel").pack(side=tk.LEFT, padx=15, pady=(4, 0))

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=20, pady=5)
        self.root.grid_rowconfigure(1, weight=1)

        # Tab 1: Category / Image Manager
        self.tab_manage = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.tab_manage, text="  🗂️ Manage Gallery  ")

        # Tab 2: Mobile Upload
        self.tab_mobile = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.tab_mobile, text="  📱 Mobile Upload  ")

        self._build_manage_tab()
        self._build_mobile_tab()

        # Bottom Action Controls
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 8))

        self.btn_open_web = ttk.Button(bottom_frame, text="🚀 Open Gallery (Direct/Browser)",
                                       style="Primary.TButton", command=self.open_webpage)
        self.btn_open_web.pack(side=tk.LEFT)

        self.btn_server = ttk.Button(bottom_frame, text=f"🌐 Optional: Launch Server ({DEFAULT_PORT})",
                                     style="Secondary.TButton", command=self.toggle_web_server)
        self.btn_server.pack(side=tk.LEFT, padx=8)

        # Footer Status
        status_strip = ttk.Frame(self.root, style="Status.TFrame")
        status_strip.grid(row=3, column=0, sticky="ew")
        self.lbl_status = ttk.Label(status_strip, text="System Ready", style="Status.TLabel")
        self.lbl_status.pack(side=tk.LEFT, padx=15, pady=3)

    def _build_manage_tab(self):
        """Build the Category/Image Manager tab content."""
        frame = self.tab_manage
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        paned = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Left Panel: Categories List
        left_panel = ttk.Frame(paned, style="Panel.TFrame")
        paned.add(left_panel, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        ttk.Label(ttk.Frame(left_panel, style="Panel.TFrame"),
                  text="📁 Categories Directory", style="SubHeader.TLabel").pack(side=tk.LEFT)
        cat_hf = ttk.Frame(left_panel, style="Panel.TFrame")
        cat_hf.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        ttk.Label(cat_hf, text="📁 Categories Directory", style="SubHeader.TLabel").pack(side=tk.LEFT)

        tree_frame = ttk.Frame(left_panel, style="Panel.TFrame")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.cat_tree = ttk.Treeview(tree_frame, columns=("count",), show="tree headings", selectmode="browse")
        self.cat_tree.heading("#0", text="Category Name", anchor=tk.W)
        self.cat_tree.heading("count", text="Images", anchor=tk.CENTER)
        self.cat_tree.column("#0", stretch=True, minwidth=120)
        self.cat_tree.column("count", width=65, stretch=False, anchor=tk.CENTER)
        cat_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.cat_tree.yview)
        self.cat_tree.configure(yscrollcommand=cat_scroll.set)
        self.cat_tree.grid(row=0, column=0, sticky="nsew")
        cat_scroll.grid(row=0, column=1, sticky="ns")
        self.cat_tree.bind("<<TreeviewSelect>>", self.on_category_select)

        cat_btn_frame = ttk.Frame(left_panel, style="Panel.TFrame")
        cat_btn_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=12)
        ttk.Button(cat_btn_frame, text="➕ New Category", style="Primary.TButton", command=self.create_category).pack(fill=tk.X, pady=3)
        ttk.Button(cat_btn_frame, text="✏️ Rename Selected", style="Secondary.TButton", command=self.rename_category).pack(fill=tk.X, pady=3)
        ttk.Button(cat_btn_frame, text="🗑️ Delete Selected", style="Danger.TButton", command=self.delete_category).pack(fill=tk.X, pady=3)

        # Right Panel
        right_panel = ttk.Frame(paned, style="Panel.TFrame")
        paned.add(right_panel, weight=3)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        img_hf = ttk.Frame(right_panel, style="Panel.TFrame")
        img_hf.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        self.lbl_selected_cat = ttk.Label(img_hf, text="Select a Category", style="SubHeader.TLabel")
        self.lbl_selected_cat.pack(side=tk.LEFT)

        img_content_frame = ttk.Frame(right_panel, style="Panel.TFrame")
        img_content_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        img_content_frame.grid_rowconfigure(0, weight=1)
        img_content_frame.grid_columnconfigure(0, weight=3)
        img_content_frame.grid_columnconfigure(1, weight=2)

        # Listbox
        listbox_container = ttk.Frame(img_content_frame, style="Panel.TFrame")
        listbox_container.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        listbox_container.grid_rowconfigure(0, weight=1)
        listbox_container.grid_columnconfigure(0, weight=1)

        self.img_listbox = tk.Listbox(listbox_container, font=("Segoe UI", 10), selectmode=tk.SINGLE,
                                      bg="#0f172a", fg="#f8fafc", selectbackground="#3b82f6",
                                      selectforeground="#ffffff", bd=0, highlightthickness=1,
                                      highlightbackground="#334155")
        img_scroll = ttk.Scrollbar(listbox_container, orient=tk.VERTICAL, command=self.img_listbox.yview)
        self.img_listbox.configure(yscrollcommand=img_scroll.set)
        self.img_listbox.grid(row=0, column=0, sticky="nsew")
        img_scroll.grid(row=0, column=1, sticky="ns")
        self.img_listbox.bind("<<ListboxSelect>>", self.on_image_select)
        self.img_listbox.bind("<Double-Button-1>", lambda e: self.rename_image())

        # Preview Panel
        preview_panel = ttk.Frame(img_content_frame, style="Card.TFrame")
        preview_panel.grid(row=0, column=1, sticky="nsew")
        preview_panel.grid_rowconfigure(1, weight=1)
        preview_panel.grid_columnconfigure(0, weight=1)

        prev_head_frame = ttk.Frame(preview_panel, style="Card.TFrame")
        prev_head_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        ttk.Label(prev_head_frame, text="🔍 Image Preview & Details", style="CardHeader.TLabel").pack(side=tk.LEFT)

        self.preview_lbl = tk.Label(preview_panel,
                                    text="No image selected\n\nClick an image to preview",
                                    font=("Segoe UI", 9), bg="#0b0f19", fg="#64748b",
                                    relief="flat", bd=0, highlightthickness=1,
                                    highlightbackground="#334155")
        self.preview_lbl.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)

        meta_frame = ttk.Frame(preview_panel, style="Card.TFrame")
        meta_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 8))

        self.lbl_preview_name = ttk.Label(meta_frame, text="Name: —", style="CardHeader.TLabel", wraplength=230)
        self.lbl_preview_name.pack(anchor="w", pady=(0, 2))
        self.lbl_preview_dims = ttk.Label(meta_frame, text="Resolution: —", style="CardMuted.TLabel")
        self.lbl_preview_dims.pack(anchor="w")
        self.lbl_preview_size = ttk.Label(meta_frame, text="Size: —", style="CardMuted.TLabel")
        self.lbl_preview_size.pack(anchor="w")
        self.lbl_preview_date = ttk.Label(meta_frame, text="📅 Upload Date: —", style="CardMuted.TLabel")
        self.lbl_preview_date.pack(anchor="w")

        # Image Action Buttons
        img_btn_frame = ttk.Frame(right_panel, style="Panel.TFrame")
        img_btn_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=12)
        img_btn_frame.grid_columnconfigure(0, weight=1)
        img_btn_frame.grid_columnconfigure(1, weight=1)
        img_btn_frame.grid_columnconfigure(2, weight=1)

        self.btn_upload = ttk.Button(img_btn_frame, text="📤 Upload Images",
                                     style="Primary.TButton", command=self.upload_images, state=tk.DISABLED)
        self.btn_upload.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.btn_rename_img = ttk.Button(img_btn_frame, text="✏️ Edit Image Label",
                                         style="Secondary.TButton", command=self.rename_image, state=tk.DISABLED)
        self.btn_rename_img.grid(row=0, column=1, sticky="ew", padx=4)
        self.btn_delete_img = ttk.Button(img_btn_frame, text="❌ Delete Image",
                                         style="Danger.TButton", command=self.delete_images, state=tk.DISABLED)
        self.btn_delete_img.grid(row=0, column=2, sticky="ew", padx=(4, 0))

    def _build_mobile_tab(self):
        """Build the Mobile Upload tab with QR code and server controls."""
        frame = self.tab_mobile
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        # ---- LEFT COLUMN: Server Controls & Info ----
        left_col = ttk.Frame(frame, style="Panel.TFrame")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left_col.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ttk.Frame(left_col, style="Panel.TFrame")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(hdr, text="📱 Mobile Upload Server", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(hdr,
                  text="Start the upload server, then scan the QR code\nor type the URL on your phone browser.",
                  style="PanelMuted.TLabel").pack(anchor="w", pady=(3, 0))

        # Server Status Card
        status_card = tk.Frame(left_col, bg="#0f172a", relief="flat",
                               highlightthickness=1, highlightbackground="#334155")
        status_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        status_inner = ttk.Frame(status_card, style="Card.TFrame")
        status_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        ttk.Label(status_inner, text="Server Status", style="CardMuted.TLabel").pack(anchor="w", padx=12, pady=(10, 2))
        self.lbl_mobile_status = ttk.Label(status_inner, text="⚫ Offline", style="CardHeader.TLabel")
        self.lbl_mobile_status.pack(anchor="w", padx=12, pady=(0, 4))

        ttk.Label(status_inner, text="Upload URL (type or scan on phone)", style="CardMuted.TLabel").pack(anchor="w", padx=12, pady=(8, 2))
        self.lbl_mobile_url = ttk.Label(status_inner, text="—", style="URL.TLabel", wraplength=340)
        self.lbl_mobile_url.pack(anchor="w", padx=12, pady=(0, 10))

        # Copy URL button
        self.btn_copy_url = ttk.Button(left_col, text="📋 Copy URL to Clipboard",
                                       style="Secondary.TButton", command=self.copy_mobile_url, state=tk.DISABLED)
        self.btn_copy_url.grid(row=2, column=0, sticky="ew", pady=(0, 6))

        # Open in browser button
        self.btn_open_mobile = ttk.Button(left_col, text="🌐 Open in PC Browser (Test)",
                                          style="Secondary.TButton", command=self.open_mobile_in_browser, state=tk.DISABLED)
        self.btn_open_mobile.grid(row=3, column=0, sticky="ew", pady=(0, 12))

        # Start/Stop mobile server button
        self.btn_mobile_server = ttk.Button(left_col, text="▶  Start Mobile Upload Server",
                                            style="Amber.TButton", command=self.toggle_mobile_server)
        self.btn_mobile_server.grid(row=4, column=0, sticky="ew")

        # How to use section
        how_frame = tk.Frame(left_col, bg="#1e293b", relief="flat",
                             highlightthickness=1, highlightbackground="#334155")
        how_frame.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        how_inner = ttk.Frame(how_frame, style="Panel.TFrame")
        how_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        ttk.Label(how_inner, text="📖 How It Works", style="SubHeader.TLabel").pack(anchor="w", padx=12, pady=(10, 6))
        steps = [
            ("1️⃣", "Make sure your phone & PC are on the\n   same Wi-Fi network"),
            ("2️⃣", "Click 'Start Mobile Upload Server'"),
            ("3️⃣", "Scan the QR code or type the URL in\n   your phone's browser"),
            ("4️⃣", "Choose a category, pick your photos\n   and tap Upload"),
            ("5️⃣", "Gallery auto-refreshes in admin panel"),
        ]
        for icon, text in steps:
            row_f = ttk.Frame(how_inner, style="Panel.TFrame")
            row_f.pack(fill=tk.X, padx=12, pady=3)
            ttk.Label(row_f, text=icon, style="PanelMuted.TLabel").pack(side=tk.LEFT)
            ttk.Label(row_f, text=text, style="PanelMuted.TLabel").pack(side=tk.LEFT, padx=6)

        ttk.Label(how_inner, text="", style="PanelMuted.TLabel").pack(pady=4)

        # ---- RIGHT COLUMN: QR Code Display ----
        right_col = ttk.Frame(frame, style="Panel.TFrame")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        right_col.grid_rowconfigure(1, weight=1)
        right_col.grid_columnconfigure(0, weight=1)

        ttk.Label(right_col, text="📷 QR Code — Scan to Open on Phone",
                  style="SubHeader.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))

        # QR Canvas placeholder
        qr_container = tk.Frame(right_col, bg="#0f172a", relief="flat",
                                highlightthickness=1, highlightbackground="#334155")
        qr_container.grid(row=1, column=0, sticky="nsew")

        self.qr_label = tk.Label(qr_container,
                                 text="QR code will appear\nhere after starting\nthe upload server",
                                 font=("Segoe UI", 10), bg="#0f172a", fg="#64748b",
                                 justify=tk.CENTER)
        self.qr_label.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        ttk.Label(right_col,
                  text="🔒 Works only on your local Wi-Fi network",
                  style="Amber.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))

        if not HAS_QRCODE:
            ttk.Label(right_col,
                      text="⚠️ Install qrcode library for QR support:\n   pip install qrcode[pil]",
                      style="Amber.TLabel").grid(row=3, column=0, sticky="w", pady=(4, 0))

    # =====================================================================
    # Mobile Upload Server Methods
    # =====================================================================

    def toggle_mobile_server(self):
        if not self.mobile_running:
            self.start_mobile_server()
        else:
            self.stop_mobile_server()

    def start_mobile_server(self):
        local_ip = get_local_ip()
        url = f"http://{local_ip}:{self.mobile_port}/upload"

        # Set the app reference on the handler class
        MobileUploadHandler.app_ref = self

        class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        try:
            self.mobile_httpd = ThreadedTCPServer(("", self.mobile_port), MobileUploadHandler)
            self.mobile_thread = threading.Thread(target=self.mobile_httpd.serve_forever, daemon=True)
            self.mobile_thread.start()
            self.mobile_running = True
            self.mobile_url = url

            self.lbl_mobile_status.config(text="🟢 Running", foreground="#10b981")
            self.lbl_mobile_url.config(text=url)
            self.btn_mobile_server.config(text="⏹  Stop Mobile Upload Server", style="Danger.TButton")
            self.btn_copy_url.config(state=tk.NORMAL)
            self.btn_open_mobile.config(state=tk.NORMAL)
            self.set_status(f"📱 Mobile upload server active at {url}")

            self._render_qr(url)

        except OSError as e:
            messagebox.showerror("Port Error",
                                 f"Could not start mobile server on port {self.mobile_port}.\n"
                                 f"Port may be in use. Error: {e}", parent=self.root)

    def stop_mobile_server(self):
        if self.mobile_httpd:
            self.mobile_httpd.shutdown()
            self.mobile_httpd.server_close()
            self.mobile_httpd = None
        self.mobile_running = False
        self.mobile_url = ""
        self.lbl_mobile_status.config(text="⚫ Offline", foreground="#94a3b8")
        self.lbl_mobile_url.config(text="—")
        self.btn_mobile_server.config(text="▶  Start Mobile Upload Server", style="Amber.TButton")
        self.btn_copy_url.config(state=tk.DISABLED)
        self.btn_open_mobile.config(state=tk.DISABLED)
        self.qr_label.config(image="", text="QR code will appear\nhere after starting\nthe upload server")
        self.qr_photo = None
        self.set_status("Mobile upload server stopped.")

    def _render_qr(self, url):
        """Generate and display QR code image in the label widget."""
        if not HAS_QRCODE:
            self.qr_label.config(
                text=f"QR library not installed.\n\nManually type this URL\non your phone:\n\n{url}",
                fg="#f59e0b"
            )
            return

        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=7,
                border=3,
            )
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")

            # Resize to fit nicely in the panel
            qr_img = qr_img.resize((280, 280), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(qr_img)
            self.qr_photo = photo  # Prevent GC

            self.qr_label.config(image=photo, text="", bg="#ffffff", padx=10, pady=10)

        except Exception as e:
            self.qr_label.config(text=f"QR Error: {e}\n\nURL:\n{url}", fg="#ef4444")

    def copy_mobile_url(self):
        url = getattr(self, "mobile_url", "")
        if url:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.set_status(f"Copied to clipboard: {url}")
            messagebox.showinfo("Copied!", f"URL copied:\n{url}", parent=self.root)

    def open_mobile_in_browser(self):
        url = getattr(self, "mobile_url", "")
        if url:
            webbrowser.open(url)

    # =====================================================================
    # Category & Image Management Methods
    # =====================================================================

    def set_status(self, text):
        self.lbl_status.config(text=f"Status: {text}")

    def get_selected_category_name(self):
        selected = self.cat_tree.selection()
        if selected:
            return self.cat_tree.item(selected[0], "text")
        return None

    def get_selected_image_name(self):
        selected_indices = self.img_listbox.curselection()
        if selected_indices:
            return self.img_listbox.get(selected_indices[0]).strip()
        return None

    def refresh_all(self, keep_img_selection=None):
        manifest = self.sync_manifest()

        for item in self.cat_tree.get_children():
            self.cat_tree.delete(item)

        selected_cat = self.get_selected_category_name()
        reselect_item = None

        for cat_info in manifest:
            cat_name = cat_info["category"]
            img_count = len(cat_info["images"])
            item_id = self.cat_tree.insert("", tk.END, text=cat_name, values=(img_count,))
            if cat_name == selected_cat:
                reselect_item = item_id

        if reselect_item:
            self.cat_tree.selection_set(reselect_item)
            self.cat_tree.see(reselect_item)
            self.on_category_select(None, target_image=keep_img_selection)
        else:
            self.on_category_select(None)

        self.set_status("Manifests synced (categories.json & categories-data.js).")

    def on_category_select(self, event, target_image=None):
        cat_name = self.get_selected_category_name()
        self.img_listbox.delete(0, tk.END)
        self.clear_preview()

        if cat_name:
            self.lbl_selected_cat.config(text=f"🖼️ Images in '{cat_name}'")
            self.btn_upload.config(state=tk.NORMAL)
            self.btn_rename_img.config(state=tk.DISABLED)
            self.btn_delete_img.config(state=tk.DISABLED)

            cat_path = os.path.join(CATEGORIES_DIR, cat_name)
            if os.path.exists(cat_path):
                images = sorted([
                    f for f in os.listdir(cat_path)
                    if os.path.isfile(os.path.join(cat_path, f))
                    and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
                ])
                reselect_idx = None
                for idx, img in enumerate(images):
                    self.img_listbox.insert(tk.END, f"  {img}")
                    if target_image and img == target_image:
                        reselect_idx = idx

                if reselect_idx is not None:
                    self.img_listbox.selection_set(reselect_idx)
                    self.img_listbox.see(reselect_idx)
                    self.on_image_select(None)
        else:
            self.lbl_selected_cat.config(text="Select a Category")
            self.btn_upload.config(state=tk.DISABLED)
            self.btn_rename_img.config(state=tk.DISABLED)
            self.btn_delete_img.config(state=tk.DISABLED)

    def on_image_select(self, event):
        cat_name = self.get_selected_category_name()
        img_name = self.get_selected_image_name()

        if cat_name and img_name:
            self.btn_rename_img.config(state=tk.NORMAL)
            self.btn_delete_img.config(state=tk.NORMAL)
            img_path = os.path.join(CATEGORIES_DIR, cat_name, img_name)
            self.update_image_preview(img_path)
        else:
            self.btn_rename_img.config(state=tk.DISABLED)
            self.btn_delete_img.config(state=tk.DISABLED)
            self.clear_preview()

    def clear_preview(self):
        self.preview_lbl.config(image="", text="No image selected\n\nClick an image to preview", fg="#64748b")
        self.lbl_preview_name.config(text="Name: —")
        self.lbl_preview_dims.config(text="Resolution: —")
        self.lbl_preview_size.config(text="Size: —")
        self.lbl_preview_date.config(text="📅 Upload Date: —")
        self.current_preview_photo = None

    def update_image_preview(self, img_path):
        if not img_path or not os.path.exists(img_path):
            self.clear_preview()
            return

        cat_name = self.get_selected_category_name()
        file_name = os.path.basename(img_path)

        try:
            # Handle HEIC files for preview
            ext = os.path.splitext(img_path)[1].lower()
            if ext == ".heic" and HAS_HEIF:
                try:
                    heif_file = pillow_heif.read_heif(img_path)
                    img = Image.frombytes(
                        heif_file.mode,
                        heif_file.size,
                        heif_file.data,
                        "raw",
                        heif_file.mode,
                        heif_file.stride
                    )
                except Exception as e:
                    raise Exception(f"HEIC preview error: {e}")
            else:
                img = Image.open(img_path)

            with img as pil_img:
                orig_w, orig_h = pil_img.size
                img_format = pil_img.format or os.path.splitext(img_path)[1].upper().replace(".", "")
                max_w, max_h = 240, 180
                thumb = pil_img.copy()
                thumb.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(thumb)
                self.current_preview_photo = photo
                self.preview_lbl.config(image=photo, text="")

                file_size_bytes = os.path.getsize(img_path)
                if file_size_bytes < 1024:
                    size_str = f"{file_size_bytes} B"
                elif file_size_bytes < 1024 * 1024:
                    size_str = f"{file_size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB"

                img_date = self.metadata.get(cat_name, {}).get(file_name, {}).get("date", "—")
                self.lbl_preview_name.config(text=f"Name: {file_name}")
                self.lbl_preview_dims.config(text=f"Resolution: {orig_w} × {orig_h} px")
                self.lbl_preview_size.config(text=f"Size: {size_str} ({img_format})")
                self.lbl_preview_date.config(text=f"📅 Upload Date: {img_date}")

        except Exception as e:
            self.preview_lbl.config(image="", text=f"Preview Unavailable\n({str(e)})", fg="#ef4444")
            self.lbl_preview_name.config(text=f"Name: {os.path.basename(img_path)}")
            self.lbl_preview_dims.config(text="Resolution: —")
            self.lbl_preview_size.config(text="Size: —")
            self.lbl_preview_date.config(text="📅 Upload Date: —")
            self.current_preview_photo = None

    def rename_image(self):
        cat_name = self.get_selected_category_name()
        old_img_name = self.get_selected_image_name()

        if not cat_name or not old_img_name:
            messagebox.showwarning("Warning", "Please select an image to rename.", parent=self.root)
            return

        old_base, old_ext = os.path.splitext(old_img_name)
        new_name = simpledialog.askstring(
            "Edit Image Label",
            f"Enter new name for '{old_img_name}':",
            initialvalue=old_img_name,
            parent=self.root
        )

        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_img_name:
            return
        if not os.path.splitext(new_name)[1]:
            new_name += old_ext

        old_path = os.path.join(CATEGORIES_DIR, cat_name, old_img_name)
        new_path = os.path.join(CATEGORIES_DIR, cat_name, new_name)

        if os.path.exists(new_path):
            messagebox.showerror("Error", f"An image named '{new_name}' already exists!", parent=self.root)
            return

        try:
            os.rename(old_path, new_path)
            if cat_name in self.metadata and old_img_name in self.metadata[cat_name]:
                self.metadata[cat_name][new_name] = self.metadata[cat_name].pop(old_img_name)
                self.save_metadata()
            self.refresh_all(keep_img_selection=new_name)
            self.set_status(f"Renamed '{old_img_name}' → '{new_name}'.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rename image: {str(e)}", parent=self.root)

    def create_category(self):
        new_name = simpledialog.askstring("New Category", "Enter new category name:", parent=self.root)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            return

        cat_path = os.path.join(CATEGORIES_DIR, new_name)
        if os.path.exists(cat_path):
            messagebox.showerror("Error", f"Category '{new_name}' already exists!", parent=self.root)
            return

        try:
            os.makedirs(cat_path)
            if new_name not in self.metadata:
                self.metadata[new_name] = {}
                self.save_metadata()
            self.refresh_all()
            for item in self.cat_tree.get_children():
                if self.cat_tree.item(item, "text") == new_name:
                    self.cat_tree.selection_set(item)
                    break
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create category: {str(e)}", parent=self.root)

    def rename_category(self):
        old_name = self.get_selected_category_name()
        if not old_name:
            messagebox.showwarning("Warning", "Please select a category to rename.", parent=self.root)
            return

        new_name = simpledialog.askstring("Rename Category",
                                          f"New name for '{old_name}':",
                                          initialvalue=old_name, parent=self.root)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return

        old_path = os.path.join(CATEGORIES_DIR, old_name)
        new_path = os.path.join(CATEGORIES_DIR, new_name)
        if os.path.exists(new_path):
            messagebox.showerror("Error", f"Category '{new_name}' already exists!", parent=self.root)
            return

        try:
            os.rename(old_path, new_path)
            if old_name in self.metadata:
                self.metadata[new_name] = self.metadata.pop(old_name)
                self.save_metadata()
            self.refresh_all()
            for item in self.cat_tree.get_children():
                if self.cat_tree.item(item, "text") == new_name:
                    self.cat_tree.selection_set(item)
                    break
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rename category: {str(e)}", parent=self.root)

    def delete_category(self):
        cat_name = self.get_selected_category_name()
        if not cat_name:
            messagebox.showwarning("Warning", "Please select a category to delete.", parent=self.root)
            return

        confirm = messagebox.askyesno("Confirm Delete",
                                      f"Delete category '{cat_name}' and ALL its images?",
                                      parent=self.root)
        if not confirm:
            return

        cat_path = os.path.join(CATEGORIES_DIR, cat_name)
        try:
            shutil.rmtree(cat_path)
            if cat_name in self.metadata:
                self.metadata.pop(cat_name)
                self.save_metadata()
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete category: {str(e)}", parent=self.root)

    def upload_images(self):
        cat_name = self.get_selected_category_name()
        if not cat_name:
            messagebox.showwarning("Warning", "Please select a category first.", parent=self.root)
            return

        files = filedialog.askopenfilenames(
            title="Select Images to Upload",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.gif *.svg *.bmp *.heic"), ("All Files", "*.*")],
            parent=self.root
        )
        if not files:
            return

        target_dir = os.path.join(CATEGORIES_DIR, cat_name)
        copied_count = 0
        last_uploaded = None
        today_str = datetime.now().strftime("%Y/%m/%d")

        if cat_name not in self.metadata:
            self.metadata[cat_name] = {}

        for file_path in files:
            file_name = os.path.basename(file_path)
            
            # Check if HEIC and convert if possible
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".heic" and HAS_HEIF:
                try:
                    with open(file_path, "rb") as f:
                        heic_data = f.read()
                    jpeg_data = convert_heic_to_jpeg(heic_data)
                    if jpeg_data:
                        # Save as JPEG
                        file_name = os.path.splitext(file_name)[0] + ".jpg"
                        target_path = os.path.join(target_dir, file_name)
                        base, file_ext = os.path.splitext(file_name)
                        counter = 1
                        while os.path.exists(target_path):
                            target_path = os.path.join(target_dir, f"{base}_{counter}{file_ext}")
                            counter += 1
                        
                        with open(target_path, "wb") as f:
                            f.write(jpeg_data)
                        
                        dest_filename = os.path.basename(target_path)
                        self.metadata[cat_name][dest_filename] = {"date": today_str}
                        copied_count += 1
                        last_uploaded = dest_filename
                        continue
                except Exception as e:
                    print(f"Error converting HEIC {file_path}: {e}")
                    # Fall through to try copying as-is
            
            # Normal copy for non-HEIC or if conversion failed
            target_path = os.path.join(target_dir, file_name)
            base, ext = os.path.splitext(file_name)
            counter = 1
            while os.path.exists(target_path):
                target_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
                counter += 1

            try:
                shutil.copy2(file_path, target_path)
                dest_filename = os.path.basename(target_path)
                self.metadata[cat_name][dest_filename] = {"date": today_str}
                copied_count += 1
                last_uploaded = dest_filename
            except Exception as e:
                print(f"Error copying {file_path}: {e}")

        self.save_metadata()
        self.refresh_all(keep_img_selection=last_uploaded)
        messagebox.showinfo("Success", f"Uploaded {copied_count} image(s) to '{cat_name}' with date ({today_str}).", parent=self.root)

    def delete_images(self):
        cat_name = self.get_selected_category_name()
        img_name = self.get_selected_image_name()

        if not cat_name or not img_name:
            messagebox.showwarning("Warning", "Please select an image to delete.", parent=self.root)
            return

        confirm = messagebox.askyesno("Confirm Delete",
                                      f"Delete '{img_name}' from '{cat_name}'?",
                                      parent=self.root)
        if not confirm:
            return

        img_path = os.path.join(CATEGORIES_DIR, cat_name, img_name)
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
                if cat_name in self.metadata and img_name in self.metadata[cat_name]:
                    self.metadata[cat_name].pop(img_name)
                    self.save_metadata()
            except Exception as e:
                print(f"Error removing {img_path}: {e}")

        self.refresh_all()
        self.clear_preview()

    # =====================================================================
    # Gallery Web Server
    # =====================================================================

    def toggle_web_server(self):
        if not self.server_running:
            self.start_web_server()
        else:
            self.stop_web_server()

    def start_web_server(self):
        handler = http.server.SimpleHTTPRequestHandler

        class QuietHandler(handler):
            def log_message(self, format, *args):
                pass

        os.chdir(SCRIPT_DIR)

        try:
            self.httpd = socketserver.TCPServer(("", DEFAULT_PORT), QuietHandler)
            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()
            self.server_running = True
            self.btn_server.config(text=f"🛑 Stop Gallery Server (Port {DEFAULT_PORT})", style="Danger.TButton")
            self.set_status(f"Gallery server active at http://localhost:{DEFAULT_PORT}")
        except Exception as e:
            messagebox.showerror("Server Error", f"Failed to start server: {str(e)}", parent=self.root)

    def stop_web_server(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.server_running = False
            self.btn_server.config(text=f"🌐 Optional: Launch Server ({DEFAULT_PORT})", style="Secondary.TButton")
            self.set_status("Gallery server offline.")

    def open_webpage(self):
        if self.server_running:
            webbrowser.open(f"http://localhost:{DEFAULT_PORT}/index.html")
        else:
            index_path = os.path.join(SCRIPT_DIR, "index.html")
            webbrowser.open(f"file:///{index_path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = GalleryAdminApp(root)
    root.mainloop()