"""Optional UV-attached dielectric wet patches and droplet normals; no texture edits."""
import bpy
GROUP_NAME='MR · Wet Skin v2'
PREFIX='MR · Wet '


def ensure_group():
    from .shading import node,math_node
    from .hair import vector
    group=bpy.data.node_groups.get(GROUP_NAME)
    if group and group.get('mr_wet_version')==2:return group
    group=bpy.data.node_groups.new(GROUP_NAME,'ShaderNodeTree');group['mr_wet_version']=2
    for name,kind,value in [('Dry Shader','NodeSocketShader',None),('Normal','NodeSocketVector',(0,0,0)),
                            ('Alpha','NodeSocketFloat',1),('UV','NodeSocketVector',(0,0,0)),
                            ('Mask','NodeSocketFloat',1),('Amount','NodeSocketFloat',.85),
                            ('Film','NodeSocketFloat',1),('Drops','NodeSocketFloat',1),
                            ('Scale','NodeSocketFloat',28),('Relief','NodeSocketFloat',.004)]:
        socket=group.interface.new_socket(name=name,in_out='INPUT',socket_type=kind)
        if value is not None:socket.default_value=value
    group.interface.new_socket(name='Shader',in_out='OUTPUT',socket_type='NodeSocketShader')
    gi=node(group,'NodeGroupInput','Wet inputs',-1100,0);go=node(group,'NodeGroupOutput','Wet skin',1250,0)
    noise=node(group,'ShaderNodeTexNoise','Uneven water film',-900,350)
    noise.inputs['Scale'].default_value=9;noise.inputs['Detail'].default_value=2
    group.links.new(gi.outputs['UV'],noise.inputs['Vector'])
    patch=node(group,'ShaderNodeMapRange','Local film patches',-650,350);patch.clamp=True;patch.interpolation_type='SMOOTHSTEP'
    patch.inputs['From Min'].default_value=.42;patch.inputs['From Max'].default_value=.64
    group.links.new(noise.outputs['Fac'],patch.inputs['Value'])
    film=math_node(group,'Optional film','MULTIPLY',patch.outputs[0],gi.outputs['Film'],-400,350)
    vor=node(group,'ShaderNodeTexVoronoi','Tiny water droplets',-900,-150)
    vor.voronoi_dimensions='2D';vor.feature='F1';vor.distance='EUCLIDEAN'
    group.links.new(gi.outputs['UV'],vor.inputs['Vector']);group.links.new(gi.outputs['Scale'],vor.inputs['Scale'])
    droplet=node(group,'ShaderNodeMapRange','Rounded droplet profile',-650,-150)
    droplet.clamp=True;droplet.interpolation_type='SMOOTHSTEP'
    droplet.inputs['From Min'].default_value=.028;droplet.inputs['From Max'].default_value=.25
    droplet.inputs['To Min'].default_value=1;droplet.inputs['To Max'].default_value=0
    group.links.new(vor.outputs['Distance'],droplet.inputs['Value'])
    separate=node(group,'ShaderNodeSeparateXYZ','Per drop randomness',-650,-400)
    group.links.new(vor.outputs['Color'],separate.inputs[0])
    sparse=math_node(group,'Sparse droplet cells','GREATER_THAN',separate.outputs[0],.4,-450,-400)
    drops=math_node(group,'Sparse domes','MULTIPLY',droplet.outputs[0],sparse,-400,-150)
    drops=math_node(group,'Optional droplets','MULTIPLY',drops,gi.outputs['Drops'],-200,-150)
    height=drops
    for i,source in enumerate((gi.outputs['Amount'],gi.outputs['Mask'])):
        height=math_node(group,f'Droplet relief gate {i}','MULTIPLY',height,source,0+i*180,-250)
    bump=node(group,'ShaderNodeBump','Water bead normal',400,-250)
    bump.inputs['Strength'].default_value=.65
    group.links.new(height,bump.inputs['Height']);group.links.new(gi.outputs['Relief'],bump.inputs['Distance'])
    group.links.new(gi.outputs['Normal'],bump.inputs['Normal'])
    film=math_node(group,'Restrained film gloss','MULTIPLY',film,.22,-200,350)
    coverage=math_node(group,'Film or droplets','MAXIMUM',film,drops,0,350)
    for i,source in enumerate((gi.outputs['Amount'],gi.outputs['Mask'])):
        coverage=math_node(group,f'Water coverage gate {i}','MULTIPLY',coverage,source,200+i*180,350)
    fresnel=node(group,'ShaderNodeFresnel','Water dielectric Fresnel',400,150)
    fresnel.inputs['IOR'].default_value=1.333;group.links.new(bump.outputs['Normal'],fresnel.inputs['Normal'])
    amount=math_node(group,'Reflection coverage','MULTIPLY',coverage,fresnel.outputs[0],650,250)
    amount=math_node(group,'Readable water glints','MULTIPLY',amount,8,800,250)
    amount=math_node(group,'Bounded coat energy','MINIMUM',amount,.4,950,250)
    reflection=node(group,'ShaderNodeBsdfGlossy','Wet reflection',650,-150)
    reflection.inputs['Color'].default_value=(1,1,1,1);reflection.inputs['Roughness'].default_value=.028
    group.links.new(bump.outputs['Normal'],reflection.inputs['Normal'])
    transparent=node(group,'ShaderNodeBsdfTransparent','Keep alpha holes',650,-450)
    alpha=node(group,'ShaderNodeMixShader','Original alpha on reflection',850,-150)
    group.links.new(gi.outputs['Alpha'],alpha.inputs[0]);group.links.new(transparent.outputs[0],alpha.inputs[1])
    group.links.new(reflection.outputs[0],alpha.inputs[2])
    result=node(group,'ShaderNodeMixShader','Water over dry skin',1050,0)
    group.links.new(amount,result.inputs[0]);group.links.new(gi.outputs['Dry Shader'],result.inputs[1])
    group.links.new(alpha.outputs[0],result.inputs[2]);group.links.new(result.outputs[0],go.inputs[0])
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
    tree=material.node_tree
    if not tree:return
    disconnect(material)
    material['mr_wet_active']=False
    if not getattr(settings,'wet_enabled',False) or settings.wet_amount<=0 or material.get('zd_role')!='SKIN':return
    original=material.get('zd_original_name',material.name).lower()
    if not settings.wet_face and any(x in original for x in ('face','cheek','脸','顔','面部')):return
    surface=tree.nodes.get('ZD · Surface')
    output=next((n for n in tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output),None)
    if not surface or not output or not output.inputs['Surface'].is_linked:return
    wrapper=tree.nodes.new('ShaderNodeGroup');wrapper.name=wrapper.label=PREFIX+'Layer';wrapper.node_tree=ensure_group()
    wrapper.location=(output.location.x-180,output.location.y-300)
    source=output.inputs['Surface'].links[0].from_socket
    tree.links.new(source,wrapper.inputs['Dry Shader'])
    for name in ('Normal','Alpha'):
        socket=surface.inputs[name]
        if socket.is_linked:tree.links.new(socket.links[0].from_socket,wrapper.inputs[name])
        else:wrapper.inputs[name].default_value=socket.default_value
    uv=tree.nodes.new('ShaderNodeUVMap');uv.name=PREFIX+'UV';uv.uv_map=settings.wet_uv
    uv.location=(wrapper.location.x-450,wrapper.location.y-200)
    tree.links.new(uv.outputs[0],wrapper.inputs['UV'])
    for name,value in [('Amount',settings.wet_amount),('Scale',settings.wet_scale),
                       ('Film',settings.wet_style!='DROPS'),('Drops',settings.wet_style!='FILM')]:
        wrapper.inputs[name].default_value=value
    if settings.wet_mask:
        mask=tree.nodes.new('ShaderNodeTexImage');mask.name=PREFIX+'Mask';mask.image=settings.wet_mask
        tree.links.new(uv.outputs[0],mask.inputs['Vector']);tree.links.new(mask.outputs['Color'],wrapper.inputs['Mask'])
    tree.links.new(wrapper.outputs[0],output.inputs['Surface'])
    material['mr_wet_active']=True


def update_settings(settings,context):
    # Scene controls only refresh already-derived skin materials; no conversion or scene changes.
    scene=settings.id_data
    seen=set()
    for obj in scene.objects:
        if obj.type!='MESH':continue
        for slot in obj.material_slots:
            material=slot.material
            if not material or not material.get('zd_owned') or material.as_pointer() in seen:continue
            seen.add(material.as_pointer())
            if material.get('zd_role')=='SKIN':configure(material,settings)
