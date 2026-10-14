# Fonti fisse dell'osservatorio

Aggiornate al 09-10-2026 (note sulle prove dal cloud del giro del 09-10-2026 per la terza interrogazione SPARQL, la «Prima pagina» della Camera e la home di LAB-TO; decisione dell'utente del 09-10-2026). Modifiche del 07-10-2026 (decisioni dell'utente: aggiunte la «Prima pagina» della Camera e la home di LAB-TO, sezioni 4 e 5; terza interrogazione SPARQL sugli atti che citano o interpretano gli atti dell'elenco 1.1, sezione 1, punto 3; Safety Gate tolto dalle fonti, perché notifiche e rapporti settimanali li tratta la routine del venerdì; aggiunte le due fonti proposte dal bollettino del 07-10-2026, DG GROW pubblicazioni e dati aperti del Senato). Fonti da controllare a ogni giro, con il metodo di accesso provato dal cloud il 03-10-2026. Una fonte nuova entra in questo elenco solo su decisione dell'utente: l'agente la propone nel bollettino, sezione «Fonti nuove proposte».

Metodi:
- **SPARQL**: `curl -G https://publications.europa.eu/webapi/rdf/sparql --data-urlencode "query=..." -H "Accept: text/csv"`. Funziona. EUR-Lex (`eur-lex.europa.eu`) e i suoi feed RSS sono bloccati da una sfida anti-bot: non usarli.
- **Cellar**: testo integrale di un atto con `curl -sL -H "Accept: application/xhtml+xml" -H "Accept-Language: ita" https://publications.europa.eu/resource/celex/<CELEX>`. Il PDF non è disponibile da Cellar.
- **Presscorner API**: `https://ec.europa.eu/commission/presscorner/api/latestnews?language=en&pagesize=50`; ricerca `.../api/search?language=en&text=<parola>&pagesize=50` (filtra solo `text`; ordinare per `eventDate`); testo `.../api/documents?reference=<refCode>&language=en` (campo `htmlContent`); PDF `.../api/files/document/print/en/<ref minuscolo con _>/<REF_MAIUSCOLO>_EN.pdf`.
- **Web**: WebFetch, e se fallisce curl.

## 1. Gazzetta ufficiale dell'Unione europea (SPARQL e Cellar)

Tre interrogazioni a ogni giro, sulla finestra del giro:

1. **Atti nuovi** con CELEX che inizia per `3` (atti legislativi e non legislativi) e data del documento nella finestra, titolo in italiano; escludere consolidati (`0...`). Le rettifiche (`...R(nn)`) si tengono solo se toccano la versione italiana o un atto dell'elenco 1.1. Leggere tutti i titoli e aprire con Cellar ogni atto nel dominio (criteri nelle istruzioni). Esempio di query provata:
```
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex ?date ?title WHERE {
 ?w cdm:resource_legal_id_celex ?celex . ?w cdm:work_date_document ?date .
 FILTER(?date >= "AAAA-MM-GG"^^xsd:date && STRSTARTS(STR(?celex),"3"))
 ?e cdm:expression_belongs_to_work ?w .
 ?e cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ITA> .
 ?e cdm:expression_title ?title } ORDER BY DESC(?date)
```
2. **Atti collegati** agli atti dell'elenco 1.1: atti che li modificano, li rettificano, li abrogano o li citano come base giuridica, con data nella finestra. Query provata il 03-10-2026 (25 righe sulla finestra di prova):
```
SELECT DISTINCT ?celex ?date ?p ?target WHERE {
 VALUES ?target { "32023R0988"^^xsd:string ... (tutti i CELEX dell'elenco 1.1) }
 VALUES ?p { cdm:resource_legal_amends_resource_legal cdm:resource_legal_based_on_resource_legal
   cdm:resource_legal_corrects_resource_legal cdm:resource_legal_repeals_resource_legal
   cdm:resource_legal_implicitly_repeals_resource_legal }
 ?t cdm:resource_legal_id_celex ?target . ?w ?p ?t . ?w cdm:resource_legal_id_celex ?celex .
 ?w cdm:work_date_document ?date . FILTER(?date >= "AAAA-MM-GG"^^xsd:date) }
```
   La proprietà `implements` non dà risultati. Le decisioni sulle norme armonizzate (base giuridica Reg. (UE) 1025/2012) non escono da questa query: si trovano con quella degli atti nuovi.
3. **Atti che citano o interpretano** gli atti dell'elenco 1.1, con data nella finestra: comunicazioni e orientamenti della Commissione in serie C, proposte e comunicazioni COM, posizioni del Consiglio e del Parlamento, sentenze e domande di pronuncia pregiudiziale. Coprono ciò che le prime due interrogazioni non vedono, perché questi documenti citano l'atto senza modificarlo né averlo come base giuridica. Query provata il 07-10-2026 dal PC (sotto un secondo con tutti i 54 CELEX; 6 righe sulla finestra dal 28-09-2026) e dal cloud nel giro del 09-10-2026 (HTTP 200, 6 righe):
```
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex ?date (GROUP_CONCAT(DISTINCT ?target; separator=" ") AS ?atti) (SAMPLE(?tit) AS ?titolo) WHERE {
 VALUES ?target { "32023R0988"^^xsd:string ... (tutti i CELEX dell'elenco 1.1) }
 VALUES ?p { cdm:work_cites_work cdm:case-law_interpretes_resource_legal
   cdm:communication_case_new_submits_preliminary_question_resource_legal }
 ?t cdm:resource_legal_id_celex ?target . ?w ?p ?t . ?w cdm:resource_legal_id_celex ?celex .
 ?w cdm:work_date_document ?date . FILTER(?date >= "AAAA-MM-GG"^^xsd:date)
 FILTER(REGEX(STR(?celex), "^(3|5[0-9]{4}(PC|DC|XC|AG|AP)|6[0-9]{4}(CJ|TJ|CN|CC))"))
 OPTIONAL { ?e cdm:expression_belongs_to_work ?w .
   ?e cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ITA> .
   ?e cdm:expression_title ?tit }
} GROUP BY ?celex ?date ORDER BY DESC(?date)
```
   Il filtro sul CELEX tiene: atti del settore 3; nel settore 5 le proposte (PC), le comunicazioni (DC), gli avvisi e gli orientamenti in serie C (XC), le posizioni del Consiglio (AG) e del Parlamento (AP); nel settore 6 le sentenze della Corte e del Tribunale (CJ, TJ), le domande di pronuncia pregiudiziale (CN) e le conclusioni degli avvocati generali (CC). Esclusi i documenti di lavoro dei servizi (SC), che accompagnano le proposte, e i ricorsi al Tribunale (TN), quasi tutti su singole autorizzazioni di biocidi. Le righe con codice CELEX del settore 3 già uscite dalle interrogazioni 1 e 2 non si contano due volte. Se il titolo italiano manca (capita per le proposte appena adottate), leggere il titolo e il testo con Cellar in inglese (`Accept-Language: eng`). Gli atti che citano il codice doganale (32013R0952) comprendono molti avvisi antidumping e antisovvenzioni: si tengono solo se riguardano sicurezza o conformità dei prodotti. Ogni riga si valuta con i criteri di rilevanza delle istruzioni (sezioni 4.4 e 5) e si riporta nella sezione fonti come riga propria: «GUUE, atti che citano o interpretano gli atti dell'elenco 1.1 (SPARQL)».

Limite noto, per tutte e tre le interrogazioni: il filtro è sulla data del documento, non sulla data di pubblicazione in Gazzetta; la finestra si allarga quindi di 7 giorni all'indietro e i doppioni si tolgono con il registro delle voci.

### 1.1 Atti di riferimento (CELEX da verificare al primo giro con SPARQL: titolo e esistenza)

| Area | Atto | CELEX |
|---|---|---|
| GPSR e vigilanza | Reg. (UE) 2023/988 GPSR | 32023R0988 |
| GPSR e vigilanza | Reg. (UE) 2019/1020 vigilanza del mercato | 32019R1020 |
| GPSR e vigilanza | Reg. (CE) 765/2008 | 32008R0765 |
| GPSR e vigilanza | Dec. 768/2008/CE | 32008D0768 |
| GPSR e vigilanza | Reg. (UE) 2019/515 mutuo riconoscimento | 32019R0515 |
| Imballaggi | Reg. (UE) 2025/40 PPWR | 32025R0040 |
| Imballaggi e rifiuti | Dir. 2008/98/CE rifiuti | 32008L0098 |
| Imballaggi e rifiuti | Dir. (UE) 2019/904 plastica monouso | 32019L0904 |
| Prodotti elettrici | Dir. 2014/35/UE LVD | 32014L0035 |
| Prodotti elettrici | Dir. 2014/30/UE EMC | 32014L0030 |
| Prodotti elettrici | Dir. 2014/53/UE RED | 32014L0053 |
| Prodotti elettrici | Dir. 2011/65/UE RoHS | 32011L0065 |
| Prodotti elettrici | Dir. 2012/19/UE RAEE | 32012L0019 |
| Batterie | Reg. (UE) 2023/1542 | 32023R1542 |
| Sostanze chimiche | Reg. (CE) 1907/2006 REACH | 32006R1907 |
| Sostanze chimiche | Reg. (CE) 1272/2008 CLP | 32008R1272 |
| Sostanze chimiche | Reg. (UE) 2019/1021 POPs | 32019R1021 |
| Sostanze chimiche | Reg. (UE) 528/2012 biocidi | 32012R0528 |
| Sostanze chimiche | Reg. (CE) 648/2004 detergenti | 32004R0648 |
| Sostanze chimiche | Reg. (UE) 2026/405 detergenti | 32026R0405 |
| Sostanze chimiche | Reg. (UE) 2024/573 gas fluorurati | 32024R0573 |
| Giocattoli | Dir. 2009/48/CE | 32009L0048 |
| Giocattoli | Reg. (UE) 2025/2509 | 32025R2509 |
| Macchine | Dir. 2006/42/CE | 32006L0042 |
| Macchine | Reg. (UE) 2023/1230 | 32023R1230 |
| DPI | Reg. (UE) 2016/425 | 32016R0425 |
| Apparecchi a gas | Reg. (UE) 2016/426 | 32016R0426 |
| Attrezzature a pressione | Dir. 2014/68/UE PED | 32014L0068 |
| Ecodesign | Reg. (UE) 2024/1781 ESPR | 32024R1781 |
| Ecodesign | Dir. 2009/125/CE | 32009L0125 |
| Ecodesign | Reg. (UE) 2017/1369 etichettatura energetica | 32017R1369 |
| MOCA | Reg. (CE) 1935/2004 | 32004R1935 |
| MOCA | Reg. (UE) 10/2011 plastica | 32011R0010 |
| Cosmetici | Reg. (CE) 1223/2009 | 32009R1223 |
| Consumatori | Dir. (UE) 2024/825 transizione verde | 32024L0825 |
| Consumatori | Dir. (UE) 2024/1799 riparazione | 32024L1799 |
| Consumatori | Dir. (UE) 2024/2853 responsabilità prodotti difettosi | 32024L2853 |
| Consumatori | Dir. 2005/29/CE pratiche commerciali sleali | 32005L0029 |
| Consumatori | Dir. (UE) 2019/771 vendita di beni | 32019L0771 |
| Digitale | Reg. (UE) 2024/2847 CRA | 32024R2847 |
| Digitale | Reg. (UE) 2024/1689 AI Act | 32024R1689 |
| Digitale | Reg. (UE) 2022/2065 DSA | 32022R2065 |
| Digitale | Reg. (UE) 2023/2854 Data Act | 32023R2854 |
| Costruzioni | Reg. (UE) 305/2011 CPR | 32011R0305 |
| Costruzioni | Reg. (UE) 2024/3110 CPR nuovo | 32024R3110 |
| Acque potabili | Dir. (UE) 2020/2184 | 32020L2184 |
| Deforestazione | Reg. (UE) 2023/1115 EUDR | 32023R1115 |
| Dogane | Reg. (UE) 952/2013 codice doganale | 32013R0952 |
| Dogane | Reg. (UE) 2023/956 CBAM | 32023R0956 |
| Fertilizzanti | Reg. (UE) 2019/1009 | 32019R1009 |
| Tessili | Reg. (UE) 1007/2011 | 32011R1007 |
| Aerosol | Dir. 75/324/CEE | 31975L0324 |
| Accendini | Dec. 2006/502/CE | 32006D0502 |
| Dispositivi medici | Reg. (UE) 2017/745 MDR | 32017R0745 |

## 2. Commissione europea

| Fonte | Accesso | Cosa cercare |
|---|---|---|
| Sala stampa (presscorner) | Presscorner API: `latestnews` e `search` con `text` = packaging, product safety, market surveillance, chemicals, REACH, batteries, toys, ecodesign, consumer, customs, imballaggi | comunicati, domande e risposte, procedure di infrazione (INF) su atti dell'elenco 1.1 |
| DG GROW, notizie | https://single-market-economy.ec.europa.eu/news_en | campagne di vigilanza (JACOP, ADCO, EEPLIANT), PPWR, GPSR |
| DG GROW, pubblicazioni | https://single-market-economy.ec.europa.eu/publications_en (leggibile con curl, prova del 07-10-2026) | proposte, allegati e valutazioni d'impatto in PDF prima dell'indicizzazione in EUR-Lex e Cellar |
| DG ENV, notizie | https://environment.ec.europa.eu/news_en | consultazioni su atti delegati (batterie, EUDR, ESPR, REACH), PPWR |
| Have Your Say, consultazioni | API: elenco `https://ec.europa.eu/info/law/better-regulation/brpapi/searchInitiatives?language=EN&page=0&size=100&feedbackStatus=OPEN` (risultati in `initiativeResultDtoPage.content`; con `text=<termine>` serve anche `language`; `sort=publishedDate,DESC` dà 406); dettaglio `.../brpapi/groupInitiatives/<id>` (provate il 03-10-2026) | consultazioni aperte su atti delegati e di esecuzione |
| PPWR, pagina di attuazione | https://green-forum.ec.europa.eu/packaging-and-packaging-waste-regulation-implementation_en | cambi nella timeline degli atti secondari, linee guida, FAQ |
| EU Law Tracker | https://law-tracker.europa.eu/ (pagina JavaScript: provare un'API, altrimenti «non letta») | accordi di trilogo |

## 3. Altre istituzioni UE

| Fonte | Accesso | Cosa cercare |
|---|---|---|
| Parlamento europeo, notizie | https://www.europarl.europa.eu/news/en (provare anche l'Osservatorio legislativo, OEIL) | accordi provvisori, voti in plenaria su atti del dominio |
| Consiglio UE, comunicati | sito in 403 anche a curl; leggibile il feed RSS https://www.consilium.europa.eu/en/rss/pressreleases.ashx (pochi giorni) e il registro documenti https://data.consilium.europa.eu/ in PDF | orientamenti generali, accordi, adozioni |
| ECHA | https://echa.europa.eu/news | lista delle sostanze candidate, restrizioni |

## 4. Italia

| Fonte | Accesso | Cosa cercare |
|---|---|---|
| Gazzetta Ufficiale, Serie generale | https://www.gazzettaufficiale.it/30giorni/serie_generale e ogni Gazzetta della finestra (leggibile da WebFetch il 03-10-2026) | decreti legislativi e ministeriali, recepimenti, sanzioni, vigilanza (criteri nelle istruzioni, sezione 5) |
| Gazzetta Ufficiale, serie UE | https://www.gazzettaufficiale.it/rss/S2 | riscontro degli atti UE |
| Agenzia delle dogane (ADM) | https://www.adm.gov.it/portale/circolari-dogane e https://www.adm.gov.it/portale/comunicati-stampa-adm (leggibili il 03-10-2026) | circolari e note su controlli di sicurezza prodotti e imballaggi all'importazione, riemissione della circolare 18/2026 |
| Ministero dell'ambiente (MASE) | https://www.mase.gov.it/portale/web/guest/notizie e https://www.mase.gov.it/portale/comunicati-stampa | PPWR, autorità competente, decreti |
| MIMIT | https://www.mimit.gov.it/it/notizie-stampa e https://www.mimit.gov.it/it/assistenza/domande-frequenti | vigilanza, codice del consumo, FAQ su green claims e D.Lgs. 30/2026 |
| Governo, Consiglio dei ministri | https://www.governo.it/it/archivio-riunioni | schemi di decreto legislativo, recepimenti |
| Camera, atti del Governo | https://www.camera.it/leg19/142; per i progetti di legge la scheda `https://www.camera.it/leg19/126?leg=19&idDocumento=<numero>` | stato degli atti del Governo e delle conversioni dei decreti-legge |
| Camera, notizie di prima pagina | https://comunicazione.camera.it/archivio-prima-pagina (leggibile con curl dal PC il 07-10-2026 e dal cloud nel giro del 09-10-2026, HTTP 200; elenco dinamico, il vecchio /feeds la apriva dal browser) | iter di recepimento delle direttive, schemi di decreto legislativo, legge di delegazione europea, tutela dei consumatori |
| Senato | https://www.senato.it/attualita/in-copertina (sfida anti-bot AWS WAF); dati aperti con SPARQL su https://dati.senato.it/sparql (provata il 07-10-2026: stato, titolo e date dei disegni di legge e documenti sugli atti del Governo) | pareri sugli schemi di decreto, stato delle conversioni dei decreti-legge |
| Normattiva | https://www.normattiva.it | riscontro degli atti italiani |
| Ministero della salute | https://www.salute.gov.it/new/it/sezione/notizie/ (anti-bot noto) | cosmetici, MOCA, biocidi, sostanze |
| REACH Italia | https://www.reach.gov.it/ | restrizioni, lista candidate |
| AGCM, comunicati | https://www.agcm.it/Media-e-Comunicazione/comunicati-stampa/index (403 a WebFetch: provare curl) | pratiche commerciali scorrette, greenwashing |
| CONAI | https://www.conai.org | FAQ e note operative sugli imballaggi |
| Unioncamere | https://www.unioncamere.gov.it/comunicazione/comunicati-stampa | sicurezza prodotti, normativa |

## 5. Settore, commenti e tracker

| Fonte | Accesso | Cosa cercare |
|---|---|---|
| Tracker EUROPEN degli atti PPWR | https://www.ppwrtracker-europen.eu/ | stato degli atti delegati e di esecuzione PPWR, consultazioni |
| EuroCommerce | https://www.eurocommerce.eu/latest/ | sicurezza prodotti, imballaggi, e-commerce |
| Cooley Product Counselor | https://products.cooley.com/ | sicurezza prodotti UE |
| HKTDC, alert normativi UE | API https://api-research.hktdc.com/v1/regulatory-alerts/eu (la pagina web è JavaScript) | requisiti di prodotto |
| Aggiornamento Normativo | https://www.aggiornamentonormativo.com/news.aspx | notizie tecniche italiane |
| Camera di commercio di Milano | https://www.milomb.camcom.it/ufficio-stampa | vigilanza, normativa |
| Laboratorio chimico della Camera di commercio di Torino (LAB-TO), home | https://www.lab-to.camcom.it/ (leggibile con curl dal PC il 07-10-2026 e dal cloud nel giro del 09-10-2026, HTTP 200) | notizie su prove, analisi, sicurezza prodotti, REACH, giocattoli; date dei webinar annunciati |

## 6. Webinar camerali (solo segnalazione nel bollettino, sezione «Webinar ed eventi»)

| Fonte | Accesso |
|---|---|
| LAB-TO, eventi | https://www.lab-to.camcom.it/eventi/ |
| Portale etichettatura, eventi della rete camerale | https://portale-etichettatura.lab-to.camcom.it/eventi/ (pagine evento senza barra finale) |
| Camera di commercio di Cuneo, calendario | https://www.cn.camcom.it/assistenza-alle-imprese/sportello-etichettatura-sicurezza-prodotti/eventi-2026 |
| UNICAdesk, normazione tecnica | https://unicadesk.camcom.it/eventi |

Per i webinar già svolti di interesse (sicurezza prodotti, chimica, imballaggi, MOCA, tessili, giocattoli, dogane, green claims, normazione tecnica; esclusi temi alimentari, sanità, marchi) segnalare se sono state pubblicate le slide, con il collegamento ai PDF. Lo scarico e la scelta delle slide (escluse quelle solo pubblicitarie) li fa la chat locale.
