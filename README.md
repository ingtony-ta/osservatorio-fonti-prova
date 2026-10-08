# Osservatorio fonti, prova di fattibilità

Prova per capire se GitHub Actions riesce a leggere le fonti pubbliche dell'osservatorio normativo.
Una volta al giorno (e a richiesta dal pulsante «Run workflow») il programma `controlla_fonti.py`
chiede 16 fonti pubbliche e scrive in `esiti/` il codice di risposta, il peso della pagina e l'impronta
del contenuto, confrontata con quella dell'esecuzione precedente. Il programma `estrai_novita.py` ricava
inoltre da sala stampa della Commissione, consultazioni Have Your Say e due feed le voci pertinenti al dominio
(`esiti/novita.md`), segnando le nuove.

Contiene solo indirizzi di fonti pubbliche e gli esiti delle richieste. Nessun dato di clienti.

## Analisi con il modello

Nei giorni pari del mese (e a richiesta) il flusso «Analisi delle novità con il modello» esegue `raccogli.py`, che legge le fonti con
dati strutturati (Gazzetta UE via SPARQL, sala stampa e consultazioni della Commissione, feed pubblici italiani e UE), e poi
`analizza.py`, che passa il materiale a un modello Claude via API con le istruzioni di `istruzioni_analista.md`. Il modello
esamina la raccolta, fa ricerche complementari sul web, verifica le voci sulla fonte ufficiale e scrive in `esiti/analisi/`
il file del giorno (`.json` e `.md`). Token e costo stimato di ogni esecuzione sono in `esiti/analisi/costi.csv`.
La chiave API sta nei secret del repository e non compare in nessun file. Solo fonti pubbliche, nessun dato di clienti.
