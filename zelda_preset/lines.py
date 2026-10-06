"""Reversible hair outline hiding and native local texture-line repair."""
import bpy

GROUP_NAME = 'ZD · Hair Line Repair v1'
PREFIX = 'ZD · Line '


def is_hair_outline(material, settings):
    chosen = settings.hair_outline_material
    if material == chosen or (chosen and chosen.get('zd_owned') and
                              chosen.get('zd_original_name') == material.name):
        return True
    name = material.get('zd_original_name', material.name).lower()
    hair = any(word in name for word in ('hair', '髪', '头发', '頭髮', '发_', '髮'))
    edge = any(word in name for word in ('outline', 'edge', '描边', '描邊', '輪郭', '黑边', '黑邊'))
    return hair and edge


def invisible_outline(original):
    material = original.copy()
    material.name = f'ZD · Hidden hair outline · {original.name}'
    material.use_nodes = True
    material['zd_owned'] = True
    material['zd_original_name'] = original.name
    material['zd_hidden_hair_outline'] = True
    tree = material.node_tree
    output = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    if output is None:
        output = tree.nodes.new('ShaderNodeOutputMaterial')
    transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
    transparent.name = transparent.label = 'ZD · Invisible outline'
    transparent.inputs[0].default_value = (1,1,1,1)
    tree.links.new(transparent.outputs[0],output.inputs['Surface'])
    if hasattr(material, 'surface_render_method'):
        methods = material.bl_rna.properties['surface_render_method'].enum_items
        if any(item.identifier == 'DITHERED' for item in methods):
            material.surface_render_method = 'DITHERED'
    return material


def ensure_group():
    from .shading import node, math_node, mix
    from .hair import vector
    group = bpy.data.node_groups.get(GROUP_NAME)
    if group and group.get('zd_line_version') == 1:
        return group
    group = bpy.data.node_groups.new(GROUP_NAME, 'ShaderNodeTree')
    group['zd_line_version'] = 1
    for name, kind, default in [('Original Color','NodeSocketColor',(.2,.3,.4,1)),
                                ('Strength','NodeSocketFloat',.9),
                                ('Threshold','NodeSocketFloat',.03),
                                ('Contrast','NodeSocketFloat',1.6),
                                ('Mask','NodeSocketFloat',1)]:
        socket = group.interface.new_socket(name=name,in_out='INPUT',socket_type=kind)
        socket.default_value = default
    for index in range(8):
        for suffix,kind,default in [('Color','NodeSocketColor',(0,0,0,1)),('Alpha','NodeSocketFloat',1)]:
            socket = group.interface.new_socket(name=f'Neighbour {index} {suffix}',in_out='INPUT',socket_type=kind)
            socket.default_value = default
    group.interface.new_socket(name='Color',in_out='OUTPUT',socket_type='NodeSocketColor')
    gi = node(group,'NodeGroupInput','Repair inputs',-1100,0)
    go = node(group,'NodeGroupOutput','Repaired color',1350,0)
    luminance = node(group,'ShaderNodeRGBToBW','Original texture luminance',-850,500)
    group.links.new(gi.outputs['Original Color'],luminance.inputs[0])
    minimum = math_node(group,'Required local contrast','MULTIPLY',luminance.outputs[0],gi.outputs['Contrast'],-650,500)
    minimum = math_node(group,'Reject black neighbours','MAXIMUM',minimum,.0001,-450,500)
    weight_sum = None
    color_sum = None
    for index in range(8):
        y = -index*230
        lum = node(group,'ShaderNodeRGBToBW',f'Neighbour {index} luminance',-850,y)
        group.links.new(gi.outputs[f'Neighbour {index} Color'],lum.inputs[0])
        brighter = math_node(group,f'Neighbour {index} brighter','GREATER_THAN',lum.outputs[0],minimum,-650,y)
        opaque = math_node(group,f'Neighbour {index} opaque','GREATER_THAN',gi.outputs[f'Neighbour {index} Alpha'],.5,-650,y-90)
        weight = math_node(group,f'Neighbour {index} weight','MULTIPLY',brighter,opaque,-450,y)
        weighted = vector(group,f'Neighbour {index} weighted color','SCALE',gi.outputs[f'Neighbour {index} Color'],weight,-250,y)
        weight_sum = weight if weight_sum is None else math_node(group,f'Weight sum {index}','ADD',weight_sum,weight,0,y)
        color_sum = weighted if color_sum is None else vector(group,f'Color sum {index}','ADD',color_sum,weighted,200,y)
    denominator = math_node(group,'Safe weight sum','MAXIMUM',weight_sum,.0001,450,-1200)
    reciprocal = math_node(group,'Inverse weight sum','DIVIDE',1,denominator,650,-1200)
    average = vector(group,'Nearby hair color','SCALE',color_sum,reciprocal,850,-1000)
    candidate = node(group,'ShaderNodeMapRange','Dark line eligibility',-250,500)
    candidate.clamp = True
    candidate.interpolation_type = 'SMOOTHSTEP'
    group.links.new(luminance.outputs[0],candidate.inputs['Value'])
    candidate.inputs['From Min'].default_value = 0
    group.links.new(gi.outputs['Threshold'],candidate.inputs['From Max'])
    candidate.inputs['To Min'].default_value = 1
    candidate.inputs['To Max'].default_value = 0
    valid = math_node(group,'Has valid nearby hair','GREATER_THAN',weight_sum,.5,450,300)
    amount = candidate.outputs['Result']
    for index,source in enumerate((valid,gi.outputs['Strength'],gi.outputs['Mask'])):
        amount = math_node(group,f'Repair gate {index}','MULTIPLY',amount,source,650+index*170,300)
    color = mix(group,'Local hair line replacement','MIX',amount,gi.outputs['Original Color'],average,1100,0)
    group.links.new(color,go.inputs[0])
    return group


