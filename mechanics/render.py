"""Off-screen renders of CadQuery parts with pyvista (run under xvfb-run)."""
import numpy as np
import pyvista as pv

pv.OFF_SCREEN = True

def to_mesh(shape, tol=0.08, ang=0.3):
    obj = shape.val() if hasattr(shape, 'val') else shape
    try:
        vs, tris = obj.tessellate(tol, ang)
    except Exception:
        return None
    if not tris:
        return None
    pts = np.array([(v.x, v.y, v.z) for v in vs], dtype=float)
    faces = np.hstack([[3, *t] for t in tris]).astype(np.int64)
    return pv.PolyData(pts, faces)

def render(parts, path, view='iso', size=(1600, 1200), bg='white', zoom=1.0, edges=False, title=None, parallel=False,
           focus=None, cam=None):
    """parts: list of (shape, rgb, opacity)."""
    p = pv.Plotter(off_screen=True, window_size=size)
    p.set_background(bg)
    for shape, col, op in parts:
        m = to_mesh(shape)
        if m is None:
            continue
        p.add_mesh(m, color=col, opacity=op, smooth_shading=True, show_edges=False, specular=0.25, specular_power=20)
        if edges:
            fe = m.extract_feature_edges(feature_angle=35, boundary_edges=True, non_manifold_edges=False, manifold_edges=False)
            if fe.n_points:
                p.add_mesh(fe, color='#333333', line_width=1.0, opacity=min(1.0, op + 0.2))
    p.enable_anti_aliasing('ssaa')
    if parallel:
        p.enable_parallel_projection()
    if cam is not None:
        p.camera_position = cam
    elif view == 'iso':
        p.view_vector((1.1, 1.3, 0.85), viewup=(0, 0, 1))
    elif view == 'iso_rear':
        p.view_vector((-1.1, -1.3, 0.85), viewup=(0, 0, 1))
    elif view == 'front':
        p.view_vector((0, 1, 0), viewup=(0, 0, 1))
    elif view == 'side':
        p.view_vector((1, 0, 0), viewup=(0, 0, 1))
    elif view == 'top':
        p.view_vector((0, 0, 1), viewup=(0, 1, 0))
    elif view == 'bottom':
        p.view_vector((0, 0, -1), viewup=(0, 1, 0))
    p.reset_camera()
    if focus is not None:
        p.set_focus(focus)
    p.camera.zoom(zoom)
    if title:
        p.add_text(title, position='upper_left', font_size=12, color='#222222')
    p.screenshot(path)
    p.close()
    return path
