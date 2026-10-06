"""Independent Eevee render presets for MMD characters and scenes."""
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from . import shading, scene_setup, hair, presets, wet, face, blush

ROLES = [('AUTO', '自动识别', '按材质名猜测；可手动覆盖'),
         ('SKIN', '皮肤', '暖阴影，弱高光'), ('HAIR', '头发', '清晰分区'),
         ('CLOTH', '布料', '哑光色块'), ('EYE', '眼睛／面部线条', '保留可读性'),
         ('METAL', '金属', '较强的分区高光'),
         ('ENV', '环境', '柔和过渡和空气透视')]

class ZD_SlotBackup(bpy.types.PropertyGroup):
    index: IntProperty()
    material: PointerProperty(type=bpy.types.Material)
    applied: PointerProperty(type=bpy.types.Material)
    link: StringProperty()

class ZD_LightBackup(bpy.types.PropertyGroup):
    light: PointerProperty(type=bpy.types.Object)
    hidden: BoolProperty()
    hidden_viewport: BoolProperty()

class ZD_Settings(bpy.types.PropertyGroup):
    preset: EnumProperty(name='渲染预设', items=presets.ITEMS, default='KINGDOM', update=presets.defaults)
    wet_enabled: BoolProperty(name='皮肤水渍', default=False, update=wet.update_settings,
                              description='在已应用的皮肤材质上添加湿润反光和水珠；不修改原贴图')
    wet_amount: FloatProperty(name='水渍强度', default=.85, min=0, max=1, update=wet.update_settings)
    wet_style: EnumProperty(name='水渍样式', items=[('BOTH','湿润＋水珠','局部水膜与细小水珠'),
                           ('FILM','湿润反光','不添加水珠法线'),('DROPS','细小水珠','仅添加局部水珠')],
                           default='BOTH', update=wet.update_settings)
    wet_face: BoolProperty(name='脸部也添加', default=False, update=wet.update_settings)
    wet_scale: FloatProperty(name='水珠密度', default=28, min=5, max=400, update=wet.update_settings)
    wet_uv: StringProperty(name='水渍 UV', description='留空使用活动 UV；UV 坐标随蒙皮变形', update=wet.update_settings)
    wet_mask: PointerProperty(name='皮肤水渍遮罩', type=bpy.types.Image, update=wet.update_settings,
                              description='可选 Non-Color 灰度图；白色允许水渍，黑色保护衣物与图案')
    blush_enabled: BoolProperty(name='脸红', default=False, update=blush.update_settings,
                                description='在已应用的人物脸部叠加柔边腮红，保留贴图与透明度')
    blush_amount: FloatProperty(name='脸红强度', default=2.2, min=0, max=3, update=blush.update_settings)
    blush_color: FloatVectorProperty(name='脸红颜色', subtype='COLOR', size=4, default=(1,.08,.13,1), min=0, max=1, update=blush.update_settings)
    blush_spacing: FloatProperty(name='两颊间距', default=.25, min=.05, max=.45, update=blush.update_settings)
    blush_height: FloatProperty(name='脸红高度', default=.32, min=.05, max=.95, update=blush.update_settings)
    blush_width: FloatProperty(name='横向范围', default=.24, min=.03, max=.5, update=blush.update_settings)
    blush_radius: FloatProperty(name='纵向范围', default=.145, min=.02, max=.4, update=blush.update_settings)
    blush_front: EnumProperty(name='脸部正面', items=[('NEG_Y','−Y（常见 MMD）',''),('POS_Y','＋Y',''),('NEG_Z','−Z',''),('POS_Z','＋Z',''),('NEG_X','−X',''),('POS_X','＋X','')], default='NEG_Y', update=blush.update_settings)
    blush_material: PointerProperty(name='额外脸部材质', type=bpy.types.Material, update=blush.update_settings)
    blush_mask: PointerProperty(name='自定义脸红遮罩', type=bpy.types.Image, update=blush.update_settings,
                                description='可选灰度遮罩替代自动腮红位置；白色允许脸红，黑色保护五官')
    blush_uv: StringProperty(name='脸红 UV', update=blush.update_settings, description='仅自定义遮罩使用；留空使用活动 UV')
    stage_keep_sphere: BoolProperty(name='保留 MMD 固定反光', default=False,
                                     description='关闭可避免 Sphere 高光与新物理反光叠加；不影响原材质')
    face_softness: FloatProperty(name='柔和动画脸', default=.85, min=0, max=1, update=face.update_settings,
                                  description='冷暖逆光专用；降低鼻颊阴影与油亮反光，保留原脸部贴图；零可关闭')
    stage_dof: BoolProperty(name='舞台景深', default=True, description='复制当前相机数据后设置景深；恢复环境可还原')
    active_preset: StringProperty()
    active_scene_revision: IntProperty(default=0)
    old_camera: PointerProperty(type=bpy.types.Object)
    old_camera_data: PointerProperty(type=bpy.types.Camera)
    owned_camera_data: PointerProperty(type=bpy.types.Camera)
    show_advanced: BoolProperty(name='高级设置', default=False)
    role: EnumProperty(name='材质类型', items=ROLES, default='AUTO')
    threshold: FloatProperty(name='明暗分界', default=.68, min=.02, max=2)
    softness: FloatProperty(name='边界柔和度', default=.045, min=.005, max=.3)
    shadow_strength: FloatProperty(name='阴影强度', default=1, min=0, max=1.5)
    rim: FloatProperty(name='边缘光', default=.055, min=0, max=.3)
    mist_start: FloatProperty(name='雾起始距离', default=12, min=0, max=10000)
    mist_density: FloatProperty(name='雾浓度', default=.012, min=0, max=1)
    replace_lights: BoolProperty(name='暂时停用原灯光', default=True)
    mute_outline: BoolProperty(name='暂时停用轮廓描边', default=True)
    hair_hide_outline: BoolProperty(name='隐藏头发描边材质', default=True,
                                    description='仅自动隐藏名字明确包含头发与描边的材质；其它材质可手动指定')
    hair_outline_material: PointerProperty(name='额外描边材质', type=bpy.types.Material,
                                           description='指定需要隐藏的独立描边材质，仅作用于选中模型')
    hair_clean_lines: BoolProperty(name='修复贴图黑线', default=True)
    hair_line_strength: FloatProperty(name='黑线修复强度', default=.9, min=0, max=1)
    hair_line_threshold: FloatProperty(name='暗线阈值', default=.03, min=.0001, max=.3,
                                      description='仅修复基础贴图中低于此线性亮度的区域，不改变光照产生的阴影')
    hair_line_radius: IntProperty(name='取色距离（像素）', default=6, min=1, max=32)
    hair_line_contrast: FloatProperty(name='邻近颜色对比', default=1.6, min=1.05, max=8,
                                     description='邻近像素需比当前像素更亮；提高可保护深色发色与纹理')
    hair_line_mask: PointerProperty(name='黑线修复遮罩', type=bpy.types.Image,
                                    description='可选 Non-Color 灰度图；白色允许修复，黑色保留原色')
    hair_enabled: BoolProperty(name='启用头发亮带', default=True)
    hair_color: FloatVectorProperty(name='亮带颜色', subtype='COLOR', size=4,
                                    default=(.72,.87,1,1), min=0, max=1)
    hair_strength: FloatProperty(name='亮带强度', default=.32, min=0, max=1)
    hair_width: FloatProperty(name='亮带宽度', default=.16, min=.005, max=.7)
    hair_feather: FloatProperty(name='亮带柔边', default=.06, min=.005, max=.3)
    hair_shift: FloatProperty(name='亮带偏移', default=0, min=-1, max=1)
    hair_direction: EnumProperty(name='发流方向', items=[
        ('OBJECT_Z','模型纵向','将模型 Z 轴投影到发束表面；适合先试效果'),
        ('UV_U','UV 的 U 方向','使用沿发根到发梢展开的 U 方向'),
        ('UV_V','UV 的 V 方向','使用沿发根到发梢展开的 V 方向')], default='OBJECT_Z')
    hair_uv: StringProperty(name='头发 UV', description='留空使用模型活动 UV')
    hair_flow_map: PointerProperty(name='发流贴图', type=bpy.types.Image,
                                   description='可选 Non-Color 贴图；RG 从 0..1 解码为 UV 切线平面方向')
    hair_mask: PointerProperty(name='高光遮罩', type=bpy.types.Image,
                               description='可选灰度 Non-Color 贴图；白色显示亮带，黑色隐藏')
    hair_light: PointerProperty(name='高光太阳', type=bpy.types.Object,
                                poll=lambda self,obj: obj.type=='LIGHT' and obj.data.type=='SUN',
                                description='留空优先使用本预设的太阳，再选场景中可见的太阳')
    active: BoolProperty(default=False)
    old_world: PointerProperty(type=bpy.types.World)
    old_compositor: PointerProperty(type=bpy.types.NodeTree)
    owned_world: PointerProperty(type=bpy.types.World)
    owned_compositor: PointerProperty(type=bpy.types.NodeTree)
    owned_collection: PointerProperty(type=bpy.types.Collection)
    old_scene: StringProperty()
    lights: CollectionProperty(type=ZD_LightBackup)

