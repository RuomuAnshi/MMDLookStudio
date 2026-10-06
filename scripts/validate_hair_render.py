"""Pixel checks for hair masks and a render without the extension registered."""
import bpy
import json
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT/'output/王国白昼_头发演示.blend'
bpy.ops.wm.open_mainfile(filepath=str(path))
scene = bpy.context.scene
assert not hasattr(bpy.types.Scene, 'zelda_daylight')
scene.render.filepath = '/private/tmp/zelda-hair-without-extension.png'
bpy.ops.render.render(write_still=True)
hair_materials = [m for m in bpy.data.materials if m.get('zd_owned') and m.get('zd_role')=='HAIR']
assert all(d.driver.is_valid and d.driver.is_simple_expression
           for m in hair_materials for d in m.node_tree.animation_data.drivers)
checks = ['Render succeeds without extension registration']

def pixels(filename):
    image = bpy.data.images.load(str(filename), check_existing=False)
    values = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(values)
    bpy.data.images.remove(image)
    return values.reshape((-1,4))[:,:3]

without = pixels(scene.render.filepath)
saved = pixels(ROOT/'output/hair_after.png')
mean_error = float(np.abs(without-saved).mean())
assert mean_error < .0005, mean_error
checks.append('Render without extension matches saved preview')
sys.path.insert(0,str(ROOT))
import zelda_preset
from zelda_preset import shading
zelda_preset.register()
settings = scene.zelda_daylight
model = next(o for o in scene.objects if o.type=='MESH' and len(o.zelda_slot_backups)==49)
strength = settings.hair_strength
settings.hair_strength = 0
shading.apply_objects([model], settings)
scene.render.filepath = '/private/tmp/zelda-hair-zero-strength.png'
bpy.ops.render.render(write_still=True)
zero = pixels(scene.render.filepath)
mask = bpy.data.images.new('Black Hair Test Mask', width=2,height=2)
mask.colorspace_settings.name = 'Non-Color'
mask.generated_color = (0,0,0,1)
settings.hair_strength = strength
settings.hair_mask = mask
shading.apply_objects([model], settings)
scene.render.filepath = '/private/tmp/zelda-hair-black-mask.png'
bpy.ops.render.render(write_still=True)
masked = pixels(scene.render.filepath)
mask_error = float(np.abs(masked-zero).mean())
assert mask_error < .0005, mask_error
assert (np.abs(saved-zero).max(axis=1) > .02).sum() > 500
checks.append('Black mask removes visible band like zero strength')
report_path = ROOT/'output/hair_validation.json'
report = json.loads(report_path.read_text())
report['passed'].extend(checks)
report['standalone_render_mean_error'] = mean_error
report['black_mask_mean_error'] = mask_error
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('HAIR PIXEL CHECKS PASSED', len(checks), mean_error, mask_error)
