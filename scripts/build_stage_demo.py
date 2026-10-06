"""Packed private MMD comparison; does not modify the source project."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import shading,scene_setup
zelda_preset.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/王国白昼_黑边修复演示.blend'))
scene=bpy.context.scene;o=bpy.data.objects['Head only']
shading.restore_objects([o]);scene_setup.restore(scene)
for obj in scene.objects:
 if obj.type not in {'LIGHT','CAMERA'}:obj.hide_render=obj!=o
points=[o.matrix_world@Vector(c) for c in o.bound_box]
lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)])
center=(lo+hi)*.5;size=max(hi.z-lo.z,hi.x-lo.x)
camera=bpy.data.objects.new('MR · Portrait Camera',bpy.data.cameras.new('MR · Portrait Camera'))
scene.collection.objects.link(camera);scene.camera=camera
camera.location=center+Vector((size*.12,-size*3,size*.08))
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.lens=70
scene.render.resolution_x=800;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.media_type='IMAGE';scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGBA';scene.render.film_transparent=False
scene.render.use_sequencer=False;scene.eevee.taa_render_samples=96
bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
s=scene.zelda_daylight
s.hair_outline_material=next((x.material for x in o.material_slots if x.material and x.material.name=='头_Outline'),None)
s.preset='KINGDOM';bpy.ops.zelda_daylight.apply_preset()
scene.render.filepath=str(ROOT/'output/stage_daylight_comparison.png');bpy.ops.render.render(write_still=True)
s.preset='STAGE';bpy.ops.zelda_daylight.apply_preset()
# Original demonstration set dressing provides background depth without becoming preset behavior.
for i,(x,z,color) in enumerate([(-.85,.2,(1,.23,.05,1)),(.8,.6,(.08,.2,1,1)),(-.65,-.3,(1,.4,.1,1)),(.65,-.35,(.1,.25,1,1))]):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=size*.06,location=center+Vector((x*size,size*.85,z*size)))
 obj=bpy.context.object;obj.name='MR Demo · Defocused light '+str(i)
 mat=bpy.data.materials.new(obj.name);mat.use_nodes=True;nt=mat.node_tree;nt.nodes.clear()
 em=nt.nodes.new('ShaderNodeEmission');em.inputs['Color'].default_value=color;em.inputs['Strength'].default_value=3
 out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(em.outputs[0],out.inputs[0]);obj.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
scene.render.filepath=str(ROOT/'output/stage_cold_warm.png');bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/冷暖逆光_MMD演示.blend'))
report={'model':o.name,'preset':s.preset,'materials':sum(bool(x.material and x.material.get('zd_preset')=='STAGE') for x in o.material_slots),
        'packed_images':sum(bool(x.packed_file) for x in bpy.data.images),'resolution':[800,1100]}
(ROOT/'output/stage_mmd_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('STAGE MMD DEMO COMPLETE',json.dumps(report,ensure_ascii=False))
