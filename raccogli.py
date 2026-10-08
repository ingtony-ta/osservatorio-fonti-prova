"""Raccolta del materiale grezzo per l'analista (prima fase, senza modello).

Legge le fonti con dati strutturati e scrive `esiti/analisi/raccolta.json`: atti nuovi e collegati in Gazzetta UE
(SPARQL dell'Ufficio pubblicazioni), sala stampa della Commissione, consultazioni Have Your Say, feed pubblici
(Consiglio UE, Gazzetta Ufficiale serie generale e serie UE, Governo, MIMIT, Ministero della salute, notizie della
Commissione) e una prova di lettura di un feed pubblico di EUR-Lex. Solo fonti pubbliche, nessun dato di clienti.
"""
import csv
import io
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import estrai_novita as en

UA = "Mozilla/5.0 (compatible; osservatorio-fonti-prova/1.0)"
CARTELLA = Path("esiti/analisi")

# atti di riferimento (elenco 1.1 delle fonti fisse dell'osservatorio)
CELEX_RIFERIMENTO = """32023R0988 32019R1020 32008R0765 32008D0768 32019R0515 32025R0040 32008L0098 32019L0904
32014L0035 32014L0030 32014L0053 32011L0065 32012L0019 32023R1542 32006R1907 32008R1272 32019R1021 32012R0528
32004R0648 32026R0405 32024R0573 32009L0048 32025R2509 32006L0042 32023R1230 32016R0425 32016R0426 32014L0068
32024R1781 32009L0125 32017R1369 32004R1935 32011R0010 32009R1223 32024L0825 32024L1799 32024L2853 32005L0029
32019L0771 32024R2847 32024R1689 32022R2065 32023R2854 32011R0305 32024R3110 32020L2184 32023R1115 32013R0952
32023R0956 32019R1009 32011R1007 31975L0324 32006D0502 32017R0745""".split()

FEED = [
    ("https://www.gazzettaufficiale.it/rss/SG", "Gazzetta Ufficiale, serie generale", "gusg"),
    ("https://www.governo.it/feed/rss", "Governo", "gov"),
    ("https://www.mimit.gov.it/it/notizie-stampa?format=feed&type=rss", "MIMIT, notizie", "mimit"),
    ("https://www.salute.gov.it/new/rss/RSS_comunicati.xml", "Ministero della salute, comunicati", "sal"),
    ("https://commission.europa.eu/node/33506/rss_en", "Commissione, notizie", "ecn"),
]
# feed pubblico di EUR-Lex (Gazzetta UE serie L): serve a capire se da GitHub i feed di EUR-Lex si leggono
FEED_PROVA_EURLEX = "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=222"


def scarica(url, accept="*/*", timeout=60):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(r, timeout=timeout) as x:
        return x.status, x.read()


def sparql(query):
    url = "https://publications.europa.eu/webapi/rdf/sparql?" + urllib.parse.urlencode({"query": query})
    _, dati = scarica(url, accept="text/csv", timeout=120)
    return list(csv.DictReader(io.StringIO(dati.decode("utf-8"))))


PREFISSO = "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
ITA = "<http://publications.europa.eu/resource/authority/language/ITA>"


def atti_nuovi(da):
    q = PREFISSO + f"""SELECT ?celex ?date ?title WHERE {{
 ?w cdm:resource_legal_id_celex ?celex . ?w cdm:work_date_document ?date .
 FILTER(?date >= "{da}"^^xsd:date && STRSTARTS(STR(?celex),"3") && !CONTAINS(STR(?celex),"R("))
 ?e cdm:expression_belongs_to_work ?w . ?e cdm:expression_uses_language {ITA} . ?e cdm:expression_title ?title
}} ORDER BY DESC(?date)"""
    return sparql(q)


def valori_celex():
    return " ".join(f'"{c}"^^xsd:string' for c in CELEX_RIFERIMENTO)


def atti_collegati(da):
    q = PREFISSO + f"""SELECT DISTINCT ?celex ?date ?p ?target WHERE {{
 VALUES ?target {{ {valori_celex()} }}
 VALUES ?p {{ cdm:resource_legal_amends_resource_legal cdm:resource_legal_based_on_resource_legal
   cdm:resource_legal_corrects_resource_legal cdm:resource_legal_repeals_resource_legal
   cdm:resource_legal_implicitly_repeals_resource_legal }}
 ?t cdm:resource_legal_id_celex ?target . ?w ?p ?t . ?w cdm:resource_legal_id_celex ?celex .
 ?w cdm:work_date_document ?date . FILTER(?date >= "{da}"^^xsd:date) }}"""
    return sparql(q)


