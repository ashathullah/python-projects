"""ROI Placement Utility

Interactive GUI to create/edit named ROI rectangles with per-ROI colors.
ROIs are stored as normalized coordinates (x1, y1, x2, y2) in [0..1].

Usage:
  python roi_tool.py --images ./test_images --out rois.json

Controls:
  - Add ROI: enter name, pick color (optional), click "Add" then draw box (click-drag)
  - Select ROI: click ROI in list; it becomes active for editing
  - Move ROI: drag inside the active rectangle
  - Resize ROI: drag a corner handle of the active rectangle
  - Delete ROI: select in list then click "Delete"
  - Navigate images: Prev/Next
  - Save: writes normalized ROIs to JSON

This tool keeps one shared ROI mapping applied across all images.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageTk
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow is required. Install with: pip install pillow\n"
        f"Import error: {exc}"
    )

import tkinter as tk
from tkinter import colorchooser, messagebox


NormROI = Tuple[float, float, float, float]


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def normalize_roi(x1: float, y1: float, x2: float, y2: float) -> NormROI:
    x1c, x2c = sorted((clamp01(x1), clamp01(x2)))
    y1c, y2c = sorted((clamp01(y1), clamp01(y2)))
    # Avoid degenerate boxes
    if abs(x2c - x1c) < 1e-6:
        x2c = clamp01(x1c + 1e-6)
    if abs(y2c - y1c) < 1e-6:
        y2c = clamp01(y1c + 1e-6)
    return (x1c, y1c, x2c, y2c)


def hex_color_or_default(color: Optional[str], default: str = "#00FF00") -> str:
    if not color:
        return default
    c = color.strip()
    if c.startswith("#") and len(c) in (4, 7):
        return c
    return default


@dataclass
class ROI:
    name: str
    color: str
    norm: NormROI


class ROIEditorApp(tk.Tk):
    def __init__(
        self,
        image_paths: List[Path],
        out_path: Path,
        initial_rois: Dict[str, NormROI],
    ) -> None:
        super().__init__()
        self.title("ROI Placement Utility")
        self.geometry("1200x800")

        self.image_paths = image_paths
        self.out_path = out_path

        # ROI name -> ROI
        self.rois: Dict[str, ROI] = {}
        # Preserve insert order for list UI
        self.roi_order: List[str] = []

        for name, norm in initial_rois.items():
            self._upsert_roi(name=name, color=self._default_color_for_index(len(self.roi_order)), norm=norm)

        self.current_image_index = 0
        self.current_image: Optional[Image.Image] = None
        self.current_photo: Optional[ImageTk.PhotoImage] = None

        # Canvas transform state
        self.display_scale = 1.0
        self.display_offset = (0, 0)  # x, y
        self.display_size = (1, 1)  # w, h

        # Active ROI editing
        self.active_roi_name: Optional[str] = None
        self._drag_mode: Optional[str] = None  # None|"draw"|"move"|"resize"
        self._drag_start_canvas: Optional[Tuple[int, int]] = None
        self._drag_start_norm: Optional[NormROI] = None
        self._resize_handle: Optional[str] = None  # "nw"|"ne"|"sw"|"se"

        # Active ROI coordinate controls
        self._coord_vars: Dict[str, tk.StringVar] = {}
        self._coord_spins: Dict[str, tk.Spinbox] = {}
        self._coord_update_job: Optional[str] = None
        self._updating_coord_vars = False

        self._build_ui()
        self._load_image(self.current_image_index)
        self._redraw()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        # Left: canvas
        self.canvas = tk.Canvas(self, bg="#111111", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Right: controls
        side = tk.Frame(self)
        side.grid(row=0, column=1, sticky="ns")
        side.rowconfigure(4, weight=1)

        nav = tk.Frame(side)
        nav.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        nav.columnconfigure(1, weight=1)

        self.prev_btn = tk.Button(nav, text="Prev", command=self._prev_image)
        self.prev_btn.grid(row=0, column=0, sticky="ew")

        self.image_label = tk.Label(nav, text="", anchor="w")
        self.image_label.grid(row=0, column=1, padx=8, sticky="ew")

        self.next_btn = tk.Button(nav, text="Next", command=self._next_image)
        self.next_btn.grid(row=0, column=2, sticky="ew")

        # ROI add controls
        add_box = tk.LabelFrame(side, text="Add ROI")
        add_box.grid(row=1, column=0, sticky="ew", padx=10, pady=6)
        add_box.columnconfigure(1, weight=1)

        tk.Label(add_box, text="Name").grid(row=0, column=0, sticky="w")
        self.roi_name_var = tk.StringVar(value="")
        self.roi_name_entry = tk.Entry(add_box, textvariable=self.roi_name_var)
        self.roi_name_entry.grid(row=0, column=1, sticky="ew")

        tk.Label(add_box, text="Color").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.roi_color_var = tk.StringVar(value="#00FF00")
        self.color_btn = tk.Button(add_box, text="Pick…", command=self._pick_color)
        self.color_btn.grid(row=1, column=1, sticky="w", pady=(6, 0))

        self.add_btn = tk.Button(add_box, text="Add (then draw)", command=self._add_roi)
        self.add_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        # ROI list
        list_box = tk.LabelFrame(side, text="ROIs")
        list_box.grid(row=2, column=0, sticky="nsew", padx=10, pady=6)
        list_box.rowconfigure(0, weight=1)
        list_box.columnconfigure(0, weight=1)

        self.roi_list = tk.Listbox(list_box, height=12)
        self.roi_list.grid(row=0, column=0, sticky="nsew")
        self.roi_list.bind("<<ListboxSelect>>", self._on_roi_select)

        btn_row = tk.Frame(list_box)
        btn_row.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.delete_btn = tk.Button(btn_row, text="Delete", command=self._delete_roi)
        self.delete_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.rename_btn = tk.Button(btn_row, text="Rename", command=self._rename_roi)
        self.rename_btn.grid(row=0, column=1, sticky="ew")

        # Active ROI details
        details = tk.LabelFrame(side, text="Active ROI")
        details.grid(row=3, column=0, sticky="ew", padx=10, pady=6)
        details.columnconfigure(1, weight=1)

        self.active_name_label = tk.Label(details, text="(none)", anchor="w")
        self.active_name_label.grid(row=0, column=0, columnspan=2, sticky="ew")

        tk.Label(details, text="Coordinates (0.0000–1.0000)").grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        coords = tk.Frame(details)
        coords.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        for col in range(4):
            coords.columnconfigure(col, weight=1)

        for key, col in [("x1", 0), ("y1", 1), ("x2", 2), ("y2", 3)]:
            tk.Label(coords, text=key).grid(row=0, column=col, sticky="w")
            var = tk.StringVar(value="")
            spin = tk.Spinbox(
                coords,
                from_=0.0,
                to=1.0,
                increment=0.001,
                width=8,
                textvariable=var,
                command=self._schedule_apply_coords_from_spins,
            )
            spin.grid(row=1, column=col, sticky="ew", padx=(0, 6 if col < 3 else 0))
            spin.bind("<KeyRelease>", lambda _e: self._schedule_apply_coords_from_spins())
            # Ensure arrow keys behave like numeric stepper.
            spin.bind("<Up>", lambda _e, s=spin: (s.invoke("buttonup"), "break")[1])
            spin.bind("<Down>", lambda _e, s=spin: (s.invoke("buttondown"), "break")[1])
            spin.bind("<FocusOut>", lambda _e: self._schedule_apply_coords_from_spins())
            self._coord_vars[key] = var
            self._coord_spins[key] = spin

        hint = tk.Label(details, text="Tip: click a field and use ↑/↓ to adjust.", anchor="w")
        hint.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        self.set_color_btn = tk.Button(details, text="Set color", command=self._set_active_color)
        self.set_color_btn.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # Save/Load
        io_box = tk.LabelFrame(side, text="Save / Load")
        io_box.grid(row=5, column=0, sticky="ew", padx=10, pady=(6, 10))
        io_box.columnconfigure(0, weight=1)

        self.save_btn = tk.Button(io_box, text=f"Save → {self.out_path.name}", command=self._save)
        self.save_btn.grid(row=0, column=0, sticky="ew")

        self.load_btn = tk.Button(io_box, text="Load from JSON", command=self._load_json)
        self.load_btn.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self.export_btn = tk.Button(io_box, text="Export Python snippet", command=self._export_python)
        self.export_btn.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        # Canvas bindings
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Key bindings
        self.bind("<Escape>", lambda _e: self._cancel_drag())
        self.bind("<Delete>", lambda _e: self._delete_roi())

        self._refresh_roi_list()

    # ---------------- Images ----------------

    def _load_image(self, index: int) -> None:
        index = max(0, min(len(self.image_paths) - 1, index))
        self.current_image_index = index
        img_path = self.image_paths[index]
        self.current_image = Image.open(img_path).convert("RGB")
        self.image_label.configure(text=f"{index+1}/{len(self.image_paths)}: {img_path.name}")

    def _prev_image(self) -> None:
        if self.current_image_index > 0:
            self._load_image(self.current_image_index - 1)
            self._redraw()

    def _next_image(self) -> None:
        if self.current_image_index < len(self.image_paths) - 1:
            self._load_image(self.current_image_index + 1)
            self._redraw()

    # ---------------- ROI Data ----------------

    def _default_color_for_index(self, idx: int) -> str:
        palette = [
            "#00FF00", "#FF0000", "#00B0FF", "#FFB300", "#AA00FF", "#00C853", "#FF1744", "#2979FF"
        ]
        return palette[idx % len(palette)]

    def _upsert_roi(self, name: str, color: str, norm: NormROI) -> None:
        color = hex_color_or_default(color, default=self._default_color_for_index(len(self.roi_order)))
        norm = normalize_roi(*norm)
        if name in self.rois:
            self.rois[name].color = color
            self.rois[name].norm = norm
        else:
            self.rois[name] = ROI(name=name, color=color, norm=norm)
            self.roi_order.append(name)

    def _refresh_roi_list(self) -> None:
        self.roi_list.delete(0, tk.END)
        for name in self.roi_order:
            roi = self.rois.get(name)
            if roi:
                self.roi_list.insert(tk.END, f"{roi.name}  ({roi.color})")

        if self.active_roi_name:
            try:
                idx = self.roi_order.index(self.active_roi_name)
                self.roi_list.selection_clear(0, tk.END)
                self.roi_list.selection_set(idx)
                self.roi_list.see(idx)
            except ValueError:
                pass

    def _set_active_roi(self, name: Optional[str]) -> None:
        self.active_roi_name = name
        if not name or name not in self.rois:
            self.active_name_label.configure(text="(none)")
            self._set_coord_vars(None)
            return
        roi = self.rois[name]
        self.active_name_label.configure(text=f"{roi.name}  color={roi.color}")
        self._set_coord_vars(roi.norm)

    # ---------------- Canvas Geometry ----------------

    def _compute_display_transform(self) -> None:
        if not self.current_image:
            return
        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        img_w, img_h = self.current_image.size

        scale = min(canvas_w / img_w, canvas_h / img_h)
        # Tk can report very small sizes during initial layout; never allow 0-sized images.
        disp_w = max(1, int(round(img_w * scale)))
        disp_h = max(1, int(round(img_h * scale)))
        off_x = max(0, (canvas_w - disp_w) // 2)
        off_y = max(0, (canvas_h - disp_h) // 2)

        self.display_scale = scale
        self.display_offset = (off_x, off_y)
        self.display_size = (disp_w, disp_h)

    def _canvas_to_norm(self, cx: float, cy: float) -> Tuple[float, float]:
        off_x, off_y = self.display_offset
        disp_w, disp_h = self.display_size
        x = (cx - off_x) / max(1, disp_w)
        y = (cy - off_y) / max(1, disp_h)
        return (clamp01(x), clamp01(y))

    def _norm_to_canvas(self, nx: float, ny: float) -> Tuple[float, float]:
        off_x, off_y = self.display_offset
        disp_w, disp_h = self.display_size
        cx = off_x + nx * disp_w
        cy = off_y + ny * disp_h
        return (cx, cy)

    # ---------------- Rendering ----------------

    def _redraw(self) -> None:
        if not self.current_image:
            return
        self._compute_display_transform()
        self.canvas.delete("all")

        disp_w, disp_h = self.display_size
        disp_w = max(1, int(disp_w))
        disp_h = max(1, int(disp_h))

        try:
            resized = self.current_image.resize((disp_w, disp_h))
        except ValueError:
            # Canvas may not be laid out yet; retry shortly.
            self.after(30, self._redraw)
            return
        self.current_photo = ImageTk.PhotoImage(resized)
        off_x, off_y = self.display_offset
        self.canvas.create_image(off_x, off_y, image=self.current_photo, anchor="nw")

        # Draw ROIs
        for name in self.roi_order:
            roi = self.rois.get(name)
            if not roi:
                continue
            x1, y1, x2, y2 = roi.norm
            cx1, cy1 = self._norm_to_canvas(x1, y1)
            cx2, cy2 = self._norm_to_canvas(x2, y2)

            width = 3 if name == self.active_roi_name else 2
            self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=roi.color, width=width)
            self.canvas.create_text(
                cx1 + 6,
                cy1 + 10,
                text=name,
                anchor="w",
                fill=roi.color,
                font=("Segoe UI", 10, "bold"),
            )

            # Active handles
            if name == self.active_roi_name:
                self._draw_handles(cx1, cy1, cx2, cy2, roi.color)

    def _draw_handles(self, cx1: float, cy1: float, cx2: float, cy2: float, color: str) -> None:
        size = 6
        for hx, hy in [(cx1, cy1), (cx2, cy1), (cx1, cy2), (cx2, cy2)]:
            self.canvas.create_rectangle(hx - size, hy - size, hx + size, hy + size, outline=color, width=2)

    # ---------------- ROI Manipulation ----------------

    def _pick_color(self) -> None:
        color = colorchooser.askcolor(title="Pick ROI color")
        if color and color[1]:
            self.roi_color_var.set(color[1])

    def _add_roi(self) -> None:
        name = self.roi_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Enter a ROI name.")
            return
        if name in self.rois:
            messagebox.showwarning("Exists", f"ROI '{name}' already exists.")
            return
        color = hex_color_or_default(self.roi_color_var.get().strip(), default=self._default_color_for_index(len(self.roi_order)))
        self._upsert_roi(name=name, color=color, norm=(0.1, 0.1, 0.2, 0.2))
        self._set_active_roi(name)
        self._refresh_roi_list()
        self._redraw()
        messagebox.showinfo("Draw", "Now click-drag on the image to draw this ROI.")

    def _delete_roi(self) -> None:
        name = self.active_roi_name
        if not name:
            return
        if messagebox.askyesno("Delete ROI", f"Delete ROI '{name}'?"):
            self.rois.pop(name, None)
            self.roi_order = [n for n in self.roi_order if n != name]
            self._set_active_roi(None)
            self._refresh_roi_list()
            self._redraw()

    def _rename_roi(self) -> None:
        name = self.active_roi_name
        if not name:
            return
        new_name = self.roi_name_var.get().strip()
        if not new_name:
            messagebox.showwarning("Missing name", "Enter new name in Name field.")
            return
        if new_name in self.rois and new_name != name:
            messagebox.showwarning("Exists", f"ROI '{new_name}' already exists.")
            return
        roi = self.rois.pop(name)
        roi.name = new_name
        self.rois[new_name] = roi
        self.roi_order = [new_name if n == name else n for n in self.roi_order]
        self._set_active_roi(new_name)
        self._refresh_roi_list()
        self._redraw()

    def _on_roi_select(self, _event) -> None:
        sel = self.roi_list.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self.roi_order):
            return
        name = self.roi_order[idx]
        self._set_active_roi(name)
        self._refresh_roi_list()
        self._redraw()

    def _set_coord_vars(self, norm: Optional[NormROI]) -> None:
        # Avoid triggering apply during programmatic updates.
        self._updating_coord_vars = True
        try:
            if norm is None:
                for key in ("x1", "y1", "x2", "y2"):
                    if key in self._coord_vars:
                        self._coord_vars[key].set("")
                return
            x1, y1, x2, y2 = norm
            vals = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            for key, v in vals.items():
                if key in self._coord_vars:
                    self._coord_vars[key].set(f"{v:.4f}")
        finally:
            self._updating_coord_vars = False

    def _schedule_apply_coords_from_spins(self) -> None:
        if self._updating_coord_vars:
            return
        if self._coord_update_job is not None:
            try:
                self.after_cancel(self._coord_update_job)
            except Exception:
                pass
        self._coord_update_job = self.after(30, self._apply_coords_from_spins)

    def _apply_coords_from_spins(self) -> None:
        self._coord_update_job = None
        name = self.active_roi_name
        if not name or name not in self.rois:
            return
        try:
            x1 = float(self._coord_vars["x1"].get())
            y1 = float(self._coord_vars["y1"].get())
            x2 = float(self._coord_vars["x2"].get())
            y2 = float(self._coord_vars["y2"].get())
        except Exception:
            return
        norm = normalize_roi(x1, y1, x2, y2)
        self.rois[name].norm = norm
        self._set_coord_vars(norm)
        self._redraw()

    def _set_active_color(self) -> None:
        name = self.active_roi_name
        if not name or name not in self.rois:
            return
        color = colorchooser.askcolor(title=f"Pick color for {name}")
        if color and color[1]:
            self.rois[name].color = color[1]
            self._set_active_roi(name)
            self._refresh_roi_list()
            self._redraw()

    # ---------------- Mouse Handling ----------------

    def _cancel_drag(self) -> None:
        self._drag_mode = None
        self._drag_start_canvas = None
        self._drag_start_norm = None
        self._resize_handle = None

    def _hit_test_handle(self, cx: int, cy: int, roi: ROI) -> Optional[str]:
        x1, y1, x2, y2 = roi.norm
        cx1, cy1 = self._norm_to_canvas(x1, y1)
        cx2, cy2 = self._norm_to_canvas(x2, y2)
        size = 8

        def near(px: float, py: float) -> bool:
            return abs(cx - px) <= size and abs(cy - py) <= size

        if near(cx1, cy1):
            return "nw"
        if near(cx2, cy1):
            return "ne"
        if near(cx1, cy2):
            return "sw"
        if near(cx2, cy2):
            return "se"
        return None

    def _point_in_roi(self, cx: int, cy: int, roi: ROI) -> bool:
        x1, y1, x2, y2 = roi.norm
        cx1, cy1 = self._norm_to_canvas(x1, y1)
        cx2, cy2 = self._norm_to_canvas(x2, y2)
        return min(cx1, cx2) <= cx <= max(cx1, cx2) and min(cy1, cy2) <= cy <= max(cy1, cy2)

    def _on_mouse_down(self, event) -> None:
        if not self.current_image:
            return
        cx, cy = int(event.x), int(event.y)

        # If we have an active ROI, prioritize resize/move
        if self.active_roi_name and self.active_roi_name in self.rois:
            roi = self.rois[self.active_roi_name]
            handle = self._hit_test_handle(cx, cy, roi)
            if handle:
                self._drag_mode = "resize"
                self._resize_handle = handle
                self._drag_start_canvas = (cx, cy)
                self._drag_start_norm = roi.norm
                return
            if self._point_in_roi(cx, cy, roi):
                self._drag_mode = "move"
                self._drag_start_canvas = (cx, cy)
                self._drag_start_norm = roi.norm
                return

        # Otherwise: if we have an active ROI, start draw to redefine it
        if self.active_roi_name and self.active_roi_name in self.rois:
            self._drag_mode = "draw"
            self._drag_start_canvas = (cx, cy)
            nx, ny = self._canvas_to_norm(cx, cy)
            self.rois[self.active_roi_name].norm = normalize_roi(nx, ny, nx, ny)
            self._redraw()
            return

        # No active ROI: ignore

    def _on_mouse_drag(self, event) -> None:
        if not self.current_image:
            return
        if not self._drag_mode or not self.active_roi_name or self.active_roi_name not in self.rois:
            return

        cx, cy = int(event.x), int(event.y)
        roi = self.rois[self.active_roi_name]

        if self._drag_mode == "draw":
            if not self._drag_start_canvas:
                return
            sx, sy = self._drag_start_canvas
            nx1, ny1 = self._canvas_to_norm(sx, sy)
            nx2, ny2 = self._canvas_to_norm(cx, cy)
            roi.norm = normalize_roi(nx1, ny1, nx2, ny2)
            self._set_active_roi(roi.name)
            self._redraw()
            return

        if self._drag_mode == "move":
            if not self._drag_start_canvas or not self._drag_start_norm:
                return
            sx, sy = self._drag_start_canvas
            dx = cx - sx
            dy = cy - sy

            disp_w, disp_h = self.display_size
            ndx = dx / max(1, disp_w)
            ndy = dy / max(1, disp_h)

            x1, y1, x2, y2 = self._drag_start_norm
            roi.norm = normalize_roi(x1 + ndx, y1 + ndy, x2 + ndx, y2 + ndy)
            self._set_active_roi(roi.name)
            self._redraw()
            return

        if self._drag_mode == "resize":
            if not self._drag_start_norm or not self._resize_handle:
                return
            x1, y1, x2, y2 = self._drag_start_norm
            nx, ny = self._canvas_to_norm(cx, cy)

            if self._resize_handle == "nw":
                roi.norm = normalize_roi(nx, ny, x2, y2)
            elif self._resize_handle == "ne":
                roi.norm = normalize_roi(x1, ny, nx, y2)
            elif self._resize_handle == "sw":
                roi.norm = normalize_roi(nx, y1, x2, ny)
            elif self._resize_handle == "se":
                roi.norm = normalize_roi(x1, y1, nx, ny)

            self._set_active_roi(roi.name)
            self._redraw()

    def _on_mouse_up(self, _event) -> None:
        if self.active_roi_name and self.active_roi_name in self.rois:
            self._set_active_roi(self.active_roi_name)
        self._cancel_drag()

    # ---------------- Persistence ----------------

    def _save(self) -> None:
        payload = {
            "version": 1,
            "shared": True,
            "rois": {name: list(self.rois[name].norm) for name in self.roi_order if name in self.rois},
            "colors": {name: self.rois[name].color for name in self.roi_order if name in self.rois},
        }
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self.out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        messagebox.showinfo("Saved", f"Saved ROIs to {self.out_path}")

    def _load_json(self) -> None:
        if not self.out_path.exists():
            messagebox.showwarning("Missing", f"{self.out_path} does not exist yet.")
            return
        try:
            payload = json.loads(self.out_path.read_text(encoding="utf-8"))
            rois = payload.get("rois", {})
            colors = payload.get("colors", {})
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load JSON: {exc}")
            return

        # Replace existing
        self.rois = {}
        self.roi_order = []
        for name, coords in rois.items():
            try:
                norm = normalize_roi(float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3]))
            except Exception:
                continue
            self._upsert_roi(name=name, color=colors.get(name), norm=norm)

        self._set_active_roi(self.roi_order[0] if self.roi_order else None)
        self._refresh_roi_list()
        self._redraw()

    def _export_python(self) -> None:
        out_py = self.out_path.with_suffix(".py")
        lines = ["# Auto-generated by roi_tool.py", "", "# Normalized ROIs: (x1, y1, x2, y2)"]
        for name in self.roi_order:
            if name not in self.rois:
                continue
            x1, y1, x2, y2 = self.rois[name].norm
            safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name).upper()
            lines.append(f"{safe}_ROI = ({x1:.6f}, {y1:.6f}, {x2:.6f}, {y2:.6f})")
        out_py.write_text("\n".join(lines) + "\n", encoding="utf-8")
        messagebox.showinfo("Exported", f"Wrote {out_py}")


def parse_initial_rois(path: Optional[str]) -> Dict[str, NormROI]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        rois = payload.get("rois", {})
        out: Dict[str, NormROI] = {}
        for name, coords in rois.items():
            out[name] = normalize_roi(float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3]))
        return out
    except Exception:
        return {}


def collect_images(folder: Path) -> List[Path]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
    paths = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts]
    paths.sort(key=lambda p: p.name.lower())
    return paths


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Visual ROI placement tool")
    ap.add_argument("--images", default="./test_images", help="Folder containing images")
    ap.add_argument("--out", default="rois.json", help="Output JSON file")
    ap.add_argument("--load", default=None, help="Load initial ROIs from an existing JSON")
    args = ap.parse_args(argv)

    images_dir = Path(args.images).resolve()
    if not images_dir.exists() or not images_dir.is_dir():
        raise SystemExit(f"Images folder not found: {images_dir}")

    image_paths = collect_images(images_dir)
    if not image_paths:
        raise SystemExit(f"No images found in: {images_dir}")

    out_path = Path(args.out).resolve()

    initial = parse_initial_rois(args.load)

    # Provide defaults matching user's example if no initial is provided
    if not initial:
        initial = {
            "EPIC": (0.55, 0.05, 0.98, 0.18),
            "HOUSE": (0.05, 0.42, 0.78, 0.56),
        }

    app = ROIEditorApp(image_paths=image_paths, out_path=out_path, initial_rois=initial)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
