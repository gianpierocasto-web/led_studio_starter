"""LED Studio — Geometry Nodes starter, Blender 4.3+. Run from Text Editor.
Creates a NEW scene for each preset. Existing scenes and objects are retained.
CLI: blender -b --python led_starter.py -- --output /absolute/path/LED_Studio.blend
"""
import bpy
import math
import os
import sys
from mathutils import Vector

PREFIX = 'LED Studio'


class Graph:
    def __init__(self, name):
        self.g = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        self.g.is_modifier = True
        self.i = self.node('NodeGroupInput', 'Parametri', -1000, 0)
        self.o = self.node('NodeGroupOutput', 'Risultato', 1600, 0)
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
        self.link(a, n.inputs[0]); self.link(b, n.inputs[1])
        return n.outputs[0]

    def vec(self, x=0, y=0, z=0):
        n = self.node('ShaderNodeCombineXYZ')
        for v, s in zip((x, y, z), n.inputs):
            self.link(v, s)
        return n.outputs[0]

    def transform(self, geo, translation=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
        n = self.node('GeometryNodeTransform')
        for name, value in [('Geometry', geo), ('Translation', translation), ('Rotation', rotation), ('Scale', scale)]:
            self.link(value, n.inputs[name])
        return n.outputs[0]

    def material(self, geo, mat):
        n = self.node('GeometryNodeSetMaterial')
        self.link(geo, n.inputs['Geometry']); self.link(mat, n.inputs['Material'])
        return n.outputs[0]

    def join(self, *geos):
        n = self.node('GeometryNodeJoinGeometry')
        for geo in geos:
            self.link(geo, n.inputs[0])
        return n.outputs[0]

    def cube(self, size, translation=(0, 0, 0)):
        n = self.node('GeometryNodeMeshCube')
        self.link(size, n.inputs['Size'])
        return self.transform(n.outputs['Mesh'], translation)

    def finish(self, geo):
        self.link(geo, self.o.inputs['Geometry'])
        self.g.asset_mark()
        self.g.asset_data.description = 'LED Studio: generatore parametrico in metri, modificabile senza script.'
        return self.g


def make_material(name, color, metallic=0, roughness=.4):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Specular IOR Level'].default_value = .22
    return m


def build_path():
    q = Graph('LED | 01 Percorso spirale e uscita')
    for name, value, lo, hi in [('Raggio mozzo', .026, .012, .08), ('Raggio avvolgimento', .078, .025, .18),
                                ('Passo radiale', .002, .0012, .008), ('Giri uscita', .83, .25, 1.5),
                                ('Apertura uscita', .035, .005, .08)]:
        q.sock(name, default=value, lo=lo, hi=hi)
    p = q.i.outputs
    radius = q.math('MAXIMUM', p['Raggio avvolgimento'], q.math('ADD', p['Raggio mozzo'], .003))
    turns = q.math('FLOOR', q.math('DIVIDE', q.math('SUBTRACT', radius, p['Raggio mozzo']), p['Passo radiale']))
    idx = q.node('GeometryNodeInputIndex').outputs[0]
    t = q.math('MULTIPLY', q.math('DIVIDE', idx, 8191), q.math('ADD', turns, p['Giri uscita']))
    tail = q.math('MAXIMUM', q.math('SUBTRACT', t, turns), 0)
    expansion = q.math('MULTIPLY', p['Apertura uscita'], q.math('POWER', q.math('DIVIDE', tail, p['Giri uscita']), 2))
    r = q.math('ADD', q.math('ADD', p['Raggio mozzo'], q.math('MULTIPLY', t, p['Passo radiale'])), expansion)
    angle = q.math('MULTIPLY', t, 2 * math.pi)
    x = q.math('MULTIPLY', r, q.math('COSINE', angle))
    y = q.math('MULTIPLY', r, q.math('SINE', angle))
    line = q.node('GeometryNodeMeshLine'); line.inputs['Count'].default_value = 8192
    pos = q.node('GeometryNodeSetPosition', 'Spirale planare con uscita continua')
    q.link(line.outputs['Mesh'], pos.inputs['Geometry']); q.link(q.vec(x, y, 0), pos.inputs['Position'])
    cv = q.node('GeometryNodeMeshToCurve'); q.link(pos.outputs[0], cv.inputs['Mesh'])
    return q.finish(cv.outputs[0])


def build_strip():
    q = Graph('LED | 02 PCB e componenti su curva')
    q.sock('Curva', 'NodeSocketGeometry')
    for name, value, lo, hi in [('Larghezza PCB', .01, .005, .025), ('Spessore PCB', .0003, .0001, .001),
                               ('Passo LED', .016667, .008, .04), ('Larghezza LED', .0028, .001, .008),
                               ('Lunghezza LED', .0035, .001, .008)]:
        q.sock(name, default=value, lo=lo, hi=hi)
    for name in ['Materiale PCB', 'Materiale package', 'Materiale fosforo', 'Materiale rame', 'Materiale resistenza']:
        q.sock(name, 'NodeSocketMaterial')
    p = q.i.outputs
    # Planar sweep: profile X is radial; profile Y is vertical.
    profile = q.node('GeometryNodeCurvePrimitiveQuadrilateral', 'Sezione: larghezza verticale')
    profile.mode = 'RECTANGLE'
    q.link(p['Spessore PCB'], profile.inputs['Width'])
    q.link(p['Larghezza PCB'], profile.inputs['Height'])
    sweep = q.node('GeometryNodeCurveToMesh', 'Supporto PCB flessibile')
    q.link(p['Curva'], sweep.inputs['Curve']); q.link(profile.outputs[0], sweep.inputs['Profile Curve'])
    sweep.inputs['Fill Caps'].default_value = True
    support = q.material(sweep.outputs[0], p['Materiale PCB'])
    # Module local axes: X along path, Z across strip, -Y outward.
    package = q.material(q.cube(q.vec(p['Lunghezza LED'], .0007, p['Larghezza LED']), (0, -.0005, 0)), p['Materiale package'])
    phosphor = q.material(q.cube(q.vec(q.math('MULTIPLY', p['Lunghezza LED'], .77), .00012,
                                               q.math('MULTIPLY', p['Larghezza LED'], .74)), (0, -.00091, 0)), p['Materiale fosforo'])
    res = q.material(q.cube((.0018, .00055, .001), q.vec(q.math('MULTIPLY', p['Passo LED'], .46), -.00045, 0)), p['Materiale resistenza'])
    pads = []
    for side in [-1, 1]:
        pads.append(q.material(q.cube((.002, .00008, .0015),
                    q.vec(q.math('MULTIPLY', p['Passo LED'], -.38), -.0002,
                          q.math('MULTIPLY', p['Larghezza PCB'], side * .29))), p['Materiale rame']))
    module = q.join(package, phosphor, res, *pads)
    length = q.node('GeometryNodeCurveLength'); q.link(p['Curva'], length.inputs['Curve'])
    nmodules = q.math('MAXIMUM', q.math('FLOOR', q.math('DIVIDE', length.outputs['Length'], p['Passo LED'])), 2)
    trim = q.node('GeometryNodeTrimCurve'); trim.mode = 'LENGTH'
    q.link(p['Curva'], trim.inputs['Curve'])
    q.link(q.math('MULTIPLY', q.math('SUBTRACT', nmodules, 1), p['Passo LED']),
           next(s for s in trim.inputs if s.name == 'End' and s.enabled))
    points = q.node('GeometryNodeCurveToPoints'); points.mode = 'COUNT'
    q.link(trim.outputs['Curve'], points.inputs['Curve']); q.link(nmodules, points.inputs['Count'])
    align = q.node('FunctionNodeAlignEulerToVector', 'X tangente / Z verticale')
    align.axis = 'X'; align.pivot_axis = 'Z'
    q.link(points.outputs['Tangent'], align.inputs['Vector'])
    inst = q.node('GeometryNodeInstanceOnPoints', 'LED e componenti rigidi')
    q.link(points.outputs['Points'], inst.inputs['Points']); q.link(module, inst.inputs['Instance'])
    q.link(align.outputs['Rotation'], inst.inputs['Rotation'])
    return q.finish(q.join(support, inst.outputs['Instances']))


def build_reel():
    q = Graph('LED | 03 Bobina parametrica')
    for name, value, lo, hi in [('Raggio bobina', .09, .05, .2), ('Raggio mozzo', .026, .012, .08),
                               ('Larghezza PCB', .01, .005, .025)]:
        q.sock(name, default=value, lo=lo, hi=hi)
    q.sock('Numero raggi', 'NodeSocketInt', 5, 3, 12)
    q.sock('Gioco flange', default=.0044, lo=.002, hi=.02,
           description='Spazio aggiuntivo tra flange oltre alla larghezza del PCB, in metri.')
    q.sock('Materiale bobina', 'NodeSocketMaterial')
    p = q.i.outputs
    def ring(radius, radial, height):
        circle = q.node('GeometryNodeCurvePrimitiveCircle'); circle.inputs['Resolution'].default_value = 192
        q.link(radius, circle.inputs['Radius'])
        rect = q.node('GeometryNodeCurvePrimitiveQuadrilateral'); rect.mode = 'RECTANGLE'
        q.link(radial, rect.inputs['Width']); q.link(height, rect.inputs['Height'])
        mesh = q.node('GeometryNodeCurveToMesh')
        q.link(circle.outputs['Curve'], mesh.inputs['Curve']); q.link(rect.outputs[0], mesh.inputs['Profile Curve'])
        return mesh.outputs[0]
    outer = ring(p['Raggio bobina'], .006, .0026)
    inner = ring(p['Raggio mozzo'], .007, .0026)
    mid = q.math('MULTIPLY', q.math('ADD', p['Raggio bobina'], p['Raggio mozzo']), .5)
    spoke_len = q.math('SUBTRACT', p['Raggio bobina'], p['Raggio mozzo'])
    circle = q.node('GeometryNodeCurvePrimitiveCircle'); q.link(mid, circle.inputs['Radius'])
    points = q.node('GeometryNodeCurveToPoints'); points.mode = 'COUNT'
    q.link(circle.outputs[0], points.inputs['Curve']); q.link(p['Numero raggi'], points.inputs['Count'])
    position = q.node('GeometryNodeInputPosition')
    rotation = q.node('FunctionNodeAlignEulerToVector'); rotation.axis = 'X'; rotation.pivot_axis = 'Z'
    q.link(position.outputs[0], rotation.inputs['Vector'])
    spoke = q.cube(q.vec(spoke_len, .009, .0020))
    inst = q.node('GeometryNodeInstanceOnPoints')
    q.link(points.outputs['Points'], inst.inputs['Points']); q.link(spoke, inst.inputs['Instance'])
    q.link(rotation.outputs[0], inst.inputs['Rotation'])
    flange = q.join(outer, inner, inst.outputs[0])
    z = q.math('MULTIPLY', q.math('ADD', p['Larghezza PCB'], p['Gioco flange']), .5)
    upper = q.transform(flange, q.vec(0, 0, z))
    lower = q.transform(flange, q.vec(0, 0, q.math('MULTIPLY', z, -1)))
    hub = ring(q.math('SUBTRACT', p['Raggio mozzo'], .003), .002,
               q.math('ADD', p['Larghezza PCB'], p['Gioco flange']))
    # Realize before assigning material, including spokes.
    real = q.node('GeometryNodeRealizeInstances'); q.link(q.join(upper, lower, hub), real.inputs[0])
    return q.finish(q.material(real.outputs[0], p['Materiale bobina']))


def build_master(path, strip, reel):
    q = Graph('LED | 00 Prodotto completo')
    definitions = [('Raggio bobina', .09, .05, .2), ('Raggio mozzo', .026, .012, .08),
                   ('Raggio avvolgimento', .078, .025, .18), ('Passo radiale', .002, .0012, .008),
                   ('Larghezza PCB', .01, .005, .025), ('Spessore PCB', .0003, .0001, .001),
                   ('Passo LED', .016667, .008, .04), ('Larghezza LED', .0028, .001, .008),
                   ('Lunghezza LED', .0035, .001, .008), ('Giri uscita', .83, .25, 1.5),
                   ('Apertura uscita', .035, .005, .08)]
    for name, default, lo, hi in definitions:
        q.sock(name, default=default, lo=lo, hi=hi)
    q.sock('Numero raggi', 'NodeSocketInt', 5, 3, 12)
    q.sock('Gioco flange', default=.0044, lo=.002, hi=.02,
           description='Aumenta l’altezza della bobina senza cambiare la larghezza PCB.')
    for name in ['Materiale PCB', 'Materiale package', 'Materiale fosforo', 'Materiale rame', 'Materiale resistenza', 'Materiale bobina']:
        q.sock(name, 'NodeSocketMaterial')
    pathnode = q.node('GeometryNodeGroup', '01 Percorso'); pathnode.node_tree = path
    stripnode = q.node('GeometryNodeGroup', '02 Striscia'); stripnode.node_tree = strip
    reelnode = q.node('GeometryNodeGroup', '03 Bobina'); reelnode.node_tree = reel
    for node in (pathnode, stripnode, reelnode):
        for socket in node.inputs:
            if socket.name in q.i.outputs:
                q.link(q.i.outputs[socket.name], socket)
    q.link(pathnode.outputs[0], stripnode.inputs['Curva'])
    return q.finish(q.join(stripnode.outputs[0], reelnode.outputs[0]))


def set_input(modifier, name, value):
    for s in modifier.node_group.interface.items_tree:
        if s.item_type == 'SOCKET' and s.in_out == 'INPUT' and s.name == name:
            modifier[s.identifier] = value
            return
    raise KeyError(name)


PRESETS = [
    ('01_Bianco_8mm', {'Larghezza PCB': .008, 'Passo LED': 1 / 120, 'Larghezza LED': .0028,
                     'Lunghezza LED': .0035, 'Numero raggi': 5, 'Passo radiale': .0018}, 'bianco', 'nero'),
    ('02_Caldo_10mm', {'Larghezza PCB': .010, 'Passo LED': 1 / 60, 'Larghezza LED': .0028,
                     'Lunghezza LED': .0035, 'Numero raggi': 5}, 'caldo', 'nero'),
    ('03_RGB_12mm', {'Larghezza PCB': .012, 'Passo LED': 1 / 60, 'Larghezza LED': .005,
                   'Lunghezza LED': .005, 'Numero raggi': 6, 'Raggio bobina': .098,
                   'Raggio avvolgimento': .084, 'Passo radiale': .0023}, 'rgb', 'grigio'),
]


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def setup_scene(name, group, values, mats, ledmat, reelmat):
    scene = bpy.data.scenes.new(PREFIX + ' | ' + name)
    scene.unit_settings.system = 'METRIC'; scene.unit_settings.length_unit = 'MILLIMETERS'
    root = bpy.data.collections.new('Prodotto | ' + name); scene.collection.children.link(root)
    mesh = bpy.data.meshes.new('Supporto generatore')
    obj = bpy.data.objects.new('LED_' + name, mesh); root.objects.link(obj)
    mod = obj.modifiers.new('Configurazione prodotto', 'NODES'); mod.node_group = group
    material_values = {'Materiale PCB': mats['pcb'], 'Materiale package': mats['package'],
                       'Materiale fosforo': mats[ledmat], 'Materiale rame': mats['rame'],
                       'Materiale resistenza': mats['resistenza'], 'Materiale bobina': mats[reelmat]}
    for k, v in {**values, **material_values}.items():
        set_input(mod, k, v)
    obj.location.z = .019
    bevel = obj.modifiers.new('Bordi bobina e PCB', 'BEVEL'); bevel.width = .00035; bevel.segments = 2
    # Instances remain instances; bevel affects the realized bobina and PCB only.
    stage = bpy.data.collections.new('Studio | ' + name); scene.collection.children.link(stage)
    floor_mesh = bpy.data.meshes.new('Fondo'); floor_mesh.from_pydata([(-2,-2,0),(2,-2,0),(2,2,0),(-2,2,0)], [], [(0,1,2,3)])
    floor = bpy.data.objects.new('Fondo bianco', floor_mesh); stage.objects.link(floor); floor.data.materials.append(mats['fondo'])
    camera = bpy.data.objects.new('Camera catalogo', bpy.data.cameras.new('Camera catalogo'))
    stage.objects.link(camera); camera.location = (.27, -.40, .29); look_at(camera, (0, 0, .015))
    camera.data.type = 'ORTHO'; camera.data.ortho_scale = .32; camera.data.lens = 50; scene.camera = camera
    for title, location, power, size in [('Key', (.12,-.18,.38), 3, .27), ('Fill', (-.25,-.05,.22), 2, .22), ('Rim', (.05,.24,.28), 3, .20)]:
        light = bpy.data.objects.new(title, bpy.data.lights.new(title, 'AREA'))
        stage.objects.link(light); light.location = location; light.data.energy = power; light.data.shape = 'DISK'; light.data.size = size; look_at(light, (0,0,0))
    world = bpy.data.worlds.new('Studio bianco'); world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (.8,.8,.8,1)
    world.node_tree.nodes['Background'].inputs[1].default_value = .20; scene.world = world
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 64; scene.cycles.use_denoising = False
    scene.render.resolution_x = 1400; scene.render.resolution_y = 1100; scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'; scene.render.filepath = '//renders/' + name + '.png'
    scene.view_settings.view_transform = 'AgX'
    scene['NOTE'] = 'Preset dimostrativo. Quote in metri nei nodi. Nessuna lunghezza commerciale garantita.'
    scene.view_layers[0].objects.active = obj
    obj.select_set(True, view_layer=scene.view_layers[0])
    return scene, obj


README = '''LED STUDIO — PARTENZA RAPIDA

Blender 4.3.2: file generato e controllato. Usare Blender 4.3 o successivo.
Tre scene, selezionabili dal menu Scene in alto: 8 mm, 10 mm, RGB 12 mm.
Le denominazioni sono preset geometrici dimostrativi, non prodotti certificati.

1. Seleziona LED_... nell'Outliner della scena corrente.
2. Modificatori > Configurazione prodotto: cambia quote, materiali e numero raggi.
3. F12 per il render; tastierino 0 per la camera.
4. Workspace Geometry Nodes: scegli il modificatore Configurazione prodotto.

Gruppi disponibili e marcati come asset:
00 Prodotto completo; 01 Percorso spirale e uscita;
02 PCB e componenti su curva; 03 Bobina parametrica.

IMPORTAZIONE: File > Append > LED_Studio.blend > Collection > Prodotto | ...
Importa la sola collezione prodotto: nodi e materiali collegati sono inclusi.
Per usare il generatore da zero su una mesh, aggiungi un modificatore Geometry
Nodes e scegli LED | 00 Prodotto completo, poi assegna i materiali nei socket.

QUOTE: valori numerici in metri: 0.008 = 8 mm. La larghezza si sviluppa
verticalmente fra le flange. Passo radiale = distanza fra spire, non larghezza.
Mantieni Raggio mozzo < Raggio avvolgimento < Raggio bobina - 0.005.
Il generatore arrotonda i giri interni per ottenere un'uscita ripetibile.
Gioco flange aumenta l'altezza della bobina senza allargare il PCB.
Giri uscita / Apertura uscita controllano il tratto libero.
Un avvolgimento troppo fitto può intersecare i componenti: controlla il passo.
Non interpreta una lunghezza commerciale esatta: e' un avvolgimento illustrativo.

Il preset RGB usa un package quadrato con finestra scura: non e' un circuito
elettronico RGB completo. Componenti e contatti sono rappresentativi.
Nessun testo, logo, liner adesivo, cavo o guaina impermeabile incluso.
Il dettaglio frontale inferiore della foto non viene composto automaticamente.
Il gruppo 02 puo' essere riutilizzato su una curva diritta per produrlo.

PERSONALIZZAZIONE: il gruppo 02 contiene i blocchi package, fosforo,
resistenza e contatti; sostituiscili con i tuoi componenti. I materiali sono
gia' separati. La bobina di base ha flange ad anello e raggi modificabili.
I gruppi condivisi aggiornano tutte le scene; i valori dei modificatori sono
indipendenti. Duplica un gruppo prima di cambiarne la struttura per un prodotto.

SCRIPT: eseguire led_starter.py dal Text Editor crea nuove scene, senza
cancellare quelle esistenti. Ripetere lo script crea altre copie, non aggiorna.
La scena originale rimane disponibile. Lo script non salva automaticamente
il progetto aperto; salva una copia manualmente dopo averlo eseguito.
'''


def main():
    if bpy.app.version < (4, 3, 0):
        raise RuntimeError('LED Studio richiede Blender 4.3 o successivo.')
    mats = {key: make_material('LED | ' + key, color, metal, rough) for key, color, metal, rough in [
        ('pcb',(.88,.89,.84),0,.42), ('package',(.8,.81,.75),0,.3),
        ('bianco',(.95,.72,.13),0,.34), ('caldo',(.95,.49,.055),0,.34), ('rgb',(.12,.14,.16),.15,.22),
        ('rame',(.64,.29,.07),.75,.3), ('resistenza',(.018,.02,.022),0,.36),
        ('nero',(.012,.014,.017),0,.3), ('grigio',(.45,.48,.50),0,.33), ('fondo',(1,1,1),0,.7) ]}
    path = build_path(); strip = build_strip(); reel = build_reel(); master = build_master(path, strip, reel)
    built = [setup_scene(name, master, vals, mats, ledmat, reelmat) for name, vals, ledmat, reelmat in PRESETS]
    bpy.context.window.scene = built[1][0]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.color_type = 'MATERIAL'
            elif area.type == 'PROPERTIES':
                area.spaces.active.context = 'MODIFIER'
    text = bpy.data.texts.new('LEGGIMI - LED Studio'); text.write(README)
    for scene, obj in built:
        bpy.context.window.scene = scene
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = ev.to_mesh()
        if not mesh.vertices:
            raise RuntimeError('Geometria vuota: ' + scene.name)
        coords = [v.co for v in mesh.vertices]
        bounds = [(min(v[i] for v in coords), max(v[i] for v in coords)) for i in range(3)]
        print('LED_CHECK', scene.name, 'vertices', len(mesh.vertices), 'bounds', bounds)
        ev.to_mesh_clear()
    bpy.context.window.scene = built[1][0]
    if '--' in sys.argv:
        args = sys.argv[sys.argv.index('--') + 1:]
        if '--output' in args:
            target = os.path.abspath(args[args.index('--output') + 1])
            bpy.ops.wm.save_as_mainfile(filepath=target)
    print('LED Studio: pronto. Tre preset, quattro gruppi Geometry Nodes.')


if __name__ == '__main__':
    main()
