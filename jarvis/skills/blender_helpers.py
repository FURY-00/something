"""Helper functions pre-loaded into every Blender script Jarvis runs.

This file runs *inside Blender* (it only needs bpy), so it must not import
anything from Jarvis. Tested with Blender 4.x and 5.0.
"""

import json
import math
import os
import subprocess
import tempfile

import bpy
from mathutils import Vector

JARVIS_HELPERS_VERSION = 1

COLORS = {
    "red": (0.8, 0.03, 0.03), "green": (0.05, 0.6, 0.1), "blue": (0.03, 0.15, 0.8),
    "yellow": (0.9, 0.75, 0.05), "orange": (0.9, 0.3, 0.02), "purple": (0.4, 0.05, 0.6),
    "pink": (0.9, 0.3, 0.5), "white": (0.9, 0.9, 0.9), "black": (0.02, 0.02, 0.02),
    "grey": (0.4, 0.4, 0.4), "gray": (0.4, 0.4, 0.4), "gold": (0.95, 0.65, 0.2),
    "silver": (0.8, 0.8, 0.82), "brown": (0.3, 0.15, 0.05), "cyan": (0.05, 0.6, 0.7),
}


def color(value):
    """'red', '#ff8800' or (r, g, b) -> (r, g, b, 1)."""
    if isinstance(value, str):
        v = value.strip().lower()
        if v.startswith("#") and len(v) == 7:
            rgb = tuple(int(v[i:i + 2], 16) / 255 for i in (1, 3, 5))
            rgb = tuple(c ** 2.2 for c in rgb)  # sRGB -> linear
        else:
            rgb = COLORS.get(v, (0.8, 0.8, 0.8))
    else:
        rgb = tuple(value)[:3]
    return (*rgb, 1.0)


def obj(name_or_obj):
    """Get an object by name (or pass an object straight through)."""
    if isinstance(name_or_obj, str):
        found = bpy.data.objects.get(name_or_obj)
        if found is None:
            raise KeyError(f"No object called {name_or_obj!r}. Objects: {[o.name for o in bpy.data.objects]}")
        return found
    return name_or_obj


def clear_scene(keep_camera_and_lights=False):
    """Delete objects (and their unused data) to start from an empty scene."""
    for o in list(bpy.data.objects):
        if keep_camera_and_lights and o.type in ("CAMERA", "LIGHT"):
            continue
        bpy.data.objects.remove(o, do_unlink=True)
    for data in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.cameras,
                 bpy.data.lights, bpy.data.actions):
        for block in list(data):
            if block.users == 0:
                data.remove(block)


def _link(o):
    bpy.context.scene.collection.objects.link(o)
    return o


def add_object(kind="cube", name=None, location=(0, 0, 0), size=1.0, rotation=(0, 0, 0),
               scale=None, segments=32):
    """Add a primitive: cube, sphere, ico_sphere, cylinder, cone, plane, torus, monkey.

    size is the overall size in metres (edge length for a cube/plane, diameter for
    round things). rotation is in degrees.
    """
    import bmesh

    kind = kind.lower().replace(" ", "_")
    mesh = bpy.data.meshes.new(name or kind.capitalize())
    bm = bmesh.new()
    r = size / 2
    if kind == "cube":
        bmesh.ops.create_cube(bm, size=size)
    elif kind in ("sphere", "uv_sphere"):
        bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=r)
    elif kind == "ico_sphere":
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r)
    elif kind in ("cylinder", "cone"):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r,
                              radius2=r if kind == "cylinder" else 0, depth=size)
    elif kind == "plane":
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=r)
    elif kind == "torus":
        bm.free()
        bpy.ops.mesh.primitive_torus_add(major_radius=r * 0.75, minor_radius=r * 0.25,
                                         location=location)
        o = bpy.context.active_object
        if name:
            o.name = name
        _place(o, location, rotation, scale)
        return o
    elif kind in ("monkey", "suzanne"):
        bmesh.ops.create_monkey(bm)
        bmesh.ops.scale(bm, vec=(r, r, r), verts=bm.verts)
    else:
        bm.free()
        raise ValueError(f"Unknown primitive {kind!r}")
    bm.to_mesh(mesh)
    bm.free()
    o = _link(bpy.data.objects.new(name or kind.capitalize(), mesh))
    _place(o, location, rotation, scale)
    return o


