'use strict';
document.getElementById('login').addEventListener('submit',async event=>{
 event.preventDefault();const el=id=>document.getElementById(id);el('status').textContent='Caricamento…';
 for(const id of ['opens','actions','summary'])el(id).replaceChildren();
 try{
  const result=await fetch('/api/audience/report?days='+el('days').value,{headers:{Authorization:'Bearer '+el('key').value},cache:'no-store',credentials:'omit'});
  if(!result.ok)throw Error(result.status===401?'Chiave non valida.':'Statistiche temporaneamente non disponibili.');
  const data=await result.json(),totals={};let opens=0;
  function row(parent,values){const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}el(parent).append(tr);}
  for(const item of data.rows){if(item.event==='apertura'){opens+=item.total;row('opens',[item.day,item.source,item.total]);}else totals[item.event]=(totals[item.event]||0)+item.total;}
  const labels={pronostici:'Pronostici',quote:'Analisi quote',statistiche:'Statistiche giocatori',archivio:'Archivio esiti',informazioni:'Come funziona',filtro_quote:'Uso filtri quote',scelta_giocatore:'Scelta giocatore',dettagli:'Apertura dettagli',csv:'Esportazione CSV'};
  for(const [name,total] of Object.entries(totals).sort((a,b)=>b[1]-a[1]))row('actions',[labels[name]||name,total]);
  el('summary').textContent=opens+' aperture nel periodo · '+Object.values(totals).reduce((a,b)=>a+b,0)+' azioni';
  el('status').textContent=data.rows.length?'Dati aggiornati.':'Nessun dato nel periodo. La raccolta inizia dall’attivazione.';
 }catch(error){el('status').textContent=error.message;}
});
