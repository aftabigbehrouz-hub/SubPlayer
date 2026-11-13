"""Python port of AudioDecoder.Resampler and SrtBuilder to verify the maths."""
import math
class Resampler:
    def __init__(s, src, dst):
        s.step = src/dst; s.alpha = 1-math.exp(-2*math.pi*(0.45*dst)/src) if src>dst else 1.0
        s.lp1=s.lp2=0.0; s.t=0.0; s.prev=0.0
    def process(s, inp):
        n=len(inp); x=[]
        for v in inp:
            s.lp1+=s.alpha*(v-s.lp1); s.lp2+=s.alpha*(s.lp1-s.lp2); x.append(s.lp2)
        cap=int((n+1-s.t)/s.step)+2; out=[]
        while s.t<n-1 and len(out)<cap:
            i=math.floor(s.t); f=s.t-i; a=s.prev if i<0 else x[i]; b=x[i+1]
            out.append(max(-32768,min(32767,round(a+(b-a)*f)))); s.t+=s.step
        assert len(out)<cap, "buffer cap reached"
        s.t-=n; s.prev=x[-1]; return out
# Test 1: 10 s of 440 Hz tone at 48 kHz / 44.1 kHz in uneven chunks -> expect 160 000 samples
for src in (48000,44100,16000,22050):
    r=Resampler(src,16000); total=0; sig=[int(10000*math.sin(2*math.pi*440*k/src)) for k in range(src*10)]
    pos=0; sizes=[1024,2048,777,4096,1]
    j=0
    while pos<len(sig):
        c=sizes[j%len(sizes)]; total+=len(r.process(sig[pos:pos+c])); pos+=c; j+=1
    print(f"src {src:>5} Hz, 10.000 s -> {total} samples @16k (expected ~160000, diff {total-160000})")
# Test 2: SRT grouping
MAX_GAP,MAX_DUR,MAX_CHARS,MIN_HOLD,MIN_SHOW,SEP=0.8,5.0,80,0.3,1.0,0.05
words=[(0.5,0.8,"hallo"),(0.85,1.2,"wie"),(1.25,1.5,"geht's"),(3.0,3.4,"mir"),(3.45,3.9,"geht"),(3.95,4.3,"es"),(4.35,4.8,"gut")]
cues=[];cur=[]
def flush():
    if cur: t=" ".join(w[2] for w in cur); cues.append([cur[0][0],cur[-1][1],t[0].upper()+t[1:]]); cur.clear()
for w in words:
    if cur:
        ln=sum(len(x[2])+1 for x in cur)+len(w[2])
        if w[0]-cur[-1][1]>MAX_GAP or w[1]-cur[0][0]>MAX_DUR or ln>MAX_CHARS: flush()
    cur.append(w)
flush()
for i,c in enumerate(cues):
    nxt=cues[i+1][0] if i+1<len(cues) else 1e9
    c[1]=max(min(max(c[1]+MIN_HOLD,c[0]+MIN_SHOW),nxt-SEP),c[1])
def ts(s):
    ms=round(s*1000); return "%02d:%02d:%02d,%03d"%(ms//3600000,ms//60000%60,ms//1000%60,ms%1000)
for i,c in enumerate(cues,1): print(f"{i}\n{ts(c[0])} --> {ts(c[1])}\n{c[2]}\n")
