import json
import math
import bpy
from mathutils import Vector

def _world():
    world = bpy.data.worlds.new('ZD · Daylight Sky')
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    geometry = nt.nodes.new('ShaderNodeNewGeometry')
    separate = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geometry.outputs['Incoming'], separate.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0
    ramp.color_ramp.elements[0].color = (.52, .72, .76, 1)
    ramp.color_ramp.elements[1].position = .8
    ramp.color_ramp.elements[1].color = (.13, .36, .57, 1)
    nt.links.new(separate.outputs['Z'], ramp.inputs[0])
    background = nt.nodes.new('ShaderNodeBackground')
    nt.links.new(ramp.outputs[0], background.inputs['Color'])
    output = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(background.outputs[0], output.inputs[0])
    for n, x in zip((geometry, separate, ramp, background, output), (-800, -600, -400, 0, 220)):
        n.location = (x, 0)
    return world

def _compositor(scene):
    # Modern compositor owns its tree separately; 4.x uses scene.node_tree.
    modern = hasattr(scene, 'compositing_node_group')
    if modern:
        tree = bpy.data.node_groups.new('ZD · Gentle Bloom', 'CompositorNodeTree')
        tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        scene.compositing_node_group = tree
    else:
        scene.use_nodes = True
        tree = scene.node_tree
        # In 4.x retain every existing node and output link, use a passthrough reroute backup.
    render = tree.nodes.new('CompositorNodeRLayers')
    render.name = 'ZD · Render'
    glare = tree.nodes.new('CompositorNodeGlare')
    glare.name = 'ZD · Bloom'
    if glare.inputs.get('Type'):
        glare.inputs['Type'].default_value = 'Fog Glow'
        glare.inputs['Quality'].default_value = 'High'
    else:
        glare.glare_type = 'FOG_GLOW'
        glare.quality = 'HIGH'
    if glare.inputs.get('Threshold'):
        glare.inputs['Threshold'].default_value = 1.35
    elif hasattr(glare, 'threshold'):
        glare.threshold = 1.35
    if hasattr(glare, 'mix'):
        glare.mix = -.94
    if glare.inputs.get('Strength'):
        glare.inputs['Strength'].default_value = .06
    tree.links.new(render.outputs['Image'], glare.inputs['Image'])
    render.location = (-450, 0)
    glare.location = (-180, 0)
    if modern:
        output = tree.nodes.new('NodeGroupOutput')
        tree.links.new(glare.outputs['Image'], output.inputs['Image'])
    else:
        output = next((n for n in tree.nodes if n.type == 'COMPOSITE'), None)
        if output is None:
            output = tree.nodes.new('CompositorNodeComposite')
            output.name = 'ZD · Output'
        backup = tree.nodes.new('NodeReroute')
        backup.name = 'ZD · Previous composite'
        if output.inputs['Image'].is_linked:
            tree.links.new(output.inputs['Image'].links[0].from_socket, backup.inputs[0])
        tree.links.new(glare.outputs['Image'], output.inputs['Image'])
    output.location = (150, 0)
    return tree

def apply(scene, objects=None):
    try:
        _apply(scene, objects)
        from . import hair
        hair.refresh_lights(scene)
        from . import presets
        presets.refresh_lights(scene)
    except Exception:
        restore(scene)
        raise

