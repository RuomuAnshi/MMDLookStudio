"""Render and validate directional hair on the existing local MMD demonstration."""
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import zelda_preset
from zelda_preset import shading, hair, scene_setup
zelda_preset.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/王国白昼_MMD演示.blend'))
scene = bpy.context.scene
settings = scene.zelda_daylight
model = next(o for o in scene.objects if o.type == 'MESH' and len(o.zelda_slot_backups) == 49)
model_name = model.name
hair_materials = [slot.material for slot in model.material_slots if shading.classify(slot.material) == 'HAIR']
other_materials = {slot.material.name: slot.material.node_tree.as_pointer()
                   for slot in model.material_slots if shading.classify(slot.material) != 'HAIR'}
originals = [(b.index, b.material.as_pointer()) for b in model.zelda_slot_backups]
checks = []
def check(condition, message):
    assert condition, message
    checks.append(message)

scene.camera.location = (0, -2.0, 1.47)
scene.camera.rotation_euler = (Vector((0,.03,1.26))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
scene.camera.data.lens = 62
scene.render.resolution_x = scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'PNG'
scene.render.use_sequencer = False
scene.eevee.taa_render_samples = 48
settings.hair_enabled = False
shading.apply_objects([model], settings)
scene.render.filepath = str(ROOT/'output/hair_before.png')
bpy.ops.render.render(write_still=True)

settings.hair_enabled = True
shading.apply_objects([model], settings)
check(len(hair_materials) == 6, 'Six real MMD hair materials upgraded')
check(all(m.node_tree.nodes[shading.NODE_NAME].node_tree.get('zd_hair_version') == 1 for m in hair_materials),
      'Dedicated native hair node group')
check([(b.index,b.material.as_pointer()) for b in model.zelda_slot_backups] == originals,
      'Original MMD material backup pointers preserved')
check(all(bpy.data.materials[name].node_tree.as_pointer() == pointer for name,pointer in other_materials.items()),
      'Non-hair node trees preserved')
g = hair_materials[0].node_tree.nodes[shading.NODE_NAME]
check(all(g.inputs[name].is_linked for name in ('Base Color','Alpha','Normal','Hair Tangent')),
      'MMD base color alpha normal and tangent preserved')
count = len(hair_materials[0].node_tree.nodes)
shading.apply_objects([model], settings)
check(len(hair_materials[0].node_tree.nodes) == count, 'Reapply creates no extra hair nodes')
sun = hair.choose_sun(scene)
check(sun is not None, 'Scene sun automatically selected')
bpy.context.view_layer.update()
expected = sun.matrix_world.to_quaternion() @ Vector((0,0,1))
actual = Vector(g.inputs['Light Direction'].default_value)
check((expected-actual).length < 1e-5, 'Sun direction drivers match world rotation')
before = actual.copy()
rotation = sun.rotation_euler.copy()
sun.rotation_euler.z += math.radians(45)
bpy.context.view_layer.update()
check((before-Vector(g.inputs['Light Direction'].default_value)).length > .1,
      'Sun rotation updates the hair driver')
sun.data.energy = 0
bpy.context.view_layer.update()
check(abs(g.inputs['Light Strength'].default_value) < 1e-6, 'Zero-energy sun suppresses band')
sun.data.energy = 2.2
sun.rotation_euler = rotation
bpy.context.view_layer.update()

mask = bpy.data.images.new('ZD Test mask', width=2, height=2)
mask.colorspace_settings.name = 'Non-Color'
mask.generated_color = (0,0,0,1)
settings.hair_mask = mask
settings.hair_flow_map = mask
shading.apply_objects([model], settings)
g = hair_materials[0].node_tree.nodes[shading.NODE_NAME]
check(g.inputs['Hair Mask'].is_linked and any(n.type=='TEX_IMAGE' and n.image == mask
          for n in hair_materials[0].node_tree.nodes), 'Optional image mask connected')
check(any(n.name == hair.PREFIX+'Mapped flow' for n in hair_materials[0].node_tree.nodes),
      'Optional RG flow map connected')
settings.hair_mask = settings.hair_flow_map = None
shading.apply_objects([model], settings)
bpy.data.images.remove(mask)
for direction in ('UV_U','UV_V','OBJECT_Z'):
    settings.hair_direction = direction
    shading.apply_objects([model], settings)
    check(g.inputs['Hair Tangent'].is_linked, direction+' direction supported')
settings.hair_direction = 'OBJECT_Z'
shading.apply_objects([model], settings)
settings.hair_enabled = False
shading.apply_objects([model], settings)
check(g.node_tree == shading.ensure_group() and not hair_materials[0].node_tree.animation_data.drivers,
      'Disable returns to generic shader without dangling drivers')
settings.hair_enabled = True
shading.apply_objects([model], settings)
scene.render.filepath = str(ROOT/'output/hair_after.png')
bpy.context.preferences.filepaths.save_version = 0
path = ROOT/'output/王国白昼_头发演示.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.render.render(write_still=True)
strength = settings.hair_strength
settings.hair_strength = 0
shading.apply_objects([model], settings)
scene.render.filepath = '/private/tmp/zelda-hair-band-disabled.png'
bpy.ops.render.render(write_still=True)
def pixels(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    values = np.empty(len(image.pixels),dtype=np.float32)
    image.pixels.foreach_get(values)
    bpy.data.images.remove(image)
    return values.reshape((-1,4))[:,:3]
delta = np.abs(pixels(ROOT/'output/hair_after.png')-pixels(scene.render.filepath)).max(axis=1)
visible_band_pixels = int((delta > .02).sum())
check(visible_band_pixels > 500, 'Directional band visibly affects the rendered hair')
settings.hair_strength = strength
shading.apply_objects([model], settings)
sun.rotation_euler.z += math.radians(45)
scene.render.filepath = str(ROOT/'output/hair_sun_rotated.png')
bpy.ops.render.render(write_still=True)
bpy.ops.wm.open_mainfile(filepath=str(path))
scene = bpy.context.scene
model = bpy.data.objects[model_name]
g = next(s.material.node_tree.nodes[shading.NODE_NAME] for s in model.material_slots
         if s.material.get('zd_role') == 'HAIR')
bpy.context.view_layer.update()
check(all(d.driver.is_valid and d.driver.is_simple_expression for d in g.id_data.animation_data.drivers),
      'Simple built-in drivers survive file reload')
scene_setup.restore(scene)
check(g.inputs['Light Strength'].default_value == 0 and not g.id_data.animation_data.drivers,
      'Environment restoration safely unbinds removed sun')
scene_setup.apply(scene)
bpy.context.view_layer.update()
check(g.inputs['Light Strength'].default_value > 0 and all(d.driver.is_valid for d in g.id_data.animation_data.drivers),
      'New daylight sun automatically rebinds existing hair')
check(shading.restore_objects([model]) == 49, 'All 49 MMD material slots restore after reload')
scene_setup.restore(scene)
check(not scene.zelda_daylight.active, 'Scene environment restores after reload')
report = {'version':'0.2.0','blender':bpy.app.version_string,'startup':'factory-startup',
          'hair_materials':6,'resolution':[960,960], 'visible_band_pixels':visible_band_pixels,'passed':checks}
(ROOT/'output/hair_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('HAIR VALIDATION PASSED', len(checks))