def _place(o, location, rotation, scale):
    o.location = location
    o.rotation_euler = [math.radians(a) for a in rotation]
    if scale is not None:
        o.scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale


def set_material(target, color_value="grey", metallic=0.0, roughness=0.5, emission=0.0,
                 alpha=1.0, name=None):
    """Give an object a simple principled material."""
    o = obj(target)
    mat = bpy.data.materials.new(name or f"{o.name} material")
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    rgba = color(color_value)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Alpha"].default_value = alpha
    if emission:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emission
    mat.diffuse_color = rgba  # what the solid viewport shows
    if o.data is not None and hasattr(o.data, "materials"):
        o.data.materials.clear()
        o.data.materials.append(mat)
    return mat


def smooth(target, subdivisions=0):
    """Smooth shading, optionally with a subdivision surface modifier."""
    o = obj(target)
    for poly in getattr(o.data, "polygons", []):
        poly.use_smooth = True
    if subdivisions:
        mod = o.modifiers.new("Subdivision", "SUBSURF")
        mod.levels = mod.render_levels = subdivisions
    return o


def add_modifier(target, kind, **settings):
    """e.g. add_modifier('Cube', 'BEVEL', width=0.05, segments=3) or 'ARRAY', count=5."""
    o = obj(target)
    mod = o.modifiers.new(kind.title(), kind.upper())
    for key, value in settings.items():
        setattr(mod, key, value)
    return mod


def set_timeline(start=1, end=120, fps=24):
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = start, end
    scene.render.fps = fps


def keyframe(target, frame, location=None, rotation=None, scale=None):
    """Keyframe location / rotation (degrees) / scale of an object at a frame."""
    o = obj(target)
    if location is not None:
        o.location = location
        o.keyframe_insert("location", frame=frame)
    if rotation is not None:
        o.rotation_euler = [math.radians(a) for a in rotation]
        o.keyframe_insert("rotation_euler", frame=frame)
    if scale is not None:
        o.scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale
        o.keyframe_insert("scale", frame=frame)


def fcurves(target):
    """All animation curves of an object (works with old and new Blender actions)."""
    o = obj(target)
    ad = o.animation_data
    if not ad or not ad.action:
        return []
    action = ad.action
    try:
        from bpy_extras import anim_utils

        bag = anim_utils.action_get_channelbag_for_slot(action, ad.action_slot)
        if bag is not None:
            return list(bag.fcurves)
    except (ImportError, AttributeError):
        pass
    return list(getattr(action, "fcurves", []))


def set_interpolation(target, mode="LINEAR", easing=None):
    """LINEAR, BEZIER, CONSTANT, BOUNCE, ELASTIC, SINE... for all keys of an object."""
    for fc in fcurves(target):
        for kp in fc.keyframe_points:
            kp.interpolation = mode.upper()
            if easing:
                kp.easing = easing.upper()


def add_camera(location=(7, -7, 5), look_at=(0, 0, 0), lens=50, name="Camera"):
    cam = _link(bpy.data.objects.new(name, bpy.data.cameras.new(name)))
    cam.data.lens = lens
    cam.location = location
    point_at(cam, look_at)
    bpy.context.scene.camera = cam
    return cam


def point_at(target, where):
    """Rotate an object (camera, light) to face a point or another object."""
    o = obj(target)
    goal = obj(where).location if isinstance(where, str) else Vector(where)
    direction = Vector(goal) - o.location
    o.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_light(kind="AREA", location=(4, -4, 6), energy=None, color_value="white", size=2.0,
              look_at=(0, 0, 0), name=None):
    """kind: SUN, POINT, SPOT, AREA. energy in watts (sun: strength)."""
    kind = kind.upper()
    data = bpy.data.lights.new(name or f"{kind.title()} light", kind)
    data.energy = energy if energy is not None else {"SUN": 3, "POINT": 1000, "SPOT": 1000, "AREA": 500}[kind]
    data.color = color(color_value)[:3]
    if kind == "AREA":
        data.size = size
    light = _link(bpy.data.objects.new(data.name, data))
    light.location = location
    point_at(light, look_at)
    return light


