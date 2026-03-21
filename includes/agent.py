#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent-Klasse für SynthAgora
- PERSÖNLICHKEITS-GESTEUERTE ARGUMENTATION
- CHARAKTER-TYP BEEINFLUSST ANTWORT-STIL
- ZIELE UND ÄNGSTE BEEINFLUSSEN ARGUMENTATION
- LERNEN MIT SCORE-BASIERTER LLM-ENTSCHEIDUNG (0-100)
- SKILL-ENTWICKLUNG (fachwissen, kommunikation, analyse, kreativität, diplomatie)
- ERFAHRUNGSPUNKTE UND RANG-SYSTEM (Junior → Senior → Experte → Master)
- PERSISTENTE ERINNERUNGEN IN SQLITE
- DUPLIKAT-ERKENNUNG (RAM + DB + Text-Ähnlichkeit + Zeit-basiert)
- GLOBALE DUPLIKAT-ERKENNUNG MIT THREAD-LOCK
"""

import json
import random
import re
import time
import hashlib
import uuid
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

from .config import Config


class Agent:
    """
    Ein Agent mit Persönlichkeit, Gedächtnis und Lernfähigkeit.
    """
    
    # Klassenweiter Lock für globale Duplikat-Prüfung (thread-safe)
    _global_lock = threading.Lock()
    
    # Rang-Schwellwerte (Erfahrungspunkte)
    RANK_THRESHOLDS = Config.RANK_THRESHOLDS
    
    # Skill-Steigerungs-Faktoren pro Lernvorgang
    SKILL_GAIN_FACTOR = Config.SKILL_GAIN_FACTOR
    
    def __init__(self, data: dict, knowledge_graph=None, external_source=None):
        """
        Initialisiert einen Agenten aus JSON-Daten.
        """
        # Basisdaten
        self.name = data["name"]
        self.role = data["role"]
        self.personality = data["personality"]
        self.color = data.get("color", "#cccccc")
        
        # Erweiterte Daten
        self.education = data.get("education", "")
        self.background = data.get("background", "")
        self.goals = data.get("goals", [])
        self.fears = data.get("fears", [])
        self.team = data.get("team", "")
        self.team_role = data.get("team_role", "Mitglied")
        self.charakter_typ = data.get("charakter_typ", "Realist")
        
        # Persönlichkeits-Traits (können sich entwickeln)
        self.personality_traits = {
            "offenheit": data.get("offenheit", 0.5),
            "gewissenhaftigkeit": data.get("gewissenhaftigkeit", 0.5),
            "extraversion": data.get("extraversion", 0.5),
            "verträglichkeit": data.get("verträglichkeit", 0.5),
            "neurotizismus": data.get("neurotizismus", 0.5)
        }
        
        # Skills (werden aus DB geladen oder initialisiert)
        self.skills = {
            "fachwissen": 0.5,
            "kommunikation": 0.5,
            "analyse": 0.5,
            "kreativitaet": 0.5,
            "diplomatie": 0.5
        }
        
        # Evolutionsdaten
        self.experience_points = 0
        self.rank = "Junior"
        self.total_discussions = 0
        self.total_contributions = 0
        self.total_learned_facts = 0
        self.total_analyses = 0
        self.total_influences_given = 0
        self.total_influences_received = 0
        self.total_score_points = 0
        self.evolution_history = []
        
        # Lernfähigkeit
        self.training_level = 1.0
        self.learned_facts = []
        self.schon_gesagtes = []
        self.wiederholungen = 0
        self.ausgeschlossen = False
        
        # Aktuelle Position
        self.current_position = None
        self.last_response = ""
        self.influenced_by = []
        self.influenced_others = []
        
        # Referenzen
        self.knowledge_graph = knowledge_graph
        self.external_source = external_source
        self.db = None
        self.sim = None
        
        # Agent-ID (wird später von DB gesetzt oder generiert)
        self.agent_id = data.get("agent_id", f"agent_{self.name.lower().replace(' ', '_')}")
        
        # GUI-Komponenten
        self.status_label = None
        self.response_label = None
        
        # Diskussions-Log
        self.discussion_log = []
        
        # Cache für gelernte Fakten-Hashes (wird VOR DB-Speicherung eingefügt)
        self.learned_hashes = set()
        
        print(f"✅ Agent {self.name} ({self.charakter_typ}) initialisiert")
    
    def set_db(self, db):
        """Setzt Datenbank-Referenz und lädt Skills/Evolution"""
        self.db = db
        self._load_skills_from_db()
        self._load_evolution_from_db()
        self._load_existing_hashes()
    
    def set_simulation(self, sim):
        """Setzt Simulations-Referenz für Callbacks"""
        self.sim = sim
    
    def set_external_source(self, external_source):
        """Setzt externe Quelle für Recherchen"""
        self.external_source = external_source
    
    def _load_skills_from_db(self):
        """Lädt Skills aus der Datenbank"""
        if not self.db:
            return
        try:
            skills = self.db.get_agent_skills(self.agent_id)
            if skills:
                self.skills = skills
                print(f"📚 {self.name}: Skills geladen (Fachwissen: {skills['fachwissen']:.2f}, Kommunikation: {skills['kommunikation']:.2f})")
        except Exception as e:
            print(f"⚠️ Fehler beim Laden der Skills: {e}")
    
    def _load_evolution_from_db(self):
        """Lädt Evolutionsdaten aus der Datenbank"""
        if not self.db:
            return
        try:
            evolution = self.db.get_agent_evolution(self.agent_id)
            if evolution:
                self.experience_points = evolution.get("experience_points", 0)
                self.rank = evolution.get("rank", "Junior")
                self.total_discussions = evolution.get("total_discussions", 0)
                self.total_contributions = evolution.get("total_contributions", 0)
                self.total_learned_facts = evolution.get("total_learned_facts", 0)
                self.total_analyses = evolution.get("total_analyses", 0)
                self.total_influences_given = evolution.get("total_influences_given", 0)
                self.total_influences_received = evolution.get("total_influences_received", 0)
                self.total_score_points = evolution.get("total_score_points", 0)
                self.evolution_history = evolution.get("evolution_history", [])
                print(f"🏆 {self.name}: Rang {self.rank} ({self.experience_points} XP)")
        except Exception as e:
            print(f"⚠️ Fehler beim Laden der Evolution: {e}")
    
    def _load_existing_hashes(self):
        """Lädt Hashes aller vorhandenen Erinnerungen für Duplikat-Check"""
        if not self.db:
            return
        try:
            # Stelle sicher dass der Agent in der DB existiert, bevor wir seine Erinnerungen laden
            agent_exists = self.db.get_agent(self.agent_id)
            if not agent_exists:
                # Agent noch nicht in DB → keine Erinnerungen
                return
            
            memories = self.db.get_agent_memories(self.agent_id, limit=Config.MAX_MEMORY_RESULTS)
            for mem in memories:
                fact = mem.get('fact', '')
                fact_hash = hashlib.md5(fact.encode()).hexdigest()
                self.learned_hashes.add(fact_hash)
            print(f"📚 {self.name}: {len(self.learned_hashes)} bestehende Erinnerungen geladen")
        except Exception as e:
            print(f"⚠️ Fehler beim Laden der bestehenden Hashes: {e}")
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Berechnet einfache Jaccard-Ähnlichkeit zwischen zwei Texten"""
        if not text1 or not text2:
            return 0.0
        t1 = text1.lower().replace('.', '').replace(',', '').replace('!', '').replace('?', '')
        t2 = text2.lower().replace('.', '').replace(',', '').replace('!', '').replace('?', '')
        words1 = set(t1.split())
        words2 = set(t2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)
    
    def _global_duplicate_check(self, fact: str, topic: str) -> bool:
        """
        Prüft ob eine ähnliche Tatsache bereits von IRGENDEINEM Agenten gelernt wurde.
        Verwendet Text-Ähnlichkeit statt exaktem Match.
        MIT LOCK um Race-Conditions zu vermeiden.
        """
        if not self.db:
            return False
        
        with Agent._global_lock:
            try:
                return self.db.is_duplicate_fact(fact, topic, Config.DUPLICATE_SIMILARITY_THRESHOLD)
            except Exception as e:
                print(f"⚠️ Globaler Duplikat-Check fehlgeschlagen: {e}")
                return False
    
    def _is_duplicate(self, statement: str) -> bool:
        """
        Prüft ob eine Aussage bereits als Erinnerung existiert.
        Prüft in: RAM (alle gelernten Fakten), Hash-Cache, DB.
        Verwendet einheitliche Schwelle aus Config.
        """
        # 1. Schneller Hash-Check
        statement_hash = hashlib.md5(statement.encode()).hexdigest()
        if statement_hash in self.learned_hashes:
            print(f"⏭️ {self.name}: Duplikat per Hash erkannt")
            return True
        
        # 2. RAM-Check mit ALLEN gelernten Fakten
        for fact in self.learned_facts:
            similarity = self._text_similarity(statement, fact['fact'])
            if similarity > Config.LOCAL_DUPLICATE_THRESHOLD:
                print(f"⏭️ {self.name}: Duplikat im RAM erkannt (Ähnlichkeit: {similarity:.2f})")
                return True
        
        # 3. DB-Check mit bestehenden Erinnerungen (eigene)
        if self.db:
            existing_memories = self.db.get_agent_memories(self.agent_id, limit=100)
            for mem in existing_memories:
                existing_fact = mem.get('fact', '')
                similarity = self._text_similarity(statement, existing_fact)
                if similarity > Config.LOCAL_DUPLICATE_THRESHOLD:
                    print(f"⏭️ {self.name}: Duplikat in eigener DB erkannt (Ähnlichkeit: {similarity:.2f})")
                    return True
        
        return False
    
    def _limit_learned_facts(self):
        """Begrenzt die Anzahl der gelernten Fakten im RAM (LRU-artig)"""
        if len(self.learned_facts) > Config.MAX_LEARNED_FACTS_PER_AGENT:
            removed = self.learned_facts[:len(self.learned_facts) - Config.MAX_LEARNED_FACTS_PER_AGENT]
            self.learned_facts = self.learned_facts[-Config.MAX_LEARNED_FACTS_PER_AGENT:]
            for fact in removed:
                fact_hash = hashlib.md5(fact['fact'].encode()).hexdigest()
                self.learned_hashes.discard(fact_hash)
    
    # ==================== SKILL-ENTWICKLUNG ====================
    
    def _gain_experience(self, points: int, reason: str):
        """Fügt Erfahrungspunkte hinzu und aktualisiert Rang"""
        if not self.db:
            return
        
        self.experience_points += points
        self.db.add_experience(self.agent_id, points, reason)
        
        # Prüfe auf Rang-Aufstieg
        old_rank = self.rank
        for rank, threshold in self.RANK_THRESHOLDS.items():
            if self.experience_points >= threshold:
                self.rank = rank
        
        if old_rank != self.rank:
            print(f"🏆 {self.name} wurde zu {self.rank} befördert! ({self.experience_points} XP)")
    
    def _update_skill(self, skill: str, increment: float):
        """Erhöht einen Skill"""
        if not self.db:
            return
        self.db.update_agent_skill(self.agent_id, skill, increment)
        if skill in self.skills:
            self.skills[skill] = min(1.0, self.skills[skill] + increment)
    
    def _update_skills_for_learning(self, score: int):
        """Aktualisiert Skills basierend auf Lern-Erfolg - SKALIERT NACH SCORE"""
        skill_gain = (score / 100.0) * self.SKILL_GAIN_FACTOR
        
        self._update_skill("fachwissen", skill_gain)
        self._update_skill("analyse", skill_gain * 0.5)
        
        print(f"📈 {self.name}: Fachwissen +{skill_gain:.2f}, Analyse +{skill_gain*0.5:.2f}")
    
    def _update_skills_for_contribution(self, is_reaction: bool = False):
        """Aktualisiert Skills basierend auf Beitrag"""
        self._update_skill("kommunikation", self.SKILL_GAIN_FACTOR * 0.3)
        
        if is_reaction:
            self._update_skill("diplomatie", self.SKILL_GAIN_FACTOR * 0.4)
        
        if random.random() < 0.1:
            self._update_skill("kreativitaet", self.SKILL_GAIN_FACTOR * 0.5)
            print(f"🎨 {self.name}: Kreativität gestiegen!")
    
    # ==================== PERSÖNLICHKEITS-STEUERUNG ====================
    
    def _get_argumentation_style(self) -> str:
        """
        Generiert eine Persönlichkeits-Beschreibung für den Prompt.
        Berücksichtigt Charakter-Typ, Ziele, Ängste und Skills.
        """
        charakter_stile = {
            "Optimist": "Siehst immer das Positive, suchst nach Chancen, glaubst an Lösungen.",
            "Pessimist": "Siehst eher Risiken, bist vorsichtig, warnst vor Problemen.",
            "Realist": "Bleibst sachlich, analysierst nüchtern, argumentierst faktenbasiert.",
            "Idealist": "Hast hohe Prinzipien, kämpfst für das Gute, manchmal naiv.",
            "Pragmatiker": "Suchst praktische Lösungen, Kompromisse sind okay.",
            "Träumer": "Hast visionäre Ideen, denkst groß, manchmal realitätsfern.",
            "Macher": "Willst sofort handeln, ergebnisorientiert, ungeduldig.",
            "Denker": "Analysierst gründlich, brauchst Zeit, detailversessen.",
            "Chaot": "Bist spontan, unstrukturiert, kreativ, manchmal unberechenbar.",
            "Pedant": "Bist ordnungsliebend, genau, korrekt, manchmal kleinlich.",
            "Nerd": "Bist detailversessen, technisch, etwas sozial unbeholfen.",
            "Hipster": "Bist alternativ, kritisch gegenüber Mainstream, stylebewusst.",
            "Zyniker": "Bist sarkastisch, distanziert, hinterfragst alles.",
            "Idiot": "Bist unbedarft, naiv, manchmal dumm, aber ehrlich.",
            "Querulant": "Bist widerspenstig, stellst alles in Frage, provozierst.",
            "Klugscheißer": "Weißt alles besser, korrigierst andere, nervt manchmal.",
            "Streber": "Willst immer gut dastehen, fleißig, angepasst.",
            "Introvertiert": "Bist zurückhaltend, denkst erst, dann sprichst du.",
            "Extrovertiert": "Bist gesprächig, offen, impulsiv.",
            "Empathisch": "Fühlst mit anderen, bist mitfühlend, harmoniebedürftig.",
            "Rational": "Bist logisch, emotionslos, faktenorientiert.",
            "Karrierist": "Denkst an deine Karriere, strategisch, zielorientiert.",
            "Familiemensch": "Stellst Familie über alles, fürsorglich, konservativ.",
            "Workaholic": "Bist arbeitssüchtig, perfektionistisch, getrieben.",
            "Kümmerer": "Kümmerst dich um andere, fürsorglich, aufopfernd."
        }
        
        base_style = charakter_stile.get(self.charakter_typ, "Bist sachlich und ausgewogen.")
        
        goals_text = ""
        if self.goals:
            goals_text = f"\nDeine Ziele: {', '.join(self.goals[:2])}. Diese Ziele prägen deine Argumentation."
        
        fears_text = ""
        if self.fears:
            fears_text = f"\nDeine Ängste: {', '.join(self.fears[:2])}. Diese Ängste machen dich in bestimmten Punkten besonders vorsichtig."
        
        strong_skills = [f"{k} ({v:.1f})" for k, v in self.skills.items() if v > 0.6]
        skills_text = f"\nDeine Stärken: {', '.join(strong_skills)}" if strong_skills else ""
        
        return f"{base_style}{goals_text}{fears_text}{skills_text}"
    
    def _get_response_guidelines(self) -> str:
        """Gibt Antwort-Richtlinien basierend auf Persönlichkeit und Skills"""
        guidelines = {
            "Optimist": "Beton Chancen, bleib zuversichtlich.",
            "Pessimist": "Weise auf Risiken hin, bleib realistisch.",
            "Realist": "Argumentiere sachlich und ausgewogen.",
            "Idealist": "Verteidige Prinzipien, auch wenn sie unbequem sind.",
            "Pragmatiker": "Schlage praktische Kompromisse vor.",
            "Träumer": "Denk in großen Visionen, sei kreativ.",
            "Macher": "Sei direkt, fordere Handlungen.",
            "Denker": "Analysiere gründlich, zeige Zusammenhänge.",
            "Chaot": "Sei spontan, denk um die Ecke.",
            "Pedant": "Sei genau, korrigiere Details.",
            "Nerd": "Geh in die Tiefe, zeige Fachwissen.",
            "Hipster": "Sei alternativ, kritisiere Mainstream.",
            "Zyniker": "Sei sarkastisch, aber mit Substanz.",
            "Idiot": "Sei ehrlich, auch wenn es dumm klingt.",
            "Querulant": "Stell alles in Frage, provoziere.",
            "Klugscheißer": "Zeig dein Wissen, korrigiere.",
            "Streber": "Sei fleißig, zeig Einsatz.",
            "Introvertiert": "Bleib kurz, präzise, überlege gut.",
            "Extrovertiert": "Sei offen, gesprächig, direkt.",
            "Empathisch": "Zeig Verständnis, sei einfühlsam.",
            "Rational": "Bleib logisch, emotionslos.",
            "Karrierist": "Zeig strategisches Denken.",
            "Familiemensch": "Stell familiäre Werte in den Vordergrund.",
            "Workaholic": "Sei zielstrebig, effizient.",
            "Kümmerer": "Kümmer dich um andere, sei fürsorglich."
        }
        
        base = guidelines.get(self.charakter_typ, "Argumentiere sachlich und ausgewiesen.")
        
        if self.skills.get("fachwissen", 0) > 0.8:
            base += " Nutze dein fundiertes Fachwissen, um Argumente zu untermauern."
        if self.skills.get("diplomatie", 0) > 0.8:
            base += " Bleib besonders diplomatisch und vermittelnd."
        if self.skills.get("kreativitaet", 0) > 0.8:
            base += " Bring kreative, unkonventionelle Ideen ein."
        
        return base
    
    # ==================== ANTWORTEN ====================
    
    def answer(self, topic: str, document: Optional[str], 
               lm, stop_event=None, round_num: int = 0,
               progress=None) -> str:
        """Generiert eine Antwort zum Thema"""
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        external_info = ""
        if self.external_source and self.external_source.use_external:
            if self.external_source.should_search(topic):
                results = self.external_source.search(topic, 2, progress)
                if results:
                    external_info = self.external_source.format_results(results)
        
        context = ""
        if self.discussion_log and len(self.discussion_log) > 3:
            context = "\n".join(self.discussion_log[-3:])
        
        personality_style = self._get_argumentation_style()
        response_guideline = self._get_response_guidelines()
        
        ziele = ", ".join(self.goals[:2]) if self.goals else "keine spezifischen"
        aengste = ", ".join(self.fears[:2]) if self.fears else "keine spezifischen"
        rank_text = f" (Rang: {self.rank}, {self.experience_points} XP)"
        
        prompt = f"""Du bist {self.name}, {self.role}{rank_text}.

PERSÖNLICHKEIT:
{personality_style}

CHARAKTER-TYP: {self.charakter_typ}
ZIELE: {ziele}
ÄNGSTE: {aengste}

ANWEISUNG: {response_guideline}

Thema: {topic}
"""
        if document:
            prompt += f"\nDOKUMENT:\n{document[:500]}...\n"
        
        if context:
            prompt += f"\nLETZTE BEITRÄGE:\n{context}\n"
        
        if external_info:
            prompt += f"\nRECHERCHE:\n{external_info}\n"
        
        prompt += f"""
Runde {round_num + 1} der Diskussion.

Formuliere EINEN prägnanten Beitrag (max 3 Sätze). 
Passe deinen Stil an deine Persönlichkeit an.
KEINE Einleitungen wie "Als {self.role}..." - sag einfach deine Meinung.
"""
        
        response = lm.ask(prompt, f"Du bist {self.name} ({self.charakter_typ}).", stop_event)
        
        if response and response != "[ABGEBROCHEN]":
            self.last_response = response
            self.schon_gesagtes.append(response)
            self.current_position = response
            
            self._gain_experience(Config.XP_PER_CONTRIBUTION, "Beitrag in Diskussion")
            self._update_skills_for_contribution(is_reaction=False)
            
            if self.knowledge_graph:
                self.knowledge_graph.add_node(
                    self.agent_id,
                    "agent",
                    {
                        "name": self.name,
                        "role": self.role,
                        "charakter": self.charakter_typ,
                        "rank": self.rank,
                        "skills": self.skills,
                        "last_statement": response[:100],
                        "timestamp": datetime.now().isoformat()
                    }
                )
        
        return response
    
    def react_to(self, other_name: str, other_statement: str, 
                 topic: str, lm, stop_event=None) -> str:
        """Reagiert auf einen anderen Agenten"""
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        personality_style = self._get_argumentation_style()
        response_guideline = self._get_response_guidelines()
        
        prompt = f"""Du bist {self.name}, {self.role} ({self.rank}).

PERSÖNLICHKEIT:
{personality_style}

CHARAKTER-TYP: {self.charakter_typ}

ANWEISUNG: {response_guideline}

{other_name} hat gerade gesagt:
"{other_statement}"

Reagiere kurz darauf (max 2 Sätze). Stimme zu, widerspreche oder ergänze.
Passe deinen Stil an deine Persönlichkeit an.
KEINE Einleitungen.
"""
        
        response = lm.ask(prompt, f"Du bist {self.name} ({self.charakter_typ}).", stop_event)
        
        if response and response != "[ABGEBROCHEN]":
            self.last_response = response
            self.schon_gesagtes.append(response)
            
            self._gain_experience(Config.XP_PER_REACTION, "Reaktion auf anderen Agenten")
            self._update_skills_for_contribution(is_reaction=True)
            
            if self.knowledge_graph:
                self.knowledge_graph.add_influence(
                    other_name,
                    self.name,
                    topic,
                    0.5
                )
        
        return response
    
    # ==================== ANALYSE ====================
    
    def analyze(self, text: str, task_type: str, lm) -> Dict:
        """Führt eine Analyse des Texts durch"""
        
        personality_style = self._get_argumentation_style()
        response_guideline = self._get_response_guidelines()
        
        prompts = {
            "analyse": f"""Du bist {self.name}, {self.role} ({self.rank}).

PERSÖNLICHKEIT:
{personality_style}

CHARAKTER-TYP: {self.charakter_typ}

ANWEISUNG: {response_guideline}

Analysiere folgenden Text aus deiner fachlichen Perspektive:

{text}

Was sind die 2-3 wichtigsten Punkte, die dir als {self.role} auffallen?
Schreibe eine kurze Analyse (3-4 Sätze). Keine Einleitung, keine Vorstellung.""",

            "evaluate": f"""Du bist {self.name}, {self.role} ({self.rank}).

PERSÖNLICHKEIT:
{personality_style}

CHARAKTER-TYP: {self.charakter_typ}

ANWEISUNG: {response_guideline}

Bewerte folgende Situation aus deiner fachlichen Perspektive:

{text}

Gib eine Bewertung von 1-10 mit kurzer Begründung (3-4 Sätze). Keine Einleitung.""",

            "recommend": f"""Du bist {self.name}, {self.role} ({self.rank}).

PERSÖNLICHKEIT:
{personality_style}

CHARAKTER-TYP: {self.charakter_typ}

ANWEISUNG: {response_guideline}

Gib 3 konkrete Empfehlungen basierend auf diesem Text:

{text}

1. 
2. 
3. 

Begründe jede Empfehlung kurz.""",

            "summarize": f"""Du bist {self.name}, {self.role} ({self.rank}).

PERSÖNLICHKEIT:
{personality_style}

CHARAKTER-TYP: {self.charakter_typ}

ANWEISUNG: {response_guideline}

Fasse folgenden Text aus deiner Perspektive zusammen:

{text}

Maximal 3 Sätze. Keine Einleitung.""",

            "extract": f"""Du bist {self.name}, {self.role} ({self.rank}).

PERSÖNLICHKEIT:
{personality_style}

CHARAKTER-TYP: {self.charakter_typ}

ANWEISUNG: {response_guideline}

Extrahiere aus diesem Text:

{text}

- Fakten (was steht fest?)
- Probleme (was sind die Herausforderungen?)
- Chancen (was könnte verbessert werden?)

Keine Einleitung."""
        }
        
        prompt = prompts.get(task_type, prompts["analyse"])
        system = f"Du bist {self.name} ({self.charakter_typ}). Antworte präzise und fachlich."
        response = lm.ask(prompt, system)
        
        self._gain_experience(Config.XP_PER_ANALYSIS, f"Analyse durchgeführt ({task_type})")
        self.total_analyses += 1
        
        result = {
            "agent": self.name,
            "role": self.role,
            "charakter": self.charakter_typ,
            "rank": self.rank,
            "skills": self.skills,
            "task": task_type,
            "analysis": response,
            "timestamp": datetime.now().isoformat()
        }
        
        if task_type == "evaluate":
            score_match = re.search(r'(\d+)[^\d]*10', response)
            if score_match:
                result["score"] = float(score_match.group(1))
            else:
                result["score"] = None
        
        return result
    
    # ==================== LERNEN ====================
    
    def learn_from(self, other_name: str, other_statement: str, 
                   topic: str, lm, other_role: str = "") -> bool:
        """
        Lernt aus der Aussage eines anderen Agenten.
        """
        
        # ===== GLOBALER DUPLIKAT-CHECK MIT LOCK =====
        if self._global_duplicate_check(other_statement, topic):
            return False
        
        # ===== LOKALER DUPLIKAT-CHECK =====
        current_time = time.time()
        for fact in self.learned_facts[-10:]:
            if fact.get('timestamp') and (current_time - fact['timestamp']) < Config.TIME_WINDOW_DUPLICATE:
                similarity = self._text_similarity(other_statement, fact['fact'])
                if similarity > Config.LOCAL_DUPLICATE_THRESHOLD:
                    print(f"⏭️ {self.name}: Duplikat in den letzten {Config.TIME_WINDOW_DUPLICATE}s erkannt")
                    return False
        
        statement_hash = hashlib.md5(other_statement.encode()).hexdigest()
        if statement_hash in self.learned_hashes:
            print(f"⏭️ {self.name}: Duplikat per Hash erkannt")
            return False
        
        for fact in self.learned_facts:
            similarity = self._text_similarity(other_statement, fact['fact'])
            if similarity > Config.LOCAL_DUPLICATE_THRESHOLD:
                print(f"⏭️ {self.name}: Duplikat im RAM erkannt (Ähnlichkeit: {similarity:.2f})")
                return False
        
        if self.db:
            existing_memories = self.db.get_agent_memories(self.agent_id, limit=100)
            for mem in existing_memories:
                existing_fact = mem.get('fact', '')
                similarity = self._text_similarity(other_statement, existing_fact)
                if similarity > Config.LOCAL_DUPLICATE_THRESHOLD:
                    print(f"⏭️ {self.name}: Duplikat in eigener DB erkannt (Ähnlichkeit: {similarity:.2f})")
                    return False
        
        # ===== LERNEN =====
        recent_facts = ""
        if self.learned_facts:
            facts_list = []
            for f in self.learned_facts[-5:]:
                facts_list.append(f"- {f['fact'][:100]}... (von {f['source']})")
            recent_facts = "\n".join(facts_list)
        else:
            recent_facts = "Du hast noch keine Kenntnisse zu diesem Thema."
        
        prompt = f"""Du bist {self.name}, {self.role} ({self.charakter_typ}, {self.rank}).

DISKUSSIONSTHEMA: {topic}

DEINE BISHERIGEN KENNTNISSE:
{recent_facts}

{other_name} (Rolle: {other_role}) hat gerade gesagt:
"{other_statement}"

Auf einer Skala von 0 bis 100:
- 0 = völlig irrelevant oder bereits bekannt
- 50 = teilweise neu, könnte nützlich sein
- 100 = absolut neue, wichtige Information

Gib NUR eine Zahl zwischen 0 und 100."""
        
        try:
            response = lm.ask(prompt, f"Du bist {self.name}.", max_tokens=10)
            score_match = re.search(r'(\d+)', response)
            if score_match:
                base_score = int(score_match.group(1))
                base_score = max(0, min(100, base_score))
            else:
                base_score = 50
        except:
            base_score = 50
        
        skill_bonus = (self.skills.get("analyse", 0.5) - 0.5) * 40
        base_score = min(100, base_score + int(skill_bonus))
        
        importance = base_score / 100.0
        
        expert_keywords = ["professor", "doktor", "experte", "forscher", "richter", "anwalt", "ärzt", "pflege"]
        if any(kw in other_role.lower() for kw in expert_keywords):
            importance += 0.1
            print(f"📚 {self.name}: Experten-Bonus (+0.1)")
        
        if self.last_response and ("widersprech" in self.last_response.lower() or 
                                    "stimme nicht" in self.last_response.lower() or
                                    "sehe ich anders" in self.last_response.lower()):
            importance += 0.15
            print(f"⚡ {self.name}: Widerspruchs-Bonus (+0.15)")
        
        if "?" in other_statement:
            importance += 0.05
        
        if len(self.learned_facts) < 5:
            importance += 0.1
            print(f"🌱 {self.name}: Anfangs-Bonus (+0.1)")
        
        importance = min(1.0, importance)
        
        print(f"🤔 {self.name} ({self.charakter_typ}) bewertet Aussage: Score={base_score}, Importance={importance:.2f}")
        
        if base_score >= 60:
            fact_entry = {
                "fact": other_statement,
                "source": other_name,
                "topic": topic,
                "importance": importance,
                "score": base_score,
                "learned_at": datetime.now().isoformat(),
                "timestamp": time.time()
            }
            self.learned_facts.append(fact_entry)
            
            statement_hash = hashlib.md5(other_statement.encode()).hexdigest()
            self.learned_hashes.add(statement_hash)
            
            self._limit_learned_facts()
            
            self._gain_experience(Config.XP_PER_LEARNED_FACT, f"Neue Information gelernt (Score: {base_score})")
            self.total_learned_facts += 1
            
            self._update_skills_for_learning(base_score)
            
            if self.db:
                self.db.update_expertise(self.agent_id, topic, 0.05)
            
            with Agent._global_lock:
                if self.db:
                    try:
                        room = self.db.get_memory_room(self.agent_id)
                        if not room:
                            room_id = f"room_{self.agent_id}"
                            self.db.create_memory_room(
                                room_id, 
                                self.agent_id, 
                                f"{self.name}s Gedächtnis",
                                size=1.0,
                                color=self.color
                            )
                            room = self.db.get_memory_room(self.agent_id)
                        
                        if room:
                            crystal_id = f"crystal_{uuid.uuid4().hex}"
                            self.db.add_memory_crystal(
                                crystal_id,
                                room['room_id'],
                                other_statement[:500],
                                topic,
                                importance=importance,
                                position=(random.uniform(-100, 100), random.uniform(-100, 100), 0),
                                metadata={
                                    "source": other_name,
                                    "score": base_score,
                                    "source_role": other_role,
                                    "charakter": self.charakter_typ,
                                    "rank": self.rank,
                                    "skills": self.skills
                                }
                            )
                            print(f"💾 {self.name} ({self.charakter_typ}, {self.rank}) speichert Erinnerung (Score: {base_score})")
                            
                            if self.sim and hasattr(self.sim, 'trigger_callback'):
                                self.sim.trigger_callback("memory_updated", self.name)
                    except Exception as e:
                        print(f"⚠️ Fehler beim Speichern: {e}")
            
            if self.knowledge_graph:
                self.knowledge_graph.add_memory_crystal(
                    self.agent_id,
                    other_statement,
                    topic,
                    importance
                )
            
            return True
        
        print(f"⏭️ {self.name} ignoriert (Score {base_score} < 60)")
        return False
    
    # ==================== PROGNOSEN ====================
    
    def make_prognosis(self, topic: str, lm):
        """Erstellt eine Prognose"""
        personality_style = self._get_argumentation_style()
        
        prompt = f"""Du bist {self.name}, {self.role} ({self.charakter_typ}, {self.rank}).

PERSÖNLICHKEIT:
{personality_style}

Prognose zu: {topic}
2-3 Sätze, passend zu deiner Persönlichkeit."""
        
        prediction = lm.ask(prompt, f"Du bist {self.name}.")
        
        self._gain_experience(Config.XP_PER_PROGNOSIS, "Prognose erstellt")
        
        if self.db:
            self.db.add_prognosis(self.agent_id, topic, prediction, 0.5)
        return prediction
    
    # ==================== PERSÖNLICHKEIT ====================
    
    def _get_personality_text(self) -> str:
        """Generiert lesbaren Persönlichkeitstext."""
        traits = []
        if self.personality_traits["extraversion"] > 0.7:
            traits.append("gesprächig")
        if self.personality_traits["offenheit"] > 0.7:
            traits.append("neugierig")
        if self.personality_traits["gewissenhaftigkeit"] > 0.7:
            traits.append("gründlich")
        
        if traits:
            return f"{', '.join(traits)}. {self.personality}"
        return self.personality
    
    # ==================== HILFSFUNKTIONEN ====================
    
    def to_dict(self) -> dict:
        """Konvertiert Agenten zu Dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "personality": self.personality,
            "color": self.color,
            "goals": self.goals,
            "fears": self.fears,
            "education": self.education,
            "background": self.background,
            "team": self.team,
            "team_role": self.team_role,
            "charakter_typ": self.charakter_typ,
            "training_level": self.training_level,
            "skills": self.skills,
            "rank": self.rank,
            "experience_points": self.experience_points,
            "learned_facts_count": len(self.learned_facts)
        }
    
    def __repr__(self) -> str:
        return f"Agent({self.name}, {self.role}, {self.charakter_typ}, {self.rank})"