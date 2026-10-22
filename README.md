# NBA STATS 4.0 — progetto separato

Prima versione di sviluppo. **Non sostituisce NBA STATS 3.5** e non richiede modifiche al repository Streamlit.

## Avvio locale

1. Installa Python 3.11+.
2. Apri questa cartella in un terminale e installa le dipendenze: `pip install -r requirements.txt`.
3. Imposta le variabili d'ambiente `ODDSPAPI_API_KEY` e `NBA_STATS_ACCESS_TOKEN`. Non caricare mai i valori su GitHub. Puoi usare `.env.example` come riferimento, ma il programma legge le variabili d'ambiente, non carica automaticamente `.env`.
4. Esegui `uvicorn main:app --host 127.0.0.1 --port 8000`.
5. Apri `http://127.0.0.1:8000` e inserisci il token di accesso.

## Pubblicazione

Usa **un nuovo repository GitHub**, distinto da quello della versione 3.5. Per l'hosting scegli un servizio che supporti processi Python web e HTTPS; configura le due variabili come secrets nel provider. Avvio: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}` (su piattaforme che espandono la variabile PORT tramite shell). Il piano gratuito e la sua disponibilità vanno verificati prima della pubblicazione. Per installare la PWA su Android apri l'URL HTTPS in Chrome e scegli «Aggiungi a schermata Home» / «Installa app» se disponibile.

## Stato / limiti MVP

- Logica OddsPapi/ESPN e modello statistico derivati dal file 3.5 fornito dall'utente.
- Scansione unica per data con cache in memoria e CSV completo. Non aggiornare le quote automaticamente.
- Grafica dark responsive, Dashboard, Value Finder, Player Stats e shell PWA. Le statistiche live **richiedono internet**.
- I job e la cache non sopravvivono al riavvio del server; usa un solo processo. Non adatto ancora a deployment con più worker o hosting che interrompe le richieste lunghe.
- Mancano ancora registro giocate persistente, filtri Regular/Playoff nella nuova interfaccia, diagnostica completa e test di integrazione con risposte reali delle API. Il Player Stats MVP mostra i log regular season raccolti dalla scansione.
- Autenticazione con token condiviso semplice: per uso privato iniziale, non equivalente a un sistema account completo. Token tenuto solo in memoria della pagina, da reinserire al refresh.
- Il modello è una stima empirica non calibrata e non garantisce esiti futuri.
