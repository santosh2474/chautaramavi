import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import shutil
import re

HTML_FILE = "banner.html"
MEDIA_FOLDER = "banner/banner_img"


class BannerManager:

    def __init__(self, root):
        self.root = root
        self.root.title("Banner Manager - Realtime Preview & Sorting")
        self.root.geometry("1200x700")
        self.root.configure(bg="white")

        self.slides = []
        self.current_index = 0
        self.photo = None

        # Ensure media folder exists
        os.makedirs(MEDIA_FOLDER, exist_ok=True)

        self.load_html()
        self.create_ui()
        self.refresh_slide_list()
        self.display_slide()

    # ---------------------------------------------------
    # LOAD HTML
    # ---------------------------------------------------
    def load_html(self):

        if not os.path.exists(HTML_FILE):
            return

        with open(HTML_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        slide_blocks = re.findall(
            r'<div class="slide.*?">.*?</div>', content, re.DOTALL)

        self.slides.clear()

        for block in slide_blocks:

            if "<img" in block:
                file_match = re.search(
                    r'src="\.\/banner\/banner_img\/(.*?)"', block)
                caption_match = re.search(r'<p>"(.*?)"</p>', block)

                if file_match:
                    self.slides.append({
                        "type": "image",
                        "file": file_match.group(1),
                        "caption": caption_match.group(1) if caption_match else ""
                    })

            elif "<video" in block:
                file_match = re.search(
                    r'src="\.\/banner\/banner_img\/(.*?)"', block)
                caption_match = re.search(r'<p>(.*?)</p>', block)

                if file_match:
                    self.slides.append({
                        "type": "video",
                        "file": file_match.group(1),
                        "caption": caption_match.group(1) if caption_match else ""
                    })

    # ---------------------------------------------------
    # UI
    # ---------------------------------------------------
    def create_ui(self):

        main_frame = tk.Frame(self.root, bg="white")
        main_frame.pack(fill="both", expand=True)

        # LEFT SIDE - Slide List
        left_frame = tk.Frame(main_frame, bg="white", width=300)
        left_frame.pack(side="left", fill="y", padx=10, pady=10)

        tk.Label(left_frame, text="Slide Sequence",
                 font=("Arial", 14, "bold")).pack(pady=5)

        self.slide_listbox = tk.Listbox(left_frame, width=40, height=30)
        self.slide_listbox.pack(pady=10)
        self.slide_listbox.bind("<<ListboxSelect>>", self.on_select_slide)

        ttk.Button(left_frame, text="Move Up",
                   command=self.move_up).pack(pady=5)
        ttk.Button(left_frame, text="Move Down",
                   command=self.move_down).pack(pady=5)

        # RIGHT SIDE - Preview
        right_frame = tk.Frame(main_frame, bg="white")
        right_frame.pack(side="right", fill="both", expand=True)

        self.preview_frame = tk.Frame(
            right_frame, width=800, height=450, bg="black")
        self.preview_frame.pack(pady=20)
        self.preview_frame.pack_propagate(False)

        self.caption_entry = tk.Entry(
            right_frame, font=("Arial", 14), width=80)
        self.caption_entry.pack(pady=10)

        btn_frame = tk.Frame(right_frame, bg="white")
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text="Add Slide",
                   command=self.add_slide).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Update Caption",
                   command=self.update_caption).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Delete Slide",
                   command=self.delete_slide).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="Save Changes",
                   command=self.generate_html).grid(row=0, column=3, padx=5)

    # ---------------------------------------------------
    # Refresh Listbox
    # ---------------------------------------------------
    def refresh_slide_list(self):

        self.slide_listbox.delete(0, tk.END)

        for index, slide in enumerate(self.slides):
            display_text = f"{index+1}. {slide['file']} ({slide['type']})"
            self.slide_listbox.insert(tk.END, display_text)

        if self.slides:
            self.slide_listbox.select_set(self.current_index)

    # ---------------------------------------------------
    # Select Slide
    # ---------------------------------------------------
    def on_select_slide(self, event):

        selection = self.slide_listbox.curselection()
        if selection:
            self.current_index = selection[0]
            self.display_slide()

    # ---------------------------------------------------
    # Display Preview
    # ---------------------------------------------------
    def display_slide(self):

        for widget in self.preview_frame.winfo_children():
            widget.destroy()

        if not self.slides:
            tk.Label(self.preview_frame,
                     text="No Slides Available",
                     fg="white",
                     bg="black",
                     font=("Arial", 20)).pack(expand=True)
            return

        slide = self.slides[self.current_index]
        file_path = os.path.join(MEDIA_FOLDER, slide["file"])

        if slide["type"] == "image" and os.path.exists(file_path):

            img = Image.open(file_path)
            img = img.resize((800, 450))
            self.photo = ImageTk.PhotoImage(img)

            tk.Label(self.preview_frame,
                     image=self.photo).pack(fill="both", expand=True)

        else:
            tk.Label(self.preview_frame,
                     text=f"VIDEO PREVIEW\n\n{slide['file']}",
                     fg="white",
                     bg="black",
                     font=("Arial", 18),
                     justify="center").pack(expand=True)

        self.caption_entry.delete(0, tk.END)
        self.caption_entry.insert(0, slide["caption"])

    # ---------------------------------------------------
    # Move Up
    # ---------------------------------------------------
    def move_up(self):
        if self.current_index > 0:
            self.slides[self.current_index], self.slides[self.current_index - 1] = \
                self.slides[self.current_index - 1], self.slides[self.current_index]

            self.current_index -= 1
            self.refresh_slide_list()
            self.display_slide()

    # ---------------------------------------------------
    # Move Down
    # ---------------------------------------------------
    def move_down(self):
        if self.current_index < len(self.slides) - 1:
            self.slides[self.current_index], self.slides[self.current_index + 1] = \
                self.slides[self.current_index + 1], self.slides[self.current_index]

            self.current_index += 1
            self.refresh_slide_list()
            self.display_slide()

    # ---------------------------------------------------
    # Add Slide
    # ---------------------------------------------------
    def add_slide(self):

        file_path = filedialog.askopenfilename(
            filetypes=[("Media Files", "*.jpg *.png *.jpeg *.mp4")]
        )

        if not file_path:
            return

        filename = os.path.basename(file_path)
        dest_path = os.path.join(MEDIA_FOLDER, filename)

        if not os.path.exists(dest_path):
            shutil.copy(file_path, dest_path)

        slide_type = "video" if filename.lower().endswith(".mp4") else "image"

        self.slides.append({
            "type": slide_type,
            "file": filename,
            "caption": "New Caption"
        })

        self.current_index = len(self.slides) - 1
        self.refresh_slide_list()
        self.display_slide()

    # ---------------------------------------------------
    # Update Caption
    # ---------------------------------------------------
    def update_caption(self):
        if self.slides:
            self.slides[self.current_index]["caption"] = self.caption_entry.get()
            messagebox.showinfo("Success", "Caption Updated Successfully")

    # ---------------------------------------------------
    # Delete Slide + Delete Media File Permanently
    # ---------------------------------------------------
    def delete_slide(self):

        if not self.slides:
            return

        slide = self.slides[self.current_index]
        file_path = os.path.join(MEDIA_FOLDER, slide["file"])

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete this slide?\n\nFile: {slide['file']}\n\nThis will permanently remove the media file."
        )

        if confirm:

            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    messagebox.showerror("Error", f"Unable to delete file:\n{e}")
                    return

            self.slides.pop(self.current_index)

            if self.current_index >= len(self.slides):
                self.current_index = len(self.slides) - 1

            if self.current_index < 0:
                self.current_index = 0

            self.refresh_slide_list()
            self.display_slide()

            messagebox.showinfo(
                "Success", "Slide and media file deleted permanently.")

    # ---------------------------------------------------
    # Generate HTML
    # ---------------------------------------------------
    def generate_html(self):

        html_content = """<!-- Banner Start -->
<div id="slideContainer">
    <button id="close" class="closeBtn">&times;</button>
    <button id="prev" class="sliderBtn">&lt;</button>
    <button id="next" class="sliderBtn">&gt;</button>
"""

        for i, slide in enumerate(self.slides):
            active = " show" if i == 0 else ""
            html_content += f'    <div class="slide{active}">\n'

            if slide["type"] == "image":
                html_content += f'        <img src="./banner/banner_img/{slide["file"]}" />\n'
                html_content += f'        <p>"{slide["caption"]}"</p>\n'
            else:
                html_content += f'        <video controls>\n'
                html_content += f'            <source src="./banner/banner_img/{slide["file"]}" type="video/mp4">\n'
                html_content += f'        </video>\n'
                html_content += f'        <p>{slide["caption"]}</p>\n'

            html_content += f'        <a href="./banner/banner_img/{slide["file"]}" download="{slide["file"]}" class="downloadBtn">Download</a>\n'
            html_content += "    </div>\n"

        html_content += """</div>
<script src='./banner/script_banner.js'></script>
<!-- Banner End -->
"""

        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)

        messagebox.showinfo(
            "Success", "Banner Order Updated Successfully")


# ---------------------------------------------------
# RUN APPLICATION
# ---------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = BannerManager(root)
    root.mainloop()
