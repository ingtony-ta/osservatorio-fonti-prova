"""Estrazione di prova delle novità dalle fonti pubbliche con dati strutturati.

Legge le interfacce dati della sala stampa della Commissione, delle consultazioni Have Your Say e
due feed (Consiglio UE, Gazzetta Ufficiale serie UE). Per ogni voce registra data, titolo, collegamento e se
contiene parole del dominio (sicurezza prodotti, imballaggi, chimica, batterie, giocattoli, ecodesign, dogane,
consumatori). Segnala le voci nuove rispetto all'esecuzione precedente. Solo fonti pubbliche.
"""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (compatible; osservatorio-fonti-prova/1.0)"

PAROLE = [
    "packaging", "imballagg", "product safety", "sicurezza dei prodotti", "sicurezza prodott", "market surveillance",
    "vigilanza", "consumer", "consumator", "chemical", "chimic", "sostanz", "reach", "clp", "battery", "batteries",
    "batteri", "toy", "giocattol", "ecodesign", "ecoprogett", "customs", "dogan", "waste", "rifiut", "recycl",
    "riciclo", "machinery", "macchin", "radio equipment", "cyber resilience", "artificial intelligence", "digital product",
    "green claim", "greenwashing", "pfas", "restriction", "restrizion", "safety gate", "rapex", "harmonised standard",
    "norme armonizzate", "norma armonizzata", "general product safety", "gpsr", "ppwr", "responsabilità estesa",
    "etichettatur", "labelling", "recepiment", "decreto legislativo", "sanzion", "penalt", "toxic", "tossic",
]


def scarica(url, metodo="GET", corpo=None, tipo=None):
    dati = corpo.encode("utf-8") if corpo else None
    r = urllib.request.Request(url, data=dati, method=metodo)
    r.add_header("User-Agent", UA)
    if tipo:
        r.add_header("Content-Type", tipo)
    with urllib.request.urlopen(r, timeout=40) as x:
        return x.read()


def pertinente(testo):
    t = (testo or "").lower()
    return sorted({p for p in PAROLE if p in t})


def presscorner():
    d = json.loads(scarica("https://ec.europa.eu/commission/presscorner/api/latestnews?language=en&pagesize=50"))
    out = []
    for v in d.get("docuLanguageListResources", []):
        ref = v.get("refCode") or ""
        out.append({"fonte": "Commissione, sala stampa", "id": "pc:" + ref, "data": v.get("eventDate") or "",
                    "titolo": v.get("title") or "", "tipo": (v.get("docutype") or {}).get("description", ""),
                    "url": "https://ec.europa.eu/commission/presscorner/detail/it/" + ref.lower().replace("/", "_")})
    return out


def haveyoursay():
    d = json.loads(scarica("https://ec.europa.eu/info/law/better-regulation/brpapi/searchInitiatives?language=EN&page=0&size=100&feedbackStatus=OPEN"))
    out = []
    for v in d.get("initiativeResultDtoPage", {}).get("content", []):
        st = next((s for s in v.get("currentStatuses", []) if s.get("isCurrent")), {})
        i = int(v["id"])
        out.append({"fonte": "Have Your Say, consultazioni aperte", "id": f"hys:{i}", "data": (st.get("feedbackStartDate") or "")[:10].replace("/", "-"),
                    "titolo": v.get("shortTitle") or "", "tipo": f"{v.get('foreseenActType', '')} {v.get('reference') or ''}".strip(),
                    "scadenza": (st.get("feedbackEndDate") or "")[:10].replace("/", "-"),
                    "url": f"https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/{i}_it"})
    return out


def feed(url, nome, prefisso):
    radice = ET.fromstring(scarica(url))
    out = []
    for it in radice.iter("item"):
        titolo = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        data = (it.findtext("pubDate") or "").strip()
        try:
            data = datetime.strptime(data[:25].strip().rstrip(" +0"), "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
        except Exception:
            data = data[:16]
        out.append({"fonte": nome, "id": prefisso + ":" + (link or titolo), "data": data, "titolo": titolo, "tipo": "feed", "url": link})
    return out


def main():
    cartella = Path("esiti")
    cartella.mkdir(exist_ok=True)
    tutte, errori = [], []
    for nome, f in [("sala stampa", presscorner), ("Have Your Say", haveyoursay),
                    ("Consiglio UE", lambda: feed("https://www.consilium.europa.eu/en/rss/pressreleases.ashx", "Consiglio UE, comunicati", "cu")),
                    ("Gazzetta UE", lambda: feed("https://www.gazzettaufficiale.it/rss/S2", "Gazzetta Ufficiale, serie UE", "gu"))]:
        try:
            voci = f()
            tutte += voci
            print(f"{nome}: {len(voci)} voci")
        except Exception as e:
            errori.append(f"{nome}: {type(e).__name__}: {str(e)[:100]}")
            print(f"{nome}: ERRORE {e}")
    visti_file = cartella / "visti.json"
    try:
        visti = set(json.loads(visti_file.read_text(encoding="utf-8")))
    except Exception:
        visti = set()
    prima_volta = not visti
    for v in tutte:
        v["parole"] = pertinente(v["titolo"] + " " + v.get("tipo", ""))
        v["pertinente"] = bool(v["parole"])
        v["nuova"] = v["id"] not in visti
    nuove = [v for v in tutte if v["nuova"]]
    visti |= {v["id"] for v in tutte}
    visti_file.write_text(json.dumps(sorted(visti)[-3000:], ensure_ascii=False), encoding="utf-8")
    adesso = datetime.now(timezone.utc)
    (cartella / "novita.json").write_text(json.dumps({"eseguito_alle_utc": adesso.isoformat(timespec="seconds"), "prima_volta": prima_volta,
                                                      "errori": errori, "voci": tutte}, ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# Novità estratte il {adesso:%d-%m-%Y %H:%M} UTC", "",
          f"Voci lette: {len(tutte)}. Pertinenti al dominio (parole chiave): {sum(1 for v in tutte if v['pertinente'])}. "
          + ("Prima esecuzione: tutte le voci risultano nuove." if prima_volta else f"Nuove dall'ultima esecuzione: {len(nuove)}."), ""]
    if errori:
        md += ["Fonti non lette: " + "; ".join(errori), ""]
    for fonte in dict.fromkeys(v["fonte"] for v in tutte):
        voci = [v for v in tutte if v["fonte"] == fonte and v["pertinente"]]
        md += [f"## {fonte} ({len(voci)} pertinenti su {sum(1 for v in tutte if v['fonte'] == fonte)})", ""]
        for v in sorted(voci, key=lambda x: x["data"], reverse=True)[:15]:
            extra = f" (scade {v['scadenza']})" if v.get("scadenza") else ""
            md.append(f"- {v['data']} · [{v['titolo'][:140]}]({v['url']}) · {v['tipo']}{extra}" + (" · **nuova**" if v["nuova"] and not prima_volta else ""))
        md.append("")
    (cartella / "novita.md").write_text("\n".join(md), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
