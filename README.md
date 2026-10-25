# NBA STATS PRO

Web app privata per l'analisi dei player props NBA Bet365, con statistiche ESPN,
archivio PostgreSQL/Supabase e interfaccia PWA. Repository indipendente dalla versione 3.5.

## Avvio

Usa Python 3.11 o successivo e installa `pip install -r requirements.txt`.
Configura `ODDSPAPI_API_KEY`, `NBA_STATS_ACCESS_TOKEN` e `DATABASE_URL` nel provider
(senza pubblicarne i valori). Il programma legge le variabili d'ambiente;
`.env.example` è solo un riferimento e non viene caricato automaticamente.

Comando locale: `uvicorn main:app --host 127.0.0.1 --port 8000`.
Su Render: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
Mantieni **una sola istanza e un solo worker**: i job attivi sono in memoria.
Gli snapshot completati e gli storici sono salvati su PostgreSQL.
Le letture delle analisi e delle statistiche sono pubbliche; le operazioni di
scansione e manutenzione richiedono il token Bearer. Non esporre il servizio
come sistema multiutente con autenticazione individuale.

## Aggiornamenti automatici

GitHub Actions programma le scansioni alle **07:00, 12:00, 17:00 e 21:00** nel
fuso `Europe/Rome`, con cambio automatico tra ora solare e legale. Il secret
GitHub `NBA_STATS_ACCESS_TOKEN` deve corrispondere al token del server.
Sono previsti controlli di recupero ogni dieci minuti, fino a due ore dopo
ogni fascia. Prima di prenotare una fascia vengono verificati entrambi i calendari
ESPN gratuiti: se non sono disponibili, il controllo successivo può riprovare
senza aver consumato la prenotazione o richieste OddsPapi. Render esegue anche
un controllo interno mentre il server è attivo.
GitHub può ritardare o perdere eventi pianificati; Render Free può sospendersi.

La prenotazione atomica `nba_scan_slots` impedisce che GitHub e Render ripetano
la stessa fascia. Una fascia prenotata **non viene ritentata automaticamente**
dopo errori, timeout o riavvii: potrebbe aver già consumato chiamate API.
Ogni esecuzione controlla su ESPN oggi e domani e scarica quote solo per le
partite ancora da iniziare. I controlli di recupero senza nuova prenotazione
non contattano OddsPapi. Non fare deploy durante una scansione: un riavvio può
interrompere i job prima del salvataggio. Le fasce successive restano indipendenti.

`GET /api/health` mostra il commit Render e la revisione dello scheduler.
`GET /api/saved/time?date=YYYY-MM-DD` mostra il riepilogo salvato:
`quote_lines_scan` conta le righe di quota; `odds_api_http_requests_scan` conta
le richieste HTTP OddsPapi della scansione. Per gli archivi precedenti alla
misurazione, il numero di richieste rimane sconosciuto. Il contatore del provider
resta il riferimento per il consumo totale dell'abbonamento, comprese scansioni
interrotte o richieste esterne all'app.

## Verifiche offline

```
pip install -r requirements-dev.txt
python scripts/run_offline_tests.py
npm ci --ignore-scripts
npm test
```

Il runner Python vieta le connessioni di rete reali; i test HTTP usano risposte
simulate. I test JavaScript verificano sintassi, cambio giornata, profili
senza foto e ciclo di vita del service worker. Questi comandi non avviano
scansioni e non consumano chiamate OddsPapi. GitHub esegue gli stessi controlli
su push e pull request che modificano il codice.

## Limiti del modello e dei dati

Lo storico usato per le stime include soltanto partite il cui stato ESPN è
ufficialmente concluso. Non esiste un'esclusione fissa delle ultime 24 ore:
una gara finale di poche ore prima è utilizzabile anche nei back-to-back.
Le gare in corso o senza conferma di conclusione vengono escluse. Il calendario
stagionale e i riepiloghi per ID partita sono condivisi in cache per cinque minuti;
non richiedono OddsPapi. Una nuova scansione aggiorna le stime salvate, senza
riscrivere gli archivi precedenti.

Le probabilità sono stime empiriche, non garanzie di esito. Le correzioni di
calibrazione esistenti richiedono validazione storica walk-forward; il controllo
sul minutaggio resta in modalità osservazione. I backtest sperimentali delle
multiple non rappresentano necessariamente le selezioni effettivamente mostrate
in passato. Nessun archivio viene eliminato automaticamente.

I risultati live dipendono dalla disponibilità dei provider esterni; i test
simulati non certificano quote o risultati futuri. Il service worker conserva
la shell dell'app e non memorizza le risposte API.
