"""UV-independent, rest-mesh cheek mask and reversible base-color tint."""
import math
import bpy
from mathutils import Vector
PREFIX='MR · Blush '
ATTRIBUTE='mr_blush_cheeks_v1'


def eligible(material,settings):
    from .face import is_face
    custom=settings.blush_material
    return is_face(material) or bool(custom and (material==custom or material.get('zd_original_name')==custom.name))


def prepare(obj,settings):
    if obj.type!='MESH' or obj.library or obj.data.library:return
    indices={i for i,s in enumerate(obj.material_slots) if s.material and s.material.get('zd_owned') and eligible(s.material,settings)}
    if not settings.blush_enabled or settings.blush_amount<=0 or not indices:
        # Do not remove a mask still used by another object sharing this mesh.
        if not any(o!=obj and o.type=='MESH' and o.data==obj.data and any(s.material and s.material.get('mr_blush_active') for s in o.material_slots) for o in bpy.data.objects):
            attr=obj.data.attributes.get(ATTRIBUTE)
            if attr:obj.data.attributes.remove(attr)
        return
    verts={v for p in obj.data.polygons if p.material_index in indices for v in p.vertices}
    if not verts:return
    directions={'NEG_Y':(0,-1,0),'POS_Y':(0,1,0),'NEG_Z':(0,0,-1),'POS_Z':(0,0,1),'NEG_X':(-1,0,0),'POS_X':(1,0,0)}
    front=Vector(directions[settings.blush_front]);up=Vector((0,0,1)) if abs(front.z)<.5 else Vector((0,1,0))
    right=up.cross(front).normalized()
    xs=[obj.data.vertices[i].co.dot(right) for i in verts];zs=[obj.data.vertices[i].co.dot(up) for i in verts]
    xmin,xmax=min(xs),max(xs);zmin,zmax=min(zs),max(zs)
    width=max(xmax-xmin,1e-6);height=max(zmax-zmin,1e-6);center=(xmin+xmax)*.5
    values=[0.0]*len(obj.data.vertices)
    for i in verts:
        vertex=obj.data.vertices[i]
        x=(vertex.co.dot(right)-center)/width;z=(vertex.co.dot(up)-zmin)/height
        dx=(abs(x)-settings.blush_spacing)/settings.blush_width
        dz=(z-settings.blush_height)/settings.blush_radius
        # Gaussian diffusion has no hard perimeter or clipped opaque center.
        smooth=math.exp(-1.5*(dx*dx+dz*dz))
        bridge=.12*math.exp(-2*((x/.18)**2+((z-settings.blush_height)/settings.blush_radius)**2))
        smooth=max(smooth,bridge)
        facing=max(0,vertex.normal.dot(front))**.35
        values[i]=smooth*facing
    attr=obj.data.attributes.get(ATTRIBUTE) or obj.data.attributes.new(ATTRIBUTE,'FLOAT','POINT')
    attr.data.foreach_set('value',values);obj.data.update()


def disconnect(material):
    tree=material.node_tree;mix=tree.nodes.get(PREFIX+'Tint')
    if mix:
        source=mix.inputs[1]
        targets=[link.to_socket for link in list(mix.outputs[0].links)]
        for target in targets:
            if source.is_linked:tree.links.new(source.links[0].from_socket,target)
            else:
                for link in list(target.links):tree.links.remove(link)
                target.default_value=source.default_value
    for n in list(tree.nodes):
        if n.name.startswith(PREFIX):tree.nodes.remove(n)
    material['mr_blush_active']=False


def configure(material,settings):
    tree=material.node_tree
    if not tree:return
    disconnect(material)
    if not settings.blush_enabled or settings.blush_amount<=0 or not eligible(material,settings):return
    surface=tree.nodes.get('ZD · Surface')
    if not surface:return
    from .shading import node,math_node
    base=surface.inputs['Base Color'];mix=node(tree,'ShaderNodeMixRGB',PREFIX+'Tint',surface.location.x-230,surface.location.y+350)
    mix.blend_type='MULTIPLY'
    if base.is_linked:tree.links.new(base.links[0].from_socket,mix.inputs[1])
    else:mix.inputs[1].default_value=base.default_value
    mix.inputs[2].default_value=settings.blush_color
    if settings.blush_mask:
        uv=node(tree,'ShaderNodeUVMap',PREFIX+'UV',mix.location.x-600,mix.location.y);uv.uv_map=settings.blush_uv
        mask=node(tree,'ShaderNodeTexImage',PREFIX+'Mask',mix.location.x-450,mix.location.y);mask.image=settings.blush_mask
        tree.links.new(uv.outputs[0],mask.inputs['Vector']);source=mask.outputs['Color']
    else:
        mask=node(tree,'ShaderNodeAttribute',PREFIX+'Cheek mask',mix.location.x-450,mix.location.y)
        mask.attribute_name=ATTRIBUTE;source=mask.outputs['Fac']
    factor=math_node(tree,PREFIX+'Strength','MULTIPLY',source,-settings.blush_amount,mix.location.x-350,mix.location.y-200)
    attenuation=math_node(tree,PREFIX+'Smooth saturation','EXPONENT',factor,None,mix.location.x-170,mix.location.y-200)
    factor=math_node(tree,PREFIX+'Diffused tint','SUBTRACT',1,attenuation,mix.location.x,mix.location.y-200)
    factor=math_node(tree,PREFIX+'Preserve skin translucency','MULTIPLY',factor,.8,mix.location.x+150,mix.location.y-200)
    tree.links.new(factor,mix.inputs[0]);tree.links.new(mix.outputs[0],base)
    # Both stage physical skin and its soft-face layer must receive the same tint.
    wrapper=tree.nodes.get('MR · Face Layer')
    if wrapper:tree.links.new(mix.outputs[0],wrapper.inputs['Base Color'])
    material['mr_blush_active']=True


def update_settings(settings,context):
    from . import face,wet
    seen=set()
    for obj in settings.id_data.objects:
        if obj.type!='MESH':continue
        for slot in obj.material_slots:
            material=slot.material
            if not material or not material.get('zd_owned') or material.as_pointer() in seen:continue
            seen.add(material.as_pointer());configure(material,settings)
            if material.get('zd_preset')=='STAGE':face.configure(material,settings)
            wet.configure(material,settings)
        prepare(obj,settings)
