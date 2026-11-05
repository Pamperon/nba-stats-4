# Basket Lab — Verifica completa dei dati e della selezione

5 novembre 2026 · Periodo storico: 23 ottobre–5 novembre 2026

## Conclusione

**Il calcolo è coerente con la formula, ma l’ordinamento attuale non dimostra di individuare i candidati migliori.** Il problema principale è la sovrastima delle probabilità nel sottoinsieme promosso dai filtri: selezionare il valore massimo di una stima non calibrata amplifica gli errori. Non è sufficiente alzare la soglia dal 70% al 90%.

La verifica non giustifica ancora una sostituzione automatica dei filtri. Il controllo sul minutaggio è il candidato più utile da valutare prospetticamente; privilegiare quote basse è un benchmark, non un nuovo modello validato.

## 1. Dati esaminati

| Controllo | Risultato |
|---|---:|
| Giornate storiche concluse | 13 |
| Linee uniche osservate nelle scansioni | 21.079 |
| Linee con probabilità disponibile | 19.113 |
| Linee con stima e orario sicuramente precedente alla partita | 19.071 |
| Linee precedenti alla partita con esito verificato | 18.253 |
| Esiti espliciti “non ha giocato” tra le linee valutabili | 303 |
| Altri esiti non risolti tra le linee valutabili | 515 |
| Linee osservate dopo l’inizio, escluse dal confronto | 42 |
| Partite con esiti verificati | 105 |

Le linee alternative dello stesso giocatore non sono osservazioni indipendenti. Le 18.253 verifiche non equivalgono a 18.253 partite. L’analisi conserva tutte le linee per studiare probabilità e fasce di quota, ma confronta le graduatorie con un solo pronostico per giocatore e partita.

Sono state utilizzate tutte le scansioni storiche disponibili, comprese quelle parziali. Per una stessa combinazione partita/giocatore/mercato/scelta/linea è stata mantenuta la prima osservazione salvata, senza scegliere la versione con il risultato più favorevole. Le quote future del 6 novembre non hanno ancora un esito e non entrano nel test.

## 2. Integrità e formula

- Nessuna squadra estranea alla partita nelle 19.113 linee con stima.
- Nessuna discrepanza di squadra nei casi con identità ESPN verificata sul tabellino. Le righe storiche senza ID mantengono il metodo conservativo di corrispondenza del verificatore e non sono considerate prove equivalenti a un ID verificato.
- Esiti verificati sui tabellini ESPN della partita esatta; assenze e mancate corrispondenze non sono perdite.
- Ricalcolate **4.337 probabilità** sulle due scansioni sorgente delle sessioni ufficiali del 2 e 4 novembre: **zero differenze** oltre l’arrotondamento.
- Nei **339 storici** di quelle due scansioni: nessun ID partita duplicato e nessun record successivo alla scansione. Questo controllo approfondito riguarda quelle due sorgenti, non ogni singolo storico di ottobre.

La formula attuale usa l’80% della frequenza regolarizzata sull’intero storico disponibile e il 20% sulle ultime 20 partite. Il contributo della stagione precedente può quindi restare elevato a inizio stagione. La correttezza aritmetica non dimostra la calibrazione predittiva.

## 3. Dove emerge la sovrastima

| Insieme | Esiti verificati | Stima media | Frequenza effettiva |
|---|---:|---:|---:|
| Tutte le linee nella fascia quota 1,20–2,20 | 3.809 | 61,4% | 59,8% |
| Linee che superano filtri e soglia minima del 70% | 586 | 80,6% | 66,0% |
| Graduatoria attuale, fino a 10 per giornata nel replay | 113 | 87,7% | 66,4% |

La distorsione aumenta quando si scelgono le probabilità più alte. Il filtro sul “value” dipende dalla stessa stima che si vuole verificare: un errore ottimistico può far apparire una linea più vantaggiosa di quanto sia.

Nella fascia 1,20–2,20 il Brier score è 0,2410 per il modello e 0,2312 per il semplice reciproco della quota: più basso è meglio. Il reciproco include il margine del bookmaker e non è una probabilità equa; è soltanto un confronto di riferimento. Questo campione non dimostra un vantaggio predittivo del modello rispetto a tale riferimento.

## 4. Confronto delle regole

Stessi input salvati prima delle partite; i risultati non intervengono nell’ordinamento. Fino a 10 candidati per giornata, un giocatore per partita. Sono simulazioni della regola attuale sulle prime osservazioni, **non il conteggio delle Top 10 effettivamente pubblicate**. Il numero di esiti varia per disponibilità e copertura.

