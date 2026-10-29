# NBA STATS PRO

Web app per l'analisi dei player props NBA Bet365, con statistiche ESPN,
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

Render programma le scansioni alle **07:00, 11:00, 14:30, 18:00 e 21:00** nel
fuso `Europe/Rome`, con cambio automatico tra ora solare e legale. GitHub Actions
esegue controlli secondari di recupero sulle stesse fasce. Il secret
GitHub `NBA_STATS_ACCESS_TOKEN` deve corrispondere al token del server.
Sono previsti controlli di recupero ogni dieci minuti, fino a due ore dopo
ogni fascia. Prima di prenotare una fascia vengono verificati entrambi i calendari
ESPN gratuiti: se non sono disponibili, il controllo successivo può riprovare
senza aver consumato la prenotazione o richieste OddsPapi. Render esegue anche
un controllo interno mentre il server è attivo: al massimo ogni dieci minuti,
con attesa abbreviata se si avvicina una delle cinque fasce, per non superarla.
GitHub può ritardare o perdere eventi pianificati; Render Free può sospendersi.

La prenotazione atomica `nba_scan_slots` impedisce che GitHub e Render ripetano
la stessa fascia. Una fascia prenotata **non viene ritentata automaticamente**
dopo errori, timeout o riavvii: potrebbe aver già consumato chiamate API.
Ogni esecuzione controlla su ESPN oggi e domani e scarica quote solo per le
partite ancora da iniziare. I controlli di recupero senza nuova prenotazione
non contattano OddsPapi. I deploy ordinari attendono fino a dieci minuti che terminino le scansioni e le
fasce già avviate; nel frattempo le nuove fasce vengono rinviate. Se l'attesa
scade, il nuovo avvio fallisce senza sostituire l'istanza ancora attiva. I segnali
di attività scadono dopo due minuti, così un processo già morto non blocca
indefinitamente l'avvio. Riavvii forzati e arresti del provider possono comunque
interrompere una scansione; le fasce successive restano indipendenti.

`GET /api/health` mostra il commit Render e la revisione dello scheduler.
`GET /api/saved/time?date=YYYY-MM-DD` mostra il riepilogo salvato:
`quote_lines_scan` conta le righe di quota; `odds_api_http_requests_scan` conta
le richieste HTTP OddsPapi della scansione. Per gli archivi precedenti alla
misurazione, il numero di richieste rimane sconosciuto. Il contatore del provider
resta il riferimento per il consumo totale dell'abbonamento.

Il registro persistente `nba_odds_request_log` salva ogni tentativo PRIMA della
richiesta HTTP, senza chiavi o parametri sensibili, e poi registra l'esito. Se il
registro non è disponibile, non viene inviata una nuova richiesta a pagamento.
Un tentativo privo di risposta confermata resta separato come incerto: in caso
di arresto tra registrazione e invio, o errore di rete, non è possibile sapere
con certezza se il provider l'abbia conteggiato. Non si effettuano replay per
ricostruire il consumo. Il registro copre le nuove richieste dall'attivazione;
non ricostruisce gli arresti precedenti né richieste effettuate fuori dall'app.

Le quote NBA Bet365 Italia dei tre mercati giocatore vengono recuperate insieme
con `odds-by-tournaments` (torneo 132), senza ripiego a chiamate per partita.
Oggi e domani condividono il download della fascia; calendario e catalogo vengono
scaricati una volta per giornata italiana. La validità delle quote resta di tre
ore, ma una nuova fascia richiede dati nuovi anche prima della scadenza. Le
letture dalla cache conservano l'orario originale del download. Database e RAM
conservano solo l'ultima versione di ciascuno dei tre feed; gli snapshot completi
restano nell'archivio PostgreSQL. In condizioni ordinarie cinque aggiornamenti
costano fino a 7 chiamate al giorno (217 in 31 giorni); prove, scansioni manuali
e richieste aggiuntive possono aumentare il consumo.

`GET /api/saved/status?date=YYYY-MM-DD` distingue l'ultimo tentativo dall'ultimo
snapshot salvato. L'interfaccia controlla lo stato in sottofondo con sole letture
per caricare i nuovi dati salvati, senza mostrare un riquadro tecnico. Un errore
non aggiorna l'orario delle quote precedenti.
La pagina ricontrolla lo snapshot anche all'inizio annunciato delle partite,
senza richieste OddsPapi, e riprova le letture fallite. Al ritorno su una scheda
rimasta in sottofondo verifica subito se la visibilità delle selezioni è scaduta.
Gli snapshot salvati vengono riletti dal database quando richiesti, anche per
l'esportazione CSV dopo un riavvio. Quelli non salvati restano disponibili in RAM
per il recupero. Le risposte HTTP grandi vengono compresse quando il client lo supporta.

## Consultazione del sito

