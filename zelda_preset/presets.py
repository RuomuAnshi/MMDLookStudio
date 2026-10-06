"""Author-maintained render pipelines; no user preset storage or editing API."""
from importlib import import_module

# Each author-supplied backend owns its material graph, update hook and scene rig.
BACKENDS = {'STAGE': '.stage'}

ITEMS = [('KINGDOM', '王国白昼', '暖阳、分区明暗与方向性头发亮带', 0),
         ('STAGE', '冷暖逆光', '柔和肤色、真实反光、金蓝逆光与景深', 1)]

def selected(settings):
    return getattr(settings, 'preset', 'KINGDOM')

def defaults(settings, context=None):
    values = dict(threshold=.68, softness=.045, shadow_strength=1, rim=.055,
                  mist_start=12, mist_density=.012, hair_strength=.32,
                  hair_width=.16, hair_feather=.06, hair_shift=0)
    if selected(settings) == 'STAGE':
        values.update(mist_density=0, hair_strength=.18, hair_width=.12, hair_feather=.08)
    for key, value in values.items():
        setattr(settings, key, value)

def backend(settings):
    module = BACKENDS.get(selected(settings))
    return import_module(module, __package__) if module else None

def refresh_lights(scene):
    for module in BACKENDS.values():
        import_module(module, __package__).refresh_lights(scene)
