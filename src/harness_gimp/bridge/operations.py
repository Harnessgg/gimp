import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from harness_gimp import __version__
from harness_gimp.core.gimp import GimpExecutionError, resolve_gimp_binary, resolve_profile_dir, run_python_batch


class BridgeOperationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


ACTION_METHODS = [
    "system.health",
    "system.version",
    "system.actions",
    "system.doctor",
    "system.soak",
    "project.plan_edit",
    "image.inspect",
    "image.validate",
    "image.diff",
    "image.snapshot",
    "image.undo",
    "image.redo",
    "image.open",
    "image.save",
    "image.clone",
    "image.resize",
    "image.crop",
    "image.crop_center",
    "image.rotate",
    "image.flip",
    "image.canvas_size",
    "image.montage_grid",
    "image.export",
    "adjust.brightness_contrast",
    "adjust.levels",
    "adjust.curves",
    "adjust.hue_saturation",
    "adjust.color_balance",
    "adjust.color_temperature",
    "adjust.invert",
    "adjust.desaturate",
    "filter.blur",
    "filter.gaussian_blur",
    "filter.sharpen",
    "filter.unsharp_mask",
    "filter.noise_reduction",
    "layer.list",
    "layer.add",
    "layer.remove",
    "layer.rename",
    "layer.opacity",
    "layer.blend_mode",
    "layer.duplicate",
    "layer.merge_down",
    "layer.reorder",
    "selection.all",
    "selection.none",
    "selection.invert",
    "selection.feather",
    "selection.rectangle",
    "selection.ellipse",
    "mask.add",
    "mask.apply",
    "text.add",
    "text.update",
    "annotation.stroke_selection",
    "macro.run",
    "preset.list",
    "preset.apply",
]


HISTORY_ROOT = Path.cwd() / ".harness-gimp-history"
HISTORY_STATE = HISTORY_ROOT / "state.json"

PRESETS: Dict[str, List[Dict[str, Any]]] = {
    "web-optimize": [
        {"method": "image.resize", "params": {"width": 1920, "height": 1080}},
        {"method": "adjust.levels", "params": {"black": 5, "white": 250, "gamma": 1.0}},
    ],
    "thumbnail": [
        {"method": "image.resize", "params": {"width": 512, "height": 512}},
        {"method": "adjust.brightness_contrast", "params": {"brightness": 4, "contrast": 8}},
    ],
    "social-crop": [
        {"method": "image.crop", "params": {"x": 0, "y": 0, "width": 1080, "height": 1080}},
    ],
}


