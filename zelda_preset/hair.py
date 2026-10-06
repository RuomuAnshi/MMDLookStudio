"""Native-node directional hair bands with persistent, simple sun drivers."""
import bpy

GROUP_NAME = 'ZD · Hair Toon v1'
PREFIX = 'ZD · Hair '


def vector(tree, name, operation, a, b=None, x=0, y=0):
    from .shading import node
    n = node(tree, 'ShaderNodeVectorMath', name, x, y)
    n.operation = operation
    for socket, value in ((n.inputs[0], a), (n.inputs['Scale'] if operation == 'SCALE' else n.inputs[1], b)):
        if value is None:
            continue
        if hasattr(value, 'node'):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return n.outputs['Value'] if operation in {'DOT_PRODUCT', 'LENGTH', 'DISTANCE'} else n.outputs['Vector']


def ensure_group():
    from . import shading
    group = bpy.data.node_groups.get(GROUP_NAME)
    if group and group.get('zd_hair_version') == 1:
        return group
    group = shading.ensure_group().copy()
    group.name = GROUP_NAME
    group['zd_hair_version'] = 1
    for socket in list(group.interface.items_tree):
        if socket.item_type == 'SOCKET' and socket.in_out == 'INPUT' and socket.name in {'Highlight', 'Roughness'}:
            group.interface.remove(socket)
    inputs = [('Hair Tangent', 'NodeSocketVector', (0, 0, 1)),
              ('Light Direction', 'NodeSocketVector', (0, -1, 1)),
              ('Light Strength', 'NodeSocketFloat', 1),
              ('Hair Color', 'NodeSocketColor', (.72, .87, 1, 1)),
              ('Hair Strength', 'NodeSocketFloat', .32),
              ('Hair Width', 'NodeSocketFloat', .16),
              ('Hair Feather', 'NodeSocketFloat', .06),
              ('Hair Shift', 'NodeSocketFloat', 0),
              ('Hair Mask', 'NodeSocketFloat', 1)]
    for name, kind, default in inputs:
        socket = group.interface.new_socket(name=name, in_out='INPUT', socket_type=kind)
        socket.default_value = default
    gi = next(n for n in group.nodes if n.type == 'GROUP_INPUT')
    old = group.nodes['Small warm highlights']
    base = old.inputs[1].links[0].from_socket
    geometry = shading.node(group, 'ShaderNodeNewGeometry', 'Hair view direction', -900, -1300)
    # Incoming already points from the surface towards the viewer in Blender.
    view = vector(group, 'Towards camera', 'NORMALIZE', geometry.outputs['Incoming'], x=-700, y=-1300)
    light = vector(group, 'Normalized sun direction', 'NORMALIZE', gi.outputs['Light Direction'], x=-900, y=-1510)
    halfway = vector(group, 'Light plus view', 'ADD', light, view, -470, -1300)
    halfway = vector(group, 'Halfway direction', 'NORMALIZE', halfway, x=-250, y=-1300)
    normal_shift = vector(group, 'Shift along surface normal', 'SCALE', gi.outputs['Normal'], gi.outputs['Hair Shift'], -900, -1740)
    tangent = vector(group, 'Shifted strand direction', 'ADD', gi.outputs['Hair Tangent'], normal_shift, -650, -1740)
    tangent = vector(group, 'Normalized strand direction', 'NORMALIZE', tangent, x=-430, y=-1740)
    dot = vector(group, 'Strand and halfway alignment', 'DOT_PRODUCT', tangent, halfway, -200, -1510)
    alignment = shading.math_node(group, 'Absolute strand alignment', 'ABSOLUTE', dot, x=0, y=-1510)
    end = shading.math_node(group, 'Band plus feather', 'ADD', gi.outputs['Hair Width'], gi.outputs['Hair Feather'], 0, -1760)
    band = shading.node(group, 'ShaderNodeMapRange', 'Directional hair band', 230, -1510)
    band.interpolation_type = 'SMOOTHSTEP'
    band.clamp = True
    for source, key in ((alignment, 'Value'), (gi.outputs['Hair Width'], 'From Min'), (end, 'From Max')):
        group.links.new(source, band.inputs[key])
    band.inputs['To Min'].default_value = 1
    band.inputs['To Max'].default_value = 0
    amount = band.outputs['Result']
    for i, source in enumerate((gi.outputs['Hair Strength'], gi.outputs['Hair Mask'],
                               group.nodes['Two-tone light boundary'].outputs['Result'],
                               gi.outputs['Light Strength'])):
        amount = shading.math_node(group, f'Hair band gate {i}', 'MULTIPLY', amount, source, 450+i*170, -1500)
    color = shading.mix(group, 'Tinted directional hair highlight', 'MIX', amount, base, gi.outputs['Hair Color'], 500, 120)
    for link in list(old.outputs[0].links):
        group.links.new(color, link.to_socket)
    for name in ('Material highlight probe', 'Highlight light', 'Highlight luminance',
                 'Simplified highlight', 'Highlight amount', 'Small warm highlights'):
        group.nodes.remove(group.nodes[name])
    return group


