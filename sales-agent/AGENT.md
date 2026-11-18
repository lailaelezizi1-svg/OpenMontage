# Istruzioni per Claude Code (agente commerciale)
Lavora da `sales-agent/`. Stato = `data/sales.db` (SQLite). Non inventare dati: usa solo campi presenti con `source`.

## Ciclo
1. `python3 -m agent.cli discover` -> `analyze` -> `status`.
2. Per le aziende `qualified` rivedi i fatti (`issues`) e, se serve, apri il sito per verificarli.
   Riscrivi le bozze in `messages` (status `draft`) in modo piu naturale, citando SOLO problemi rilevati. Mantieni
   identita mittente, indirizzo postale, riga STOP e link privacy.
3. `review` e presenta le bozze all'utente. **Mai `approve` o `send` senza richiesta esplicita dell'utente.**
4. `inbox`: per le risposte `other` o ambigue rileggi il testo e correggi `classification`/`status`.
   Rispondi alle domande commerciali solo con informazioni verificate (listino/servizi dall'utente); se non le hai, chiedi.
5. Ogni opposizione/cancellazione: `suppress <email>` subito, nessuna risposta promozionale.
6. Segnala all'utente trattative `interested`, `quote`, `meeting` (la notifica email parte da `inbox`).
## Divieti
Niente telefonate/messaggi social automatici, niente indirizzi personali, niente invii oltre `send_per_day`,
niente credenziali nei log o nei file committati.
