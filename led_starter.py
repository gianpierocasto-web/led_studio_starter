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

    def vmath(self, operation, a, b=None, label=''):
        n = self.node('ShaderNodeVectorMath', label or operation)
        n.operation = operation
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs['Scale'] if operation == 'SCALE' else n.inputs[1])
        if operation in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE'):
            return n.outputs['Value']
        return n.outputs['Vector']

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
    """Repeat the modeled module along the curve, one vertex at a time."""
    q = Graph('LED | 02 PCB e componenti su curva')
    q.sock('Curva', 'NodeSocketGeometry')
    q.sock('Modulo PCB', 'NodeSocketObject')
    q.sock('Passo', default=.016, lo=.0005, hi=.1,
           description='Lunghezza X del modulo, in metri.')
    q.sock('Min X', default=-.008, lo=-.1, hi=.1,
           description='Inizio X del modulo, in metri.')
    p = q.i.outputs
    info = q.node('GeometryNodeObjectInfo', 'Modulo PCB')
    info.transform_space = 'ORIGINAL'
    info.inputs['As Instance'].default_value = False
    q.link(p['Modulo PCB'], info.inputs['Object'])
    pos = q.node('GeometryNodeInputPosition')

    cap = q.node('GeometryNodeCaptureAttribute', 'Posizione nel modulo')
    cap.domain = 'POINT'
    cap.capture_items.new('VECTOR', 'Origine')
    q.link(info.outputs['Geometry'], cap.inputs['Geometry'])
    q.link(pos.outputs['Position'], cap.inputs['Origine'])
    orig = q.node('ShaderNodeSeparateXYZ')
    q.link(cap.outputs['Origine'], orig.inputs['Vector'])

    # The board section is what both X ends have in common. A part that touches
    # only one end, such as a LED cut by the pattern boundary, stays out of it.
    def section(selection, label):
        stat = q.node('GeometryNodeAttributeStatistic', label)
        stat.data_type = 'FLOAT_VECTOR'
        stat.domain = 'POINT'
        q.link(info.outputs['Geometry'], stat.inputs['Geometry'])
        q.link(selection, stat.inputs['Selection'])
        q.link(pos.outputs['Position'], stat.inputs['Attribute'])
        lo = q.node('ShaderNodeSeparateXYZ')
        hi = q.node('ShaderNodeSeparateXYZ')
        q.link(stat.outputs['Min'], lo.inputs['Vector'])
        q.link(stat.outputs['Max'], hi.inputs['Vector'])
        return lo.outputs, hi.outputs

    mod_x = q.node('ShaderNodeSeparateXYZ')
    q.link(pos.outputs['Position'], mod_x.inputs['Vector'])
    at_start = q.math('LESS_THAN', mod_x.outputs['X'], q.math('ADD', p['Min X'], .00001))
    at_end = q.math('GREATER_THAN', mod_x.outputs['X'],
                    q.math('SUBTRACT', q.math('ADD', p['Min X'], p['Passo']), .00001))
    s_lo, s_hi = section(at_start, 'Estremità iniziale')
    e_lo, e_hi = section(at_end, 'Estremità finale')
    y_lo = q.math('MAXIMUM', s_lo['Y'], e_lo['Y'])
    y_hi = q.math('MINIMUM', s_hi['Y'], e_hi['Y'])
    z_lo = q.math('MAXIMUM', s_lo['Z'], e_lo['Z'])
    z_hi = q.math('MINIMUM', s_hi['Z'], e_hi['Z'])
    valid = q.math('MINIMUM', q.math('GREATER_THAN', y_hi, y_lo), q.math('GREATER_THAN', z_hi, z_lo))
    box = q.node('GeometryNodeBoundBox', 'Ingombro modulo')
    q.link(info.outputs['Geometry'], box.inputs['Geometry'])
    box_lo = q.node('ShaderNodeSeparateXYZ')
    box_hi = q.node('ShaderNodeSeparateXYZ')
    q.link(box.outputs['Min'], box_lo.inputs['Vector'])
    q.link(box.outputs['Max'], box_hi.inputs['Vector'])

    def center(lo, hi, box_a, box_b, label):
        sw = q.node('GeometryNodeSwitch', label)
        sw.input_type = 'FLOAT'
        q.link(valid, sw.inputs['Switch'])
        q.link(q.math('MULTIPLY', q.math('ADD', box_a, box_b), .5), sw.inputs['False'])
        q.link(q.math('MULTIPLY', q.math('ADD', lo, hi), .5), sw.inputs['True'])
        return sw.outputs['Output']

    center_y = center(y_lo, y_hi, box_lo.outputs['Y'], box_hi.outputs['Y'], 'Centro Y basetta')
    center_z = center(z_lo, z_hi, box_lo.outputs['Z'], box_hi.outputs['Z'], 'Centro Z basetta')

    domain = q.node('GeometryNodeAttributeDomainSize', 'Vertici modulo')
    domain.component = 'MESH'
    q.link(info.outputs['Geometry'], domain.inputs['Geometry'])
    has_module = q.math('GREATER_THAN', domain.outputs['Point Count'], 0)
    length = q.node('GeometryNodeCurveLength')
    q.link(p['Curva'], length.inputs['Curve'])
    safe = q.math('MAXIMUM', p['Passo'], .0000001)
    raw_count = q.node('FunctionNodeFloatToInt', 'Copie lungo la curva')
    raw_count.rounding_mode = 'CEILING'
    q.link(q.math('DIVIDE', length.outputs['Length'], safe), raw_count.inputs['Float'])
    count = q.node('GeometryNodeSwitch', 'Nessuna copia senza PCB')
    count.input_type = 'INT'
    q.link(has_module, count.inputs['Switch'])
    count.inputs['False'].default_value = 0
    q.link(raw_count.outputs['Integer'], count.inputs['True'])
    line = q.node('GeometryNodeMeshLine', 'Una copia per passo')
    line.mode = 'OFFSET'
    q.link(count.outputs['Output'], line.inputs['Count'])
    inst = q.node('GeometryNodeInstanceOnPoints', 'Copie del modulo')
    q.link(line.outputs['Mesh'], inst.inputs['Points'])
    q.link(cap.outputs['Geometry'], inst.inputs['Instance'])
    stored = q.node('GeometryNodeStoreNamedAttribute', 'Indice copia')
    stored.data_type = 'INT'
    stored.domain = 'INSTANCE'
    q.link(inst.outputs['Instances'], stored.inputs['Geometry'])
    stored.inputs['Name'].default_value = 'copia'
    q.link(q.node('GeometryNodeInputIndex').outputs['Index'], stored.inputs['Value'])
    realize = q.node('GeometryNodeRealizeInstances', 'Modulo realizzato')
    q.link(stored.outputs['Geometry'], realize.inputs['Geometry'])
    copia = q.node('GeometryNodeInputNamedAttribute', 'Copia')
    copia.data_type = 'INT'
    copia.inputs['Name'].default_value = 'copia'
    arc = q.math('ADD', q.math('SUBTRACT', orig.outputs['X'], p['Min X']),
                 q.math('MULTIPLY', copia.outputs['Attribute'], p['Passo']), 'Arco')

    sample = q.node('GeometryNodeSampleCurve', 'Punto sulla curva')
    sample.mode = 'LENGTH'
    sample.use_all_curves = True
    q.link(p['Curva'], sample.inputs['Curves'])
    q.link(arc, sample.inputs['Length'])
    tangent = q.vmath('NORMALIZE', sample.outputs['Tangent'], label='Tangente')
    sampled = q.node('ShaderNodeSeparateXYZ')
    q.link(sample.outputs['Position'], sampled.inputs['Vector'])
    radial = q.vmath('NORMALIZE', q.vec(sampled.outputs['X'], sampled.outputs['Y'], 0), label='Radiale')
    # Keep the sampled normal pointing away from the hub, then perpendicular to the tangent.
    outward = q.math('LESS_THAN', q.vmath('DOT_PRODUCT', sample.outputs['Normal'], radial), 0)
    normal = q.vmath('SCALE', sample.outputs['Normal'], q.math('SUBTRACT', 1, q.math('MULTIPLY', outward, 2)))
    normal = q.vmath('SUBTRACT', normal, q.vmath('SCALE', tangent, q.vmath('DOT_PRODUCT', normal, tangent)))
    normal = q.vmath('NORMALIZE', normal, label='Normale esterna')
    binormal = q.vmath('CROSS_PRODUCT', normal, tangent, 'Binormale')
    b_xyz = q.node('ShaderNodeSeparateXYZ')
    t_xyz = q.node('ShaderNodeSeparateXYZ')
    q.link(binormal, b_xyz.inputs['Vector'])
    q.link(tangent, t_xyz.inputs['Vector'])
    # On a reversed layer the binormal points down. Flip it back while the path is horizontal.
    flip_b = q.math('MINIMUM', q.math('LESS_THAN', q.math('ABSOLUTE', t_xyz.outputs['Z']), .5),
                    q.math('LESS_THAN', b_xyz.outputs['Z'], 0))
    binormal = q.vmath('SCALE', binormal, q.math('SUBTRACT', 1, q.math('MULTIPLY', flip_b, 2)), 'Binormale in su')
    y_rel = q.math('SUBTRACT', orig.outputs['Y'], center_y)
    z_rel = q.math('SUBTRACT', orig.outputs['Z'], center_z)
    moved = q.vmath('ADD', sample.outputs['Position'], q.vmath(
        'ADD', q.vmath('SCALE', normal, q.math('MULTIPLY', y_rel, -1), '-Y verso l\'esterno'),
        q.vmath('SCALE', binormal, z_rel, 'Z in verticale')))
    placed = q.node('GeometryNodeSetPosition', 'Vertici sul percorso')
    q.link(realize.outputs['Geometry'], placed.inputs['Geometry'])
    q.link(moved, placed.inputs['Position'])
    cut = q.node('GeometryNodeDeleteGeometry', 'Oltre la fine')
    cut.domain = 'POINT'
    cut.mode = 'ALL'
    q.link(placed.outputs['Geometry'], cut.inputs['Geometry'])
    q.link(q.math('GREATER_THAN', arc, q.math('ADD', length.outputs['Length'], .00001)), cut.inputs['Selection'])
    weld = q.node('GeometryNodeMergeByDistance', 'Salda le giunzioni')
    q.link(cut.outputs['Geometry'], weld.inputs['Geometry'])
    weld.inputs['Mode'].default_value = 'All'
    weld.inputs['Distance'].default_value = .00001
    out = q.node('GeometryNodeSwitch', 'Solo con un PCB scelto')
    out.input_type = 'GEOMETRY'
    q.link(has_module, out.inputs['Switch'])
    q.link(weld.outputs['Geometry'], out.inputs['True'])
    return q.finish(out.outputs['Output'])


