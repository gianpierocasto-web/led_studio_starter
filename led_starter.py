"""LED Studio — Geometry Nodes starter, Blender 5.3+. Run from Text Editor.
Creates a NEW scene for each preset. Existing scenes and objects are retained.
CLI: blender -b --python led_starter.py -- --output /absolute/path/LED_Studio.blend

Coil and PCB geometry come from .blend files in ./bobine and ./pcb.
The embedded text "LED Studio Libreria" registers the modifier panel on file load.
"""
import bpy
import math
import os
import shutil
import sys
import tempfile
from mathutils import Vector

PREFIX = 'LED Studio'


class Graph:
    def __init__(self, name):
        self.g = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        self.g.is_modifier = True
        self.i = self.node('NodeGroupInput', 'Parametri', -1400, 0)
        self.o = self.node('NodeGroupOutput', 'Risultato', 2400, 0)
        self.sock('Geometry', 'NodeSocketGeometry', output=True)
        self.count = 0

    def node(self, kind, label='', x=None, y=None):
        n = self.g.nodes.new(kind)
        n.label = label
        n.width = 190
        if x is None:
            k = len(self.g.nodes) - 3
            x, y = (k % 7) * 245 - 700, -(k // 7) * 310 - 280
        n.location = (x, y)
        return n

    def sock(self, name, kind='NodeSocketFloat', default=None, lo=None, hi=None, output=False, description=''):
        s = self.g.interface.new_socket(name=name, in_out='OUTPUT' if output else 'INPUT', socket_type=kind)
        s.description = description
        if default is not None:
            s.default_value = default
        if lo is not None:
            s.min_value = lo
        if hi is not None:
            s.max_value = hi
        return s

    def link(self, value, socket):
        if isinstance(value, bpy.types.NodeSocket):
            self.g.links.new(value, socket)
        else:
            socket.default_value = value

    def math(self, operation, a, b=0, label=''):
        n = self.node('ShaderNodeMath', label or operation)
        n.operation = operation
        self.link(a, n.inputs[0])
        self.link(b, n.inputs[1])
        return n.outputs[0]

    def compare(self, a, b, eps=0.1, label=''):
        n = self.node('ShaderNodeMath', label or 'COMPARE')
        n.operation = 'COMPARE'
        self.link(a, n.inputs[0])
        self.link(b, n.inputs[1])
        n.inputs[2].default_value = eps
        return n.outputs[0]

    def vec(self, x=0, y=0, z=0):
        n = self.node('ShaderNodeCombineXYZ')
        for v, s in zip((x, y, z), n.inputs):
            self.link(v, s)
        return n.outputs[0]

    def transform(self, geo, translation=(0, 0, 0)):
        n = self.node('GeometryNodeTransform')
        n.inputs['Mode'].default_value = 'Components'
        self.link(geo, n.inputs['Geometry'])
        self.link(translation, n.inputs['Translation'])
        return n.outputs[0]

    def material(self, geo, mat):
        n = self.node('GeometryNodeSetMaterial')
        self.link(geo, n.inputs['Geometry'])
        self.link(mat, n.inputs['Material'])
        return n.outputs[0]

    def join(self, *geos):
        n = self.node('GeometryNodeJoinGeometry')
        for geo in geos:
            self.link(geo, n.inputs[0])
        return n.outputs[0]

    def call(self, tree, label):
        n = self.node('GeometryNodeGroup', label)
        n.node_tree = tree
        return n

    def repeat(self, label='Livelli'):
        enter = self.node('GeometryNodeRepeatInput', label)
        leave = self.node('GeometryNodeRepeatOutput', label + ' uniti')
        enter.pair_with_output(leave)
        return enter, leave

    def finish(self, geo):
        self.link(geo, self.o.inputs['Geometry'])
        bad = []
        for link in self.g.links:
            if not link.is_valid:
                bad.append('%s.%s -> %s.%s' % (
                    link.from_node.name, link.from_socket.name,
                    link.to_node.name, link.to_socket.name))
        if bad:
            raise RuntimeError(self.g.name + '\n' + '\n'.join(bad))
        self.g.asset_mark()
        self.g.asset_data.description = 'LED Studio: generatore parametrico in metri, modificabile senza script.'
        return self.g


def make_material(name, color, metallic=0, roughness=.4):
    m = bpy.data.materials.new(PREFIX + ' | ' + name)
    m.diffuse_color = (*color, 1)
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Specular IOR Level'].default_value = .22
    return m


def build_path():
    """One planar spiral. An integer turn count ends it on +X."""
    q = Graph('LED | 01 Percorso spirale e uscita')
    for name, value, lo, hi in [('Raggio mozzo', .026, .012, .08), ('Raggio avvolgimento', .078, .025, .18),
                                ('Passo radiale', .002, .0012, .008), ('Giri uscita', .83, .25, 1.5),
                                ('Apertura uscita', .035, .005, .08)]:
        q.sock(name, default=value, lo=lo, hi=hi)
    q.sock('Con uscita', 'NodeSocketBool', default=True,
           description='Aggiunge il tratto libero in fondo alla spirale.')
    p = q.i.outputs
    giri = q.node('GeometryNodeSwitch', 'Con uscita')
    giri.input_type = 'FLOAT'
    q.link(p['Con uscita'], giri.inputs['Switch'])
    giri.inputs['False'].default_value = 0.0
    q.link(p['Giri uscita'], giri.inputs['True'])
    # Keep this radius clamp identical to the connector in group 00.
    radius = q.math('MAXIMUM', p['Raggio avvolgimento'], q.math('ADD', p['Raggio mozzo'], .003))
    turns = q.math('FLOOR', q.math('DIVIDE', q.math('SUBTRACT', radius, p['Raggio mozzo']), p['Passo radiale']))
    idx = q.node('GeometryNodeInputIndex').outputs['Index']
    t = q.math('MULTIPLY', q.math('DIVIDE', idx, 8191), q.math('ADD', turns, giri.outputs['Output']))
    tail = q.math('MAXIMUM', q.math('SUBTRACT', t, turns), 0)
    expansion = q.math('MULTIPLY', p['Apertura uscita'], q.math('POWER', q.math('DIVIDE', tail, giri.outputs['Output']), 2))
    r = q.math('ADD', q.math('ADD', p['Raggio mozzo'], q.math('MULTIPLY', t, p['Passo radiale'])), expansion)
    angle = q.math('MULTIPLY', t, 2 * math.pi)
    x = q.math('MULTIPLY', r, q.math('COSINE', angle))
    y = q.math('MULTIPLY', r, q.math('SINE', angle))
    line = q.node('GeometryNodeMeshLine')
    line.mode = 'OFFSET'
    line.inputs['Count'].default_value = 8192
    pos = q.node('GeometryNodeSetPosition', 'Spirale planare con uscita continua')
    q.link(line.outputs['Mesh'], pos.inputs['Geometry'])
    q.link(q.vec(x, y, 0), pos.inputs['Position'])
    cv = q.node('GeometryNodeMeshToCurve')
    cv.mode = 'EDGES'
    q.link(pos.outputs['Geometry'], cv.inputs['Mesh'])
    return q.finish(cv.outputs['Curve'])


def build_strip():
    """Repeat the PCB object along a curve. Instances stay instances."""
    q = Graph('LED | 02 PCB e componenti su curva')
    q.sock('Curva', 'NodeSocketGeometry')
    q.sock('Modulo PCB', 'NodeSocketObject')
    q.sock('Passo', default=.016, lo=.0005, hi=.1,
           description='Lunghezza X del modulo, in metri.')
    p = q.i.outputs
    info = q.node('GeometryNodeObjectInfo', 'Modulo PCB')
    info.transform_space = 'ORIGINAL'
    info.inputs['As Instance'].default_value = False
    q.link(p['Modulo PCB'], info.inputs['Object'])
    safe = q.math('MAXIMUM', p['Passo'], .001)
    points = q.node('GeometryNodeCurveToPoints')
    points.mode = 'LENGTH'
    if not points.inputs['Length'].enabled:
        raise RuntimeError('Curve to Points: socket Length non disponibile')
    q.link(p['Curva'], points.inputs['Curve'])
    q.link(safe, points.inputs['Length'])
    align = q.node('FunctionNodeAlignRotationToVector', 'X tangente / Z verticale')
    align.axis = 'X'
    align.pivot_axis = 'Z'
    align.inputs['Factor'].default_value = 1.0
    q.link(points.outputs['Tangent'], align.inputs['Vector'])
    inst = q.node('GeometryNodeInstanceOnPoints', 'Modulo ripetuto')
    q.link(points.outputs['Points'], inst.inputs['Points'])
    q.link(info.outputs['Geometry'], inst.inputs['Instance'])
    q.link(align.outputs['Rotation'], inst.inputs['Rotation'])
    q.link(q.math('GREATER_THAN', p['Passo'], .0001), inst.inputs['Selection'])
    return q.finish(inst.outputs['Instances'])


def build_reel():
    """Move up and down apart. A cylinder fills the opening with up's first material."""
    q = Graph('LED | 03 Bobina parametrica')
    q.sock('Flangia up', 'NodeSocketObject')
    q.sock('Flangia down', 'NodeSocketObject')
    q.sock('Raggio mozzo', default=.026, lo=.012, hi=.08)
    q.sock('Altezza bobina', default=.014, lo=.002, hi=.2,
           description='Luce interna fra le flange, in metri.')
    p = q.i.outputs

    def flange(socket_name, sign):
        info = q.node('GeometryNodeObjectInfo', socket_name)
        info.transform_space = 'ORIGINAL'
        info.inputs['As Instance'].default_value = False
        q.link(p[socket_name], info.inputs['Object'])
        box = q.node('GeometryNodeBoundBox')
        q.link(info.outputs['Geometry'], box.inputs['Geometry'])
        sep = q.node('ShaderNodeSeparateXYZ')
        q.link(box.outputs['Min'] if sign > 0 else box.outputs['Max'], sep.inputs['Vector'])
        half = q.math('MULTIPLY', p['Altezza bobina'], .5 * sign)
        moved = q.transform(info.outputs['Geometry'], q.vec(0, 0, q.math('SUBTRACT', half, sep.outputs['Z'])))
        return moved, info

    up, up_info = flange('Flangia up', 1)
    down, _down_info = flange('Flangia down', -1)
    cyl = q.node('GeometryNodeMeshCylinder', 'Mozzo')
    cyl.inputs['Vertices'].default_value = 64
    cyl.inputs['Side Segments'].default_value = 1
    cyl.inputs['Fill Segments'].default_value = 1
    cyl.fill_type = 'NONE'
    q.link(p['Raggio mozzo'], cyl.inputs['Radius'])
    q.link(p['Altezza bobina'], cyl.inputs['Depth'])
    mats = q.node('GeometryNodeGeometryMaterials')
    mats.inputs['Component Type'].default_value = 'Mesh'
    q.link(up_info.outputs['Geometry'], mats.inputs['Geometry'])
    item = q.node('GeometryNodeListGetItem')
    item.socket_type = 'MATERIAL'
    q.link(mats.outputs['Materials'], item.inputs['List'])
    item.inputs['Index'].default_value = 0
    hub = q.material(cyl.outputs['Mesh'], item.outputs['Value'])
    return q.finish(q.join(up, down, hub))


def build_master(path, strip, reel):
    """Stack alternating spiral layers in the reel opening and instance the PCB."""
    q = Graph('LED | 00 Prodotto completo')
    q.sock('Flangia up', 'NodeSocketObject')
    q.sock('Flangia down', 'NodeSocketObject')
    q.sock('Modulo PCB', 'NodeSocketObject')
    for name, value, lo, hi in [('Raggio mozzo', .026, .012, .08), ('Raggio avvolgimento', .078, .025, .18),
                                ('Passo radiale', .002, .0012, .008), ('Giri uscita', .83, .25, 1.5),
                                ('Apertura uscita', .035, .005, .08)]:
        q.sock(name, default=value, lo=lo, hi=hi)
    q.sock('Altezza bobina', default=.014, lo=.002, hi=.2,
           description='Luce interna fra le flange, in metri. I livelli sono la parte intera di questa misura divisa per la larghezza Z del PCB.')
    p = q.i.outputs
    info = q.node('GeometryNodeObjectInfo', 'Quote modulo')
    info.transform_space = 'ORIGINAL'
    info.inputs['As Instance'].default_value = False
    q.link(p['Modulo PCB'], info.inputs['Object'])
    box = q.node('GeometryNodeBoundBox')
    q.link(info.outputs['Geometry'], box.inputs['Geometry'])
    lo = q.node('ShaderNodeSeparateXYZ')
    hi = q.node('ShaderNodeSeparateXYZ')
    q.link(box.outputs['Min'], lo.inputs['Vector'])
    q.link(box.outputs['Max'], hi.inputs['Vector'])
    passo = q.math('SUBTRACT', hi.outputs['X'], lo.outputs['X'], 'Passo')
    larghezza = q.math('SUBTRACT', hi.outputs['Z'], lo.outputs['Z'], 'Larghezza')
    livelli = q.math('MAXIMUM', q.math('FLOOR', q.math('DIVIDE', p['Altezza bobina'], larghezza)), 1, 'Livelli')
    margin = q.math('MULTIPLY', q.math('SUBTRACT', p['Altezza bobina'], q.math('MULTIPLY', livelli, larghezza)), .5)
    # Same clamp as group 01, so the riser meets the end of an integer spiral.
    radius = q.math('MAXIMUM', p['Raggio avvolgimento'], q.math('ADD', p['Raggio mozzo'], .003))
    turns = q.math('FLOOR', q.math('DIVIDE', q.math('SUBTRACT', radius, p['Raggio mozzo']), p['Passo radiale']))
    r_end = q.math('ADD', p['Raggio mozzo'], q.math('MULTIPLY', turns, p['Passo radiale']), 'Raggio fine spira')
    enter, leave = q.repeat('Livelli')
    as_int = q.node('FunctionNodeFloatToInt')
    as_int.rounding_mode = 'FLOOR'
    q.link(livelli, as_int.inputs['Float'])
    q.link(as_int.outputs['Integer'], enter.inputs['Iterations'])
    iteration = enter.outputs['Iteration']
    is_last = q.compare(iteration, q.math('SUBTRACT', livelli, 1), label='Ultimo')
    modulo = q.math('FLOORED_MODULO', iteration, 2)
    is_even = q.compare(modulo, 0, label='Pari')
    is_odd = q.compare(modulo, 1, label='Dispari')
    spiral = q.call(path, '01 Percorso')
    for socket in spiral.inputs:
        if socket.name in p and socket.name != 'Con uscita':
            q.link(p[socket.name], socket)
    q.link(q.math('MINIMUM', is_last, is_even, 'Con uscita'), spiral.inputs['Con uscita'])
    rev = q.node('GeometryNodeReverseCurve')
    q.link(spiral.outputs[0], rev.inputs['Curve'])
    q.link(is_odd, rev.inputs['Selection'])
    radius_sw = q.node('GeometryNodeSwitch', 'Raggio raccordo')
    radius_sw.input_type = 'FLOAT'
    q.link(is_odd, radius_sw.inputs['Switch'])
    q.link(r_end, radius_sw.inputs['False'])
    q.link(p['Raggio mozzo'], radius_sw.inputs['True'])
    riser = q.node('GeometryNodeCurvePrimitiveLine', 'Raccordo')
    riser.mode = 'POINTS'
    q.link(q.vec(radius_sw.outputs['Output'], 0, 0), riser.inputs['Start'])
    q.link(q.vec(radius_sw.outputs['Output'], 0, larghezza), riser.inputs['End'])
    with_riser = q.join(rev.outputs['Curve'], riser.outputs['Curve'])
    layer_sw = q.node('GeometryNodeSwitch', 'Senza raccordo in coda')
    layer_sw.input_type = 'GEOMETRY'
    q.link(is_last, layer_sw.inputs['Switch'])
    q.link(with_riser, layer_sw.inputs['False'])
    q.link(rev.outputs['Curve'], layer_sw.inputs['True'])
    z_layer = q.math('ADD', q.math('ADD', q.math('MULTIPLY', p['Altezza bobina'], -.5), margin),
                     q.math('ADD', q.math('MULTIPLY', larghezza, .5), q.math('MULTIPLY', iteration, larghezza)),
                     'Quota livello')
    placed = q.transform(layer_sw.outputs['Output'], q.vec(0, 0, z_layer))
    q.link(q.join(enter.outputs['Geometry'], placed), leave.inputs['Geometry'])
    strip_node = q.call(strip, '02 Striscia')
    q.link(leave.outputs['Geometry'], strip_node.inputs['Curva'])
    q.link(p['Modulo PCB'], strip_node.inputs['Modulo PCB'])
    q.link(passo, strip_node.inputs['Passo'])
    reel_node = q.call(reel, '03 Bobina')
    for name in ('Flangia up', 'Flangia down', 'Raggio mozzo', 'Altezza bobina'):
        q.link(p[name], reel_node.inputs[name])
    return q.finish(q.join(strip_node.outputs[0], reel_node.outputs[0]))


def set_input(modifier, name, value):
    for s in modifier.node_group.interface.items_tree:
        if s.item_type == 'SOCKET' and s.in_out == 'INPUT' and s.name == name:
            modifier.properties.inputs[s.identifier]['value'] = value
            modifier.id_data.update_tag()
            return
    raise KeyError(name)


PRESETS = [
    ('01_Bianco_8mm', {'Altezza bobina': .0124, 'Passo radiale': .0018}),
    ('02_Caldo_10mm', {'Altezza bobina': .0144}),
    ('03_RGB_12mm', {'Altezza bobina': .0164, 'Raggio avvolgimento': .084, 'Passo radiale': .0023}),
]


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def setup_scene(name, group, values, floor_mat):
    scene = bpy.data.scenes.new(PREFIX + ' | ' + name)
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    root = bpy.data.collections.new('Prodotto | ' + name)
    scene.collection.children.link(root)
    mesh = bpy.data.meshes.new('Supporto generatore')
    obj = bpy.data.objects.new('LED_' + name, mesh)
    root.objects.link(obj)
    mod = obj.modifiers.new('Configurazione prodotto', 'NODES')
    mod.node_group = group
    for k, v in values.items():
        set_input(mod, k, v)
    obj.location.z = .019
    stage = bpy.data.collections.new('Studio | ' + name)
    scene.collection.children.link(stage)
    floor_mesh = bpy.data.meshes.new('Fondo')
    floor_mesh.from_pydata([(-2, -2, 0), (2, -2, 0), (2, 2, 0), (-2, 2, 0)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new('Fondo bianco', floor_mesh)
    stage.objects.link(floor)
    floor.data.materials.append(floor_mat)
    camera = bpy.data.objects.new('Camera catalogo', bpy.data.cameras.new('Camera catalogo'))
    stage.objects.link(camera)
    camera.location = (.27, -.40, .29)
    look_at(camera, (0, 0, .015))
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = .32
    camera.data.lens = 50
    scene.camera = camera
    for title, location, power, size in [('Key', (.12, -.18, .38), 3, .27), ('Fill', (-.25, -.05, .22), 2, .22), ('Rim', (.05, .24, .28), 3, .20)]:
        light = bpy.data.objects.new(title, bpy.data.lights.new(title, 'AREA'))
        stage.objects.link(light)
        light.location = location
        light.data.energy = power
        light.data.shape = 'DISK'
        light.data.size = size
        look_at(light, (0, 0, 0))
    world = bpy.data.worlds.new('Studio bianco')
    bg = world.node_tree.nodes['Background']
    bg.inputs[0].default_value = (.8, .8, .8, 1)
    bg.inputs[1].default_value = .20
    scene.world = world
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = '//renders/' + name + '.png'
    scene.view_settings.view_transform = 'AgX'
    scene['NOTE'] = 'Scegli bobina e PCB dalle cartelle. Quote in metri. Nessuna lunghezza commerciale garantita.'
    scene.view_layers[0].objects.active = obj
    obj.select_set(True, view_layer=scene.view_layers[0])
    return scene, obj


PANEL_SOURCE = r'''import bpy
import os

LIBRARY = 'LED Studio | Libreria'
_bobina_items = [('NONE', 'Nessuna', 'Nessun file scelto')]
_pcb_items = [('NONE', 'Nessuna', 'Nessun file scelto')]


def library_dir(kind):
    return os.path.join(bpy.path.abspath('//'), kind)


def norm(path):
    return os.path.normcase(os.path.normpath(bpy.path.abspath(path)))


def blend_items(kind, cache_name):
    items = [('NONE', 'Nessuna', 'Nessun file scelto')]
    folder = library_dir(kind)
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith('.blend'):
                items.append((name, name[:-6], name))
    if cache_name == 'bobina':
        global _bobina_items
        _bobina_items = items
        return _bobina_items
    global _pcb_items
    _pcb_items = items
    return _pcb_items


def bobina_items(self, context):
    return blend_items('bobine', 'bobina')


def pcb_items(self, context):
    return blend_items('pcb', 'pcb')


def modifier_of(obj):
    mod = obj.modifiers.get('Configurazione prodotto')
    if mod is None or mod.type != 'NODES' or mod.node_group is None:
        return None
    return mod


def set_socket(obj, name, value):
    mod = modifier_of(obj)
    if mod is None:
        raise RuntimeError('Modificatore Configurazione prodotto mancante')
    for item in mod.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == name:
            mod.properties.inputs[item.identifier]['value'] = value
            obj.update_tag()
            return
    raise KeyError(name)


def same_object(wanted, linked_name):
    if linked_name == wanted:
        return True
    prefix = wanted + '.'
    return linked_name.startswith(prefix) and linked_name[len(prefix):].isdigit()


def ensure_collection():
    col = bpy.data.collections.get(LIBRARY)
    if col is None:
        col = bpy.data.collections.new(LIBRARY)
    for scene in bpy.data.scenes:
        if col.name not in scene.collection.children:
            scene.collection.children.link(col)
    col.hide_render = True
    col.hide_viewport = False
    return col


def load_objects(rel_path, names):
    target = norm(rel_path)
    found = {}
    for obj in bpy.data.objects:
        lib = obj.library
        if lib is None or norm(lib.filepath) != target:
            continue
        for name in names:
            if name not in found and same_object(name, obj.name):
                found[name] = obj
    needed = [name for name in names if name not in found]
    if needed:
        with bpy.data.libraries.load(rel_path, link=True) as (src, dst):
            dst.objects = [name for name in needed if name in list(src.objects)]
        for obj in dst.objects:
            if obj is None:
                continue
            for name in needed:
                if same_object(name, obj.name):
                    found[name] = obj
    col = ensure_collection()
    for obj in found.values():
        if obj.name not in col.objects:
            col.objects.link(obj)
        obj.hide_render = True
    return found


def assign_library(obj, kind, filename, mapping):
    settings = obj.led_studio
    if filename == 'NONE':
        for socket in mapping:
            set_socket(obj, socket, None)
        settings.status = ''
        return
    rel = '//' + kind + '/' + filename
    if not os.path.isfile(bpy.path.abspath(rel)):
        settings.status = 'File mancante: ' + filename
        return
    try:
        found = load_objects(rel, list(mapping.values()))
    except Exception as exc:
        settings.status = str(exc)
        return
    missing = [name for name in mapping.values() if name not in found]
    if missing:
        settings.status = 'Nel file manca: ' + ', '.join(missing)
        return
    for socket, obj_name in mapping.items():
        set_socket(obj, socket, found[obj_name])
    settings.status = ''


def update_bobina(self, context):
    assign_library(self.id_data, 'bobine', self.bobina, {'Flangia up': 'up', 'Flangia down': 'down'})


def update_pcb(self, context):
    stem = self.pcb[:-6] if self.pcb.lower().endswith('.blend') else self.pcb
    assign_library(self.id_data, 'pcb', self.pcb, {'Modulo PCB': stem})


class LEDStudioSettings(bpy.types.PropertyGroup):
    bobina: bpy.props.EnumProperty(name='Bobina', items=bobina_items, update=update_bobina)
    pcb: bpy.props.EnumProperty(name='PCB', items=pcb_items, update=update_pcb)
    status: bpy.props.StringProperty(name='Stato', default='')


class LED_PT_library(bpy.types.Panel):
    bl_label = 'Libreria bobine e PCB'
    bl_idname = 'LED_PT_library'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'modifier'

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and modifier_of(obj) is not None

    def draw(self, context):
        layout = self.layout
        settings = context.object.led_studio
        layout.prop(settings, 'bobina')
        layout.prop(settings, 'pcb')
        if settings.status:
            layout.label(text=settings.status, icon='ERROR')
        root = bpy.path.abspath('//')
        if not os.path.isdir(os.path.join(root, 'bobine')) or not os.path.isdir(os.path.join(root, 'pcb')):
            layout.label(text='Crea le cartelle bobine e pcb accanto al file.')


def register():
    if not hasattr(bpy.types, 'LEDStudioSettings'):
        bpy.utils.register_class(LEDStudioSettings)
    if not hasattr(bpy.types, 'LED_PT_library'):
        bpy.utils.register_class(LED_PT_library)
    if not hasattr(bpy.types.Object, 'led_studio'):
        bpy.types.Object.led_studio = bpy.props.PointerProperty(type=LEDStudioSettings)


def unregister():
    if hasattr(bpy.types.Object, 'led_studio'):
        del bpy.types.Object.led_studio
    if hasattr(bpy.types, 'LED_PT_library'):
        bpy.utils.unregister_class(LED_PT_library)
    if hasattr(bpy.types, 'LEDStudioSettings'):
        bpy.utils.unregister_class(LEDStudioSettings)


register()
'''


README = '''LED STUDIO — PARTENZA RAPIDA

Blender 5.3. Tre scene, dal menu Scene in alto: 8 mm, 10 mm, RGB 12 mm.
Sono preset di inquadratura e di quote della spirale, non prodotti certificati.

1. Le cartelle bobine e pcb stanno accanto a questo file.
2. In bobine metti un .blend per modello. Dentro, due mesh chiamate up e down,
   origine al centro della bobina, asse Z, transform applicati, materiali già assegnati.
   up sta dal lato Z positivo, down dal lato negativo.
3. In pcb metti un .blend per codice. L'oggetto mesh ha il nome del file
   senza estensione, per esempio FN01234. Origine al centro del passo.
   X è il passo lungo il nastro, Z è la larghezza, il lato LED guarda verso -Y.
4. Seleziona LED_... Se il pannello non compare, abilita Auto Run Python Scripts
   oppure esegui una volta il testo LED Studio Libreria.
   Nel modificatore Configurazione prodotto scegli Bobina e poi PCB.
5. Regola Altezza bobina, i raggi, il passo radiale e l'uscita.
6. F12 per il render; tastierino 0 per la camera.

Le flange non si scalano: si allontanano fino alla luce richiesta.
Il cilindro fra le due prende il primo materiale di up.
La larghezza della striscia è la misura Z del pezzo PCB, non uno slider.
I livelli sono la parte intera di altezza / larghezza, minimo uno. Il resto
resta come margine, centrato fra le flange.
Il nastro è continuo: il livello dispari torna indietro e un raccordo verticale
sale di una larghezza. L'uscita è disegnata solo se il nastro finisce all'esterno,
cioè con un numero dispari di livelli.

QUOTE in metri: 0.008 = 8 mm.
Mantieni Raggio mozzo < Raggio avvolgimento, e il raggio di avvolgimento
dentro la flangia vera. Un avvolgimento troppo fitto può intersecare i componenti.
Non interpreta una lunghezza commerciale esatta: è un avvolgimento illustrativo.

Gruppi: 00 Prodotto completo; 01 Percorso spirale e uscita;
02 PCB e componenti su curva; 03 Bobina parametrica.

IMPORTAZIONE: File > Append > LED_Studio.blend > Collection > Prodotto | ...
Il pannello legge le cartelle accanto al file in cui lavori.

SCRIPT: eseguire led_starter.py dal Text Editor crea nuove scene, senza
cancellare quelle esistenti. Ripetere lo script crea altre copie, non aggiorna.
Lo script non salva automaticamente il progetto aperto.
'''


def replace_text(name, body, module=False):
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    text.from_string(body)
    if module:
        text.use_module = True
    return text


def load_panel():
    ns = {'__name__': 'led_studio_libreria'}
    exec(PANEL_SOURCE, ns)
    return ns


def make_box(name, size, center):
    hx, hy, hz = (axis / 2 for axis in size)
    cx, cy, cz = center
    corners = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
               (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    verts = [(cx + x, cy + y, cz + z) for x, y, z in corners]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return bpy.data.objects.new(name, mesh)


def mesh_report(obj):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    zs = [v.co.z for v in mesh.vertices]
    mats = [slot.name for slot in mesh.materials if slot]
    ev.to_mesh_clear()
    return zs, mats


def instance_points(obj):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    pts = []
    seen = []
    for inst in deps.object_instances:
        if not inst.is_instance:
            continue
        parent = inst.parent
        original = getattr(parent, 'original', None) if parent else None
        if original == obj or parent == obj:
            pts.append(obj.matrix_world.inverted() @ inst.matrix_world.translation)
        elif len(seen) < 6:
            seen.append(getattr(original, 'name', None))
    return pts, seen


def exercise_library(scene, obj, values):
    """Link a temporary coil and PCB the way the panel does, then remove them."""
    panel = load_panel()
    temp = tempfile.mkdtemp(prefix='led_studio_')
    host = os.path.join(temp, 'LED_Studio.blend')
    bpy.ops.wm.save_as_mainfile(filepath=host)
    os.makedirs(os.path.join(temp, 'bobine'))
    os.makedirs(os.path.join(temp, 'pcb'))
    mat = make_material('test mozzo', (.2, .45, .8), 0, .4)
    up = make_box('up', (.2, .2, .002), (0, 0, .005))
    down = make_box('down', (.2, .2, .002), (0, 0, -.005))
    pcb = make_box('FN01234', (.004, .001, .008), (0, 0, 0))
    up.data.materials.append(mat)
    bobina_path = os.path.join(temp, 'bobine', 'bobina bianca.blend')
    pcb_path = os.path.join(temp, 'pcb', 'FN01234.blend')
    bpy.data.libraries.write(bobina_path, {up, up.data, down, down.data, mat}, fake_user=True)
    bpy.data.libraries.write(pcb_path, {pcb, pcb.data}, fake_user=True)
    for piece in (up, down, pcb):
        data = piece.data
        bpy.data.objects.remove(piece, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    try:
        bpy.context.window.scene = scene
        if 'bobina bianca.blend' not in [item[0] for item in panel['bobina_items'](None, None)]:
            raise RuntimeError('Il menu Bobina non elenca il file di prova')
        obj.led_studio.bobina = 'bobina bianca.blend'
        obj.led_studio.pcb = 'FN01234.blend'
        if obj.led_studio.status:
            raise RuntimeError(obj.led_studio.status)
        mod = obj.modifiers['Configurazione prodotto']
        set_input(mod, 'Altezza bobina', .020)
        zs, mats = mesh_report(obj)
        pts, seen = instance_points(obj)
        print('LED_CHECK library verts', len(zs), 'z', (min(zs), max(zs)), 'instances', len(pts), 'mats', mats, 'other', seen)
        if not zs or min(zs) > -.011 or max(zs) < .011:
            raise RuntimeError('Le flange non si sono aperte alla luce richiesta')
        if not any('test mozzo' in name for name in mats):
            raise RuntimeError('Il cilindro non ha preso il materiale di up: ' + ', '.join(mats))
        low = [p for p in pts if -.009 < p.z < -.002]
        high = [p for p in pts if .002 < p.z < .009]
        riser = [p for p in pts if abs(p.z) < .0015 and abs(p.y) < .01 and p.x > .07]
        if not low or not high:
            raise RuntimeError('Mancano i due livelli della striscia')
        if not riser:
            raise RuntimeError('Manca il raccordo verticale fra i livelli')
        two_levels = len(pts)
        set_input(mod, 'Altezza bobina', .010)
        pts, _seen = instance_points(obj)
        zs = [p.z for p in pts]
        print('LED_CHECK un livello', len(pts), 'z', (min(zs), max(zs)) if zs else None)
        if len(pts) > two_levels * 0.7:
            raise RuntimeError('Abbassare la bobina non ha tolto il secondo livello')
    finally:
        if obj.led_studio.bobina != 'NONE':
            obj.led_studio.bobina = 'NONE'
        if obj.led_studio.pcb != 'NONE':
            obj.led_studio.pcb = 'NONE'
        for piece in list(bpy.data.objects):
            if piece.library:
                bpy.data.objects.remove(piece, do_unlink=True)
        for collection in (bpy.data.meshes, bpy.data.materials):
            for block in list(collection):
                if block.library and block.users == 0:
                    collection.remove(block)
        for lib in list(bpy.data.libraries):
            bpy.data.libraries.remove(lib)
        local = bpy.data.materials.get(PREFIX + ' | test mozzo')
        if local and local.users == 0:
            bpy.data.materials.remove(local)
        col = bpy.data.collections.get('LED Studio | Libreria')
        if col and not col.objects:
            for scene_ in bpy.data.scenes:
                if col.name in scene_.collection.children:
                    scene_.collection.children.unlink(col)
            bpy.data.collections.remove(col)
        for name, value in values.items():
            set_input(obj.modifiers['Configurazione prodotto'], name, value)
        shutil.rmtree(temp, ignore_errors=True)


def main():
    if bpy.app.version < (5, 3, 0):
        raise RuntimeError('LED Studio richiede Blender 5.3 o successivo.')
    floor = make_material('fondo', (1, 1, 1), 0, .7)
    path = build_path()
    strip = build_strip()
    reel = build_reel()
    master = build_master(path, strip, reel)
    built = [setup_scene(name, master, vals, floor) for name, vals in PRESETS]
    replace_text('LEGGIMI - LED Studio', README)
    replace_text('LED Studio Libreria', PANEL_SOURCE, module=True)
    window = bpy.context.window
    if window is None:
        raise RuntimeError('Blender non ha una finestra: serve il contesto per valutare il modificatore')
    for scene, obj in built:
        window.scene = scene
        zs, _mats = mesh_report(obj)
        if not zs:
            raise RuntimeError('Geometria vuota: ' + scene.name)
        print('LED_CHECK', scene.name, 'vertices', len(zs), 'z', (min(zs), max(zs)))
    window.scene = built[0][0]
    exercise_library(built[0][0], built[0][1], PRESETS[0][1])
    window.scene = built[1][0]
    window.view_layer.objects.active = built[1][1]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.color_type = 'MATERIAL'
            elif area.type == 'PROPERTIES':
                space = area.spaces.active
                try:
                    space.context = 'MODIFIER'
                except TypeError:
                    pass
    if '--' in sys.argv:
        args = sys.argv[sys.argv.index('--') + 1:]
        if '--output' in args:
            target = os.path.abspath(args[args.index('--output') + 1])
            bpy.ops.wm.save_as_mainfile(filepath=target)
    print('LED Studio: pronto. Tre preset, quattro gruppi, pannello libreria.')


if __name__ == '__main__':
    main()