class ZD_OT_apply_materials(bpy.types.Operator):
    bl_idname = 'zelda_daylight.apply_materials'
    bl_label = '应用到选中模型'
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)
    def execute(self, context):
        result = shading.apply_objects(context.selected_objects, context.scene.zelda_daylight)
        self.report({'INFO'}, f"已应用 {result['applied']} 个材质槽；跳过 {len(result['skipped'])} 个")
        for msg in result['skipped']:
            print('[MMD Render Presets]', msg)
        return {'FINISHED'}

class ZD_OT_apply_preset(bpy.types.Operator):
    bl_idname = 'zelda_daylight.apply_preset'
    bl_label = '应用预设'
    bl_description = '应用所选预设的材质、灯光与后期；保留原材质和环境备份'
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)
    def execute(self, context):
        settings = context.scene.zelda_daylight
        result = shading.apply_objects(context.selected_objects, settings)
        scene_setup.apply(context.scene, context.selected_objects)
        self.report({'INFO'}, f"已应用预设；处理 {result['applied']} 个材质槽，跳过 {len(result['skipped'])} 个")
        for message in result['skipped']:
            print('[MMD Render Presets]', message)
        return {'FINISHED'}

class ZD_OT_clean_hair(bpy.types.Operator):
    bl_idname = 'zelda_daylight.clean_hair'
    bl_label = '处理头发黑边'
    bl_description = '使用自动材质识别处理选中模型的头发黑边；保留原材质备份'
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)
    def execute(self, context):
        settings = context.scene.zelda_daylight
        settings.hair_hide_outline = True
        settings.hair_clean_lines = True
        settings.mute_outline = True
        previous_role = settings.role
        settings.role = 'AUTO'
        try:
            result = shading.apply_objects(context.selected_objects, settings)
        finally:
            settings.role = previous_role
        self.report({'INFO'}, f"已处理 {result['applied']} 个材质槽；可恢复原材质")
        for message in result['skipped']:
            print('[MMD Render Presets]', message)
        return {'FINISHED'}

