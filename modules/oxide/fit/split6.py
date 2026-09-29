import json, numpy as np
b2 = json.load(open("batch2.json")); ref = b2["curves"]["1000"]
Lr = np.array([d["level"] for d in ref], float); Nr = Lr + np.array([d["gain"] for d in ref])
def N(l):
    return np.where(l < Lr[0], Nr[0] + (l - Lr[0]), np.interp(l, Lr, Nr))
def split(lv, G):
    lv = np.array(lv, float); G = np.array(G); tot = G[0]; best = None
    for e1 in np.arange(-15, 20.001, 0.02):
        e2 = tot - e1; err = np.sqrt(np.mean((N(lv + e1) + e2 - lv - G)**2))
        if best is None or err < best[0]: best = (err, e1, e2)
    return tot, best[1], best[2], best[0]
rows = []
b6 = json.load(open("batch6.json"))["lowsplit"]
for f, G in zip(b6["fs"], b6["gain"]): rows.append((f, *split(b6["lv"], G)))
old = json.load(open("split5.json"))
rows += [tuple(r) for r in old]
rows.sort()
json.dump(rows, open("split6.json", "w"))
print("    f   total    E1     E2   fit rms")
for r in rows[:14]: print(f"{r[0]:6.1f} {r[1]:6.2f} {r[2]:6.2f} {r[3]:6.2f}  {r[4]:.3f}")
