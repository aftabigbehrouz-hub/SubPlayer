"""
My Words as one HTML file ("word book"): tabs for the words (meanings, dictionary, the sentence from the video, the
sentences and collocations you added), all sentences, all collocations, and flashcards — with the audio inside the file,
read by the natural voice (Microsoft or Piper), so a click plays it in any browser, also offline and on the phone.
Words without audio are read by the browser's own voice.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import paths, voice


def akey(text: str, lang: str) -> str:
    return hashlib.sha1(f"{lang}|{text.strip()}".encode("utf-8")).hexdigest()[:12]


def say_form(w) -> str:
    """What is read for a word: the phrase, or article + base form for a noun."""
    if " " in w.text.strip():
        return w.text.strip()
    base = (w.lemma or w.text).strip()
    return f"{w.article} {base}" if w.article else base


def collect(main, words, level_name=None, category=None) -> list[dict]:
    """Everything the page shows, as plain data."""
    out = []
    for w in words:
        lang = w.lang or "de"
        d = main.dictionary(lang)
        dic = {}
        if d and " " not in w.text.strip():
            try:
                es = [x for x in d.lookup(w.lemma or w.text) if x.pos != "name"][:1] or d.lookup(w.text)[:1]
            except Exception:
                es = []
            if es:
                e = es[0]
                dic = {"pos": e.pos_de or e.pos, "ipa": e.ipa, "hyph": e.hyphenation,
                       "english": list(e.english[:6]) if lang != "en" else list(e.german[:6]),
                       "persian": list((e.persian or e.persian_via_english)[:6]),
                       "senses": [{"t": s.de, "ex": list(s.examples[:1])} for s in e.senses[:5]],
                       "synonyms": list(e.synonyms[:8])}
        cols = main.store.collocations(lang, w.lemma or w.text) or main.store.collocations(lang, w.text)
        exs = main.store.examples(w.id)
        say = say_form(w)
        out.append({
            "id": w.id, "text": w.text, "lemma": w.lemma, "article": w.article, "ipa": w.ipa or dic.get("ipa", ""),
            "english": w.english, "persian": w.persian, "lang": lang, "say": say, "a": akey(say, lang),
            "level": level_name(w) if level_name else "", "cat": category(w) if category else "",
            "sentence": w.sentence.replace("\n", " ").strip(), "sa": akey(w.sentence.replace("\n", " ").strip(), lang) if w.sentence else "",
            "video": w.video_name, "time": f"{max(0, w.start_ms) // 60000}:{max(0, w.start_ms) // 1000 % 60:02d}" if w.video_name else "",
            "saved": time.strftime("%Y-%m-%d", time.localtime(w.created / 1000)) if w.created else "",
            "reviews": w.reviews, "dict": dic,
            "examples": [{"de": e.de, "en": e.en, "fa": e.fa, "a": akey(e.de, lang)} for e in exs if e.de.strip()],
            "cols": [{"p": c["phrase"], "m": c["meaning"], "ex": c["example"], "a": akey(c["phrase"], lang),
                      "xa": akey(c["example"], lang) if c["example"] else ""} for c in cols if c["phrase"].strip()],
        })
    return out


def wanted(items: list[dict], words=True, sentences=True, collocations=False) -> dict[str, tuple[str, str]]:
    """key → (text, lang) of every clip the page should carry."""
    want: dict[str, tuple[str, str]] = {}
    for it in items:
        lg = it["lang"]
        if words:
            want[it["a"]] = (it["say"], lg)
        if sentences:
            if it["sentence"]:
                want[it["sa"]] = (it["sentence"], lg)
            for e in it["examples"]:
                want[e["a"]] = (e["de"], lg)
        if collocations:
            for c in it["cols"]:
                want[c["a"]] = (c["p"], lg)
                if c["ex"]:
                    want[c["xa"]] = (c["ex"], lg)
    return want


def to_mp3(src: Path) -> Path:
    """A clip as a small MP3 (Piper writes WAV): mono, 48 kbit/s."""
    if src.suffix.lower() == ".mp3":
        return src
    dst = src.with_suffix(".mp3")
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    import av
    tmp = dst.with_suffix(".part.mp3")
    with av.open(str(src)) as inp, av.open(str(tmp), "w", format="mp3") as out:
        st = out.add_stream("libmp3lame", rate=22050)
        st.bit_rate = 48000
        st.layout = "mono"
        rs = av.AudioResampler(format="s16p", layout="mono", rate=22050)
        for fr in inp.decode(audio=0):
            for r in rs.resample(fr):
                for p in st.encode(r):
                    out.mux(p)
        for r in rs.resample(None):
            for p in st.encode(r):
                out.mux(p)
        for p in st.encode(None):
            out.mux(p)
    tmp.replace(dst)
    return dst


def make_audio(settings: dict, want: dict, progress=lambda done, total, note: None, cancelled=lambda: False) -> tuple[dict, str]:
    """key → mp3 bytes for every clip that could be made. Returns (clips, note about what failed)."""
    clips: dict[str, bytes] = {}
    keys = list(want)
    total = len(keys)
    fails, last_err = 0, ""
    eng = settings.get("voice_engine", "edge")
    workers = 4 if eng == "edge" else 1            # Microsoft: a few at a time; Piper uses all cores for one clip

    def one(k):
        text, lang = want[k]
        f = voice.audio_file(settings, text, lang)
        return k, to_mp3(f).read_bytes()

    done = 0
    with ThreadPoolExecutor(workers) as ex:
        futs = []
        for k in keys:
            futs.append(ex.submit(one, k))
        for fu in futs:
            if cancelled():
                for f2 in futs:
                    f2.cancel()
                raise InterruptedError("cancelled")
            try:
                k, b = fu.result()
                clips[k] = b
            except Exception as e:  # noqa: BLE001
                fails += 1
                last_err = f"{e.__class__.__name__}: {e}"
                if fails >= 6 and not clips:       # nothing works (no network, no Piper): stop trying
                    for f2 in futs:
                        f2.cancel()
                    return clips, last_err
            done += 1
            progress(done, total, "")
    return clips, (f"{fails} clip(s) could not be made ({last_err})" if fails else "")


def build_html(items: list[dict], clips: dict[str, bytes], title: str = "My Words") -> str:
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    audio = json.dumps({k: base64.b64encode(v).decode("ascii") for k, v in clips.items()})
    stamp = time.strftime("%d.%m.%Y")
    return (TEMPLATE.replace("%%TITLE%%", html.escape(title)).replace("%%STAMP%%", stamp)
            .replace("%%DATA%%", data).replace("%%AUDIO%%", audio))


def save_mp3_folder(folder: Path, items: list[dict], clips: dict[str, bytes]) -> int:
    """The word clips also as single MP3 files (word.mp3), for a phone or a player."""
    import re
    folder.mkdir(parents=True, exist_ok=True)
    n = 0
    for it in items:
        b = clips.get(it["a"])
        if b:
            name = re.sub(r'[\\/:*?"<>|]+', "_", it["say"])[:80].strip() or f"word-{it['id']}"
            (folder / f"{name}.mp3").write_bytes(b)
            n += 1
    return n


TEMPLATE = r"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%% — SubPlayer</title>
<style>
:root{--bg:#0f0d1a;--card:#1a1729;--card2:#221e35;--txt:#edebf5;--dim:#9a96b0;--cyan:#38e1ff;--gold:#ffc857;--pink:#ff5fa2;
 --mint:#5be3a6;--violet:#8b7bff;--der:#5aa9ff;--die:#ff6b8b;--das:#5be3a6;--line:#2c2843}
@media (prefers-color-scheme: light){:root{--bg:#f6f5fb;--card:#fff;--card2:#f0eef8;--txt:#1d1a2b;--dim:#6b6780;--line:#e2dff0;
 --cyan:#0a8fb0;--gold:#b07800;--mint:#139a63;--der:#1f6fd1;--die:#cc2d52;--das:#139a63}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 "Segoe UI",system-ui,-apple-system,Roboto,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 20px 0}
h1{margin:0;font-size:24px;background:linear-gradient(90deg,var(--cyan),var(--violet),var(--pink));-webkit-background-clip:text;
 background-clip:text;color:transparent;display:inline-block}
.sub{color:var(--dim);font-size:13px;margin-left:8px}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}
input[type=search]{flex:1;min-width:180px;background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:12px;padding:8px 12px;font-size:15px}
.tabs{display:flex;gap:4px;overflow-x:auto}
.tab{background:none;border:0;color:var(--dim);font-size:15px;font-weight:600;padding:9px 14px;border-bottom:3px solid transparent;cursor:pointer;white-space:nowrap}
.tab.on{color:var(--txt);border-color:var(--cyan)}
.chip{background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:999px;padding:5px 12px;font-size:13px;cursor:pointer}
.chip.on{border-color:var(--cyan);color:var(--cyan)}
main{max-width:1000px;margin:0 auto;padding:16px 20px 60px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;margin:10px 0;overflow:hidden}
.head{display:flex;gap:10px;align-items:center;padding:12px 14px;cursor:pointer}
.word{font-size:19px;font-weight:700}.art-der{color:var(--der)}.art-die{color:var(--die)}.art-das{color:var(--das)}
.mean{color:var(--dim);font-size:14px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lv{font-size:11px;font-weight:800;border:1px solid var(--line);border-radius:8px;padding:1px 6px;color:var(--gold)}
.body{display:none;padding:0 16px 14px;border-top:1px solid var(--line)}.card.open .body{display:block}
.sec{color:var(--cyan);font-size:11px;letter-spacing:2px;font-weight:800;margin:14px 0 4px;text-transform:uppercase}
.fa{direction:rtl;text-align:right;font-family:"Vazirmatn","Segoe UI",Tahoma,sans-serif;font-size:16px}
.ex{margin:6px 0;padding:8px 10px;background:var(--card2);border-radius:12px}.ex .de{font-size:15.5px}.ex .tr{color:var(--dim);font-size:13.5px}
.src{color:var(--dim);font-size:12px}
mark{background:none;color:var(--gold);font-weight:700}
.say{background:none;border:1px solid var(--line);color:var(--cyan);border-radius:999px;width:32px;height:32px;font-size:15px;cursor:pointer;flex:none;vertical-align:middle}
.say:hover{border-color:var(--cyan)}.say.play{background:var(--cyan);color:var(--bg)}
.row{display:flex;gap:10px;align-items:flex-start}.row>div{flex:1}
table{border-collapse:collapse;width:100%}td{padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:top}
td.p{color:var(--gold);font-weight:700;width:36%}
.fc{max-width:560px;margin:20px auto;text-align:center}.fcard{background:var(--card);border:1px solid var(--line);border-radius:22px;min-height:260px;
 padding:30px 22px;display:flex;flex-direction:column;justify-content:center;gap:10px;cursor:pointer}
.fbig{font-size:30px;font-weight:800}.muted{color:var(--dim)}.btns{display:flex;gap:8px;justify-content:center;margin-top:14px;flex-wrap:wrap}
.btn{background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:12px;padding:9px 16px;font-size:15px;cursor:pointer}
.btn.acc{background:linear-gradient(90deg,var(--violet),var(--pink));border:0;color:#fff}
.empty{color:var(--dim);text-align:center;margin:40px}
footer{color:var(--dim);font-size:12px;text-align:center;margin:30px 0}
</style></head><body>
<header>
 <h1>%%TITLE%%</h1><span class="sub" id="count"></span>
 <div class="bar"><input type="search" id="q" placeholder="Search words, meanings, sentences …">
  <button class="chip" id="playall" title="Read the list aloud, one after the other">▶ Play all</button></div>
 <div class="tabs" id="tabs"></div>
</header>
<main id="main"></main>
<footer>Made with SubPlayer · %%STAMP%% · 🔊 plays the natural voice saved in this file (or your browser's voice)</footer>
<script>
const W=%%DATA%%; const A=%%AUDIO%%;
const TABS=[["words","Words"],["sent","Sentences"],["coll","Collocations"],["cards","Flashcards"]];
let tab="words", cat="all", q="", queue=[], cur=null;
const $=s=>document.querySelector(s), esc=s=>(s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fa=s=>/[؀-ۿ]/.test(s||"");
function hl(s,w){s=esc(s);const ks=[w.text,w.lemma].filter(Boolean).sort((a,b)=>b.length-a.length);
 for(const k of ks){const r=new RegExp("("+k.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+")","i");if(r.test(s))return s.replace(r,"<mark>$1</mark>")}return s}
function voiceFor(lang){const vs=speechSynthesis.getVoices().filter(v=>v.lang.toLowerCase().startsWith(lang));
 return vs.find(v=>/natural|online|neural/i.test(v.name))||vs[0]}
function play(key,text,lang,done){stop();const b=document.querySelector(`[data-k="${key}"]`);if(b)b.classList.add("play");
 const end=()=>{document.querySelectorAll(".say.play").forEach(x=>x.classList.remove("play"));cur=null;if(done)done()};
 if(A[key]){const a=new Audio("data:audio/mpeg;base64,"+A[key]);cur=a;a.onended=end;a.onerror=end;a.play().catch(end);return}
 if(!window.speechSynthesis){end();return}
 const u=new SpeechSynthesisUtterance(text);u.lang=lang==="en"?"en-US":"de-DE";const v=voiceFor(lang);if(v)u.voice=v;
 u.onend=end;u.onerror=end;cur={pause(){speechSynthesis.cancel()}};speechSynthesis.speak(u)}
function stop(){if(cur&&cur.pause)cur.pause();if(window.speechSynthesis)speechSynthesis.cancel();cur=null;
 document.querySelectorAll(".say.play").forEach(x=>x.classList.remove("play"))}
function sb(key,text,lang){return key?`<button class="say" data-k="${key}" data-t="${esc(text)}" data-l="${lang}" title="Listen">🔊</button>`:""}
document.addEventListener("click",e=>{const b=e.target.closest(".say");if(b){e.stopPropagation();queue=[];play(b.dataset.k,b.dataset.t,b.dataset.l);return}
 const h=e.target.closest(".head");if(h)h.parentElement.classList.toggle("open")});
function art(w){return w.article?`<span class="art-${w.article}">${w.article}</span> `:""}
function match(w){if(!q)return true;const s=[w.text,w.lemma,w.english,w.persian,w.sentence,...w.examples.map(e=>e.de+" "+e.en+" "+e.fa),
 ...w.cols.map(c=>c.p+" "+c.m)].join(" ").toLowerCase();return s.includes(q)}
function list(){return W.filter(w=>(cat==="all"||w.cat===cat)&&match(w))}
function wordCard(w){const d=w.dict||{};let b="";
 if(w.english||w.persian||d.english&&d.english.length){b+=`<div class="sec">Meaning</div>`+(w.english?`<div>${esc(w.english)}</div>`:"")+
  (d.english&&d.english.length&&d.english.join(", ")!==w.english?`<div class="muted">${d.english.map(esc).join(" · ")}</div>`:"")+
  (w.persian?`<div class="fa">${esc(w.persian)}</div>`:"")+(d.persian&&d.persian.length&&!w.persian?`<div class="fa">${d.persian.map(esc).join("، ")}</div>`:"")}
 if(d.pos||w.ipa)b+=`<div class="sec">Word</div><div>${esc(d.pos||"")} ${w.ipa?`<span style="color:var(--gold)">${esc(w.ipa)}</span>`:""} ${d.hyph?`<span class="muted">${esc(d.hyph)}</span>`:""}</div>`;
 if(d.senses&&d.senses.length)b+=`<div class="sec">${w.lang==="en"?"Definitions":"Bedeutungen"}</div>`+d.senses.map((s,i)=>`<div>${i+1}. ${esc(s.t)}${s.ex.length?`<div class="muted"><i>${esc(s.ex[0])}</i></div>`:""}</div>`).join("");
 if(d.synonyms&&d.synonyms.length)b+=`<div class="sec">${w.lang==="en"?"Synonyms":"Synonyme"}</div><div>${d.synonyms.map(esc).join(" · ")}</div>`;
 if(w.sentence)b+=`<div class="sec">From the video</div><div class="ex row">${sb(w.sa,w.sentence,w.lang)}<div><div class="de">${hl(w.sentence,w)}</div><div class="src">${esc(w.video)} ${esc(w.time)}</div></div></div>`;
 if(w.examples.length)b+=`<div class="sec">Sentences · ${w.examples.length}</div>`+w.examples.map(e=>`<div class="ex row">${sb(e.a,e.de,w.lang)}<div><div class="de">${hl(e.de,w)}</div>${e.en?`<div class="tr">${esc(e.en)}</div>`:""}${e.fa?`<div class="tr fa">${esc(e.fa)}</div>`:""}</div></div>`).join("");
 if(w.cols.length)b+=`<div class="sec">Collocations · ${w.cols.length}</div><table>`+w.cols.map(c=>`<tr><td class="p">${sb(c.a,c.p,w.lang)} ${esc(c.p)}</td><td>${esc(c.m)}${c.ex?`<div class="muted"><i>${esc(c.ex)}</i> ${sb(c.xa,c.ex,w.lang)}</div>`:""}</td></tr>`).join("")+"</table>";
 b+=`<div class="src" style="margin-top:10px">saved ${esc(w.saved)} · reviewed ${w.reviews}× <button class="chip" onclick="playWord(${w.id})">▶ word + sentences</button></div>`;
 return `<div class="card" id="w${w.id}"><div class="head">${sb(w.a,w.say,w.lang)}<span class="word">${art(w)}${esc(w.text)}</span>${w.level?`<span class="lv">${esc(w.level)}</span>`:""}<span class="mean${fa(w.english)?" fa":""}">${esc(w.english||w.persian)}</span></div><div class="body">${b}</div></div>`}
function playWord(id){const w=W.find(x=>x.id===id);queue=[[w.a,w.say,w.lang]];if(w.sentence)queue.push([w.sa,w.sentence,w.lang]);
 w.examples.forEach(e=>queue.push([e.a,e.de,w.lang]));next()}
function next(){if(!queue.length)return;const [k,t,l]=queue.shift();play(k,t,l,()=>setTimeout(next,700))}
const CATS=[["all","All"],["phrase","Phrases"],["noun","Nouns"],["verb","Verbs"],["adj","Adjectives"],["other","Others"]];
function cats(){const have=new Set(W.map(w=>w.cat));return `<div class="bar">`+CATS.filter(([k])=>k==="all"||have.has(k)).map(([k,l])=>`<button class="chip${cat===k?" on":""}" onclick="cat='${k}';draw()">${l}</button>`).join("")+`</div>`}
let fi=0,flip=false,deck=[],rev=false,auto=true;
function draw(){const m=$("#main");const L=list();$("#count").textContent=`${W.length} words · ${new Set(W.flatMap(w=>[w.sentence,...w.examples.map(e=>e.de)].filter(Boolean))).size} sentences`;
 $("#tabs").innerHTML=TABS.map(([k,l])=>`<button class="tab${tab===k?" on":""}" onclick="tab='${k}';stop();draw()">${l}</button>`).join("");
 if(tab==="words"){m.innerHTML=cats()+(L.map(wordCard).join("")||`<div class="empty">No words match.</div>`)}
 else if(tab==="sent"){const S=[];L.forEach(w=>{if(w.sentence)S.push({w,de:w.sentence,a:w.sa,src:w.video+" "+w.time});w.examples.forEach(e=>S.push({w,de:e.de,en:e.en,fa:e.fa,a:e.a}))});
  m.innerHTML=cats()+(S.map(s=>`<div class="ex row">${sb(s.a,s.de,s.w.lang)}<div><div class="de">${hl(s.de,s.w)}</div>${s.en?`<div class="tr">${esc(s.en)}</div>`:""}${s.fa?`<div class="tr fa">${esc(s.fa)}</div>`:""}<div class="src">${art(s.w)}${esc(s.w.text)}${s.src?" · "+esc(s.src):""}</div></div></div>`).join("")||`<div class="empty">No sentences.</div>`)}
 else if(tab==="coll"){const C=L.filter(w=>w.cols.length);m.innerHTML=cats()+(C.map(w=>`<div class="sec">${art(w)}${esc(w.lemma||w.text)}</div><table>`+w.cols.map(c=>`<tr><td class="p">${sb(c.a,c.p,w.lang)} ${esc(c.p)}</td><td>${esc(c.m)}${c.ex?`<div class="muted"><i>${esc(c.ex)}</i> ${sb(c.xa,c.ex,w.lang)}</div>`:""}</td></tr>`).join("")+"</table>").join("")||`<div class="empty">No collocations yet.</div>`)}
 else{deck=L;if(fi>=deck.length)fi=0;fcard()}}
function fcard(){const m=$("#main");if(!deck.length){m.innerHTML=`<div class="empty">No words.</div>`;return}const w=deck[fi];
 const front=rev?`<div class="fbig${fa(w.english)?" fa":""}" style="font-size:22px">${esc(w.english||w.persian)}</div>`:`<div class="fbig">${art(w)}${esc(w.text)}</div>${w.sentence?`<div class="muted">${hl(w.sentence,w)}</div>`:""}`;
 const back=`<div class="fbig">${art(w)}${esc(w.text)}</div>${w.english?`<div>${esc(w.english)}</div>`:""}${w.persian?`<div class="fa">${esc(w.persian)}</div>`:""}${w.examples[0]?`<div class="muted"><i>${esc(w.examples[0].de)}</i></div>`:""}`;
 m.innerHTML=`<div class="fc"><div class="muted">${fi+1} / ${deck.length}</div><div class="fcard" onclick="flip=!flip;fcard()">${flip?back:front}<div class="muted" style="font-size:12px">${flip?"":"tap to turn"}</div></div>
 <div class="btns"><button class="btn" onclick="fi=(fi-1+deck.length)%deck.length;flip=false;fcard();say()">◀</button>${sb(w.a,w.say,w.lang)}<button class="btn acc" onclick="fi=(fi+1)%deck.length;flip=false;fcard();say()">Next ▶</button></div>
 <div class="btns"><button class="chip${rev?" on":""}" onclick="rev=!rev;flip=false;fcard()">Meaning first</button><button class="chip" onclick="deck.sort(()=>Math.random()-.5);fi=0;flip=false;fcard()">Shuffle</button><button class="chip${auto?" on":""}" onclick="auto=!auto;fcard()">Read aloud</button></div></div>`}
function say(){if(auto&&!rev){const w=deck[fi];play(w.a,w.say,w.lang)}}
$("#q").addEventListener("input",e=>{q=e.target.value.trim().toLowerCase();draw()});
$("#playall").addEventListener("click",()=>{if(queue.length||cur){queue=[];stop();return}
 queue=list().map(w=>[w.a,w.say,w.lang]);next()});
if(window.speechSynthesis)speechSynthesis.onvoiceschanged=()=>{};
draw();
</script></body></html>
"""