class ZD_OT_restore_materials(bpy.types.Operator):
    bl_idname = 'zelda_daylight.restore_materials'
    bl_label = '恢复选中模型材质'
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        n = shading.restore_objects(context.selected_objects)
        self.report({'INFO'}, f'恢复 {n} 个材质槽')
        return {'FINISHED'}

class ZD_OT_scene(bpy.types.Operator):
    bl_idname = 'zelda_daylight.setup_scene'
    bl_label = '应用白昼灯光与天空'
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        scene_setup.apply(context.scene)
        self.report({'INFO'}, '已应用白昼环境；可恢复原环境')
        return {'FINISHED'}

class ZD_OT_restore_scene(bpy.types.Operator):
    bl_idname = 'zelda_daylight.restore_scene'
    bl_label = '恢复原环境'
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        scene_setup.restore(context.scene)
        return {'FINISHED'}

class ZD_PT_panel(bpy.types.Panel):
    bl_label = 'MMD 渲染预设'
    bl_idname = 'ZD_PT_daylight'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MMD Render'
    def draw(self, context):
        layout = self.layout
        s = context.scene.zelda_daylight
        layout.prop(s, 'preset', text='')
        actions = layout.column(align=True)
        actions.operator('zelda_daylight.apply_preset', icon='RENDER_STILL')
        actions.operator('zelda_daylight.clean_hair', icon='BRUSH_DATA')
        layout.prop(s, 'wet_enabled')
        if s.wet_enabled:
            layout.prop(s, 'wet_amount', slider=True)
        layout.prop(s, 'blush_enabled')
        if s.blush_enabled:
            layout.prop(s, 'blush_amount', slider=True)
        layout.label(text='选中模型后点击；修改可撤销')
        row = layout.row(align=True)
        row.operator('zelda_daylight.restore_materials', text='恢复材质', icon='LOOP_BACK')
        if s.active:
            row.operator('zelda_daylight.restore_scene', text='恢复环境', icon='LOOP_BACK')
        layout.separator()
        layout.prop(s, 'show_advanced', icon='TRIA_DOWN' if s.show_advanced else 'TRIA_RIGHT',
                    emboss=False)
        if not s.show_advanced:
            return
        layout.operator('zelda_daylight.apply_materials', text='仅更新材质', icon='MATERIAL')
        layout.operator('zelda_daylight.setup_scene', text='仅应用灯光与后期', icon='WORLD')
        if s.preset == 'STAGE':
            layout.prop(s, 'face_softness', slider=True)
            layout.prop(s, 'stage_dof')
            layout.prop(s, 'stage_keep_sphere')
        col = layout.column(align=True)
        col.prop(s, 'role')
        if s.preset == 'KINGDOM':
            for key in ('threshold', 'softness', 'shadow_strength', 'rim'):
                col.prop(s, key)
        col.prop(s, 'mute_outline')
        box = layout.box()
        box.label(text='头发亮带')
        box.prop(s, 'hair_enabled')
        controls = box.column(align=True)
        controls.enabled = s.hair_enabled
        for key in ('hair_color','hair_strength','hair_width','hair_feather','hair_shift',
                    'hair_direction','hair_uv','hair_flow_map','hair_mask','hair_light'):
            controls.prop(s, key)
        repair = layout.box()
        repair.label(text='头发黑边')
        for key in ('hair_hide_outline','hair_outline_material','hair_clean_lines'):
            repair.prop(s, key)
        controls = repair.column(align=True)
        controls.enabled = s.hair_clean_lines
        for key in ('hair_line_strength','hair_line_threshold','hair_line_radius','hair_line_contrast','hair_line_mask'):
            controls.prop(s, key)
        cheeks = layout.box()
        cheeks.label(text='脸红')
        for key in ('blush_color','blush_height','blush_spacing','blush_width','blush_radius','blush_front','blush_material','blush_mask','blush_uv'):
            cheeks.prop(s, key)
        water = layout.box()
        water.label(text='皮肤水渍')
        for key in ('wet_style','wet_face','wet_scale','wet_uv','wet_mask'):
            water.prop(s, key)
        layout.prop(s, 'mist_start')
        layout.prop(s, 'mist_density')
        layout.prop(s, 'replace_lights')
        layout.operator('zelda_daylight.apply_materials', text='更新材质参数', icon='FILE_REFRESH')
        layout.label(text='关闭黑边选项后，点更新材质参数')

CLASSES = (ZD_SlotBackup, ZD_LightBackup, ZD_Settings, ZD_OT_apply_materials,
           ZD_OT_apply_preset, ZD_OT_clean_hair, ZD_OT_restore_materials, ZD_OT_scene, ZD_OT_restore_scene, ZD_PT_panel)

def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.zelda_slot_backups = CollectionProperty(type=ZD_SlotBackup)
    bpy.types.Scene.zelda_daylight = PointerProperty(type=ZD_Settings)

def unregister():
    del bpy.types.Scene.zelda_daylight
    del bpy.types.Object.zelda_slot_backups
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