def disconnect(material):
    tree = material.node_tree
    repair = tree.nodes.get(PREFIX+'Repair')
    if repair and repair.inputs['Original Color'].is_linked:
        source = repair.inputs['Original Color'].links[0].from_socket
        for link in list(repair.outputs['Color'].links):
            tree.links.new(source,link.to_socket)
    for n in list(tree.nodes):
        if n.name.startswith(PREFIX):
            tree.nodes.remove(n)


def configure(material, settings, role):
    from .shading import node, NODE_NAME
    from .hair import vector
    disconnect(material)
    if role != 'HAIR' or not settings.hair_clean_lines or settings.hair_line_strength <= 0:
        material['zd_line_repair'] = 'disabled'
        return
    tree = material.node_tree
    base = tree.nodes.get('ZD · MMD base texture')
    target = base.inputs[2] if base else tree.nodes[NODE_NAME].inputs['Base Color']
    if not target.is_linked or target.links[0].from_node.type != 'TEX_IMAGE':
        material['zd_line_repair'] = 'requires direct base image'
        return
    source = target.links[0].from_socket
    sampler = source.node
    image = sampler.image
    if not image or sampler.projection != 'FLAT' or image.source == 'TILED':
        material['zd_line_repair'] = 'unsupported image projection'
        return
    try:
        if not image.size[0] or not image.size[1]:
            _ = image.pixels[0]
        width,height = image.size
        if not width or not height:
            raise ValueError('image unavailable')
    except (IndexError,ValueError,RuntimeError):
        material['zd_line_repair'] = 'base image unavailable'
        return
    repair = node(tree,'ShaderNodeGroup',PREFIX+'Repair',sampler.location.x+300,sampler.location.y-300)
    repair.node_tree = ensure_group()
    tree.links.new(source,repair.inputs['Original Color'])
    if sampler.inputs['Vector'].is_linked:
        uv = sampler.inputs['Vector'].links[0].from_socket
    else:
        coordinates = node(tree,'ShaderNodeUVMap',PREFIX+'Base UV',sampler.location.x-450,sampler.location.y-300)
        uv = coordinates.outputs[0]
    radius = settings.hair_line_radius
    offsets = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
    for index,(x,y) in enumerate(offsets):
        shifted = vector(tree,PREFIX+f'UV offset {index}','ADD',uv,(x*radius/width,y*radius/height,0),-1400,-index*230)
        sample = node(tree,'ShaderNodeTexImage',PREFIX+f'Neighbour {index}',-1150,-index*230)
        sample.image = image
        sample.interpolation = sampler.interpolation
        sample.extension = sampler.extension
        tree.links.new(shifted,sample.inputs['Vector'])
        tree.links.new(sample.outputs['Color'],repair.inputs[f'Neighbour {index} Color'])
        tree.links.new(sample.outputs['Alpha'],repair.inputs[f'Neighbour {index} Alpha'])
    for key,value in [('Strength',settings.hair_line_strength),('Threshold',settings.hair_line_threshold),
                      ('Contrast',settings.hair_line_contrast)]:
        repair.inputs[key].default_value = value
    if settings.hair_line_mask:
        mask = node(tree,'ShaderNodeTexImage',PREFIX+'Repair mask',-1150,-2050)
        mask.image = settings.hair_line_mask
        tree.links.new(uv,mask.inputs['Vector'])
        tree.links.new(mask.outputs['Color'],repair.inputs['Mask'])
    tree.links.new(repair.outputs['Color'],target)
    material['zd_line_repair'] = 'active'
