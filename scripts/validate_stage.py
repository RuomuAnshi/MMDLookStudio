"""Validate independent pipelines and preservation across switches and reloads."""
import bpy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import shading,scene_setup,stage
zelda_preset.register()
scene=bpy.context.scene;s=scene.zelda_daylight;o=bpy.data.objects['Cube']
original=o.material_slots[0].material
original.name='Hair'
bsdf=next(n for n in original.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
image=bpy.data.images.new('Stage source fixture',width=4,height=4,alpha=True)
image.pixels[:]=[.1,.2,.3,.5]*16
texture=original.node_tree.nodes.new('ShaderNodeTexImage');texture.image=image
for source,target in [('Color','Base Color'),('Alpha','Alpha'),('Color','Roughness')]:
 original.node_tree.links.new(texture.outputs[source],bsdf.inputs[target])
world=scene.world;camera=scene.camera;camera_data=camera.data
old_comp=scene.compositing_node_group
old_lights=[(x,x.hide_render,x.hide_viewport) for x in scene.objects if x.type=='LIGHT']
checks=[]
def check(value,name):
 assert value,name
 checks.append(name)
shared=o.copy();scene.collection.objects.link(shared);shared.select_set(False)
bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
s.preset='STAGE'
check(bpy.ops.zelda_daylight.apply_preset()=={'FINISHED'},'Combined preset operator')
m=o.material_slots[0].material;g=m.node_tree.nodes[shading.NODE_NAME]
check(m.get('zd_preset')=='STAGE' and g.node_tree==stage.ensure_group(),'Independent physical stage graph')
check(g.inputs['Alpha'].is_linked and g.inputs['Alpha'].links[0].from_node.image==image,'Original alpha texture preserved')
check(g.inputs['Roughness'].is_linked and g.inputs['Roughness'].links[0].from_node.image==image,'Authored roughness texture preserved')
physical=g.node_tree.nodes['Soft physical surface']
check(not physical.inputs['Alpha'].is_linked and physical.inputs['Alpha'].default_value==1,'Alpha applied once outside all shader layers')
check(shared.material_slots[0].material==original,'Unselected shared object preserved')
check(s.old_world==world and s.old_compositor==old_comp,'Original scene backup retained')
check(camera.data!=camera_data and camera.data.dof.use_dof,'Private camera DOF data')
check(len(s.owned_collection.objects)==5,'Three main lights plus catchlight and focus')
check(len(o.zelda_slot_backups)==1 and o.zelda_slot_backups[0].material==original,'Original slot backup')
rig=s.owned_collection;material=m
bpy.ops.zelda_daylight.apply_preset()
check(s.owned_collection==rig and o.material_slots[0].material==material,'Repeated stage apply has no duplicates')
scene.frame_set(1);bpy.context.view_layer.update()
check(g.inputs['Warm Energy'].default_value>0 and g.inputs['Cold Energy'].default_value>0,'Both hair lamp drivers bound')
warm=next(x for x in rig.objects if x.get('mr_stage_side')=='Warm')
warm.data.energy=0;scene.frame_set(2)
check(g.inputs['Warm Energy'].default_value==0,'Hair follows zero lamp energy')
s.preset='KINGDOM';bpy.ops.zelda_daylight.apply_preset()
check(o.material_slots[0].material.get('zd_preset')=='KINGDOM','Switch to daylight materials')
check(camera.data==camera_data and s.old_world==world,'Camera restored and original scene backup retained through switch')
check(any(x.data.type=='SUN' for x in s.owned_collection.objects),'Independent daylight rig')
s.preset='STAGE';bpy.ops.zelda_daylight.apply_preset()
check(o.material_slots[0].material.get('zd_preset')=='STAGE','Switch back to stage')
s.stage_dof=False;bpy.ops.zelda_daylight.apply_preset()
check(camera.data==camera_data,'Disable stage DOF restores original camera data')
s.stage_dof=True;bpy.ops.zelda_daylight.apply_preset()
check(camera.data!=camera_data and s.old_world==world,'Re-enable DOF retains initial environment backup')
path=ROOT/'output/stage_validation_roundtrip.blend'
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;s=scene.zelda_daylight;o=bpy.data.objects['Cube']
check(s.preset=='STAGE' and s.active_preset=='STAGE','Preset identity survives reload')
check(shading.restore_objects([o])==1 and o.material_slots[0].material.name=='Hair','Original material restored after reload')
scene_setup.restore(scene)
check(scene.world.name=='World','Original world restored after reload')
check(scene.camera.data.name=='Camera','Original camera data restored after reload')
check(not s.active and not s.owned_collection,'Owned scene resources cleaned')
(ROOT/'output/stage_validation.json').write_text(json.dumps({'passed':checks},ensure_ascii=False,indent=2))
print('STAGE VALIDATION PASSED',len(checks))
