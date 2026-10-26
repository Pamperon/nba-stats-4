# Basket Lab — verifica del 26 ottobre 2026

Analisi di soli archivi prepartita, con tabellini finali ESPN e identità esatte.
Nessuna chiamata OddsPapi, nessuna scansione manuale e nessuna modifica agli archivi.

## Campione e origine

Gli archivi pubblici del 20–22 ottobre rispondono 404: non sono stati ricreati.
Sono disponibili quattro date, 23–26 ottobre. Questo report usa l'ultimo snapshot
pubblico di ogni data. Le tabelle di calibrazione già consolidate usano invece
il primo snapshot completo: i due campioni non vanno sommati o confusi.
Le linee alternative dello stesso giocatore sono correlate.

| Data italiana | Linee con esito binario verificato | Singola | Doppia | Tripla |
|---|---:|---|---|---|
| 2026-10-23 | 228 | Vinta | Vinta | Incompleta |
| 2026-10-24 | 2154 | Persa | Esito incompleto/assente | Persa |
| 2026-10-25 | 306 | Vinta | Persa | Persa |
| 2026-10-26 | 840 | Esito incompleto/assente | Persa | Persa |

Le proposte storiche sono **ricostruzioni delle regole precedenti dell'interfaccia**,
non registrazioni di ciò che un visitatore aveva visualizzato. I giocatori assenti
non sono conteggiati come sconfitte. Non si presume un regolamento di rimborso.
I ticket con almeno una selezione perdente sono indicati come persi; i casi mancanti
senza selezioni perdenti restano irrisolti. Il rendimento, se presente nel JSON,
è puramente teorico e non rappresenta il registro delle giocate dell'utente.

## Calibrazione

L'ultimo snapshot per data produce 3.528 esiti binari: Brier originale
0,12140845, candidato 0,12117718. Miglioramento 0,00023127, sotto la soglia
preesistente di 0,001. La calibrazione pertanto NON viene forzata.
Il controllo già consolidato nel database dà 3.498 esiti e miglioramento 0,00018402:
la conclusione è la stessa. La valutazione usa solo giorni precedenti per ogni giorno
esaminato, con nessun risultato futuro nel relativo addestramento.

Corretto anche un disallineamento: le fasce estreme (<10% e ≥90%) escluse dalla
validazione non vengono più corrette dal percorso live. Nessun cambiamento
ai pesi 80% storico / 20% ultime 20 né alla formula di Jeffreys.
La procedura automatica continuerà a consolidare le giornate concluse e a riesaminare
l'attivazione dopo le scansioni programmate, solo quando passa i controlli.

## Minutaggio

Una sola linea, scelta con valore stimato prepartita, per giocatore/mercato/partita,
limitando le quote a 1,20–2,00:

| Minuti | Casi verificati | Successi | Frequenza | Stima media |
|---|---:|---:|---:|---:|
| Nessun forte calo | 561 | 342 | 60,96% | 63,14% |
| Forte calo | 27 | 15 | 55,56% | 67,41% |

Il sottogruppo è piccolo e non dimostra il vantaggio futuro del filtro.
Applicato un filtro **prudenziale di selezione**, senza penalità numeriche alle stime:
almeno 15 partite, ultime 5 sotto il 75% dei minuti medi e calo di almeno 5 minuti.
Questo non modifica i risultati storici o elimina le righe dalla tabella completa.
Gli archivi contengono Over: manca una base per confrontare Over e Under.

## Disponibilità e tracciamento

Dalle prossime scansioni, un controllo del report infortuni ESPN, con ID esatti,
esclude dai suggerimenti i giocatori Out, Doubtful, Questionable, Day-To-Day e sospesi.
Se il report non è verificabile o è più vecchio di 30 minuti, non si presume che i
giocatori siano disponibili. Non essere nel report non garantisce che giocheranno.
Il controllo avviene alla scansione, non continuamente tra due scansioni.
Il report infortuni corrente NON viene applicato retroattivamente al backtest.

Ogni nuovo snapshot salva policy e selezioni esatte di Singola/Doppia/Tripla.
L'interfaccia non sostituisce una selezione archiviata se una partita è iniziata.
Le nuove proposte vengono valutate automaticamente dalla procedura di consolidamento
già programmata: una voce per snapshot, senza duplicati. Il registro separato
`nba_recommendation_results` conserva selezioni, quote, stime ed esiti anche dopo
la pulizia degli archivi grezzi. I risultati mancanti restano irrisolti, senza
presumere rimborsi. È consultabile con l’endpoint autenticato
`/api/calibration/recommendation-results`.

Il comando `python -m scripts.model_review --dates 2026-10-23 2026-10-24 2026-10-25 2026-10-26`
consente di ripetere il controllo con soli archivi e ESPN. Per i nuovi snapshot
legge le selezioni effettivamente salvate; per i vecchi dichiara la ricostruzione.

Il lavoro sostituisce l'analisi della PR #22. La PR non viene integrata alla cieca:
il confronto aggiornato è riproducibile in `scripts/model_review.py`.
