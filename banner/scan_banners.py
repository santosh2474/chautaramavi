#!/usr/bin/env python3
"""
==========================================================================
Shree Chautara Secondary School - Banner Scanner & Config Updater
Website: www.chautaramavi.edu.np

Run this script anytime you add, rename, or delete files in 'banner/banner_img/'.
It automatically scans the directory and updates 'banner/banner-config.js'.
==========================================================================
"""

import os
import re

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.pdf', '.mp4', '.webm', '.ogg'}

def scan_and_update():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    img_dir = os.path.join(base_dir, "banner_img")
    config_file = os.path.join(base_dir, "banner-config.js")

    if not os.path.exists(img_dir):
        print(f"Error: Directory '{img_dir}' does not exist.")
        return

    found_files = []
    for item in sorted(os.listdir(img_dir)):
        ext = os.path.splitext(item)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            found_files.append(item)

    # Sort images first, then PDFs, then videos, keeping natural alphabetical order within each
    def sort_key(name):
        ext = os.path.splitext(name)[1].lower()
        type_priority = 0 if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif'} else (1 if ext == '.pdf' else 2)
        return (type_priority, name.lower())

    found_files.sort(key=sort_key)
    found_files = [f"banner/banner_img/{item}" for item in found_files]

    print(f"Found {len(found_files)} supported banner media files in banner/banner_img/:")
    for f in found_files:
        print(f"  - {f}")

    if not os.path.exists(config_file):
        print(f"Error: Configuration file '{config_file}' not found.")
        return

    with open(config_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Format media list
    js_media_items = ",\n".join([f'    "{item}"' for item in found_files])
    replacement = f"const bannerMedia = [\n{js_media_items}\n];"

    # Replace const bannerMedia = [...];
    new_content = re.sub(
        r"const bannerMedia\s*=\s*\[[\s\S]*?\];",
        replacement,
        content
    )

    with open(config_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"\nSuccessfully updated {config_file}!")

if __name__ == "__main__":
    scan_and_update()