| Regola | Esiti | Centrate | Quota media | Rendimento simulato a puntata fissa |
|---|---:|---:|---:|---:|
| Ordinamento attuale per probabilità | 113 | 66,4% | 1,296 | −15,2% |
| Stesso criterio, minuti recenti almeno al 90% della media | 111 | 72,1% | 1,324 | −6,3% |
| Quote più basse tra i candidati idonei | 115 | 76,5% | 1,260 | −4,1% |
| Frequenza ultime 10 prioritaria | 115 | 71,3% | 1,341 | −5,5% |
| Value stimato prioritario | 113 | 57,5% | 1,685 | −3,8% |
| Probabilità minima del 90% | 30 | 73,3% | 1,242 | −9,1% |

Il rendimento è puramente descrittivo: una unità nominale per selezione, alle quote archiviate, senza considerare esiti non risolti o assenze. Nessuna alternativa mostra qui un rendimento positivo complessivo. “Più centrate” e “maggiore rendimento” sono obiettivi diversi.

Nelle quattro giornate più recenti del confronto temporale, il criterio attuale centra 27/42 selezioni (64,3%); il controllo sui minuti ne centra 31/42 (73,8%). Su tutte le 13 giornate il vantaggio di 5,7 punti del criterio minuti ha un intervallo bootstrap per giornata circa da −3,4 a +13,3 punti: l’incertezza comprende ancora nessun miglioramento. Le alternative sono confronti esplorativi e il blocco temporale non è un test prospettico incontaminato.

## 5. Esempio concreto del limite sul minutaggio

Lauri Markkanen, sessione del 4 novembre: stima 91,9%, minuti medi 33,7 e ultimi cinque 27,6. Il calo è di circa il 18%. Il filtro attuale lo ammette, perché interviene su cali più marcati. Un criterio al 90% della media lo escluderebbe. Il caso illustra il funzionamento del filtro, non dimostra da solo che debba essere cambiato.

Richiedere almeno 10 partite della stagione corrente, invece, avrebbe azzerato i candidati nel periodo: a inizio novembre il requisito non è praticabile. Cinque partite attuali producono risultati interessanti ma un campione ridotto e una forte dipendenza dal calendario.

## 6. Controllo delle pubblicazioni reali

La Singola delle due sessioni ufficiali controllate coincide con il risultato della regola attuale applicata alle sue sorgenti. La Top 10 del 4 novembre coincide integralmente. Per il 2 novembre coincidono le prime cinque; le altre derivano dalle precedenti regole di completamento dell’archivio, limitate alle partite già rappresentate. Non è corretto considerare quella lista una riproduzione esatta della graduatoria corrente su tutte le partite.

Per questo il report distingue sempre risultati ufficiali e simulazioni. **Nessuna selezione passata è stata sostituita dopo aver visto l’esito.**

## 7. Calibrazione già disponibile

Il controllo cronologico sugli aggregati salvati usa 13 giornate e 13.192 osservazioni. La correzione prudente già presente nel codice porta il Brier da 0,123040 a 0,122646: miglioramento di circa 0,000393. È piccolo e inferiore alla soglia di 0,001 usata dal controllo esistente. Non c’è motivo sufficiente per abilitarla automaticamente. Questi aggregati usano un sottoinsieme di snapshot diverso dal campione completo deduplicato: i numeri non vanno sommati.

## 8. Intervento conseguente

È stato preparato un confronto interno versionato per salvare prima delle partite quattro graduatorie: criterio corrente, controllo minuti al 90%, benchmark quote e ultime 10. Il confronto usa le stesse regole di idoneità, esclude il giocatore della Singola, mantiene al massimo 10 scelte e una linea per giocatore/partita. Gli esiti sono abbinati alla partita e all’identità esatte; non sono permesse promozioni automatiche.

Le selezioni pubbliche e le probabilità non vengono modificate da questo esperimento. La valutazione successiva dovrà riguardare giornate nuove, con confronto per partita/giornata e verifica sia della calibrazione sia del rendimento, senza continuare a cambiare soglie per adattarle agli stessi esiti.

**Priorità:** validare il minutaggio e ridurre la sovrastima della graduatoria. Evitare di presentare le percentuali attuali come già validate o di usare il solo value stimato per dichiarare una selezione “migliore”.

## Riproducibilità e limiti

Audit eseguito in lettura: nessuna nuova chiamata al provider delle quote, nessuna scrittura dei dati storici. Gli esiti provengono da tabellini ESPN finali; gli input sono gli snapshot già salvati. Lo script di controllo separa osservazioni, selezioni, esiti e simulazioni. I test verificano che invertire gli esiti non cambi i candidati e che un esito mancante non diventi una perdita.

Il periodo è breve, le linee alternative sono correlate, le versioni storiche del modello non sono tutte identiche e le prime quote osservate non coincidono necessariamente con quelle delle 18:00. I confronti per fascia quota e mercato riducono alcuni squilibri ma non li eliminano. Le conclusioni riguardano il campione disponibile, non garantiscono il comportamento futuro.
