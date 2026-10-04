"""Prova di fattibilità: GitHub riesce a leggere le fonti pubbliche dell'osservatorio normativo?

Ogni esecuzione chiede ciascuna fonte, registra l'esito (codice, tipo, peso, impronta del contenuto)
e lo confronta con l'esecuzione precedente. Solo fonti pubbliche, nessun dato di clienti.
"""
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (compatible; osservatorio-fonti-prova/1.0)"

FONTI = [
    {"id": "sparql", "nome": "Ufficio pubblicazioni UE, SPARQL", "metodo": "GET",
     "url": "https://publications.europa.eu/webapi/rdf/sparql?query=SELECT%20%3Fc%20WHERE%20%7B%3Fw%20%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23resource_legal_id_celex%3E%20%3Fc%7D%20LIMIT%202",
     "accept": "text/csv"},
    {"id": "presscorner", "nome": "Commissione, sala stampa (API)", "metodo": "GET",
     "url": "https://ec.europa.eu/commission/presscorner/api/latestnews?language=en&pagesize=5"},
    {"id": "haveyoursay", "nome": "Have Your Say, consultazioni aperte (API)", "metodo": "GET",
     "url": "https://ec.europa.eu/info/law/better-regulation/brpapi/searchInitiatives?language=EN&page=0&size=3&feedbackStatus=OPEN"},
    {"id": "safetygate", "nome": "Safety Gate, ultime notifiche (API)", "metodo": "POST",
     "url": "https://ec.europa.eu/safety-gate-alerts/public/api/notification/mostRecent/",
     "corpo": '{"language":"en","page":"0"}', "tipo": "application/json"},
    {"id": "gazzetta30", "nome": "Gazzetta Ufficiale, serie generale (30 giorni)", "metodo": "GET",
     "url": "https://www.gazzettaufficiale.it/30giorni/serie_generale"},
    {"id": "gazzettaS2", "nome": "Gazzetta Ufficiale, feed serie UE", "metodo": "GET",
     "url": "https://www.gazzettaufficiale.it/rss/S2"},
    {"id": "consilium", "nome": "Consiglio UE, feed comunicati", "metodo": "GET",
     "url": "https://www.consilium.europa.eu/en/rss/pressreleases.ashx"},
    {"id": "governo", "nome": "Governo, archivio riunioni", "metodo": "GET",
     "url": "https://www.governo.it/it/archivio-riunioni"},
    {"id": "mase", "nome": "Ministero dell'ambiente, notizie", "metodo": "GET",
     "url": "https://www.mase.gov.it/portale/web/guest/notizie"},
    {"id": "mimit", "nome": "MIMIT, notizie", "metodo": "GET",
     "url": "https://www.mimit.gov.it/it/notizie-stampa"},
    {"id": "camera", "nome": "Camera, atti del Governo", "metodo": "GET",
     "url": "https://www.camera.it/leg19/142"},
    {"id": "adm", "nome": "Agenzia delle dogane, circolari", "metodo": "GET",
     "url": "https://www.adm.gov.it/portale/circolari-dogane"},
    {"id": "agcm", "nome": "AGCM, comunicati", "metodo": "GET",
     "url": "https://www.agcm.it/Media-e-Comunicazione/comunicati-stampa/index"},
    {"id": "eurlex", "nome": "EUR-Lex (atto di prova, noto per la sfida anti-bot)", "metodo": "GET",
     "url": "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32023R0988"},
    {"id": "echa", "nome": "ECHA, notizie (noto 403)", "metodo": "GET",
     "url": "https://echa.europa.eu/news"},
    {"id": "europen", "nome": "Tracker EUROPEN sugli atti PPWR", "metodo": "GET",
     "url": "https://www.ppwrtracker-europen.eu/"},
    {"id": "greenforum", "nome": "Commissione, pagina di attuazione PPWR", "metodo": "GET",
     "url": "https://green-forum.ec.europa.eu/packaging-and-packaging-waste-regulation-implementation_en"},
]


def chiedi(f):
    corpo = f.get("corpo", "").encode("utf-8") if f.get("corpo") else None
    richiesta = urllib.request.Request(f["url"], data=corpo, method=f["metodo"])
    richiesta.add_header("User-Agent", UA)
    richiesta.add_header("Accept", f.get("accept", "*/*"))
    if corpo:
        richiesta.add_header("Content-Type", f.get("tipo", "application/json"))
    try:
        with urllib.request.urlopen(richiesta, timeout=30) as r:
            dati = r.read()
            return {"codice": r.status, "tipo": r.headers.get("Content-Type", ""), "byte": len(dati),
                    "impronta": hashlib.sha256(dati).hexdigest()[:16], "url_finale": r.geturl()}
    except urllib.error.HTTPError as e:
        return {"codice": e.code, "tipo": e.headers.get("Content-Type", "") if e.headers else "", "byte": 0, "impronta": "", "errore": str(e)}
    except Exception as e:  # rete, timeout, certificato
        return {"codice": 0, "tipo": "", "byte": 0, "impronta": "", "errore": type(e).__name__ + ": " + str(e)[:120]}


def main():
    adesso = datetime.now(timezone.utc)
    cartella = Path("esiti")
    cartella.mkdir(exist_ok=True)
    precedente = {}
    ultimo = cartella / "ultimo.json"
    if ultimo.exists():
        try:
            precedente = {r["id"]: r for r in json.loads(ultimo.read_text(encoding="utf-8"))["fonti"]}
        except Exception:
            precedente = {}
    righe = []
    for f in FONTI:
        e = chiedi(f)
        e.update({"id": f["id"], "nome": f["nome"]})
        p = precedente.get(f["id"])
        e["cambiata"] = bool(p and p.get("impronta") and e["impronta"] and p["impronta"] != e["impronta"])
        righe.append(e)
        print(f"{e['codice']:>3}  {e['byte']:>8} B  {f['id']:<12} {e.get('errore', '')}")
    risultato = {"eseguito_alle_utc": adesso.isoformat(timespec="seconds"), "fonti": righe}
    ultimo.write_text(json.dumps(risultato, ensure_ascii=False, indent=1), encoding="utf-8")
    # una risposta vuota (per esempio 202 della sfida anti-bot) non conta come fonte raggiunta
    ok = sum(1 for r in righe if 200 <= r["codice"] < 300 and r["byte"] > 0)
    md = [f"# Esito del {adesso:%d-%m-%Y %H:%M} UTC", "", f"Fonti raggiunte: {ok} su {len(righe)}.", "",
          "| Fonte | Codice | Peso | Cambiata dall'ultima volta |", "|---|---|---|---|"]
    for r in righe:
        md.append(f"| {r['nome']} | {r['codice'] or 'errore'} | {r['byte']} B | {'sì' if r['cambiata'] else 'no'} |")
    (cartella / "ultimo.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    # storico sintetico: una riga per esecuzione
    with open(cartella / "storico.csv", "a", encoding="utf-8") as s:
        if s.tell() == 0:
            s.write("data_utc,raggiunte,totali," + ",".join(f["id"] for f in FONTI) + "\n")
        s.write(f"{adesso:%Y-%m-%d %H:%M},{ok},{len(righe)}," + ",".join(str(r["codice"]) for r in righe) + "\n")
    # estrazione delle novità dalle fonti con dati strutturati (un errore qui non ferma il controllo delle fonti)
    try:
        import estrai_novita
        estrai_novita.main()
    except Exception as e:
        print("estrazione delle novità non riuscita:", type(e).__name__, e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
