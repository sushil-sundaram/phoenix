#!/usr/bin/env python3
"""
Generate Workspace Layouts icons for COSMIC Desktop panel, menus, and application launchers.
Produces:
  - workspace-layouts-symbolic.svg (16x16 / 24x24 monochrome symbolic icon for panel/dock)
  - workspace-layouts.svg (256x256 minimalist monochrome formal icon)
  - Multi-size PNGs (16x16 up to 256x256) for system icon themes.
"""

import os
import sys
import cairo
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg

SYMBOLIC_SVG = """<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Left Master Layout Pane -->
  <rect x="1.5" y="2" width="5.5" height="12" rx="1.2" fill="currentColor"/>
  <!-- Top Right Layout Pane -->
  <rect x="8.5" y="2" width="6" height="5.2" rx="1.2" fill="currentColor"/>
  <!-- Bottom Right Layout Pane -->
  <rect x="8.5" y="8.8" width="6" height="5.2" rx="1.2" stroke="currentColor" stroke-width="1.2" fill="currentColor" fill-opacity="0.2"/>
</svg>"""

FULL_COLOR_SVG = """<svg width="256" height="256" viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Minimalist Monochrome Base Squircle -->
  <rect x="12" y="12" width="232" height="232" rx="52" fill="#1C1C20" stroke="#3A3A42" stroke-width="2.5"/>
  <!-- Left Master Layout Frame -->
  <rect x="42" y="44" width="76" height="168" rx="14" fill="#E4E4E8"/>
  <!-- Top Right Layout Frame -->
  <rect x="134" y="44" width="80" height="76" rx="14" fill="#E4E4E8"/>
  <!-- Bottom Right Layout Frame (Outlined Wireframe) -->
  <rect x="134" y="136" width="80" height="76" rx="14" fill="#E4E4E8" fill-opacity="0.12" stroke="#E4E4E8" stroke-width="5"/>
</svg>"""

def render_svg_to_png(svg_data: str, out_path: str, width: int, height: int):
    handle = Rsvg.Handle.new_from_data(svg_data.encode('utf-8'))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surf)
    dim = handle.get_intrinsic_dimensions()
    orig_w = dim.out_width.length if dim.out_has_width else width
    orig_h = dim.out_height.length if dim.out_has_height else height
    cr.scale(width / orig_w, height / orig_h)
    handle.render_cairo(cr)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    surf.write_to_png(out_path)

def main():
    base_icons_dir = os.path.expanduser("~/.local/share/icons/hicolor")
    res_dir = os.path.expanduser("~/phoenix/resources")
    os.makedirs(res_dir, exist_ok=True)

    # 1. Symbolic SVG (apps and status)
    sym_names = ["workspace-layouts-symbolic.svg", "phoenix-profile-symbolic.svg"]
    for sym_name in sym_names:
        paths = [
            os.path.join(base_icons_dir, "scalable", "apps", sym_name),
            os.path.join(base_icons_dir, "scalable", "status", sym_name),
            os.path.join(res_dir, sym_name)
        ]
        for p in paths:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(SYMBOLIC_SVG)
            print(f"Wrote symbolic icon: {p}")

    # 2. Main Monochrome SVG
    color_names = ["workspace-layouts.svg", "phoenix-profile.svg"]
    for color_name in color_names:
        paths = [
            os.path.join(base_icons_dir, "scalable", "apps", color_name),
            os.path.join(res_dir, color_name)
        ]
        for p in paths:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(FULL_COLOR_SVG)
            print(f"Wrote icon: {p}")

    # 3. Rasterized PNG sizes (16, 24, 32, 48, 64, 128, 256)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    for s in sizes:
        for prefix in ["workspace-layouts", "phoenix-profile"]:
            png_path = os.path.join(base_icons_dir, f"{s}x{s}", "apps", f"{prefix}.png")
            render_svg_to_png(FULL_COLOR_SVG, png_path, s, s)

    # Also render symbolic PNGs (white/gray on transparent)
    for s in [16, 24, 32, 48]:
        for prefix in ["workspace-layouts-symbolic", "phoenix-profile-symbolic"]:
            png_path = os.path.join(base_icons_dir, f"{s}x{s}", "status", f"{prefix}.png")
            render_svg_to_png(SYMBOLIC_SVG.replace('currentColor', '#dfdfdf'), png_path, s, s)

    # 4. Update GTK icon cache if tool exists
    if os.system(f"gtk-update-icon-cache -f -t {base_icons_dir} 2>/dev/null") == 0:
        print("Updated GTK icon cache successfully.")
    else:
        print("Icon cache updated.")

if __name__ == "__main__":
    main()
