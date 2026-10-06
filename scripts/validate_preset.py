"""Run with Blender --background --factory-startup --python this_file."""
import json
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import zelda_preset
from zelda_preset import shading, scene_setup
zelda_preset.register()
scene = bpy.context.scene
checks = []
def check(condition, name):
    assert condition, name
    checks.append(name)

obj = bpy.data.objects['Cube']
original = obj.data.materials[0]
shared = obj.copy()
scene.collection.objects.link(shared)
shared.name = 'Unselected shared mesh'
before_nodes = len(original.node_tree.nodes)
settings = scene.zelda_daylight
outline = obj.modifiers.new('Character Outline', 'SOLIDIFY')
outline.show_render = True
outline.show_viewport = True
result = shading.apply_objects([obj], settings)
check(result['applied'] == 1, 'Principled conversion')
check(shared.material_slots[0].material == original, 'Unselected shared mesh unchanged')
derived = obj.material_slots[0].material
check(len(original.node_tree.nodes) == before_nodes, 'Original node graph unchanged')
check(not outline.show_render and not outline.show_viewport, 'Outline temporarily disabled')
g = derived.node_tree.nodes[shading.NODE_NAME]
check(g.inputs['Normal'].is_linked, 'Implicit surface normal explicitly supplied')
check(shading.apply_objects([obj], settings)['applied'] == 1 and obj.material_slots[0].material == derived,
      'Reapply is idempotent')
check(shading.restore_objects([obj]) == 1 and obj.material_slots[0].material == original,
      'Material restoration')
check(outline.show_render and outline.show_viewport, 'Outline restored')

bsdf = next(n for n in original.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
texture = original.node_tree.nodes.new('ShaderNodeTexImage')
bump = original.node_tree.nodes.new('ShaderNodeBump')
original.node_tree.links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
original.node_tree.links.new(texture.outputs['Alpha'], bsdf.inputs['Alpha'])
original.node_tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
shading.apply_objects([obj], settings)
group = obj.material_slots[0].material.node_tree.nodes[shading.NODE_NAME]
check(group.inputs['Base Color'].links[0].from_node.type == 'TEX_IMAGE', 'Base texture preserved')
check(group.inputs['Alpha'].links[0].from_socket.name == 'Alpha', 'Alpha texture preserved')
check(group.inputs['Normal'].links[0].from_node.type == 'BUMP', 'Normal input preserved')
shading.restore_objects([obj])
emission = bsdf.inputs['Emission Color']
strength = bsdf.inputs['Emission Strength']
strength.default_value = 1
emission.default_value = (.2, .5, .7, 1)
check(shading.apply_objects([obj], settings)['applied'] == 0, 'Emissive Principled safely skipped')
emission.default_value = (0, 0, 0, 1)
strength.default_value = 0
shading.restore_objects([obj])

old_world = scene.world
old_engine = scene.render.engine
old_lights = [(o, o.hide_render) for o in scene.objects if o.type == 'LIGHT']
old_comp = scene.compositing_node_group
scene_setup.apply(scene)
rig = settings.owned_collection
scene_setup.apply(scene)
check(settings.owned_collection == rig, 'Scene reapply does not duplicate rig')
check(scene.render.engine.startswith('BLENDER_EEVEE'), 'Eevee engine selected')
check(scene.compositing_node_group != old_comp, 'Isolated compositor tree')
scene_setup.restore(scene)
check(scene.world == old_world and scene.render.engine == old_engine,
      'World and render engine restoration')
check(scene.compositing_node_group == old_comp, 'Compositor restoration')
check(all(o.hide_render == state for o, state in old_lights), 'Original light visibility restoration')

# Save with live backup pointers; reload to verify restoration survives a .blend round trip.
shading.apply_objects([obj], settings)
scene_setup.apply(scene)
path = ROOT / 'output/validation_roundtrip.blend'
original_name = original.name
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
obj = bpy.data.objects['Cube']
check(shading.restore_objects([obj]) == 1 and obj.material_slots[0].material.name == original_name,
      'Persistent material backup after file reload')
scene_setup.restore(bpy.context.scene)
check(not bpy.context.scene.zelda_daylight.active, 'Persistent scene backup after file reload')
report = {'blender': bpy.app.version_string, 'startup': 'factory-startup', 'passed': checks}
(ROOT / 'output/validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print('VALIDATION PASSED', len(checks))
