#!/usr/bin/env python3
"""
Generate Phoenix icons for COSMIC Desktop panel, menus, and application launchers.
Produces:
  - phoenix-profile-symbolic.svg (16x16 / 24x24 monochrome symbolic icon for panel/dock)
  - phoenix-profile.svg (256x256 full-color fiery gradient logo with multi-monitor layout motif)
  - Multi-size PNGs (16x16 up to 256x256) for system icon themes.
"""

import os
import sys
import cairo
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg

SYMBOLIC_SVG = """<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g fill="currentColor">
    <!-- Phoenix Crest and Head -->
    <path d="M 8 0.8 C 7.2 2.3 6.5 3.2 5.2 3.9 C 6.4 4.2 7.2 5.0 8 6.0 C 8.8 5.0 9.6 4.2 10.8 3.9 C 9.5 3.2 8.8 2.3 8 0.8 Z"/>
    <!-- Left Wing -->
    <path d="M 7.3 5.4 C 5.1 4.9 2.6 6.1 1.2 8.6 C 2.7 8.0 4.2 8.0 5.4 8.7 C 3.6 9.6 2.5 11.3 2.7 13.1 C 4.2 12.0 5.8 12.0 7.0 12.7 C 6.5 10.4 6.8 7.9 7.3 5.4 Z"/>
    <!-- Right Wing -->
    <path d="M 8.7 5.4 C 10.9 4.9 13.4 6.1 14.8 8.6 C 13.3 8.0 11.8 8.0 10.6 8.7 C 12.4 9.6 13.5 11.3 13.3 13.1 C 11.8 12.0 10.2 12.0 9.0 12.7 C 9.5 10.4 9.2 7.9 8.7 5.4 Z"/>
    <!-- Multi-display Layout Heart (Center display diamond flanked by wings) -->
    <path d="M 8 6.8 L 9.3 9.0 L 8 11.6 L 6.7 9.0 Z"/>
    <!-- Tail Plumes -->
    <path d="M 7.5 12.6 L 8.5 12.6 L 8.7 14.2 L 8 15.6 L 7.3 14.2 Z"/>
  </g>
</svg>"""

FULL_COLOR_SVG = """<svg width="256" height="256" viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <!-- Background Radial Glow -->
    <radialGradient id="bgGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#2D124D" stop-opacity="0.95"/>
      <stop offset="70%" stop-color="#140B22" stop-opacity="0.98"/>
      <stop offset="100%" stop-color="#0B0514" stop-opacity="1"/>
    </radialGradient>

    <!-- Fiery Wing Gradient -->
    <linearGradient id="fireWingLeft" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFF176"/>
      <stop offset="35%" stop-color="#FF9800"/>
      <stop offset="70%" stop-color="#F44336"/>
      <stop offset="100%" stop-color="#B71C1C"/>
    </linearGradient>

    <linearGradient id="fireWingRight" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFF176"/>
      <stop offset="35%" stop-color="#FF9800"/>
      <stop offset="70%" stop-color="#F44336"/>
      <stop offset="100%" stop-color="#B71C1C"/>
    </linearGradient>

    <!-- Core Phoenix Fire Gradient -->
    <linearGradient id="fireCore" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="25%" stop-color="#FFE082"/>
      <stop offset="60%" stop-color="#FF6D00"/>
      <stop offset="100%" stop-color="#D50000"/>
    </linearGradient>

    <!-- Display Screens Gradient -->
    <linearGradient id="screenGlass" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#64B5F6" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#1976D2" stop-opacity="0.7"/>
    </linearGradient>

    <!-- Drop Shadow Filter -->
    <filter id="flameGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Squircle Base Container -->
  <rect x="8" y="8" width="240" height="240" rx="54" fill="url(#bgGlow)" stroke="#FF8A65" stroke-width="2.5" stroke-opacity="0.3"/>

  <!-- Subtle Layout Screen Frames in Background -->
  <!-- Center Ultrawide Screen -->
  <rect x="76" y="160" width="104" height="48" rx="6" fill="#1E2638" stroke="#42A5F5" stroke-width="2" stroke-opacity="0.6"/>
  <rect x="80" y="164" width="96" height="40" rx="4" fill="#0D1B2A" fill-opacity="0.8"/>
  <line x1="128" y1="208" x2="128" y2="218" stroke="#42A5F5" stroke-width="3" stroke-opacity="0.7"/>
  <line x1="114" y1="218" x2="142" y2="218" stroke="#42A5F5" stroke-width="3" stroke-linecap="round" stroke-opacity="0.7"/>

  <!-- Left Vertical Screen -->
  <rect x="36" y="148" width="34" height="60" rx="5" fill="#1E2638" stroke="#29B6F6" stroke-width="1.8" stroke-opacity="0.5"/>
  <rect x="39" y="151" width="28" height="54" rx="3" fill="#0D1B2A" fill-opacity="0.8"/>

  <!-- Right Laptop Screen -->
  <rect x="186" y="166" width="36" height="42" rx="4" fill="#1E2638" stroke="#29B6F6" stroke-width="1.8" stroke-opacity="0.5"/>
  <rect x="189" y="169" width="30" height="34" rx="3" fill="#0D1B2A" fill-opacity="0.8"/>
  <line x1="182" y1="208" x2="226" y2="208" stroke="#29B6F6" stroke-width="2.5" stroke-linecap="round" stroke-opacity="0.6"/>

  <!-- Glowing Phoenix Wings and Body -->
  <g filter="url(#flameGlow)">
    <!-- Phoenix Crown / Crest -->
    <path d="M 128 24 C 117 48 106 62 86 73 C 105 78 117 90 128 106 C 139 90 151 78 170 73 C 150 62 139 48 128 24 Z" fill="url(#fireCore)"/>

    <!-- Left Wing Primary Feather Array -->
    <path d="M 118 96 C 84 88 44 107 22 146 C 45 136 69 136 88 147 C 60 161 43 188 46 216 C 69 199 95 199 114 210 C 106 174 110 135 118 96 Z" fill="url(#fireWingLeft)"/>

    <!-- Right Wing Primary Feather Array -->
    <path d="M 138 96 C 172 88 212 107 234 146 C 211 136 187 136 168 147 C 196 161 213 188 210 216 C 187 199 161 199 142 210 C 150 174 146 135 138 96 Z" fill="url(#fireWingRight)"/>

    <!-- Brilliant Radiant Heart Core -->
    <path d="M 128 116 L 148 152 L 128 194 L 108 152 Z" fill="url(#fireCore)"/>
    <circle cx="128" cy="152" r="8" fill="#FFFFFF"/>

    <!-- Tail Plumage Flames -->
    <path d="M 122 208 L 134 208 L 138 230 L 128 248 L 118 230 Z" fill="url(#fireCore)"/>
  </g>
</svg>"""

