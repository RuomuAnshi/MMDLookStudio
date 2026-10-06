"""Independent soft PBR stage pipeline, with two driven stylized hair lobes."""
import math
import bpy
from mathutils import Vector
from . import hair

GROUP_NAME = 'MR · Stage Surface v2'
BLOOM_THRESHOLD = 1.2
BLOOM_STRENGTH = .18
SCENE_REVISION = 3
# tint is retained in the base texture; these are role-specific surface properties.
PROFILES = {'SKIN':(.46,0,.06,.08), 'HAIR':(.26,0,.28,0),
            'CLOTH':(.47,0,.12,0), 'EYE':(.22,0,.2,0),
            'METAL':(.22,.9,.3,0), 'ENV':(.58,0,.08,0)}

def ensure_group():
    from .shading import node, math_node
    group=bpy.data.node_groups.get(GROUP_NAME)
    if group and group.get('mr_stage_version')==2:
        return group
    group=bpy.data.node_groups.new(GROUP_NAME,'ShaderNodeTree')
    group['mr_stage_version']=2
    inputs=[('Base Color','NodeSocketColor',(.5,.5,.5,1)),('Alpha','NodeSocketFloat',1),
            ('Normal','NodeSocketVector',(0,0,0)),('Roughness','NodeSocketFloat',.4),
            ('Metallic','NodeSocketFloat',0),('Coat','NodeSocketFloat',.25),
            ('Skin Softness','NodeSocketFloat',0),('Face Fill','NodeSocketFloat',0),
            ('Hair Tangent','NodeSocketVector',(0,0,1)),('Hair Color','NodeSocketColor',(1,1,1,1)),
            ('Hair Strength','NodeSocketFloat',0),('Hair Width','NodeSocketFloat',.12),
            ('Hair Feather','NodeSocketFloat',.08),('Hair Shift','NodeSocketFloat',0),
            ('Hair Mask','NodeSocketFloat',1)]
    for side,color in [('Warm',(1,.48,.17,1)),('Cold',(.25,.48,1,1))]:
        inputs += [(side+' Position','NodeSocketVector',(0,0,0)),
                   (side+' Energy','NodeSocketFloat',0),(side+' Color','NodeSocketColor',color)]
    for name,kind,value in inputs:
        socket=group.interface.new_socket(name=name,in_out='INPUT',socket_type=kind)
        socket.default_value=value
    group.interface.new_socket(name='Shader',in_out='OUTPUT',socket_type='NodeSocketShader')
    gi=node(group,'NodeGroupInput','Stage inputs',-1300,200)
    go=node(group,'NodeGroupOutput','Stage surface',1400,200)
    pbr=node(group,'ShaderNodeBsdfPrincipled','Soft physical surface',950,500)
    for source,target in [('Base Color','Base Color'),('Alpha','Alpha'),('Normal','Normal'),
                          ('Roughness','Roughness'),('Metallic','Metallic'),('Coat','Coat Weight'),
                          ('Skin Softness','Subsurface Weight')]:
        group.links.new(gi.outputs[source],pbr.inputs[target])
    pbr.inputs['Subsurface Scale'].default_value=.01
    pbr.inputs['Coat Roughness'].default_value=.25
    fill=node(group,'ShaderNodeEmission','Gentle face fill',950,100)
    group.links.new(gi.outputs['Base Color'],fill.inputs['Color'])
    group.links.new(gi.outputs['Face Fill'],fill.inputs['Strength'])
    combined=node(group,'ShaderNodeAddShader','Physical surface and face fill',1150,350)
    group.links.new(pbr.outputs[0],combined.inputs[0]);group.links.new(fill.outputs[0],combined.inputs[1])
    geo=node(group,'ShaderNodeNewGeometry','Surface view and position',-1300,-200)
    view=hair.vector(group,'Towards viewer','NORMALIZE',geo.outputs['Incoming'],x=-1100,y=-200)
    shifted=hair.vector(group,'Strand normal shift','SCALE',gi.outputs['Normal'],gi.outputs['Hair Shift'],-1100,-450)
    tangent=hair.vector(group,'Shifted tangent','ADD',gi.outputs['Hair Tangent'],shifted,-900,-450)
    tangent=hair.vector(group,'Normalized tangent','NORMALIZE',tangent,x=-700,y=-450)
    for index,side in enumerate(('Warm','Cold')):
        y=-750-index*750
        direction=hair.vector(group,side+' towards lamp','SUBTRACT',gi.outputs[side+' Position'],geo.outputs['Position'],-1100,y)
        direction=hair.vector(group,side+' direction','NORMALIZE',direction,x=-900,y=y)
        half=hair.vector(group,side+' half vector','ADD',direction,view,-700,y)
        half=hair.vector(group,side+' normalized half','NORMALIZE',half,x=-500,y=y)
        dot=hair.vector(group,side+' strand dot','DOT_PRODUCT',tangent,half,-300,y)
        alignment=math_node(group,side+' absolute alignment','ABSOLUTE',dot,x=-100,y=y)
        end=math_node(group,side+' band end','ADD',gi.outputs['Hair Width'],gi.outputs['Hair Feather'],-100,y-200)
        band=node(group,'ShaderNodeMapRange',side+' hair band',100,y)
        band.interpolation_type='SMOOTHSTEP';band.clamp=True
        for source,key in [(alignment,'Value'),(gi.outputs['Hair Width'],'From Min'),(end,'From Max')]:
            group.links.new(source,band.inputs[key])
        band.inputs['To Min'].default_value=1;band.inputs['To Max'].default_value=0
        facing=hair.vector(group,side+' facing lamp','DOT_PRODUCT',gi.outputs['Normal'],direction,-500,y-400)
        facing=math_node(group,side+' lit surface','MAXIMUM',facing,0,-300,y-400)
        amount=band.outputs[0]
        for j,source in enumerate((facing,gi.outputs['Hair Strength'],gi.outputs['Hair Mask'],gi.outputs[side+' Energy'])):
            amount=math_node(group,side+f' gate {j}','MULTIPLY',amount,source,300+j*140,y)
        emission=node(group,'ShaderNodeEmission',side+' hair reflection',950,y)
        color=node(group,'ShaderNodeMixRGB',side+' reflection tint',700,y-220)
        color.blend_type='MULTIPLY';color.inputs[0].default_value=1
        group.links.new(gi.outputs[side+' Color'],color.inputs[1]);group.links.new(gi.outputs['Hair Color'],color.inputs[2])
        group.links.new(color.outputs[0],emission.inputs['Color']);group.links.new(amount,emission.inputs['Strength'])
        add=node(group,'ShaderNodeAddShader',side+' added reflection',1150,y)
        group.links.new(combined.outputs[0],add.inputs[0]);group.links.new(emission.outputs[0],add.inputs[1])
        combined=add
    alpha=node(group,'ShaderNodeMixShader','Preserve original transparency',1350,0)
    transparent=node(group,'ShaderNodeBsdfTransparent','Original alpha holes',1150,0)
    group.links.new(gi.outputs['Alpha'],alpha.inputs[0]);group.links.new(transparent.outputs[0],alpha.inputs[1])
    group.links.new(combined.outputs[0],alpha.inputs[2]);group.links.new(alpha.outputs[0],go.inputs[0])
    # Transparency is applied once, outside all physical and stylized layers.
    pbr.inputs['Alpha'].default_value=1
    for link in list(pbr.inputs['Alpha'].links):group.links.remove(link)
    return group

