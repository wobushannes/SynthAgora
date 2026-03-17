#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════╗
║  🐟 SynthAgora - Mit Gedächtnis & echten Konsequenzen             ║
║  Keine Wiederholungen mehr - Agenten werden bei 3. Abschweifung rausgeworfen ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import requests
import json
import time
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import queue
import re
import os
import glob

# ===================== KONFIGURATION =====================
class Config:
    LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
    TIMEOUT = 30
    TEMPERATURE = 0.7
    MAX_TOKENS = 300
    
    # Ordner
    AGENTS_FOLDER = "agents"
    MODERATORS_FOLDER = "moderators"
    EXAMPLES_FOLDER = "examples"
    EXPORTS_FOLDER = "exports"
    MEMORY_FOLDER = "memory"  # NEU
    
    # UI Farben
    BG_MAIN = "#1a1a1a"
    BG_PANEL = "#2d2d2d"
    BG_INPUT = "#3c3c3c"
    BG_BUTTON = "#0e639c"
    BG_BUTTON_HOVER = "#1177bb"
    BG_STOP = "#b52b2b"
    BG_STOP_HOVER = "#c43a3a"
    BG_ABBRUCH = "#8b0000"
    
    FG = "#ffffff"
    FG_DIM = "#cccccc"
    FG_BRIGHT = "#ffffff"
    FG_BUTTON = "#ffffff"
    
    SUCCESS = "#2e7d32"
    ERROR = "#b52b2b"
    
    @classmethod
    def load_from_file(cls, filepath="config.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            lm = data.get("lm_studio", {})
            cls.LM_STUDIO_URL = lm.get("url", cls.LM_STUDIO_URL)
            cls.TIMEOUT = lm.get("timeout", cls.TIMEOUT)
            cls.TEMPERATURE = lm.get("temperature", cls.TEMPERATURE)
            cls.MAX_TOKENS = lm.get("max_tokens", cls.MAX_TOKENS)
            
            folders = data.get("folders", {})
            cls.AGENTS_FOLDER = folders.get("agents", cls.AGENTS_FOLDER)
            cls.MODERATORS_FOLDER = folders.get("moderators", cls.MODERATORS_FOLDER)
            cls.EXAMPLES_FOLDER = folders.get("examples", cls.EXAMPLES_FOLDER)
            cls.EXPORTS_FOLDER = folders.get("exports", cls.EXPORTS_FOLDER)
            cls.MEMORY_FOLDER = folders.get("memory", cls.MEMORY_FOLDER)
            
            return True
        except:
            return False

Config.load_from_file()

# ===================== DATEI-MANAGER =====================
class FileManager:
    def __init__(self):
        for folder in [Config.AGENTS_FOLDER, Config.MODERATORS_FOLDER, 
                       Config.EXAMPLES_FOLDER, Config.EXPORTS_FOLDER,
                       Config.MEMORY_FOLDER]:  # NEU
            if not os.path.exists(folder):
                os.makedirs(folder)
    
    def get_agent_files(self) -> List[str]:
        return glob.glob(f"{Config.AGENTS_FOLDER}/*.json")
    
    def get_moderator_files(self) -> List[str]:
        return glob.glob(f"{Config.MODERATORS_FOLDER}/*.json")
    
    def get_example_files(self) -> List[str]:
        return glob.glob(f"{Config.EXAMPLES_FOLDER}/*.txt")
    
    def load_json_file(self, filepath: str) -> Optional[dict]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden von {filepath}: {e}")
            return None
    
    def load_text_file(self, filepath: str) -> Optional[str]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return None

# ===================== LM STUDIO =====================
class LMStudio:
    def __init__(self):
        self.url = Config.LM_STUDIO_URL
        self.session = requests.Session()
        self.stats = {"calls": 0, "errors": 0}
        
    def test(self) -> bool:
        try:
            r = self.session.post(self.url, json={
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5
            }, timeout=3)
            return r.status_code == 200
        except:
            return False
    
    def ask(self, prompt: str, system: str = None, stop_event: threading.Event = None) -> str:
        self.stats["calls"] += 1
        
        try:
            if stop_event and stop_event.is_set():
                return "[ABGEBROCHEN]"
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            r = self.session.post(self.url, json={
                "messages": messages,
                "max_tokens": Config.MAX_TOKENS,
                "temperature": Config.TEMPERATURE
            }, timeout=Config.TIMEOUT)
            
            if stop_event and stop_event.is_set():
                return "[ABGEBROCHEN]"
            
            text = r.json()["choices"][0]["message"]["content"]
            text = re.sub(r'(?i)(thinking|thought).*?(\n|$)', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text if text else "..."
            
        except Exception as e:
            self.stats["errors"] += 1
            return f"[Fehler: {str(e)[:30]}]"

# ===================== AGENT MIT GEDÄCHTNIS & LERNEN =====================
class Agent:
    def __init__(self, data: dict):
        self.name = data["name"]
        self.role = data["role"]
        self.personality = data["personality"]
        self.color = data["color"]
        self.goals = data.get("goals", [])
        self.fears = data.get("fears", [])
        self.education = data.get("education", "")
        self.background = data.get("background", "")
        
        self.mood = "neutral"
        self.energy = 100
        self.arguments = []
        self.last_response = ""
        
        # Kurzzeitgedächtnis
        self.schon_gesagtes = []
        self.wiederholungen = 0
        self.ausgeschlossen = False
        
        # NEU: Langzeitgedächtnis
        self.learned_facts = []
        self.known_positions = {}
        self.memory_file = f"{Config.MEMORY_FOLDER}/{self.name}.json"
        self.load_memory()
    
    # NEU: Memory-Funktionen
    def load_memory(self):
        """Frühere Diskussionen laden"""
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)
                self.learned_facts = memory.get('facts', [])
                self.known_positions = memory.get('positions', {})
        except:
            self.learned_facts = []
            self.known_positions = {}
    
    def save_memory(self):
        """Wissen speichern"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'facts': self.learned_facts[-50:],
                    'positions': self.known_positions
                }, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def answer(self, topic: str, document: Optional[str], 
               lm: LMStudio, stop_event: threading.Event = None) -> str:
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        # Basis-Prompt
        base_prompt = f"""Du bist {self.name}, {self.role}.

Charakter: {self.personality}
Bildung: {self.education}
Hintergrund: {self.background}

Thema: {topic}"""

        # NEU: Vorwissen einbauen
        if self.learned_facts:
            base_prompt += f"\n\nWas du aus früheren Diskussionen gelernt hast:\n"
            for fact in self.learned_facts[-3:]:
                base_prompt += f"- {fact}\n"
        
        # NEU: Dokument besser verarbeiten
        if document and document.strip():
            chunks = [document[i:i+400] for i in range(0, len(document), 400)]
            doc_insights = []
            for chunk in chunks[:2]:
                insight = lm.ask(f"Fasse den Kern dieser Passage in 1 Satz zusammen: {chunk}")
                if insight and insight != "[ABGEBROCHEN]":
                    doc_insights.append(insight)
            
            base_prompt += f"\n\nDokument-Kernaussagen:\n"
            for insight in doc_insights:
                base_prompt += f"- {insight}\n"
        
        # Kurzzeitgedächtnis
        if self.schon_gesagtes:
            letzte_beitraege = self.schon_gesagtes[-3:]
            beitrags_history = "\n".join([f"- {b}" for b in letzte_beitraege])
            
            base_prompt += f"""
            
Deine letzten Beiträge:
{beitrags_history}

WICHTIG: Wiederhole dich NICHT! Du hast diese Argumente bereits gebracht.
Formuliere ein NEUES Argument oder eine NEUE Perspektive.
Wenn du nichts Neues zu sagen hast, sage: "Ich habe keine neuen Argumente mehr."
Antworte in 1-2 Sätzen."""
        
        response = lm.ask(base_prompt, f"Du bist {self.name}.", stop_event)
        
        if response and response not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
            # Wiederholungscheck
            if response in self.schon_gesagtes[-5:]:
                self.wiederholungen += 1
                if self.wiederholungen >= 3:
                    self.ausgeschlossen = True
                    return "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]"
                else:
                    warn_prompt = f"{base_prompt}\n\nACHTUNG: Das hast du schon gesagt! Sag etwas ANDERES!"
                    response = lm.ask(warn_prompt, f"Du bist {self.name}.", stop_event)
            
            # Speichern
            self.schon_gesagtes.append(response)
            self.arguments.append(response)
            self.last_response = response
            self.energy = max(0, self.energy - 5)
            
            # NEU: Lernen aus der Antwort
            fact_check = lm.ask(
                f"Extrahiere 1 Fakt aus dieser Aussage: '{response}'",
                "Antworte nur mit einem kurzen Satz"
            )
            if fact_check and fact_check not in ["[ABGEBROCHEN]", "..."]:
                if "kein" not in fact_check.lower() and "nicht" not in fact_check.lower():
                    if fact_check not in self.learned_facts:
                        self.learned_facts.append(fact_check)
                        self.save_memory()
        
        return response
    
    def react_to(self, speaker: str, statement: str, topic: str,
                 lm: LMStudio, stop_event: threading.Event = None) -> str:
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        prompt = f"""Du bist {self.name}, {self.role}.

Charakter: {self.personality}

Thema der Diskussion: {topic}

{speaker} hat gerade gesagt: "{statement}"

Deine letzten Beiträge:
{chr(10).join([f"- {b}" for b in self.schon_gesagtes[-3:]])}

Wiederhole dich NICHT! Reagiere NEU auf das, was {speaker} gesagt hat.
Antworte in 1-2 Sätzen."""
        
        response = lm.ask(prompt, f"Du bist {self.name}.", stop_event)
        
        if response and response != "[ABGEBROCHEN]":
            self.schon_gesagtes.append(f"[Reaktion] {response}")
            self.last_response = response
        
        return response

# ===================== MODERATOR =====================
class Moderator:
    def __init__(self, data: dict):
        self.name = data["name"]
        self.role = data["role"]
        self.personality = data["personality"]
        self.color = data.get("color", "#c586c0")
        self.style = data.get("style", "professionell")
        self.education = data.get("education", "")
        self.background = data.get("background", "")
        self.goals = data.get("goals", [])
        self.fears = data.get("fears", [])
        
        self.intervention_styles = data.get("intervention_styles", {})
        self.question_styles = data.get("question_styles", {})
        self.max_evasions = data.get("max_evasions", 3)
        self.abbrechen_nach = data.get("abbrechen_nach", 3)
        
        self.enabled = True
        self.last_question = ""
        self.questions_asked = 0
        self.original_topic = ""
        self.evasions = {}
        self.abgebrochene_agenten = set()
    
    def introduce(self, topic: str, document: Optional[str], 
                  lm: LMStudio, stop_event: threading.Event = None) -> str:
        if not self.enabled:
            return ""
        
        self.original_topic = topic
        self.evasions = {}
        self.abgebrochene_agenten = set()
        
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        if document and document.strip():
            prompt = f"""Du bist {self.name}, {self.role}.

Deine Persönlichkeit: {self.personality}
Dein Stil: {self.style}

Thema heute: "{topic}"
Dokument/Kontext: {document[:200]}

Stelle dich KURZ vor (maximal 2 Sätze) und nenne das heutige Thema."""
        else:
            prompt = f"""Du bist {self.name}, {self.role}.

Deine Persönlichkeit: {self.personality}
Dein Stil: {self.style}

Thema heute: "{topic}"

Stelle dich KURZ vor (maximal 2 Sätze) und nenne das heutige Thema."""
        
        return lm.ask(prompt, f"Du bist {self.name}.", stop_event)
    
    def ask_question(self, agent_name: str, agent_role: str, agent_personality: str,
                     topic: str, document: Optional[str], context: str,
                     lm: LMStudio, stop_event: threading.Event = None) -> Optional[str]:
        if not self.enabled:
            return None
        
        if stop_event and stop_event.is_set():
            return None
        
        if agent_name in self.abgebrochene_agenten:
            return None
        
        self.questions_asked += 1
        evasion_count = self.evasions.get(agent_name, 0)
        
        if evasion_count == 0:
            question_style = self.question_styles.get("first", "Stelle eine Frage zum Thema.")
        else:
            question_style = self.question_styles.get("repeat", "Du hast bereits nachgefragt. Stelle die Frage erneut, aber direkter.")
        
        if document and document.strip():
            prompt = f"""Du bist {self.name}, {self.role}.

Deine Persönlichkeit: {self.personality}
Dein Stil: {self.style}

DAS THEMA: "{topic}"

Dokument/Kontext zum Thema:
{document[:300]}

Du moderierst eine Diskussion. Jetzt ist {agent_name} ({agent_role}) an der Reihe.
Charakter von {agent_name}: {agent_personality}

Bisherige Diskussion:
{context[:200]}

{question_style}

Stelle {agent_name} JETZT eine Frage ZUM THEMA "{topic}".
Formuliere EINE präzise Frage (maximal 2 Sätze)."""
        else:
            prompt = f"""Du bist {self.name}, {self.role}.

Deine Persönlichkeit: {self.personality}
Dein Stil: {self.style}

DAS THEMA: "{topic}"

Du moderierst eine Diskussion. Jetzt ist {agent_name} ({agent_role}) an der Reihe.
Charakter von {agent_name}: {agent_personality}

Bisherige Diskussion:
{context[:200]}

{question_style}

Stelle {agent_name} JETZT eine Frage ZUM THEMA "{topic}".
Formuliere EINE präzise Frage (maximal 2 Sätze)."""
        
        question = lm.ask(prompt, f"Du bist {self.name}.", stop_event)
        self.last_question = question
        return question
    
    def intervene(self, agent_name: str, last_statement: str, topic: str,
                  lm: LMStudio, stop_event: threading.Event = None) -> Tuple[Optional[str], bool]:
        if not self.enabled:
            return None, False
        
        if stop_event and stop_event.is_set():
            return None, False
        
        if agent_name in self.abgebrochene_agenten:
            return None, False
        
        self.evasions[agent_name] = self.evasions.get(agent_name, 0) + 1
        evasion_count = self.evasions[agent_name]
        
        if evasion_count == 1:
            style_key = "first"
        elif evasion_count == 2:
            style_key = "second"
        else:
            style_key = "third"
        
        intervention = self.intervention_styles.get(style_key, {})
        intervention_text_template = intervention.get("text", "Bitte bleiben Sie beim Thema {topic}.")
        
        try:
            intervention_text = intervention_text_template.format(
                name=agent_name,
                topic=topic
            )
        except:
            intervention_text = f"Bitte bleiben Sie beim Thema {topic}, {agent_name}."
        
        abbrechen = evasion_count >= self.abbrechen_nach
        if abbrechen:
            self.abgebrochene_agenten.add(agent_name)
            return f"⛔ [ABBRUCH] {agent_name} wird wegen dauerhafter Themenverfehlung ausgeschlossen!", True
        
        return intervention_text, False
    
    def summarize(self, discussion: str, topic: str, 
                  lm: LMStudio, stop_event: threading.Event = None) -> str:
        if not self.enabled:
            return ""
        
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        prompt = f"""Du bist {self.name}, {self.role}.

Deine Persönlichkeit: {self.personality}
Dein Stil: {self.style}

Thema der Debatte war: "{topic}"

Diskussionsverlauf:
{discussion[:600]}

Fasse in 2-3 Sätzen zusammen, welche Positionen zu DIESEM Thema vertreten wurden.
Bleib dabei in deinem charakteristischen Stil."""
        
        return lm.ask(prompt, f"Du bist {self.name}.", stop_event)

# ===================== SIMULATION =====================
class Simulation:
    def __init__(self):
        self.lm = LMStudio()
        self.agents: List[Agent] = []
        self.moderator: Optional[Moderator] = None
        self.config_name = ""
        self.stop_event = threading.Event()
        self.is_running = False
        self.discussion_log = []
    
    def load_agents(self, filepath: str) -> bool:
        try:
            data = FileManager().load_json_file(filepath)
            if not data:
                return False
            
            self.config_name = data.get("name", "Unbekannt")
            self.agents = [Agent(a) for a in data["agents"]]
            return True
        except:
            return False
    
    def load_moderator(self, filepath: str) -> bool:
        try:
            data = FileManager().load_json_file(filepath)
            if not data:
                return False
            
            self.moderator = Moderator(data)
            return True
        except:
            return False
    
    def stop(self):
        self.stop_event.set()
        self.is_running = False
    
    def start_discussion(self, topic: str, document: Optional[str], 
                         rounds: int = 2, use_moderator: bool = True):
        self.stop_event.clear()
        self.is_running = True
        self.discussion_log = []
        
        for agent in self.agents:
            agent.schon_gesagtes = []
            agent.wiederholungen = 0
            agent.ausgeschlossen = False
        
        if self.moderator:
            self.moderator.enabled = use_moderator
            self.moderator.evasions = {}
            self.moderator.abgebrochene_agenten = set()
        
        if use_moderator and self.moderator:
            intro = self.moderator.introduce(topic, document, self.lm, self.stop_event)
            if intro and intro != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 {intro}")
                self.discussion_log.append(f"Moderator: {intro}")
                time.sleep(0.5)
        else:
            yield ("system", "📢 Diskussion ohne Moderator gestartet")
            self.discussion_log.append("System: Diskussion ohne Moderator")
        
        for round_num in range(rounds):
            if self.stop_event.is_set():
                break
            
            for agent in self.agents:
                if self.stop_event.is_set():
                    break
                
                if agent.ausgeschlossen:
                    continue
                
                if use_moderator and self.moderator:
                    if agent.name in self.moderator.abgebrochene_agenten:
                        continue
                    
                    context = "\n".join(self.discussion_log[-5:]) if self.discussion_log else ""
                    question = self.moderator.ask_question(
                        agent.name, agent.role, agent.personality,
                        topic, document, context, self.lm, self.stop_event
                    )
                    
                    if question and question != "[ABGEBROCHEN]":
                        yield ("moderator", f"🎭 An {agent.name}: {question}")
                        self.discussion_log.append(f"Moderator an {agent.name}: {question}")
                        time.sleep(0.3)
                        
                        answer = agent.answer(topic, document, self.lm, self.stop_event)
                        
                        if answer == "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]":
                            yield ("system", f"⛔ {agent.name} wurde wegen dauerhafter Wiederholung ausgeschlossen!")
                            self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                        elif answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                            yield ("agent", agent.name, answer, agent.color)
                            self.discussion_log.append(f"{agent.name}: {answer}")
                            time.sleep(0.3)
                            
                            intervention, abbrechen = self.moderator.intervene(
                                agent.name, answer, topic, self.lm, self.stop_event
                            )
                            if intervention:
                                yield ("moderator", f"🎭 ⚠️ {intervention}")
                                self.discussion_log.append(f"Moderator: {intervention}")
                                if abbrechen:
                                    yield ("system", f"⛔ {agent.name} wurde vom Moderator ausgeschlossen!")
                                    self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                
                else:
                    answer = agent.answer(topic, document, self.lm, self.stop_event)
                    
                    if answer == "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]":
                        yield ("system", f"⛔ {agent.name} wurde wegen dauerhafter Wiederholung ausgeschlossen!")
                        self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                    elif answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        yield ("agent", agent.name, answer, agent.color)
                        self.discussion_log.append(f"{agent.name}: {answer}")
                        time.sleep(0.3)
                
                if round_num < rounds - 1 and not self.stop_event.is_set():
                    for other in self.agents:
                        if (other.name != agent.name and not other.ausgeschlossen and 
                            not self.stop_event.is_set()):
                            if use_moderator and self.moderator:
                                if other.name in self.moderator.abgebrochene_agenten:
                                    continue
                            
                            reaction = other.react_to(agent.name, agent.last_response, topic,
                                                      self.lm, self.stop_event)
                            if reaction and reaction not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                                yield ("agent", other.name, f"[Reaktion] {reaction}", other.color)
                                self.discussion_log.append(f"{other.name} reagiert: {reaction}")
                                time.sleep(0.2)
        
        if not self.stop_event.is_set() and use_moderator and self.moderator:
            summary = self.moderator.summarize(
                "\n".join(self.discussion_log[-10:]), topic, self.lm, self.stop_event
            )
            if summary and summary != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 📋 ZUSAMMENFASSUNG: {summary}")
        
        self.is_running = False

# ===================== GUI =====================
class MiroFishUltimateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🐟 SynthAgora - Mit Gedächtnis & Lernen")
        self.root.geometry("1400x900")
        self.root.configure(bg=Config.BG_MAIN)
        
        self.fm = FileManager()
        self.sim = Simulation()
        self.msg_queue = queue.Queue()
        
        self._setup_ui()
        self._check_lm()
        self._refresh_lists()
        self._process_queue()
    
    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=Config.BG_MAIN, borderwidth=0)
        style.configure('TNotebook.Tab', background=Config.BG_PANEL, foreground=Config.FG, 
                       padding=[15, 8], font=('Segoe UI', 10))
        style.map('TNotebook.Tab', background=[('selected', Config.BG_BUTTON)])
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.tab_main = tk.Frame(self.notebook, bg=Config.BG_MAIN)
        self.notebook.add(self.tab_main, text="🎮 Debatte")
        self._setup_main_tab()
        
        self.tab_agents = tk.Frame(self.notebook, bg=Config.BG_MAIN)
        self.notebook.add(self.tab_agents, text="👥 Agenten")
        self._setup_agents_tab()
        
        self.tab_chat = tk.Frame(self.notebook, bg=Config.BG_MAIN)
        self.notebook.add(self.tab_chat, text="📜 Verlauf")
        self._setup_chat_tab()
        
        self._setup_control_bar()
        self._setup_statusbar()
    
    def _setup_main_tab(self):
        agent_frame = tk.LabelFrame(self.tab_main, text="📁 Agenten-Set", 
                                    bg=Config.BG_PANEL, fg=Config.FG,
                                    font=("Segoe UI", 12, "bold"))
        agent_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.agent_var = tk.StringVar()
        self.agent_combo = ttk.Combobox(agent_frame, textvariable=self.agent_var,
                                        state="readonly", width=60)
        self.agent_combo.pack(pady=10, padx=10)
        
        self.load_agents_btn = self._create_button(agent_frame, "🔄 AGENTEN LADEN", 
                                                   Config.BG_BUTTON, self.load_selected_agents)
        self.load_agents_btn.pack(pady=(0,10))
        
        mod_frame = tk.LabelFrame(self.tab_main, text="🎭 Moderator", 
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   font=("Segoe UI", 12, "bold"))
        mod_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.use_moderator_var = tk.BooleanVar(value=True)
        mod_check = tk.Checkbutton(mod_frame, text="✅ Moderator verwenden", 
                                   variable=self.use_moderator_var,
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   selectcolor=Config.BG_PANEL,
                                   font=("Segoe UI", 11))
        mod_check.pack(anchor=tk.W, padx=10, pady=(10,5))
        
        mod_select_frame = tk.Frame(mod_frame, bg=Config.BG_PANEL)
        mod_select_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        
        self.mod_var = tk.StringVar()
        self.mod_combo = ttk.Combobox(mod_select_frame, textvariable=self.mod_var,
                                      state="readonly", width=60)
        self.mod_combo.pack(side=tk.LEFT, padx=(0,10))
        
        self.load_mod_btn = self._create_button(mod_select_frame, "🎭 LADEN", 
                                                Config.BG_INPUT, self.load_selected_moderator)
        self.load_mod_btn.pack(side=tk.LEFT)
        
        topic_frame = tk.LabelFrame(self.tab_main, text="🎯 Thema", 
                                    bg=Config.BG_PANEL, fg=Config.FG,
                                    font=("Segoe UI", 12, "bold"))
        topic_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.topic_entry = tk.Entry(topic_frame,
                                   bg=Config.BG_INPUT, fg=Config.FG,
                                   font=("Segoe UI", 11), relief='flat',
                                   insertbackground=Config.FG)
        self.topic_entry.pack(fill=tk.X, padx=10, pady=10)
        self.topic_entry.insert(0, "Sollte Deutschland wieder eine Wehrpflicht einführen, auch für Frauen?")
        
        doc_frame = tk.LabelFrame(self.tab_main, text="📄 Dokument (optional)", 
                                  bg=Config.BG_PANEL, fg=Config.FG,
                                  font=("Segoe UI", 12, "bold"))
        doc_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        doc_toolbar = tk.Frame(doc_frame, bg=Config.BG_PANEL)
        doc_toolbar.pack(fill=tk.X, padx=10, pady=(10,0))
        
        self._create_button(doc_toolbar, "📁 Beispiel laden", Config.BG_INPUT, 
                           self.load_example_doc).pack(side=tk.LEFT, padx=5)
        
        self.example_var = tk.StringVar()
        self.example_combo = ttk.Combobox(doc_toolbar, textvariable=self.example_var,
                                         state="readonly", width=40)
        self.example_combo.pack(side=tk.LEFT, padx=5)
        
        self._create_button(doc_toolbar, "📖 Laden", Config.BG_INPUT,
                           self.load_selected_example).pack(side=tk.LEFT, padx=5)
        
        self.doc_text = tk.Text(doc_frame, height=6,
                                bg=Config.BG_INPUT, fg=Config.FG,
                                font=("Segoe UI", 10), wrap=tk.WORD,
                                relief='flat', insertbackground=Config.FG)
        self.doc_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        opt_frame = tk.Frame(self.tab_main, bg=Config.BG_MAIN)
        opt_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(opt_frame, text="Runden:", bg=Config.BG_MAIN, fg=Config.FG,
                font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=5)
        
        self.rounds_var = tk.StringVar(value="3")
        spin = tk.Spinbox(opt_frame, from_=1, to=10, textvariable=self.rounds_var,
                         width=5, bg=Config.BG_INPUT, fg=Config.FG,
                         relief='flat', buttonbackground=Config.BG_BUTTON)
        spin.pack(side=tk.LEFT, padx=5)
        
        self.start_btn = self._create_button(self.tab_main, "🎬 DISKUSSION STARTEN", 
                                             Config.BG_BUTTON, self.start_discussion)
        self.start_btn.pack(pady=20)
    
    def _setup_agents_tab(self):
        canvas = tk.Canvas(self.tab_agents, bg=Config.BG_MAIN, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_agents, orient=tk.VERTICAL, command=canvas.yview)
        
        self.agents_frame = tk.Frame(canvas, bg=Config.BG_MAIN)
        self.agents_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=self.agents_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_chat_tab(self):
        toolbar = tk.Frame(self.tab_chat, bg=Config.BG_PANEL)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        
        self._create_button(toolbar, "💾 Exportieren", Config.BG_BUTTON, self.export_chat).pack(side=tk.LEFT, padx=5)
        self._create_button(toolbar, "🗑️ Löschen", Config.BG_STOP, self.clear_chat).pack(side=tk.LEFT, padx=5)
        
        self.chat_count_label = tk.Label(toolbar, text="Einträge: 0", 
                                        bg=Config.BG_PANEL, fg=Config.FG,
                                        font=("Segoe UI", 10))
        self.chat_count_label.pack(side=tk.RIGHT, padx=10)
        
        self.chat_text = scrolledtext.ScrolledText(
            self.tab_chat,
            bg=Config.BG_INPUT,
            fg=Config.FG,
            font=("Consolas", 10),
            wrap=tk.WORD
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
    
    def _setup_control_bar(self):
        control_frame = tk.Frame(self.root, bg=Config.BG_MAIN)
        control_frame.pack(fill=tk.X, padx=10, pady=(0,5))
        
        self.stop_btn = self._create_button(control_frame, "⛔ SIMULATION STOPPEN", 
                                           Config.BG_STOP, self.stop_simulation,
                                           hover_color=Config.BG_STOP_HOVER)
        self.stop_btn.config(state=tk.DISABLED)
        self.stop_btn.pack()
    
    def _setup_statusbar(self):
        self.statusbar = tk.Label(self.root, text="Bereit",
                                  bg=Config.BG_BUTTON, fg=Config.FG,
                                  anchor=tk.W, padx=10,
                                  font=("Segoe UI", 10))
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _create_button(self, parent, text, bg_color, command, hover_color=None):
        btn = tk.Button(parent, text=text,
                       bg=bg_color, fg=Config.FG_BUTTON,
                       font=("Segoe UI", 11, "bold"),
                       relief='flat', padx=15, pady=8,
                       cursor='hand2', command=command)
        
        def on_enter(e):
            btn.config(bg=hover_color or Config.BG_BUTTON_HOVER)
        
        def on_leave(e):
            btn.config(bg=bg_color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn
    
    def _refresh_lists(self):
        agent_files = self.fm.get_agent_files()
        agent_names = [os.path.basename(f) for f in agent_files]
        self.agent_combo['values'] = agent_names
        if agent_names:
            self.agent_combo.current(0)
        
        mod_files = self.fm.get_moderator_files()
        mod_names = [os.path.basename(f) for f in mod_files]
        self.mod_combo['values'] = mod_names
        if mod_names:
            self.mod_combo.current(0)
        
        example_files = self.fm.get_example_files()
        example_names = [os.path.basename(f) for f in example_files]
        self.example_combo['values'] = example_names
        if example_names:
            self.example_combo.current(0)
    
    def load_selected_agents(self):
        selection = self.agent_combo.get()
        if not selection:
            return
        
        filepath = f"{Config.AGENTS_FOLDER}/{selection}"
        if self.sim.load_agents(filepath):
            self._update_status(f"✅ Agenten geladen: {selection} ({len(self.sim.agents)} Agenten)")
            self._create_agent_cards()
            self._add_to_chat(f"\n=== GELADEN: {self.sim.config_name} ===")
            self._add_to_chat(f"👥 {len(self.sim.agents)} Agenten geladen")
        else:
            self._update_status("❌ Fehler beim Laden der Agenten")
    
    def load_selected_moderator(self):
        selection = self.mod_combo.get()
        if not selection:
            return
        
        filepath = f"{Config.MODERATORS_FOLDER}/{selection}"
        if self.sim.load_moderator(filepath):
            self._update_status(f"✅ Moderator geladen: {self.sim.moderator.name}")
            self._add_to_chat(f"🎭 Moderator: {self.sim.moderator.name} ({self.sim.moderator.style})")
        else:
            self._update_status("❌ Fehler beim Laden des Moderators")
    
    def load_selected_example(self):
        selection = self.example_combo.get()
        if not selection:
            return
        
        filepath = f"{Config.EXAMPLES_FOLDER}/{selection}"
        content = self.fm.load_text_file(filepath)
        if content:
            self.doc_text.delete(1.0, tk.END)
            self.doc_text.insert(1.0, content)
            self._update_status(f"📄 Beispiel geladen: {selection}")
    
    def load_example_doc(self):
        filepath = filedialog.askopenfilename(
            title="Beispiel-Dokument laden",
            initialdir=Config.EXAMPLES_FOLDER,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            content = self.fm.load_text_file(filepath)
            if content:
                self.doc_text.delete(1.0, tk.END)
                self.doc_text.insert(1.0, content)
                self._update_status(f"📄 Geladen: {os.path.basename(filepath)}")
    
    def _create_agent_cards(self):
        for widget in self.agents_frame.winfo_children():
            widget.destroy()
        
        for agent in self.sim.agents:
            self._create_agent_card(agent)
    
    def _create_agent_card(self, agent):
        card = tk.Frame(self.agents_frame, bg=Config.BG_PANEL, relief='flat')
        card.pack(fill=tk.X, pady=5, padx=10)
        
        header = tk.Frame(card, bg=agent.color, height=40)
        header.pack(fill=tk.X)
        
        tk.Label(header, text=agent.name, bg=agent.color, 
                fg="#000000", font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT, padx=10, pady=8)
        
        tk.Label(header, text=agent.role, bg=agent.color,
                fg="#000000", font=("Segoe UI", 10)).pack(side=tk.RIGHT, padx=10, pady=8)
        
        content = tk.Frame(card, bg=Config.BG_INPUT)
        content.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0,1))
        
        pers_frame = tk.Frame(content, bg=Config.BG_INPUT)
        pers_frame.pack(fill=tk.X, padx=10, pady=8)
        
        tk.Label(pers_frame, text="💭 Persönlichkeit:", 
                bg=Config.BG_INPUT, fg=Config.FG,
                font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        
        tk.Label(pers_frame, text=agent.personality,
                bg=Config.BG_INPUT, fg=Config.FG,
                wraplength=700, justify=tk.LEFT,
                font=("Segoe UI", 9)).pack(anchor=tk.W, pady=2)
        
        info_frame = tk.Frame(content, bg=Config.BG_INPUT)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        if agent.education:
            tk.Label(info_frame, text=f"🎓 {agent.education}", 
                    bg=Config.BG_INPUT, fg=Config.FG_DIM,
                    font=("Segoe UI", 9)).pack(anchor=tk.W)
        
        if agent.background:
            tk.Label(info_frame, text=f"📖 {agent.background}", 
                    bg=Config.BG_INPUT, fg=Config.FG_DIM,
                    font=("Segoe UI", 9)).pack(anchor=tk.W)
        
        # NEU: Fakten-Anzeige
        facts_frame = tk.Frame(content, bg=Config.BG_INPUT)
        facts_frame.pack(fill=tk.X, padx=10, pady=2)
        
        fact_count = len(agent.learned_facts)
        tk.Label(facts_frame, text=f"📚 Gelernte Fakten: {fact_count}", 
                bg=Config.BG_INPUT, fg=Config.FG_DIM,
                font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        status_frame = tk.Frame(content, bg=Config.BG_INPUT)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = tk.Label(status_frame, text="✅ Aktiv", 
                                     bg=Config.BG_INPUT, fg=Config.SUCCESS,
                                     font=("Segoe UI", 9, "bold"))
        self.status_label.pack(side=tk.LEFT)
        
        response_frame = tk.Frame(content, bg=agent.color)
        response_frame.pack(fill=tk.X, padx=10, pady=8)
        
        response_label = tk.Label(response_frame, text="Bereit...",
                                 bg=agent.color, fg="#000000",
                                 font=("Segoe UI", 9), wraplength=700,
                                 justify=tk.LEFT, padx=8, pady=5)
        response_label.pack(fill=tk.X)
        
        card.response_label = response_label
        card.status_label = self.status_label
    
    def _check_lm(self):
        if self.sim.lm.test():
            self.statusbar.config(text="✅ LM Studio verbunden", bg=Config.SUCCESS)
        else:
            self.statusbar.config(text="⚠️ LM Studio nicht erreichbar", bg=Config.ERROR)
        self.root.after(5000, self._check_lm)
    
    def _update_status(self, text):
        self.statusbar.config(text=text, bg=Config.BG_BUTTON)
    
    def _add_to_chat(self, text):
        self.chat_text.insert(tk.END, text + "\n")
        self.chat_text.see(tk.END)
        
        count = len(self.chat_text.get(1.0, tk.END).split('\n'))
        self.chat_count_label.config(text=f"Einträge: {count-1}")
    
    def stop_simulation(self):
        if self.sim.is_running:
            self.sim.stop()
            self.stop_btn.config(state=tk.DISABLED)
            self._add_to_chat("\n⛔ SIMULATION GESTOPPT\n")
            self._update_status("Simulation gestoppt")
    
    def _enable_stop_button(self):
        self.stop_btn.config(state=tk.NORMAL)
    
    def _disable_stop_button(self):
        self.stop_btn.config(state=tk.DISABLED)
    
    def start_discussion(self):
        if self.sim.is_running:
            messagebox.showwarning("Achtung", "Simulation läuft bereits!")
            return
        
        if not self.sim.agents:
            messagebox.showwarning("Achtung", "Bitte erst Agenten laden!")
            return
        
        use_moderator = self.use_moderator_var.get()
        if use_moderator and not self.sim.moderator:
            messagebox.showwarning("Achtung", "Bitte erst Moderator laden oder Moderator deaktivieren!")
            return
        
        topic = self.topic_entry.get().strip()
        if not topic:
            messagebox.showwarning("Achtung", "Bitte Thema eingeben!")
            return
        
        document = self.doc_text.get(1.0, tk.END).strip()
        if not document:
            document = None
        
        rounds = int(self.rounds_var.get())
        
        self.start_btn.config(state=tk.DISABLED)
        self._enable_stop_button()
        
        self._add_to_chat(f"\n{'='*60}")
        self._add_to_chat(f"🎯 THEMA: {topic}")
        if document:
            self._add_to_chat(f"📄 Mit Dokument")
        if use_moderator and self.sim.moderator:
            self._add_to_chat(f"🎭 Moderator: {self.sim.moderator.name} ({self.sim.moderator.style})")
        else:
            self._add_to_chat(f"👥 Ohne Moderator")
        self._add_to_chat(f"👥 {len(self.sim.agents)} Agenten")
        self._add_to_chat(f"📚 Agenten lernen aus der Diskussion")
        self._add_to_chat(f"{'='*60}\n")
        
        thread = threading.Thread(
            target=self._process_discussion, 
            args=(topic, document, rounds, use_moderator)
        )
        thread.daemon = True
        thread.start()
    
    def _process_discussion(self, topic, document, rounds, use_moderator):
        try:
            for msg_type, *content in self.sim.start_discussion(topic, document, rounds, use_moderator):
                if msg_type == "moderator":
                    self.msg_queue.put(("moderator", content[0]))
                elif msg_type == "agent":
                    name, text, color = content
                    self.msg_queue.put(("agent", name, text, color))
                    self.msg_queue.put(("update", name, text))
                elif msg_type == "system":
                    self.msg_queue.put(("system", content[0]))
        finally:
            self.msg_queue.put(("done",))
    
    def _process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                
                if msg[0] == "moderator":
                    _, text = msg
                    self._add_to_chat(f"🎭 {text}")
                    
                elif msg[0] == "agent":
                    _, name, text, color = msg
                    self._add_to_chat(f"🗣️ {name}: {text}")
                    
                elif msg[0] == "system":
                    _, text = msg
                    self._add_to_chat(f"📢 {text}")
                    
                elif msg[0] == "update":
                    _, name, text = msg
                    self._update_agent_response(name, text)
                    
                elif msg[0] == "done":
                    self._disable_stop_button()
                    self.start_btn.config(state=tk.NORMAL)
                    self._add_to_chat("\n✅ Diskussion beendet\n")
                    
        except queue.Empty:
            pass
        
        self.root.after(50, self._process_queue)
    
    def _update_agent_response(self, name, response):
        for widget in self.agents_frame.winfo_children():
            if hasattr(widget, 'response_label'):
                header = widget.winfo_children()[0]
                for label in header.winfo_children():
                    if isinstance(label, tk.Label) and label.cget("text") == name:
                        widget.response_label.config(text=response[:150] + "..." if len(response) > 150 else response)
                        
                        agent = next((a for a in self.sim.agents if a.name == name), None)
                        if agent:
                            if agent.ausgeschlossen:
                                widget.status_label.config(text="⛔ Ausgeschlossen", fg=Config.ERROR)
                            else:
                                widget.status_label.config(text=f"✅ Aktiv ({len(agent.schon_gesagtes)} Beiträge, {len(agent.learned_facts)} Fakten)", fg=Config.SUCCESS)
                        return
    
    def export_chat(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Config.EXPORTS_FOLDER}/chat_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.chat_text.get(1.0, tk.END))
            self._update_status(f"✅ Exportiert: {os.path.basename(filename)}")
        except:
            messagebox.showerror("Fehler", "Export fehlgeschlagen")
    
    def clear_chat(self):
        if messagebox.askyesno("Chat löschen", "Wirklich löschen?"):
            self.chat_text.delete(1.0, tk.END)
            self._update_status("Chat gelöscht")

# ===================== START =====================
def main():
    root = tk.Tk()
    app = MiroFishUltimateGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()