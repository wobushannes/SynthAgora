#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Factory für SynthAgora
- VOLLSTÄNDIGE LLM-GENERIERUNG FÜR THEMA/TEXT
- LLM-GENERIERUNG NACH ROLLE UND CHARAKTER
- TEMPLATE-GENERIERUNG FÜR RANDOM/CHARAKTER/VERTEILUNG
- REALISTISCHE SKILL-INITIALISIERUNG (MAX 0.6)
- RANG-SYSTEM (Junior, Senior, Experte, Master)
- DETAILLIERTE POOL-STATISTIKEN
- FIX: ROLLEN AUS AUSGELAGERTEM MODUL
"""

import json
import os
import re
import hashlib
import random
import time
from datetime import datetime
from typing import List, Dict, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import Config
from .database import SynthAgoraDB
from .role_pools import ALL_ROLLEN, ROLE_CATEGORIES, get_random_role, get_roles_by_category


class AgentFactory:
    """Fabrik zur Massenproduktion von Agenten"""
    
    def __init__(self, lm_client):
        self.lm = lm_client
        self.db = SynthAgoraDB()
        self.progress_callback: Optional[Callable] = None
        
        # Namenspools (erweitert)
        self.vornamen_maennlich = [
            "Alexander", "Benjamin", "Christian", "Daniel", "Erik", "Felix", "Georg", 
            "Hannes", "Igor", "Johannes", "Karl", "Lukas", "Martin", "Niklas", 
            "Oliver", "Paul", "Quentin", "Raphael", "Stefan", "Thomas", "Ulrich",
            "Valentin", "Walter", "Xaver", "Yannick", "Zacharias", "Adrian", "Bastian",
            "Clemens", "Dominik", "Elias", "Fabian", "Gregor", "Henrik", "Ingo",
            "Jens", "Konstantin", "Leonard", "Moritz", "Nils", "Oskar", "Philipp",
            "Rene", "Sebastian", "Tobias", "Uwe", "Viktor", "Werner", "Xander", "Yves"
        ]
        
        self.vornamen_weiblich = [
            "Anna", "Bianca", "Clara", "Daniela", "Elena", "Franziska", "Greta",
            "Hannah", "Isabell", "Julia", "Katharina", "Laura", "Marie", "Nadine",
            "Olivia", "Paula", "Quiana", "Renate", "Sophie", "Tanja", "Ursula",
            "Verena", "Wanda", "Xenia", "Yara", "Zoe", "Amelie", "Brigitte",
            "Charlotte", "Diana", "Emilia", "Frieda", "Helena", "Ines", "Jasmin",
            "Kim", "Lena", "Mia", "Nora", "Patricia", "Rosa", "Sarah", "Theresa",
            "Ulrike", "Vanessa", "Wilma", "Xanthia", "Yvonne", "Zara"
        ]
        
        self.nachnamen = [
            "Auer", "Bauer", "Chen", "Deutsch", "Egger", "Fischer", "Graf", "Huber",
            "Ivanov", "Jung", "Klein", "Lange", "Meyer", "Neumann", "Ortiz", "Peters",
            "Quinn", "Richter", "Schmidt", "Tanner", "Urban", "Vogel", "Wagner",
            "Xavier", "Yang", "Ziegler", "Weber", "Müller", "Schneider", "König",
            "Hoffmann", "Schulz", "Koch", "Bauer", "Lehmann", "Hartmann", "Krause",
            "Werner", "Schmitt", "Meier", "Schulze", "Herrmann", "Krüger", "Walter",
            "Vogt", "Zimmermann", "Kaiser", "Fuchs", "Lang", "Beck", "Schwarz"
        ]
        
        # Charakter-Typen (erweitert)
        self.charakter_typen = [
            "Optimist", "Pessimist", "Realist", "Idealist", "Pragmatiker",
            "Träumer", "Macher", "Denker", "Chaot", "Pedant", "Nerd", "Hipster",
            "Zyniker", "Idiot", "Querulant", "Klugscheißer", "Streber",
            "Introvertiert", "Extrovertiert", "Empathisch", "Rational",
            "Karrierist", "Familiemensch", "Workaholic", "Kümmerer",
            "Abenteurer", "Analytiker", "Artist", "Diplomat", "Erfinder",
            "Forscher", "Freigeist", "Gerechtigkeitsfanatiker", "Held", "Individualist",
            "Kämpfer", "Kreativer", "Kritiker", "Lebenskünstler", "Logiker",
            "Mentor", "Motivator", "Perfektionist", "Philosoph", "Rebell",
            "Romantiker", "Skeptiker", "Strategie", "Visionär", "Wissbegieriger"
        ]
        
        self.teams = [
            "medizin", "psychosozial", "paedagogik", "justiz", "verwaltung",
            "wirtschaft", "familie", "pflege", "forschung", "politik", "medien", 
            "handwerk", "technologie", "kunst", "sport", "landwirtschaft", "handel"
        ]
        
        # ROLLEN AUS AUSGELAGERTEM MODUL
        self.all_roles = ALL_ROLLEN
        self.role_categories = ROLE_CATEGORIES
    
    def set_progress_callback(self, callback: Callable):
        self.progress_callback = callback
    
    def _update_progress(self, message: str, current: int = None, total: int = None):
        if self.progress_callback:
            self.progress_callback(message, current, total)
    
    # ==================== REALISTISCHE SKILL-INITIALISIERUNG ====================
    
    def _initialize_skills_for_role(self, role: str, charakter: str) -> Dict:
        """Initialisiert Skills basierend auf Rolle und Charakter. MAX 0.6"""
        role_lower = role.lower()
        
        skills = {
            "fachwissen": 0.3,
            "kommunikation": 0.3,
            "analyse": 0.3,
            "kreativitaet": 0.3,
            "diplomatie": 0.3
        }
        
        # ==================== ROLLE-BASIERTE BONI (max +0.3) ====================
        role_bonus_applied = False
        
        # Medizinische Berufe
        if not role_bonus_applied and any(w in role_lower for w in ["arzt", "ärztin", "chirurg", "kardiologe", "neurologe", "psychiater"]):
            skills["fachwissen"] += 0.25
            skills["analyse"] += 0.2
            role_bonus_applied = True
        
        # Pflegeberufe
        if not role_bonus_applied and any(w in role_lower for w in ["krankenschwester", "pfleger", "pflegekraft", "altenpfleger", "hebamme"]):
            skills["fachwissen"] += 0.2
            skills["kommunikation"] += 0.15
            skills["diplomatie"] += 0.1
            role_bonus_applied = True
        
        # Juristische Berufe
        if not role_bonus_applied and any(w in role_lower for w in ["anwalt", "anwältin", "richter", "staatsanwalt", "rechtspfleger"]):
            skills["fachwissen"] += 0.25
            skills["analyse"] += 0.25
            role_bonus_applied = True
        
        # Pädagogische Berufe
        if not role_bonus_applied and any(w in role_lower for w in ["lehrer", "erzieher", "pädagoge", "schulleiter", "professor"]):
            skills["kommunikation"] += 0.25
            skills["diplomatie"] += 0.15
            role_bonus_applied = True
        
        # Psychologische/Soziale Berufe
        if not role_bonus_applied and any(w in role_lower for w in ["psychologe", "therapeut", "sozialarbeiter", "berater", "seelsorger"]):
            skills["diplomatie"] += 0.25
            skills["kommunikation"] += 0.15
            skills["analyse"] += 0.1
            role_bonus_applied = True
        
        # Wirtschaft/Management
        if not role_bonus_applied and any(w in role_lower for w in ["unternehmer", "manager", "geschäftsführer", "ceo", "berater"]):
            skills["kreativitaet"] += 0.2
            skills["analyse"] += 0.15
            skills["kommunikation"] += 0.1
            role_bonus_applied = True
        
        # Technologie/IT
        if not role_bonus_applied and any(w in role_lower for w in ["entwickler", "programmierer", "admin", "architekt", "data scientist"]):
            skills["fachwissen"] += 0.25
            skills["analyse"] += 0.25
            skills["kreativitaet"] += 0.1
            role_bonus_applied = True
        
        # Kunst/Kultur
        if not role_bonus_applied and any(w in role_lower for w in ["künstler", "musiker", "designer", "autor", "fotograf"]):
            skills["kreativitaet"] += 0.3
            skills["kommunikation"] += 0.15
            role_bonus_applied = True
        
        # Handwerk
        if not role_bonus_applied and any(w in role_lower for w in ["handwerker", "elektriker", "maurer", "schreiner", "metallbauer"]):
            skills["fachwissen"] += 0.2
            skills["kreativitaet"] += 0.15
            role_bonus_applied = True
        
        # Sport
        if not role_bonus_applied and any(w in role_lower for w in ["sportler", "trainer", "coach"]):
            skills["kommunikation"] += 0.2
            skills["diplomatie"] += 0.1
            role_bonus_applied = True
        
        # Forschung
        if not role_bonus_applied and any(w in role_lower for w in ["forscher", "wissenschaftler", "physiker", "chemiker", "biologe"]):
            skills["fachwissen"] += 0.3
            skills["analyse"] += 0.25
            role_bonus_applied = True
        
        # Politik
        if not role_bonus_applied and any(w in role_lower for w in ["politiker", "minister", "bürgermeister", "abgeordneter"]):
            skills["kommunikation"] += 0.25
            skills["diplomatie"] += 0.2
            role_bonus_applied = True
        
        # Medien
        if not role_bonus_applied and any(w in role_lower for w in ["journalist", "redakteur", "moderator", "influencer"]):
            skills["kommunikation"] += 0.25
            skills["kreativitaet"] += 0.15
            role_bonus_applied = True
        
        # Familien-Rollen (niedrigste Priorität)
        if not role_bonus_applied and any(w in role_lower for w in ["mutter", "vater", "eltern", "großmutter", "großvater"]):
            skills["diplomatie"] += 0.2
            skills["kommunikation"] += 0.15
            role_bonus_applied = True
        
        # ==================== CHARAKTER-BASIERTE BONI (max +0.1) ====================
        
        charakter_lower = charakter.lower()
        
        if any(w in charakter_lower for w in ["extrovertiert", "gesprächig", "macher", "streber", "motivator"]):
            skills["kommunikation"] += 0.1
        
        if any(w in charakter_lower for w in ["introvertiert", "denker", "nerd", "pedant", "analytiker", "logiker"]):
            skills["analyse"] += 0.1
        
        if any(w in charakter_lower for w in ["empathisch", "kümmerer", "familiemensch", "diplomat", "mediator"]):
            skills["diplomatie"] += 0.1
        
        if any(w in charakter_lower for w in ["träumer", "chaot", "hipster", "künstler", "erfinder", "visionär"]):
            skills["kreativitaet"] += 0.1
        
        if any(w in charakter_lower for w in ["nerd", "denker", "klugscheißer", "streber", "forscher", "wissenschaftler"]):
            skills["fachwissen"] += 0.1
        
        # ==================== BEGRENZUNG AUF MAX 0.6 ====================
        
        for skill in skills:
            skills[skill] = min(0.6, skills[skill])
            skills[skill] = round(skills[skill], 2)
        
        return skills
    
    def _get_initial_rank(self, skills: Dict) -> str:
        """Bestimmt initialen Rang basierend auf höchstem Skill"""
        max_skill = max(skills.values())
        
        if max_skill >= 0.55:
            return "Senior"
        else:
            return "Junior"
    
    # ==================== STATISTIK-METHODEN ====================
    
    def get_pool_statistics(self) -> Dict:
        return self.db.get_pool_stats_normalized()
    
    def get_agents_by_role(self, role: str, limit: int = 2000) -> List[Dict]:
        return self.db.search_pool(role, limit)
    
    def get_agents_by_charakter(self, charakter: str, limit: int = 2000) -> List[Dict]:
        return self.db.get_by_tags([charakter.lower()], False, limit)
    
    def get_agents_by_team(self, team: str, limit: int = 2000) -> List[Dict]:
        return self.db.get_by_tags([team], False, limit)
    
    # ==================== LLM-GENERIERUNG ====================
    
    def generate_from_theme(self, theme: str, count: int = 100) -> Dict:
        self._update_progress(f"🎯 Generiere {count} Agenten zum Thema mit LLM: {theme}")
        
        base_roles = self._generate_roles_with_llm(theme, min(15, count // 5))
        self._update_progress(f"📋 Generierte Rollen: {', '.join(base_roles[:5])}...")
        
        agents = self._generate_agents_with_llm(base_roles, count, theme)
        return self._save_agent_set(agents, f"theme_{self._slugify(theme)}_{count}", "llm")
    
    def generate_from_text(self, text: str, count: int = 100) -> Dict:
        self._update_progress(f"📄 Generiere {count} Agenten aus Text mit LLM...")
        
        base_roles = self._extract_roles_with_llm(text, min(15, count // 5))
        self._update_progress(f"📋 Gefundene Rollen: {', '.join(base_roles[:5])}...")
        
        agents = self._generate_agents_with_llm(base_roles, count, text[:500])
        return self._save_agent_set(agents, f"text_{int(time.time())}", "llm")
    
    def generate_by_role_with_llm(self, role: str, count: int = 50) -> Dict:
        self._update_progress(f"🤖 Generiere {count} Agenten mit Rolle '{role}' per LLM...")
        
        agents = []
        successful = 0
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(count):
                role_variation = role
                if i > 0 and random.random() > 0.6:
                    prefixe = ["Fach", "Ober", "Senior", "Junior", "Leitender", "Staatlich geprüfter", "Diplom-", "Promovierter"]
                    suffixe = [" (Spezialist)", " mit Schwerpunkt", " in der Notaufnahme", " mit Zusatzqualifikation", " für IT-Recht"]
                    if random.random() > 0.5:
                        role_variation = f"{random.choice(prefixe)} {role}"
                    else:
                        role_variation = f"{role}{random.choice(suffixe)}"
                
                future = executor.submit(self._generate_single_agent_with_llm, role_variation, f"Rolle: {role}", i)
                futures.append(future)
                time.sleep(0.2)
            
            for i, future in enumerate(as_completed(futures)):
                try:
                    agent = future.result(timeout=90)
                    if agent:
                        skills = self._initialize_skills_for_role(agent.get("role", role), agent.get("charakter_typ", "Realist"))
                        agent["skills"] = skills
                        agent["initial_rank"] = self._get_initial_rank(skills)
                        agents.append(agent)
                        successful += 1
                    self._update_progress(f"🤖 Generiere... ({successful}/{count})", successful, count)
                except Exception as e:
                    print(f"❌ LLM-Fehler: {e}")
            
            while len(agents) < count:
                role_variation = f"{random.choice(['Fach', 'Ober', 'Senior'])} {role}" if random.random() > 0.5 else role
                agent = self._generate_single_agent_with_llm(role_variation, f"Rolle: {role}", count + len(agents))
                if agent:
                    skills = self._initialize_skills_for_role(agent.get("role", role), agent.get("charakter_typ", "Realist"))
                    agent["skills"] = skills
                    agent["initial_rank"] = self._get_initial_rank(skills)
                    agents.append(agent)
                time.sleep(0.2)
        
        return self._save_agent_set(agents, f"role_llm_{self._slugify(role)}_{count}", "llm")
    
    def generate_by_charakter_with_llm(self, charakter: str, count: int = 50) -> Dict:
        self._update_progress(f"🎭 Generiere {count} Agenten mit Charakter '{charakter}' per LLM...")
        
        agents = []
        successful = 0
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(count):
                role = random.choice(self.all_roles)
                context = f"Charakter: {charakter}. Erstelle einen Agenten mit dieser Persönlichkeit."
                
                future = executor.submit(self._generate_single_agent_with_llm, role, context, i)
                futures.append(future)
                time.sleep(0.2)
            
            for i, future in enumerate(as_completed(futures)):
                try:
                    agent = future.result(timeout=90)
                    if agent:
                        agent["charakter_typ"] = charakter
                        skills = self._initialize_skills_for_role(agent.get("role", role), charakter)
                        agent["skills"] = skills
                        agent["initial_rank"] = self._get_initial_rank(skills)
                        agents.append(agent)
                        successful += 1
                    self._update_progress(f"🎭 Generiere... ({successful}/{count})", successful, count)
                except Exception as e:
                    print(f"❌ LLM-Fehler: {e}")
            
            while len(agents) < count:
                role = random.choice(self.all_roles)
                context = f"Charakter: {charakter}. Erstelle einen Agenten mit dieser Persönlichkeit."
                agent = self._generate_single_agent_with_llm(role, context, count + len(agents))
                if agent:
                    agent["charakter_typ"] = charakter
                    skills = self._initialize_skills_for_role(agent.get("role", role), charakter)
                    agent["skills"] = skills
                    agent["initial_rank"] = self._get_initial_rank(skills)
                    agents.append(agent)
                time.sleep(0.2)
        
        return self._save_agent_set(agents, f"charakter_llm_{self._slugify(charakter)}_{count}", "llm")
    
    def _generate_agents_with_llm(self, base_roles: List[str], count: int, context: str) -> List[Dict]:
        agents = []
        successful = 0
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(count):
                role = base_roles[i % len(base_roles)]
                future = executor.submit(self._generate_single_agent_with_llm, role, context, i)
                futures.append(future)
                time.sleep(0.2)
            
            for i, future in enumerate(as_completed(futures)):
                try:
                    agent = future.result(timeout=90)
                    if agent:
                        skills = self._initialize_skills_for_role(agent.get("role", role), agent.get("charakter_typ", "Realist"))
                        agent["skills"] = skills
                        agent["initial_rank"] = self._get_initial_rank(skills)
                        agents.append(agent)
                        successful += 1
                    self._update_progress(f"🤖 Generiere... ({successful}/{count})", successful, count)
                except Exception as e:
                    print(f"❌ LLM-Fehler: {e}")
            
            while len(agents) < count:
                role = random.choice(base_roles)
                agent = self._generate_single_agent_with_llm(role, context, count + len(agents))
                if agent:
                    skills = self._initialize_skills_for_role(agent.get("role", role), agent.get("charakter_typ", "Realist"))
                    agent["skills"] = skills
                    agent["initial_rank"] = self._get_initial_rank(skills)
                    agents.append(agent)
                time.sleep(0.2)
        
        return agents[:count]
    
    def _generate_single_agent_with_llm(self, role: str, context: str, idx: int) -> Optional[Dict]:
        geschlecht = random.choice(["männlich", "weiblich"])
        if geschlecht == "männlich":
            vorname = random.choice(self.vornamen_maennlich)
        else:
            vorname = random.choice(self.vornamen_weiblich)
        nachname = random.choice(self.nachnamen)
        name = f"{vorname} {nachname}"
        
        prompt = f"""Erstelle einen Agenten für eine Diskussion.

