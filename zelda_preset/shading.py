"""Independent Eevee NPR materials built entirely from native shader nodes.

Texture color never enters the diffuse light probe. MMD toon maps are replaced
by this preset's light response; base textures, alpha and sphere color survive.
"""
import json
import bpy
from . import hair, lines, presets, stage, wet

GROUP_NAME = 'ZD · Daylight Toon v1'
NODE_NAME = 'ZD · Surface'
PROFILES = {
    'SKIN': ((.72, .52, .43, 1), .88, .04, .48),
    'HAIR': ((.44, .55, .69, 1), 1.0, .11, .4),
    'CLOTH': ((.49, .59, .67, 1), 1.0, .018, .7),
    'EYE': ((.74, .77, .81, 1), .4, .035, .3),
    'METAL': ((.41, .53, .62, 1), 1.0, .42, .22),
    'ENV': ((.49, .60, .66, 1), 1.0, .04, .65),
}

def classify(mat):
    override = mat.get('zd_role')
    if override in PROFILES:
        return override
    n = mat.name.lower()
    if any(k in n for k in ('eye', 'iris', 'lash', 'brow', '瞳', '眼', '眉', '睫', '口线', '轮廓', '高光')):
        return 'EYE'
    if any(k in n for k in ('skin', 'face', 'body', '肌', '顔', '脸', '面部', 'かお', '身_', '脖', '牙', '舌')):
        return 'SKIN'
    if any(k in n for k in ('hair', 'bangs', '髪', '发_', '头发', '前发', '后发', '辫子', '頭髮', '前髮', '後髮')):
        return 'HAIR'
    if any(k in n for k in ('metal', 'gold', 'silver', '金属', '金屬', '皇冠', '耳坠')):
        return 'METAL'
    if any(k in n for k in ('stone', 'rock', 'grass', 'ground', 'tree', 'terrain', '环境', '地面', '石', '树', '草')):
        return 'ENV'
    return 'CLOTH'

def node(tree, kind, name, x=0, y=0):
    n = tree.nodes.new(kind)
    n.name = n.label = name
    n.location = (x, y)
    return n

def math_node(tree, name, operation, a=None, b=None, x=0, y=0):
    n = node(tree, 'ShaderNodeMath', name, x, y)
    n.operation = operation
    for i, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (float, int)):
            n.inputs[i].default_value = value
        else:
            tree.links.new(value, n.inputs[i])
    return n.outputs[0]

def mix(tree, name, mode, fac, a, b, x=0, y=0):
    n = node(tree, 'ShaderNodeMixRGB', name, x, y)
    n.blend_type = mode
    for socket, value in zip(n.inputs, (fac, a, b)):
        if hasattr(value, 'node'):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return n.outputs[0]

