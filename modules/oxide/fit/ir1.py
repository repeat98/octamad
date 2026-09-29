import json, numpy as np, oxide as o
o.setp(input_level=0.0, output_level=0.0, path_select="Repro", ips="15 IPS",
       emphasis_eq="NAB", noise_reduct=True, power=True, master_bypass=False)
n = 1 << 19; i0 = 4096
z = o.run(np.zeros(n)); print("silence max", np.max(abs(z)))
irs = {}
for a in (0.1, 0.01, -0.1):
    x = np.zeros(n); x[i0] = a
    irs[str(a)] = o.run(x) / a
np.savez("ir1.npz", i0=i0, **irs)
h1, h2, h3 = irs["0.1"], irs["0.01"], irs["-0.1"]
print("IR 0.1 vs 0.01 rel diff dB", 20*np.log10(np.linalg.norm(h1-h2)/np.linalg.norm(h1)))
print("IR +0.1 vs -0.1 rel diff dB", 20*np.log10(np.linalg.norm(h1-h3)/np.linalg.norm(h1)))
print("energy before i0 (dB rel total):", 10*np.log10(np.sum(h1[:i0]**2)/np.sum(h1**2)))
print("taps -8..+8:", np.round(h1[i0-8:i0+9], 4))
e = np.cumsum(h1[i0:]**2)/np.sum(h1[i0:]**2)
for q in (0.99, 0.999, 0.9999): print(f"{q} of energy by {np.argmax(e>q)/44100*1000:.1f} ms")
print("tail rms last second", np.sqrt(np.mean(h1[-44100:]**2)))
