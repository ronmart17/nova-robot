"""Head board routing and output (2 layers): B.Cu as an almost continuous GND plane (signals run on
F.Cu; B.Cu is penalised), GND fan-outs to B.Cu, +3V3 at 0.4 mm."""
import os, sys, time, pickle, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from shapely.geometry import Point
import head_pcb as H, rgrid, autoroute, conn, export as EX
import route_main as RM

def net_named(R, suffix):
    for n in R.netpads:
        if n == suffix or n.endswith('/' + suffix):
            return n
    return None

def setup():
    b, poly, keep, issues = H.build(check=False)
    hz = []
    for name, kp, sides, ex in keep:
        hz.append((kp, ('F.Cu', 'B.Cu')))
    R = rgrid.build_router(b, poly, hz)
    R.lcost = (1.0, 2.5)
    return b, poly, keep, R

def run(verbose=True):
    t = time.time()
    b, poly, keep, R = setup()
    gnd_poly = poly.buffer(-0.35)
    planes = {'GND': [('B.Cu', gnd_poly)]}
    regions = {'GND': RM.region_mask(R, gnd_poly)}
    widths = {}
    p33 = net_named(R, '+3V3'); bl = net_named(R, 'BL_OUT')
    if p33: widths[p33] = 0.4
    if bl: widths[bl] = 0.3
    nets = [n for n in R.netpads if n != 'GND']
    def hpwl(n):
        ps = [c for _, _, _, c in R.netpads[n]]
        return (max(p[0] for p in ps) - min(p[0] for p in ps)) + (max(p[1] for p in ps) - min(p[1] for p in ps))
    wide = [n for n in nets if n in widths]
    rest = sorted([n for n in nets if n not in widths], key=hpwl)
    order = ['GND'] + sorted(wide, key=lambda n: -widths[n]) + rest
    nr = autoroute.route_all(R, b, planes, order, widths, verbose=verbose, regions=regions)
    conn.trim_stubs(b, R, planes, verbose=verbose)
    bad = conn.report(b, R, planes, verbose=verbose)
    pickle.dump({'routes': R.routes}, open(os.path.join(H.SCR, 'routes.pkl'), 'wb'))
    if verbose: print(f'routing: {time.time() - t:.0f} s')
    return b, poly, keep, R, planes, bad

def zones(b, poly, keep):
    outline = EX.ring(poly)
    b.zone('GND', 'B.Cu', outline, priority=0, clearance=0.25, min_w=0.2, connect='tht', name='GND (B)')
    b.zone('GND', 'F.Cu', outline, priority=0, clearance=0.25, min_w=0.2, connect='tht', name='GND (F)')
    for name, kp, sides, ex in keep:
        b.keepout(['F.Cu', 'B.Cu'], EX.ring(kp), tracks=False, vias=False, pads=True, pour=False, fps=True,
                  name='No copper: ' + name)
    # touch electrode pad (TP101): no GND pour in 6 × 6 mm on both sides → less parasitic capacitance
    from shapely.geometry import box
    tp = b.placed['TP101']
    b.keepout(['F.Cu', 'B.Cu'], EX.ring(box(tp.x - 3.0, tp.y - 3.0, tp.x + 3.0, tp.y + 3.0)), tracks=True, vias=True,
              pads=True, pour=False, fps=True, name='Touch: no GND pour')

def main(reroute=True):
    cache = os.path.join(H.SCR, 'routes.pkl')
    if reroute or not os.path.exists(cache):
        b, poly, keep, R, planes, bad = run()
    else:
        b, poly, keep, R = setup()
        R.routes = pickle.load(open(cache, 'rb'))['routes']
    RM.transfer(R, b)
    zones(b, poly, keep)
    b.write(H.OUT)
    print('written', H.OUT, len(b.segments), 'tracks', len(b.vias), 'vias')
    EX.fill_and_save(H.OUT, profile='head')
    d = EX.drc(H.OUT, os.path.join(H.SCR, 'drc.json'))
    return EX.summarize(d)

if __name__ == '__main__':
    main(reroute='--cache' not in sys.argv)
