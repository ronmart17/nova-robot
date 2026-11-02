"""Generate nova-main.kicad_pcb: placement + routes (from the router or the cache) + zones, fill and DRC."""
import os, sys, time, pickle, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main_pcb as M, route_main as RM, export as EX

def main(reroute=False):
    cache = os.path.join(M.SCR, 'routes.pkl')
    if reroute or not os.path.exists(cache):
        b, usable, keep, R, planes, F, bad = RM.run()
        routes = R.routes
    else:
        b, usable, keep, R = RM.setup()
        planes = RM.planes_def(usable, keep)
        d = pickle.load(open(cache, 'rb'))
        R.routes = d['routes']
        import fixed
        F = fixed.FX(R, b); F.zones = d.get('zones', [])
    RM.transfer(R, b)
    EX.zones(b, usable, keep, planes, F)
    b.write(M.OUT)
    print('written', M.OUT, len(b.segments), 'tracks', len(b.vias), 'vias', len(b.zones), 'zones')
    EX.fill_and_save(M.OUT, power=dict(widths=RM.WIDTHS, paths=RM.POWER_PATHS))
    dj = os.path.join(M.SCR, 'drc.json')
    d = EX.drc(M.OUT, dj)
    cosmetic = ('track_dangling', 'via_dangling', 'silk_edge_clearance', 'silk_over_copper', 'silk_overlap')
    for _ in range(3):
        if not any(v['type'] in cosmetic for v in d['violations']): break
        EX.cleanup(M.OUT, dj)
        d = EX.drc(M.OUT, dj)
    # final refill with kicad-cli (same engine as the GUI and the plotter) and the DRC of record
    import subprocess
    subprocess.run([EX.CLI, 'pcb', 'drc', '--refill-zones', '--save-board', '--format', 'json', '--severity-all',
                    '--schematic-parity', '--units', 'mm', '-o', dj, M.OUT], capture_output=True, env=EX.CLIENV)
    d = EX.drc(M.OUT, dj)
    return EX.summarize(d)

if __name__ == '__main__':
    v = [a for a in sys.argv if a.startswith('--variant=')]
    if v:
        # route a single variant only (to compare several in parallel); does not write the board
        RM.run(variant=int(v[0].split('=')[1]))
    else:
        main(reroute='--route' in sys.argv)
