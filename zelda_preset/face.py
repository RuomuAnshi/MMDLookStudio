"""Soft anime face lighting for the stage preset, retaining texture and alpha."""
import bpy
GROUP_NAME='MR · Soft Anime Face v1'
PREFIX='MR · Face '


def is_face(material):
    name=material.get('zd_original_name',material.name).lower()
    return material.get('zd_role')=='SKIN' and any(x in name for x in ('face','顔','脸','面部','かお'))


def ensure_group():
    from .shading import node
    group=bpy.data.node_groups.get(GROUP_NAME)
    if group and group.get('mr_face_version')==1:return group
    group=bpy.data.node_groups.new(GROUP_NAME,'ShaderNodeTree');group['mr_face_version']=1
    for name,kind,value in [('Dry Shader','NodeSocketShader',None),('Base Color','NodeSocketColor',(.8,.6,.5,1)),
                            ('Normal','NodeSocketVector',(0,0,1)),('Alpha','NodeSocketFloat',1),
                            ('Softness','NodeSocketFloat',.85)]:
        socket=group.interface.new_socket(name=name,in_out='INPUT',socket_type=kind)
        if value is not None:socket.default_value=value
    group.interface.new_socket(name='Shader',in_out='OUTPUT',socket_type='NodeSocketShader')
    gi=node(group,'NodeGroupInput','Face inputs',-900,0);go=node(group,'NodeGroupOutput','Soft face',900,0)
    probe=node(group,'ShaderNodeBsdfDiffuse','White face light probe',-700,350)
    probe.inputs['Color'].default_value=(1,1,1,1);probe.inputs['Roughness'].default_value=1
    group.links.new(gi.outputs['Normal'],probe.inputs['Normal'])
    rgb=node(group,'ShaderNodeShaderToRGB','Face lighting and cast shadows',-500,350)
    group.links.new(probe.outputs[0],rgb.inputs[0])
    bw=node(group,'ShaderNodeRGBToBW','Neutral face illumination',-300,350);group.links.new(rgb.outputs[0],bw.inputs[0])
    transition=node(group,'ShaderNodeMapRange','Broad soft face transition',-100,350)
    transition.clamp=True;transition.interpolation_type='SMOOTHSTEP'
    transition.inputs['From Min'].default_value=.08;transition.inputs['From Max'].default_value=.8
    group.links.new(bw.outputs[0],transition.inputs['Value'])
    tone=node(group,'ShaderNodeMixRGB','Warm shallow face shadow',100,350)
    tone.inputs[1].default_value=(.8,.58,.58,1);tone.inputs[2].default_value=(1.3,1.15,1.13,1)
    group.links.new(transition.outputs[0],tone.inputs[0])
    color=node(group,'ShaderNodeMixRGB','Preserve face makeup and features',300,350)
    color.blend_type='MULTIPLY';color.inputs[0].default_value=1
    group.links.new(gi.outputs['Base Color'],color.inputs[1]);group.links.new(tone.outputs[0],color.inputs[2])
    toon=node(group,'ShaderNodeEmission','Soft texture face',500,350)
    group.links.new(color.outputs[0],toon.inputs['Color']);toon.inputs['Strength'].default_value=1
    transparent=node(group,'ShaderNodeBsdfTransparent','Original face alpha',300,-150)
    alpha=node(group,'ShaderNodeMixShader','Face transparency',500,0)
    group.links.new(gi.outputs['Alpha'],alpha.inputs[0]);group.links.new(transparent.outputs[0],alpha.inputs[1]);group.links.new(toon.outputs[0],alpha.inputs[2])
    mix=node(group,'ShaderNodeMixShader','Keep some physical rim response',700,100)
    group.links.new(gi.outputs['Softness'],mix.inputs[0]);group.links.new(gi.outputs['Dry Shader'],mix.inputs[1]);group.links.new(alpha.outputs[0],mix.inputs[2])
    group.links.new(mix.outputs[0],go.inputs[0])
    return group


def disconnect(material):
    tree=material.node_tree
    wrapper=tree.nodes.get(PREFIX+'Layer')
    if wrapper and wrapper.inputs['Dry Shader'].is_linked:
        source=wrapper.inputs['Dry Shader'].links[0].from_socket
        for link in list(wrapper.outputs[0].links):tree.links.new(source,link.to_socket)
    for n in list(tree.nodes):
        if n.name.startswith(PREFIX):tree.nodes.remove(n)


def configure(material,settings):
    from . import wet
    if not material.node_tree:return
    wet.disconnect(material);disconnect(material)
    material['mr_face_active']=False
    if material.get('zd_preset')!='STAGE' or not is_face(material) or settings.face_softness<=0:return
    tree=material.node_tree;surface=tree.nodes.get('ZD · Surface')
    output=next((n for n in tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output),None)
    if not surface or not output or not output.inputs['Surface'].is_linked:return
    wrapper=tree.nodes.new('ShaderNodeGroup');wrapper.name=wrapper.label=PREFIX+'Layer';wrapper.node_tree=ensure_group()
    wrapper.location=(output.location.x-200,output.location.y+250)
    tree.links.new(output.inputs['Surface'].links[0].from_socket,wrapper.inputs['Dry Shader'])
    for key in ('Base Color','Normal','Alpha'):
        source=surface.inputs[key]
        if source.is_linked:tree.links.new(source.links[0].from_socket,wrapper.inputs[key])
        else:wrapper.inputs[key].default_value=source.default_value
    wrapper.inputs['Softness'].default_value=settings.face_softness
    tree.links.new(wrapper.outputs[0],output.inputs['Surface']);material['mr_face_active']=True


def update_settings(settings,context):
    from . import wet
    seen=set()
    for obj in settings.id_data.objects:
        for slot in obj.material_slots:
            material=slot.material
            if not material or material.as_pointer() in seen or not material.get('zd_owned') or material.get('zd_preset')!='STAGE':continue
            seen.add(material.as_pointer());configure(material,settings);wet.configure(material,settings)
