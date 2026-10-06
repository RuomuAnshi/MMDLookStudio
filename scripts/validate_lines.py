"""Native-render tests of baked lines, dark hair, alpha and reversible outlines."""
import bpy
import json
import sys
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import shading,lines
zelda_preset.register()
scene=bpy.context.scene
settings=scene.zelda_daylight
checks=[]
def check(condition,message):
    assert condition,message
    checks.append(message)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=2)
obj=bpy.context.object
obj.name='Hair line test surface'
rgba=np.zeros((128,128,4),dtype=np.float32)
rgba[:,:,:]=(.12,.28,.45,1)
rgba[:,62:66,:3]=(.001,.001,.001)
rgba[:32,:,:3]=(.001,.001,.001)  # Broad, uniform dark hair must survive.
rgba[-16:,:,3]=0  # Transparency must not grow into a silhouette.
image=bpy.data.images.new('Line test data',width=128,height=128,alpha=True)
image.colorspace_settings.name='Non-Color'
image.pixels.foreach_set(rgba.ravel())
original_pixels=np.array(image.pixels[:],dtype=np.float32)
original=bpy.data.materials.new('Hair sample')
original.use_nodes=True
nt=original.node_tree
bsdf=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
tex=nt.nodes.new('ShaderNodeTexImage')
tex.image=image
tex.interpolation='Closest'
nt.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
nt.links.new(tex.outputs['Alpha'],bsdf.inputs['Alpha'])
obj.data.materials.append(original)
shared=obj.copy()
shared.name='Unselected shared hair'
shared.hide_render=True
scene.collection.objects.link(shared)
outline=obj.modifiers.new('MMD edge','SOLIDIFY')
outline.show_render=outline.show_viewport=True
settings.hair_clean_lines=False
shading.apply_objects([obj],settings)
derived=obj.material_slots[0].material
check(shared.material_slots[0].material==original,'Unselected shared mesh unchanged')
check(not outline.show_render,'MMD edge modifier recognized')
settings.hair_clean_lines=True
shading.apply_objects([obj],settings)
check(derived.get('zd_line_repair')=='active','Direct base texture repair enabled')
count=len(derived.node_tree.nodes)
shading.apply_objects([obj],settings)
check(len(derived.node_tree.nodes)==count,'Reapplying line repair creates no duplicate nodes')
check(np.array_equal(original_pixels,np.array(image.pixels[:],dtype=np.float32)),
      'Original texture pixels never modified')
group=derived.node_tree.nodes[shading.NODE_NAME]
check(group.inputs['Alpha'].links[0].from_socket.name=='Alpha','Original alpha link preserved')

camera_data=bpy.data.cameras.new('Line test camera')
camera=bpy.data.objects.new(camera_data.name,camera_data)
scene.collection.objects.link(camera)
camera.location=(0,0,3)
camera.data.type='ORTHO'
camera.data.ortho_scale=2
scene.camera=camera
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=scene.render.resolution_y=256
scene.render.resolution_percentage=100
scene.render.image_settings.media_type='IMAGE'
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGBA'
scene.render.film_transparent=True
scene.render.use_compositing=False
scene.render.use_sequencer=False
scene.view_settings.view_transform='Standard'
scene.view_settings.look='None'
scene.eevee.taa_render_samples=32

# Expose the repaired base color as emission for quantitative color/alpha checks.
tree=derived.node_tree
output=next(n for n in tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
emission=tree.nodes.new('ShaderNodeEmission')
transparent=tree.nodes.new('ShaderNodeBsdfTransparent')
alpha=tree.nodes.new('ShaderNodeMixShader')
tree.links.new(group.inputs['Alpha'].links[0].from_socket,alpha.inputs[0])
tree.links.new(transparent.outputs[0],alpha.inputs[1])
tree.links.new(emission.outputs[0],alpha.inputs[2])
tree.links.new(alpha.outputs[0],output.inputs['Surface'])
def render(name):
    tree.links.new(group.inputs['Base Color'].links[0].from_socket,emission.inputs['Color'])
    path=ROOT/'output'/name
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    result=bpy.data.images.load(str(path),check_existing=False)
    pixels=np.array(result.pixels[:],dtype=np.float32).reshape((256,256,4))
    bpy.data.images.remove(result)
    return pixels
settings.hair_clean_lines=False
shading.apply_objects([obj],settings)
before=render('line_test_before.png')
settings.hair_clean_lines=True
shading.apply_objects([obj],settings)
after=render('line_test_after.png')
check(float(after[80:180,126:130,:3].mean())>float(before[80:180,126:130,:3].mean())+.15,
      'Baked black line replaced with neighbouring hair color in render')
check(float(np.abs(after[8:40,20:100,:3]-before[8:40,20:100,:3]).mean())<.0005,
      'Uniform near-black hair is not globally brightened')
check(float(np.abs(after[80:180,20:100,:3]-before[80:180,20:100,:3]).mean())<.0005,
      'Non-line hair color remains unchanged')
check(float(np.abs(after[:,:,3]-before[:,:,3]).max())<.0005,
      'Rendered transparency and silhouette unchanged')

mask=bpy.data.images.new('Black repair mask',width=2,height=2)
mask.colorspace_settings.name='Non-Color'
mask.generated_color=(0,0,0,1)
settings.hair_line_mask=mask
shading.apply_objects([obj],settings)
masked=render('line_test_masked.png')
check(float(np.abs(masked-before).mean())<.0005,'Black repair mask protects original black line')
settings.hair_line_mask=None
settings.hair_clean_lines=False
shading.apply_objects([obj],settings)
check(not any(n.name.startswith(lines.PREFIX) for n in tree.nodes),'Disable removes managed repair nodes')
check(shading.restore_objects([obj])==1 and obj.material_slots[0].material==original,
      'Hair material restores exactly')
check(outline.show_render and outline.show_viewport,'MMD edge modifier restored')

edge=bpy.data.materials.new('Hair Outline Black')
edge.use_nodes=True
obj.data.materials.append(edge)
settings.hair_hide_outline=True
shading.apply_objects([obj],settings)
hidden=obj.material_slots[1].material
check(hidden.get('zd_hidden_hair_outline') and hidden!=edge,'Explicit hair outline material hidden reversibly')
shading.apply_objects([obj],settings)
check(obj.material_slots[1].material==hidden,'Outline hiding is idempotent')
settings.hair_hide_outline=False
shading.apply_objects([obj],settings)
check(not obj.material_slots[1].material.get('zd_hidden_hair_outline'),'Outline disable restores visible material')
shading.restore_objects([obj])
check(obj.material_slots[1].material==edge,'Original outline material pointer restored')
settings.hair_hide_outline=True
shading.apply_objects([obj],settings)
scene.render.filepath='/private/tmp/unused.png'
path=ROOT/'output/line_validation_roundtrip.blend'
image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
obj=bpy.data.objects['Hair line test surface']
check(shading.restore_objects([obj])==2,'Both material backups restore after file reload')
report={'version':'0.3.0','blender':bpy.app.version_string,'passed':checks}
(ROOT/'output/line_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('LINE VALIDATION PASSED',len(checks))