def choose_sun(scene):
    chosen = scene.zelda_daylight.hair_light
    if chosen and chosen in scene.objects.values() and chosen.type == 'LIGHT' and chosen.data.type == 'SUN':
        return chosen
    candidates = [o for o in scene.objects if o.type == 'LIGHT' and o.data.type == 'SUN'
                  and not o.hide_render]
    rig = scene.zelda_daylight.owned_collection
    return max(candidates, key=lambda o: (bool(rig and o.name in rig.objects), o.data.energy), default=None)


def clear_drivers(group_node):
    for name in ('Light Direction', 'Light Strength'):
        socket = group_node.inputs.get(name)
        if socket:
            if name == 'Light Direction':
                for axis in range(3):
                    socket.driver_remove('default_value', axis)
            else:
                socket.driver_remove('default_value')


def bind_sun(group_node, scene):
    clear_drivers(group_node)
    sun = choose_sun(scene)
    strength = group_node.inputs['Light Strength']
    if not sun:
        strength.default_value = 0
        return
    # World XYZ Euler decomposition of the sun's transformed local +Z axis.
    expressions = ('cos(rz)*sin(ry)*cos(rx)+sin(rz)*sin(rx)',
                   'sin(rz)*sin(ry)*cos(rx)-cos(rz)*sin(rx)',
                   'cos(ry)*cos(rx)')
    for axis, expression in enumerate(expressions):
        driver = group_node.inputs['Light Direction'].driver_add('default_value', axis).driver
        driver.type = 'SCRIPTED'
        driver.expression = expression
        for name, transform in zip(('rx', 'ry', 'rz'), ('ROT_X', 'ROT_Y', 'ROT_Z')):
            variable = driver.variables.new()
            variable.name, variable.type = name, 'TRANSFORMS'
            target = variable.targets[0]
            target.id = sun
            target.transform_type = transform
            target.transform_space = 'WORLD_SPACE'
            target.rotation_mode = 'XYZ'
    driver = strength.driver_add('default_value').driver
    driver.type = 'SCRIPTED'
    driver.expression = 'min(1,max(0,energy/2.2))*(1-hidden)'
    for name, path in (('energy', 'data.energy'), ('hidden', 'hide_render')):
        variable = driver.variables.new()
        variable.name, variable.type = name, 'SINGLE_PROP'
        variable.targets[0].id = sun
        variable.targets[0].data_path = path


