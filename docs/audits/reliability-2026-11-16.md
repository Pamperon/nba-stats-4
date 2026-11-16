# Basket Lab — verifica affidabilità del 16 novembre 2026

Base: `ceed20ee3a3818b8555847279cbba9196bf0afb4`. Controlli pubblici e Render in sola lettura; test di database in PGlite isolato. Nessuna scansione OddsPapi avviata, nessuna modifica ai pronostici o agli esiti storici.

## Riscontri e interventi

| Priorità | Riscontro | Intervento / stato |
| --- | --- | --- |
| Alta | Eventi Render `server_failed` con motivo memoria esaurita il 9, 10, 11, 12 e 13 novembre. Il 16 novembre alle 13:20 UTC 532.344.830 byte su 536.870.900, circa 99,2%. | Limiti in byte alle cache principali, anziché solo numero di elementi. È una riduzione del rischio di ritenzione, non una dimostrazione che tutti i picchi RSS siano risolti. |
| Alta | `Pillow>=11,<13` impediva l'installazione delle correzioni di sicurezza di Pillow 13. `pip-audit` segnala advisory sulle versioni ammesse. | Requisito `Pillow>=13.0.0,<14`. Foto ESPN limitate al decoder PNG, a 4 milioni di pixel e a due conversioni simultanee; errore controllato sulle decompression bomb. |
| Media | Le cache ESPN del motore non avevano tutte un lock. I timestamp delle quote potevano sopravvivere all'eviction dei payload. | Lock sulle cache del motore; pulizia dei timestamp associata a scadenza/eviction. |
| Media | Probabilità delle selezioni storiche superiori alla frequenza osservata. | Nessuna promozione o ricalibrazione automatica. Necessaria valutazione temporale fuori campione. |
| Da verificare | Backup effettivamente recuperabili, retention e punto di ripristino più recente. | Metadati DB accessibili, backup e restore non verificati. Non modificata la lista IP per ottenere accesso SQL. |

## Budget delle cache modificate

La stima ricorsiva comprende contenitori Python e memoria profonda dei DataFrame. Oggetti condivisi nella stessa risposta sono contati una sola volta. Il limite riguarda i valori conservati, non l'intero processo: restano chiavi/metadati, risposte in elaborazione, serializzazione, librerie native e allocator.

| Cache | Budget MiB |
| --- | ---: |
| Quote per fixture | 16 |
| Feed/calendario/catalogo OddsPapi condivisi | 24 |
| Motore ESPN: squadre, roster, calendari, classificazioni, log | 28,25 complessivi |
| Hub NBA | 8 |
| Scoreboard calendario | 4 |

Una risposta oltre budget viene restituita integra senza conservarla in RAM. Il feed quote resta riutilizzabile dalla persistenza PostgreSQL con timestamp originale. Test esplicito: due letture di un feed troppo grande causano un solo download. Un'eviction può aumentare le letture dal DB o le richieste ESPN gratuite; non vengono cambiati TTL, slot o criteri del modello.

## Archivio, dati e modello

- Endpoint performance: 124 selezioni pubblicate, 119 giocate con esito, 77 centrate, 42 non centrate, 5 non ha giocato, zero in attesa. Singole: 8, di cui 7 centrate e una non centrata.
- Ricontrollate da ESPN le 10 selezioni ufficiali della giornata di pubblicazione 15 novembre e la singola Keldon Johnson, su sette partite concluse. Tutti gli 11 valori e stati coincidono. Verifica su campione, non su ogni riga storica.
- Media stimata selezioni: 80,6%; frequenza osservata: 64,7% su 119 esiti. Singole: 75,1% stimato contro 87,5% osservato su soli 8 esiti. Mercati/giocatori possono essere correlati: questi dati non provano una probabilità futura né un vantaggio economico.
- Confermata dal health endpoint la configurazione dei cinque slot: 09:00, 12:00, 14:30, 16:30, 17:30 Europe/Rome; registro scansioni pronto, zero scansioni attive al controllo. Non attesa ogni esecuzione futura.
- Preservate le ultime modifiche: soglia singola 1,66, gestione assenze ESPN, navigazione delle squadre.

## Sicurezza, database e costi

- Richieste pubbliche senza credenziali a `/api/admin/monitor` e `/api/calibration/summary`: HTTP 401. Test locali verificano autenticazione, errori generici e `no-store` sul monitor.
- Migrazioni privilegi/RLS applicate due volte in database isolato: ruoli client senza accesso alle tabelle private, accesso server conservato. Questo non equivale a una verifica SQL dei privilegi del DB di produzione.
- Test integrazione PostgreSQL isolato: migrazioni, conteggi audience aggregati, registro richieste a pagamento, coordinamento deploy e archivio giornaliero senza duplicati.
- Database Render disponibile; campioni 12:00–13:30 UTC: 1–3 connessioni, memoria circa 95–111 MiB su 256 MiB. Disco configurato 1 GB, autoscaling disco disattivato, nessuna replica/HA. Non misurata l'occupazione disco effettiva tramite SQL.
- Non modificati piani, numero istanze o impostazioni a pagamento. Non verificate fatture e soglie di spesa del provider quote.
- `npm audit`: nessuna vulnerabilità segnalata sulle dipendenze risolte. Le verifiche dipendenze non escludono vulnerabilità sconosciute o problemi applicativi.
- Analytics: i conteggi possono includere il proprietario; consenso e blocchi del browser influenzano la raccolta. Non acquisiti nuovi report GA4 in questa verifica.

## Validazione e limiti

- Suite Python offline, rete vietata: 347 test passati, comprese nuove regressioni su memoria e immagini.
- Frontend: sintassi e 152 test Node passati.
- Sicurezza DB e integrazione SQL eseguite in PGlite isolato.
- Browser desktop/mobile: il relativo workflow della PR esegue Chromium con fixture, confronta budget con baseline. L'esito effettivo è nei check della PR; non è un test di carico sul sito live.
- I tempi dei GET pubblici da questo ambiente (circa 4,6–7,3 s, inclusa rete) non sono una misura affidabile del solo server e non vengono presentati come Core Web Vitals.
- Non eseguito un test di carico invasivo su un'istanza già vicina al limite RAM. I limiti delle cache richiedono osservazione su più scansioni reali prima di dichiarare risolti gli arresti.
- Non eliminate funzioni di ricerca/modelli solo perché non usate dall'interfaccia: hanno riferimenti nei workflow e nei test. Nessuna cancellazione arbitraria di dati o storico.

## Ripristino: procedura ancora da provare

1. Nel dashboard del database verificare backup/PITR effettivi, ultimo punto recuperabile, retention e requisiti del piano. Registrare questi valori senza esporre credenziali.
2. Ripristinare in un database separato, con costi e destinazione definiti prima di crearli; non sovrascrivere produzione.
3. Confrontare conteggi, intervalli data, chiavi univoche e ultimi record delle tabelle scansioni, selezioni ufficiali, singole, esiti, calibrazione e audience.
4. Collegare una copia dell'app con scheduler e download quote disabilitati; verificare archivio, letture statistiche e autenticazione.
5. Registrare tempo di ripristino, perdita massima di dati e risultato; eliminare solo le risorse temporanee concordate.

## Fonti tecniche

- [Pillow 13.0.0: correzioni e compatibilità](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
- [Advisory Pillow su amplificazione memoria TIFF/EXIF](https://github.com/python-pillow/Pillow/security/advisories/GHSA-wqgw-9xfh-qf2g)
- Dati operativi: metriche/eventi Render e API pubbliche Basket Lab rilevati il 16 novembre 2026.