{context[:500]}

Rolle: {role}
Geschlecht: {geschlecht}

Generiere EIN JSON-Objekt mit folgenden Feldern:
- name: (Name, verwende "{name}" oder einen ähnlichen deutschen Namen)
- role: (die angegebene Rolle, erweitert um Details)
- personality: (kurze Persönlichkeitsbeschreibung, 5-10 Wörter)
- color: (HTML-Farbe als Hex, z.B. "#4a90e2")
- goals: (Liste mit 2 Zielen, passend zur Rolle)
- fears: (Liste mit 2 Ängsten, passend zur Rolle)
- education: (Bildungsabschluss, passend zur Rolle)
- background: (kurzer Hintergrund, 1 Satz, passend zur Rolle)
- team: (Team-Zugehörigkeit: medizin, psychosozial, paedagogik, justiz, verwaltung, wirtschaft, familie, pflege, forschung, politik, medien, handwerk, technologie, kunst, sport, landwirtschaft, handel)

NUR JSON, keine Erklärung, keine Einleitung."""
        
        try:
            response = self.lm.ask(prompt, f"Agent {role}", max_tokens=500)
            
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start == -1 or end == 0:
                return None
                
            json_str = response[start:end]
            json_str = json_str.replace('```json', '').replace('```', '').strip()
            
            try:
                agent = json.loads(json_str)
            except:
                json_str = json_str.replace("'", '"')
                try:
                    agent = json.loads(json_str)
                except:
                    return None
            
            required = ["name", "role", "personality", "color", "goals", "fears", "education", "background", "team"]
            if not all(k in agent for k in required):
                return None
            
            if isinstance(agent["goals"], str):
                agent["goals"] = [agent["goals"]]
            if isinstance(agent["fears"], str):
                agent["fears"] = [agent["fears"]]
            
            if "Charakter:" in context:
                char_match = re.search(r'Charakter:\s*([^\.]+)', context)
                if char_match:
                    agent["charakter_typ"] = char_match.group(1).strip()
                else:
                    agent["charakter_typ"] = random.choice(self.charakter_typen)
            else:
                agent["charakter_typ"] = random.choice(self.charakter_typen)
            
            return agent
                
        except Exception as e:
            print(f"❌ LLM-Agent-Fehler: {e}")
            return None
    
    def _extract_roles_with_llm(self, text: str, count: int) -> List[str]:
        prompt = f"""Extrahiere aus dem folgenden Text die wichtigsten BERUFSROLLEN oder SOZIALEN ROLLEN.

