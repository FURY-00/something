# Blender scripting guide

Scripts run inside Blender with `bpy`, `math` and `mathutils.Vector` available and the
helpers below already defined. Blender units: metres, angles in the helpers in degrees
(raw `rotation_euler` is radians), time in frames. Z is up. The default scene may contain
"Cube", "Camera" and "Light"; call `clear_scene()` when starting something new.

## Helpers (pre-loaded, prefer these)
- `clear_scene(keep_camera_and_lights=False)` delete objects to start fresh
- `obj(name)` get an object by name (raises with the list of names if missing)
- `add_object(kind, name=None, location=(0,0,0), size=1.0, rotation=(0,0,0), scale=None, segments=32)`
  kinds: cube, sphere, ico_sphere, cylinder, cone, plane, torus, monkey. size = edge length or diameter (m)
- `set_material(obj, color, metallic=0, roughness=0.5, emission=0, alpha=1)` color: 'red', '#ff8800' or (r,g,b)
- `smooth(obj, subdivisions=0)` smooth shading (+ subdivision surface)
- `add_modifier(obj, 'BEVEL', width=0.02, segments=3)`, `'ARRAY', count=5`, `'SOLIDIFY', thickness=0.1`, `'MIRROR'`...
- `set_timeline(start=1, end=120, fps=24)`
- `keyframe(obj, frame, location=None, rotation=None, scale=None)` rotation in degrees
- `set_interpolation(obj, 'LINEAR'|'BEZIER'|'SINE'|'BOUNCE'|'ELASTIC'|'CONSTANT', easing='EASE_IN_OUT')`
- `fcurves(obj)` the object's animation curves (handles Blender 4.4+/5.x layered actions)
- `add_camera(location=(7,-7,5), look_at=(0,0,0), lens=50)` also sets it as the scene camera
- `point_at(obj, target)` aim a camera/light at a point or object name
- `add_light(kind='AREA'|'SUN'|'POINT'|'SPOT', location, energy=None, color_value='white', size=2, look_at=(0,0,0))`
- `add_text(text, location, size=1, extrude=0.05, rotation=(90,0,0))` 3D text facing -Y (the default camera side)
- `set_world(color, strength=1)` background colour/lighting
- `render_settings(engine='eevee'|'cycles'|'workbench', resolution=(1920,1080), samples=64)`
- `render_image(path, frame=None)` PNG still; returns the path
- `render_animation(path, background=True)` MP4 (H.264) of the timeline; renders in a separate process, Jarvis announces when done
- `save_blend(path)`, `show_in_blender()` (opens the scene in the Blender window), `scene_summary()`

Save outputs under the user's projects folder (given in the task) or `~/Documents/Jarvis/Projects/blender/`.

## API essentials
- Objects: `bpy.data.objects`, `bpy.context.scene.objects`; delete with `bpy.data.objects.remove(o, do_unlink=True)`
- Transform: `o.location = (x, y, z)`, `o.rotation_euler = (math.radians(a), ...)`, `o.scale`, `o.dimensions`
- Parent: `child.parent = parent`. Duplicate: `new = o.copy(); new.data = o.data.copy(); bpy.context.scene.collection.objects.link(new)`
- Materials: node-based; `mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'|'Metallic'|'Roughness'|'Transmission Weight'|'Alpha'|'Emission Color'|'Emission Strength']`
  (Blender 4+ names). Glass: Transmission Weight 1, Roughness 0. Metal: Metallic 1, Roughness 0.2-0.4.
- Modifiers: `o.modifiers.new(name, 'SUBSURF'|'BEVEL'|'ARRAY'|'BOOLEAN'|'SOLIDIFY'|'MIRROR'|'SCREW'|'DISPLACE')`
  Boolean: `m = a.modifiers.new('Cut', 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.object = b; b.hide_render = True; b.display_type = 'WIRE'`