def update_material(material,role,settings):
    from . import lines
    group=material.node_tree.nodes['ZD · Surface']
    rough,metal,coat,skin=PROFILES[role]
    for name,value in [('Roughness',rough),('Metallic',metal),('Coat',coat),
                       ('Skin Softness',skin),('Face Fill',.025 if role=='SKIN' else 0)]:
        if not group.inputs[name].is_linked:group.inputs[name].default_value=value
    if role=='HAIR' and settings.hair_enabled:
        hair.configure(material,settings,bind_light=False)
    else:
        group.inputs['Hair Strength'].default_value=0
    bind_lights(group,settings.id_data)
    material['zd_role']=role
    lines.configure(material,settings,role)
    from . import face
    face.configure(material,settings)

def bind_lights(group,scene):
    collection=scene.zelda_daylight.owned_collection
    for side in ('Warm','Cold'):
        lamp=next((o for o in collection.objects if o.get('mr_stage_side')==side),None) if collection else None
        for key,count in [(side+' Position',3),(side+' Energy',1),(side+' Color',3)]:
            socket=group.inputs[key]
            for axis in range(count):
                if count==1:socket.driver_remove('default_value')
                else:socket.driver_remove('default_value',axis)
                if not lamp:
                    if key.endswith('Energy'):socket.default_value=0
                    continue
                driver=(socket.driver_add('default_value') if count==1 else socket.driver_add('default_value',axis)).driver
                driver.type='SCRIPTED'
                var=driver.variables.new();var.name='value';var.type='SINGLE_PROP'
                var.targets[0].id=lamp
                if key.endswith('Position'):
                    var.type='TRANSFORMS'
                    var.targets[0].transform_type=('LOC_X','LOC_Y','LOC_Z')[axis]
                    var.targets[0].transform_space='WORLD_SPACE'
                if not key.endswith('Position'):
                    var.targets[0].data_path=('data.energy' if key.endswith('Energy') else f'data.color[{axis}]')
                driver.expression='value'
                if key.endswith('Energy'):
                    hidden=driver.variables.new();hidden.name='hidden';hidden.type='SINGLE_PROP'
                    hidden.targets[0].id=lamp;hidden.targets[0].data_path='hide_render'
                    scale=lamp.get('mr_stage_energy_scale',1)
                    driver.expression=f'max(0,value/{scale})*(1-hidden)'