def _apply(scene, objects=None):
    s = scene.zelda_daylight
    from . import presets, stage
    if s.active:
        if s.active_preset == presets.selected(s):
            camera_changed = (presets.selected(s) == 'STAGE' and scene.camera and
                              (bool(s.owned_camera_data) != s.stage_dof or (s.stage_dof and s.old_camera != scene.camera)))
            pipeline = presets.backend(s)
            revision_changed = pipeline and s.active_scene_revision != pipeline.SCENE_REVISION
            if not camera_changed and not revision_changed:
                return
        restore(scene)
    s.old_world = scene.world
    modern = hasattr(scene, 'compositing_node_group')
    s.old_compositor = scene.compositing_node_group if modern else None
    s.old_scene = json.dumps({'engine': scene.render.engine,
        'view_transform': scene.view_settings.view_transform,
        'look': scene.view_settings.look, 'exposure': scene.view_settings.exposure,
        'gamma': scene.view_settings.gamma, 'use_nodes': getattr(scene, 'use_nodes', False),
        'compositing': scene.render.use_compositing})
    s.active = True
    s.active_preset = presets.selected(s)
    for key in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            scene.render.engine = key
            break
        except TypeError:
            continue
    pipeline = presets.backend(s)
    s.active_scene_revision = pipeline.SCENE_REVISION if pipeline else 0
    if pipeline:
        if s.replace_lights:
            for obj in scene.objects:
                if obj.type == 'LIGHT':
                    backup = s.lights.add()
                    backup.light, backup.hidden = obj, obj.hide_render
                    backup.hidden_viewport = obj.hide_viewport
                    obj.hide_render = obj.hide_viewport = True
        pipeline.build_scene(scene, objects if objects is not None else bpy.context.selected_objects)
        s.owned_compositor = _compositor(scene)
        glare = s.owned_compositor.nodes['ZD · Bloom']
        if glare.inputs.get('Threshold'):
            glare.inputs['Threshold'].default_value = pipeline.BLOOM_THRESHOLD
        if glare.inputs.get('Strength'):
            glare.inputs['Strength'].default_value = pipeline.BLOOM_STRENGTH
        scene.render.use_compositing = True
        return
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = -.12
    scene.view_settings.gamma = 1
    if s.replace_lights:
        for obj in scene.objects:
            if obj.type == 'LIGHT':
                b = s.lights.add()
                b.light, b.hidden = obj, obj.hide_render
                b.hidden_viewport = obj.hide_viewport
                obj.hide_render = True
                obj.hide_viewport = True
    collection = bpy.data.collections.new('ZD · Daylight Rig')
    scene.collection.children.link(collection)
    s.owned_collection = collection
    sun_data = bpy.data.lights.new('ZD · Warm Sun', 'SUN')
    sun_data.energy = 2.2
    sun_data.angle = math.radians(3)
    sun_data.color = (1, .94, .82)
    sun = bpy.data.objects.new(sun_data.name, sun_data)
    collection.objects.link(sun)
    # Camera-relative azimuth gives a readable front/side key for MMD scenes.
    front = Vector((0, -1, 0))
    if scene.camera:
        forward = scene.camera.rotation_euler.to_quaternion() @ Vector((0, 0, -1))
        front = Vector((-forward.x, -forward.y, 0))
        if front.length < .01:
            front = Vector((0, -1, 0))
        front.normalize()
    right = Vector((-front.y, front.x, 0))
    towards_light = (front * .7 - right * .55 + Vector((0, 0, 1))).normalized()
    sun.rotation_euler = (-towards_light).to_track_quat('-Z', 'Y').to_euler()
    s.owned_world = _world()
    scene.world = s.owned_world
    s.owned_compositor = _compositor(scene)
    scene.render.use_compositing = True
    s.active = True

def restore(scene):
    s = scene.zelda_daylight
    if not s.active:
        return
    old = json.loads(s.old_scene)
    scene.world = s.old_world
    if hasattr(scene, 'compositing_node_group'):
        scene.compositing_node_group = s.old_compositor
    else:
        tree = scene.node_tree
        backup = tree.nodes.get('ZD · Previous composite')
        output = next((n for n in tree.nodes if n.type == 'COMPOSITE'), None)
        if output:
            for link in list(output.inputs['Image'].links):
                tree.links.remove(link)
            if backup and backup.inputs[0].is_linked:
                tree.links.new(backup.inputs[0].links[0].from_socket, output.inputs['Image'])
        for n in list(tree.nodes):
            if n.name.startswith('ZD ·'):
                tree.nodes.remove(n)
        scene.use_nodes = old['use_nodes']
    scene.render.engine = old['engine']
    scene.render.use_compositing = old['compositing']
    for attr in ('view_transform', 'look', 'exposure', 'gamma'):
        setattr(scene.view_settings, attr, old[attr])
    for b in s.lights:
        if b.light:
            b.light.hide_render = b.hidden
            b.light.hide_viewport = b.hidden_viewport
    s.lights.clear()
    if s.old_camera and s.old_camera_data and s.old_camera.data == s.owned_camera_data:
        s.old_camera.data = s.old_camera_data
    camera_data = s.owned_camera_data
    s.old_camera = None
    s.old_camera_data = None
    s.owned_camera_data = None
    if camera_data and camera_data.users == 0:
        bpy.data.cameras.remove(camera_data)
    collection = s.owned_collection
    s.owned_collection = None
    if collection:
        for obj in list(collection.objects):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data and data.users == 0:
                bpy.data.lights.remove(data)
        bpy.data.collections.remove(collection)
    for attr, datablocks in (('owned_world', bpy.data.worlds), ('owned_compositor', bpy.data.node_groups)):
        data = getattr(s, attr)
        setattr(s, attr, None)
        if data and data.users == 0:
            datablocks.remove(data)
    s.old_world = None
    s.old_compositor = None
    s.old_scene = ''
    s.active = False
    s.active_preset = ''
    s.active_scene_revision = 0
    from . import presets
    presets.refresh_lights(scene)
    from . import hair
    hair.refresh_lights(scene)
