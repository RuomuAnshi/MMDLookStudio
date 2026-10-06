"""Build a packed, local-only hair-line comparison from a named MMD mesh."""
import argparse
import bpy
import json
import os
import sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import shading
zelda_preset.register()
parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path)
parser.add_argument('object')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.open_mainfile(filepath=str(args.source))
scene=bpy.context.scene
obj=bpy.data.objects[args.object]
# The comparison deliberately starts from the saved source material snapshot,
# even when this separate source project has subsequently edited its materials.
# This background process writes only the new demonstration in this workspace.
for backup in obj.zelda_slot_backups:
    if backup.index < len(obj.material_slots) and backup.material:
        slot=obj.material_slots[backup.index]
        slot.link='OBJECT'
        slot.material=backup.material
obj.zelda_slot_backups.clear()
for o in scene.objects:
    if o.type not in {'LIGHT','CAMERA'}:
        o.hide_render = o != obj
obj.hide_render=False
obj.hide_viewport=False
obj.hide_set(False)
images=set()
for slot in obj.material_slots:
    if not slot.material or not slot.material.node_tree: continue
    for node in slot.material.node_tree.nodes:
        if node.type=='TEX_IMAGE' and node.image:
            images.add(node.image)
for image in images:
    if image.source=='FILE' and not image.packed_file:
        normalized=Path(os.path.normpath(bpy.path.abspath(image.filepath)))
        if normalized.exists():
            image.filepath=str(normalized)
            image.reload()
            image.pack()
positions=[obj.matrix_world@v.co for v in obj.data.vertices]
lo=Vector([min(v[i] for v in positions) for i in range(3)])
hi=Vector([max(v[i] for v in positions) for i in range(3)])
center=(lo+hi)*.5
camera_data=bpy.data.cameras.new('ZD · Black-edge comparison camera')
camera=bpy.data.objects.new(camera_data.name,camera_data)
scene.collection.objects.link(camera)
camera.location=center+Vector((0,-3,.02))
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.type='ORTHO'
camera_data.ortho_scale=max(hi.x-lo.x,hi.z-lo.z)*1.15
scene.camera=camera
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=scene.render.resolution_y=960
scene.render.resolution_percentage=100
scene.render.image_settings.media_type='IMAGE'
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGBA'
scene.render.use_compositing=False
scene.render.use_sequencer=False
scene.render.film_transparent=False
scene.view_settings.view_transform='Standard'
scene.view_settings.look='None'
scene.view_settings.exposure=-.12
scene.eevee.taa_render_samples=48
settings=scene.zelda_daylight
settings.role='AUTO'
settings.hair_outline_material=next((s.material for s in obj.material_slots if s.material and s.material.name == '头_Outline'),None)
settings.hair_hide_outline=False
settings.hair_clean_lines=False
before_result=shading.apply_objects([obj],settings)
scene.render.filepath=str(ROOT/'output/hair_edges_before.png')
bpy.ops.render.render(write_still=True)
settings.hair_hide_outline=True
settings.hair_clean_lines=True
after_result=shading.apply_objects([obj],settings)
repairs=[s.material.name for s in obj.material_slots if s.material and s.material.get('zd_line_repair')=='active']
assert repairs,after_result
scene.render.filepath=str(ROOT/'output/hair_edges_after.png')
bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active=obj
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/王国白昼_黑边修复演示.blend'))
report={'model':obj.name,'repair_materials':repairs,'packed_images':sum(bool(i.packed_file) for i in images),
        'hidden_outline_materials':[s.material.name for s in obj.material_slots if s.material and s.material.get('zd_hidden_hair_outline')],
        'applied':after_result['applied'],'skipped_count':len(after_result['skipped']),'resolution':[960,960]}
(ROOT/'output/line_mmd_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('PACKED LINE DEMO COMPLETE',json.dumps(report,ensure_ascii=False))