- Keyframes on any property: `o.keyframe_insert('location', frame=10)`, `mat.node_tree.nodes[...].inputs[...].keyframe_insert('default_value', frame=1)`
- Follow path: `curve = bpy.data.curves.new('Path', 'CURVE')`... or constraints: `c = o.constraints.new('TRACK_TO'); c.target = obj('Target')`
- Camera orbit: parent the camera to an Empty at the centre (`e = bpy.data.objects.new('Orbit', None)`, link it) and keyframe the Empty's Z rotation 0 -> 360
- Physics: `bpy.ops.rigidbody.world_add()` then `bpy.context.view_layer.objects.active = o; bpy.ops.rigidbody.object_add(type='ACTIVE'|'PASSIVE')`
- Frame: `scene.frame_set(n)`; fps: `scene.render.fps`
- Mesh from data: `mesh = bpy.data.meshes.new('M'); mesh.from_pydata(verts, [], faces); o = bpy.data.objects.new('M', mesh)` then link it
- Import/export: `bpy.ops.wm.obj_import(filepath=...)`, `bpy.ops.wm.stl_import(filepath=...)`, `bpy.ops.import_scene.gltf(filepath=...)`,
  `bpy.ops.wm.obj_export(filepath=...)`, `bpy.ops.export_scene.gltf(filepath=...)`, `bpy.ops.wm.stl_export(filepath=...)`
- Eevee is fast; Cycles is photoreal but slow on a CPU (keep samples 32-128 for previews)

## Recipe: bouncing ball animation
```python
clear_scene()
add_object("plane", "Floor", size=20); set_material("Floor", "grey", roughness=0.9)
ball = add_object("sphere", "Ball", location=(0, 0, 4), size=1); set_material(ball, "red", roughness=0.3); smooth(ball, 1)
set_timeline(1, 96, 24)
for f, z in [(1, 4), (24, 0.5), (48, 3), (72, 0.5), (96, 2)]:
    keyframe(ball, f, location=(0, 0, z))
set_interpolation(ball, "SINE", "EASE_IN_OUT")
add_camera(location=(8, -8, 4), look_at=(0, 0, 1.5)); add_light("SUN", energy=4)
render_settings("eevee", resolution=(1280, 720))
print(render_animation("~/Documents/Jarvis/Projects/blender/bouncing_ball.mp4"))
```

## Recipe: product turntable (spin an object 360 degrees)
```python
target = obj("Product")  # or build one
add_light("AREA", location=(3, -3, 4), energy=800); add_light("AREA", location=(-4, 2, 3), energy=300)
set_timeline(1, 120, 30)
keyframe(target, 1, rotation=(0, 0, 0)); keyframe(target, 120, rotation=(0, 0, 360))
set_interpolation(target, "LINEAR")
add_camera(location=(0, -6, 2), look_at=target.location)
```

## Recipe: animated 3D title text
```python
t = add_text("HELLO", location=(0, 0, 0), size=1.5, extrude=0.1)
set_material(t, "gold", metallic=1, roughness=0.25)
set_timeline(1, 60, 30)
keyframe(t, 1, scale=0.01); keyframe(t, 30, scale=1.2); keyframe(t, 40, scale=1.0)
set_interpolation(t, "BACK", "EASE_OUT")
add_camera(location=(0, -8, 0.5), look_at=(0, 0, 0))
```

## Recipe: solar system / orbiting objects
Parent each planet to an Empty at the origin, offset the planet along X by its orbit
radius, then keyframe the Empty's Z rotation from 0 to 360 over the orbit period (frames).
Emissive sun: `set_material(sun, "orange", emission=20)`. Dark world: `set_world((0,0,0), 0)`.

## Recipe: hollow shapes and holes (booleans)
Make the main body, make a cutter (cylinder for a hole), add a BOOLEAN DIFFERENCE modifier to
the body with the cutter as object, hide the cutter in renders. Apply it with
`bpy.context.view_layer.objects.active = body; bpy.ops.object.modifier_apply(modifier='Cut')`.

## GUI: add and move an object
1. Move the mouse over the 3D viewport, press Shift+A, choose Mesh, then the shape.
2. Press G to move, R to rotate, S to scale; type a number and Enter for exact values (G Z 2 Enter moves up 2 m).
3. The N panel (press N) shows exact location, rotation and scale.

## GUI: animate with keyframes
1. Go to frame 1 on the timeline, select the object, press I and choose Location (or Location & Rotation).
2. Move to a later frame, move the object, press I again.
3. Press Space to play. Change easing in the Graph Editor: select keys, press T, choose the interpolation.

## GUI: render a video
1. Output Properties (printer icon): set frame start/end, resolution and frame rate.
2. Under Output, set the folder and File Format to FFmpeg Video, Container MPEG-4, Codec H.264.
3. Render menu > Render Animation (Ctrl+F12).

## GUI: materials
1. Select the object, open Material Properties (red sphere icon), click New.
2. Change Base Color, Metallic and Roughness. For glass set Transmission Weight to 1.
3. Switch the viewport to Material Preview (Z key) to see it.
