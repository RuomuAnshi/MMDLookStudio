"""Native render checks for skin-only wet layers, switches and restoration."""
import bpy,sys,json
from pathlib import Path
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import shading,scene_setup,wet
zelda_preset.register()
scene=bpy.context.scene;s=scene.zelda_daylight
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32)
o=bpy.context.object;o.name='Skin fixture'
for f in o.data.polygons:f.use_smooth=True
original=bpy.data.materials.new('Skin');original.use_nodes=True
bsdf=next(n for n in original.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bsdf.inputs['Base Color'].default_value=(.55,.3,.2,1)
original_nodes=len(original.node_tree.nodes);o.data.materials.append(original)
shared=o.copy();scene.collection.objects.link(shared);shared.hide_render=True
camera=bpy.data.objects.new('Wet Camera',bpy.data.cameras.new('Wet Camera'));scene.collection.objects.link(camera)
camera.location=(0,-5,0);camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=2.5;scene.camera=camera
s.preset='STAGE';s.stage_dof=False;s.wet_scale=32;s.wet_amount=1
shading.apply_objects([o],s);scene_setup.apply(scene,[o])
scene.render.resolution_x=scene.render.resolution_y=256;scene.render.resolution_percentage=100
scene.render.image_settings.media_type='IMAGE';scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.render.film_transparent=True;scene.render.use_compositing=False;scene.eevee.taa_render_samples=64
checks=[]
def check(value,name):
 assert value,name
 checks.append(name)
def render(name):
 scene.render.filepath=str(ROOT/'output'/name);bpy.ops.render.render(write_still=True)
 image=bpy.data.images.load(scene.render.filepath,check_existing=False)
 value=np.array(image.pixels[:],dtype=np.float32).reshape(256,256,4).copy();bpy.data.images.remove(image);return value
check(all(shading.classify(bpy.data.materials.new(x))=='HAIR' for x in ('前发','后发','辫子')),'Chinese hair names recognized')
dry=render('wet_fixture_dry.png');s.wet_enabled=True
m=o.material_slots[0].material
check(m.get('mr_wet_active'),'Skin wet layer enabled')
check(shared.material_slots[0].material==original and len(original.node_tree.nodes)==original_nodes,'Original and unselected shared material unchanged')
water=render('wet_fixture_water.png')
error=float(np.max(np.abs(water[:,:,:3]-dry[:,:,:3])))
check(error>.01,'Visible water reflection render difference')
check(np.max(np.abs(water[:,:,3]-dry[:,:,3]))<1e-5,'Rendered opaque skin silhouette and alpha unchanged')
wet.configure(m,s);wet.configure(m,s)
check(sum(n.name==wet.PREFIX+'Layer' for n in m.node_tree.nodes)==1,'Repeated wet update has no duplicates')
s.wet_style='FILM';check(m.node_tree.nodes[wet.PREFIX+'Layer'].inputs['Drops'].default_value==0,'Film mode disables drop relief')
s.wet_style='DROPS';check(m.node_tree.nodes[wet.PREFIX+'Layer'].inputs['Film'].default_value==0,'Drop mode disables film patches')
mask=bpy.data.images.new('Black water mask',width=4,height=4);mask.pixels[:]=[0,0,0,1]*16
s.wet_mask=mask;masked=render('wet_fixture_masked.png')
check(np.max(np.abs(masked-dry))<1e-5,'Black mask returns identical dry render')
s.wet_mask=None
s.wet_amount=0
check(not m.get('mr_wet_active'),'Zero amount removes wet effect')
s.wet_amount=1
s.wet_enabled=False
check(not any(n.name.startswith(wet.PREFIX) for n in m.node_tree.nodes),'Disable removes owned wet nodes')
again=render('wet_fixture_disabled.png');check(np.max(np.abs(again-dry))<1e-5,'Disable returns identical dry render')
s.wet_enabled=True
for role,name in [('SKIN','face'),('CLOTH','Shirt'),('HAIR','Hair')]:
 test=m.copy();test['zd_role']=role;test['zd_original_name']=name;wet.configure(test,s)
 check(not test.get('mr_wet_active'),f'{name} protected from water by default')
 bpy.data.materials.remove(test)
s.wet_face=True;test=m.copy();test['zd_original_name']='face';wet.configure(test,s)
check(test.get('mr_wet_active'),'Face can explicitly opt in');bpy.data.materials.remove(test)
s.preset='KINGDOM';shading.apply_objects([o],s)
check(o.material_slots[0].material.get('mr_wet_active'),'Wet layer survives switch to daylight')
s.preset='STAGE';shading.apply_objects([o],s)
check(o.material_slots[0].material.get('mr_wet_active'),'Wet layer survives switch back to stage')
check(shading.restore_objects([o])==1 and o.material_slots[0].material==original,'Original material restored')
(ROOT/'output/wet_validation.json').write_text(json.dumps({'passed':checks,'max_rgb_difference':error},ensure_ascii=False,indent=2))
print('WET VALIDATION PASSED',len(checks),error)
