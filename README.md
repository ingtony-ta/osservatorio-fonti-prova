# Osservatorio fonti, prova di fattibilità

Prova per capire se GitHub Actions riesce a leggere le fonti pubbliche dell'osservatorio normativo.
Una volta al giorno (e a richiesta dal pulsante «Run workflow») il programma `controlla_fonti.py`
chiede 17 fonti pubbliche e scrive in `esiti/` il codice di risposta, il peso della pagina e l'impronta
del contenuto, confrontata con quella dell'esecuzione precedente.

Contiene solo indirizzi di fonti pubbliche e gli esiti delle richieste. Nessun dato di clienti.