def ensure_group():
    group = bpy.data.node_groups.get(GROUP_NAME)
    if group and group.get('zd_version') == 1:
        return group
    group = bpy.data.node_groups.new(GROUP_NAME, 'ShaderNodeTree')
    group['zd_version'] = 1
    defs = [('Base Color', 'NodeSocketColor', (.5, .5, .5, 1)),
            ('Alpha', 'NodeSocketFloat', 1), ('Normal', 'NodeSocketVector', None),
            ('Shadow Tint', 'NodeSocketColor', (.49, .59, .67, 1)),
            ('Threshold', 'NodeSocketFloat', .68), ('Softness', 'NodeSocketFloat', .045),
            ('Shadow Strength', 'NodeSocketFloat', 1), ('Highlight', 'NodeSocketFloat', .04),
            ('Roughness', 'NodeSocketFloat', .5), ('Rim', 'NodeSocketFloat', .055),
            ('Mist Start', 'NodeSocketFloat', 12), ('Mist Density', 'NodeSocketFloat', .012)]
    for name, kind, value in defs:
        s = group.interface.new_socket(name=name, in_out='INPUT', socket_type=kind)
        if value is not None:
            s.default_value = value
    group.interface.new_socket(name='Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    gi = node(group, 'NodeGroupInput', 'Inputs', -1200, 0)
    go = node(group, 'NodeGroupOutput', 'Surface', 1700, 0)
    L = group.links
    diffuse = node(group, 'ShaderNodeBsdfDiffuse', 'Neutral light probe', -950, 500)
    diffuse.inputs['Color'].default_value = (1, 1, 1, 1)
    L.new(gi.outputs['Normal'], diffuse.inputs['Normal'])
    rgb = node(group, 'ShaderNodeShaderToRGB', 'Eevee light and cast shadows', -730, 500)
    L.new(diffuse.outputs[0], rgb.inputs[0])
    bw = node(group, 'ShaderNodeRGBToBW', 'Light luminance', -550, 500)
    L.new(rgb.outputs[0], bw.inputs[0])
    lo = math_node(group, 'Threshold minus softness', 'SUBTRACT', gi.outputs['Threshold'], gi.outputs['Softness'], -730, 240)
    hi = math_node(group, 'Threshold plus softness', 'ADD', gi.outputs['Threshold'], gi.outputs['Softness'], -730, 80)
    ramp = node(group, 'ShaderNodeMapRange', 'Two-tone light boundary', -300, 500)
    ramp.interpolation_type = 'SMOOTHERSTEP'
    ramp.clamp = True
    L.new(bw.outputs[0], ramp.inputs['Value'])
    L.new(lo, ramp.inputs['From Min'])
    L.new(hi, ramp.inputs['From Max'])
    ramp.inputs['To Min'].default_value = 0
    ramp.inputs['To Max'].default_value = 1
    shadow = mix(group, 'Colored shadow', 'MULTIPLY', 1, gi.outputs['Base Color'], gi.outputs['Shadow Tint'], -500, -60)
    shadow = mix(group, 'Shadow strength', 'MIX', gi.outputs['Shadow Strength'], gi.outputs['Base Color'], shadow, -250, -60)
    warm = mix(group, 'Warm sunlit color', 'MULTIPLY', 1, gi.outputs['Base Color'], (1.06, 1.025, .94, 1), -500, -250)
    color = mix(group, 'Shadow to sunlight', 'MIX', ramp.outputs['Result'], shadow, warm, 0, 120)
    floor = math_node(group, 'Readable unlit floor', 'MAXIMUM', bw.outputs[0], .32, -280, 740)
    ceiling = math_node(group, 'Light ceiling', 'MINIMUM', floor, 1, -80, 740)
    response = math_node(group, 'Restrained light response', 'MULTIPLY_ADD', ceiling, .22, 100, 740)
    # MULTIPLY_ADD's third input is the shadeless share.
    response.node.inputs[2].default_value = .78
    color = mix(group, 'Light response', 'MULTIPLY', 1, color, response, 250, 120)
    glossy = node(group, 'ShaderNodeBsdfGlossy', 'Material highlight probe', -900, -510)
    glossy.inputs['Color'].default_value = (1, 1, 1, 1)
    L.new(gi.outputs['Normal'], glossy.inputs['Normal'])
    L.new(gi.outputs['Roughness'], glossy.inputs['Roughness'])
    spec_rgb = node(group, 'ShaderNodeShaderToRGB', 'Highlight light', -680, -510)
    L.new(glossy.outputs[0], spec_rgb.inputs[0])
    spec_bw = node(group, 'ShaderNodeRGBToBW', 'Highlight luminance', -480, -510)
    L.new(spec_rgb.outputs[0], spec_bw.inputs[0])
    spec = node(group, 'ShaderNodeMapRange', 'Simplified highlight', -260, -510)
    spec.clamp = True
    spec.interpolation_type = 'SMOOTHSTEP'
    spec.inputs['From Min'].default_value = .65
    spec.inputs['From Max'].default_value = 1.2
    L.new(spec_bw.outputs[0], spec.inputs['Value'])
    spec_strength = math_node(group, 'Highlight amount', 'MULTIPLY', spec.outputs['Result'], gi.outputs['Highlight'], 0, -510)
    color = mix(group, 'Small warm highlights', 'ADD', spec_strength, color, (1, .89, .66, 1), 500, 120)
    layer = node(group, 'ShaderNodeLayerWeight', 'View silhouette', -220, -780)
    L.new(gi.outputs['Normal'], layer.inputs['Normal'])
    edge = math_node(group, 'Thin edge', 'POWER', layer.outputs['Fresnel'], 2.5, 0, -780)
    edge = math_node(group, 'Only light-facing edges', 'MULTIPLY', edge, ramp.outputs['Result'], 220, -700)
    edge = math_node(group, 'Rim amount', 'MULTIPLY', edge, gi.outputs['Rim'], 430, -650)
    color = mix(group, 'Subtle rim', 'ADD', edge, color, (.86, .95, 1, 1), 750, 120)
    camera = node(group, 'ShaderNodeCameraData', 'Camera distance', 150, -1000)
    distance = math_node(group, 'Distance beyond clear foreground', 'SUBTRACT', camera.outputs['View Distance'], gi.outputs['Mist Start'], 380, -1000)
    distance = math_node(group, 'Nonnegative fog distance', 'MAXIMUM', distance, 0, 580, -1000)
    optical = math_node(group, 'Optical depth', 'MULTIPLY', distance, gi.outputs['Mist Density'], 770, -1000)
    neg = math_node(group, 'Negative optical depth', 'MULTIPLY', optical, -1, 950, -1000)
    transmission = math_node(group, 'Exponential transmission', 'EXPONENT', neg, None, 1120, -1000)
    fog = math_node(group, 'Atmospheric veil', 'SUBTRACT', 1, transmission, 1280, -900)
    fog = math_node(group, 'Retain distant silhouettes', 'MINIMUM', fog, .72, 1280, -680)
    color = mix(group, 'Distance haze', 'MIX', fog, color, (.58, .72, .76, 1), 1030, 120)
    emission = node(group, 'ShaderNodeEmission', 'Painted surface', 1280, 120)
    L.new(color, emission.inputs['Color'])
    alpha = node(group, 'ShaderNodeMixShader', 'Preserve alpha', 1500, 0)
    transparent = node(group, 'ShaderNodeBsdfTransparent', 'Transparency', 1260, -160)
    L.new(gi.outputs['Alpha'], alpha.inputs[0])
    L.new(transparent.outputs[0], alpha.inputs[1])
    L.new(emission.outputs[0], alpha.inputs[2])
    L.new(alpha.outputs[0], go.inputs[0])
    return group

def surface_source(mat):
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None, None
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    if not out or not out.inputs['Surface'].is_linked:
        return None, None
    src = out.inputs['Surface'].links[0].from_node
    if src.type == 'BSDF_PRINCIPLED':
        emission = src.inputs.get('Emission Color') or src.inputs.get('Emission')
        strength = src.inputs.get('Emission Strength')
        if emission and (emission.is_linked or
                         (max(emission.default_value[:3]) > 0 and
                          (not strength or strength.is_linked or strength.default_value > 0))):
            return None, None
        return out, src
    if src.type == 'GROUP' and src.inputs.get('Base Tex') and src.inputs.get('Diffuse Color'):
        return out, src
    return None, None

def transfer(nt, source, target):
    if source.is_linked:
        nt.links.new(source.links[0].from_socket, target)
    else:
        target.default_value = source.default_value

def mmd_color_alpha(nt, source, preserve_sphere=True):
    # Mix white with base texture by the existing factor, then diffuse tint.
    white = (1, 1, 1, 1)
    def value(name):
        s = source.inputs[name]
        return s.links[0].from_socket if s.is_linked else s.default_value
    tex = mix(nt, 'ZD · MMD base texture', 'MIX', value('Base Tex Fac'), white, value('Base Tex'), -850, 400)
    color = mix(nt, 'ZD · MMD diffuse tint', 'MULTIPLY', 1, tex, value('Diffuse Color'), -620, 400)
    sphere_factor = value('Sphere Tex Fac')
    if preserve_sphere and (source.inputs['Sphere Tex'].is_linked or source.inputs['Sphere Tex Fac'].is_linked or sphere_factor != 0):
        mul = mix(nt, 'ZD · Sphere multiply', 'MULTIPLY', sphere_factor, color, value('Sphere Tex'), -400, 700)
        add = mix(nt, 'ZD · Sphere add', 'ADD', sphere_factor, color, value('Sphere Tex'), -400, 900)
        color = mix(nt, 'ZD · Sphere mode', 'MIX', value('Sphere Mul/Add'), mul, add, -180, 700)
    # Use MMD's own Alpha output to preserve its base/toon/sphere alpha semantics.
    alpha = source.outputs.get('Alpha')
    if alpha is None:
        alpha = math_node(nt, 'ZD · MMD alpha', 'MULTIPLY', value('Alpha'), value('Base Alpha'), -620, 200)
    return color, alpha

def convert_material(original, role, settings):
    if not surface_source(original)[0]:
        return None
    mat = original.copy()
    mat.name = f'ZD · {original.name}'
    mat['zd_owned'] = True
    mat['zd_original_name'] = original.name
    mat['zd_role'] = role
    mat['zd_preset'] = presets.selected(settings)
    mat['mr_adapter_revision'] = 2
    mat['mr_keep_sphere'] = settings.stage_keep_sphere if presets.selected(settings) == 'STAGE' else True
    nt = mat.node_tree
    out, src = surface_source(mat)
    g = node(nt, 'ShaderNodeGroup', NODE_NAME, out.location.x - 300, out.location.y)
    pipeline = presets.backend(settings)
    g.node_tree = pipeline.ensure_group() if pipeline else ensure_group()
    if src.type == 'BSDF_PRINCIPLED':
        transfer(nt, src.inputs['Base Color'], g.inputs['Base Color'])
        transfer(nt, src.inputs['Alpha'], g.inputs['Alpha'])
        if pipeline:
            for name in ('Roughness', 'Metallic'):
                if src.inputs[name].is_linked:
                    transfer(nt, src.inputs[name], g.inputs[name])
        if src.inputs['Normal'].is_linked:
            transfer(nt, src.inputs['Normal'], g.inputs['Normal'])
    else:
        color, alpha = mmd_color_alpha(nt, src, mat['mr_keep_sphere'])
        nt.links.new(color, g.inputs['Base Color'])
        nt.links.new(alpha, g.inputs['Alpha'])
    if not g.inputs['Normal'].is_linked:
        geometry = node(nt, 'ShaderNodeNewGeometry', 'ZD · Surface normal', -450, -350)
        nt.links.new(geometry.outputs['Normal'], g.inputs['Normal'])
    nt.links.new(g.outputs['Shader'], out.inputs['Surface'])
    update_material(mat, role, settings)
    return mat

def update_material(mat, role, s):
    from . import blush
    blush.configure(mat, s)
    pipeline = presets.backend(s)
    if pipeline:
        pipeline.update_material(mat, role, s)
        wet.configure(mat, s)
        return
    g = mat.node_tree.nodes[NODE_NAME]
    wanted = hair.ensure_group() if role == 'HAIR' and s.hair_enabled else ensure_group()
    if g.node_tree != wanted:
        hair.clear_drivers(g)
        previous = {socket.name: (tuple(socket.default_value) if socket.type in {'RGBA', 'VECTOR'} else socket.default_value,
                                 socket.links[0].from_socket if socket.is_linked else None)
                    for socket in g.inputs}
        g.node_tree = wanted
        for socket in g.inputs:
            if socket.name in previous:
                value, source = previous[socket.name]
                socket.default_value = value
                if source:
                    mat.node_tree.links.new(source, socket)
    tint, shadow, spec, roughness = PROFILES[role]
    values = {'Shadow Tint': tint, 'Threshold': s.threshold,
              'Softness': s.softness * (2.5 if role == 'ENV' else 1.3 if role == 'SKIN' else 1),
              'Shadow Strength': min(1, shadow * s.shadow_strength), 'Highlight': spec,
              'Roughness': roughness, 'Rim': s.rim * (.35 if role in {'SKIN', 'EYE'} else 1),
              'Mist Start': s.mist_start, 'Mist Density': s.mist_density}
    for key, val in values.items():
        if g.inputs.get(key):
            g.inputs[key].default_value = val
    if role == 'HAIR' and s.hair_enabled:
        hair.configure(mat, s)
    else:
        for n in list(mat.node_tree.nodes):
            if n.name.startswith(hair.PREFIX):
                mat.node_tree.nodes.remove(n)
    mat['zd_role'] = role
    lines.configure(mat, s, role)
    wet.configure(mat, s)

def is_outline_modifier(modifier):
    return modifier.type == 'SOLIDIFY' and any(
        word in modifier.name.lower() for word in ('outline', 'mmd_edge', 'mmd edge', '描边', '描邊', '輪郭'))

def apply_objects(objects, settings):
    result = {'applied': 0, 'skipped': []}
    cache = {}
    objects = list(objects)
    for obj in objects:
        if obj.type != 'MESH' or obj.library or obj.data.library:
            continue
        if settings.mute_outline and 'zd_outline_backup' not in obj:
            outlines = []
            for mod in obj.modifiers:
                if is_outline_modifier(mod):
                    outlines.append([mod.name, mod.show_render, mod.show_viewport])
                    mod.show_render = mod.show_viewport = False
            if outlines:
                obj['zd_outline_backup'] = json.dumps(outlines)
        backups = {b.index: b for b in obj.zelda_slot_backups}
        for index, slot in enumerate(obj.material_slots):
            mat = slot.material
            if not mat:
                continue
            backup = backups.get(index)
            if backup and mat != backup.applied:
                result['skipped'].append(f'{obj.name}/{mat.name}: 槽位已手动更改，请先恢复')
                continue
            original = backup.material if backup else mat
            hide_edge = settings.hair_hide_outline and lines.is_hair_outline(original, settings)
            if hide_edge:
                if not mat.get('zd_hidden_hair_outline'):
                    hidden = lines.invisible_outline(original)
                    if not backup:
                        backup = obj.zelda_slot_backups.add()
                        backup.index, backup.material, backup.link = index, mat, slot.link
                    previous = backup.applied
                    backup.applied = hidden
                    slot.link = 'OBJECT'
                    slot.material = hidden
                    if previous and previous.users == 0:
                        bpy.data.materials.remove(previous)
                result['applied'] += 1
                continue
            if mat.get('zd_hidden_hair_outline') and backup:
                derived = mat
                slot.material, slot.link = backup.material, backup.link
                obj.zelda_slot_backups.remove(next(i for i,b in enumerate(obj.zelda_slot_backups) if b == backup))
                backup = None
                mat = slot.material
                if derived.users == 0:
                    bpy.data.materials.remove(derived)
            role = settings.role if settings.role != 'AUTO' else classify(original)
            if backup and mat == backup.applied:
                if (mat.get('zd_preset', 'KINGDOM') != presets.selected(settings) or
                    (presets.selected(settings) == 'STAGE' and
                     (mat.get('mr_adapter_revision') != 2 or mat.get('mr_keep_sphere') != settings.stage_keep_sphere or
                      mat.node_tree.nodes[NODE_NAME].node_tree.get('mr_stage_version') != 2))):
                    derived = convert_material(original, role, settings)
                    if not derived:
                        result['skipped'].append(f'{obj.name}/{mat.name}: 不支持的新预设材质')
                        continue
                    previous = mat
                    backup.applied = derived
                    slot.material = derived
                    mat = derived
                    if previous.users == 0:
                        bpy.data.materials.remove(previous)
                else:
                    update_material(mat, role, settings)
                result['applied'] += 1
                continue
            if backup:
                result['skipped'].append(f'{obj.name}/{mat.name}: 槽位已手动更改，请先恢复')
                continue
            key = (obj.as_pointer(), mat.as_pointer(), role)
            if key not in cache:
                cache[key] = convert_material(mat, role, settings)
            derived = cache[key]
            if not derived:
                result['skipped'].append(f'{obj.name}/{mat.name}: 描边或不支持的节点结构')
                continue
            b = obj.zelda_slot_backups.add()
            b.index, b.material, b.applied, b.link = index, mat, derived, slot.link
            # Object-level overrides keep unselected objects sharing this mesh intact.
            slot.link = 'OBJECT'
            slot.material = derived
            result['applied'] += 1
    from . import blush
    for obj in objects:blush.prepare(obj, settings)
    return result

def restore_objects(objects):
    count = 0
    for obj in objects:
        if obj.type != 'MESH':
            continue
        for i in reversed(range(len(obj.zelda_slot_backups))):
            b = obj.zelda_slot_backups[i]
            if b.index >= len(obj.material_slots):
                continue
            slot = obj.material_slots[b.index]
            if slot.material != b.applied:
                # Respect user edits; keep the backup available for manual recovery.
                continue
            derived = b.applied
            slot.material = b.material
            slot.link = b.link
            obj.zelda_slot_backups.remove(i)
            if derived and derived.users == 0:
                bpy.data.materials.remove(derived)
            count += 1
        if not obj.zelda_slot_backups and 'zd_outline_backup' in obj:
            for name, render, viewport in json.loads(obj['zd_outline_backup']):
                mod = obj.modifiers.get(name)
                if mod:
                    mod.show_render, mod.show_viewport = render, viewport
            del obj['zd_outline_backup']
    from . import blush
    for obj in objects:
        if obj.type=='MESH' and not any(o.type=='MESH' and o.data==obj.data and any(slot.material and slot.material.get('mr_blush_active') for slot in o.material_slots) for o in bpy.data.objects):
            attr=obj.data.attributes.get(blush.ATTRIBUTE)
            if attr:obj.data.attributes.remove(attr)
    return count