def _require_path(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        raise BridgeOperationError("NOT_FOUND", f"File not found: {path}")
    return p


def _script(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload)
    return f"""
import json
from gi.repository import Gimp, Gio

payload = json.loads(r'''{blob}''')
pdb = Gimp.get_pdb()

def call(name, props):
  proc = pdb.lookup_procedure(name)
  if proc is None:
    raise RuntimeError(f"Missing procedure: {{name}}")
  cfg = proc.create_config()
  for k, v in props.items():
    cfg.set_property(k, v)
  result = proc.run(cfg)
  status = result.index(0)
  if status != Gimp.PDBStatusType.SUCCESS:
    raise RuntimeError(f"{{name}} failed: {{status}}")
  return [result.index(i + 1) for i in range(len(proc.get_return_values()))]

def load_image(path):
  return call("gimp-file-load", {{
    "run-mode": Gimp.RunMode.NONINTERACTIVE,
    "file": Gio.File.new_for_path(path),
  }})[0]

def save_image(image, path):
  call("gimp-file-save", {{
    "run-mode": Gimp.RunMode.NONINTERACTIVE,
    "image": image,
    "file": Gio.File.new_for_path(path),
    "options": None,
  }})

def delete_image(image):
  try:
    image.delete()
  except Exception:
    call("gimp-image-delete", {{"image": image}})

def image_layers(image):
  return list(image.get_layers())

def layer_by_index(image, index):
  layers = image_layers(image)
  if index < 0 or index >= len(layers):
    raise RuntimeError(f"Invalid layer index: {{index}}")
  return layers[index]

def image_dimensions(image):
  width = int(image.get_width())
  height = int(image.get_height())
  return width, height

def enum_member(enum_cls, candidate_names):
  for name in candidate_names:
    if hasattr(enum_cls, name):
      return getattr(enum_cls, name)
  raise RuntimeError(f"Missing enum values: {{candidate_names}}")

def layer_mode_from_name(name):
  normalized = str(name).strip().upper().replace("-", "_").replace(" ", "_")
  candidates = [normalized]
  if not normalized.endswith("_LEGACY"):
    candidates.append(normalized + "_LEGACY")
  return enum_member(Gimp.LayerMode, candidates)

def _gegl_color(hex_value):
  from gi.repository import Gegl
  return Gegl.Color.new(str(hex_value))

def _apply_gegl_filter(drawable, operation_name, filter_name, config_values):
  flt = call("gimp-drawable-filter-new", {{
    "drawable": drawable,
    "operation-name": operation_name,
    "name": filter_name,
  }})[0]
  cfg = flt.get_config()
  for key, value in config_values.items():
    cfg.set_property(key, value)
  call("gimp-drawable-merge-filters", {{"drawable": drawable}})

action = payload.get("action")

if action == "inspect":
  image = load_image(payload["image"])
  width, height = image_dimensions(image)
  layers = image_layers(image)
  out = []
  for idx, layer in enumerate(layers):
    out.append({{"index": idx, "name": layer.get_name(), "opacity": layer.get_opacity(), "mode": str(layer.get_mode())}})
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"width": width, "height": height, "layerCount": len(layers), "layers": out}}))

elif action == "resize":
  image = load_image(payload["image"])
  call("gimp-image-scale", {{"image": image, "new-width": int(payload["width"]), "new-height": int(payload["height"])}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "width": int(payload["width"]), "height": int(payload["height"])}}))

elif action == "crop":
  image = load_image(payload["image"])
  call("gimp-image-crop", {{
    "image": image,
    "new-width": int(payload["width"]),
    "new-height": int(payload["height"]),
    "offx": int(payload["x"]),
    "offy": int(payload["y"]),
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "rotate":
  degrees = int(payload["degrees"])
  image = load_image(payload["image"])
  mapping = {{
    90: Gimp.RotationType.DEGREES90,
    180: Gimp.RotationType.DEGREES180,
    270: Gimp.RotationType.DEGREES270,
  }}
  if degrees not in mapping:
    raise RuntimeError("rotate currently supports 90/180/270")
  call("gimp-image-rotate", {{"image": image, "rotate-type": mapping[degrees]}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "degrees": degrees}}))

elif action == "flip":
  image = load_image(payload["image"])
  axis = str(payload["axis"]).lower()
  orientation = Gimp.OrientationType.HORIZONTAL if axis == "horizontal" else Gimp.OrientationType.VERTICAL
  call("gimp-image-flip", {{"image": image, "flip-type": orientation}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "axis": axis}}))

elif action == "canvas_size":
  image = load_image(payload["image"])
  call("gimp-image-resize", {{
    "image": image,
    "new-width": int(payload["width"]),
    "new-height": int(payload["height"]),
    "offx": int(payload.get("offsetX", 0)),
    "offy": int(payload.get("offsetY", 0)),
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "export":
  image = load_image(payload["image"])
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "brightness_contrast":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  brightness = max(-1.0, min(1.0, float(payload["brightness"]) / 127.0))
  contrast = max(-1.0, min(1.0, float(payload["contrast"]) / 127.0))
  call("gimp-drawable-brightness-contrast", {{"drawable": layer, "brightness": brightness, "contrast": contrast}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "brightness": brightness, "contrast": contrast}}))

elif action == "levels":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  black = max(0.0, min(255.0, float(payload["black"])))
  white = max(0.0, min(255.0, float(payload["white"])))
  gamma = float(payload["gamma"])
  if white <= black:
    raise RuntimeError("white must be greater than black")
  call("gimp-drawable-levels", {{
    "drawable": layer,
    "channel": Gimp.HistogramChannel.VALUE,
    "low-input": black / 255.0,
    "high-input": white / 255.0,
    "clamp-input": True,
    "gamma": gamma,
    "low-output": 0.0,
    "high-output": 1.0,
    "clamp-output": True,
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "hue_saturation":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  call("gimp-drawable-hue-saturation", {{
    "drawable": layer,
    "hue-range": Gimp.HueRange.ALL,
    "hue-offset": float(payload["hue"]),
    "lightness": float(payload["lightness"]),
    "saturation": float(payload["saturation"]),
    "overlap": 0.0,
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "color_balance":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  transfer_name = str(payload.get("transferMode", "MIDTONES")).upper()
  transfer_map = {{
    "SHADOWS": Gimp.TransferMode.SHADOWS,
    "MIDTONES": Gimp.TransferMode.MIDTONES,
    "HIGHLIGHTS": Gimp.TransferMode.HIGHLIGHTS,
  }}
  if transfer_name not in transfer_map:
    raise RuntimeError("transferMode must be SHADOWS|MIDTONES|HIGHLIGHTS")
  call("gimp-drawable-color-balance", {{
    "drawable": layer,
    "transfer-mode": transfer_map[transfer_name],
    "preserve-lum": True,
    "cyan-red": float(payload["cyanRed"]) / 100.0,
    "magenta-green": float(payload["magentaGreen"]) / 100.0,
    "yellow-blue": float(payload["yellowBlue"]) / 100.0,
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "transferMode": transfer_name}}))

elif action == "curves":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  channel_name = str(payload.get("channel", "value")).upper()
  channel_map = {{
    "VALUE": Gimp.HistogramChannel.VALUE,
    "RED": Gimp.HistogramChannel.RED,
    "GREEN": Gimp.HistogramChannel.GREEN,
    "BLUE": Gimp.HistogramChannel.BLUE,
    "ALPHA": Gimp.HistogramChannel.ALPHA,
  }}
  if channel_name not in channel_map:
    raise RuntimeError("channel must be value|red|green|blue|alpha")
  points = payload.get("points", [])
  if not isinstance(points, list) or len(points) < 2:
    raise RuntimeError("points must be a non-empty list")
  normalized = []
  for pt in points:
    if isinstance(pt, dict):
      x_raw = pt.get("x", 0.0)
      y_raw = pt.get("y", 0.0)
    elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
      x_raw, y_raw = pt[0], pt[1]
    else:
      raise RuntimeError("points must be objects {{x,y}} or [x,y] pairs")
    x = float(x_raw)
    y = float(y_raw)
    if x > 1.0 or y > 1.0:
      x /= 255.0
      y /= 255.0
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    normalized.append((x, y))
  normalized.sort(key=lambda p: p[0])
  black = int(max(0, min(255, round(normalized[0][0] * 255))))
  white = int(max(1, min(255, round(normalized[-1][0] * 255))))
  if white <= black:
    white = min(255, black + 1)
  call("gimp-drawable-levels", {{
    "drawable": layer,
    "channel": channel_map[channel_name],
    "low-input": black / 255.0,
    "high-input": white / 255.0,
    "clamp-input": True,
    "gamma": 1.0,
    "low-output": 0.0,
    "high-output": 1.0,
    "clamp-output": True,
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "implementedAs": "levels-approximation"}}))

elif action == "color_temperature":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  temp = float(payload.get("temperature", 6500.0))
  _apply_gegl_filter(
    layer,
    "gegl:color-temperature",
    "color-temp",
    {{"original-temperature": 6500.0, "intended-temperature": temp}},
  )
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "temperature": temp}}))

elif action == "invert":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  call("gimp-drawable-invert", {{"drawable": layer, "linear": False}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "desaturate":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  mode_name = str(payload.get("mode", "luma")).upper()
  mode_map = {{
    "LUMA": Gimp.DesaturateMode.LUMA,
    "AVERAGE": Gimp.DesaturateMode.AVERAGE,
    "LIGHTNESS": Gimp.DesaturateMode.LIGHTNESS,
  }}
  if mode_name not in mode_map:
    raise RuntimeError("mode must be luma|average|lightness")
  call("gimp-drawable-desaturate", {{"drawable": layer, "desaturate-mode": mode_map[mode_name]}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "mode": mode_name.lower()}}))

elif action == "gaussian_blur":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  rx = float(payload.get("radiusX", 4.0))
  ry = float(payload.get("radiusY", rx))
  _apply_gegl_filter(layer, "gegl:gaussian-blur", "gaussian-blur", {{"std-dev-x": rx, "std-dev-y": ry}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "radiusX": rx, "radiusY": ry}}))

elif action == "blur":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  radius = float(payload.get("radius", 4.0))
  _apply_gegl_filter(layer, "gegl:gaussian-blur", "blur", {{"std-dev-x": radius, "std-dev-y": radius}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "radius": radius}}))

elif action == "unsharp_mask":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  radius = float(payload.get("radius", 2.0))
  amount = float(payload.get("amount", 1.0))
  threshold = float(payload.get("threshold", 0.0))
  _apply_gegl_filter(layer, "gegl:unsharp-mask", "unsharp", {{"std-dev": radius, "scale": amount, "threshold": threshold}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "radius": radius, "amount": amount, "threshold": threshold}}))

elif action == "sharpen":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  radius = float(payload.get("radius", 2.0))
  amount = float(payload.get("amount", 1.0))
  _apply_gegl_filter(layer, "gegl:unsharp-mask", "sharpen", {{"std-dev": radius, "scale": amount, "threshold": 0.0}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "radius": radius, "amount": amount}}))

elif action == "noise_reduction":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  strength = int(max(1, min(10, int(payload.get("strength", 3)))))
  _apply_gegl_filter(layer, "gegl:noise-reduction", "noise-reduction", {{"iterations": strength}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "strength": strength}}))

elif action == "layer_list":
  image = load_image(payload["image"])
  layers = image_layers(image)
  out = []
  for idx, layer in enumerate(layers):
    out.append({{
      "index": idx,
      "name": layer.get_name(),
      "opacity": layer.get_opacity(),
      "mode": str(layer.get_mode()),
    }})
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"layers": out, "count": len(out)}}))

elif action == "layer_add":
  image = load_image(payload["image"])
  width, height = image_dimensions(image)
  existing = image_layers(image)
  if existing:
    ltype = call("gimp-drawable-type", {{"drawable": existing[0]}})[0]
  else:
    ltype = enum_member(Gimp.ImageType, ["RGBA_IMAGE", "RGB_IMAGE"])
  mode = enum_member(Gimp.LayerMode, ["NORMAL", "NORMAL_LEGACY"])
  layer = call("gimp-layer-new", {{
    "image": image,
    "name": payload["name"],
    "width": width,
    "height": height,
    "type": ltype,
    "opacity": 100.0,
    "mode": mode,
  }})[0]
  call("gimp-image-insert-layer", {{"image": image, "layer": layer, "parent": None, "position": int(payload.get("position", 0))}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "layer_remove":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  call("gimp-image-remove-layer", {{"image": image, "layer": layer}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "layer_rename":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  layer.set_name(payload["name"])
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "layer_opacity":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  layer.set_opacity(float(payload["opacity"]))
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "layer_blend_mode":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  mode = layer_mode_from_name(payload["mode"])
  layer.set_mode(mode)
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "mode": str(mode)}}))

elif action == "layer_duplicate":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  dup = call("gimp-layer-copy", {{"layer": layer}})[0]
  call("gimp-image-insert-layer", {{
    "image": image,
    "layer": dup,
    "parent": None,
    "position": int(payload.get("position", int(payload["layerIndex"]) + 1)),
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "layer_merge_down":
  image = load_image(payload["image"])
  idx = int(payload["layerIndex"])
  layers = image_layers(image)
  if len(layers) < 2:
    raise RuntimeError("layer_merge_down requires at least 2 layers")
  if idx < 0 or idx >= (len(layers) - 1):
    raise RuntimeError("layerIndex must reference a layer with another layer below it")
  layer = layers[idx]
  call("gimp-image-merge-down", {{"image": image, "merge-layer": layer, "merge-type": Gimp.MergeType.EXPAND_AS_NECESSARY}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "layer_reorder":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  call("gimp-image-reorder-item", {{
    "image": image,
    "item": layer,
    "parent": None,
    "position": int(payload["index"]),
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action in ("selection_all", "selection_none", "selection_invert"):
  image = load_image(payload["image"])
  proc_map = {{
    "selection_all": "gimp-selection-all",
    "selection_none": "gimp-selection-none",
    "selection_invert": "gimp-selection-invert",
  }}
  call(proc_map[action], {{"image": image}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "action": action}}))

elif action == "selection_feather":
  image = load_image(payload["image"])
  call("gimp-selection-feather", {{"image": image, "radius": float(payload.get("radius", 5.0))}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "selection_rectangle":
  image = load_image(payload["image"])
  call("gimp-image-select-rectangle", {{
    "image": image,
    "operation": Gimp.ChannelOps.REPLACE,
    "x": float(payload["x"]),
    "y": float(payload["y"]),
    "width": float(payload["width"]),
    "height": float(payload["height"]),
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "selection_ellipse":
  image = load_image(payload["image"])
  call("gimp-image-select-ellipse", {{
    "image": image,
    "operation": Gimp.ChannelOps.REPLACE,
    "x": float(payload["x"]),
    "y": float(payload["y"]),
    "width": float(payload["width"]),
    "height": float(payload["height"]),
  }})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "mask_add":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  mode_name = str(payload.get("mode", "WHITE")).upper()
  mode_map = {{
    "WHITE": Gimp.AddMaskType.WHITE,
    "BLACK": Gimp.AddMaskType.BLACK,
    "ALPHA": Gimp.AddMaskType.ALPHA,
    "SELECTION": Gimp.AddMaskType.SELECTION,
    "COPY": Gimp.AddMaskType.COPY,
  }}
  if mode_name not in mode_map:
    raise RuntimeError("mask mode must be one of WHITE|BLACK|ALPHA|SELECTION|COPY")
  mask = call("gimp-layer-create-mask", {{"layer": layer, "mask-type": mode_map[mode_name]}})[0]
  call("gimp-layer-add-mask", {{"layer": layer, "mask": mask}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"], "mode": mode_name}}))

elif action == "mask_apply":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  call("gimp-layer-remove-mask", {{"layer": layer, "mode": Gimp.MaskApplyMode.APPLY}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "text_add":
  image = load_image(payload["image"])
  font_name = str(payload.get("font", "")).strip()
  font = call("gimp-context-get-font", {{}})[0]
  if font_name:
    try:
      candidate = call("gimp-font-get-by-name", {{"name": font_name}})[0]
      if candidate is not None:
        font = candidate
    except Exception:
      pass
  if payload.get("color"):
    call("gimp-context-set-foreground", {{"foreground": _gegl_color(payload.get("color"))}})
  text_layer = call("gimp-text-font", {{
    "image": image,
    "drawable": None,
    "x": float(payload.get("x", 0)),
    "y": float(payload.get("y", 0)),
    "text": str(payload.get("text", "")),
    "border": 0,
    "antialias": True,
    "size": float(payload.get("size", 24)),
    "font": font,
  }})[0]
  if payload.get("color"):
    try:
      call("gimp-text-layer-set-color", {{"layer": text_layer, "color": _gegl_color(payload.get("color"))}})
    except Exception:
      pass
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "text_update":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload["layerIndex"]))
  try:
    call("gimp-text-layer-set-text", {{"layer": layer, "text": str(payload.get("text", ""))}})
  except Exception as exc:
    raise RuntimeError("layerIndex must reference a text layer") from exc
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

elif action == "stroke_selection":
  image = load_image(payload["image"])
  layer = layer_by_index(image, int(payload.get("layerIndex", 0)))
  call("gimp-context-set-line-width", {{"line-width": float(payload.get("width", 1.0))}})
  if payload.get("color"):
    call("gimp-context-set-foreground", {{"foreground": _gegl_color(payload.get("color"))}})
  try:
    call("gimp-drawable-edit-stroke-selection", {{"drawable": layer}})
  except Exception:
    call("gimp-selection-all", {{"image": image}})
    call("gimp-drawable-edit-stroke-selection", {{"drawable": layer}})
  save_image(image, payload["output"])
  delete_image(image)
  print("HARNESS_JSON:" + json.dumps({{"output": payload["output"]}}))

else:
  raise RuntimeError("Unsupported action: " + str(action))
"""


def _run_action(action: str, payload: Dict[str, Any], timeout_seconds: float = 240.0) -> Dict[str, Any]:
    data = dict(payload)
    data["action"] = action
    try:
        result = run_python_batch(_script(data), timeout_seconds=timeout_seconds)
    except GimpExecutionError as exc:
        raise BridgeOperationError("ERROR", str(exc)) from exc
    mutating = {
        "resize",
        "crop",
        "rotate",
        "flip",
        "canvas_size",
        "brightness_contrast",
        "levels",
        "curves",
        "hue_saturation",
        "color_balance",
        "color_temperature",
        "invert",
        "desaturate",
        "blur",
        "gaussian_blur",
        "sharpen",
        "unsharp_mask",
        "noise_reduction",
        "layer_add",
        "layer_remove",
        "layer_rename",
        "layer_opacity",
        "layer_blend_mode",
        "layer_duplicate",
        "layer_merge_down",
        "layer_reorder",
        "selection_all",
        "selection_none",
        "selection_invert",
        "selection_feather",
        "selection_rectangle",
        "selection_ellipse",
        "mask_add",
        "mask_apply",
        "text_add",
        "text_update",
        "stroke_selection",
    }
    if action in mutating and "image" in payload:
        image_path = Path(str(payload["image"]))
        output = Path(str(payload.get("output") or payload["image"]))
        try:
            same_target = image_path.resolve() == output.resolve()
        except Exception:
            same_target = str(image_path) == str(output)
        if same_target and image_path.exists():
            _snapshot_image(image_path, f"auto-after-{action}")
    return result


def _output_or_input(params: Dict[str, Any], image: str) -> str:
    return str(Path(params.get("output") or image))


def _montage_grid(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageColor, ImageOps
    except Exception as exc:
        raise BridgeOperationError("ERROR", "Pillow is required for image.montage_grid") from exc

    images = params.get("images")
    if not isinstance(images, list) or not images:
        raise BridgeOperationError("INVALID_INPUT", "images must be a non-empty list of file paths")
    image_paths = [_require_path(str(p)) for p in images]

    rows = int(params.get("rows", 0))
    cols = int(params.get("cols", 0))
    if rows <= 0 or cols <= 0:
        raise BridgeOperationError("INVALID_INPUT", "rows and cols must be > 0")
    if len(image_paths) != rows * cols:
        raise BridgeOperationError("INVALID_INPUT", "images length must equal rows * cols")

    tile_w = int(params.get("tileWidth", 0))
    tile_h = int(params.get("tileHeight", 0))
    if tile_w <= 0 or tile_h <= 0:
        raise BridgeOperationError("INVALID_INPUT", "tileWidth and tileHeight must be > 0")

    gutter = int(params.get("gutter", 0))
    if gutter < 0:
        raise BridgeOperationError("INVALID_INPUT", "gutter must be >= 0")

    fit_mode = str(params.get("fitMode", "cover")).strip().lower()
    if fit_mode not in {"cover", "contain"}:
        raise BridgeOperationError("INVALID_INPUT", "fitMode must be cover or contain")

    output = Path(str(params.get("output", "")).strip())
    if not str(output):
        raise BridgeOperationError("INVALID_INPUT", "output is required")
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        bg_rgb = ImageColor.getrgb(str(params.get("background", "#000000")))
    except Exception as exc:
        raise BridgeOperationError("INVALID_INPUT", "background must be a valid CSS hex color") from exc

    canvas_w = cols * tile_w + (cols - 1) * gutter
    canvas_h = rows * tile_h + (rows - 1) * gutter
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_rgb)

    for i, source_path in enumerate(image_paths):
        src = Image.open(source_path).convert("RGB")
        if fit_mode == "cover":
            tile = ImageOps.fit(src, (tile_w, tile_h), method=Image.Resampling.LANCZOS)
        else:
            tile = src.copy()
            tile.thumbnail((tile_w, tile_h), resample=Image.Resampling.LANCZOS)
            fitted = Image.new("RGB", (tile_w, tile_h), bg_rgb)
            fitted.paste(tile, ((tile_w - tile.width) // 2, (tile_h - tile.height) // 2))
            tile = fitted

        r = i // cols
        c = i % cols
        x = c * (tile_w + gutter)
        y = r * (tile_h + gutter)
        canvas.paste(tile, (x, y))

    canvas.save(output)
    return {
        "output": str(output),
        "rows": rows,
        "cols": cols,
        "tileWidth": tile_w,
        "tileHeight": tile_h,
        "gutter": gutter,
    }


def _exif_orientation(path: Path) -> int | None:
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return None
            value = exif.get(274)
            return int(value) if value else None
    except Exception:
        return None


def _layer_index(params: Dict[str, Any], default: int = -1) -> int:
    raw = params.get("layerIndex", params.get("layerId", default))
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise BridgeOperationError("INVALID_INPUT", "layerIndex/layerId must be an integer") from exc


def _history_load() -> Dict[str, Any]:
    if HISTORY_STATE.exists():
        return json.loads(HISTORY_STATE.read_text(encoding="utf-8"))
    return {"images": {}}


def _history_save(state: Dict[str, Any]) -> None:
    HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
    HISTORY_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _safe_name(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-")
    return cleaned or "snapshot"


def _snapshot_image(image: Path, description: str) -> Dict[str, Any]:
    state = _history_load()
    image_key = str(image.resolve())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    entry_dir = HISTORY_ROOT / _safe_name(image.stem)
    entry_dir.mkdir(parents=True, exist_ok=True)
    snapshot = entry_dir / f"{stamp}__{_safe_name(description)}{image.suffix.lower()}"
    shutil.copyfile(image, snapshot)
    image_state = state["images"].setdefault(image_key, {"snapshots": [], "index": -1})
    image_state["snapshots"] = image_state["snapshots"][: image_state["index"] + 1]
    image_state["snapshots"].append(str(snapshot))
    image_state["index"] = len(image_state["snapshots"]) - 1
    _history_save(state)
    return {"snapshot": str(snapshot), "index": image_state["index"], "count": len(image_state["snapshots"])}


def _undo_redo(image: Path, direction: int) -> Dict[str, Any]:
    state = _history_load()
    image_key = str(image.resolve())
    image_state = state.get("images", {}).get(image_key)
    if not image_state or not image_state.get("snapshots"):
        raise BridgeOperationError("INVALID_INPUT", f"No snapshot history for: {image}")
    idx = int(image_state.get("index", -1))
    next_idx = idx + direction
    if next_idx < 0 or next_idx >= len(image_state["snapshots"]):
        raise BridgeOperationError("INVALID_INPUT", "No further history step available")
    target = Path(image_state["snapshots"][next_idx])
    if not target.exists():
        raise BridgeOperationError("NOT_FOUND", f"Snapshot missing: {target}")
    shutil.copyfile(target, image)
    image_state["index"] = next_idx
    _history_save(state)
    return {"image": str(image), "snapshot": str(target), "index": next_idx, "count": len(image_state["snapshots"])}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _maybe_auto_snapshot(image: Path, params: Dict[str, Any], label: str) -> None:
    output = Path(str(params.get("output") or image))
    try:
        same_target = output.resolve() == image.resolve()
    except Exception:
        same_target = str(output) == str(image)
    if same_target:
        _snapshot_image(image, f"auto-before-{label}")


def handle_method(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if method == "system.health":
        return {"ok": True}
    if method == "system.version":
        return {"packageVersion": __version__}
    if method == "system.actions":
        return {"actions": ACTION_METHODS}
    if method == "system.doctor":
        verbose = bool(params.get("verbose", False))
        bridge_url_env = os.getenv("HARNESS_GIMP_BRIDGE_URL")
        bridge_url = bridge_url_env or "http://127.0.0.1:41749"
        try:
            gimp_bin = resolve_gimp_binary()
        except GimpExecutionError as exc:
            return {"healthy": False, "issues": [str(exc)]}
        proc = subprocess.run([str(gimp_bin), "--version"], capture_output=True, text=True, timeout=15)
        data = {
            "healthy": proc.returncode == 0,
            "gimpBinary": str(gimp_bin),
            "gimpVersionRaw": (proc.stdout or proc.stderr).strip(),
            "issues": [] if proc.returncode == 0 else ["Unable to run gimp --version"],
            "nonFatalWarningsSuppressed": True,
        }
        if verbose:
            data["runtime"] = {
                "pythonExecutable": sys.executable,
                "modulePath": str(Path(__file__).resolve()),
                "bridgeUrl": bridge_url,
                "bridgeUrlSource": "HARNESS_GIMP_BRIDGE_URL" if bridge_url_env else "default",
                "gimpProfileDir": str(resolve_profile_dir()),
                "invocationHint": "Prefer `harness-gimp` or `harnessgg-gimp` over `python -m harness_gimp` to reduce module collision risk.",
            }
        return data
    if method == "system.soak":
        iterations = int(params.get("iterations", 100))
        action = str(params.get("action", "system.health"))
        action_params = params.get("action_params", {}) or {}
        failures = 0
        for _ in range(max(1, iterations)):
            try:
                if action == "system.health":
                    handle_method("system.health", {})
                else:
                    handle_method(action, action_params)
            except Exception:
                failures += 1
        return {"iterations": iterations, "action": action, "failures": failures, "stable": failures == 0}
    if method == "project.plan_edit":
        image = str(_require_path(str(params.get("image", ""))))
        action = str(params.get("action", "")).strip()
        action_params = params.get("params", {}) or {}
        method_map = {
            "resize": "image.resize",
            "crop": "image.crop",
            "crop-center": "image.crop_center",
            "rotate": "image.rotate",
            "flip": "image.flip",
            "canvas-size": "image.canvas_size",
            "montage-grid": "image.montage_grid",
            "brightness-contrast": "adjust.brightness_contrast",
            "levels": "adjust.levels",
            "curves": "adjust.curves",
            "hue-saturation": "adjust.hue_saturation",
            "color-balance": "adjust.color_balance",
            "color-temperature": "adjust.color_temperature",
            "invert": "adjust.invert",
            "desaturate": "adjust.desaturate",
            "blur": "filter.blur",
            "gaussian-blur": "filter.gaussian_blur",
            "sharpen": "filter.sharpen",
            "unsharp-mask": "filter.unsharp_mask",
            "noise-reduction": "filter.noise_reduction",
            "layer-add": "layer.add",
            "layer-remove": "layer.remove",
            "layer-rename": "layer.rename",
            "layer-opacity": "layer.opacity",
            "layer-blend-mode": "layer.blend_mode",
            "layer-duplicate": "layer.duplicate",
            "layer-merge-down": "layer.merge_down",
            "layer-reorder": "layer.reorder",
            "select-all": "selection.all",
            "select-none": "selection.none",
            "invert-selection": "selection.invert",
            "feather-selection": "selection.feather",
            "select-rectangle": "selection.rectangle",
            "select-ellipse": "selection.ellipse",
            "add-layer-mask": "mask.add",
            "apply-layer-mask": "mask.apply",
            "add-text": "text.add",
            "update-text": "text.update",
            "stroke-selection": "annotation.stroke_selection",
        }
        if action not in method_map:
            raise BridgeOperationError("INVALID_INPUT", f"Unsupported plan action: {action}")
        merged = {"image": image}
        merged.update(action_params)
        return handle_method(method_map[action], merged)
    if method == "image.open":
        image = str(_require_path(str(params.get("image", ""))))
        return _run_action("inspect", {"image": image}, timeout_seconds=180)
    if method == "image.save":
        image = str(_require_path(str(params.get("image", ""))))
        output = str(params.get("output", "")).strip()
        if not output:
            raise BridgeOperationError("INVALID_INPUT", "output is required")
        return _run_action("export", {"image": image, "output": output})
    if method == "image.clone":
        source = _require_path(str(params.get("source", "")))
        target = Path(str(params.get("target", "")))
        if not str(target):
            raise BridgeOperationError("INVALID_INPUT", "target is required")
        if target.exists() and not bool(params.get("overwrite", False)):
            raise BridgeOperationError("INVALID_INPUT", f"Target exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return {"source": str(source), "target": str(target)}
    if method == "image.inspect":
        image = str(_require_path(str(params.get("image", ""))))
        data = _run_action("inspect", {"image": image}, timeout_seconds=180)
        exif_orientation = _exif_orientation(Path(image))
        data["exifOrientation"] = exif_orientation
        data["orientationWarning"] = bool(exif_orientation and exif_orientation != 1)
        return data
    if method == "image.validate":
        image = str(_require_path(str(params.get("image", ""))))
        data = _run_action("inspect", {"image": image}, timeout_seconds=180)
        return {"isValid": data["width"] > 0 and data["height"] > 0, "details": data}
    if method == "image.diff":
        source = _require_path(str(params.get("source", "")))
        target = _require_path(str(params.get("target", "")))
        src_info = _run_action("inspect", {"image": str(source)}, timeout_seconds=180)
        tgt_info = _run_action("inspect", {"image": str(target)}, timeout_seconds=180)
        src_hash = _sha256(source)
        tgt_hash = _sha256(target)
        return {
            "sameBytes": src_hash == tgt_hash,
            "source": {"path": str(source), "sha256": src_hash, "width": src_info["width"], "height": src_info["height"]},
            "target": {"path": str(target), "sha256": tgt_hash, "width": tgt_info["width"], "height": tgt_info["height"]},
            "sameDimensions": (src_info["width"], src_info["height"]) == (tgt_info["width"], tgt_info["height"]),
        }
    if method == "image.snapshot":
        image = _require_path(str(params.get("image", "")))
        description = str(params.get("description", "snapshot"))
        return _snapshot_image(image, description)
    if method == "image.undo":
        image = _require_path(str(params.get("image", "")))
        return _undo_redo(image, -1)
    if method == "image.redo":
        image = _require_path(str(params.get("image", "")))
        return _undo_redo(image, 1)
    if method == "image.resize":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "resize")
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))
        if width <= 0 or height <= 0:
            raise BridgeOperationError("INVALID_INPUT", "width and height must be > 0")
        return _run_action("resize", {"image": image, "width": width, "height": height, "output": _output_or_input(params, image)})
    if method == "image.crop":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "crop")
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))
        if width <= 0 or height <= 0:
            raise BridgeOperationError("INVALID_INPUT", "width and height must be > 0")
        return _run_action(
            "crop",
            {
                "image": image,
                "width": width,
                "height": height,
                "x": int(params.get("x", 0)),
                "y": int(params.get("y", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "image.crop_center":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "crop-center")
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))
        if width <= 0 or height <= 0:
            raise BridgeOperationError("INVALID_INPUT", "width and height must be > 0")
        inspect = _run_action("inspect", {"image": image}, timeout_seconds=180)
        src_w = int(inspect["width"])
        src_h = int(inspect["height"])
        if width > src_w or height > src_h:
            raise BridgeOperationError("INVALID_INPUT", "crop size cannot exceed source dimensions")
        x = int((src_w - width) // 2)
        y = int((src_h - height) // 2)
        return _run_action(
            "crop",
            {"image": image, "width": width, "height": height, "x": x, "y": y, "output": _output_or_input(params, image)},
        )
    if method == "image.rotate":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "rotate")
        degrees = int(params.get("degrees", 0))
        if degrees not in {90, 180, 270}:
            raise BridgeOperationError("INVALID_INPUT", "degrees must be one of 90, 180, 270")
        return _run_action("rotate", {"image": image, "degrees": degrees, "output": _output_or_input(params, image)})
    if method == "image.flip":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "flip")
        axis = str(params.get("axis", "horizontal")).lower()
        if axis not in {"horizontal", "vertical"}:
            raise BridgeOperationError("INVALID_INPUT", "axis must be horizontal or vertical")
        return _run_action("flip", {"image": image, "axis": axis, "output": _output_or_input(params, image)})
    if method == "image.canvas_size":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "canvas-size")
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))
        if width <= 0 or height <= 0:
            raise BridgeOperationError("INVALID_INPUT", "width and height must be > 0")
        return _run_action(
            "canvas_size",
            {
                "image": image,
                "width": width,
                "height": height,
                "offsetX": int(params.get("offsetX", 0)),
                "offsetY": int(params.get("offsetY", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "image.export":
        image = str(_require_path(str(params.get("image", ""))))
        output = str(params.get("output", "")).strip()
        if not output:
            raise BridgeOperationError("INVALID_INPUT", "output is required")
        return _run_action("export", {"image": image, "output": output})
    if method == "image.montage_grid":
        return _montage_grid(params)
    if method == "adjust.brightness_contrast":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "brightness-contrast")
        return _run_action(
            "brightness_contrast",
            {
                "image": image,
                "brightness": float(params.get("brightness", 0)),
                "contrast": float(params.get("contrast", 0)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "adjust.levels":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "levels")
        return _run_action(
            "levels",
            {
                "image": image,
                "black": float(params.get("black", 0)),
                "white": float(params.get("white", 255)),
                "gamma": float(params.get("gamma", 1.0)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "adjust.hue_saturation":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "hue-saturation")
        return _run_action(
            "hue_saturation",
            {
                "image": image,
                "hue": float(params.get("hue", 0)),
                "saturation": float(params.get("saturation", 0)),
                "lightness": float(params.get("lightness", 0)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "adjust.color_balance":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "color-balance")
        return _run_action(
            "color_balance",
            {
                "image": image,
                "transferMode": str(params.get("transferMode", "MIDTONES")),
                "cyanRed": float(params.get("cyanRed", 0)),
                "magentaGreen": float(params.get("magentaGreen", 0)),
                "yellowBlue": float(params.get("yellowBlue", 0)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "adjust.curves":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "curves")
        points = params.get("points")
        if not isinstance(points, list):
            raise BridgeOperationError("INVALID_INPUT", "points must be a list of {x,y} objects or [x,y] pairs")
        return _run_action(
            "curves",
            {
                "image": image,
                "channel": str(params.get("channel", "value")),
                "points": points,
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "adjust.color_temperature":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "color-temperature")
        return _run_action(
            "color_temperature",
            {
                "image": image,
                "temperature": float(params.get("temperature", 6500.0)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "adjust.invert":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "invert")
        return _run_action(
            "invert",
            {"image": image, "layerIndex": int(params.get("layerIndex", 0)), "output": _output_or_input(params, image)},
        )
    if method == "adjust.desaturate":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "desaturate")
        return _run_action(
            "desaturate",
            {
                "image": image,
                "mode": str(params.get("mode", "luma")),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "filter.blur":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "blur")
        return _run_action(
            "blur",
            {
                "image": image,
                "radius": float(params.get("radius", 4.0)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "filter.gaussian_blur":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "gaussian-blur")
        return _run_action(
            "gaussian_blur",
            {
                "image": image,
                "radiusX": float(params.get("radiusX", 4.0)),
                "radiusY": float(params.get("radiusY", params.get("radiusX", 4.0))),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "filter.sharpen":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "sharpen")
        return _run_action(
            "sharpen",
            {
                "image": image,
                "radius": float(params.get("radius", 2.0)),
                "amount": float(params.get("amount", 1.0)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "filter.unsharp_mask":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "unsharp-mask")
        return _run_action(
            "unsharp_mask",
            {
                "image": image,
                "radius": float(params.get("radius", 2.0)),
                "amount": float(params.get("amount", 1.0)),
                "threshold": float(params.get("threshold", 0.0)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "filter.noise_reduction":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "noise-reduction")
        return _run_action(
            "noise_reduction",
            {
                "image": image,
                "strength": int(params.get("strength", 3)),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "layer.list":
        image = str(_require_path(str(params.get("image", ""))))
        return _run_action("layer_list", {"image": image}, timeout_seconds=180)
    if method == "layer.add":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "layer-add")
        name = str(params.get("name", "")).strip()
        if not name:
            raise BridgeOperationError("INVALID_INPUT", "name is required")
        return _run_action(
            "layer_add",
            {"image": image, "name": name, "position": int(params.get("position", 0)), "output": _output_or_input(params, image)},
        )
    if method == "layer.remove":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "layer-remove")
        return _run_action(
            "layer_remove",
            {"image": image, "layerIndex": int(params.get("layerIndex", -1)), "output": _output_or_input(params, image)},
        )
    if method == "layer.rename":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "layer-rename")
        name = str(params.get("name", "")).strip()
        if not name:
            raise BridgeOperationError("INVALID_INPUT", "name is required")
        return _run_action(
            "layer_rename",
            {
                "image": image,
                "layerIndex": int(params.get("layerIndex", -1)),
                "name": name,
                "output": _output_or_input(params, image),
            },
        )
    if method == "layer.opacity":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "layer-opacity")
        opacity = float(params.get("opacity", -1))
        if opacity < 0 or opacity > 100:
            raise BridgeOperationError("INVALID_INPUT", "opacity must be between 0 and 100")
        return _run_action(
            "layer_opacity",
            {
                "image": image,
                "layerIndex": int(params.get("layerIndex", -1)),
                "opacity": opacity,
                "output": _output_or_input(params, image),
            },
        )
    if method == "layer.blend_mode":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "layer-blend-mode")
        mode = str(params.get("mode", "")).strip()
        if not mode:
            raise BridgeOperationError("INVALID_INPUT", "mode is required")
        return _run_action(
            "layer_blend_mode",
            {
                "image": image,
                "layerIndex": int(params.get("layerIndex", -1)),
                "mode": mode,
                "output": _output_or_input(params, image),
            },
        )
    if method == "layer.merge_down":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "layer-merge-down")
        return _run_action(
            "layer_merge_down",
            {"image": image, "layerIndex": int(params.get("layerIndex", -1)), "output": _output_or_input(params, image)},
        )
    if method == "layer.duplicate":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "layer-duplicate")
        return _run_action(
            "layer_duplicate",
            {
                "image": image,
                "layerIndex": int(params.get("layerIndex", -1)),
                "position": int(params.get("position", int(params.get("layerIndex", 0)) + 1)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "layer.reorder":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "layer-reorder")
        return _run_action(
            "layer_reorder",
            {
                "image": image,
                "layerIndex": int(params.get("layerIndex", -1)),
                "index": int(params.get("index", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method in {"selection.all", "selection.none", "selection.invert"}:
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, method.replace(".", "-"))
        action = {
            "selection.all": "selection_all",
            "selection.none": "selection_none",
            "selection.invert": "selection_invert",
        }[method]
        return _run_action(action, {"image": image, "output": _output_or_input(params, image)})
    if method == "selection.feather":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "selection-feather")
        return _run_action(
            "selection_feather",
            {"image": image, "radius": float(params.get("radius", 5.0)), "output": _output_or_input(params, image)},
        )
    if method == "selection.rectangle":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "selection-rectangle")
        return _run_action(
            "selection_rectangle",
            {
                "image": image,
                "x": float(params.get("x", 0)),
                "y": float(params.get("y", 0)),
                "width": float(params.get("width", 0)),
                "height": float(params.get("height", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "selection.ellipse":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "selection-ellipse")
        return _run_action(
            "selection_ellipse",
            {
                "image": image,
                "x": float(params.get("x", 0)),
                "y": float(params.get("y", 0)),
                "width": float(params.get("width", 0)),
                "height": float(params.get("height", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "mask.add":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "mask-add")
        return _run_action(
            "mask_add",
            {
                "image": image,
                "layerIndex": _layer_index(params, -1),
                "mode": str(params.get("mode", "WHITE")),
                "output": _output_or_input(params, image),
            },
        )
    if method == "mask.apply":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "mask-apply")
        return _run_action(
            "mask_apply",
            {"image": image, "layerIndex": _layer_index(params, -1), "output": _output_or_input(params, image)},
        )
    if method == "text.add":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "text-add")
        return _run_action(
            "text_add",
            {
                "image": image,
                "text": str(params.get("text", "")),
                "x": int(params.get("x", 0)),
                "y": int(params.get("y", 0)),
                "font": str(params.get("font", "Sans")),
                "size": float(params.get("size", 36)),
                "color": params.get("color"),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "text.update":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "text-update")
        return _run_action(
            "text_update",
            {
                "image": image,
                "text": str(params.get("text", "")),
                "layerIndex": _layer_index(params, -1),
                "output": _output_or_input(params, image),
            },
        )
    if method == "annotation.stroke_selection":
        image = str(_require_path(str(params.get("image", ""))))
        _maybe_auto_snapshot(Path(image), params, "stroke-selection")
        return _run_action(
            "stroke_selection",
            {
                "image": image,
                "width": float(params.get("width", 1.0)),
                "color": params.get("color", "#ffffff"),
                "layerIndex": int(params.get("layerIndex", 0)),
                "output": _output_or_input(params, image),
            },
        )
    if method == "macro.run":
        image = str(_require_path(str(params.get("image", ""))))
        macro = params.get("macro")
        macro_params = params.get("params", {}) or {}
        macro_steps: List[Dict[str, Any]]
        if isinstance(macro, list):
            macro_steps = macro
        else:
            macro_path = _require_path(str(macro))
            macro_steps = json.loads(macro_path.read_text(encoding="utf-8"))
        if not isinstance(macro_steps, list):
            raise BridgeOperationError("INVALID_INPUT", "macro must be a list of steps")
        outputs = []
        for step in macro_steps:
            if not isinstance(step, dict) or "method" not in step:
                raise BridgeOperationError("INVALID_INPUT", "each macro step must contain method")
            step_method = str(step["method"])
            step_params = dict(step.get("params", {}))
            step_params.setdefault("image", image)
            for k, v in macro_params.items():
                step_params.setdefault(k, v)
            outputs.append({"method": step_method, "result": handle_method(step_method, step_params)})
        return {"steps": outputs}
    if method == "preset.list":
        return {"presets": sorted(PRESETS.keys())}
    if method == "preset.apply":
        image = str(_require_path(str(params.get("image", ""))))
        name = str(params.get("preset", "")).strip()
        if name not in PRESETS:
            raise BridgeOperationError("INVALID_INPUT", f"Unknown preset: {name}")
        results = []
        for step in PRESETS[name]:
            p = dict(step.get("params", {}))
            p.setdefault("image", image)
            p.setdefault("output", image)
            results.append({"method": step["method"], "result": handle_method(step["method"], p)})
        return {"preset": name, "results": results}
    raise BridgeOperationError("INVALID_INPUT", f"Unknown method: {method}")
