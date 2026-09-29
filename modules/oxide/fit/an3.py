import numpy as np
SR = 44100
d = np.load("ir1.npz"); i0 = int(d["i0"]); h = d["0.01"]
N = len(h); h0 = np.roll(h, -i0)                      # impulse instant -> index 0 (pre-ring wraps to the end)
H = np.fft.fft(h0); f = np.fft.fftfreq(N, 1/SR)
mag = np.maximum(np.abs(H), 10**(-140/20))
# minimum phase via the real cepstrum
c = np.fft.ifft(np.log(mag)).real
w = np.zeros(N); w[0] = 1; w[1:N//2] = 2; w[N//2] = 1
Hmin = np.exp(np.fft.fft(c * w))
ex = np.unwrap(np.angle(H / Hmin)[:N//2])             # excess phase = actual - minimum
fp = f[:N//2]
print("    f    |H| dB   phase   minphase   excess(deg)   excess as delay (samples)")
for ff in (0.5, 1, 2, 3, 5, 8, 12, 20, 30, 45, 70, 100, 150, 250, 400, 700, 1000, 2000, 4000, 8000, 12000, 16000, 19000):
    k = np.argmin(abs(fp - ff))
    e = np.degrees(ex[k])
    print(f"{ff:7.1f} {20*np.log10(abs(H[k])):7.2f} {np.degrees(np.angle(H[k])):8.1f} {np.degrees(np.angle(Hmin[k])):8.1f}   {e:9.1f}     {(-ex[k]/(2*np.pi*ff/SR)) if ff>0 else 0:8.2f}")
np.save("excess.npy", np.c_[fp, ex, np.abs(H[:N//2]), np.angle(H[:N//2])])