def realize_collection(q, collection, label):
    """Every object in the collection, at the position it was given, as real vertices."""
    info = q.node('GeometryNodeCollectionInfo', label)
    info.transform_space = 'ORIGINAL'
    info.inputs['Separate Children'].default_value = True
    info.inputs['Reset Children'].default_value = False
    q.link(collection, info.inputs['Collection'])
    real = q.node('GeometryNodeRealizeInstances', label + ' reali')
    real.inputs['Realize All'].default_value = True
    q.link(info.outputs['Instances'], real.inputs['Geometry'])
    return real.outputs['Geometry']


def build_cable():
    """Lay every mesh in the cable collection once, starting where the strip ends."""
    q = Graph('LED | 04 Cavo su curva')
    q.sock('Curva', 'NodeSocketGeometry')
    q.sock('Cavo', 'NodeSocketCollection')
    q.sock('Inizio', default=0, lo=0, hi=40,
           description='Arco, in metri, dove finisce la striscia.')
    p = q.i.outputs
    geo = realize_collection(q, p['Cavo'], 'Cavo')
    pos = q.node('GeometryNodeInputPosition')
    cap = q.node('GeometryNodeCaptureAttribute', 'Posizione nel cavo')
    cap.domain = 'POINT'
    cap.capture_items.new('VECTOR', 'Origine')
    q.link(geo, cap.inputs['Geometry'])
    q.link(pos.outputs['Position'], cap.inputs['Origine'])
    orig = q.node('ShaderNodeSeparateXYZ')
    q.link(cap.outputs['Origine'], orig.inputs['Vector'])
    box = q.node('GeometryNodeBoundBox', 'Ingombro cavo')
    q.link(geo, box.inputs['Geometry'])
    box_lo = q.node('ShaderNodeSeparateXYZ')
    box_hi = q.node('ShaderNodeSeparateXYZ')
    q.link(box.outputs['Min'], box_lo.inputs['Vector'])
    q.link(box.outputs['Max'], box_hi.inputs['Vector'])
    # The end that meets the strip is min X. Its section, not the connector, sits on the curve.
    here = q.node('ShaderNodeSeparateXYZ')
    q.link(pos.outputs['Position'], here.inputs['Vector'])
    at_start = q.math('LESS_THAN', here.outputs['X'], q.math('ADD', box_lo.outputs['X'], .00001))
    stat = q.node('GeometryNodeAttributeStatistic', 'Sezione di attacco')
    stat.data_type = 'FLOAT_VECTOR'
    stat.domain = 'POINT'
    q.link(geo, stat.inputs['Geometry'])
    q.link(at_start, stat.inputs['Selection'])
    q.link(pos.outputs['Position'], stat.inputs['Attribute'])
    sec_lo = q.node('ShaderNodeSeparateXYZ')
    sec_hi = q.node('ShaderNodeSeparateXYZ')
    q.link(stat.outputs['Min'], sec_lo.inputs['Vector'])
    q.link(stat.outputs['Max'], sec_hi.inputs['Vector'])
    center_y = q.math('MULTIPLY', q.math('ADD', sec_lo.outputs['Y'], sec_hi.outputs['Y']), .5)
    center_z = q.math('MULTIPLY', q.math('ADD', sec_lo.outputs['Z'], sec_hi.outputs['Z']), .5)
    arc = q.math('ADD', p['Inizio'], q.math('SUBTRACT', orig.outputs['X'], box_lo.outputs['X']), 'Arco')
    length = q.node('GeometryNodeCurveLength')
    q.link(p['Curva'], length.inputs['Curve'])
    sample = q.node('GeometryNodeSampleCurve', 'Punto sulla curva')
    sample.mode = 'LENGTH'
    sample.use_all_curves = True
    q.link(p['Curva'], sample.inputs['Curves'])
    q.link(arc, sample.inputs['Length'])
    tangent = q.vmath('NORMALIZE', sample.outputs['Tangent'], label='Tangente')
    sampled = q.node('ShaderNodeSeparateXYZ')
    q.link(sample.outputs['Position'], sampled.inputs['Vector'])
    radial = q.vmath('NORMALIZE', q.vec(sampled.outputs['X'], sampled.outputs['Y'], 0), label='Radiale')
    outward = q.math('LESS_THAN', q.vmath('DOT_PRODUCT', sample.outputs['Normal'], radial), 0)
    normal = q.vmath('SCALE', sample.outputs['Normal'], q.math('SUBTRACT', 1, q.math('MULTIPLY', outward, 2)))
    normal = q.vmath('SUBTRACT', normal, q.vmath('SCALE', tangent, q.vmath('DOT_PRODUCT', normal, tangent)))
    normal = q.vmath('NORMALIZE', normal, label='Normale esterna')
    binormal = q.vmath('CROSS_PRODUCT', normal, tangent, 'Binormale')
    b_xyz = q.node('ShaderNodeSeparateXYZ')
    t_xyz = q.node('ShaderNodeSeparateXYZ')
    q.link(binormal, b_xyz.inputs['Vector'])
    q.link(tangent, t_xyz.inputs['Vector'])
    flip_b = q.math('MINIMUM', q.math('LESS_THAN', q.math('ABSOLUTE', t_xyz.outputs['Z']), .5),
                    q.math('LESS_THAN', b_xyz.outputs['Z'], 0))
    binormal = q.vmath('SCALE', binormal, q.math('SUBTRACT', 1, q.math('MULTIPLY', flip_b, 2)), 'Binormale in su')
    y_rel = q.math('SUBTRACT', orig.outputs['Y'], center_y)
    z_rel = q.math('SUBTRACT', orig.outputs['Z'], center_z)
    moved = q.vmath('ADD', sample.outputs['Position'], q.vmath(
        'ADD', q.vmath('SCALE', normal, q.math('MULTIPLY', y_rel, -1), '-Y verso l\'esterno'),
        q.vmath('SCALE', binormal, z_rel, 'Z in verticale')))
    placed = q.node('GeometryNodeSetPosition', 'Cavo sul percorso')
    q.link(cap.outputs['Geometry'], placed.inputs['Geometry'])
    q.link(moved, placed.inputs['Position'])
    cut = q.node('GeometryNodeDeleteGeometry', 'Oltre la fine')
    cut.domain = 'POINT'
    cut.mode = 'ALL'
    q.link(placed.outputs['Geometry'], cut.inputs['Geometry'])
    q.link(q.math('GREATER_THAN', arc, q.math('ADD', length.outputs['Length'], .00001)), cut.inputs['Selection'])
    domain = q.node('GeometryNodeAttributeDomainSize', 'Vertici cavo')
    domain.component = 'MESH'
    q.link(geo, domain.inputs['Geometry'])
    out = q.node('GeometryNodeSwitch', 'Solo con un cavo scelto')
    out.input_type = 'GEOMETRY'
    q.link(q.math('GREATER_THAN', domain.outputs['Point Count'], 0), out.inputs['Switch'])
    q.link(cut.outputs['Geometry'], out.inputs['True'])
    return q.finish(out.outputs['Output'])


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


