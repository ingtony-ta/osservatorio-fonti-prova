"""Analista diurno dell'osservatorio normativo (seconda fase, con il modello via API).

Legge `esiti/analisi/raccolta.json` e `istruzioni_analista.md`, chiede al modello di esaminare la raccolta, fare le
ricerche complementari e verificare ogni voce, e scrive `esiti/analisi/AAAA-MM-GG.json` e `.md`. Registra token e
costo stimato in `esiti/analisi/costi.csv`. La chiave API arriva dal secret ANTHROPIC_API_KEY e non si scrive mai.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MODELLO = os.environ.get("MODELLO", "claude-sonnet-5-5")
# prezzi in dollari per milione di token: ingresso, uscita, scrittura in cache, lettura dalla cache
PREZZI = {"claude-sonnet-5-5": (2.0, 10.0, 2.5, 0.10), "claude-opus-5-5": (5.0, 25.0, 6.25, 0.50)}
PREZZO_RICERCA = 0.01  # dollari per ricerca web
TETTO_DOLLARI = float(os.environ.get("TETTO_DOLLARI", "5"))
MAX_GIRI = int(os.environ.get("MAX_GIRI", "60"))
MAX_RICERCHE = int(os.environ.get("MAX_RICERCHE", "40"))
LIMITE_TESTO = 20000
UA = "Mozilla/5.0 (compatible; osservatorio-fonti-prova/1.0)"
CARTELLA = Path("esiti/analisi")

STRUMENTI = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_RICERCHE},
    {"name": "leggi_pagina", "description": "Legge il testo di una pagina web pubblica o di un PDF e lo restituisce come testo semplice (al massimo 20000 caratteri). Usarlo per aprire comunicati, consultazioni, Gazzetta Ufficiale, siti dei ministeri e delle autorità.",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string", "description": "Indirizzo http o https"},
                                                        "da_carattere": {"type": "integer", "description": "Posizione da cui riprendere la lettura di un testo lungo (predefinito 0)"}},
                      "required": ["url"]}},
    {"name": "leggi_atto_ue", "description": "Legge il testo di un atto dell'Unione europea dal codice CELEX, dal Cellar dell'Ufficio pubblicazioni (al massimo 20000 caratteri per lettura).",
     "input_schema": {"type": "object", "properties": {"celex": {"type": "string", "description": "Codice CELEX, per esempio 32023R0988"},
                                                        "lingua": {"type": "string", "enum": ["ita", "eng"], "description": "Lingua del testo (predefinito ita)"},
                                                        "da_carattere": {"type": "integer"}},
                      "required": ["celex"]}},
]


def testo_da_html(dati):
    t = dati.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def scarica(url, accept="*/*", lingua=None):
    intestazioni = {"User-Agent": UA, "Accept": accept}
    if lingua:
        intestazioni["Accept-Language"] = lingua
    r = urllib.request.Request(url, headers=intestazioni)
    with urllib.request.urlopen(r, timeout=60) as x:
        return x.status, x.headers.get("Content-Type", ""), x.read()


def taglia(testo, da):
    da = max(0, int(da or 0))
    pezzo = testo[da:da + LIMITE_TESTO]
    resto = len(testo) - (da + len(pezzo))
    if resto > 0:
        pezzo += f"\n[... testo continua: altri {resto} caratteri; per proseguire usare da_carattere={da + len(pezzo)}]"
    return pezzo


def leggi_pagina(url, da_carattere=0):
    if not re.match(r"^https?://", url or ""):
        return "Indirizzo non valido: servono http o https."
    # pagine JavaScript con interfaccia dati pubblica: si legge l'interfaccia
    pc = re.search(r"presscorner/detail/(\w+)/([a-z]+_\d+_\d+)", url or "", re.I)
    if pc:
        rif = pc.group(2).upper().replace("_", "/")
        try:
            _, _, dati = scarica("https://ec.europa.eu/commission/presscorner/api/documents?reference=" + rif + "&language=en")
            d = json.loads(dati)
            corpo = (d.get("docuLanguageResource") or {}).get("htmlContent") or json.dumps(d, ensure_ascii=False)
            return taglia(testo_da_html(corpo.encode("utf-8")), da_carattere)
        except Exception as e:
            return f"Comunicato {rif}: interfaccia della sala stampa non leggibile ({type(e).__name__}: {str(e)[:100]})"
    hys = re.search(r"have-your-say/initiatives/(\d+)", url or "")
    if hys:
        try:
            _, _, dati = scarica(f"https://ec.europa.eu/info/law/better-regulation/brpapi/groupInitiatives/{hys.group(1)}")
            return taglia(json.dumps(json.loads(dati), ensure_ascii=False), da_carattere)
        except Exception as e:
            return f"Iniziativa {hys.group(1)}: interfaccia di Have Your Say non leggibile ({type(e).__name__}: {str(e)[:100]})"
    try:
        codice, tipo, dati = scarica(url)
    except urllib.error.HTTPError as e:
        return f"Errore HTTP {e.code} su {url}"
    except Exception as e:
        return f"Errore {type(e).__name__} su {url}: {str(e)[:150]}"
    if "pdf" in tipo.lower() or dati[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
            import io
            testo = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(dati)).pages)
        except Exception as e:
            return f"PDF scaricato ({len(dati)} byte) ma testo non estraibile: {type(e).__name__}"
    else:
        testo = testo_da_html(dati)
    if len(testo) < 200:
        return f"HTTP {codice}, pagina quasi vuota ({len(dati)} byte): probabile pagina JavaScript o sfida anti-bot. Testo: {testo[:200]}"
    return taglia(testo, da_carattere)


def leggi_atto_ue(celex, lingua="ita", da_carattere=0):
    celex = re.sub(r"[^0-9A-Za-z()]", "", celex or "")
    try:
        _, _, dati = scarica(f"https://publications.europa.eu/resource/celex/{celex}",
                             accept="application/xhtml+xml, text/html;q=0.9", lingua=lingua or "ita")
    except urllib.error.HTTPError as e:
        if e.code != 300:
            return f"Errore HTTP {e.code} per il CELEX {celex} in lingua {lingua}"
        # più documenti per lo stesso atto (proposte con allegati): si leggono tutti, in ordine
        parti = re.findall(r'href="(https?://publications\.europa\.eu/resource/cellar/[^"]+/DOC_\d+)"', e.read().decode("utf-8", errors="replace"))
        testi = []
        for u in dict.fromkeys(parti):
            try:
                testi.append(testo_da_html(scarica(u, accept="application/xhtml+xml, text/html;q=0.9")[2]))
            except Exception as x:
                testi.append(f"[{u}: {type(x).__name__}]")
        if not testi:
            return f"Errore HTTP 300 per il CELEX {celex} in lingua {lingua}, nessun documento nell'elenco"
        return taglia("\n\n[documento successivo]\n\n".join(testi), da_carattere)
    except Exception as e:
        return f"Errore {type(e).__name__} per il CELEX {celex}: {str(e)[:150]}"
    testo = testo_da_html(dati)
    if len(testo) < 200:
        return f"Testo dell'atto {celex} non disponibile in XHTML in lingua {lingua}."
    return taglia(testo, da_carattere)


def esegui_strumento(nome, ingresso):
    if nome == "leggi_pagina":
        return leggi_pagina(ingresso.get("url", ""), ingresso.get("da_carattere", 0))
    if nome == "leggi_atto_ue":
        return leggi_atto_ue(ingresso.get("celex", ""), ingresso.get("lingua", "ita"), ingresso.get("da_carattere", 0))
    return f"Strumento sconosciuto: {nome}"


def chiama_api(chiave, corpo):
    dati = json.dumps(corpo).encode("utf-8")
    for tentativo in range(5):
        r = urllib.request.Request("https://api.anthropic.com/v1/messages", data=dati, method="POST", headers={
            "x-api-key": chiave, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=600) as x:
                return json.loads(x.read())
        except urllib.error.HTTPError as e:
            messaggio = e.read().decode("utf-8", errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 529) and tentativo < 4:
                print(f"API {e.code}, nuovo tentativo fra {30 * (tentativo + 1)} s")
                time.sleep(30 * (tentativo + 1))
                continue
            raise RuntimeError(f"API HTTP {e.code}: {messaggio}")


def voci_gia_riportate(oggi):
    out = []
    for f in sorted(CARTELLA.glob("20??-??-??.json")):
        try:
            if (oggi - date.fromisoformat(f.stem)).days > 45 or f.stem == oggi.isoformat():
                continue
            for v in json.loads(f.read_text(encoding="utf-8")).get("voci", []):
                out.append(f"{v.get('data', '')} · {v.get('atto', '')} · {v.get('titolo', '')[:100]} · {v.get('url', '')}")
        except Exception:
            continue
    return out


def segna_cache(messaggi):
    """Un solo punto di cache, sull'ultimo blocco dell'ultimo messaggio: il resto della conversazione si rilegge dalla cache."""
    for m in messaggi:
        if isinstance(m["content"], list):
            for b in m["content"]:
                if isinstance(b, dict):
                    b.pop("cache_control", None)
    ultimo = messaggi[-1]
    if isinstance(ultimo["content"], str):
        ultimo["content"] = [{"type": "text", "text": ultimo["content"]}]
    ultimo["content"][-1]["cache_control"] = {"type": "ephemeral"}


def main():
    chiave = os.environ.get("ANTHROPIC_API_KEY")
    if not chiave:
        print("Manca il secret ANTHROPIC_API_KEY")
        return 1
    oggi = datetime.now(timezone.utc).date()
    raccolta = json.loads((CARTELLA / "raccolta.json").read_text(encoding="utf-8"))
    istruzioni = Path("istruzioni_analista.md").read_text(encoding="utf-8")
    gia = voci_gia_riportate(oggi)
    it = lambda s: date.fromisoformat(s).strftime("%d-%m-%Y")
    richiesta = (f"Finestra: dal {it(raccolta['finestra_da'])} al {it(raccolta['finestra_al'])} (oggi {oggi:%d-%m-%Y}).\n\n"
                 f"Voci già riportate nei giorni precedenti ({len(gia)}):\n" + ("\n".join(gia) or "nessuna") + "\n\n"
                 "Raccolta delle fonti con dati strutturati (JSON):\n" + json.dumps(raccolta, ensure_ascii=False))
    messaggi = [{"role": "user", "content": richiesta}]
    sistema = [{"type": "text", "text": istruzioni, "cache_control": {"type": "ephemeral"}}]
    uso = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "ricerche": 0}
    p = PREZZI.get(MODELLO, PREZZI["claude-sonnet-5-5"])
    costo = lambda: (uso["input_tokens"] * p[0] + uso["output_tokens"] * p[1] + uso["cache_creation_input_tokens"] * p[2]
                     + uso["cache_read_input_tokens"] * p[3]) / 1e6 + uso["ricerche"] * PREZZO_RICERCA
    finale, avviso_dato, letture = None, False, 0
    for giro in range(MAX_GIRI):
        segna_cache(messaggi)
        risposta = chiama_api(chiave, {"model": MODELLO, "max_tokens": 32000, "system": sistema, "tools": STRUMENTI, "messages": messaggi})
        u = risposta.get("usage", {})
        for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
            uso[k] += u.get(k) or 0
        uso["ricerche"] += (u.get("server_tool_use") or {}).get("web_search_requests") or 0
        messaggi.append({"role": "assistant", "content": risposta["content"]})
        motivo = risposta.get("stop_reason")
        print(f"giro {giro + 1}: {motivo}, costo finora {costo():.2f} $")
        if motivo == "pause_turn":
            continue
        if motivo == "tool_use":
            risultati = []
            for b in risposta["content"]:
                if b.get("type") == "tool_use":
                    letture += 1
                    risultati.append({"type": "tool_result", "tool_use_id": b["id"], "content": esegui_strumento(b["name"], b.get("input", {}))})
            if costo() > TETTO_DOLLARI and not avviso_dato:
                risultati.append({"type": "text", "text": "Tetto di spesa raggiunto: non usare altri strumenti e scrivi ora il risultato finale con quanto verificato, indicando in note_fonti i controlli non eseguiti per questo motivo."})
                avviso_dato = True
            messaggi.append({"role": "user", "content": risultati})
            continue
        finale = "".join(b.get("text", "") for b in risposta["content"] if b.get("type") == "text")
        if "===JSON_INIZIO===" not in finale and motivo == "max_tokens":
            messaggi.append({"role": "user", "content": "Continua da dove ti sei fermato."})
            continue
        break

    m = re.search(r"===JSON_INIZIO===\s*(.*?)\s*===JSON_FINE===", finale or "", re.S)
    try:
        esito = json.loads(re.sub(r"^```(json)?|```$", "", m.group(1).strip(), flags=re.M)) if m else None
    except Exception:
        esito = None
    CARTELLA.mkdir(parents=True, exist_ok=True)
    adesso = datetime.now(timezone.utc)
    if esito is None:
        (CARTELLA / f"{oggi.isoformat()} risposta non valida.txt").write_text(finale or "(nessuna risposta finale)", encoding="utf-8")
        print("Risposta finale senza JSON valido")
    else:
        esito["generato_alle_utc"] = adesso.isoformat(timespec="seconds")
        esito["modello"] = MODELLO
        esito["costo_stimato_dollari"] = round(costo(), 3)
        (CARTELLA / f"{oggi.isoformat()}.json").write_text(json.dumps(esito, ensure_ascii=False, indent=1), encoding="utf-8")
        md = [f"# Analisi del {oggi:%d-%m-%Y}", "", f"Finestra dal {esito.get('finestra', {}).get('dal', '')} al {esito.get('finestra', {}).get('al', '')}. "
              f"Modello {MODELLO}. Costo stimato {costo():.2f} $.", "", esito.get("autoverifica", ""), "", "## Voci", ""]
        for v in esito.get("voci", []):
            md += [f"### {v.get('titolo', '')} ({v.get('rilevanza', '')}, {v.get('area', '')})", "",
                   f"{v.get('data', '')} · {v.get('fonte', '')} · [{v.get('url', '')}]({v.get('url', '')})", "", v.get("descrizione", ""), ""]
        md += ["## Monitoraggi", ""] + [f"- {x.get('id')}: {x.get('esito')}. {x.get('nota', '')}" for x in esito.get("monitoraggi", [])]
        md += ["", "## Fonti proposte", ""] + [f"- {x.get('nome')}: {x.get('url')} ({x.get('motivo', '')})" for x in esito.get("fonti_proposte", [])]
        md += ["", "## Note sulle fonti", ""] + [f"- {x}" for x in esito.get("note_fonti", [])]
        (CARTELLA / f"{oggi.isoformat()}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        (CARTELLA / "stato.json").write_text(json.dumps({"ultima_finestra_al": raccolta["finestra_al"], "ultima_analisi": oggi.isoformat()}, indent=1), encoding="utf-8")
        print(f"Voci: {len(esito.get('voci', []))}")
    with open(CARTELLA / "costi.csv", "a", encoding="utf-8") as s:
        if s.tell() == 0:
            s.write("data_utc,modello,giri,letture,ricerche,input,output,cache_scrittura,cache_lettura,costo_dollari,esito\n")
        s.write(f"{adesso:%Y-%m-%d %H:%M},{MODELLO},{giro + 1},{letture},{uso['ricerche']},{uso['input_tokens']},{uso['output_tokens']},"
                f"{uso['cache_creation_input_tokens']},{uso['cache_read_input_tokens']},{costo():.3f},{'ok' if esito else 'senza JSON'}\n")
    print(f"Costo stimato: {costo():.2f} $; token: {uso}")
    return 0 if esito else 2


if __name__ == "__main__":
    sys.exit(main())
