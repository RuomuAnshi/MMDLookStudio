"""Build local-only MMD + landscape demonstration from an existing user asset."""
import json
import argparse
import math
import random
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import zelda_preset
from zelda_preset import shading, scene_setup

parser = argparse.ArgumentParser(description='Build an MMD daylight demonstration from a local model scene')
parser.add_argument('source', type=Path)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
SOURCE = args.source
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
if not hasattr(bpy.types.Scene, 'zelda_daylight'):
    zelda_preset.register()
scene = bpy.context.scene
model = bpy.data.objects['FC式-丰川祥子_改2.1_mesh']
scene.render.resolution_x = 1280
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = False
scene.render.image_settings.media_type = 'IMAGE'
scene.eevee.taa_render_samples = 48
scene.render.use_file_extension = True
scene.render.use_sequencer = False
scene.render.engine = 'BLENDER_EEVEE'
scene.camera.data.type = 'PERSP'
scene.camera.data.lens = 46
scene.camera.location = (.4, -5.8, 1.65)
target = Vector((.55, .4, 1.13))
scene.camera.rotation_euler = (target - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera.data.clip_end = 500
for o in scene.objects:
    if o.name == 'Shoko_Preview_Backdrop':
        o.hide_render = True

def mat(name, color, noise=0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m['zd_role'] = 'ENV'
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = .85
    if noise:
        tex = m.node_tree.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = noise
        ramp = m.node_tree.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (*[v*.84 for v in color], 1)
        ramp.color_ramp.elements[1].color = (*[v*1.09 for v in color], 1)
        m.node_tree.links.new(tex.outputs['Fac'], ramp.inputs[0])
        m.node_tree.links.new(ramp.outputs[0], bs.inputs['Base Color'])
    return m

stone = mat('ENV · Warm limestone', (.42, .42, .32), 3)
grass = mat('ENV · Sage grass', (.23, .33, .095), 4)
gold = [mat('ENV · Golden foliage '+str(i), c) for i,c in enumerate(((.61,.34,.055),(.74,.48,.105),(.49,.26,.043)))]
bark = mat('ENV · Tree bark', (.19, .14, .07))
far_stone = mat('ENV · Distant cool stone', (.38, .49, .48))
env = []
random.seed(19)
def sphere(name, loc, scale, material, subdivision=2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivision, radius=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    env.append(o)
    return o
def cube(name, loc, scale, material, bevel=.1):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    if bevel:
        m = o.modifiers.new('Worn edges', 'BEVEL')
        m.width, m.segments = bevel, 2
        o.modifiers.new('Weighted stone normals', 'WEIGHTED_NORMAL')
    env.append(o)
    return o

cube('Plateau stone', (0, 3, -.38), (18, 18, .6), stone, .25)
cube('Meadow', (0, 3, -.052), (17.9, 17.9, .08), grass, .02)
for j in range(6):
    cube('Ancient stepping stone', (.45 + math.sin(j)*.1, j*.66 + 1.1, .012), (.84,.51,.065), stone, .045)
for x,y,h in ((-2,4,2.5),(2.3,4.5,2.7),(3.7,6,1.2)):
    cube('Ruin plinth', (x,y,.12), (.8,.8,.25), stone)
    cube('Weathered column', (x,y,h/2), (.5,.5,h), stone, .085)
    cube('Column capital', (x,y,h+.08), (.73,.72,.22), stone)
cube('Broken lintel', (3.0,4.5,2.96), (2.4,.7,.3), stone)
for i in range(13):
    x,y = random.choice((-1,1))*random.uniform(2,7),random.uniform(.5,12)
    sphere('Weathered rock', (x,y,.08), (random.uniform(.25,.8),random.uniform(.35,.9),random.uniform(.25,.65)), stone)
for i,(x,y,h) in enumerate(((-3.3,3,3.9),(-5.2,7,4.6),(5.2,8,4.5),(-3.5,12,5.0))):
    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=.2, radius2=.08, depth=h, location=(x,y,h/2))
    o = bpy.context.object
    o.name = 'Golden tree trunk'
    o.data.materials.append(bark)
    env.append(o)
    for j in range(8):
        a=j*math.tau/8
        sphere('Golden tree crown', (x+math.cos(a)*.8,y+math.sin(a)*.65,h+random.uniform(-.2,.6)),
               (1.1,1.0,.9),gold[(j+i)%3],3)
for i,(x,y,z,r) in enumerate(((-15,44,5,6),(11,52,7,8),(26,65,10,7),(-28,70,11,10))):
    sphere('Distant floating island', (x,y,z), (r,r*.62,1.5),far_stone,2)
    sphere('Distant island underside', (x,y,z-2), (r*.5,r*.4,3.4),far_stone,1)
    cube('Distant island grass', (x,y,z+1.25), (r*1.1,r*.75,.18), grass)
    for j in range(3):
        sphere('Distant golden treetop', (x+(j-1)*r*.3,y,z+2.3), (r*.18,r*.15,r*.15), gold[j],2)

settings = scene.zelda_daylight
settings.mist_start = 9
settings.mist_density = .015
scene_setup.apply(scene)
result = shading.apply_objects([model] + env, settings)
assert result['applied'] >= 49, result
# Validate real texture / alpha links before rendering.
eye = next(m for m in bpy.data.materials if m.get('zd_original_name') == '脸_瞳')
veil = next(m for m in bpy.data.materials if m.get('zd_original_name') == '服_背后透明纱')
assert eye.node_tree.nodes[shading.NODE_NAME].inputs['Base Color'].is_linked
assert veil.node_tree.nodes[shading.NODE_NAME].inputs['Alpha'].is_linked
scene['zd_demo_model'] = model.name
scene['zd_demo_note'] = '本机私人 MMD 示例；模型不包含在预设安装包中。'
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
        area.spaces.active.shading.type = 'MATERIAL'
        area.spaces.active.shading.use_scene_world = True
        area.spaces.active.shading.use_scene_lights = True
bpy.ops.object.select_all(action='DESELECT')
model.select_set(True)
bpy.context.view_layer.objects.active = model
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'output/王国白昼_MMD演示.blend'))
scene.render.filepath = str(ROOT / 'output/mmd_daylight.png')
bpy.ops.render.render(write_still=True)

# Same lighting, geometry and camera; only shader changes for the comparison.
shading.restore_objects([model] + env)
# Keep outline state equal in this shader-only comparison.
for modifier in model.modifiers:
    if shading.is_outline_modifier(modifier):
        modifier.show_render = False
scene.render.filepath = str(ROOT / 'output/mmd_original_materials.png')
bpy.ops.render.render(write_still=True)
check = shading.apply_objects([model], settings)
assert check['applied'] == 49, check
restored = shading.restore_objects([model])
assert restored == 49
(ROOT / 'output/mmd_validation.json').write_text(json.dumps({
    'model':model.name,'applied':result['applied'],'skipped_count':len(result['skipped']),
    'mmd_slots_restored':restored,'eye_base_color_link':True,'veil_alpha_link':True,
    'resolution':[1280,800]},ensure_ascii=False,indent=2))
print('MMD DEMO AND RESTORE VALIDATED', result['applied'])