def add_text(text, location=(0, 0, 0), size=1.0, extrude=0.05, name="Text", rotation=(90, 0, 0)):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body = text
    curve.size = size
    curve.extrude = extrude
    curve.align_x = "CENTER"
    t = _link(bpy.data.objects.new(name, curve))
    _place(t, location, rotation, None)
    return t


def set_world(color_value=(0.05, 0.05, 0.07), strength=1.0):
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    if hasattr(world, "use_nodes") and not world.use_nodes:
        world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs["Color"].default_value = color(color_value)
        bg.inputs["Strength"].default_value = strength


def _engine_id(engine):
    available = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    wanted = {"eevee": ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"], "cycles": ["CYCLES"],
              "workbench": ["BLENDER_WORKBENCH"]}.get(engine.lower(), [engine.upper()])
    for w in wanted:
        if w in available:
            return w
    if engine.lower() == "cycles":
        return "CYCLES"  # Cycles registers itself lazily
    return available[0]


def render_settings(engine="eevee", resolution=(1920, 1080), samples=64, percentage=100):
    scene = bpy.context.scene
    scene.render.engine = _engine_id(engine)
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = percentage
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.device = "CPU"
    elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = samples


def _output_path(path, ext):
    path = os.path.abspath(os.path.expanduser(path))
    if not path.lower().endswith(ext):
        path += ext
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def render_image(path, frame=None):
    """Render a still image to a PNG file."""
    scene = bpy.context.scene
    path = _output_path(path, ".png")
    if frame is not None:
        scene.frame_set(frame)
    settings = scene.render.image_settings
    if hasattr(settings, "media_type"):
        settings.media_type = "IMAGE"
    settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered image: {path}")
    return path


def _video_settings(scene, path):
    settings = scene.render.image_settings
    if hasattr(settings, "media_type"):  # Blender 5.0+
        settings.media_type = "VIDEO"
    settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.audio_codec = "AAC"
    # The path ends in ".mp4", so Blender uses it as-is instead of adding frame numbers.
    scene.render.use_file_extension = True
    scene.render.filepath = path


def render_animation(path, background=True):
    """Render the timeline to an MP4 video.

    With background=True (default) Blender renders in a separate process so you
    can keep working, and Jarvis announces when the video is ready.
    """
    scene = bpy.context.scene
    path = _output_path(path, ".mp4")
    _video_settings(scene, path)
    exe = bpy.app.binary_path
    is_blender = bool(exe) and "blender" in os.path.basename(exe).lower()
    if background and is_blender:
        blend = os.path.join(tempfile.gettempdir(), "jarvis_render.blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
        proc = subprocess.Popen([exe, "-b", blend, "-a"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        frames = scene.frame_end - scene.frame_start + 1
        print(f"Rendering {frames} frames in the background to {path}")
        print("JARVIS_BACKGROUND " + json.dumps({"name": "animation render", "pid": proc.pid,
                                                 "output": path}))
        return path
    bpy.ops.render.render(animation=True)
    print(f"Rendered animation: {path}")
    return path


def save_blend(path):
    path = _output_path(path, ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print(f"Saved Blender file: {path}")
    return path


def show_in_blender():
    """Ask Jarvis to open the current scene in the Blender window."""
    print("JARVIS_SHOW_BLENDER")


def scene_summary():
    scene = bpy.context.scene
    lines = [
        f"Scene '{scene.name}', frames {scene.frame_start}-{scene.frame_end} at {scene.render.fps} fps, "
        f"engine {scene.render.engine}, resolution {scene.render.resolution_x}x{scene.render.resolution_y}, "
        f"camera: {scene.camera.name if scene.camera else 'none'}",
        f"File: {bpy.data.filepath or '(unsaved)'}",
    ]
    for o in scene.objects:
        loc = ", ".join(f"{v:.2f}" for v in o.location)
        dims = ", ".join(f"{v:.2f}" for v in o.dimensions)
        mats = [m.name for m in getattr(o.data, "materials", []) if m] if o.data else []
        anim = " animated" if o.animation_data and o.animation_data.action else ""
        mods = [m.type for m in o.modifiers]
        lines.append(f"- {o.name} ({o.type}) at ({loc}) size ({dims})"
                     + (f" materials {mats}" if mats else "") + (f" modifiers {mods}" if mods else "")
                     + anim)
    if len(scene.objects) == 0:
        lines.append("- (no objects)")
    return "\n".join(lines)