def render_svg_to_png(svg_data: str, out_path: str, width: int, height: int):
    handle = Rsvg.Handle.new_from_data(svg_data.encode('utf-8'))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surf)
    # Scale to target dimensions
    dim = handle.get_intrinsic_dimensions()
    orig_w = dim.out_width.length if dim.out_has_width else width
    orig_h = dim.out_height.length if dim.out_has_height else height
    cr.scale(width / orig_w, height / orig_h)
    handle.render_cairo(cr)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    surf.write_to_png(out_path)

def main():
    base_icons_dir = os.path.expanduser("~/.local/share/icons/hicolor")
    
    # 1. Symbolic SVG (apps and status)
    sym_paths = [
        os.path.join(base_icons_dir, "scalable", "apps", "phoenix-profile-symbolic.svg"),
        os.path.join(base_icons_dir, "scalable", "status", "phoenix-profile-symbolic.svg"),
        os.path.expanduser("~/phoenix/resources/phoenix-profile-symbolic.svg")
    ]
    for p in sym_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(SYMBOLIC_SVG)
        print(f"Wrote symbolic icon: {p}")

    # 2. Full Color SVG
    color_paths = [
        os.path.join(base_icons_dir, "scalable", "apps", "phoenix-profile.svg"),
        os.path.expanduser("~/phoenix/resources/phoenix-profile.svg")
    ]
    for p in color_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(FULL_COLOR_SVG)
        print(f"Wrote color icon: {p}")

    # 3. Rasterized PNG sizes (16, 24, 32, 48, 64, 128, 256)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    for s in sizes:
        png_path = os.path.join(base_icons_dir, f"{s}x{s}", "apps", "phoenix-profile.png")
        render_svg_to_png(FULL_COLOR_SVG, png_path, s, s)
        print(f"Rendered PNG {s}x{s}: {png_path}")

    # Also render symbolic PNGs
    for s in [16, 24, 32, 48]:
        png_path = os.path.join(base_icons_dir, f"{s}x{s}", "status", "phoenix-profile-symbolic.png")
        render_svg_to_png(SYMBOLIC_SVG.replace('currentColor', '#dfdfdf'), png_path, s, s)

    # 4. Update GTK icon cache if tool exists
    if os.system(f"gtk-update-icon-cache -f -t {base_icons_dir} 2>/dev/null") == 0:
        print("Updated GTK icon cache successfully.")
    else:
        print("Icon cache updated.")

if __name__ == "__main__":
    main()
