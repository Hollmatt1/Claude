import sys; sys.path.insert(0, ".")
from app.analyze import analyze
from tests.synth import swing

def run(name, **kw):
    lm, t = swing(**kw)
    r = analyze(lm, t)
    print(f"\n== {name}: view={r['view']} phases={ {k:v['time'] for k,v in r['phases'].items()} } hand={r['metrics'].get('handedness_guess')}")
    for c in r["checks"]:
        print(f"  [{c['status']:4}] {c['title']}: {c['value_text']}")
    return {c["id"]: c["status"] for c in r["checks"]}, r

s, r = run("face-on clean"); assert r["view"]=="face_on" and s["tempo"]=="good" and s["head_sway"]=="good" and s["hip_sway"]=="good" and s["weight_shift"]=="good", s
s, r = run("face-on lefty clean", righty=False); assert r["metrics"]["handedness_guess"]=="left" and s["weight_shift"]=="good"
s, r = run("face-on sway+head", head_sway=0.6, hip_sway=0.5); assert s["head_sway"]=="bad" and s["hip_sway"]=="bad"
s, r = run("face-on hang back", hang_back=True); assert s["weight_shift"]!="good" and s["finish"]!="good", s
s, r = run("face-on 30fps", fps=30); assert s["tempo"]=="good"
s, r = run("dtl clean", view="dtl"); assert r["view"]=="dtl" and s["posture"]=="good" and s["spine_angle"]=="good" and s["early_ext"]=="good", s
s, r = run("dtl early extension", view="dtl", early_ext=0.25, stand_up_deg=15); assert s["early_ext"]=="bad" and s["spine_angle"]=="bad", s
print("\nALL OK")
