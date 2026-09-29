"""Shared Analog BD gate defaults and 24-bit WAV output."""
import wave
DEFAULTS=[64,80,80,64,64,0,0,64,127,64,64,0]
DEFAULTS_909=[64,32,64,32,64,0,1,64,64,64,64,0]
def wav(path,samples):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1); f.setsampwidth(3); f.setframerate(44100)
        f.writeframes(b''.join((int(x)&0xffffff).to_bytes(3,'little') for x in samples))