def atti_che_citano(da):
    q = PREFISSO + f"""SELECT ?celex ?date (GROUP_CONCAT(DISTINCT ?target; separator=" ") AS ?atti) (SAMPLE(?tit) AS ?titolo) WHERE {{
 VALUES ?target {{ {valori_celex()} }}
 VALUES ?p {{ cdm:work_cites_work cdm:case-law_interpretes_resource_legal
   cdm:communication_case_new_submits_preliminary_question_resource_legal }}
 ?t cdm:resource_legal_id_celex ?target . ?w ?p ?t . ?w cdm:resource_legal_id_celex ?celex .
 ?w cdm:work_date_document ?date . FILTER(?date >= "{da}"^^xsd:date)
 FILTER(REGEX(STR(?celex), "^(3|5[0-9]{{4}}(PC|DC|XC|AG|AP)|6[0-9]{{4}}(CJ|TJ|CN|CC))"))
 OPTIONAL {{ ?e cdm:expression_belongs_to_work ?w . ?e cdm:expression_uses_language {ITA} . ?e cdm:expression_title ?tit }}
}} GROUP BY ?celex ?date ORDER BY DESC(?date)"""
    return sparql(q)


def feed_generico(url, nome, prefisso):
    _, dati = scarica(url)
    radice = ET.fromstring(dati)
    out = []
    atom = "{http://www.w3.org/2005/Atom}"
    voci = list(radice.iter("item")) or list(radice.iter(atom + "entry"))
    for it in voci:
        titolo = (it.findtext("title") or it.findtext(atom + "title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not link:
            el = it.find(atom + "link")
            link = el.get("href", "") if el is not None else ""
        data = (it.findtext("pubDate") or it.findtext(atom + "updated") or it.findtext(atom + "published") or "").strip()
        try:
            data = parsedate_to_datetime(data).date().isoformat()
        except Exception:
            data = data[:10]
        desc = (it.findtext("description") or it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
                or it.findtext(atom + "summary") or "")
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()[:400]
        out.append({"fonte": nome, "id": prefisso + ":" + (link or titolo), "data": data, "titolo": titolo,
                    "descrizione": desc, "url": link})
    return out


def main():
    CARTELLA.mkdir(parents=True, exist_ok=True)
    stato_file = CARTELLA / "stato.json"
    try:
        stato = json.loads(stato_file.read_text(encoding="utf-8"))
    except Exception:
        stato = {}
    ieri = datetime.now(timezone.utc).date() - timedelta(days=1)
    if stato.get("ultima_finestra_al"):
        da = date.fromisoformat(stato["ultima_finestra_al"]) + timedelta(days=1)
    else:
        da = ieri - timedelta(days=6)
    if da > ieri:
        da = ieri
    da_sparql = da - timedelta(days=7)  # la data del documento precede la pubblicazione

    raccolta = {"finestra_da": da.isoformat(), "finestra_al": ieri.isoformat(), "sparql_da": da_sparql.isoformat(),
                "eseguita_alle_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "errori": [], "sezioni": {}}

    def prova(nome, f):
        try:
            v = f()
            raccolta["sezioni"][nome] = v
            print(f"{nome}: {len(v)}")
        except Exception as e:
            raccolta["errori"].append(f"{nome}: {type(e).__name__}: {str(e)[:150]}")
            print(f"{nome}: ERRORE {e}")

    prova("GUUE, atti nuovi (SPARQL)", lambda: atti_nuovi(da_sparql.isoformat()))
    prova("GUUE, atti collegati agli atti di riferimento (SPARQL)", lambda: atti_collegati(da_sparql.isoformat()))
    prova("GUUE, atti che citano o interpretano gli atti di riferimento (SPARQL)", lambda: atti_che_citano(da_sparql.isoformat()))
    prova("Commissione, sala stampa", en.presscorner)
    prova("Have Your Say, consultazioni aperte", en.haveyoursay)
    prova("Consiglio UE, comunicati", lambda: en.feed("https://www.consilium.europa.eu/en/rss/pressreleases.ashx", "Consiglio UE, comunicati", "cu"))
    prova("Gazzetta Ufficiale, serie UE", lambda: en.feed("https://www.gazzettaufficiale.it/rss/S2", "Gazzetta Ufficiale, serie UE", "gu"))
    for url, nome, pref in FEED:
        prova(nome, lambda url=url, nome=nome, pref=pref: feed_generico(url, nome, pref))

    try:
        codice, dati = scarica(FEED_PROVA_EURLEX)
        esito = f"HTTP {codice}, {len(dati)} byte, " + ("feed RSS" if b"<rss" in dati[:500] else "non è un feed (probabile sfida anti-bot)")
    except Exception as e:
        esito = f"{type(e).__name__}: {str(e)[:120]}"
    raccolta["prova_feed_eurlex"] = esito
    print("prova feed EUR-Lex:", esito)

    (CARTELLA / "raccolta.json").write_text(json.dumps(raccolta, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
