"""808 DSP model calibrated to the user's *_Orig.wav recordings only.
A decaying pitched body and a damped trigger transient; no recording playback.
The desk and output LPF use the 909's exact source and tables.
"""
import math, re
from pathlib import Path
import dsp909
HERE=Path(__file__).resolve().parent
RATE=44100
# Post-desk attenuation: default 500 ms hit energy matches the 909 within 0.1 dB.
OUTPUT_TRIM=0.215
SWORDS=48
OFF=dict(U=0,EH=1,EL=2,EP=3,PC=4,PS=5,DC=6,TF=7,INC=8,BEND=9,DE=10,DP=11,KT=12,GAIN=13,VEL=14,ATK=15,SEG=16,YL=20,KLPF=32)
OFF.update({k:v for k,v in dsp909.OFF.items() if v>=37})
def interp(i, vals):
    x=i/127*5; j=min(4,int(x)); return vals[j]+(vals[j+1]-vals[j])*(x-j)
def tables():
    tau=[interp(i,[.0164,.0409,.0979,.1617,.2622,.3401]) for i in range(128)]
    pt=[interp(i,[.03,.0357,.0656,.1087,.204,.3109]) for i in range(128)]
    return dict(
      B_INC=[2*48.85*2**((i-64)/48)/RATE for i in range(128)],
      B_DE=[-math.expm1(-1/(RATE*x)) for x in tau],
      B_DP=[-math.expm1(-1/(RATE*x)) for x in pt],
      B_BEND=[2*interp(i,[12,11.44,8.56,7.09,6.094,5.866])/RATE for i in range(128)],
      B_GAIN=[interp(i,[.90,.812,.759,.744,.741,.738])/2 for i in range(128)],
      B_TONE=[-math.expm1(-2*math.pi*350*(2300/350)**(i/127)/RATE) for i in range(128)],
      B_VEL=[max(1,i)/127 for i in range(128)],
      B_ATK=[i/127 for i in range(128)])
def layout(base):
    return {k:base+128*i for i,k in enumerate(tables())}
def data_lines(lay):
    return ''.join('X %x '%lay[k]+' '.join('%06x'%dsp909.q24(v) for v in vs)+'\n' for k,vs in tables().items())
def source(lay,shared,*,output_trim=True):
    text=(HERE/'bd808.asm').read_text()
    full=dsp909.source(shared)
    for tag in ('desk-decode','desk'):
        block=full[full.index(';<' + tag + '>'):full.index(';</' + tag + '>')]
        if tag=='desk' and output_trim:
            # Limit to the same 24-bit sample as the original output store first.
            # The oscillator, LPF and saturation states are untouched.
            stores='        move    a,x:(r0)+'
            at=block.index(stores)
            block=block[:at]+('        move    a,x0\n'
                             f'        move    #>${dsp909.q24(OUTPUT_TRIM):06x},y0\n'
                             '        mpy     y0,x0,a\n')+block[at:]
        text=text.replace('@'+tag+'@',block)
    subs={k:f'${v:x}' for k,v in {**OFF,**lay,'T_LPF':shared['T_LPF']}.items()}
    con=dict(PK=2*math.sin(math.pi*129.10747/RATE),PD=-math.expm1(-1/(RATE*.00203264)),DD=-math.expm1(-1/(RATE*.00301295)),PC0=3.27303983/4,PS0=-1.57554231/4,DC0=-1.09270470/4,U0=(-1.3892912-math.pi/2)/math.pi,
             S1=math.pi/4,S3=-(math.pi/2)**3/12,S5=(math.pi/2)**5/240,S7=-(math.pi/2)**7/10080,S9=(math.pi/2)**9/725760)
    subs.update({k:f'${dsp909.q24(v):06x}' for k,v in con.items()})
    return re.sub(r'@([A-Z0-9_]+)@',lambda m:subs[m[1]],text)

class Voice(dsp909.Voice):
    """Independent float reference, with 24-bit phase/control quantization."""
    def __init__(self):
        super().__init__()
        q=lambda v: ((dsp909.q24(v)^0x800000)-0x800000)/8388608
        self.bt={k:[q(v) for v in vs] for k,vs in tables().items()}
        self.q=q
        self.u=self.e=self.ep=self.pc=self.ps=self.dc=self.tf=0.
        self.count=0x7fffff
    def block(self,k,trig=None,frames=16):
        t=self.bt; f=dsp909.fl24; q=self.q
        inc=t['B_INC'][k[0]]; de=t['B_DE'][k[1]]; dp=t['B_DP'][k[1]]
        bend=f(2*t['B_BEND'][k[1]]*k[4]/128)
        gain=t['B_GAIN'][k[1]];kt=t['B_TONE'][k[2]];vel=t['B_VEL'][k[7]];atk=t['B_ATK'][k[3]]
        pk=q(2*math.sin(math.pi*129.10747/RATE));pd=q(-math.expm1(-1/(RATE*.00203264)));dd=q(-math.expm1(-1/(RATE*.00301295)))
        cs=[q(math.pi/4),q(-(math.pi/2)**3/12),q((math.pi/2)**5/240),q(-(math.pi/2)**7/10080),q((math.pi/2)**9/725760)]
        self.desk_knobs(k);out=[]
        for i in range(frames):
            if i==trig:
                self.count=0;self.e=1.;self.ep=q(1);self.u=q((-1.3892912-math.pi/2)/math.pi)
                self.pc=q(3.27303983/4);self.ps=q(-1.57554231/4);self.dc=q(-1.09270470/4)
            step=f(inc+bend*self.ep);self.ep=f(self.ep-dp*self.ep)
            self.u=(self.u+step+1)%2-1
            x=min(1-2**-23,1-2*abs(self.u));xx=f(x*x)
            h=cs[-1]
            for c in cs[-2::-1]:h=f(c+h*xx)
            sn=f(h*x)
            harmonic=f(q(.03076)+q(-.246062)*f(sn*sn))
            body=f((sn+harmonic)*gain)
            self.e-=de*f(self.e)
            body=f(body*f(self.e))
            pc=f(self.pc-pk*self.ps);ps=self.ps+pk*pc
            self.ps=f(ps-pd*f(ps));self.pc=f(pc-pd*pc);self.dc=f(self.dc-dd*self.dc)
            self.count+=1
            y=(f(2*(self.pc+self.dc)*atk) if self.count<4096 else 0)+body
            self.tf=f(self.tf+kt*(y-self.tf))
            y=f(max(-1,min(1-2**-23,4*self.tf))*vel)
            self.yl+=self.t['T_LPF'][k[8]]*(y-self.yl)
            out.append(f(f(self.desk(self.yl))*q(OUTPUT_TRIM)))
        return out
