import re, unicodedata
from pathlib import Path
import pandas as pd

UNRESOLVED_FILE="flashscore_alias_still_unresolved.csv"
PLAYERS_FILE="players_master.csv"
OUTPUT_FILE="flashscore_alias_review_candidates.csv"
SEP=";"

def clean(v):
    return " ".join(str(v or "").replace("\xa0"," ").split()).strip()

def strip_accents(v):
    v=unicodedata.normalize("NFKD", clean(v))
    return "".join(ch for ch in v if not unicodedata.combining(ch))

def norm(v):
    v=strip_accents(v).casefold()
    v=re.sub(r"[^a-z0-9 ]+"," ",v)
    return " ".join(v.split())

def flash_parts(name):
    words=[]; initials=[]
    for token in clean(name).split():
        raw=strip_accents(token)
        if re.fullmatch(r"[A-Za-z]\.", raw):
            initials.append(raw[0].casefold())
        else:
            n=norm(raw)
            if n: words.append(n)
    return words, initials

def candidate_score(fs_name, player_name):
    fs_words, fs_initials = flash_parts(fs_name)
    p = norm(player_name).split()
    if not fs_words or not p:
        return 0, []
    score=0; reasons=[]
    last=fs_words[-1]
    if p[-1]==last:
        score+=60; reasons.append("presne posledne priezvisko")
    elif last in p:
        score+=40; reasons.append("priezvisko v TA mene")
    else:
        return 0, []
    matched=sum(1 for w in fs_words if w in p)
    if len(fs_words)>1 and matched==len(fs_words):
        score+=25; reasons.append("vsetky textove casti sedia")
    elif matched>1:
        score+=12; reasons.append("viac textovych casti sedi")
    if fs_initials:
        first=p[0][0] if p[0] else ""
        if fs_initials[0]==first:
            score+=20; reasons.append("prva iniciala sedi")
        else:
            score-=12; reasons.append("prva iniciala nesedi")
    return score, reasons

def main():
    if not Path(UNRESOLVED_FILE).exists():
        raise FileNotFoundError(UNRESOLVED_FILE)
    if not Path(PLAYERS_FILE).exists():
        raise FileNotFoundError(PLAYERS_FILE)

    u=pd.read_csv(UNRESOLVED_FILE, sep=SEP)
    p=pd.read_csv(PLAYERS_FILE, sep=SEP)
    u.columns=[str(c).replace("\ufeff","").strip() for c in u.columns]
    p.columns=[str(c).replace("\ufeff","").strip() for c in p.columns]

    rows=[]
    for _,r in u[["FlashscoreName","Tour"]].drop_duplicates().iterrows():
        fs=clean(r["FlashscoreName"]); tour=clean(r["Tour"])
        pool=p[p["Tour"].astype(str).str.strip().str.casefold()==tour.casefold()]
        cand=[]
        for _,pr in pool.iterrows():
            player=clean(pr["Player"])
            score,reasons=candidate_score(fs,player)
            if score>0:
                cand.append((score,player,", ".join(reasons)))
        cand.sort(key=lambda x:(-x[0],x[1]))
        top=cand[:3]
        row={"FlashscoreName":fs,"Tour":tour}
        for i in range(3):
            if i<len(top):
                row[f"Candidate{i+1}"]=top[i][1]
                row[f"Score{i+1}"]=top[i][0]
                row[f"Reason{i+1}"]=top[i][2]
            else:
                row[f"Candidate{i+1}"]=""
                row[f"Score{i+1}"]=""
                row[f"Reason{i+1}"]=""
        if not top:
            decision="NO_CANDIDATE"
        elif len(top)==1:
            decision="REVIEW_SINGLE"
        elif top[0][0]>=top[1][0]+20:
            decision="REVIEW_STRONG"
        else:
            decision="REVIEW_MULTIPLE"
        row["SuggestedDecision"]=decision
        rows.append(row)

    out=pd.DataFrame(rows)
    out.to_csv(OUTPUT_FILE, sep=SEP, index=False, encoding="utf-8-sig")
    print("="*70)
    print("ALIAS REVIEW CANDIDATES")
    print("="*70)
    print(f"Nevyriesenych mien: {len(out)}")
    print(f"Vystup: {OUTPUT_FILE}")
    for _,r in out.head(20).iterrows():
        print(f"{r['FlashscoreName']} [{r['Tour']}] -> {r['Candidate1'] or 'BEZ KANDIDATA'} | score={r['Score1']} | {r['SuggestedDecision']}")
    print("="*70)

if __name__=="__main__":
    main()
