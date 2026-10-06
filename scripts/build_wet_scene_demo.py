"""User scene comparison saved as private copies; never overwrites the original."""
import bpy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import shading,scene_setup
zelda_preset.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/backups/pre_wet_20261005/当前场景_修改前.blend'))
# The user's original file lives on NAS; resolve its relative images in this private copy.
import os
for image in bpy.data.images:
 if image.source=='FILE' and not image.packed_file:
  filename=image.filepath
  candidate=Path(os.path.normpath('/Volumes/NAS/Blender/'+filename[2:])) if filename.startswith('//') else Path(filename)
  if candidate.exists():
   image.filepath=str(candidate);image.reload();image.pack()
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/backups/pre_wet_20261005/当前场景_修改前.blend'),copy=True)
s=bpy.context.scene;settings=s.zelda_daylight
o=bpy.data.objects['鸣潮_女漂泊者1.023_mesh']
s.render.resolution_percentage=50;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
s.render.image_settings.media_type='IMAGE';s.render.use_sequencer=False
s.eevee.taa_render_samples=64
s.render.filepath=str(ROOT/'output/wet_scene_before.png');bpy.ops.render.render(write_still=True)
settings.role='AUTO';settings.wet_enabled=False
scene_setup.restore(s)
result=shading.apply_objects([o],settings);scene_setup.apply(s,[o])
s.render.filepath=str(ROOT/'output/wet_scene_improved_dry.png');bpy.ops.render.render(write_still=True)
settings.wet_enabled=True
s.render.filepath=str(ROOT/'output/wet_scene_improved_wet.png');bpy.ops.render.render(write_still=True)
for image in bpy.data.images:
 if image.source=='FILE' and image.has_data and not image.packed_file:
  try:image.pack()
  except RuntimeError:pass
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/冷暖逆光_水渍_女漂演示.blend'))
report={'version':'0.3.2','applied':result['applied'],'skipped':result['skipped'],
        'hair':[slot.material.get('zd_original_name') for slot in o.material_slots if slot.material and slot.material.get('zd_role')=='HAIR'],
        'wet':[slot.material.get('zd_original_name') for slot in o.material_slots if slot.material and slot.material.get('mr_wet_active')],
        'camera':s.camera.name,'dof':s.camera.data.dof.use_dof,'resolution':[540,960]}
(ROOT/'output/wet_scene_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('WET SCENE DEMO COMPLETE',json.dumps(report,ensure_ascii=False))