WICHTIG: Gib JEDE Rolle in EINER EIGENEN ZEILE an, ohne Nummerierung, ohne Erklärung.

Text:
{text[:1500]}

Rollen (eine pro Zeile):"""
        
        try:
            response = self.lm.ask(prompt, "Rollen-Extraktion", max_tokens=300)
            
            rollen = []
            for line in response.split('\n'):
                line = line.strip()
                line = re.sub(r'^[\d\.\-\s\*]+', '', line)
                if line and len(line) > 2 and len(line) < 50:
                    if not any([c in line for c in ['.', '!', '?', 'und', 'oder']]):
                        rollen.append(line)
            
            rollen = list(dict.fromkeys(rollen))
            
            while len(rollen) < count:
                rollen.append(random.choice(self.all_roles))
            
            return rollen[:count]
            
        except Exception as e:
            print(f"⚠️ LLM-Fehler: {e}")
            return [random.choice(self.all_roles) for _ in range(count)]
    
    def _generate_roles_with_llm(self, theme: str, count: int) -> List[str]:
        prompt = f"""Generiere {count} BERUFSROLLEN oder SOZIALE ROLLEN, die zum Thema "{theme}" passen.

WICHTIG: Gib JEDE Rolle in EINER EIGENEN ZEILE an, ohne Nummerierung, ohne Erklärung.