I collegamenti **Archivio esiti** (`#archivio`) e **Come funziona**
(`#come-funziona`) sono discreti e si trovano nel footer. Non occupano la
navigazione principale di pronostici e statistiche.

L'archivio presenta una sola raccolta per giornata di tutti i pronostici distinti
realmente pubblicati, raggruppati in singole, doppie e triple. Lo stesso
pronostico ripetuto in più aggiornamenti compare una sola volta, con la quota
e la stima della prima pubblicazione. I soli cambi di quota o di ordine delle
selezioni non creano nuove voci. Un cambio di partita, giocatore, mercato,
scelta o linea distingue il pronostico. Le multiple rimangono le combinazioni
originali pubblicate: non vengono create combinazioni nuove a posteriori.

Gli esiti provengono dalle verifiche ESPN persistite. Dati mancanti o in
conflitto rimangono da verificare; non vengono simulati rimborsi o rendimenti.
Gli snapshot originali sono conservati per gli studi sul modello. Il riepilogo
giornaliero è una vista di sola lettura e non modifica dati o selezioni salvate.

`/api/history/dates` e `/api/history?date=YYYY-MM-DD` sono pubblici e leggono
solo PostgreSQL, senza chiamate ai provider o scritture. L'interfaccia non
espone un selettore delle scansioni. Preferiti e movimenti quote, inclusi i
relativi endpoint e filtri, sono stati rimossi; al caricamento viene eliminata
solo la vecchia chiave locale di quella funzione.

Da telefono Analisi quote mostra inizialmente 100 righe, con caricamento
progressivo fino a 500; resta disponibile l'azzeramento dei filtri.

## Verifiche offline

```
pip install -r requirements-dev.txt
npm ci --ignore-scripts
python scripts/run_offline_tests.py
python scripts/check_tracking_db.py
npm test
```

Il runner Python vieta le connessioni di rete reali; i test HTTP usano risposte
simulate. Le query di migrazione, contatori, fasce e protezione deploy sono
eseguite anche su PostgreSQL/PGlite isolato in memoria, senza socket o provider
esterni. I test JavaScript verificano sintassi, cambio giornata, profili
senza foto e ciclo di vita del service worker. Questi comandi non avviano
scansioni e non consumano chiamate OddsPapi. GitHub esegue gli stessi controlli
su push e pull request che modificano il codice.

## Limiti del modello e dei dati

Lo storico usato per le stime include soltanto partite il cui stato ESPN è
ufficialmente concluso. Non esiste un'esclusione fissa delle ultime 24 ore:
una gara finale di poche ore prima è utilizzabile anche nei back-to-back.
Le gare in corso o senza conferma di conclusione vengono escluse. Il calendario
stagionale e i riepiloghi per ID partita sono condivisi in cache per cinque minuti,
conservando soltanto ID, data, tipo e conferma di conclusione. Le risposte ESPN
complete (box score, cronache e media) non restano in questa cache, per contenere
la memoria sul servizio Render da 512 MB. Questi controlli non richiedono OddsPapi. Una nuova scansione aggiorna le stime salvate, senza
riscrivere gli archivi precedenti.

Le probabilità sono stime empiriche, non garanzie di esito. Le correzioni di
calibrazione esistenti richiedono validazione storica walk-forward e sono
bloccate dal flag di rilascio `LIVE_CALIBRATION_ENABLED = False` in `main.py`:
la sola raccolta di nuovi risultati non può attivarle. Un'eventuale abilitazione
richiede una revisione e una decisione separata. Il controllo
sul minutaggio resta in modalità osservazione. I backtest sperimentali delle
multiple non rappresentano necessariamente le selezioni effettivamente mostrate
in passato. Nessun archivio viene eliminato automaticamente.

I risultati live dipendono dalla disponibilità dei provider esterni; i test
simulati non certificano quote o risultati futuri. Il service worker conserva
la shell dell'app e non memorizza le risposte API.

### Consultazione dei giocatori e delle quote

Nelle statistiche il campo Giocatore apre il roster della squadra selezionata senza abilitare la tastiera. La lente abilita la ricerca digitata in tutta la NBA, mostrando temporaneamente “Tutte le squadre”; scegliendo un risultato si ripristina la modalità tendina e si imposta la squadra corretta. Annullando si ripristina la selezione precedente. Non esiste un riquadro di ricerca separato. L’elenco usa i roster ESPN già memorizzati, con caricamento condiviso e riutilizzo nel browser; non scarica game log durante la ricerca e non usa OddsPapi. In caso di indisponibilità si può riprovare o usare i selettori esistenti.

Analisi Quote permette di filtrare per partita, insieme a giocatore, mercato e filtri avanzati, usando solo le selezioni salvate della giornata. Il ritorno dalle statistiche conserva filtri, risultati già caricati, dettagli aperti e posizione verticale e orizzontale nella stessa giornata. Cambiare giornata azzera la partita selezionata e la posizione salvata.

