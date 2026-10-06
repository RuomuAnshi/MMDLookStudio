"""Actual actor render, normalized cheek masks, shared data safety and restoration."""
import bpy,sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import blush,shading,face
zelda_preset.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/冷暖逆光_水渍_女漂演示.blend'))
scene=bpy.context.scene;s=scene.zelda_daylight;o=bpy.data.objects['鸣潮_女漂泊者1.023_mesh']
scene.render.resolution_percentage=100;scene.render.use_border=True;scene.render.use_crop_to_border=True
scene.render.border_min_x=.15;scene.render.border_max_x=.64;scene.render.border_min_y=.66;scene.render.border_max_y=.93
scene.render.use_compositing=False;scene.render.film_transparent=True
checks=[]
def check(ok,name):
 assert ok,name
 checks.append(name)
def render(name):
 scene.render.filepath=str(ROOT/'output'/name);bpy.ops.render.render(write_still=True)
 image=bpy.data.images.load(scene.render.filepath,check_existing=False);pixels=np.array(image.pixels[:],dtype=np.float32).reshape(-1,4).copy();bpy.data.images.remove(image);return pixels
s.blush_enabled=False;before=render('blush_before.png')
s.blush_enabled=True;after=render('blush_after.png')
check(np.max(abs(before[:,:3]-after[:,:3]))>.02,'Visible real-model cheek tint')
check(np.max(abs(before[:,3]-after[:,3]))<1e-5,'Rendered alpha unchanged')
active=[slot.material for slot in o.material_slots if slot.material and slot.material.get('mr_blush_active')]
check(active and all(blush.eligible(m,s) for m in active),'Only face materials tinted')
check(all(not slot.material.get('mr_blush_active') for slot in o.material_slots if slot.material and not blush.eligible(slot.material,s)),'Body hair eyes clothing protected')
attr=o.data.attributes[blush.ATTRIBUTE];values=np.array([v.value for v in attr.data]);check(values.max()>.4 and values.min()==0,'Localized cheek mask')
original=o.data.vertices[0].co.copy();o.location.x+=1;s.blush_amount=.7
check(o.data.vertices[0].co==original,'Mesh geometry unchanged');o.location.x-=1
s.blush_enabled=False;disabled=render('blush_disabled.png');check(np.max(abs(before-disabled))<1e-5,'Disable restores exact baseline pixels')
s.blush_enabled=True
m=active[0];blush.update_settings(s,bpy.context);blush.update_settings(s,bpy.context)
check(sum(n.name==blush.PREFIX+'Tint' for n in m.node_tree.nodes)==1,'No duplicate tint nodes')
s.face_softness=.7
check(m.node_tree.nodes['MR · Face Layer'].inputs['Base Color'].links[0].from_node.name==blush.PREFIX+'Tint','Soft face updates retain cheek tint')
s.wet_face=True
check(m.get('mr_wet_active') and m.get('mr_blush_active'),'Face water combines with blush');s.wet_face=False;s.face_softness=.85
# A second instance with a radically different object scale uses the same rest mask.
other=o.copy();other.data=o.data.copy();scene.collection.objects.link(other);other.hide_render=True;other.scale=(3,3,3)
for layer in list(other.data.uv_layers):other.data.uv_layers.remove(layer)
blush.prepare(other,s)
check(np.max(abs(np.array([v.value for v in other.data.attributes[blush.ATTRIBUTE].data])-np.array([v.value for v in o.data.attributes[blush.ATTRIBUTE].data])))<1e-6,'Cheeks independent of object size, position and UV layout')
bpy.data.objects.remove(other,do_unlink=True)
evaluated=o.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
check(mesh.attributes.get(blush.ATTRIBUTE) is not None and max(v.value for v in mesh.attributes[blush.ATTRIBUTE].data)>.4,'Cheek mask survives actual actor modifiers and armature')
evaluated.to_mesh_clear()
mask=bpy.data.images.new('Blush black mask',width=2,height=2);mask.pixels[:]=[0,0,0,1]*4
s.blush_mask=mask;masked=render('blush_masked.png');check(np.max(abs(before-masked))<1e-5,'Black custom mask protects all features');s.blush_mask=None
s.blush_amount=2.2;s.preset='STAGE'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/通用脸红_女漂演示.blend'))
s.preset='KINGDOM';shading.apply_objects([o],s)
check(any(slot.material.get('mr_blush_active') for slot in o.material_slots if slot.material),'Daylight supports blush')
s.preset='STAGE';shading.apply_objects([o],s)
check(any(slot.material.get('mr_blush_active') for slot in o.material_slots if slot.material),'Stage supports blush')
check(shading.restore_objects([o])==35,'Original material restore')
check(o.data.attributes.get(blush.ATTRIBUTE) is None,'Restore cleans generated mask')
(ROOT/'output/blush_validation.json').write_text(json.dumps({'passed':checks,'max_rgb_difference':float(np.max(abs(before-after)))},ensure_ascii=False,indent=2))
print('BLUSH VALIDATION PASSED',len(checks))
