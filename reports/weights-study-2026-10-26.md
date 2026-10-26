# Basket Lab — revisione storico e selezioni, 26 ottobre 2026

## Decisione

Mantenere formula pubblica e priorità alla probabilità. Le alternative non mostrano
un miglioramento stabile nei dati disponibili. Raccogliere confronti prospettici
con definizioni congelate `weights-v1`, senza promozione automatica.

Correggere invece la presentazione delle multiple: per selezioni della stessa partita
non sono stimate né quota né probabilità combinate. Il prodotto delle singole quote
non certifica una quota effettivamente offerta dal bookmaker e il prodotto delle
probabilità richiede un'ipotesi di indipendenza che qui non è verificata.

## Metodo e limiti

- Quattro giornate italiane: 23, 24, 25 e 26 ottobre 2026.
- Ultimo snapshot pubblico prepartita per ogni giornata, con i game log salvati allora.
- Risultati da tabellini ESPN finali, associati tramite identità e partita esatte.
- 588 righe confrontabili: una linea per giocatore/mercato/partita, scelta PRIMA
  dell'esito avvicinando la quota a 1,80 nella fascia 1,20–2,00. Stesse righe per tutti i modelli.
- Nessuna ricostruzione dello storico usando dati ESPN di oggi. Zero discrepanze
  nel riprodurre le probabilità grezze originali alla precisione pubblicata.
- Queste quattro date erano già state esaminate: analisi retrospettiva, non un
  holdout indipendente. I mercati dello stesso giocatore restano correlati.
- Nessuna assenza attuale è stata applicata al passato. Assenti, identità mancanti
  e casi irrisolti non diventano sconfitte. Il campione contiene soltanto Over.
- Le alternative sono state definite prima di calcolare questo confronto; nessuna
  ricerca di pesi ottimali o prova di decine di soglie.

Il Brier misura l'errore delle probabilità: più basso è meglio. I valori qui sotto
riguardano un campione diverso dal precedente report su tutte le linee e non vanno
confrontati direttamente con il suo Brier di circa 0,121.

## Peso dello storico

| Metodo | Campione | Brier complessivo | Brier con uguale peso a ogni giornata |
|---|---:|---:|---:|
| Attuale: 80% storico + 20% ultime 20 | 588 | 0.242674 | 0.235969 |
| Storico limitato alle ultime 40 | 588 | 0.244781 | 0.236462 |
| Stagione corrente + prior di 20 partite | 588 | 0.243901 | 0.235909 |

Il modello attuale usa Jeffreys su tutte le partite delle due stagioni (80%) e sulle
ultime 20 (20%). La prima alternativa mantiene la stessa formula ma limita il primo
insieme alle ultime 40. La seconda usa le ultime 40 della stagione precedente per
costruire un prior con forza fissa pari a 20 partite, e lo aggiorna con i successi
della stagione corrente: `(successi correnti + 20 × prior) / (partite correnti + 20)`.
Se manca la stagione precedente, usa Jeffreys sulla stagione corrente; se mancano
le etichette di stagione, la variante non viene inventata.

Il modello attuale ha il Brier complessivo migliore. Dando lo stesso peso alle
quattro giornate, la variante con prior ha un vantaggio di appena 0,000061: il
verdetto dipende dalla ponderazione e non sostiene un cambio di formula.

| Data | Casi | Attuale | Ultime 40 | Prior stagione corrente |
|---|---:|---:|---:|---:|
| 2026-10-23 | 37 | 0.217330 | 0.220208 | 0.219869 |
| 2026-10-24 | 360 | 0.241712 | 0.247084 | 0.245855 |
| 2026-10-25 | 52 | 0.227092 | 0.226277 | 0.225965 |
| 2026-10-26 | 139 | 0.257744 | 0.252278 | 0.251947 |

## Scelta dei suggerimenti

Le seguenti sono simulazioni delle regole attuali sulle quote archiviate, non
registrazioni di ciò che un visitatore aveva effettivamente visualizzato.
Ogni multipla viene mantenuta come blocco unico. Non si sostituisce una selezione
mancante con un'altra dopo aver conosciuto il risultato.

Le strategie confrontate sono: probabilità prima del valore (attuale), valore
stimato prima della probabilità, e probabilità con partite obbligatoriamente distinte.
Gli stessi filtri di storico, minuti e disponibilità salvata valgono per tutte.
Nessuna variante cambia il criterio in base al risultato della giornata.

La priorità al valore produce una sola Singola vinta su tre risolte, contro due
su tre dell'attuale, con una irrisolta in entrambi i casi. Le multiple non danno
un vantaggio coerente. Imporre partite diverse riduce ulteriormente le proposte
complete nel piccolo campione. Nessuna di queste osservazioni dimostra un rendimento
futuro; per questo la selezione pubblica resta invariata.

## Interventi implementati

1. Due modelli alternativi e tre criteri di selezione sono definiti in codice,
   versionati e verificati rispetto al modello originale.
2. Dalle scansioni successive alla pubblicazione vengono salvate probabilità e
   selezioni alternative prima dei risultati, in parallelo alle proposte pubbliche.
3. Il consolidamento già programmato valuta queste stesse selezioni sui risultati
   ESPN e conserva metriche e casi irrisolti nel registro per snapshot. Non conta
   le diverse scansioni come partite indipendenti e non aggrega arbitrariamente i loro rendimenti.
4. Il confronto non avvia scansioni o richieste OddsPapi, non cambia percentuali
   pubbliche e non può promuovere da solo un modello. La calibrazione automatica
   esistente mantiene i suoi controlli separati.
5. I dati della ricerca parallela sono esclusi dalla risposta pubblica usata dalla
   pagina principale. Il contesto del giocatore viene preparato una sola volta,
   senza ulteriori richieste di storico: il confronto non aggiunge chiamate ESPN o OddsPapi durante la scansione.
6. Per multiple della stessa partita, l'interfaccia segnala che quota e probabilità
   combinate non sono stimate e richiede di verificare la combinazione sul bookmaker.

## Ripetizione e verifica

`python -m scripts.weight_selection_review --dates 2026-10-23 2026-10-24 2026-10-25 2026-10-26`

Il JSON allegato contiene risultati dettagliati, selezioni, esiti, job ID e hash
canonici degli input. Gli archivi grezzi restano soggetti alla normale pulizia;
questa analisi non modifica la retention. Il registro permanente conserva invece
le metriche dei nuovi confronti per snapshot, consultabili dall'endpoint autenticato
`/api/calibration/recommendation-results` nella proprietà `report.model_shadow`.

Resta necessaria una verifica su nuove giornate: le sole quattro date attuali non
consentono di dichiarare una nuova formula o una nuova strategia più affidabile.