### Ripristino della navigazione e aggiornamento archivio

Il refresh di uno snapshot della stessa giornata conserva i filtri, il numero di quote caricate, i dettagli aperti e la posizione della vista attiva. Il cambio effettivo di giornata azzera il filtro partita e la posizione; durante il caricamento le proposte precedenti restano nascoste. La lista quote costruisce solo le schede mobile oppure la tabella desktop, secondo lo schermo.

Riaprire l’archivio o usare “Ricarica archivio” aggiorna anche le date disponibili, mantenendo la data selezionata se ancora presente. Le categorie occupano righe separate, con una griglia di schede adattiva al loro interno. Il CSV continua a esportare tutte le righe dello snapshot pubblico caricato, senza nuove richieste.

### Statistiche aggregate di utilizzo

`/admin/visite` mostra aperture per giorno/provenienza e azioni delle sezioni (7/30/90 giorni). Accesso al report con il valore server di `NBA_STATS_ACCESS_TOKEN`, mai la chiave OddsPapi; il browser mantiene la chiave solo nella pagina aperta. Il report autenticato usa `Cache-Control: no-store`; il pannello è escluso dall'indicizzazione e dalla cache del service worker.

La raccolta parte dal deploy: nessuna ricostruzione delle visite precedenti. Dati salvati solo in `nba_audience_daily`: giorno italiano, evento consentito, categoria provenienza e contatore. Nessun cookie, storage browser, ID visitatore, IP, query di ricerca, URL completo o dispositivo nel contatore. Eventuali log HTTP dell'hosting restano separati. DNT/GPC e bot riconosciuti sono esclusi; i bot non riconosciuti e i blocchi del browser rendono i conteggi indicativi. Non misura persone uniche, ritorni, sessioni o tempo di utilizzo. Refresh = nuova apertura. La pagina iniziale conta come apertura; i contatori delle sezioni contano le successive aperture tramite navigazione.

Fonti consentite: diretto, instagram, facebook, tiktok, whatsapp, telegram, google, bing, altro. Per app social usare `?utm_source=instagram` o `?utm_source=whatsapp` (nessun nome personale). Le azioni ripetute sono limitate a una per tipo ogni 5 secondi e 60 per pagina; batch di massimo 10, senza retry per evitare duplicazioni ambigue. Limite globale di 300 richieste/minuto per processo, senza chiavi IP; i conteggi non sono certificati né utilizzabili per fatturazione. Errori di raccolta non bloccano le funzionalità. Non richiede servizi a pagamento o chiamate OddsPapi.

### Anteprima dei link

La home espone metadati Open Graph e Twitter Card nell'HTML iniziale, con immagine PNG pubblica compatta 1200×400 in `/static/social-card-v2.png`. La copertina riutilizza il marchio della home; sorgente SVG e script `scripts/build_social_card.py` sono conservati nel repository. Per rigenerarla serve CairoSVG solo in fase di progettazione, senza nuove dipendenze di produzione. Le anteprime delle piattaforme possono mantenere copie precedenti nella propria cache.

### Nome e icona nei risultati Google

La home dichiara `Basket Lab` come nome preferito e `BasketLab` come alternativa nello stesso nodo JSON-LD `WebSite`; titolo, marchio e `og:site_name` mantengono il nome principale. La favicon principale è il logo PNG quadrato 192×192 già presente, con URL stabile `/static/icon-192.png`; il fallback ICO conserva taglie 16/32/48. Google sceglie autonomamente nome e icona e li aggiorna dopo la propria scansione: il deploy non modifica immediatamente i risultati. Il tag di verifica Search Console è conservato. Dopo accesso all'account proprietario, usare Controllo URL sulla home e verificare la sitemap esistente.

### Dettagli delle partite nel grafico giocatore

Ogni barra è apribile con tocco/clic o tastiera. Mostra avversario, casa/trasferta, minuti e punti/rimbalzi/assist della partita selezionata. Il risultato finale viene richiesto a ESPN solo all'apertura del dettaglio, tramite `/api/players/game?event_id=...`; nessun caricamento di risultati in blocco o chiamata OddsPapi. Si pubblicano soltanto partite esplicitamente concluse, con ID, due squadre e punteggi verificabili. Esito vittoria/sconfitta solo quando campo e avversario permettono di abbinare la squadra del giocatore; i dati mancanti restano indicati come non disponibili. I risultati compatti vengono condivisi tra visitatori e conservati tramite la cache ESPN esistente; errori non vengono salvati.

I log pubblici includono GAME_ID: versione schema final-v4 (batch team-logs-v3); durate della cache statistiche invariate. Motore delle previsioni, formule, soglie, aggiornamenti e cache OddsPapi non cambiano.