def build_master(path, strip, reel, cable):
    """Stack alternating spiral layers in the reel opening and lay the PCB and cable."""
    q = Graph('LED | 00 Prodotto completo')
    q.sock('Flangia up', 'NodeSocketObject')
    q.sock('Flangia down', 'NodeSocketObject')
    q.sock('Modulo PCB', 'NodeSocketObject')
    q.sock('Cavo', 'NodeSocketCollection')
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
    # Weld the layers and risers into one spline so the base sweep has no joint.
    edges = q.node('GeometryNodeCurveToMesh', 'Percorso in spigoli')
    q.link(leave.outputs['Geometry'], edges.inputs['Curve'])
    weld = q.node('GeometryNodeMergeByDistance', 'Salda livelli e raccordi')
    q.link(edges.outputs['Mesh'], weld.inputs['Geometry'])
    weld.inputs['Mode'].default_value = 'All'
    weld.inputs['Distance'].default_value = .00001
    single = q.node('GeometryNodeMeshToCurve', 'Percorso unico')
    single.mode = 'EDGES'
    q.link(weld.outputs['Geometry'], single.inputs['Mesh'])
    pos = q.node('GeometryNodeInputPosition')
    radial = q.node('ShaderNodeSeparateXYZ')
    q.link(pos.outputs['Position'], radial.inputs['Vector'])
    outward = q.node('ShaderNodeVectorMath', 'Esterno')
    outward.operation = 'NORMALIZE'
    q.link(q.vec(radial.outputs['X'], radial.outputs['Y'], 0), outward.inputs[0])
    normal = q.node('GeometryNodeSetCurveNormal', 'Normale radiale')
    q.link(single.outputs['Curve'], normal.inputs['Curve'])
    normal.inputs['Mode'].default_value = 'Free'
    q.link(outward.outputs['Vector'], normal.inputs['Normal'])
    strip_node = q.call(strip, '02 Striscia')
    q.link(normal.outputs['Curve'], strip_node.inputs['Curva'])
    q.link(p['Modulo PCB'], strip_node.inputs['Modulo PCB'])
    q.link(passo, strip_node.inputs['Passo'])
    q.link(lo.outputs['X'], strip_node.inputs['Min X'])
    cinfo = realize_collection(q, p['Cavo'], 'Cavo')
    cbox = q.node('GeometryNodeBoundBox', 'Lunghezza cavo')
    q.link(cinfo, cbox.inputs['Geometry'])
    c_lo = q.node('ShaderNodeSeparateXYZ')
    c_hi = q.node('ShaderNodeSeparateXYZ')
    q.link(cbox.outputs['Min'], c_lo.inputs['Vector'])
    q.link(cbox.outputs['Max'], c_hi.inputs['Vector'])
    cable_len = q.math('SUBTRACT', c_hi.outputs['X'], c_lo.outputs['X'], 'Lunghezza cavo')
    span = q.node('GeometryNodeCurveLength', 'Lunghezza nastro')
    q.link(single.outputs['Curve'], span.inputs['Curve'])
    end = q.node('GeometryNodeSampleCurve', 'Fine della striscia')
    end.mode = 'LENGTH'
    end.use_all_curves = True
    q.link(single.outputs['Curve'], end.inputs['Curves'])
    q.link(span.outputs['Length'], end.inputs['Length'])
    end_xyz = q.node('ShaderNodeSeparateXYZ')
    q.link(end.outputs['Position'], end_xyz.inputs['Vector'])
    end_tan = q.vmath('NORMALIZE', end.outputs['Tangent'], label='Tangente finale')
    end_rad = q.vmath('NORMALIZE', q.vec(end_xyz.outputs['X'], end_xyz.outputs['Y'], 0), label='Radiale finale')
    radius0 = q.vmath('LENGTH', q.vec(end_xyz.outputs['X'], end_xyz.outputs['Y'], 0), label='Raggio finale')
    drds = q.vmath('DOT_PRODUCT', end_tan, end_rad, 'Apertura')
    spin = q.node('ShaderNodeSeparateXYZ')
    q.link(q.vmath('CROSS_PRODUCT', end_rad, end_tan, 'Giro'), spin.inputs['Vector'])
    omega = q.math('DIVIDE', spin.outputs['Z'], q.math('MAXIMUM', radius0, .001), 'Velocità angolare')
    angle0 = q.math('ARCTAN2', end_xyz.outputs['Y'], end_xyz.outputs['X'], 'Angolo finale')
    step = q.math('DIVIDE', q.node('GeometryNodeInputIndex').outputs['Index'], 127)
    distance = q.math('MULTIPLY', step, cable_len, 'Distanza sul cavo')
    angle = q.math('ADD', angle0, q.math('MULTIPLY', omega, distance))
    radius = q.math('ADD', radius0, q.math('MULTIPLY', drds, distance))
    tail = q.node('GeometryNodeMeshLine', 'Prolungamento')
    tail.mode = 'OFFSET'
    tail.inputs['Count'].default_value = 128
    tail_pos = q.node('GeometryNodeSetPosition', 'Stessa tangente e apertura')
    q.link(tail.outputs['Mesh'], tail_pos.inputs['Geometry'])
    q.link(q.vec(q.math('MULTIPLY', radius, q.math('COSINE', angle)),
                 q.math('MULTIPLY', radius, q.math('SINE', angle)),
                 end_xyz.outputs['Z']), tail_pos.inputs['Position'])
    tail_curve = q.node('GeometryNodeMeshToCurve', 'Curva del cavo')
    tail_curve.mode = 'EDGES'
    q.link(tail_pos.outputs['Geometry'], tail_curve.inputs['Mesh'])
    origin = q.node('GeometryNodeSampleCurve', 'Capo del prolungamento')
    origin.mode = 'FACTOR'
    origin.use_all_curves = True
    q.link(tail_curve.outputs['Curve'], origin.inputs['Curves'])
    origin.inputs['Factor'].default_value = 0
    turned = q.vmath('LENGTH', q.vmath('SUBTRACT', origin.outputs['Position'], end.outputs['Position']),
                     label='Curva rovesciata')
    tail_rev = q.node('GeometryNodeReverseCurve', 'Capo verso la striscia')
    q.link(tail_curve.outputs['Curve'], tail_rev.inputs['Curve'])
    q.link(q.math('GREATER_THAN', turned, .001), tail_rev.inputs['Selection'])
    lead_pos = q.node('GeometryNodeInputPosition')
    lead_xy = q.node('ShaderNodeSeparateXYZ')
    q.link(lead_pos.outputs['Position'], lead_xy.inputs['Vector'])
    lead_out = q.node('ShaderNodeVectorMath', 'Esterno sul cavo')
    lead_out.operation = 'NORMALIZE'
    q.link(q.vec(lead_xy.outputs['X'], lead_xy.outputs['Y'], 0), lead_out.inputs[0])
    lead_normal = q.node('GeometryNodeSetCurveNormal', 'Normale del cavo')
    q.link(tail_rev.outputs['Curve'], lead_normal.inputs['Curve'])
    lead_normal.inputs['Mode'].default_value = 'Free'
    q.link(lead_out.outputs['Vector'], lead_normal.inputs['Normal'])
    cable_node = q.call(cable, '04 Cavo')
    q.link(lead_normal.outputs['Curve'], cable_node.inputs['Curva'])
    q.link(p['Cavo'], cable_node.inputs['Cavo'])
    reel_node = q.call(reel, '03 Bobina')
    for name in ('Flangia up', 'Flangia down', 'Raggio mozzo', 'Altezza bobina'):
        q.link(p[name], reel_node.inputs[name])
    return q.finish(q.join(strip_node.outputs[0], reel_node.outputs[0], cable_node.outputs[0]))


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
    scene['NOTE'] = 'Scegli bobina, PCB e cavo dalle cartelle. Quote in metri. Nessuna lunghezza commerciale garantita.'
    scene.view_layers[0].objects.active = obj
    obj.select_set(True, view_layer=scene.view_layers[0])
    return scene, obj


