"""LED Studio — Geometry Nodes starter, Blender 5.3+. Run from Text Editor.
Creates a NEW scene for each preset. Existing scenes and objects are retained.
CLI: blender -b --python scripts/led_starter.py -- --output /absolute/path/LED_Studio.blend
     blender -b LED_Studio.blend --python scripts/led_starter.py -- --upgrade-inplace

Coil, PCB and cable geometry come from .blend files in ./bobine, ./pcb and ./cavi.
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


def curve_frame(q, sample):
    """Shared orthonormal frame for strip and cable: X along tangent, -Y outward, Z up."""
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
    return tangent, normal, binormal


def build_strip():
    """Repeat the modeled module along the curve, one vertex at a time."""
    q = Graph('LED | 02 PCB e componenti su curva')
    q.sock('Curva', 'NodeSocketGeometry')
    q.sock('Modulo PCB', 'NodeSocketCollection')
    q.sock('Passo', default=.016, lo=.0005, hi=.1,
           description='Lunghezza X del modulo, in metri.')
    q.sock('Min X', default=-.008, lo=-.1, hi=.1,
           description='Inizio X del modulo, in metri.')
    p = q.i.outputs
    mod_geo = realize_collection(q, p['Modulo PCB'], 'Modulo PCB')
    pos = q.node('GeometryNodeInputPosition')

    cap = q.node('GeometryNodeCaptureAttribute', 'Posizione nel modulo')
    cap.domain = 'POINT'
    cap.capture_items.new('VECTOR', 'Origine')
    q.link(mod_geo, cap.inputs['Geometry'])
    q.link(pos.outputs['Position'], cap.inputs['Origine'])
    orig = q.node('ShaderNodeSeparateXYZ')
    q.link(cap.outputs['Origine'], orig.inputs['Vector'])

    # The board section is what both X ends have in common. A part that touches
    # only one end, such as a LED cut by the pattern boundary, stays out of it.
    def section(selection, label):
        stat = q.node('GeometryNodeAttributeStatistic', label)
        stat.data_type = 'FLOAT_VECTOR'
        stat.domain = 'POINT'
        q.link(mod_geo, stat.inputs['Geometry'])
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
    q.link(mod_geo, box.inputs['Geometry'])
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
    q.link(mod_geo, domain.inputs['Geometry'])
    has_module = q.math('GREATER_THAN', domain.outputs['Point Count'], 0)
    length = q.node('GeometryNodeCurveLength')
    q.link(p['Curva'], length.inputs['Curve'])
    safe = q.math('MAXIMUM', p['Passo'], .0000001)
    raw_count = q.node('FunctionNodeFloatToInt', 'Copie intere')
    raw_count.rounding_mode = 'FLOOR'
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
    tangent, normal, binormal = curve_frame(q, sample)
    y_rel = q.math('SUBTRACT', orig.outputs['Y'], center_y)
    z_rel = q.math('SUBTRACT', orig.outputs['Z'], center_z)
    moved = q.vmath('ADD', sample.outputs['Position'], q.vmath(
        'ADD', q.vmath('SCALE', normal, q.math('MULTIPLY', y_rel, -1), '-Y verso l\'esterno'),
        q.vmath('SCALE', binormal, z_rel, 'Z in verticale')))
    arc_store = q.node('GeometryNodeStoreNamedAttribute', 'Arco')
    arc_store.data_type = 'FLOAT'
    arc_store.domain = 'POINT'
    arc_store.inputs['Name'].default_value = 'arco'
    q.link(realize.outputs['Geometry'], arc_store.inputs['Geometry'])
    q.link(arc, arc_store.inputs['Value'])
    flag = q.node('GeometryNodeStoreNamedAttribute', 'Nastro')
    flag.data_type = 'FLOAT'
    flag.domain = 'POINT'
    flag.inputs['Name'].default_value = 'nastro'
    flag.inputs['Value'].default_value = 1.0
    q.link(arc_store.outputs['Geometry'], flag.inputs['Geometry'])
    tan_store = q.node('GeometryNodeStoreNamedAttribute', 'Tangente nastro')
    tan_store.data_type = 'FLOAT_VECTOR'
    tan_store.domain = 'POINT'
    tan_store.inputs['Name'].default_value = 'tangente'
    q.link(flag.outputs['Geometry'], tan_store.inputs['Geometry'])
    q.link(tangent, tan_store.inputs['Value'])
    placed = q.node('GeometryNodeSetPosition', 'Vertici sul percorso')
    q.link(tan_store.outputs['Geometry'], placed.inputs['Geometry'])
    q.link(moved, placed.inputs['Position'])
    weld = q.node('GeometryNodeMergeByDistance', 'Salda le giunzioni')
    q.link(placed.outputs['Geometry'], weld.inputs['Geometry'])
    weld.inputs['Mode'].default_value = 'All'
    weld.inputs['Distance'].default_value = .00001
    edge_ang = q.node('GeometryNodeInputMeshEdgeAngle', 'Angolo spigoli')
    sharp = q.node('GeometryNodeSetShadeSmooth', 'Spigoli vivi oltre 35 gradi')
    sharp.domain = 'EDGE'
    sharp.inputs['Shade Smooth'].default_value = False
    q.link(weld.outputs['Geometry'], sharp.inputs['Geometry'])
    q.link(q.math('GREATER_THAN', edge_ang.outputs['Unsigned Angle'], math.radians(35)), sharp.inputs['Selection'])
    out = q.node('GeometryNodeSwitch', 'Solo con un PCB scelto')
    out.input_type = 'GEOMETRY'
    q.link(has_module, out.inputs['Switch'])
    q.link(sharp.outputs['Geometry'], out.inputs['True'])
    return q.finish(out.outputs['Output'])


def realize_collection(q, collection, label, with_piece_id=False):
    """Every object in the collection, at the position it was given, as real vertices."""
    info = q.node('GeometryNodeCollectionInfo', label)
    info.transform_space = 'ORIGINAL'
    info.inputs['Separate Children'].default_value = True
    info.inputs['Reset Children'].default_value = False
    q.link(collection, info.inputs['Collection'])
    instances = info.outputs['Instances']
    if with_piece_id:
        piece = q.node('GeometryNodeStoreNamedAttribute', label + ' id')
        piece.data_type = 'INT'
        piece.domain = 'INSTANCE'
        piece.inputs['Name'].default_value = 'pezzo'
        q.link(instances, piece.inputs['Geometry'])
        q.link(q.node('GeometryNodeInputIndex').outputs['Index'], piece.inputs['Value'])
        instances = piece.outputs['Geometry']
    real = q.node('GeometryNodeRealizeInstances', label + ' reali')
    real.inputs['Realize All'].default_value = True
    q.link(instances, real.inputs['Geometry'])
    return real.outputs['Geometry']


def densify_tubes(q, geo, step):
    """Rebuild a two-ring tube with skinned quad rings every `step`, keeping circle count, caps and material."""
    island = q.node('GeometryNodeInputMeshIsland')
    counted = q.node('GeometryNodeAttributeStatistic', 'Isole del cavo')
    counted.data_type = 'FLOAT'
    counted.domain = 'POINT'
    q.link(geo, counted.inputs['Geometry'])
    q.link(island.outputs['Island Index'], counted.inputs['Attribute'])
    total_pts = q.node('GeometryNodeAttributeDomainSize', 'Punti flessibili')
    total_pts.component = 'MESH'
    q.link(geo, total_pts.inputs['Geometry'])
    has_pts = q.math('GREATER_THAN', total_pts.outputs['Point Count'], 0)
    how_many = q.node('FunctionNodeFloatToInt', 'Quante isole')
    how_many.rounding_mode = 'FLOOR'
    q.link(q.math('MULTIPLY', q.math('ADD', counted.outputs['Max'], 1), has_pts), how_many.inputs['Float'])
    enter, leave = q.repeat('Isole guaina')
    q.link(how_many.outputs['Integer'], enter.inputs['Iterations'])
    part = q.node('GeometryNodeSeparateGeometry', 'Isola')
    part.domain = 'POINT'
    q.link(geo, part.inputs['Geometry'])
    q.link(q.compare(island.outputs['Island Index'], enter.outputs['Iteration']), part.inputs['Selection'])
    box = q.node('GeometryNodeBoundBox', 'Ingombro isola')
    q.link(part.outputs['Selection'], box.inputs['Geometry'])
    lo = q.node('ShaderNodeSeparateXYZ')
    hi = q.node('ShaderNodeSeparateXYZ')
    q.link(box.outputs['Min'], lo.inputs['Vector'])
    q.link(box.outputs['Max'], hi.inputs['Vector'])
    span = q.math('SUBTRACT', hi.outputs['X'], lo.outputs['X'])
    here = q.node('ShaderNodeSeparateXYZ')
    q.link(q.node('GeometryNodeInputPosition').outputs['Position'], here.inputs['Vector'])
    at_lo = q.math('LESS_THAN', here.outputs['X'], q.math('ADD', lo.outputs['X'], .00005))
    at_hi = q.math('GREATER_THAN', here.outputs['X'], q.math('SUBTRACT', hi.outputs['X'], .00005))
    ring = q.node('GeometryNodeSeparateGeometry', 'Anello iniziale')
    ring.domain = 'POINT'
    q.link(part.outputs['Selection'], ring.inputs['Geometry'])
    q.link(at_lo, ring.inputs['Selection'])
    far = q.node('GeometryNodeSeparateGeometry', 'Anello finale')
    far.domain = 'POINT'
    q.link(part.outputs['Selection'], far.inputs['Geometry'])
    q.link(at_hi, far.inputs['Selection'])
    n_all = q.node('GeometryNodeAttributeDomainSize', 'Vertici isola')
    n_all.component = 'MESH'
    q.link(part.outputs['Selection'], n_all.inputs['Geometry'])
    n_lo = q.node('GeometryNodeAttributeDomainSize', 'Vertici anello')
    n_lo.component = 'MESH'
    q.link(ring.outputs['Selection'], n_lo.inputs['Geometry'])
    n_hi = q.node('GeometryNodeAttributeDomainSize', 'Vertici anello opposto')
    n_hi.component = 'MESH'
    q.link(far.outputs['Selection'], n_hi.inputs['Geometry'])
    is_tube = q.math('MINIMUM', q.math('GREATER_THAN', n_lo.outputs['Point Count'], 2), q.math('MINIMUM',
                     q.compare(n_lo.outputs['Point Count'], n_hi.outputs['Point Count'], .1),
                     q.math('MINIMUM', q.compare(n_all.outputs['Point Count'],
                                                 q.math('MULTIPLY', n_lo.outputs['Point Count'], 2), .1),
                            q.math('GREATER_THAN', span, q.math('MULTIPLY', step, 1.5)))))
    no_faces = q.node('GeometryNodeDeleteGeometry', 'Solo bordo')
    no_faces.domain = 'FACE'
    no_faces.mode = 'ONLY_FACE'
    q.link(ring.outputs['Selection'], no_faces.inputs['Geometry'])
    rim_init = q.node('GeometryNodeStoreNamedAttribute', 'Bordo iniziale')
    rim_init.data_type = 'BOOLEAN'
    rim_init.domain = 'EDGE'
    rim_init.inputs['Name'].default_value = 'bordo'
    rim_init.inputs['Value'].default_value = True
    q.link(no_faces.outputs['Geometry'], rim_init.inputs['Geometry'])
    gaps = q.node('FunctionNodeFloatToInt', 'Anelli da inserire')
    gaps.rounding_mode = 'ROUND'
    q.link(q.math('DIVIDE', span, q.math('MAXIMUM', step, .0000001)), gaps.inputs['Float'])
    tube_iters = q.node('FunctionNodeFloatToInt', 'Passi estrusi')
    tube_iters.rounding_mode = 'ROUND'
    q.link(q.math('MULTIPLY', gaps.outputs['Integer'], is_tube), tube_iters.inputs['Float'])
    dx = q.math('DIVIDE', span, q.math('MAXIMUM', gaps.outputs['Integer'], 1))
    step_in, step_out = q.repeat('Passi guaina')
    q.link(tube_iters.outputs['Integer'], step_in.inputs['Iterations'])
    q.link(rim_init.outputs['Geometry'], step_in.inputs['Geometry'])
    rim_attr = q.node('GeometryNodeInputNamedAttribute', 'Bordo corrente')
    rim_attr.data_type = 'BOOLEAN'
    rim_attr.inputs['Name'].default_value = 'bordo'
    extrude = q.node('GeometryNodeExtrudeMesh', 'Fascia guaina')
    extrude.mode = 'EDGES'
    extrude.inputs['Offset Scale'].default_value = 1.0
    q.link(step_in.outputs['Geometry'], extrude.inputs['Mesh'])
    q.link(rim_attr.outputs['Attribute'], extrude.inputs['Selection'])
    q.link(q.vec(dx, 0, 0), extrude.inputs['Offset'])
    rim_next = q.node('GeometryNodeStoreNamedAttribute', 'Nuovo bordo')
    rim_next.data_type = 'BOOLEAN'
    rim_next.domain = 'EDGE'
    rim_next.inputs['Name'].default_value = 'bordo'
    q.link(extrude.outputs['Mesh'], rim_next.inputs['Geometry'])
    q.link(extrude.outputs['Top'], rim_next.inputs['Value'])
    q.link(rim_next.outputs['Geometry'], step_out.inputs['Geometry'])
    cy = q.math('MULTIPLY', q.math('ADD', lo.outputs['Y'], hi.outputs['Y']), .5)
    cz = q.math('MULTIPLY', q.math('ADD', lo.outputs['Z'], hi.outputs['Z']), .5)
    outward_yz = q.vec(0, q.math('SUBTRACT', here.outputs['Y'], cy), q.math('SUBTRACT', here.outputs['Z'], cz))
    wall_flip = q.node('GeometryNodeFlipFaces', 'Normali esterne')
    q.link(step_out.outputs['Geometry'], wall_flip.inputs['Mesh'])
    q.link(q.math('LESS_THAN', q.vmath('DOT_PRODUCT',
                  q.node('GeometryNodeInputNormal').outputs['Normal'], outward_yz), 0),
           wall_flip.inputs['Selection'])
    skinned = q.join(wall_flip.outputs['Mesh'], ring.outputs['Selection'], far.outputs['Selection'])
    weld = q.node('GeometryNodeMergeByDistance', 'Salda tappi')
    weld.inputs['Mode'].default_value = 'All'
    weld.inputs['Distance'].default_value = .00001
    q.link(skinned, weld.inputs['Geometry'])
    mats = q.node('GeometryNodeGeometryMaterials', 'Materiali tubo')
    mats.inputs['Component Type'].default_value = 'Mesh'
    q.link(part.outputs['Selection'], mats.inputs['Geometry'])
    mat_item = q.node('GeometryNodeListGetItem', 'Primo materiale')
    mat_item.socket_type = 'MATERIAL'
    q.link(mats.outputs['Materials'], mat_item.inputs['List'])
    mat_item.inputs['Index'].default_value = 0
    with_mat = q.material(weld.outputs['Geometry'], mat_item.outputs['Value'])
    sm_stat = q.node('GeometryNodeAttributeStatistic', 'Ombreggiatura tubo')
    sm_stat.data_type = 'FLOAT'
    sm_stat.domain = 'FACE'
    q.link(part.outputs['Selection'], sm_stat.inputs['Geometry'])
    q.link(q.node('GeometryNodeInputShadeSmooth').outputs['Smooth'], sm_stat.inputs['Attribute'])
    shaded = q.node('GeometryNodeSetShadeSmooth', 'Stessa ombreggiatura')
    q.link(with_mat, shaded.inputs['Geometry'])
    q.link(q.math('GREATER_THAN', sm_stat.outputs['Max'], .5), shaded.inputs['Shade Smooth'])
    cleaned = q.node('GeometryNodeRemoveAttribute', 'Pulisci bordo')
    cleaned.inputs['Name'].default_value = 'bordo'
    q.link(shaded.outputs['Geometry'], cleaned.inputs['Geometry'])
    chosen = q.node('GeometryNodeSwitch', 'Solo i tubi lunghi')
    chosen.input_type = 'GEOMETRY'
    q.link(is_tube, chosen.inputs['Switch'])
    q.link(part.outputs['Selection'], chosen.inputs['False'])
    q.link(cleaned.outputs['Geometry'], chosen.inputs['True'])
    q.link(q.join(enter.outputs['Geometry'], chosen.outputs['Output']), leave.inputs['Geometry'])
    return leave.outputs['Geometry']


def build_cable():
    """Lay every mesh in the cable collection once, starting where the strip ends."""
    q = Graph('LED | 04 Cavo su curva')
    q.sock('Curva', 'NodeSocketGeometry')
    q.sock('Cavo flessibile', 'NodeSocketCollection')
    q.sock('Connettore', 'NodeSocketCollection')
    q.sock('Passo deformazione cavo', default=.001, lo=.0002, hi=.01,
           description='Distanza fra gli anelli inseriti nella guaina, in metri.')
    p = q.i.outputs
    flex = densify_tubes(q, realize_collection(q, p['Cavo flessibile'], 'Cavo flessibile'),
                         p['Passo deformazione cavo'])
    rigid = realize_collection(q, p['Connettore'], 'Connettore', with_piece_id=True)
    both = q.join(flex, rigid)
    pos = q.node('GeometryNodeInputPosition')
    box = q.node('GeometryNodeBoundBox', 'Ingombro cavo')
    q.link(both, box.inputs['Geometry'])
    box_lo = q.node('ShaderNodeSeparateXYZ')
    q.link(box.outputs['Min'], box_lo.inputs['Vector'])

    def place(geometry, along, dx, y_rel, z_rel, role):
        sample = q.node('GeometryNodeSampleCurve', 'Punto sulla curva')
        sample.mode = 'LENGTH'
        sample.use_all_curves = True
        q.link(p['Curva'], sample.inputs['Curves'])
        q.link(along, sample.inputs['Length'])
        tangent, normal, binormal = curve_frame(q, sample)
        moved = q.vmath('ADD', sample.outputs['Position'], q.vmath('ADD', q.vmath(
            'SCALE', tangent, dx), q.vmath(
            'ADD', q.vmath('SCALE', normal, q.math('MULTIPLY', y_rel, -1)),
            q.vmath('SCALE', binormal, z_rel))))
        cap_i = q.node('GeometryNodeCaptureAttribute', 'Origine pezzo')
        cap_i.domain = 'POINT'
        cap_i.capture_items.new('VECTOR', 'Origine')
        q.link(geometry, cap_i.inputs['Geometry'])
        q.link(pos.outputs['Position'], cap_i.inputs['Origine'])
        placed = q.node('GeometryNodeSetPosition', 'Sul percorso')
        q.link(cap_i.outputs['Geometry'], placed.inputs['Geometry'])
        q.link(moved, placed.inputs['Position'])
        marked = q.node('GeometryNodeStoreNamedAttribute', 'Ruolo')
        marked.data_type = 'INT'
        marked.domain = 'POINT'
        marked.inputs['Name'].default_value = 'ruolo'
        marked.inputs['Value'].default_value = role
        q.link(placed.outputs['Geometry'], marked.inputs['Geometry'])
        origin = q.node('GeometryNodeStoreNamedAttribute', 'Origine')
        origin.data_type = 'FLOAT_VECTOR'
        origin.domain = 'POINT'
        origin.inputs['Name'].default_value = 'origine'
        q.link(marked.outputs['Geometry'], origin.inputs['Geometry'])
        q.link(cap_i.outputs['Origine'], origin.inputs['Value'])
        flagged = q.node('GeometryNodeStoreNamedAttribute', 'Cavo')
        flagged.data_type = 'FLOAT'
        flagged.domain = 'POINT'
        flagged.inputs['Name'].default_value = 'cavo'
        flagged.inputs['Value'].default_value = 1.0
        q.link(origin.outputs['Geometry'], flagged.inputs['Geometry'])
        tan_store = q.node('GeometryNodeStoreNamedAttribute', 'Tangente cavo')
        tan_store.data_type = 'FLOAT_VECTOR'
        tan_store.domain = 'POINT'
        tan_store.inputs['Name'].default_value = 'tangente'
        q.link(flagged.outputs['Geometry'], tan_store.inputs['Geometry'])
        q.link(tangent, tan_store.inputs['Value'])
        return tan_store.outputs['Geometry']

    flex_cap = q.node('GeometryNodeCaptureAttribute', 'Flessibile')
    flex_cap.domain = 'POINT'
    flex_cap.capture_items.new('VECTOR', 'Origine')
    q.link(flex, flex_cap.inputs['Geometry'])
    q.link(pos.outputs['Position'], flex_cap.inputs['Origine'])
    flex_o = q.node('ShaderNodeSeparateXYZ')
    q.link(flex_cap.outputs['Origine'], flex_o.inputs['Vector'])
    here = q.node('ShaderNodeSeparateXYZ')
    q.link(pos.outputs['Position'], here.inputs['Vector'])
    at_start = q.math('LESS_THAN', here.outputs['X'], q.math('ADD', box_lo.outputs['X'], .00001))
    stat = q.node('GeometryNodeAttributeStatistic', 'Sezione di attacco')
    stat.data_type = 'FLOAT_VECTOR'
    stat.domain = 'POINT'
    q.link(both, stat.inputs['Geometry'])
    q.link(at_start, stat.inputs['Selection'])
    q.link(pos.outputs['Position'], stat.inputs['Attribute'])
    sec_lo = q.node('ShaderNodeSeparateXYZ')
    sec_hi = q.node('ShaderNodeSeparateXYZ')
    q.link(stat.outputs['Min'], sec_lo.inputs['Vector'])
    q.link(stat.outputs['Max'], sec_hi.inputs['Vector'])
    center_y = q.math('MULTIPLY', q.math('ADD', sec_lo.outputs['Y'], sec_hi.outputs['Y']), .5)
    center_z = q.math('MULTIPLY', q.math('ADD', sec_lo.outputs['Z'], sec_hi.outputs['Z']), .5)
    flex_s = q.math('SUBTRACT', flex_o.outputs['X'], box_lo.outputs['X'])
    flex_geo = place(flex_cap.outputs['Geometry'], flex_s, 0,
                     q.math('SUBTRACT', flex_o.outputs['Y'], center_y),
                     q.math('SUBTRACT', flex_o.outputs['Z'], center_z), 0)
    piece_id = q.node('GeometryNodeInputNamedAttribute', 'Id connettore')
    piece_id.data_type = 'INT'
    piece_id.inputs['Name'].default_value = 'pezzo'
    rigid_cap = q.node('GeometryNodeCaptureAttribute', 'Connettore')
    rigid_cap.domain = 'POINT'
    rigid_cap.capture_items.new('VECTOR', 'Origine')
    q.link(rigid, rigid_cap.inputs['Geometry'])
    q.link(pos.outputs['Position'], rigid_cap.inputs['Origine'])
    rigid_o = q.node('ShaderNodeSeparateXYZ')
    q.link(rigid_cap.outputs['Origine'], rigid_o.inputs['Vector'])
    xmin = q.node('GeometryNodeFieldMinAndMax', 'X di innesto')
    xmin.data_type = 'FLOAT'
    xmin.domain = 'POINT'
    q.link(rigid_o.outputs['X'], xmin.inputs['Value'])
    q.link(piece_id.outputs['Attribute'], xmin.inputs['Group ID'])
    rigid_s = q.math('SUBTRACT', xmin.outputs['Min'], box_lo.outputs['X'])
    rigid_placed = place(rigid_cap.outputs['Geometry'], rigid_s,
                         q.math('SUBTRACT', rigid_o.outputs['X'], xmin.outputs['Min']),
                         q.math('SUBTRACT', rigid_o.outputs['Y'], center_y),
                         q.math('SUBTRACT', rigid_o.outputs['Z'], center_z),
                         1)
    rigid_geo = q.node('GeometryNodeRemoveAttribute', 'Pulisci pezzo')
    rigid_geo.inputs['Name'].default_value = 'pezzo'
    q.link(rigid_placed, rigid_geo.inputs['Geometry'])
    domain = q.node('GeometryNodeAttributeDomainSize', 'Vertici cavo')
    domain.component = 'MESH'
    q.link(both, domain.inputs['Geometry'])
    out = q.node('GeometryNodeSwitch', 'Solo con un cavo scelto')
    out.input_type = 'GEOMETRY'
    q.link(q.math('GREATER_THAN', domain.outputs['Point Count'], 0), out.inputs['Switch'])
    q.link(q.join(flex_geo, rigid_geo.outputs['Geometry']), out.inputs['True'])
    return q.finish(out.outputs['Output'])


def build_reel():
    """Move up and down apart to match Altezza bobina."""
    q = Graph('LED | 03 Bobina parametrica')
    q.sock('Flangia up', 'NodeSocketCollection')
    q.sock('Flangia down', 'NodeSocketCollection')
    q.sock('Altezza bobina', default=.014, lo=.002, hi=.2,
           description='Luce interna fra le flange, in metri.')
    p = q.i.outputs

    def flange(socket_name, sign):
        flange_geo = realize_collection(q, p[socket_name], socket_name)
        pos = q.node('GeometryNodeInputPosition')
        sep_p = q.node('ShaderNodeSeparateXYZ')
        q.link(pos.outputs['Position'], sep_p.inputs['Vector'])
        rad = q.vmath('LENGTH', q.vec(sep_p.outputs['X'], sep_p.outputs['Y'], 0), label='Raggio punto')
        r_stat = q.node('GeometryNodeAttributeStatistic', 'Raggio max flangia')
        r_stat.data_type = 'FLOAT'
        r_stat.domain = 'POINT'
        q.link(flange_geo, r_stat.inputs['Geometry'])
        q.link(rad, r_stat.inputs['Attribute'])
        on_disk = q.math('GREATER_THAN', rad, q.math('MULTIPLY', r_stat.outputs['Max'], .45))
        disk_geo = q.node('GeometryNodeSeparateGeometry', 'Disco flangia')
        disk_geo.domain = 'POINT'
        q.link(flange_geo, disk_geo.inputs['Geometry'])
        q.link(on_disk, disk_geo.inputs['Selection'])
        disk_cnt = q.node('GeometryNodeAttributeDomainSize', 'Punti disco')
        disk_cnt.component = 'MESH'
        q.link(disk_geo.outputs['Selection'], disk_cnt.inputs['Geometry'])
        z_stat = q.node('GeometryNodeAttributeStatistic', 'Quota disco')
        z_stat.data_type = 'FLOAT'
        z_stat.domain = 'POINT'
        q.link(flange_geo, z_stat.inputs['Geometry'])
        q.link(on_disk, z_stat.inputs['Selection'])
        q.link(sep_p.outputs['Z'], z_stat.inputs['Attribute'])
        box = q.node('GeometryNodeBoundBox')
        q.link(flange_geo, box.inputs['Geometry'])
        sep = q.node('ShaderNodeSeparateXYZ')
        q.link(box.outputs['Min'] if sign > 0 else box.outputs['Max'], sep.inputs['Vector'])
        z_ref = q.node('GeometryNodeSwitch', 'Appoggio flangia')
        z_ref.input_type = 'FLOAT'
        q.link(q.math('GREATER_THAN', disk_cnt.outputs['Point Count'], 0), z_ref.inputs['Switch'])
        q.link(sep.outputs['Z'], z_ref.inputs['False'])
        q.link(z_stat.outputs['Min'] if sign > 0 else z_stat.outputs['Max'], z_ref.inputs['True'])
        half = q.math('MULTIPLY', p['Altezza bobina'], .5 * sign)
        moved = q.transform(flange_geo, q.vec(0, 0, q.math('SUBTRACT', half, z_ref.outputs['Output'])))
        return moved

    up = flange('Flangia up', 1)
    down = flange('Flangia down', -1)
    return q.finish(q.join(up, down))


def build_master(path, strip, reel, cable):
    """Stack alternating spiral layers in the reel opening and lay the PCB and cable."""
    q = Graph('LED | 00 Prodotto completo')
    q.sock('Flangia up', 'NodeSocketCollection')
    q.sock('Flangia down', 'NodeSocketCollection')
    q.sock('Modulo PCB', 'NodeSocketCollection')
    q.sock('Cavo flessibile', 'NodeSocketCollection')
    q.sock('Connettore', 'NodeSocketCollection')
    q.sock('Passo deformazione cavo', default=.001, lo=.0002, hi=.01,
           description='Distanza fra gli anelli inseriti nella guaina, in metri.')
    for name, value, lo, hi in [('Raggio mozzo', .026, .012, .08), ('Raggio avvolgimento', .078, .025, .18),
                                ('Passo radiale', .002, .0012, .008), ('Giri uscita', .83, .25, 1.5),
                                ('Apertura uscita', .035, .005, .08)]:
        q.sock(name, default=value, lo=lo, hi=hi)
    q.sock('Altezza bobina', default=.014, lo=.002, hi=.2,
           description='Luce interna fra le flange, in metri. I livelli sono la parte intera di questa misura divisa per la larghezza Z del PCB.')
    p = q.i.outputs
    mod_geo = realize_collection(q, p['Modulo PCB'], 'Quote modulo')
    box = q.node('GeometryNodeBoundBox')
    q.link(mod_geo, box.inputs['Geometry'])
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
    # Mesh to Curve does not keep the winding order. The path has to start at the hub.
    z0 = q.math('ADD', q.math('ADD', q.math('MULTIPLY', p['Altezza bobina'], -.5), margin),
                q.math('MULTIPLY', larghezza, .5))
    hub = q.vec(p['Raggio mozzo'], 0, z0)
    path_head = q.node('GeometryNodeSampleCurve', 'Capo percorso')
    path_foot = q.node('GeometryNodeSampleCurve', 'Coda percorso')
    for sample, factor in ((path_head, 0.0), (path_foot, 1.0)):
        sample.mode = 'FACTOR'
        sample.use_all_curves = True
        q.link(single.outputs['Curve'], sample.inputs['Curves'])
        sample.inputs['Factor'].default_value = factor
    path_back = q.node('GeometryNodeReverseCurve', 'Il percorso parte dal mozzo')
    q.link(single.outputs['Curve'], path_back.inputs['Curve'])
    path_aimed = q.node('GeometryNodeSwitch', 'Verso del percorso')
    path_aimed.input_type = 'GEOMETRY'
    q.link(q.math('LESS_THAN', q.vmath('DISTANCE', path_foot.outputs['Position'], hub),
                  q.vmath('DISTANCE', path_head.outputs['Position'], hub)), path_aimed.inputs['Switch'])
    q.link(single.outputs['Curve'], path_aimed.inputs['False'])
    q.link(path_back.outputs['Curve'], path_aimed.inputs['True'])
    single_curve = path_aimed.outputs['Output']
    pos = q.node('GeometryNodeInputPosition')
    radial = q.node('ShaderNodeSeparateXYZ')
    q.link(pos.outputs['Position'], radial.inputs['Vector'])
    outward = q.node('ShaderNodeVectorMath', 'Esterno')
    outward.operation = 'NORMALIZE'
    q.link(q.vec(radial.outputs['X'], radial.outputs['Y'], 0), outward.inputs[0])
    normal = q.node('GeometryNodeSetCurveNormal', 'Normale radiale')
    q.link(single_curve, normal.inputs['Curve'])
    normal.inputs['Mode'].default_value = 'Free'
    q.link(outward.outputs['Vector'], normal.inputs['Normal'])
    strip_node = q.call(strip, '02 Striscia')
    q.link(normal.outputs['Curve'], strip_node.inputs['Curva'])
    q.link(p['Modulo PCB'], strip_node.inputs['Modulo PCB'])
    q.link(passo, strip_node.inputs['Passo'])
    q.link(lo.outputs['X'], strip_node.inputs['Min X'])
    cinfo = q.join(realize_collection(q, p['Cavo flessibile'], 'Cavo flessibile'),
                   realize_collection(q, p['Connettore'], 'Connettore'))
    cbox = q.node('GeometryNodeBoundBox', 'Lunghezza cavo')
    q.link(cinfo, cbox.inputs['Geometry'])
    c_lo = q.node('ShaderNodeSeparateXYZ')
    c_hi = q.node('ShaderNodeSeparateXYZ')
    q.link(cbox.outputs['Min'], c_lo.inputs['Vector'])
    q.link(cbox.outputs['Max'], c_hi.inputs['Vector'])
    cable_len = q.math('SUBTRACT', c_hi.outputs['X'], c_lo.outputs['X'], 'Lunghezza cavo')
    span = q.node('GeometryNodeCurveLength', 'Lunghezza nastro')
    q.link(single_curve, span.inputs['Curve'])
    # Whole modules only: the cable starts where that last face sits, not at the raw curve end.
    safe_pitch = q.math('MAXIMUM', passo, .0000001)
    modules = q.node('FunctionNodeFloatToInt', 'Moduli interi')
    modules.rounding_mode = 'FLOOR'
    q.link(q.math('DIVIDE', span.outputs['Length'], safe_pitch), modules.inputs['Float'])
    has_pitch = q.math('GREATER_THAN', passo, .00001)
    attach = q.node('GeometryNodeSwitch', 'Arco di attacco')
    attach.input_type = 'FLOAT'
    q.link(has_pitch, attach.inputs['Switch'])
    q.link(q.math('MULTIPLY', modules.outputs['Integer'], passo), attach.inputs['True'])
    attach.inputs['False'].default_value = 0.0
    # The cable curve starts at the attachment and runs along the same spiral.
    on_curve = q.node('GeometryNodeTrimCurve', 'Dal PCB lungo la spirale')
    on_curve.mode = 'LENGTH'
    q.link(single_curve, on_curve.inputs['Curve'])
    q.link(attach.outputs['Output'], on_curve.inputs['Start_001'])
    q.link(q.math('MINIMUM', q.math('ADD', attach.outputs['Output'], cable_len), span.outputs['Length']),
           on_curve.inputs['End_001'])
    covered = q.node('GeometryNodeCurveLength', 'Tratto già sulla spirale')
    q.link(on_curve.outputs['Curve'], covered.inputs['Curve'])
    extra_len = q.math('MAXIMUM', q.math('SUBTRACT', cable_len, covered.outputs['Length']), 0)
    giri = p['Giri uscita']
    last_even = q.compare(q.math('FLOORED_MODULO', q.math('SUBTRACT', livelli, 1), 2), 0, label='Ultimo pari')
    t_end = q.node('GeometryNodeSwitch', 'Parametro finale')
    t_end.input_type = 'FLOAT'
    q.link(last_even, t_end.inputs['Switch'])
    q.link(q.math('ADD', turns, giri), t_end.inputs['True'])
    t_end.inputs['False'].default_value = 0.0
    z_last = q.math('ADD', q.math('ADD', q.math('MULTIPLY', p['Altezza bobina'], -.5), margin),
                    q.math('ADD', q.math('MULTIPLY', larghezza, .5),
                           q.math('MULTIPLY', q.math('SUBTRACT', livelli, 1), larghezza)),
                    'Quota ultimo livello')
    along = q.math('DIVIDE', q.node('GeometryNodeInputIndex').outputs['Index'], 3071)
    outward_t = q.math('ADD', t_end.outputs['Output'], q.math('MULTIPLY', along, 3))
    inward_t = q.math('MULTIPLY', q.math('MULTIPLY', along, 3), -1)
    t_tail = q.node('GeometryNodeSwitch', 'Verso di uscita')
    t_tail.input_type = 'FLOAT'
    q.link(last_even, t_tail.inputs['Switch'])
    q.link(outward_t, t_tail.inputs['True'])
    q.link(inward_t, t_tail.inputs['False'])
    past = q.math('MAXIMUM', q.math('SUBTRACT', t_tail.outputs['Output'], turns), 0)
    expansion = q.math('MULTIPLY', p['Apertura uscita'],
                       q.math('POWER', q.math('DIVIDE', past, q.math('MAXIMUM', giri, .001)), 2))
    radius = q.math('MAXIMUM',
                    q.math('ADD', q.math('ADD', p['Raggio mozzo'],
                                         q.math('MULTIPLY', t_tail.outputs['Output'], p['Passo radiale'])),
                           expansion),
                    .004)
    angle = q.math('MULTIPLY', t_tail.outputs['Output'], 2 * math.pi)
    tail = q.node('GeometryNodeMeshLine', 'Prolungamento della spirale')
    tail.mode = 'OFFSET'
    tail.inputs['Count'].default_value = 3072
    tail_pos = q.node('GeometryNodeSetPosition', 'Stessa spirale')
    q.link(tail.outputs['Mesh'], tail_pos.inputs['Geometry'])
    q.link(q.vec(q.math('MULTIPLY', radius, q.math('COSINE', angle)),
                 q.math('MULTIPLY', radius, q.math('SINE', angle)),
                 z_last), tail_pos.inputs['Position'])
    tail_curve = q.node('GeometryNodeMeshToCurve', 'Curva del prolungamento')
    tail_curve.mode = 'EDGES'
    q.link(tail_pos.outputs['Geometry'], tail_curve.inputs['Mesh'])
    # Mesh to Curve can flip the spline. Keep the end that sits on the spiral.
    r_join = q.math('ADD', q.math('ADD', p['Raggio mozzo'],
                                  q.math('MULTIPLY', t_end.outputs['Output'], p['Passo radiale'])),
                    q.math('MULTIPLY', p['Apertura uscita'], q.math('POWER', q.math('DIVIDE',
                        q.math('MAXIMUM', q.math('SUBTRACT', t_end.outputs['Output'], turns), 0),
                        q.math('MAXIMUM', giri, .001)), 2)))
    ang_join = q.math('MULTIPLY', t_end.outputs['Output'], 2 * math.pi)
    expect = q.vec(q.math('MULTIPLY', r_join, q.math('COSINE', ang_join)),
                   q.math('MULTIPLY', r_join, q.math('SINE', ang_join)), z_last)
    head = q.node('GeometryNodeSampleCurve', 'Capo grezzo')
    foot = q.node('GeometryNodeSampleCurve', 'Coda grezza')
    for sample, factor in ((head, 0.0), (foot, 1.0)):
        sample.mode = 'FACTOR'
        sample.use_all_curves = True
        q.link(tail_curve.outputs['Curve'], sample.inputs['Curves'])
        sample.inputs['Factor'].default_value = factor
    flipped = q.math('LESS_THAN', q.vmath('DISTANCE', foot.outputs['Position'], expect),
                     q.vmath('DISTANCE', head.outputs['Position'], expect))
    backward = q.node('GeometryNodeReverseCurve', 'Raddrizza il prolungamento')
    q.link(tail_curve.outputs['Curve'], backward.inputs['Curve'])
    aimed = q.node('GeometryNodeSwitch', 'Verso del prolungamento')
    aimed.input_type = 'GEOMETRY'
    q.link(flipped, aimed.inputs['Switch'])
    q.link(tail_curve.outputs['Curve'], aimed.inputs['False'])
    q.link(backward.outputs['Curve'], aimed.inputs['True'])
    tail_trim = q.node('GeometryNodeTrimCurve', 'Solo il tratto che manca')
    tail_trim.mode = 'LENGTH'
    q.link(aimed.outputs['Output'], tail_trim.inputs['Curve'])
    tail_trim.inputs['Start_001'].default_value = 0.0
    q.link(extra_len, tail_trim.inputs['End_001'])
    end_pt = q.node('GeometryNodeSampleCurve', 'Fine della striscia')
    end_pt.mode = 'LENGTH'
    end_pt.use_all_curves = True
    q.link(single_curve, end_pt.inputs['Curves'])
    q.link(span.outputs['Length'], end_pt.inputs['Length'])
    tail_pt = q.node('GeometryNodeSampleCurve', 'Inizio prolungamento')
    tail_pt.mode = 'FACTOR'
    tail_pt.use_all_curves = True
    q.link(tail_trim.outputs['Curve'], tail_pt.inputs['Curves'])
    tail_pt.inputs['Factor'].default_value = 0.0
    shift = q.vmath('SUBTRACT', end_pt.outputs['Position'], tail_pt.outputs['Position'], 'Allinea il capo')
    tail_shift = q.node('GeometryNodeSetPosition', 'Capo sulla fine della striscia')
    q.link(tail_trim.outputs['Curve'], tail_shift.inputs['Geometry'])
    q.link(shift, tail_shift.inputs['Offset'])
    tangent_ok = q.math('GREATER_THAN', q.vmath(
        'DOT_PRODUCT', q.vmath('NORMALIZE', end_pt.outputs['Tangent']),
        q.vmath('NORMALIZE', tail_pt.outputs['Tangent'])), .999)
    use_tail = q.math('MINIMUM', tangent_ok, q.math('GREATER_THAN', extra_len, .0001))
    extended = q.join(on_curve.outputs['Curve'], tail_shift.outputs['Geometry'])
    ext_edges = q.node('GeometryNodeCurveToMesh', 'Cavo in spigoli')
    q.link(extended, ext_edges.inputs['Curve'])
    ext_weld = q.node('GeometryNodeMergeByDistance', 'Salda il prolungamento')
    q.link(ext_edges.outputs['Mesh'], ext_weld.inputs['Geometry'])
    ext_weld.inputs['Mode'].default_value = 'All'
    ext_weld.inputs['Distance'].default_value = .00001
    ext_curve = q.node('GeometryNodeMeshToCurve', 'Curva del cavo')
    ext_curve.mode = 'EDGES'
    q.link(ext_weld.outputs['Geometry'], ext_curve.inputs['Mesh'])
    cable_curve = q.node('GeometryNodeSwitch', 'Prolungamento solo se è tangente')
    cable_curve.input_type = 'GEOMETRY'
    q.link(use_tail, cable_curve.inputs['Switch'])
    q.link(on_curve.outputs['Curve'], cable_curve.inputs['False'])
    q.link(ext_curve.outputs['Curve'], cable_curve.inputs['True'])
    join_pt = q.node('GeometryNodeSampleCurve', 'Punto di attacco')
    join_pt.mode = 'LENGTH'
    join_pt.use_all_curves = True
    q.link(single_curve, join_pt.inputs['Curves'])
    q.link(attach.outputs['Output'], join_pt.inputs['Length'])
    raw_head = q.node('GeometryNodeSampleCurve', 'Inizio cavo')
    raw_foot = q.node('GeometryNodeSampleCurve', 'Fine cavo')
    for sample, factor in ((raw_head, 0.0), (raw_foot, 1.0)):
        sample.mode = 'FACTOR'
        sample.use_all_curves = True
        q.link(cable_curve.outputs['Output'], sample.inputs['Curves'])
        sample.inputs['Factor'].default_value = factor
    cable_back = q.node('GeometryNodeReverseCurve', 'Il cavo parte dal PCB')
    q.link(cable_curve.outputs['Output'], cable_back.inputs['Curve'])
    cable_aimed = q.node('GeometryNodeSwitch', 'Verso del cavo')
    cable_aimed.input_type = 'GEOMETRY'
    q.link(q.math('LESS_THAN', q.vmath('DISTANCE', raw_foot.outputs['Position'], join_pt.outputs['Position']),
                  q.vmath('DISTANCE', raw_head.outputs['Position'], join_pt.outputs['Position'])),
           cable_aimed.inputs['Switch'])
    q.link(cable_curve.outputs['Output'], cable_aimed.inputs['False'])
    q.link(cable_back.outputs['Curve'], cable_aimed.inputs['True'])
    lead_pos = q.node('GeometryNodeInputPosition')
    lead_xy = q.node('ShaderNodeSeparateXYZ')
    q.link(lead_pos.outputs['Position'], lead_xy.inputs['Vector'])
    lead_out = q.node('ShaderNodeVectorMath', 'Esterno sul cavo')
    lead_out.operation = 'NORMALIZE'
    q.link(q.vec(lead_xy.outputs['X'], lead_xy.outputs['Y'], 0), lead_out.inputs[0])
    lead_normal = q.node('GeometryNodeSetCurveNormal', 'Normale del cavo')
    q.link(cable_aimed.outputs['Output'], lead_normal.inputs['Curve'])
    lead_normal.inputs['Mode'].default_value = 'Free'
    q.link(lead_out.outputs['Vector'], lead_normal.inputs['Normal'])
    cable_node = q.call(cable, '04 Cavo')
    q.link(lead_normal.outputs['Curve'], cable_node.inputs['Curva'])
    q.link(p['Cavo flessibile'], cable_node.inputs['Cavo flessibile'])
    q.link(p['Connettore'], cable_node.inputs['Connettore'])
    q.link(p['Passo deformazione cavo'], cable_node.inputs['Passo deformazione cavo'])
    reel_node = q.call(reel, '03 Bobina')
    for name in ('Flangia up', 'Flangia down', 'Altezza bobina'):
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
import bmesh
import math
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
    low_wanted = wanted.lower()
    low_name = linked_name.lower()
    if low_name == low_wanted:
        return True
    prefix = low_wanted + '.'
    return low_name.startswith(prefix) and low_name[len(prefix):].isdigit()


def get_socket(obj, name, default=None):
    mod = modifier_of(obj)
    if mod is None:
        return default
    for item in mod.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == name:
            return mod.properties.inputs[item.identifier].get('value', default)
    return default


def ensure_collection():
    col = bpy.data.collections.get(LIBRARY)
    if col is None:
        col = bpy.data.collections.new(LIBRARY)
    for scene in bpy.data.scenes:
        if scene.library is not None:
            continue
        if col.name not in scene.collection.children:
            scene.collection.children.link(col)
    col.hide_render = True
    col.hide_viewport = False
    return col


def role_bucket(name):
    parent = ensure_collection()
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in parent.children:
        parent.children.link(col)
    for piece in list(col.objects):
        col.objects.unlink(piece)
        if piece.library is None and piece.name.startswith('LED Studio | Consolidato '):
            data = piece.data
            bpy.data.objects.remove(piece, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)
    col.hide_render = True
    col.hide_viewport = True
    return col


def is_renderable_mesh(obj, pre_hidden=None):
    if obj is None or obj.type != 'MESH':
        return False
    was_hidden = pre_hidden.get(obj.name, obj.hide_render) if pre_hidden is not None else obj.hide_render
    return (not was_hidden and not obj.hide_viewport
            and obj.display_type not in ('WIRE', 'BOUNDS'))


def link_blend_assets(rel_path, reload_lib=False):
    target = norm(rel_path)
    if reload_lib:
        for lib in list(bpy.data.libraries):
            if norm(lib.filepath) == target:
                lib.reload()
    def from_target(items):
        return [x for x in items if x.library is not None and norm(x.library.filepath) == target]

    pre_hidden = {o.name: bool(o.hide_render) for o in from_target(bpy.data.objects)}
    with bpy.data.libraries.load(rel_path, link=True) as (src, dst):
        ex_o = set(pre_hidden.keys())
        ex_c = {c.name for c in from_target(bpy.data.collections)}
        ex_s = {s.name for s in from_target(bpy.data.scenes)}
        dst.objects = [n for n in src.objects if n not in ex_o]
        dst.collections = [n for n in src.collections if n not in ex_c]
        dst.scenes = [n for n in src.scenes if n not in ex_s]
    for o in dst.objects:
        if o is not None:
            pre_hidden[o.name] = bool(o.hide_render)
    loaded_objs = from_target(bpy.data.objects)
    loaded_cols = from_target(bpy.data.collections)
    loaded_scenes = from_target(bpy.data.scenes)

    visible = set()
    if loaded_scenes:
        for sc in loaded_scenes:
            if not sc.view_layers:
                continue
            root_lc = sc.view_layers[0].layer_collection
            if root_lc is None:
                continue
            def walk(lc):
                if lc.exclude or lc.hide_viewport or lc.collection.hide_viewport or lc.collection.hide_render:
                    return
                for o in lc.collection.objects:
                    if is_renderable_mesh(o, pre_hidden):
                        visible.add(o)
                for ch in lc.children:
                    walk(ch)
            walk(root_lc)
    if not visible:
        for o in loaded_objs:
            if is_renderable_mesh(o, pre_hidden):
                visible.add(o)

    parent = ensure_collection()
    parent.hide_viewport = False
    existing_ptrs = set(parent.objects)
    for o in loaded_objs:
        if o not in existing_ptrs:
            parent.objects.link(o)
            existing_ptrs.add(o)
    parent.hide_render = True
    bpy.context.view_layer.update()
    return sorted(visible, key=lambda o: o.name), loaded_cols


def hide_library_in_viewport():
    col = bpy.data.collections.get(LIBRARY)
    if col is not None:
        col.hide_render = True
        col.hide_viewport = True


def bake_finished_mesh(objs, bucket, label, slice_step=None, align_ends=False):
    if not objs:
        return None
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats = []
    mat_map = {}
    uv_layer = bm.loops.layers.uv.new('UVMap')
    sharp_edges = bm.edges.layers.int.get('sharp_edge')
    if sharp_edges is None:
        sharp_edges = bm.edges.layers.int.new('sharp_edge')
    for o in sorted(objs, key=lambda x: x.name):
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        if not len(me.vertices):
            ev.to_mesh_clear()
            continue
        if not o.matrix_world.is_identity or len(o.location) == 3:
            mw = o.matrix_world if any(abs(o.matrix_world[r][c] - (1.0 if r == c else 0.0)) > 1e-6 for r in range(4) for c in range(4)) else o.matrix_basis
            me.transform(mw)
        src_mats = [bpy.data.materials.get((mt.name, mt.library.filepath) if mt.library else mt.name) if mt else None
                    for mt in me.materials]
        l2g = {}
        has_valid = any(mt is not None for mt in src_mats)
        for idx, mt in enumerate(src_mats):
            if mt is None:
                continue
            key = (mt.name, mt.library.filepath if mt.library else '')
            if key not in mat_map:
                mat_map[key] = len(mats)
                mats.append(mt)
            l2g[idx] = mat_map[key]
        old_faces = len(bm.faces)
        old_edges = len(bm.edges)
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        src_sharp = me.attributes.get('sharp_edge')
        if src_sharp is not None and src_sharp.domain == 'EDGE':
            for ei, ed in enumerate(bm.edges[old_edges:]):
                ed[sharp_edges] = 1 if src_sharp.data[ei].value else 0
        src_uv = me.uv_layers.active.data if me.uv_layers.active else None
        for fi, f in enumerate(bm.faces[old_faces:]):
            poly = me.polygons[fi]
            f.material_index = l2g.get(poly.material_index, 0) if has_valid else 0
            f.smooth = poly.use_smooth
            if src_uv:
                for li, loop in enumerate(f.loops):
                    loop[uv_layer].uv = src_uv[poly.loop_start + li].uv
        ev.to_mesh_clear()

    if not len(bm.verts):
        bm.free()
        return None

    if align_ends and len(bm.verts):
        # Snap open profile loops at the two ends of each spanning island to one clean X plane
        xs_all = [v.co.x for v in bm.verts]
        g_min_x, g_max_x = min(xs_all), max(xs_all)
        g_span = g_max_x - g_min_x
        if g_span > 1e-4:
            bm.verts.index_update()
            seen_v = set()
            snap_lo = []
            snap_hi = []
            for v in bm.verts:
                if v.index in seen_v:
                    continue
                comp = []
                stack = [v]
                while stack:
                    cur = stack.pop()
                    if cur.index in seen_v:
                        continue
                    seen_v.add(cur.index)
                    comp.append(cur)
                    for ed in cur.link_edges:
                        stack.append(ed.other_vert(cur))
                c_xs = [cv.co.x for cv in comp]
                c_min, c_max = min(c_xs), max(c_xs)
                if (c_max - c_min) > g_span * 0.96:
                    snap_lo.append((comp, c_min))
                    snap_hi.append((comp, c_max))
            if snap_lo:
                target_lo = max(c_min for _comp, c_min in snap_lo)
                target_hi = min(c_max for _comp, c_max in snap_hi)
                if target_hi > target_lo + g_span * 0.90:
                    for comp, c_min in snap_lo:
                        for cv in comp:
                            if cv.co.x < c_min + 2e-4:
                                cv.co.x = target_lo
                    for comp, c_max in snap_hi:
                        for cv in comp:
                            if cv.co.x > c_max - 2e-4:
                                cv.co.x = target_hi
                    for v in bm.verts:
                        if v.co.x < target_lo:
                            v.co.x = target_lo
                        elif v.co.x > target_hi:
                            v.co.x = target_hi

    if slice_step and slice_step > 1e-5:
        xs = [v.co.x for v in bm.verts]
        min_x, max_x = min(xs), max(xs)
        n_cuts = min(int(math.ceil((max_x - min_x) / slice_step)), 400)
        for k in range(1, n_cuts):
            px = min_x + k * slice_step
            if px >= max_x - 1e-4:
                break
            geom = set()
            for e in bm.edges:
                x0, x1 = e.verts[0].co.x, e.verts[1].co.x
                if min(x0, x1) < px - 1e-6 and max(x0, x1) > px + 1e-6 and abs(x1 - x0) > slice_step * 1.15:
                    geom.add(e)
                    for f in e.link_faces:
                        geom.add(f)
                        for fe in f.edges:
                            geom.add(fe)
                            geom.add(fe.verts[0])
                            geom.add(fe.verts[1])
            if geom:
                bmesh.ops.bisect_plane(bm, geom=list(geom), plane_co=(px, 0, 0), plane_no=(1, 0, 0))
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)

    mesh_name = 'LED Studio | Consolidato ' + label
    out_me = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(out_me)
    bm.free()
    if 'custom_normal' in out_me.attributes:
        out_me.attributes.remove(out_me.attributes['custom_normal'])
    for mt in mats:
        out_me.materials.append(mt)
    out_me.update()
    out_obj = bpy.data.objects.new(mesh_name, out_me)
    out_obj.hide_render = True
    out_obj.hide_viewport = False
    bucket.objects.link(out_obj)
    hide_library_in_viewport()
    return out_obj


def update_bobina(self, context):
    obj = self.id_data
    settings = obj.led_studio
    up_bucket = role_bucket('LED Studio | Flangia up')
    down_bucket = role_bucket('LED Studio | Flangia down')
    if self.bobina == 'NONE':
        set_socket(obj, 'Flangia up', None)
        set_socket(obj, 'Flangia down', None)
        settings.status = ''
        return
    rel = '//bobine/' + self.bobina
    if not os.path.isfile(bpy.path.abspath(rel)):
        settings.status = 'File mancante: ' + self.bobina
        return
    try:
        vis_meshes, cols = link_blend_assets(rel)
    except Exception as exc:
        settings.status = str(exc)
        return
    vis_set = set(vis_meshes)
    found = {'up': [], 'down': []}
    for col in cols:
        for wanted in ('up', 'down'):
            if not found[wanted] and same_object(wanted, col.name):
                col_vis = [o for o in col.all_objects if o in vis_set]
                if not col_vis:
                    col_vis = [o for o in col.all_objects if is_renderable_mesh(o)]
                found[wanted] = col_vis
    for wanted in ('up', 'down'):
        if not found[wanted]:
            for piece in vis_meshes:
                if same_object(wanted, piece.name):
                    found[wanted].append(piece)
    missing = [name for name in ('up', 'down') if not found[name]]
    if missing:
        settings.status = 'Nel file manca la collection (o mesh): ' + ', '.join(missing)
        return
    # Ensure physical Z side matches up (+Z) and down (-Z) even if swapped in source file
    deps = bpy.context.evaluated_depsgraph_get()
    def mean_z(pieces):
        zs = []
        for p_obj in pieces:
            ev = p_obj.evaluated_get(deps)
            me = ev.to_mesh()
            if len(me.vertices):
                pts = [p_obj.matrix_world @ v.co for v in me.vertices]
                zs.append(0.5 * (min(p.z for p in pts) + max(p.z for p in pts)))
            ev.to_mesh_clear()
        return sum(zs) / len(zs) if zs else 0.0
    if mean_z(found['up']) < mean_z(found['down']) - 1e-5:
        found['up'], found['down'] = found['down'], found['up']
    bake_finished_mesh(found['up'], up_bucket, 'Flangia up', slice_step=None)
    bake_finished_mesh(found['down'], down_bucket, 'Flangia down', slice_step=None)
    set_socket(obj, 'Flangia up', up_bucket)
    set_socket(obj, 'Flangia down', down_bucket)
    settings.status = ''


def update_pcb(self, context):
    obj = self.id_data
    settings = obj.led_studio
    pcb_bucket = role_bucket('LED Studio | Modulo PCB')
    if self.pcb == 'NONE':
        set_socket(obj, 'Modulo PCB', None)
        settings.status = ''
        return
    rel = '//pcb/' + self.pcb
    if not os.path.isfile(bpy.path.abspath(rel)):
        settings.status = 'File mancante: ' + self.pcb
        return
    try:
        vis_meshes, _cols = link_blend_assets(rel)
    except Exception as exc:
        settings.status = str(exc)
        return
    if not vis_meshes:
        settings.status = 'Nessuna mesh visibile nel file: ' + self.pcb
        return
    baked = bake_finished_mesh(vis_meshes, pcb_bucket, 'PCB', slice_step=.002, align_ends=True)
    if baked is None:
        settings.status = 'Geometria PCB vuota: ' + self.pcb
        return
    set_socket(obj, 'Modulo PCB', pcb_bucket)
    settings.status = ''


def update_cavo(self, context):
    obj = self.id_data
    settings = obj.led_studio
    flex = role_bucket('LED Studio | Cavo flessibile')
    rigid = role_bucket('LED Studio | Cavo rigido')
    if self.cavo == 'NONE':
        set_socket(obj, 'Cavo flessibile', None)
        set_socket(obj, 'Connettore', None)
        settings.status = ''
        return
    rel = '//cavi/' + self.cavo
    if not os.path.isfile(bpy.path.abspath(rel)):
        settings.status = 'File mancante: ' + self.cavo
        return
    try:
        vis_meshes, _cols = link_blend_assets(rel)
    except Exception as exc:
        settings.status = str(exc)
        return
    if not vis_meshes:
        settings.status = 'Nessuna mesh visibile nel file: ' + self.cavo
        return
    step = float(get_socket(obj, 'Passo deformazione cavo', .001) or .001)
    flex_objs = [p for p in vis_meshes if p.get('led_role') != 'connector']
    rigid_objs = [p for p in vis_meshes if p.get('led_role') == 'connector']
    if flex_objs:
        bake_finished_mesh(flex_objs, flex, 'Cavo flessibile', slice_step=max(step, .0004))
    for idx, r_obj in enumerate(rigid_objs):
        bake_finished_mesh([r_obj], rigid, 'Connettore %d' % idx, slice_step=None)
    set_socket(obj, 'Cavo flessibile', flex)
    set_socket(obj, 'Connettore', rigid)
    settings.status = ''


class LED_OT_reload_assets(bpy.types.Operator):
    bl_idname = 'led_studio.reload_assets'
    bl_label = 'Ricarica asset'
    bl_description = 'Rilegge i file .blend scelti e ricalcola modificatori e mesh finite'

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and modifier_of(obj) is not None

    def execute(self, context):
        obj = context.object
        st = obj.led_studio
        for folder, fname in (('bobine', st.bobina), ('pcb', st.pcb), ('cavi', st.cavo)):
            if fname != 'NONE':
                rel = '//' + folder + '/' + fname
                if os.path.isfile(bpy.path.abspath(rel)):
                    link_blend_assets(rel, reload_lib=True)
        if st.bobina != 'NONE':
            st.bobina = st.bobina
        if st.pcb != 'NONE':
            st.pcb = st.pcb
        if st.cavo != 'NONE':
            st.cavo = st.cavo
        return {'FINISHED'}


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
        layout.operator('led_studio.reload_assets', icon='FILE_REFRESH')
        if settings.status:
            layout.label(text=settings.status, icon='ERROR')
        root = bpy.path.abspath('//')
        missing = [name for name in ('bobine', 'pcb', 'cavi') if not os.path.isdir(os.path.join(root, name))]
        if missing:
            layout.label(text='Crea accanto al file: ' + ', '.join(missing) + '.')


def register():
    if not hasattr(bpy.types, 'LED_OT_reload_assets'):
        bpy.utils.register_class(LED_OT_reload_assets)
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
    if hasattr(bpy.types, 'LED_OT_reload_assets'):
        bpy.utils.unregister_class(LED_OT_reload_assets)


register()
'''


README = '''LED STUDIO — PARTENZA RAPIDA

Blender 5.3. Tre scene, dal menu Scene in alto: 8 mm, 10 mm, RGB 12 mm.
Sono preset di inquadratura e di quote della spirale, non prodotti certificati.

1. Le cartelle bobine, pcb e cavi stanno accanto a questo file. Il nome nei menu
   a tendina viene ereditato direttamente dal nome del file .blend.
2. In bobine metti un .blend per modello. Dentro, due collection chiamate up e down
   (con dentro quante mesh vuoi e con qualunque nome), asse Z al centro della bobina.
   Lo script separa i dischi flangia in base ad Altezza bobina.
3. In pcb metti un .blend per codice (es. FN01234.blend o FN04950.blend). Puoi usare
   più oggetti e modificatori (Boolean, Array, Subdivision...): all'importazione
   vengono valutati in una mesh finita suddivisa lungo X, ignorando cutter wireframe
   e collection escluse/nascoste. X è il passo, Z la larghezza, -Y verso l'esterno.
4. In cavi metti un .blend per cavo. Anche qui modificatori e più oggetti sono
   consentiti e consolidati all'importazione. X è la lunghezza: il capo a X minimo
   si attacca alla striscia, il connettore sta verso X massimo.
   Un oggetto con led_role = connector resta rigido; gli altri seguono la curva.
5. Seleziona LED_... Se il pannello non compare, abilita Auto Run Python Scripts
   oppure esegui una volta il testo LED Studio Libreria.
   Nel modificatore Configurazione prodotto scegli Bobina, PCB e poi Cavo.
6. Regola Altezza bobina, i raggi, il passo radiale e l'uscita.
7. F12 per il render; tastierino 0 per la camera.

Le flange non si scalano: si allontanano fino alla luce richiesta.
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

SCRIPT: eseguire scripts/led_starter.py dal Text Editor crea nuove scene, senza
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
    for station in (0, length):
        for i in range(segs):
            ang = 2 * math.pi * i / segs
            verts.append((station, radius * math.cos(ang), radius * math.sin(ang)))
    faces = []
    rings = 2
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
    plug['led_role'] = 'connector'
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


def check_cable(obj):
    """The cable section meets the PCB end face, and the sheath follows the curve."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    for vert in mesh.vertices:
        if not all(math.isfinite(axis) for axis in vert.co):
            ev.to_mesh_clear()
            raise RuntimeError('Coordinate non finite sulla mesh valutata')
    if 'nastro' not in mesh.attributes or 'cavo' not in mesh.attributes or 'origine' not in mesh.attributes or 'tangente' not in mesh.attributes:
        ev.to_mesh_clear()
        raise RuntimeError('Mancano gli attributi di attacco')
    strip = []
    cable = []
    sheath = []
    plug = []
    cable_verts = set()
    sheath_verts = set()
    plug_verts = set()
    for i, vert in enumerate(mesh.vertices):
        if mesh.attributes['nastro'].data[i].value > .5:
            strip.append((mesh.attributes['arco'].data[i].value, vert.co.copy(),
                          mesh.attributes['tangente'].data[i].vector.copy()))
        if mesh.attributes['cavo'].data[i].value > .5:
            origin = mesh.attributes['origine'].data[i].vector.copy()
            placed = vert.co.copy()
            heading = mesh.attributes['tangente'].data[i].vector.copy()
            cable.append((origin, placed, heading))
            cable_verts.add(i)
            if 'ruolo' in mesh.attributes and mesh.attributes['ruolo'].data[i].value == 1:
                plug.append((origin, placed))
                plug_verts.add(i)
            else:
                sheath.append((origin, placed))
                sheath_verts.add(i)
    sheath_faces = 0
    plug_faces = 0
    used_mats = set()
    for poly in mesh.polygons:
        if all(v in sheath_verts for v in poly.vertices):
            sheath_faces += 1
        elif all(v in plug_verts for v in poly.vertices):
            plug_faces += 1
        if any(v in cable_verts for v in poly.vertices) and poly.material_index < len(mesh.materials):
            slot = mesh.materials[poly.material_index]
            if slot:
                used_mats.add(slot.name)
    mats = [slot.name for slot in mesh.materials if slot]
    ev.to_mesh_clear()
    if len(strip) < 8 or len(cable) < 8:
        raise RuntimeError('Il cavo non è in scena: nastro %d, cavo %d' % (len(strip), len(cable)))
    end_arc = max(arc for arc, _co, _tangent in strip)
    end_face = [(co, tangent) for arc, co, tangent in strip if arc > end_arc - .00005]
    min_x = min(origin.x for origin, _co, _tangent in cable)
    start_face = [(co, tangent) for origin, co, tangent in cable if origin.x < min_x + .00005]
    if len(end_face) < 3 or len(start_face) < 3:
        raise RuntimeError('Manca la sezione di attacco')
    end = sum((co for co, _tangent in end_face), Vector()) / len(end_face)
    end_tangent = sum((tangent for _co, tangent in end_face), Vector()).normalized()
    start = sum((co for co, _tangent in start_face), Vector()) / len(start_face)
    start_tangent = sum((tangent for _co, tangent in start_face), Vector()).normalized()
    gap = (start - end).length
    align = end_tangent.dot(start_tangent)
    buckets = {}
    for origin, co in sheath:
        buckets.setdefault(round(origin.x, 4), []).append(co)
    stations = sorted(buckets.items())
    if len(stations) < 20:
        raise RuntimeError('La guaina non è stata infittita: %d sezioni' % len(stations))
    if sheath_faces < (len(stations) - 1) * 8:
        raise RuntimeError('La guaina non ha le facce laterali: %d facce' % sheath_faces)
    centers = []
    for sx, pts in stations:
        ctr = sum(pts, Vector()) / len(pts)
        rad = min((pt - ctr).length for pt in pts)
        if rad < .0004:
            raise RuntimeError('Sezione della guaina collassata a X=%.4f' % sx)
        centers.append((sx, ctr))
    for (x0, c0), (x1, c1) in zip(centers, centers[1:]):
        if (c1 - c0).length < (x1 - x0) * .35:
            raise RuntimeError('Percorso cavo troppo corto: sezioni accumulate a X=%.4f' % x1)
    sheath_hi = stations[-1][0]
    mid_idx = len(centers) // 2
    mid = centers[mid_idx][1]
    far = centers[-1][1]
    chord = far - start
    closest = start + chord * ((mid - start).dot(chord) / chord.length_squared)
    bow = (mid - closest).length
    rigid = 0.0
    plug_joint = 0.0
    if len(plug) >= 4:
        for i in range(len(plug)):
            for j in range(i + 1, len(plug)):
                rigid = max(rigid, abs((plug[i][1] - plug[j][1]).length - (plug[i][0] - plug[j][0]).length))
        inlet_x = min(origin.x for origin, _co in plug)
        inlet_pts = [co for origin, co in plug if origin.x < inlet_x + .00005]
        if inlet_pts:
            plug_joint = (sum(inlet_pts, Vector()) / len(inlet_pts) - far).length
    flex_len = sheath_hi - min_x
    print(
        'LED_CHECK cavo blender %s | pcb %.4f m P_pcb (%.4f, %.4f, %.4f) | flex %.4f m P_cavo (%.4f, %.4f, %.4f) | '
        'gap %.5f mm | dot %.5f | freccia %.4f m | sezioni %d | facce_guaina %d | flex_v %d | rigidi_v %d facce_conn %d | '
        'innesto_conn %.5f mm | deform_conn %.5f mm' % (
            '.'.join(str(n) for n in bpy.app.version), end_arc, end.x, end.y, end.z,
            flex_len, start.x, start.y, start.z, gap * 1000, align, bow,
            len(stations), sheath_faces, len(sheath), len(plug), plug_faces,
            plug_joint * 1000, rigid * 1000))
    print('LED_CHECK materiali cavo', ', '.join(sorted(used_mats)))
    if gap > .0001:
        raise RuntimeError('Attacco del cavo staccato: %.4f mm' % (gap * 1000))
    if align < .999:
        raise RuntimeError('Il cavo non segue la tangente della striscia: %.4f' % align)
    if bow < .001:
        raise RuntimeError('La guaina non segue la curva: freccia %.4f mm' % (bow * 1000))
    if len(plug) < 8 or plug_faces < 6:
        raise RuntimeError('Manca il connettore')
    if rigid > .0001:
        raise RuntimeError('Il connettore si è deformato: %.4f mm' % (rigid * 1000))
    if plug_joint > .0001:
        raise RuntimeError('Connettore staccato dalla guaina: %.4f mm' % (plug_joint * 1000))
    if not any('test cavo' in name for name in used_mats) or not any('connettore' in name for name in used_mats):
        raise RuntimeError('Materiali del cavo non conservati sulle facce: ' + ', '.join(mats))


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
    pcb = make_pcb_piece('modulo_generico', pcb_mat)
    cable = make_cable('collection_qualsiasi', cable_mat, plug_mat)
    up.data.materials.append(mat)
    bobina_col = bpy.data.collections.new('gruppo_bobina')
    bobina_col.objects.link(up)
    bobina_col.objects.link(down)
    bobina_path = os.path.join(temp, 'bobine', 'bobina bianca.blend')
    pcb_path = os.path.join(temp, 'pcb', 'FN01234.blend')
    cable_path = os.path.join(temp, 'cavi', 'cavo bianco.blend')
    bpy.data.libraries.write(bobina_path, {bobina_col, up, up.data, down, down.data, mat}, fake_user=True)
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
    bpy.data.collections.remove(bobina_col)
    for piece in list(cable.objects):
        data = piece.data
        bpy.data.objects.remove(piece, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    bpy.data.collections.remove(cable)
    # Second synthetic library: collection-based bobina with inner hub collars + swapped Z,
    # and a 12 cm coarse PCB with Boolean + WIRE cutter + excluded HIDE collection + Array.
    reel_sc = bpy.data.scenes.new('SrcBobina')
    col_up = bpy.data.collections.new('up')
    col_dn = bpy.data.collections.new('down')
    reel_sc.collection.children.link(col_up)
    reel_sc.collection.children.link(col_dn)
    # Intentionally put UP at -Z and DOWN.001 at +Z with 7mm inner collars like FN04950
    f_up = make_box('UP', (.22, .22, .002), (0, 0, -.001))
    c_up = make_box('COLLAR_A', (.05, .05, .007), (0, 0, -.0055))
    f_dn = make_box('DOWN.001', (.22, .22, .002), (0, 0, .001))
    c_dn = make_box('COLLAR_B', (.05, .05, .007), (0, 0, .0055))
    f_up.data.materials.append(mat)
    f_dn.data.materials.append(mat)
    col_up.objects.link(f_up)
    col_up.objects.link(c_up)
    col_dn.objects.link(f_dn)
    col_dn.objects.link(c_dn)
    bobina2_path = os.path.join(temp, 'bobine', 'bobina_col.blend')
    bpy.data.libraries.write(bobina2_path, {reel_sc, col_up, col_dn, f_up, f_up.data, c_up, c_up.data,
                                            f_dn, f_dn.data, c_dn, c_dn.data, mat}, fake_user=True)

    pcb_sc = bpy.data.scenes.new('SrcPcb')
    col_pcb = bpy.data.collections.new('Modello PCB')
    col_cut = bpy.data.collections.new('Cutters')
    col_hide = bpy.data.collections.new('HIDE')
    pcb_sc.collection.children.link(col_pcb)
    pcb_sc.collection.children.link(col_cut)
    pcb_sc.collection.children.link(col_hide)
    prev_sc = bpy.context.window.scene
    bpy.context.window.scene = pcb_sc
    for ch_lc in pcb_sc.view_layers[0].layer_collection.children:
        if ch_lc.name == 'HIDE':
            ch_lc.exclude = True
    bpy.context.window.scene = prev_sc
    long_base = make_box('Base Lunga', (.12, .001, .010), (0, 0, 0))
    long_base.data.materials.append(pcb_mat)
    cutter = make_box('Foro Cutter', (.01, .02, .004), (0, 0, 0))
    cutter.display_type = 'WIRE'
    cutter.hide_render = True
    bmod = long_base.modifiers.new('Boolean', 'BOOLEAN')
    bmod.operation = 'DIFFERENCE'
    bmod.object = cutter
    chip = make_box('Chip LED', (.002, .001, .002), (-.04, -.001, 0))
    chip.data.materials.append(pcb_mat)
    amod = chip.modifiers.new('Array', 'ARRAY')
    amod.count = 4
    amod.relative_offset_displace = (8.0, 0.0, 0.0)
    ghost = make_box('Fantasma HIDE', (.12, .05, .05), (0, -.04, 0))
    col_pcb.objects.link(long_base)
    col_pcb.objects.link(chip)
    col_cut.objects.link(cutter)
    col_hide.objects.link(ghost)
    pcb2_path = os.path.join(temp, 'pcb', 'FN_MODS.blend')
    bpy.data.libraries.write(pcb2_path, {pcb_sc, col_pcb, col_cut, col_hide, long_base, long_base.data,
                                         cutter, cutter.data, chip, chip.data, ghost, ghost.data, pcb_mat},
                             fake_user=True)

    for tmp_obj in (f_up, c_up, f_dn, c_dn, long_base, cutter, chip, ghost):
        d = tmp_obj.data
        bpy.data.objects.remove(tmp_obj, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    for tmp_col in (col_up, col_dn, col_pcb, col_cut, col_hide):
        bpy.data.collections.remove(tmp_col)
    bpy.data.scenes.remove(reel_sc)
    bpy.data.scenes.remove(pcb_sc)
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
        for height in (.010, .020, .028):
            set_input(mod, 'Altezza bobina', height)
            print('LED_CHECK altezza', height)
            check_cable(obj)
        set_input(mod, 'Altezza bobina', .010)
        set_input(mod, 'Giri uscita', 1.15)
        set_input(mod, 'Apertura uscita', .05)
        set_input(mod, 'Raggio avvolgimento', .092)
        print('LED_CHECK variazione spirale')
        check_cable(obj)
        obj.led_studio.cavo = 'NONE'
        if obj.led_studio.status:
            raise RuntimeError(obj.led_studio.status)
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(deps)
        bare = ev.to_mesh()
        left = sum(1 for item in bare.attributes['cavo'].data if item.value > .5) if 'cavo' in bare.attributes else 0
        ev.to_mesh_clear()
        if left:
            raise RuntimeError('Il cavo resta in scena dopo la rimozione: %d' % left)
        print('LED_CHECK senza cavo')
        obj.led_studio.pcb = 'NONE'
        bpy.context.view_layer.update()
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        reel_only = ev.to_mesh()
        strip_left = sum(1 for item in reel_only.attributes['nastro'].data if item.value > .5) if 'nastro' in reel_only.attributes else 0
        ev.to_mesh_clear()
        if strip_left:
            raise RuntimeError('La striscia resta in scena senza PCB: %d' % strip_left)
        print('LED_CHECK senza pcb')

        # Exercise collection-based bobina (with collars + swapped Z) and modifier/cutter PCB
        set_input(mod, 'Altezza bobina', .016)
        set_input(mod, 'Raggio mozzo', .028)
        set_input(mod, 'Raggio avvolgimento', .082)
        set_input(mod, 'Passo radiale', .003)
        obj.led_studio.bobina = 'bobina_col.blend'
        obj.led_studio.pcb = 'FN_MODS.blend'
        if obj.led_studio.status:
            raise RuntimeError('Errore su bobina_col / FN_MODS: ' + obj.led_studio.status)
        bpy.context.view_layer.update()
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        m_mod = ev.to_mesh()
        disk_zs = [v.co.z for v in m_mod.vertices if math.hypot(v.co.x, v.co.y) > .09]
        if not disk_zs or abs(min(disk_zs) - (-.010)) > .0005 or abs(max(disk_zs) - .010) > .0005:
            ev.to_mesh_clear()
            raise RuntimeError('Le flange con colletto non hanno rispettato Altezza bobina: %s' %
                               ((min(disk_zs), max(disk_zs)) if disk_zs else None))
        strip_ids = {i for i, v in enumerate(m_mod.vertices) if m_mod.attributes['nastro'].data[i].value > .5}
        strip_rs = [math.hypot(m_mod.vertices[i].co.x, m_mod.vertices[i].co.y) for i in strip_ids]
        max_s_edge = max((m_mod.vertices[e.vertices[1]].co - m_mod.vertices[e.vertices[0]].co).length
                         for e in m_mod.edges if e.vertices[0] in strip_ids and e.vertices[1] in strip_ids)
        strip_zs = (min(m_mod.vertices[i].co.z for i in strip_ids), max(m_mod.vertices[i].co.z for i in strip_ids))
        ev.to_mesh_clear()
        if min(strip_rs) < .026:
            raise RuntimeError('Corde nel foro del mozzo: min_r %.4f m' % min(strip_rs))
        if max_s_edge > .012:
            raise RuntimeError('Modulo lungo non suddiviso lungo X: max_edge %.4f m' % max_s_edge)
        if strip_zs[0] < -.008 or strip_zs[1] > .008:
            raise RuntimeError('Oggetti HIDE o Cutter entrati nella striscia: Z=%s' % (strip_zs,))
        print('LED_CHECK bobina_col + FN_MODS ok | min_r %.4f m | max_edge %.4f m | disk_z (%.4f, %.4f)' % (
            min(strip_rs), max_s_edge, min(disk_zs), max(disk_zs)))
    finally:
        if obj.led_studio.bobina != 'NONE':
            obj.led_studio.bobina = 'NONE'
        if obj.led_studio.pcb != 'NONE':
            obj.led_studio.pcb = 'NONE'
        if obj.led_studio.cavo != 'NONE':
            obj.led_studio.cavo = 'NONE'
        for piece in list(bpy.data.objects):
            if piece.name.startswith('LED Studio | Consolidato '):
                d = piece.data
                bpy.data.objects.remove(piece, do_unlink=True)
                if d is not None and d.users == 0:
                    bpy.data.meshes.remove(d)
        for bucket_name in ('LED Studio | Flangia up', 'LED Studio | Flangia down',
                            'LED Studio | Modulo PCB', 'LED Studio | Cavo flessibile',
                            'LED Studio | Cavo rigido'):
            bucket = bpy.data.collections.get(bucket_name)
            if bucket:
                for piece in list(bucket.objects):
                    bucket.objects.unlink(piece)
                for parent in bpy.data.collections:
                    if parent.library is None and bucket.name in parent.children:
                        parent.children.unlink(bucket)
                bpy.data.collections.remove(bucket)
        col = bpy.data.collections.get('LED Studio | Libreria')
        if col:
            for piece in list(col.objects):
                col.objects.unlink(piece)
            for child in list(col.children):
                col.children.unlink(child)
            for scene_ in bpy.data.scenes:
                if scene_.library is None and col.name in scene_.collection.children:
                    scene_.collection.children.unlink(col)
            bpy.data.collections.remove(col)
        for sc_linked in list(bpy.data.scenes):
            if sc_linked.library is not None:
                bpy.data.scenes.remove(sc_linked)
        for col_linked in list(bpy.data.collections):
            if col_linked.library is not None:
                for parent in bpy.data.collections:
                    if parent.library is None and col_linked.name in parent.children:
                        parent.children.unlink(col_linked)
                bpy.data.collections.remove(col_linked)
        for piece in list(bpy.data.objects):
            if piece.library is not None:
                bpy.data.objects.remove(piece, do_unlink=True)
        for collection in (bpy.data.meshes, bpy.data.materials):
            for block in list(collection):
                if block.library is not None and block.users == 0:
                    collection.remove(block)
        for lib in list(bpy.data.libraries):
            bpy.data.libraries.remove(lib)
        for name in ('test mozzo', 'test base pcb', 'test cavo', 'test cavo connettore'):
            local = bpy.data.materials.get(PREFIX + ' | ' + name)
            if local and local.users == 0:
                bpy.data.materials.remove(local)
        for reset_name, reset_val in (('Altezza bobina', .014), ('Raggio mozzo', .026),
                                      ('Giri uscita', .83), ('Apertura uscita', .035),
                                      ('Raggio avvolgimento', .078), ('Passo radiale', .002)):
            set_input(obj.modifiers['Configurazione prodotto'], reset_name, reset_val)
        for name, value in values.items():
            set_input(obj.modifiers['Configurazione prodotto'], name, value)
        shutil.rmtree(temp, ignore_errors=True)


def upgrade_inplace():
    """Rebuild the five Geometry Nodes groups and panel text without touching scenes, lights or cameras."""
    if bpy.app.version < (5, 3, 0):
        raise RuntimeError('LED Studio richiede Blender 5.3 o successivo.')
    saved = []
    for obj in bpy.data.objects:
        mod = obj.modifiers.get('Configurazione prodotto')
        if mod is None or mod.type != 'NODES' or mod.node_group is None:
            continue
        numeric = {}
        for item in mod.node_group.interface.items_tree:
            if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.socket_type in ('NodeSocketFloat', 'NodeSocketInt', 'NodeSocketBool'):
                val = mod.properties.inputs[item.identifier].get('value')
                if val is not None:
                    numeric[item.name] = val
        saved.append((obj, mod, numeric))
    old_groups = [g for g in bpy.data.node_groups if g.name.startswith('LED | ')]
    for obj, mod, _numeric in saved:
        mod.node_group = None
    for old in old_groups:
        old.asset_clear()
        old.use_fake_user = False
        bpy.data.node_groups.remove(old)
    path = build_path()
    strip = build_strip()
    reel = build_reel()
    cable = build_cable()
    master = build_master(path, strip, reel, cable)
    for obj, mod, numeric in saved:
        mod.node_group = master
        for name, val in numeric.items():
            try:
                set_input(mod, name, val)
            except KeyError:
                pass
    replace_text('LEGGIMI - LED Studio', README)
    replace_text('LED Studio Libreria', PANEL_SOURCE, module=True)
    load_panel()
    for obj, _mod, _numeric in saved:
        if hasattr(obj, 'led_studio'):
            if obj.led_studio.bobina != 'NONE':
                obj.led_studio.bobina = obj.led_studio.bobina
            if obj.led_studio.pcb != 'NONE':
                obj.led_studio.pcb = obj.led_studio.pcb
            if obj.led_studio.cavo != 'NONE':
                obj.led_studio.cavo = obj.led_studio.cavo
    bpy.ops.wm.save_mainfile()
    print('LED Studio: nodi e pannello aggiornati in-place (%d oggetti preservati).' % len(saved))


def main():
    if '--' in sys.argv and '--upgrade-inplace' in sys.argv[sys.argv.index('--') + 1:]:
        upgrade_inplace()
        return
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
        if zs:
            raise RuntimeError('Geometria non vuota senza asset scelti: ' + scene.name)
        print('LED_CHECK', scene.name, 'vertices', len(zs))
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