def refresh_lights(scene):
    seen=set()
    for obj in scene.objects:
        for slot in obj.material_slots:
            material=slot.material
            if not material or material.as_pointer() in seen or material.get('zd_preset')!='STAGE':continue
            seen.add(material.as_pointer())
            bind_lights(material.node_tree.nodes['ZD · Surface'],scene)

def build_scene(scene,objects):
    s=scene.zelda_daylight
    objects=[o for o in objects if o.type=='MESH' and not o.hide_render]
    if not objects:objects=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
    points=[o.matrix_world@Vector(corner) for o in objects for corner in o.bound_box]
    if points:
        lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)])
        center=(lo+hi)*.5;size=max(hi.z-lo.z,hi.x-lo.x,.01)
    else:center=Vector((0,0,1));size=2
    front=Vector((0,-1,0))
    if scene.camera:
        front=scene.camera.matrix_world.translation-center
        front.z=0
        if front.length<.001:front=Vector((0,-1,0))
        front.normalize()
    right=Vector((0,0,1)).cross(front).normalized()
    collection=bpy.data.collections.new('MR · Cold Warm Stage Rig');scene.collection.children.link(collection)
    s.owned_collection=collection
    for side,offset,color,power,width in [
        ('Warm',(-.55,-.48,.34),(1,.42,.14),46, .25),
        ('Cold',(.58,-.42,.5),(.17,.35,1),48,.28),
        ('Fill',(-.1,.85,.4),(1,.94,.88),7,1.05),
        ('Catchlight',(-.12,.7,.18),(1,.96,.9),2.5,.08)]:
        data=bpy.data.lights.new('MR · Stage '+side,'AREA');data.shape='DISK'
        data.color=color;data.energy=power*size*size;data.size=width*size
        obj=bpy.data.objects.new(data.name,data);collection.objects.link(obj)
        obj.location=center+size*(right*offset[0]+front*offset[1]+Vector((0,0,offset[2])))
        obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
        obj['mr_stage_side']=side;obj['mr_stage_energy_scale']=power*size*size
    world=bpy.data.worlds.new('MR · Dark Blue Stage');world.use_nodes=True
    world.node_tree.nodes.clear()
    background=world.node_tree.nodes.new('ShaderNodeBackground')
    output=world.node_tree.nodes.new('ShaderNodeOutputWorld')
    world.node_tree.links.new(background.outputs[0],output.inputs['Surface'])
    background.inputs['Color'].default_value=(.025,.045,.12,1);background.inputs['Strength'].default_value=.2
    s.owned_world=world;scene.world=world
    scene.view_settings.view_transform='AgX';scene.view_settings.look='None';scene.view_settings.exposure=0
    if scene.camera and s.stage_dof:
        camera=scene.camera
        s.old_camera=camera;s.old_camera_data=camera.data
        camera.data=camera.data.copy();s.owned_camera_data=camera.data
        focus=bpy.data.objects.new('MR · Stage Focus',None);collection.objects.link(focus)
        focus.location=center+Vector((0,0,size*.2))
        # Prefer the actual deformed face to a torso-height bounding-box focus.
        face_positions=[]
        from .shading import classify
        for model in objects:
            face_indices={i for i,slot in enumerate(model.material_slots) if slot.material and
                          any(word in slot.material.get('zd_original_name',slot.material.name).lower()
                              for word in ('face','顔','脸'))}
            if not face_indices:continue
            evaluated=model.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh=evaluated.to_mesh()
            indices={v for polygon in mesh.polygons if polygon.material_index in face_indices for v in polygon.vertices}
            face_positions.extend(model.matrix_world@mesh.vertices[i].co for i in indices)
            evaluated.to_mesh_clear()
        if face_positions:
            focus.location=sum(face_positions,Vector())/len(face_positions)
        for model in objects:
            armature=next((mod.object for mod in model.modifiers if mod.type=='ARMATURE' and mod.object),None)
            if not armature:continue
            head=next((bone.name for bone in armature.data.bones if bone.name.lower() in ('head','頭','头','頭部','头部')),None)
            if head:
                world_position=focus.location.copy()
                focus.parent=armature;focus.parent_type='BONE';focus.parent_bone=head
                bpy.context.view_layer.update()
                transform=focus.matrix_world.copy();transform.translation=world_position
                focus.matrix_world=transform
                break
        camera.data.dof.use_dof=True;camera.data.dof.focus_object=focus
        camera.data.dof.aperture_fstop=5.6
