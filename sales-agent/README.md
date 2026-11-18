# Agente commerciale locale (siti web per attivita locali)

Sistema su misura, solo libreria standard di Python 3 (nessuna dipendenza da installare). Claude Code e l'agente
principale (vedi `AGENT.md`); questo codice e l'infrastruttura: database, ricerca, analisi, controlli di conformita,
casella email e notifiche. **OpenOutreach non e usato**: e un lead finder B2B su persone (BetterContact), non copre
ricerca locale, analisi siti, gestione risposte.

## Cosa fa / non fa
| Fa | Non fa |
|---|---|
| Cerca attivita per citta+categoria da OpenStreetMap (gratis) | Non usa Google Maps, Instagram o Facebook per scraping |
| Analizza il sito (HTTPS, mobile, velocita, tecnologie, prenotazioni) e dà un punteggio 1-100 con motivazioni | Non inventa dati: solo cio che e rilevato |
| Database SQLite persistente, dedup, lista "non ricontattare" | Non chiama mai per telefono |
| Prepara bozze personalizzate | **Non invia nulla senza tua approvazione** (`auto_send: false`) |
| Legge le risposte via IMAP, classifica, ti notifica via email | Le opposizioni (STOP, cancellazione...) sono applicate subito |

## Installazione sul Mac
```bash
git clone <repo> && cd OpenMontage/sales-agent   # branch claude/cool-fermat-163jef
python3 --version                                # serve >= 3.9
cp .env.example .env && chmod 600 .env           # poi compila .env
python3 -m unittest tests.test_flow              # 7 test, devono passare
```
Credenziali (solo in `.env`, ignorato da git): casella email + **password per app** (Gmail: Account Google > Sicurezza >
Verifica in 2 passaggi > Password per le app), `NOTIFY_TO` = dove ricevere le notifiche.
Compila anche `config/settings.json > sender` (nome, ragione sociale, **indirizzo postale**, link informativa privacy):
senza questi dati l'invio resta bloccato.

## Uso
```bash
python3 -m agent.cli discover                    # cerca (tutte le citta/categorie abilitate)
python3 -m agent.cli discover --territory monopoli --category bar
python3 -m agent.cli analyze                     # analizza e valuta
python3 -m agent.cli draft -n 10                 # bozze (solo email generiche aziendali con fonte)
python3 -m agent.cli review                      # leggi le bozze
python3 -m agent.cli approve 1 2 3               # approvi tu
python3 -m agent.cli send --dry-run              # verifica conformita senza inviare
python3 -m agent.cli send                        # invia solo approvate e conformi, entro il tetto giornaliero
python3 -m agent.cli inbox                       # legge risposte, classifica, notifica
python3 -m agent.cli suppress info@esempio.it    # lista non ricontattare
python3 -m agent.cli status
python3 -m agent.cli cycle                       # ciclo completo SENZA invio
```
## Aggiungere citta/regioni
Solo dati: aggiungi un oggetto in `config/territories.json` (`"enabled": true`). Nessun codice da toccare.
Nota: il nome deve coincidere con il confine amministrativo OSM.

## Esecuzione programmata (macOS launchd)
Crea `~/Library/LaunchAgents/it.salesagent.cycle.plist` (sostituisci il percorso) e `launchctl load` il file:
```xml
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>it.salesagent.cycle</string>
<key>WorkingDirectory</key><string>/PERCORSO/OpenMontage/sales-agent</string>
<key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>-m</string><string>agent.cli</string><string>cycle</string></array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>7</integer></dict>
<key>StandardOutPath</key><string>/tmp/salesagent.log</string><key>StandardErrorPath</key><string>/tmp/salesagent.log</string>
</dict></plist>
```
I limiti (`config/settings.json > limits`) e la dedup rendono i cicli ripetibili senza duplicati.
Per rispondere alle risposte interessate in autonomia, apri Claude Code nella cartella e segui `AGENT.md`.

## Conformita (non e un parere legale)
- Molte attivita sono ditte individuali = persone fisiche: l'email promozionale richiede in genere consenso preventivo
  (art. 130 Codice Privacy / GDPR). Il sistema **blocca** email personali, nome.cognome@ e provider gratuiti (gmail, libero...).
  Passano solo indirizzi generici aziendali (info@, prenotazioni@...) pubblicati dall'attivita, con fonte registrata.
- Ogni messaggio contiene identita, indirizzo postale, opt-out e link privacy; `List-Unsubscribe` incluso.
  L'alias `+unsub` deve arrivare a te (verifica prima del primo invio).
- Verifica con un consulente la base giuridica prima di inviare in volume. Dati OSM: licenza ODbL, fonte registrata.

## Stato del collaudo
- Testato qui con dati simulati: dedup, punteggio, filtri, risposte, opposizione, notifica (7 test).
- **Non testato dal vivo**: Overpass, SMTP e IMAP (rete del cloud bloccata / nessuna credenziale). Primo collaudo da fare sul Mac:
  `discover --territory monopoli --category bar`, poi `analyze`, `status`. Nessun invio richiesto.