PANEL_SOURCE = r'''import bpy
import os

LIBRARY = 'LED Studio | Libreria'
_bobina_items = [('NONE', 'Nessuna', 'Nessun file scelto')]
_pcb_items = [('NONE', 'Nessuna', 'Nessun file scelto')]
_cavo_items = [('NONE', 'Nessuno', 'Nessun file scelto')]


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
    if cache_name == 'cavo':
        global _cavo_items
        _cavo_items = items
        return _cavo_items
    global _pcb_items
    _pcb_items = items
    return _pcb_items


def bobina_items(self, context):
    return blend_items('bobine', 'bobina')


def pcb_items(self, context):
    return blend_items('pcb', 'pcb')


def cavo_items(self, context):
    return blend_items('cavi', 'cavo')


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


def load_collection(rel_path, name):
    target = norm(rel_path)
    for col in bpy.data.collections:
        lib = col.library
        if lib is None or norm(lib.filepath) != target:
            continue
        if same_object(name, col.name):
            return col
    with bpy.data.libraries.load(rel_path, link=True) as (src, dst):
        dst.collections = [item for item in src.collections if same_object(name, item)]
    for col in dst.collections:
        if col is not None and same_object(name, col.name):
            return col
    return None


def assign_collection(obj, kind, filename, socket, name):
    settings = obj.led_studio
    if filename == 'NONE':
        set_socket(obj, socket, None)
        settings.status = ''
        return
    rel = '//' + kind + '/' + filename
    if not os.path.isfile(bpy.path.abspath(rel)):
        settings.status = 'File mancante: ' + filename
        return
    try:
        col = load_collection(rel, name)
    except Exception as exc:
        settings.status = str(exc)
        return
    if col is None:
        settings.status = 'Nel file manca la collection: ' + name
        return
    parent = ensure_collection()
    if col.name not in parent.children:
        parent.children.link(col)
    col.hide_render = True
    set_socket(obj, socket, col)
    settings.status = ''


def update_bobina(self, context):
    assign_library(self.id_data, 'bobine', self.bobina, {'Flangia up': 'up', 'Flangia down': 'down'})


def update_pcb(self, context):
    stem = self.pcb[:-6] if self.pcb.lower().endswith('.blend') else self.pcb
    assign_library(self.id_data, 'pcb', self.pcb, {'Modulo PCB': stem})


def update_cavo(self, context):
    stem = self.cavo[:-6] if self.cavo.lower().endswith('.blend') else self.cavo
    assign_collection(self.id_data, 'cavi', self.cavo, 'Cavo', stem)


class LEDStudioSettings(bpy.types.PropertyGroup):
    bobina: bpy.props.EnumProperty(name='Bobina', items=bobina_items, update=update_bobina)
    pcb: bpy.props.EnumProperty(name='PCB', items=pcb_items, update=update_pcb)
    cavo: bpy.props.EnumProperty(name='Cavo', items=cavo_items, update=update_cavo)
    status: bpy.props.StringProperty(name='Stato', default='')


class LED_PT_library(bpy.types.Panel):
    bl_label = 'Libreria bobine, PCB e cavi'
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
        layout.prop(settings, 'cavo')
        if settings.status:
            layout.label(text=settings.status, icon='ERROR')
        root = bpy.path.abspath('//')
        missing = [name for name in ('bobine', 'pcb', 'cavi') if not os.path.isdir(os.path.join(root, name))]
        if missing:
            layout.label(text='Crea accanto al file: ' + ', '.join(missing) + '.')


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

1. Le cartelle bobine, pcb e cavi stanno accanto a questo file.
2. In bobine metti un .blend per modello. Dentro, due mesh chiamate up e down,
   origine al centro della bobina, asse Z, transform applicati, materiali già assegnati.
   up sta dal lato Z positivo, down dal lato negativo.
3. In pcb metti un .blend per codice. L'oggetto mesh ha il nome del file
   senza estensione, per esempio FN01234. Origine al centro del passo.
   X è il passo lungo il nastro, Z è la larghezza, il lato LED guarda verso -Y.
   Il modulo viene ripetuto così com'è: ogni vertice segue la curva, quindi
   basetta e LED restano quelli del file, senza giunzione fra una copia e la successiva.
4. In cavi metti un .blend per cavo. La collection ha il nome del file
   senza estensione e può contenere più mesh. X è la lunghezza: il capo a
   X minimo si attacca alla striscia, il connettore sta verso X massimo.
   La sezione sta in Y e Z, il lato -Y guarda fuori dal mozzo.
   Conta la posizione di ogni oggetto: non unirli e non applicare i transform.
   Non si ripete: la misura X complessiva è il tratto.
5. Seleziona LED_... Se il pannello non compare, abilita Auto Run Python Scripts
   oppure esegui una volta il testo LED Studio Libreria.
   Nel modificatore Configurazione prodotto scegli Bobina, PCB e poi Cavo.
6. Regola Altezza bobina, i raggi, il passo radiale e l'uscita.
7. F12 per il render; tastierino 0 per la camera.

Le flange non si scalano: si allontanano fino alla luce richiesta.
Il cilindro fra le due prende il primo materiale di up.
La larghezza della striscia è la misura Z del pezzo PCB, non uno slider.
I livelli sono la parte intera di altezza / larghezza, minimo uno. Il resto
resta come margine, centrato fra le flange.
Il nastro è continuo: il livello dispari torna indietro e un raccordo verticale
sale di una larghezza. L'uscita è disegnata solo se il nastro finisce all'esterno,
cioè con un numero dispari di livelli.
Il cavo parte da quel punto e ne segue la curva, con la stessa tangente.

QUOTE in metri: 0.008 = 8 mm.
Mantieni Raggio mozzo < Raggio avvolgimento, e il raggio di avvolgimento
dentro la flangia vera. Un avvolgimento troppo fitto può intersecare i componenti.
Non interpreta una lunghezza commerciale esatta: è un avvolgimento illustrativo.

Gruppi: 00 Prodotto completo; 01 Percorso spirale e uscita;
02 PCB e componenti su curva; 03 Bobina parametrica; 04 Cavo su curva.

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


def make_pcb_piece(name, material):
    """Base spanning the full pitch, plus two detached components on the -Y side."""
    parts = [((.004, .0003, .008), (0, 0, 0)),
             ((.001, .0006, .002), (-.001, -.00045, 0)),
             ((.001, .0006, .002), (.001, -.00045, .002))]
    verts, faces = [], []
    for size, (cx, cy, cz) in parts:
        hx, hy, hz = (axis / 2 for axis in size)
        start = len(verts)
        for x, y, z in [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
                        (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]:
            verts.append((cx + x, cy + y, cz + z))
        for face in [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]:
            faces.append(tuple(start + i for i in face))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    return bpy.data.objects.new(name, mesh)


def make_cable(name, tube_mat, plug_mat):
    """A tube and a separate connector, kept apart by the connector's location."""
    segs = 16
    length = .08
    radius = .0015
    verts = []
    for station in (0, .02, .04, .06, length):
        for i in range(segs):
            ang = 2 * math.pi * i / segs
            verts.append((station, radius * math.cos(ang), radius * math.sin(ang)))
    faces = []
    rings = 5
    for ring in range(rings - 1):
        for i in range(segs):
            nxt = (i + 1) % segs
            a = ring * segs + i
            b = ring * segs + nxt
            faces.append((a, a + segs, b + segs, b))
    tube_mesh = bpy.data.meshes.new(name + ' tubo')
    tube_mesh.from_pydata(verts, [], faces)
    tube_mesh.materials.append(tube_mat)
    tube_mesh.update()
    tube = bpy.data.objects.new(name + ' tubo', tube_mesh)
    hx, hy, hz = .006, .002, .002
    box = []
    for x, y, z in [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
                    (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]:
        box.append((x, y, z))
    box_faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    plug_mesh = bpy.data.meshes.new(name + ' connettore')
    plug_mesh.from_pydata(box, [], box_faces)
    plug_mesh.materials.append(plug_mat)
    plug_mesh.update()
    plug = bpy.data.objects.new(name + ' connettore', plug_mesh)
    plug.location.x = length + hx
    col = bpy.data.collections.new(name)
    col.objects.link(tube)
    col.objects.link(plug)
    return col


def mesh_report(obj):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    zs = [v.co.z for v in mesh.vertices]
    mats = [slot.name for slot in mesh.materials if slot]
    # Base vertices only: away from the hub and below the flange faces at +-0.005.
    strip_z = [v.co.z for v in mesh.vertices
               if .03 < Vector((v.co.x, v.co.y)).length < .095 and abs(v.co.z) < .0049]
    parent = list(range(len(mesh.vertices)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for edge in mesh.edges:
        a, b = root(edge.vertices[0]), root(edge.vertices[1])
        if a != b:
            parent[a] = b
    islands = len({root(i) for i in range(len(parent))})
    ev.to_mesh_clear()
    return zs, mats, islands, strip_z


def analyze_strip(obj):
    """The welded base is the one large island. Each rigid part must sit just outside it."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    zs = [v.co.z for v in mesh.vertices]
    mats = [slot.name for slot in mesh.materials if slot]
    parent = list(range(len(mesh.vertices)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for edge in mesh.edges:
        a, b = root(edge.vertices[0]), root(edge.vertices[1])
        if a != b:
            parent[a] = b
    groups = {}
    for i in range(len(mesh.vertices)):
        groups.setdefault(root(i), []).append(i)
    islands = list(groups.values())
    report = {'verts': len(zs), 'z': (min(zs), max(zs)) if zs else None, 'mats': mats,
              'base_verts': 0, 'base_span': None, 'big_islands': 0,
              'components': 0, 'near': 0, 'seated': 0, 'low': 0, 'high': 0, 'gap': None}
    gaps = []
    if not islands:
        ev.to_mesh_clear()
        return report
    base_ids = max(islands, key=len)
    report['base_verts'] = len(base_ids)
    report['big_islands'] = sum(1 for ids in islands if len(ids) > 500)
    cell = .004
    grid = {}
    span = []
    for i in base_ids:
        co = mesh.vertices[i].co
        key = tuple(int(math.floor(axis / cell)) for axis in co)
        grid.setdefault(key, []).append(Vector(co))
        if .03 < math.hypot(co.x, co.y) < .095:
            span.append(co.z)
    if span:
        report['base_span'] = (min(span), max(span))

    def nearest(point):
        base_key = tuple(int(math.floor(axis / cell)) for axis in point)
        found = None
        gap = None
        for dz in range(-2, 3):
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    for co in grid.get((base_key[0] + dx, base_key[1] + dy, base_key[2] + dz), ()):
                        dist = (co - point).length
                        if gap is None or dist < gap:
                            gap = dist
                            found = co
        return gap, found

    for ids in islands:
        if ids is base_ids or len(ids) > 24:
            continue
        acc = Vector()
        for i in ids:
            acc += mesh.vertices[i].co
        center = acc / len(ids)
        radius = math.hypot(center.x, center.y)
        if radius < .02:
            continue
        report['components'] += 1
        gap, found = nearest(center)
        if gap is not None:
            gaps.append(gap)
        if found is not None and gap < .006:
            report['near'] += 1
            outward = Vector((found.x, found.y, 0))
            if outward.length > 1e-6 and (center - found).dot(outward.normalized()) > .00005:
                report['seated'] += 1
        if center.z < -.001:
            report['low'] += 1
        if center.z > .001:
            report['high'] += 1
    if gaps:
        gaps.sort()
        report['gap'] = gaps[len(gaps) // 2]
    ev.to_mesh_clear()
    return report


def check_cable(obj, mat_name):
    """The lead starts on the strip end, follows its tangent, and bends outward."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    cable = []
    plug = []
    used = set()
    for poly in mesh.polygons:
        slot = mesh.materials[poly.material_index] if poly.material_index < len(mesh.materials) else None
        if slot is None or mat_name not in slot.name:
            continue
        is_plug = 'connettore' in slot.name
        for index in poly.vertices:
            if index not in used:
                used.add(index)
                co = mesh.vertices[index].co.copy()
                cable.append(co)
                if is_plug:
                    plug.append(co)
    strip = [v.co.copy() for i, v in enumerate(mesh.vertices)
             if i not in used and abs(v.co.z) < .0045 and math.hypot(v.co.x, v.co.y) > .03]
    ev.to_mesh_clear()
    if len(cable) < 8 or len(strip) < 8:
        raise RuntimeError('Il cavo non è in scena: pezzi %d, striscia %d' % (len(cable), len(strip)))
    if len(plug) < 8:
        raise RuntimeError('Manca il connettore: la collection non è arrivata intera')
    plug_r = max(math.hypot(v.x, v.y) for v in plug)
    tube_r = max(math.hypot(v.x, v.y) for v in cable if v not in plug)
    if plug_r <= tube_r:
        raise RuntimeError('Il connettore non sta oltre il tubo')
    tip = max(math.hypot(v.x, v.y) for v in strip)
    inner = min(cable, key=lambda v: math.hypot(v.x, v.y))
    ring = [v for v in cable if (v - inner).length < .0032]
    if len(ring) < 8:
        raise RuntimeError('Il cavo non ha il capo di attacco')
    start = sum(ring, Vector()) / len(ring)
    closest = sorted(strip, key=lambda v: (v - start).length)[:4]
    end = sum(closest, Vector()) / len(closest)
    gap = (start - end).length
    # The test module only has vertices at the ends of its 4 mm pitch, so the
    # mesh can stop a couple of millimetres before the curve end. A real PCB,
    # with vertices all along X, meets the cable.
    if gap > .0025:
        raise RuntimeError('Attacco del cavo staccato: %.4f m' % gap)
    ahead = [v for v in cable if .008 < (v - start).length < .02]
    before = [v for v in strip if .006 < (v - end).length < .015 and math.hypot(v.x, v.y) < math.hypot(end.x, end.y) + .001]
    if len(ahead) < 4 or not before:
        raise RuntimeError('Manca il tratto fra striscia e cavo')
    prev = sum(before, Vector()) / len(before)
    mid = sum(ahead, Vector()) / len(ahead)
    align = (end - prev).normalized().dot((mid - start).normalized())
    if align < .95:
        raise RuntimeError('Il cavo non segue la tangente della striscia: %.3f' % align)
    far = max(math.hypot(v.x, v.y) for v in cable)
    if far < tip + .005:
        raise RuntimeError('Il cavo non esce oltre la striscia')
    outer_pts = [v for v in cable if math.hypot(v.x, v.y) > far - .003]
    outer = sum(outer_pts, Vector()) / len(outer_pts)
    chord = outer - start
    span = chord.length
    half = []
    for v in cable:
        t = (v - start).dot(chord) / (span * span)
        if .4 < t < .6:
            half.append(v)
    if not half:
        raise RuntimeError('Il cavo non ha un tratto centrale')
    center = sum(half, Vector()) / len(half)
    closest = start + chord * ((center - start).dot(chord) / (span * span))
    bow = (center - closest).length
    print('LED_CHECK cavo gap', round(gap, 5), 'far', round(far - tip, 4), 'bow', round(bow, 4))
    if bow < .001:
        raise RuntimeError('Il cavo è diritto, non segue la curva')


def exercise_library(scene, obj, values):
    """Link a temporary coil and PCB the way the panel does, then remove them."""
    panel = load_panel()
    temp = tempfile.mkdtemp(prefix='led_studio_')
    host = os.path.join(temp, 'LED_Studio.blend')
    bpy.ops.wm.save_as_mainfile(filepath=host)
    os.makedirs(os.path.join(temp, 'bobine'))
    os.makedirs(os.path.join(temp, 'pcb'))
    os.makedirs(os.path.join(temp, 'cavi'))
    mat = make_material('test mozzo', (.2, .45, .8), 0, .4)
    pcb_mat = make_material('test base pcb', (.9, .9, .85), 0, .4)
    cable_mat = make_material('test cavo', (.95, .95, .95), 0, .35)
    plug_mat = make_material('test cavo connettore', (.2, .2, .2), .6, .3)
    up = make_box('up', (.2, .2, .002), (0, 0, .005))
    down = make_box('down', (.2, .2, .002), (0, 0, -.005))
    pcb = make_pcb_piece('FN01234', pcb_mat)
    cable = make_cable('cavo bianco', cable_mat, plug_mat)
    up.data.materials.append(mat)
    bobina_path = os.path.join(temp, 'bobine', 'bobina bianca.blend')
    pcb_path = os.path.join(temp, 'pcb', 'FN01234.blend')
    cable_path = os.path.join(temp, 'cavi', 'cavo bianco.blend')
    bpy.data.libraries.write(bobina_path, {up, up.data, down, down.data, mat}, fake_user=True)
    bpy.data.libraries.write(pcb_path, {pcb, pcb.data, pcb_mat}, fake_user=True)
    cable_ids = {cable, cable_mat, plug_mat}
    for piece in cable.objects:
        cable_ids.add(piece)
        cable_ids.add(piece.data)
    bpy.data.libraries.write(cable_path, cable_ids, fake_user=True)
    for piece in (up, down, pcb):
        data = piece.data
        bpy.data.objects.remove(piece, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    for piece in list(cable.objects):
        data = piece.data
        bpy.data.objects.remove(piece, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    bpy.data.collections.remove(cable)
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
        report = analyze_strip(obj)
        print('LED_CHECK library', report)
        if not report['z'] or report['z'][0] > -.011 or report['z'][1] < .011:
            raise RuntimeError('Le flange non si sono aperte alla luce richiesta')
        if not any('test mozzo' in name for name in report['mats']):
            raise RuntimeError('Il cilindro non ha preso il materiale di up: ' + ', '.join(report['mats']))
        if not any('test base pcb' in name for name in report['mats']):
            raise RuntimeError('La basetta non ha il materiale del modulo: ' + ', '.join(report['mats']))
        if report['big_islands'] != 1:
            raise RuntimeError('La basetta non è un unico pezzo: %d isole grandi' % report['big_islands'])
        if not report['components'] or report['near'] != report['components'] or report['seated'] < report['components'] * .99:
            raise RuntimeError('Componenti staccati dalla basetta: %d vicini, %d esterni, su %d' % (
                report['near'], report['seated'], report['components']))
        if not report['low'] or not report['high']:
            raise RuntimeError('Mancano i componenti su uno dei due livelli')
        two_levels = report['verts']
        set_input(mod, 'Altezza bobina', .010)
        report = analyze_strip(obj)
        print('LED_CHECK un livello', report)
        if report['verts'] > two_levels * 0.7:
            raise RuntimeError('Abbassare la bobina non ha tolto il secondo livello')
        if report['big_islands'] != 1 or report['near'] != report['components'] or report['seated'] < report['components'] * .99:
            raise RuntimeError('Un livello: basetta spezzata o componenti staccati')
        span = report['base_span']
        if not span or span[1] - span[0] < .007:
            raise RuntimeError('La larghezza della basetta non è verticale')
        if 'cavo bianco.blend' not in [item[0] for item in panel['cavo_items'](None, None)]:
            raise RuntimeError('Il menu Cavo non elenca il file di prova')
        obj.led_studio.cavo = 'cavo bianco.blend'
        if obj.led_studio.status:
            raise RuntimeError(obj.led_studio.status)
        check_cable(obj, 'test cavo')
    finally:
        if obj.led_studio.bobina != 'NONE':
            obj.led_studio.bobina = 'NONE'
        if obj.led_studio.pcb != 'NONE':
            obj.led_studio.pcb = 'NONE'
        if obj.led_studio.cavo != 'NONE':
            obj.led_studio.cavo = 'NONE'
        for piece in list(bpy.data.objects):
            if piece.library:
                bpy.data.objects.remove(piece, do_unlink=True)
        for collection in (bpy.data.meshes, bpy.data.materials):
            for block in list(collection):
                if block.library and block.users == 0:
                    collection.remove(block)
        for col in list(bpy.data.collections):
            if not col.library:
                continue
            for parent in bpy.data.collections:
                if col.name in parent.children:
                    parent.children.unlink(col)
            bpy.data.collections.remove(col)
        for lib in list(bpy.data.libraries):
            bpy.data.libraries.remove(lib)
        for name in ('test mozzo', 'test base pcb', 'test cavo', 'test cavo connettore'):
            local = bpy.data.materials.get(PREFIX + ' | ' + name)
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
    cable = build_cable()
    master = build_master(path, strip, reel, cable)
    built = [setup_scene(name, master, vals, floor) for name, vals in PRESETS]
    replace_text('LEGGIMI - LED Studio', README)
    replace_text('LED Studio Libreria', PANEL_SOURCE, module=True)
    window = bpy.context.window
    if window is None:
        raise RuntimeError('Blender non ha una finestra: serve il contesto per valutare il modificatore')
    for scene, obj in built:
        window.scene = scene
        zs, _mats, _islands, _strip_z = mesh_report(obj)
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
    print('LED Studio: pronto. Tre preset, cinque gruppi, pannello libreria.')


if __name__ == '__main__':
    main()
