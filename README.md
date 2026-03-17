# SynthAgora

**Debatte-Simulation mit echten Konsequenzen**  
KI-Agenten diskutieren ein Thema – mit **Gedächtnis**, **Wiederholungsverbot** und **Ausschluss** bei 3× Abschweifen oder Wiederholung.

Moderne lokale Multi-Agenten-Debatte mit grafischer Oberfläche, LM Studio Backend und hartem Moderations-Regime.


## ✨ Features

- **Echtes Agenten-Gedächtnis** → Wiederholungen werden gezählt
- **Automatischer Ausschluss** nach **3× gleichem/ähnlichem Inhalt**
- **Moderationssystem mit Konsequenzen**  
  → 3× Abschweifen → Agent wird rausgeworfen
- **Lokales LLM Backend** (LM Studio / OpenAI-kompatible API)
- **Schöne Tkinter-GUI** mit farbigen Agenten-Karten
- **Live-Status** der Agenten (aktiv / ausgeschlossen / Beitragszahl)
- **Rundenbasiertes System** + freie Reaktionen
- **Optionales Kontext-Dokument** (z. B. Gesetzestext, Studie, Wikipedia-Auszug)
- **Export** des kompletten Chat-Verlaufs
- **Stop-Button** mit sauberem Thread-Handling

## Demo-Video / Screenshots

*(Hier wäre jetzt ein guter Platz für 2–4 Screenshots oder ein kurzes Gif/Loom-Video)*

Beispiele:

- Startbildschirm mit Agenten-Auswahl  
- Diskussion läuft – Agent wird ausgeschlossen  
- Moderator greift ein  
- Zusammenfassung am Ende

## Voraussetzungen

- **Python 3.9–3.12**
- **LM Studio** (oder jede andere OpenAI-kompatible lokale API) läuft auf `http://localhost:1234`
- Empfohlene Modelle:  
  7B–13B instruct Modelle (z. B. Llama-3.1, Mistral-Nemo, Qwen2.5, Gemma-2, etc.)

## Installation

```bash
# 1. Repository klonen
git clone https://github.com/deinusername/mirofish-ultimate.git
cd mirofish-ultimate

# 2. Virtuelle Umgebung (empfohlen)
python -m venv venv
source venv/bin/activate    # Linux / macOS
# oder
.\venv\Scripts\activate     # Windows



# 4. LM Studio starten und Server auf Port 1234 laufen lassen