def configure(material, settings, bind_light=True):
    from .shading import node, math_node
    tree = material.node_tree
    group = tree.nodes['ZD · Surface']
    for n in list(tree.nodes):
        if n.name.startswith(PREFIX):
            tree.nodes.remove(n)
    normal = group.inputs['Normal'].links[0].from_socket
    uv = node(tree, 'ShaderNodeTangent', PREFIX+'UV tangent', -1000, -600)
    uv.direction_type = 'UV_MAP'
    uv.uv_map = settings.hair_uv
    across = vector(tree, PREFIX+'UV bitangent', 'CROSS_PRODUCT', normal, uv.outputs[0], -800, -600)
    if settings.hair_direction == 'UV_U':
        direction = uv.outputs[0]
    elif settings.hair_direction == 'UV_V':
        direction = across
    else:
        axis = node(tree, 'ShaderNodeVectorTransform', PREFIX+'Object vertical', -1000, -850)
        axis.vector_type, axis.convert_from, axis.convert_to = 'VECTOR', 'OBJECT', 'WORLD'
        axis.inputs[0].default_value = (0, 0, 1)
        dot = vector(tree, PREFIX+'Vertical normal projection', 'DOT_PRODUCT', axis.outputs[0], normal, -800, -850)
        perpendicular = vector(tree, PREFIX+'Vertical normal component', 'SCALE', normal, dot, -600, -850)
        projected = vector(tree, PREFIX+'Surface flow', 'SUBTRACT', axis.outputs[0], perpendicular, -400, -850)
        length = vector(tree, PREFIX+'Flow length', 'LENGTH', projected, x=-200, y=-1050)
        valid = math_node(tree, PREFIX+'Stable flow', 'GREATER_THAN', length, .01, 0, -1050)
        inverse = math_node(tree, PREFIX+'Cap fallback', 'SUBTRACT', 1, valid, 180, -1050)
        main = vector(tree, PREFIX+'Vertical contribution', 'SCALE', projected, valid, -180, -850)
        cap = vector(tree, PREFIX+'UV cap contribution', 'SCALE', uv.outputs[0], inverse, 0, -650)
        direction = vector(tree, PREFIX+'Combined flow', 'ADD', main, cap, 180, -850)
    if settings.hair_flow_map:
        image = node(tree, 'ShaderNodeTexImage', PREFIX+'Flow map', -1000, -1300)
        image.image = settings.hair_flow_map
        coords = node(tree, 'ShaderNodeUVMap', PREFIX+'UV map', -1200, -1300)
        coords.uv_map = settings.hair_uv
        tree.links.new(coords.outputs[0], image.inputs['Vector'])
        separate = node(tree, 'ShaderNodeSeparateXYZ', PREFIX+'Flow channels', -780, -1300)
        tree.links.new(image.outputs['Color'], separate.inputs[0])
        components = []
        for index, source in enumerate((uv.outputs[0], across)):
            component = math_node(tree, PREFIX+f'Flow remap {index}', 'MULTIPLY_ADD', separate.outputs[index], 2, -560, -1300-index*180)
            component.node.inputs[2].default_value = -1
            components.append(vector(tree, PREFIX+f'Flow direction {index}', 'SCALE', source, component, -340, -1300-index*180))
        mapped = vector(tree, PREFIX+'Mapped flow', 'ADD', *components, -100, -1300)
        length = vector(tree, PREFIX+'Map length', 'LENGTH', mapped, x=100, y=-1480)
        valid = math_node(tree, PREFIX+'Valid map flow', 'GREATER_THAN', length, .01, 280, -1480)
        inverse = math_node(tree, PREFIX+'Map fallback', 'SUBTRACT', 1, valid, 460, -1480)
        mapped = vector(tree, PREFIX+'Mapped contribution', 'SCALE', mapped, valid, 100, -1300)
        fallback = vector(tree, PREFIX+'Fallback contribution', 'SCALE', direction, inverse, 280, -1120)
        direction = vector(tree, PREFIX+'Mapped or default', 'ADD', mapped, fallback, 460, -1300)
    direction = vector(tree, PREFIX+'Normalized flow', 'NORMALIZE', direction, x=650, y=-850)
    tree.links.new(direction, group.inputs['Hair Tangent'])
    mask = group.inputs['Hair Mask']
    if settings.hair_mask:
        texture = node(tree, 'ShaderNodeTexImage', PREFIX+'Highlight mask', -1000, -1700)
        texture.image = settings.hair_mask
        coords = node(tree, 'ShaderNodeUVMap', PREFIX+'Mask UV', -1200, -1700)
        coords.uv_map = settings.hair_uv
        tree.links.new(coords.outputs[0], texture.inputs['Vector'])
        tree.links.new(texture.outputs['Color'], mask)
    else:
        mask.default_value = 1
    for name, value in (('Hair Color', settings.hair_color), ('Hair Strength', settings.hair_strength),
                        ('Hair Width', settings.hair_width), ('Hair Feather', settings.hair_feather),
                        ('Hair Shift', settings.hair_shift)):
        group.inputs[name].default_value = value
    if bind_light:
        bind_sun(group, settings.id_data)


def refresh_lights(scene):
    visited = set()
    for obj in scene.objects:
        for slot in obj.material_slots:
            material = slot.material
            if not material or not material.get('zd_owned') or material.as_pointer() in visited:
                continue
            visited.add(material.as_pointer())
            group = material.node_tree.nodes.get('ZD · Surface')
            if group and group.node_tree and group.node_tree.get('zd_hair_version'):
                bind_sun(group, scene)
