"""Renders of the NOVA Rev B assembly (pyvista, off-screen). Run: xvfb-run -a python3 render_all.py [views...]"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pyvista as pv
import cadquery as cq
import assembly as AS
from dims import *

pv.OFF_SCREEN = True
OUT = AS.OUT

def walk(asm):
    """Flatten an Assembly into [(Shape located in world, (r, g, b), name)]."""
    return [(s, c.toTuple()[:3] if c is not None else (0.6, 0.6, 0.6), n) for s, c, n in AS.flatten(asm)]

def mesh(shape, tol=0.08, ang=0.35):
    try:
        vs, tris = shape.tessellate(tol, ang)
    except Exception:
        return None
    if not tris:
        return None
    pts = np.array([(v.x, v.y, v.z) for v in vs], dtype=float)
    faces = np.hstack([[3, *t] for t in tris]).astype(np.int64)
    return pv.PolyData(pts, faces)

def scene(items, path, view, size=(1800, 1350), zoom=1.0, opacity=None, title=None, edges=True):
    p = pv.Plotter(off_screen=True, window_size=size)
    p.set_background('white', top='#e9eef5')
    for shp, col, nm in items:
        m = mesh(shp)
        if m is None:
            continue
        op = opacity.get(nm, 1.0) if opacity else 1.0
        p.add_mesh(m, color=col, opacity=op, smooth_shading=True, specular=0.3, specular_power=25)
        if edges and op > 0.5:
            fe = m.extract_feature_edges(feature_angle=40, boundary_edges=False, non_manifold_edges=False, manifold_edges=False)
            if fe.n_points:
                p.add_mesh(fe, color='#3a3a3a', line_width=0.8, opacity=0.6)
    p.enable_anti_aliasing('ssaa')
    vv = {'iso': ((1.0, 1.25, 0.8), (0, 0, 1)), 'iso_rear': ((-1.0, -1.25, 0.8), (0, 0, 1)), 'front': ((0, 1, 0.08), (0, 0, 1)),
          'side': ((1, 0, 0.05), (0, 0, 1)), 'top': ((0, 0, 1), (0, 1, 0)), 'under': ((0.6, -0.9, -0.7), (0, 0, 1)),
          'iso_left': ((-1.2, 1.1, 0.8), (0, 0, 1))}[view]
    p.view_vector(vv[0], viewup=vv[1])
    p.reset_camera()
    p.camera.zoom(zoom)
    if title:
        p.add_text(title, position='upper_left', font_size=11, color='#222222')
    p.screenshot(path)
    p.close()
    print('render', path)

# ------------------------------------------------------------------ studio renders (product look)
GLOW = ('halo', 'lcd_eyes', 'dock_lightpipe')
def material(nm, col):
    """pyvista add_mesh kwargs per part: matte white / satin graphite plastics, glossy smoked visor, glowing halo."""
    if nm == 'visor':
        return dict(color=(0.015, 0.02, 0.03), specular=0.9, specular_power=110, diffuse=0.25, ambient=0.05)
    if nm == 'halo':
        return dict(color=(0.55, 0.9, 1.0), ambient=0.8, diffuse=0.3, specular=0.5, specular_power=60)
    if nm in ('lcd_eyes', 'dock_lightpipe', 'face_glow') or nm.startswith('led_'):
        return dict(color=(0.45, 0.95, 1.0), lighting=False)
    if nm in ('shell_upper', 'top_cap', 'dock_tower'):
        return dict(color=(0.92, 0.93, 0.94), ambient=0.18, diffuse=0.85, specular=0.18, specular_power=12)
    if nm in ('shell_skirt', 'dock_base', 'dock_tongue', 'dock_tag_panel'):
        return dict(color=(0.13, 0.14, 0.16), ambient=0.12, diffuse=0.8, specular=0.45, specular_power=35)
    return dict(color=col, specular=0.3, specular_power=25)

def face_glow():
    """The display image seen through the smoked visor (render only): two rounded eyes on the visor face."""
    zl = HEAD_Z0 + HEAD_LCD_ZC + 1.0
    out = []
    for xx in (-11.0, 11.0):
        e = (cq.Workplane('XZ').rect(11.0, 16.0).extrude(-0.05).edges('|Y').fillet(5.0)
             .translate((xx, SHELL_D / 2 + 0.03, zl)))
        out.append((e.val(), (0.45, 0.95, 1.0), 'face_glow'))
    return out

def studio(items, path, eye, focal=None, size=(2000, 1400), zoom=1.0, dark=True, floor_z=None, title=None, floor=True):
    p = pv.Plotter(off_screen=True, window_size=size, lighting='none')
    if dark:
        p.set_background('#06080c', top='#2a3442')
    else:
        p.set_background('#f4f6f9', top='#dfe6ef')
    pts = []
    for shp, col, nm in items:
        m = mesh(shp, tol=0.05, ang=0.25)
        if m is None:
            continue
        pts.append(m.bounds)
        p.add_mesh(m, smooth_shading=True, **material(nm, col))
    b = np.array(pts); lo = b[:, ::2].min(0); hi = b[:, 1::2].max(0); c = (lo + hi) / 2
    R = max(hi - lo)
    if floor_z is None:
        floor_z = float(lo[2])
    if floor:
        _floor(p, c, R, lo, hi, floor_z, dark)
    _lights(p, c, R)
    _camera_shot(p, c, R, eye, focal, zoom, dark, title, path)

def _floor(p, c, R, lo, hi, floor_z, dark):
    floor = pv.Disc(center=(c[0], c[1], floor_z - 0.05), inner=0, outer=R * 4, c_res=120, r_res=8)
    fcol = '#11151b' if dark else '#e8ecf1'
    p.add_mesh(floor, color=fcol, specular=0.5 if dark else 0.1, specular_power=40, ambient=0.2)
    # soft contact shadow under the footprint (render-time ambient occlusion substitute)
    rx, ry = (hi - lo)[0] / 2 * 1.25, (hi - lo)[1] / 2 * 1.25
    sh = pv.Plane(center=(c[0], c[1], floor_z + 0.05), i_size=2 * rx, j_size=2 * ry, i_resolution=200, j_resolution=200)
    q = sh.points
    d = np.sqrt(((q[:, 0] - c[0]) / rx) ** 2 + ((q[:, 1] - c[1]) / ry) ** 2)
    rgba = np.zeros((len(q), 4)); rgba[:, 3] = np.clip(1.15 - d, 0, 1) ** 1.8 * 255 * (0.85 if dark else 0.45)
    p.add_mesh(sh, scalars=rgba.astype(np.uint8), rgba=True, lighting=False, show_scalar_bar=False)

def _lights(p, c, R):
    # three-point lighting: key (warm, front-right high), fill (cool, left), rim (behind)
    key = pv.Light(position=(c[0] + 3 * R, c[1] + 3 * R, c[2] + 4 * R), focal_point=tuple(c), color='#fff6ec', intensity=0.95)
    key.positional = True; key.cone_angle = 40; key.shadow_attenuation = 0.85
    fill = pv.Light(position=(c[0] - 4 * R, c[1] + 1.5 * R, c[2] + 1.5 * R), focal_point=tuple(c), color='#dfeaff', intensity=0.45)
    rim = pv.Light(position=(c[0] - 1.5 * R, c[1] - 4 * R, c[2] + 3 * R), focal_point=tuple(c), color='#cfe6ff', intensity=0.7)
    top = pv.Light(position=(c[0], c[1], c[2] + 6 * R), focal_point=tuple(c), color='white', intensity=0.25)
    for L in (key, fill, rim, top):
        p.add_light(L)

def _camera_shot(p, c, R, eye, focal, zoom, dark, title, path):
    if os.environ.get('NOVA_SHADOWS', '0') == '1':
        try:
            p.enable_shadows()
        except Exception:
            pass
    if os.environ.get('NOVA_SSAO', '0') == '1':
        p.enable_ssao(radius=6.0, bias=0.3, kernel_size=128, blur=True)
    p.enable_anti_aliasing('ssaa')
    focal = tuple(c) if focal is None else focal
    p.camera.focal_point = focal
    e = np.array(eye, float); e = e / np.linalg.norm(e)
    p.camera.position = tuple(np.array(focal) + e * R * 3.2)
    p.camera.up = (0, 0, 1)
    p.camera.view_angle = 26
    p.camera.zoom(zoom)
    if title:
        p.add_text(title, position='lower_left', font_size=10, color='#9fb3c8' if dark else '#445566')
    p.screenshot(path)
    p.close()
    print('studio', path)

if __name__ == '__main__':
    views = sys.argv[1:] or ['hero', 'robot', 'core', 'explode', 'front', 'rear', 'under', 'dock', 'docked']
    if any(v.startswith('hero') for v in views):
        full = walk(AS.build(shell=True)) + face_glow()
        dk = walk(AS.build_dock())
        if 'hero' in views or 'hero1' in views:
            studio(full, f'{OUT}/NOVA_RevB_hero_front.png', (0.75, 1.0, 0.42), zoom=1.15, title='NOVA · Rev B')
        if 'hero' in views or 'hero2' in views:
            studio(full, f'{OUT}/NOVA_RevB_hero_rear.png', (-0.8, -1.0, 0.5), zoom=1.15, title='NOVA · Rev B — rear')
        if 'hero' in views or 'hero3' in views:
            docked = full + dk
            studio(docked, f'{OUT}/NOVA_RevB_hero_docked.png', (0.9, 1.0, 0.45), zoom=1.1, title='NOVA · Rev B — on its dock')
        if 'hero' in views or 'hero4' in views:
            studio(dk, f'{OUT}/NOVA_RevB_hero_dock.png', (0.9, 1.1, 0.6), zoom=1.15, title='NOVA dock')
        if 'hero' in views or 'hero5' in views:
            studio(full, f'{OUT}/NOVA_RevB_hero_face.png', (0.0, 1.0, 0.12), zoom=1.25, title='NOVA · Rev B — face')
        views = [v for v in views if not v.startswith('hero')]
    L = dict(dark=False)
    if any(v in views for v in ('robot', 'front', 'rear', 'under', 'docked')):
        full = walk(AS.build(shell=True)) + face_glow()
    if 'robot' in views:
        studio(full, f'{OUT}/NOVA_RevB_iso.png', (1.0, 1.25, 0.8), zoom=1.2, title='NOVA Rev B', **L)
    if 'front' in views:
        studio(full, f'{OUT}/NOVA_RevB_front.png', (0.0, 1.0, 0.06), zoom=1.25, title='NOVA Rev B — front', **L)
    if 'rear' in views:
        studio(full, f'{OUT}/NOVA_RevB_rear.png', (-1.0, -1.25, 0.8), zoom=1.2, title='NOVA Rev B — rear', **L)
    if 'under' in views:
        studio(full, f'{OUT}/NOVA_RevB_under.png', (0.6, -0.9, -0.7), zoom=1.2, floor=False,
               title='NOVA Rev B — underside (dock contact plate)', **L)
    if 'core' in views:
        core = walk(AS.build(shell=False))
        studio(core, f'{OUT}/NOVA_RevB_core.png', (1.0, 1.25, 0.8), zoom=1.25, title='NOVA Rev B — without the enclosure', **L)
        studio(core, f'{OUT}/NOVA_RevB_core_left.png', (-1.2, 1.1, 0.8), zoom=1.25,
               title='NOVA Rev B — without the enclosure (left)', **L)
    if 'explode' in views:
        ex = walk(AS.build(shell=True, explode=115.0)) + [(s.moved(cq.Location((0, 0, 115.0))), c, n) for s, c, n in face_glow()]
        studio(ex, f'{OUT}/NOVA_RevB_explode.png', (1.0, 1.25, 0.7), zoom=1.05, title='NOVA Rev B — enclosure exploded', **L)
    if 'dock' in views or 'docked' in views:
        dk = walk(AS.build_dock())
        if 'dock' in views:
            studio(dk, f'{OUT}/NOVA_RevB_dock.png', (1.0, 1.25, 0.8), zoom=1.1, title='NOVA dock Rev B', **L)
        if 'docked' in views:
            studio(full + dk, f'{OUT}/NOVA_RevB_docked.png', (-1.0, -1.25, 0.8), zoom=1.1, title='NOVA Rev B — docked', **L)
