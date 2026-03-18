# SynthAgora (0.2B - 18.03.2026)

**Multi-Agent AI Debate Simulator** – KI-Agenten diskutieren kontroverse Themen mit **echtem Gedächtnis**, **Wiederholungsverbot** und **Ausschluss** bei Regelverstößen. Powered by lokalen LLMs (LM Studio, Ollama).

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/) [![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE) [![LLM Backend](https://img.shields.io/badge/LLM-LM%20Studio%20%7C%20Ollama-orange)](https://lmstudio.ai/) [![Project Status](https://img.shields.io/badge/Status-Active-brightgreen)]() [![GitHub last commit](https://img.shields.io/github/last-commit/wobushannes/SynthAgora)]()

👉 **[Demo-Video auf YouTube](https://youtu.be/DIhA5LQgyPM)**

## ✨ Features
✅ **Echtes Agenten-Gedächtnis** – Jeder Agent merkt sich, was er und andere gesagt haben  
✅ **Automatischer Ausschluss** – 3× gleiche Aussage oder 3× Abschweifen → raus!  
✅ **Lokale LLMs** – Läuft mit LM Studio, Ollama (OpenAI-kompatibel)  
✅ **Schöne Tkinter-GUI** – Farbige Agentenkarten, Live-Status, Rundenanzeige  
✅ **Knowledge Graph** – Agenten lernen voneinander, Konzepte werden verknüpft  
✅ **8+ Agenten gleichzeitig** – Skaliert bis zu 20 Agenten  
✅ **Konfigurations-Tab** – Wähle Provider, passe Temperatur, Tokens an  
✅ **Chat-Export** – Speichere Diskussionen als `.txt`  
✅ **Stop-Button** – Sauberes Thread-Handling

## 📋 Voraussetzungen
- **Python 3.9–3.12**
- **LM Studio** (empfohlen) oder **Ollama** mit einem instruct-Modell (z.B. Llama-3, Mistral, Gemma-2)

## 🔧 Installation
```bash
git clone https://github.com/wobushannes/SynthAgora.git
cd SynthAgora
python -m venv venv
source venv/bin/activate    # Linux/macOS | .\venv\Scripts\activate (Windows)
pip install -r requirements.txt
# LM Studio starten, Modell laden, Server auf Port 1234
python main.py

⚙️ Konfiguration
Agenten (/agents/): Jeder Agent als JSON mit name, role, personality, color, goals, fears
Moderatoren (/moderators/): Definieren Interventionsstile, max_evasions, abbrechen_nach
Dokumente (/examples/): Einfache .txt-Dateien als Diskussionsgrundlage
Provider: Im GUI-Konfigurations-Tab wählbar (LM Studio, Ollama, OpenAI/BETA, Grok/BETA, Claude/BETA)

📁 Projektstruktur
synthagora/
│
├── main.py                          # Hauptprogramm (bleibt im Hauptordner)
├── config.json                       # Konfigurationsdatei (JSON)
│
├── includes/                          # ALLES was importiert wird
│   ├── config.py                       # ← HIER hin mit der config.py!
│   │
│   └── plugins/                         # Plugin-Ordner
│       ├── __init__.py
│       ├── wikipedia_plugin.py
│       ├── arxiv_simple.py
│
├── agents/                             # Agenten-JSONs
├── moderators/                          # Moderator-JSONs
├── examples/                            # Beispiel-Dokumente
├── memory/                               # Agenten-Erinnerungen
├── knowledge_graph/                      # Knowledge Graph Daten
└── exports/                              # Exportierte Diskussionen