Beispiel für Thema "Krankenhaus":
Arzt
Krankenschwester
Patient
Pfleger
Radiologe
Apotheker

Thema: {theme}

Rollen (eine pro Zeile):"""
        
        try:
            response = self.lm.ask(prompt, "Rollen-Generierung", max_tokens=400)
            
            rollen = []
            for line in response.split('\n'):
                line = line.strip()
                line = re.sub(r'^[\d\.\-\s\*]+', '', line)
                if line and len(line) > 2 and len(line) < 50:
                    if not any([c in line for c in ['.', '!', '?', 'und', 'oder']]):
                        rollen.append(line)
            
            rollen = list(dict.fromkeys(rollen))
            
            while len(rollen) < count:
                rollen.append(random.choice(self.all_roles))
            
            return rollen[:count]
            
        except Exception as e:
            print(f"⚠️ LLM-Fehler: {e}")
            return [random.choice(self.all_roles) for _ in range(count)]
    
    # ==================== TEMPLATE-GENERIERUNG (schnell) ====================
    
    def generate_random(self, count: int = 100) -> Dict:
        self._update_progress(f"🎲 Generiere {count} zufällige Agenten...")
        
        agents = []
        for i in range(count):
            geschlecht = random.choice(["männlich", "weiblich"])
            if geschlecht == "männlich":
                vorname = random.choice(self.vornamen_maennlich)
            else:
                vorname = random.choice(self.vornamen_weiblich)
            nachname = random.choice(self.nachnamen)
            
            charakter = random.choice(self.charakter_typen)
            team = random.choice(self.teams)
            role = random.choice(self.all_roles)
            
            skills = self._initialize_skills_for_role(role, charakter)
            initial_rank = self._get_initial_rank(skills)
            
            # Ziel und Ängste rollenabhängig generieren
            goals = self._generate_goals_for_role(role)
            fears = self._generate_fears_for_role(role)
            education = self._generate_education_for_role(role)
            background = self._generate_background_for_role(role, charakter)
            
            agent = {
                "name": f"{vorname} {nachname}",
                "role": role,
                "personality": f"{charakter}, {random.choice(['einfühlsam', 'direkt', 'geduldig', 'sarkastisch', 'hilfsbereit', 'chaotisch', 'strukturiert', 'analytisch', 'kreativ', 'pragmatisch'])}",
                "color": f"#{random.randint(0, 0xFFFFFF):06x}",
                "goals": goals,
                "fears": fears,
                "education": education,
                "background": background,
                "team": team,
                "charakter_typ": charakter,
                "skills": skills,
                "initial_rank": initial_rank
            }
            agents.append(agent)
            
            if i % 10 == 0:
                self._update_progress(f"🎲 Generiere... ({i}/{count})", i, count)
        
        return self._save_agent_set(agents, f"random_{count}", "template")
    
    def _generate_goals_for_role(self, role: str) -> List[str]:
        role_lower = role.lower()
        
        if any(w in role_lower for w in ["arzt", "ärztin", "chirurg", "kardiologe"]):
            return ["Patienten bestmöglich versorgen", "Medizinischen Fortschritt vorantreiben"]
        elif any(w in role_lower for w in ["anwalt", "richter", "staatsanwalt"]):
            return ["Gerechtigkeit durchsetzen", "Mandanten erfolgreich vertreten"]
        elif any(w in role_lower for w in ["lehrer", "professor", "pädagoge"]):
            return ["Wissen vermitteln", "Schüler individuell fördern"]
        elif any(w in role_lower for w in ["entwickler", "programmierer"]):
            return ["Innovative Software entwickeln", "Probleme elegant lösen"]
        elif any(w in role_lower for w in ["künstler", "musiker", "designer"]):
            return ["Kreativität ausleben", "Menschen mit Kunst berühren"]
        elif any(w in role_lower for w in ["unternehmer", "manager", "ceo"]):
            return ["Unternehmen erfolgreich führen", "Innovationen vorantreiben"]
        else:
            return random.choice([
                ["Karriere machen", "Fachwissen vertiefen"],
                ["Team führen", "Projekte erfolgreich abschließen"],
                ["Gesellschaft positiv beeinflussen", "Menschen helfen"],
                ["Neues lernen", "Sich persönlich weiterentwickeln"],
                ["Work-Life-Balance finden", "Familie und Beruf vereinbaren"]
            ])
    
    def _generate_fears_for_role(self, role: str) -> List[str]:
        role_lower = role.lower()
        
        if any(w in role_lower for w in ["arzt", "ärztin", "chirurg"]):
            return ["Behandlungsfehler", "Patienten verlieren"]
        elif any(w in role_lower for w in ["anwalt", "richter"]):
            return ["Falsches Urteil", "Mandanten enttäuschen"]
        elif any(w in role_lower for w in ["lehrer", "professor"]):
            return ["Schüler nicht erreichen", "Bildungsauftrag nicht erfüllen"]
        elif any(w in role_lower for w in ["entwickler", "programmierer"]):
            return ["Sicherheitslücken übersehen", "Technologischer Rückstand"]
        elif any(w in role_lower for w in ["künstler", "musiker"]):
            return ["Kreativität verlieren", "Nicht ernst genommen werden"]
        else:
            return random.choice([
                ["Versagen", "Überforderung"],
                ["Kontrolle verlieren", "Stillstand"],
                ["Kritik nicht aushalten", "Fehler machen"],
                ["Bedeutungslosigkeit", "Isolation"]
            ])
    
    def _generate_education_for_role(self, role: str) -> str:
        role_lower = role.lower()
        
        if any(w in role_lower for w in ["arzt", "ärztin", "chirurg", "psychiater"]):
            return random.choice(["Medizinstudium mit Promotion", "Facharztausbildung", "Universitätsmedizin"])
        elif any(w in role_lower for w in ["anwalt", "richter", "staatsanwalt"]):
            return random.choice(["Jurastudium mit 1. und 2. Staatsexamen", "Rechtswissenschaften (Masters)", "Promotion im Rechtsbereich"])
        elif any(w in role_lower for w in ["lehrer", "professor", "pädagoge"]):
            return random.choice(["Lehramtsstudium", "Erziehungswissenschaften (Master)", "Promotion in Pädagogik"])
        elif any(w in role_lower for w in ["entwickler", "programmierer", "architekt"]):
            return random.choice(["Informatikstudium", "Fachinformatiker-Ausbildung", "Bootcamp + Berufserfahrung"])
        elif any(w in role_lower for w in ["künstler", "musiker", "designer"]):
            return random.choice(["Kunsthochschule", "Design-Studium", "Autodidakt mit Werkstatt"])
        elif any(w in role_lower for w in ["unternehmer", "manager", "ceo"]):
            return random.choice(["BWL-Studium (MBA)", "Wirtschaftsingenieurwesen", "Selbstständig gelernt"])
        else:
            return random.choice(["Studium", "Berufsausbildung", "Weiterbildung", "Autodidakt", "Fachhochschule"])
    
    def _generate_background_for_role(self, role: str, charakter: str) -> str:
        staedte = ["Berlin", "München", "Hamburg", "Köln", "Frankfurt", "Stuttgart", "Leipzig", "Dresden", "Hannover", "Nürnberg"]
        stadt = random.choice(staedte)
        jahre = random.randint(3, 25)
        
        return f"Aufgewachsen in {stadt}, {jahre} Jahre Berufserfahrung als {role}. {charakter}-Typ prägt die Arbeitsweise."
    
    def generate_by_role(self, role: str, count: int = 50, variations: bool = True) -> Dict:
        self._update_progress(f"👨‍⚕️ Generiere {count} Agenten mit Rolle '{role}' (Template)...")
        
        agents = []
        varianten = ["Facharzt", "Oberarzt", "Chefarzt", "Assistenzarzt", "Praktikant", "Senior", "Junior", "Leitender", "Staatlich geprüfter", "Promovierter", "Diplom-"]
        
        for i in range(count):
            geschlecht = random.choice(["männlich", "weiblich"])
            if geschlecht == "männlich":
                vorname = random.choice(self.vornamen_maennlich)
            else:
                vorname = random.choice(self.vornamen_weiblich)
            nachname = random.choice(self.nachnamen)
            charakter = random.choice(self.charakter_typen)
            
            if variations and i > 0 and random.random() > 0.5:
                prefix = random.choice(varianten)
                role_variation = f"{prefix} {role}"
            else:
                role_variation = role
            
            team = self._guess_team(role_variation)
            skills = self._initialize_skills_for_role(role_variation, charakter)
            initial_rank = self._get_initial_rank(skills)
            
            agent = {
                "name": f"{vorname} {nachname}",
                "role": role_variation,
                "personality": f"{charakter}, {random.choice(['einfühlsam', 'direkt', 'geduldig', 'sarkastisch', 'hilfsbereit'])}",
                "color": f"#{random.randint(0, 0xFFFFFF):06x}",
                "goals": self._generate_goals_for_role(role_variation),
                "fears": self._generate_fears_for_role(role_variation),
                "education": self._generate_education_for_role(role_variation),
                "background": self._generate_background_for_role(role_variation, charakter),
                "team": team,
                "charakter_typ": charakter,
                "skills": skills,
                "initial_rank": initial_rank
            }
            agents.append(agent)
            
            if i % 10 == 0:
                self._update_progress(f"👨‍⚕️ Generiere... ({i}/{count})", i, count)
        
        return self._save_agent_set(agents, f"role_{self._slugify(role)}_{count}", "template")
    
    def generate_by_charakter(self, charakter: str, count: int = 50) -> Dict:
        self._update_progress(f"🎭 Generiere {count} Agenten vom Typ '{charakter}' (Template)...")
        
        agents = []
        for i in range(count):
            geschlecht = random.choice(["männlich", "weiblich"])
            if geschlecht == "männlich":
                vorname = random.choice(self.vornamen_maennlich)
            else:
                vorname = random.choice(self.vornamen_weiblich)
            nachname = random.choice(self.nachnamen)
            role = random.choice(self.all_roles)
            team = self._guess_team(role)
            
            skills = self._initialize_skills_for_role(role, charakter)
            initial_rank = self._get_initial_rank(skills)
            
            agent = {
                "name": f"{vorname} {nachname}",
                "role": role,
                "personality": f"{charakter}, {random.choice(['einfühlsam', 'direkt', 'geduldig', 'sarkastisch', 'hilfsbereit'])}",
                "color": f"#{random.randint(0, 0xFFFFFF):06x}",
                "goals": self._generate_goals_for_role(role),
                "fears": self._generate_fears_for_role(role),
                "education": self._generate_education_for_role(role),
                "background": self._generate_background_for_role(role, charakter),
                "team": team,
                "charakter_typ": charakter,
                "skills": skills,
                "initial_rank": initial_rank
            }
            agents.append(agent)
            
            if i % 10 == 0:
                self._update_progress(f"🎭 Generiere... ({i}/{count})", i, count)
        
        return self._save_agent_set(agents, f"charakter_{charakter}_{count}", "template")
    
    def generate_by_role_distribution(self, distribution: Dict[str, int]) -> Dict:
        total = sum(distribution.values())
        self._update_progress(f"📊 Generiere {total} Agenten nach Verteilung...")
        
        agents = []
        current = 0
        
        for category, count in distribution.items():
            if category in self.role_categories:
                possible_roles = self.role_categories[category]
                for i in range(count):
                    geschlecht = random.choice(["männlich", "weiblich"])
                    if geschlecht == "männlich":
                        vorname = random.choice(self.vornamen_maennlich)
                    else:
                        vorname = random.choice(self.vornamen_weiblich)
                    nachname = random.choice(self.nachnamen)
                    charakter = random.choice(self.charakter_typen)
                    role = random.choice(possible_roles)
                    team = category
                    
                    skills = self._initialize_skills_for_role(role, charakter)
                    initial_rank = self._get_initial_rank(skills)
                    
                    agent = {
                        "name": f"{vorname} {nachname}",
                        "role": role,
                        "personality": f"{charakter}, {random.choice(['einfühlsam', 'direkt', 'geduldig', 'sarkastisch'])}",
                        "color": f"#{random.randint(0, 0xFFFFFF):06x}",
                        "goals": self._generate_goals_for_role(role),
                        "fears": self._generate_fears_for_role(role),
                        "education": self._generate_education_for_role(role),
                        "background": self._generate_background_for_role(role, charakter),
                        "team": team,
                        "charakter_typ": charakter,
                        "skills": skills,
                        "initial_rank": initial_rank
                    }
                    agents.append(agent)
                    current += 1
                    self._update_progress(f"📊 {category}: {i+1}/{count}", current, total)
        
        return self._save_agent_set(agents, f"distribution_{int(time.time())}", "template")
    
    def _guess_team(self, role: str) -> str:
        role_lower = role.lower()
        
        if any(w in role_lower for w in ["arzt", "kranken", "pfleger", "chirurg", "anästhesist", "kardiologe", "neurologe"]):
            return "medizin"
        if any(w in role_lower for w in ["psych", "sozial", "therapeut", "berater", "seelsorger"]):
            return "psychosozial"
        if any(w in role_lower for w in ["lehrer", "erzieher", "pädagog", "schule", "professor"]):
            return "paedagogik"
        if any(w in role_lower for w in ["anwalt", "richter", "recht", "staatsanwalt", "jurist"]):
            return "justiz"
        if any(w in role_lower for w in ["sachbearbeiter", "amtsleiter", "verwaltung", "beamter"]):
            return "verwaltung"
        if any(w in role_lower for w in ["unternehmer", "manager", "geschäftsführer", "ceo", "berater"]):
            return "wirtschaft"
        if any(w in role_lower for w in ["mutter", "vater", "groß"]):
            return "familie"
        if any(w in role_lower for w in ["altenpfleger", "hebamme", "pflege"]):
            return "pflege"
        if any(w in role_lower for w in ["wissenschaftler", "forscher", "physiker", "chemiker", "biologe"]):
            return "forschung"
        if any(w in role_lower for w in ["politiker", "bürgermeister", "abgeordneter", "minister"]):
            return "politik"
        if any(w in role_lower for w in ["journalist", "redakteur", "moderator", "influencer"]):
            return "medien"
        if any(w in role_lower for w in ["entwickler", "programmierer", "admin", "architekt"]):
            return "technologie"
        if any(w in role_lower for w in ["künstler", "musiker", "designer", "autor"]):
            return "kunst"
        if any(w in role_lower for w in ["sportler", "trainer", "coach"]):
            return "sport"
        if any(w in role_lower for w in ["landwirt", "gärtner", "förster", "winzer"]):
            return "landwirtschaft"
        if any(w in role_lower for w in ["verkäufer", "kaufmann", "handelsvertreter"]):
            return "handel"
        
        return random.choice(self.teams)
    
    # ==================== HILFSFUNKTIONEN ====================
    
    def _slugify(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^a-z0-9]', '_', text)
        text = re.sub(r'_+', '_', text)
        return text[:30]
    
    def _save_agent_set(self, agents: List[Dict], name: str, mode: str = "llm") -> Dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._slugify(name)
        filename = f"{Config.AGENTS_FOLDER}/{safe_name}_{timestamp}.json"
        
        set_id = hashlib.md5(f"{name}_{timestamp}".encode()).hexdigest()[:8]
        
        result = {
            "name": name,
            "description": f"{len(agents)} Agenten generiert am {timestamp}",
            "moderator_required": True,
            "default_moderator": "prof_neutral.json",
            "generation_mode": mode,
            "generation_date": datetime.now().isoformat(),
            "agents": []
        }
        
        for idx, agent in enumerate(agents):
            agent["agent_id"] = f"agent_{set_id}_{idx}"
            result["agents"].append(agent)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        self._add_to_pool(result, filename, mode)
        
        self._update_progress(f"✅ {len(agents)} Agenten gespeichert")
        return result
    
    def _add_to_pool(self, agent_set: Dict, filename: str, mode: str = "llm"):
        for idx, agent in enumerate(agent_set["agents"]):
            agent_id = agent.get("agent_id", f"agent_{idx}")
            
            tags = []
            if "role" in agent:
                primary_role = agent["role"].split()[0] if agent["role"] else ""
                tags.append(primary_role.lower())
            if "team" in agent:
                tags.append(agent["team"].lower())
            if "charakter_typ" in agent:
                tags.append(agent["charakter_typ"].lower())
            
            tags = [t for t in list(set(tags)) if t and len(t) > 1]
            
            metadata = {
                "education": agent.get("education", ""),
                "background": agent.get("background", ""),
                "goals": agent.get("goals", []),
                "fears": agent.get("fears", []),
                "team": agent.get("team", ""),
                "charakter_typ": agent.get("charakter_typ", ""),
                "skills": agent.get("skills", {}),
                "initial_rank": agent.get("initial_rank", "Junior"),
                "personality": agent.get("personality", "")
            }
            
            self.db.add_to_pool({
                "agent_id": agent_id,
                "set_name": agent_set["name"],
                "name": agent["name"],
                "role": agent["role"],
                "tags": json.dumps(tags[:5]),
                "json_file": filename,
                "generation_mode": mode,
                "generation_date": agent_set.get("generation_date", datetime.now().isoformat()),
                "metadata": json.dumps(metadata)
            })
    
    # ==================== POOL-METHODEN ====================
    
    def search_pool(self, query: str, limit: int = 100) -> List[Dict]:
        return self.db.search_pool(query, limit)
    
    def get_random_from_pool(self, count: int, filters: Dict = None) -> List[Dict]:
        return self.db.get_random_from_pool(count, filters)
    
    def get_by_tags(self, tags: List[str], match_all: bool = False, limit: int = 100) -> List[Dict]:
        return self.db.get_by_tags(tags, match_all, limit)
    
    def get_by_team(self, team: str, limit: int = 100) -> List[Dict]:
        return self.db.get_by_tags([team], False, limit)
    
    def get_by_charakter(self, charakter: str, limit: int = 100) -> List[Dict]:
        return self.db.get_by_tags([charakter.lower()], False, limit)
    
    def get_stats(self) -> Dict:
        return self.db.get_pool_stats()