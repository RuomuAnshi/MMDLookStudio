"""Small asset library with no third-party model or textures."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import zelda_preset
from zelda_preset import shading, scene_setup
zelda_preset.register()
scene = bpy.context.scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
models = []
colors = {'SKIN':(.66,.42,.27), 'HAIR':(.19,.32,.41), 'CLOTH':(.1,.29,.34),
          'EYE':(.26,.44,.35), 'METAL':(.46,.33,.10), 'ENV':(.35,.39,.25)}
for i,(role,color) in enumerate(colors.items()):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=.65,
                                      location=((i-2.5)*1.5,0,.65))
    obj = bpy.context.object
    obj.name = f'ZD Sample · {role}'
    for face in obj.data.polygons:
        face.use_smooth = True
    material = bpy.data.materials.new(f'ZD Source · {role}')
    material.use_nodes = True
    material['zd_role'] = role
    next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Base Color'].default_value = (*color,1)
    obj.data.materials.append(material)
    models.append(obj)
camera_data = bpy.data.cameras.new('ZD Library Camera')
camera = bpy.data.objects.new(camera_data.name,camera_data)
scene.collection.objects.link(camera)
camera.location = (0,-13,5)
camera.rotation_euler = (Vector((0,0,.65))-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 10.5
scene.camera = camera
scene_setup.apply(scene)
shading.apply_objects(models,scene.zelda_daylight)
for obj in models:
    material=obj.material_slots[0].material
    material.asset_mark()
    material.asset_data.description = f'Kingdom daylight {material["zd_role"]}; Eevee only'
    material.use_fake_user = True
group=shading.ensure_group()
group.asset_mark()
group.asset_data.description='Eevee daylight toon / original textures / cast shadows / depth haze'
group.use_fake_user=True
from zelda_preset import hair, lines
hair_group = hair.ensure_group()
hair_group.asset_mark()
hair_group.asset_data.description = 'Directional toon hair / tangent flow / sun and view / optional mask'
hair_group.use_fake_user = True
line_group=lines.ensure_group()
line_group.asset_mark()
line_group.asset_data.description='Local hair texture line repair / original alpha / optional mask'
line_group.use_fake_user=True
scene.world.asset_mark()
scene.zelda_daylight.owned_collection.asset_mark()
scene.render.resolution_x=1400
scene.render.resolution_y=500
scene.render.resolution_percentage=100
scene.render.image_settings.media_type='IMAGE'
scene.render.image_settings.file_format='PNG'
scene.eevee.taa_render_samples=48
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/王国白昼_材质灯光预设.blend'))
print('NATIVE ASSET LIBRARY CREATED')

# A second library exposes the independently authored physical stage pipeline.
scene_setup.restore(scene)
scene.zelda_daylight.preset='STAGE'
scene.zelda_daylight.stage_dof=False
shading.apply_objects(models,scene.zelda_daylight)
scene_setup.apply(scene,models)
for obj in models:
    material=obj.material_slots[0].material
    material.asset_mark()
    material.asset_data.description=f'Cold warm stage {material["zd_role"]}; Eevee physical surface'
    material.use_fake_user=True
from zelda_preset import stage
stage_group=stage.ensure_group()
stage_group.asset_mark()
stage_group.asset_data.description='Soft physical surface / two driven hair lobes / preserved alpha'
stage_group.use_fake_user=True
from zelda_preset import face
face_group=face.ensure_group();face_group.asset_mark();face_group.use_fake_user=True
face_group.asset_data.description='Eevee soft anime face / warm shallow shadows / texture and alpha preserved'
scene.world.asset_mark()
scene.zelda_daylight.owned_collection.asset_mark()
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/冷暖逆光_材质灯光预设.blend'))
print('STAGE ASSET LIBRARY CREATED')
