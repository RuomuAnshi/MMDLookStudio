"""Real actor closeup, face-only updates, alpha, wet layering and rollback."""
import bpy,sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import face,shading,wet
zelda_preset.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/冷暖逆光_水渍_女漂演示.blend'))
scene=bpy.context.scene;s=scene.zelda_daylight;o=bpy.data.objects['鸣潮_女漂泊者1.023_mesh']
scene.render.resolution_percentage=100;scene.render.use_border=True;scene.render.use_crop_to_border=True
scene.render.border_min_x=.15;scene.render.border_max_x=.64
scene.render.border_min_y=.66;scene.render.border_max_y=.93
scene.render.use_compositing=False;scene.render.film_transparent=True
checks=[]
def check(ok,name):
 assert ok,name
 checks.append(name)
def render(name):
 scene.render.filepath=str(ROOT/'output'/name);bpy.ops.render.render(write_still=True)
 image=bpy.data.images.load(scene.render.filepath,check_existing=False)
 pixels=np.array(image.pixels[:],dtype=np.float32).reshape(-1,4).copy();bpy.data.images.remove(image);return pixels
s.face_softness=0;before=render('face_before.png')
s.face_softness=.85;after=render('face_soft_anime.png')
check(float(np.max(abs(before[:,:3]-after[:,:3])))>.01,'Face render visibly changes')
check(float(np.max(abs(before[:,3]-after[:,3])))<1e-5,'Rendered face alpha unchanged')
active=[slot.material for slot in o.material_slots if slot.material and slot.material.get('mr_face_active')]
check(len(active)>0 and all(face.is_face(m) for m in active),'Only named face skin gets face shader')
check(all(not slot.material.get('mr_face_active') for slot in o.material_slots if slot.material and not face.is_face(slot.material)),'Body hair eyes clothing remain separate')
m=active[0]
face.update_settings(s,bpy.context);face.update_settings(s,bpy.context)
check(sum(n.name==face.PREFIX+'Layer' for n in m.node_tree.nodes)==1,'Repeated update does not duplicate shader')
s.wet_face=True
check(m.get('mr_wet_active') and m.node_tree.nodes[wet.PREFIX+'Layer'].inputs['Dry Shader'].links[0].from_node.name==face.PREFIX+'Layer','Explicit face water wraps face shader without cycles')
s.face_softness=.7
check(m.node_tree.nodes[wet.PREFIX+'Layer'].inputs['Dry Shader'].links[0].from_node.name==face.PREFIX+'Layer','Live face slider preserves water ordering')
s.wet_face=False;s.face_softness=0;disabled=render('face_disabled.png')
check(float(np.max(abs(before-disabled)))<1e-5,'Zero slider restores identical original face rendering')
s.face_softness=.85
s.preset='KINGDOM';shading.apply_objects([o],s)
check(all(not any(n.name.startswith(face.PREFIX) for n in slot.material.node_tree.nodes) for slot in o.material_slots if slot.material),'Face stage shader does not leak into daylight')
s.preset='STAGE';shading.apply_objects([o],s)
check(any(slot.material.get('mr_face_active') for slot in o.material_slots if slot.material),'Stage switch rebuilds face layer')
count=shading.restore_objects([o])
check(count==35 and all(not slot.material.get('zd_owned') for slot in o.material_slots if slot.material),'35 original materials restored')
(ROOT/'output/face_validation.json').write_text(json.dumps({'passed':checks,'render_max_difference':float(np.max(abs(before-after)))},ensure_ascii=False,indent=2))
print('FACE VALIDATION PASSED',len(checks))
