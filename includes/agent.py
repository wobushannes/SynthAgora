#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent-Klasse für SynthAgora
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
    """Ein Agent mit Persönlichkeit, Gedächtnis und Lernfähigkeit."""
    
    _global_lock = threading.Lock()
    RANK_THRESHOLDS = Config.RANK_THRESHOLDS
    SKILL_GAIN_FACTOR = Config.SKILL_GAIN_FACTOR
    
    def __init__(self, data: dict, knowledge_graph=None, external_source=None):
        self.name = data["name"]
        self.role = data["role"]
        self.personality = data["personality"]
        self.color = data.get("color", "#cccccc")
        
        self.education = data.get("education", "")
        self.background = data.get("background", "")
        self.goals = data.get("goals", [])
        self.fears = data.get("fears", [])
        self.team = data.get("team", "")
        self.team_role = data.get("team_role", "Mitglied")
        self.charakter_typ = data.get("charakter_typ", "Realist")
        
        self.personality_traits = {
            "offenheit": data.get("offenheit", 0.5),
            "gewissenhaftigkeit": data.get("gewissenhaftigkeit", 0.5),
            "extraversion": data.get("extraversion", 0.5),
            "verträglichkeit": data.get("verträglichkeit", 0.5),
            "neurotizismus": data.get("neurotizismus", 0.5)
        }
        
        self.skills = {
            "fachwissen": 0.5,
            "kommunikation": 0.5,
            "analyse": 0.5,
            "kreativitaet": 0.5,
            "diplomatie": 0.5
        }
        
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
        
        self.training_level = 1.0
        self.learned_facts = []
        self.schon_gesagtes = []
        self.wiederholungen = 0
        self.ausgeschlossen = False
        
        self.current_projects = []
        self.retrieval_k = 5
        self.retrieval_enabled = True
        self.last_retrieved_context = ""
        
        self.citations_in_current_response = []
        self.external_citations_in_current_response = []
        self.missing_citations_this_round = 0
        self.total_citations_given = 0
        self.total_external_citations_given = 0
        self.total_citation_points = 0
        
        self.current_position = None
        self.last_response = ""
        self.influenced_by = []
        self.influenced_others = []
        
        self.knowledge_graph = knowledge_graph
        self.external_source = external_source
        self.db = None
        self.sim = None
        self.project_manager = None
        
        self.agent_id = data.get("agent_id", f"agent_{self.name.lower().replace(' ', '_')}")
        
        self.status_label = None
        self.response_label = None
        self.discussion_log = []
        self.learned_hashes = set()
    
    def set_db(self, db):
        self.db = db
        self._load_skills_from_db()
        self._load_evolution_from_db()
        self._load_existing_hashes()
    
    def set_simulation(self, sim):
        self.sim = sim
        if sim and hasattr(sim, 'project_manager'):
            self.project_manager = sim.project_manager
    
    def set_project_manager(self, pm):
        self.project_manager = pm
    
    def set_external_source(self, external_source):
        self.external_source = external_source
    
    def _load_skills_from_db(self):
        if not self.db:
            return
        try:
            skills = self.db.get_agent_skills(self.agent_id)
            if skills:
                self.skills = skills
        except Exception as e:
            pass
    
    def _load_evolution_from_db(self):
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
        except Exception as e:
            pass
    
    def _load_existing_hashes(self):
        if not self.db:
            return
        try:
            agent_exists = self.db.get_agent(self.agent_id)
            if not agent_exists:
                return
            memories = self.db.get_agent_memories(self.agent_id, limit=Config.MAX_MEMORY_RESULTS)
            for mem in memories:
                fact = mem.get('fact', '')
                fact_hash = hashlib.md5(fact.encode()).hexdigest()
                self.learned_hashes.add(fact_hash)
        except Exception as e:
            pass
    
    def _text_similarity(self, text1: str, text2: str) -> float:
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
        if not self.db:
            return False
        with Agent._global_lock:
            try:
                return self.db.is_duplicate_fact(fact, topic, Config.DUPLICATE_SIMILARITY_THRESHOLD)
            except Exception as e:
                return False
    
    def _is_duplicate(self, statement: str) -> bool:
        statement_hash = hashlib.md5(statement.encode()).hexdigest()
        if statement_hash in self.learned_hashes:
            return True
        for fact in self.learned_facts:
            similarity = self._text_similarity(statement, fact['fact'])
            if similarity > Config.LOCAL_DUPLICATE_THRESHOLD:
                return True
        if self.db:
            existing_memories = self.db.get_agent_memories(self.agent_id, limit=100)
            for mem in existing_memories:
                existing_fact = mem.get('fact', '')
                similarity = self._text_similarity(statement, existing_fact)
                if similarity > Config.LOCAL_DUPLICATE_THRESHOLD:
                    return True
        return False
    
    def _limit_learned_facts(self):
        if len(self.learned_facts) > Config.MAX_LEARNED_FACTS_PER_AGENT:
            removed = self.learned_facts[:len(self.learned_facts) - Config.MAX_LEARNED_FACTS_PER_AGENT]
            self.learned_facts = self.learned_facts[-Config.MAX_LEARNED_FACTS_PER_AGENT:]
            for fact in removed:
                fact_hash = hashlib.md5(fact['fact'].encode()).hexdigest()
                self.learned_hashes.discard(fact_hash)
    
    def get_document_context(self, topic: str, query: str = None) -> str:
        if not self.retrieval_enabled:
            return ""
        if not self.project_manager:
            return ""
        if not self.current_projects:
            return ""
        search_query = query or topic
        if self.last_response:
            search_query = f"{topic} {self.last_response[:200]}"
        try:
            context = self.project_manager.get_context(
                search_query, 
                self.current_projects, 
                self.retrieval_k
            )
            self.last_retrieved_context = context
            return context
        except Exception as e:
            return ""
    
    def _requires_citation(self) -> bool:
        return self.rank in Config.CITATION_REQUIRED_FOR_RANKS
    
    def _citation_bonus_applies(self) -> bool:
        return self.rank in Config.CITATION_BONUS_FOR_RANKS
    
    def _extract_citations(self, response: str) -> Tuple[List[Dict], List[Dict]]:
        doc_citations = []
        ext_citations = []
        pattern1 = r'\[([^:]+)::([^:]+)::([^\]]+)\]'
        for match in re.findall(pattern1, response):
            doc_citations.append({
                "type": "document",
                "project": match[0].strip(),
                "document": match[1].strip(),
                "chunk": match[2].strip(),
                "quoted_text": ""
            })
        pattern2 = r'\(([^,]+),\s*(?:S\.?\s*(\d+)|(?:Beschl\.|Urt\.|Urteil|Beschluss|BVerfG|BGH|VG)[^)]*)\)'
        for match in re.findall(pattern2, response):
            ext_citations.append({
                "type": "external",
                "source": match[0].strip(),
                "page": match[1] if len(match) > 1 and match[1] else None
            })
        pattern3 = r'"([^"]+)"\s*\(([^)]+)\)'
        for match in re.findall(pattern3, response):
            ext_citations.append({
                "type": "external",
                "source": match[1].strip(),
                "quoted_text": match[0].strip()
            })
        return doc_citations, ext_citations
    
    def _check_citation_compliance(self, response: str, has_document_context: bool) -> Tuple[bool, int, List[Dict], List[Dict]]:
        doc_citations, ext_citations = self._extract_citations(response)
        if not self._requires_citation():
            if doc_citations and self._citation_bonus_applies():
                bonus = len(doc_citations)
                self._add_score(bonus, f"Dokumenten-Zitat-Bonus ({len(doc_citations)} Zitate)")
                self.total_citations_given += len(doc_citations)
                self.total_citation_points += bonus
            return True, 0, doc_citations, ext_citations
        if has_document_context and not doc_citations:
            penalty = Config.CITATION_PENALTY
            self.missing_citations_this_round += 1
            self._add_score(-penalty, f"Fehlende Dokumenten-Zitate (Verstoß {self.missing_citations_this_round})")
            return False, penalty, doc_citations, ext_citations
        if doc_citations:
            points = len(doc_citations)
            self.total_citations_given += len(doc_citations)
            self.total_citation_points += points
            self._add_score(points, f"{len(doc_citations)} Dokumenten-Zitate geliefert")
        return True, 0, doc_citations, ext_citations
    
    def _save_citations_to_db(self, citations: List[Dict], citation_type: str):
        if not self.db or not self.sim:
            return
        for cit in citations:
            if citation_type == "document":
                self.db.add_citation(
                    self.agent_id,
                    self.sim.current_discussion_id if self.sim else None,
                    None,
                    cit.get("project", ""),
                    cit.get("document", ""),
                    cit.get("chunk", ""),
                    cit.get("quoted_text", ""),
                    0.9,
                    len(citations),
                    "document"
                )
            else:
                self.db.add_external_citation(
                    self.agent_id,
                    self.sim.current_discussion_id if self.sim else None,
                    cit.get("source", ""),
                    cit.get("quoted_text", ""),
                    cit.get("reference", "")
                )
    
    def _add_score(self, points: int, reason: str):
        if self.db and self.sim:
            self.db.add_score(self.agent_id, points, reason, "citation")
        self.total_score_points += points
    
    def _gain_experience(self, points: int, reason: str):
        if not self.db:
            return
        self.experience_points += points
        self.db.add_experience(self.agent_id, points, reason)
        old_rank = self.rank
        for rank, threshold in self.RANK_THRESHOLDS.items():
            if self.experience_points >= threshold:
                self.rank = rank
        if old_rank != self.rank:
            print(f"🏆 {self.name} wurde zu {self.rank} befördert!")
    
    def _update_skill(self, skill: str, increment: float):
        if not self.db:
            return
        self.db.update_agent_skill(self.agent_id, skill, increment)
        if skill in self.skills:
            self.skills[skill] = min(1.0, self.skills[skill] + increment)
    
    def _update_skills_for_learning(self, score: int):
        skill_gain = (score / 100.0) * self.SKILL_GAIN_FACTOR
        self._update_skill("fachwissen", skill_gain)
        self._update_skill("analyse", skill_gain * 0.5)
    
    def _update_skills_for_contribution(self, is_reaction: bool = False):
        self._update_skill("kommunikation", self.SKILL_GAIN_FACTOR * 0.3)
        if is_reaction:
            self._update_skill("diplomatie", self.SKILL_GAIN_FACTOR * 0.4)
        if random.random() < 0.1:
            self._update_skill("kreativitaet", self.SKILL_GAIN_FACTOR * 0.5)
    
    def answer(self, topic: str, document: Optional[str], 
               lm, stop_event=None, round_num: int = 0,
               progress=None) -> str:
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        # Team-Information aus topic extrahieren (wenn vorhanden)
        team_tag = ""
        team_name = None
        if topic.startswith("[TEAM ") and "]" in topic:
            team_match = re.match(r'\[TEAM ([A-Z]+)\]', topic)
            if team_match:
                team_name = team_match.group(1).lower()
                team_tag = f"[{team_name.upper()}] "
                topic = topic[team_match.end():].strip()
        
        doc_context = self.get_document_context(topic)
        has_document_context = bool(doc_context)
        
        # Externe Quellen
        external_info = ""
        if self.external_source and hasattr(self.external_source, 'use_external'):
            if self.external_source.use_external and hasattr(self.external_source, 'search_all'):
                try:
                    results = self.external_source.search_all(topic, 2)
                    if results and hasattr(self.external_source, 'format_all_results'):
                        external_info = self.external_source.format_all_results(results)
                except Exception as e:
                    pass
        
        context = ""
        if self.discussion_log and len(self.discussion_log) > 3:
            context = "\n".join(self.discussion_log[-3:])
        
        ziele = ", ".join(self.goals[:2]) if self.goals else "keine spezifischen"
        aengste = ", ".join(self.fears[:2]) if self.fears else "keine spezifischen"
        rank_text = f" (Rang: {self.rank}, {self.experience_points} XP)"
        
        citation_instruction = ""
        if self._requires_citation() and has_document_context and self.current_projects:
            citation_instruction = """
WICHTIG: Du MUSST Quellen angeben, wenn du aus Dokumenten zitierst!
Format: [Projekt::Dokument::Chunk]
Bei Nutzung von Dokumenten ohne Zitat gibt es Punktabzug!
"""
        
        # ========== NEUER PROMPT - NUTZT NUR VORHANDENE AGENTEN-DATEN ==========
        prompt = f"""Du bist {self.name}. Deine Rolle: {self.role}. Dein Charakter: {self.charakter_typ}.

Deine Ziele: {ziele}
Deine Ängste: {aengste}

So argumentierst du: {self.personality[:250]}

DEINE AUFGABE:
- Reagiere konkret auf andere Agenten
- Bringe deine fachspezifische Perspektive als {self.role} ein
- Positioniere dich klar
- Keine Floskeln wie "interessant" oder "komplex"
- Sag, was Sache ist aus deiner Rolle heraus
"""

        if self.current_projects:
            prompt += """
- Zitiere Quellen aus den Projekten: [Projekt::Dokument]
"""
        
        prompt += f"""
Thema: {topic}
"""
        if document:
            prompt += f"\nDOKUMENT:\n{document[:500]}...\n"
        if doc_context:
            prompt += f"\n{doc_context}\n"
        if context:
            prompt += f"\nLETZTE BEITRÄGE:\n{context}\n"
        if external_info:
            prompt += f"\nRECHERCHE:\n{external_info}\n"
        if citation_instruction:
            prompt += citation_instruction
        if team_name:
            prompt += f"\nDu bist im Team {team_name.upper()}. Passe deine Argumentation entsprechend an.\n"
        
        prompt += f"""
Runde {round_num + 1} der Diskussion.

3-5 Sätze. Keine Einleitungen wie "Als {self.role}..." - sag einfach deine Meinung.
"""
        
        response = lm.ask(prompt, f"Du bist {self.name} ({self.charakter_typ}).", stop_event)
        
        if response and response not in ["[ABGEBROCHEN]", "[Timeout]", "[Fehler]"]:
            self.last_response = response
            self.schon_gesagtes.append(response)
            self.current_position = response
            
            compliant, penalty, doc_citations, ext_citations = self._check_citation_compliance(response, has_document_context)
            self.citations_in_current_response = doc_citations
            self.external_citations_in_current_response = ext_citations
            
            self._gain_experience(Config.XP_PER_CONTRIBUTION, f"Beitrag in Diskussion")
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
                        "last_statement": response[:100]
                    }
                )
        
        return response if response else "..."
    
    def react_to(self, other_name: str, other_statement: str, 
                 topic: str, lm, stop_event=None, team_name: str = None) -> str:
        """Reagiert auf eine Aussage eines anderen Agenten"""
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        doc_context = self.get_document_context(topic, other_statement)
        has_document_context = bool(doc_context)
        
        ziele = ", ".join(self.goals[:2]) if self.goals else "keine spezifischen"
        aengste = ", ".join(self.fears[:2]) if self.fears else "keine spezifischen"
        
        citation_instruction = ""
        if self._requires_citation() and has_document_context and self.current_projects:
            citation_instruction = "\n- Zitiere Quellen: [Projekt::Dokument]"
        
        # ========== NEUER PROMPT FÜR REAKTIONEN ==========
        prompt = f"""Du bist {self.name}, {self.role} ({self.charakter_typ}).

Deine Ziele: {ziele}
Deine Ängste: {aengste}

So argumentierst du: {self.personality[:200]}

{other_name} hat gesagt: "{other_statement}"

Reagiere als {self.role}:
- Stimmst du zu? Widersprichst du?
- Was übersieht {other_name} aus deiner Perspektive?
{citation_instruction}
- Positioniere dich klar

3-4 Sätze. Keine Einleitungen.
"""
        
        if doc_context:
            prompt += f"\nRELEVANTE DOKUMENTE:\n{doc_context}\n"
        
        if team_name:
            prompt += f"\nDu bist im Team {team_name.upper()}.\n"
        
        response = lm.ask(prompt, f"Du bist {self.name} ({self.charakter_typ}).", stop_event)
        
        if response and response not in ["[ABGEBROCHEN]", "[Timeout]", "[Fehler]"]:
            self.last_response = response
            self.schon_gesagtes.append(response)
            
            compliant, penalty, doc_citations, ext_citations = self._check_citation_compliance(response, bool(doc_context))
            
            self._gain_experience(Config.XP_PER_REACTION, "Reaktion auf anderen Agenten")
            self._update_skills_for_contribution(is_reaction=True)
            
            if self.knowledge_graph:
                self.knowledge_graph.add_influence(other_name, self.name, topic, 0.5)
        
        return response if response else "..."
    
    def analyze(self, text: str, task_type: str, lm) -> Dict:
        prompt = f"""Du bist {self.name}, {self.role} ({self.rank}).

Deine Persönlichkeit: {self.personality[:200]}

Analysiere folgenden Text aus deiner fachspezifischen Perspektive als {self.role}:
{text}

Was sind die wichtigsten Punkte? Schreibe 3-4 Sätze. Keine Einleitungen.
"""
        
        response = lm.ask(prompt, f"Du bist {self.name}.")
        
        self._gain_experience(Config.XP_PER_ANALYSIS, f"Analyse durchgeführt")
        self.total_analyses += 1
        
        return {
            "agent": self.name,
            "role": self.role,
            "charakter": self.charakter_typ,
            "rank": self.rank,
            "task": task_type,
            "analysis": response
        }
    
    def learn_from(self, other_name: str, other_statement: str, 
                   topic: str, lm, other_role: str = "") -> bool:
        if self._global_duplicate_check(other_statement, topic):
            return False
        
        current_time = time.time()
        for fact in self.learned_facts[-10:]:
            if fact.get('timestamp') and (current_time - fact['timestamp']) < Config.TIME_WINDOW_DUPLICATE:
                similarity = self._text_similarity(other_statement, fact['fact'])
                if similarity > Config.LOCAL_DUPLICATE_THRESHOLD:
                    return False
        
        statement_hash = hashlib.md5(other_statement.encode()).hexdigest()
        if statement_hash in self.learned_hashes:
            return False
        
        for fact in self.learned_facts:
            if self._text_similarity(other_statement, fact['fact']) > Config.LOCAL_DUPLICATE_THRESHOLD:
                return False
        
        recent_facts = ""
        if self.learned_facts:
            facts_list = []
            for f in self.learned_facts[-5:]:
                facts_list.append(f"- {f['fact'][:100]}...")
            recent_facts = "\n".join(facts_list)
        else:
            recent_facts = "Du hast noch keine Kenntnisse."
        
        prompt = f"""Du bist {self.name}, {self.role}.

DEINE BISHERIGEN KENNTNISSE:
{recent_facts}

{other_name} hat gesagt:
"{other_statement}"

Auf einer Skala von 0 bis 100:
- 0 = irrelevant oder bereits bekannt
- 50 = teilweise neu
- 100 = absolut neu und wichtig

Gib NUR eine Zahl zwischen 0 und 100."""
        
        try:
            response = lm.ask(prompt, f"Du bist {self.name}.", max_tokens=10)
            score_match = re.search(r'(\d+)', response)
            base_score = int(score_match.group(1)) if score_match else 50
            base_score = max(0, min(100, base_score))
        except:
            base_score = 50
        
        skill_bonus = (self.skills.get("analyse", 0.5) - 0.5) * 40
        base_score = min(100, base_score + int(skill_bonus))
        importance = base_score / 100.0
        
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
            self.learned_hashes.add(statement_hash)
            self._limit_learned_facts()
            self._gain_experience(Config.XP_PER_LEARNED_FACT, f"Neue Information gelernt")
            self.total_learned_facts += 1
            self._update_skills_for_learning(base_score)
            return True
        
        return False
    
    def set_projects(self, project_names: List[str], k: int = None):
        self.current_projects = project_names
        if k:
            self.retrieval_k = k
    
    def get_citation_stats(self) -> Dict:
        return {
            "total_citations": self.total_citations_given,
            "total_external_citations": self.total_external_citations_given,
            "total_points": self.total_citation_points,
            "citations_this_round": len(self.citations_in_current_response),
            "missing_citations": self.missing_citations_this_round
        }
    
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "personality": self.personality,
            "color": self.color,
            "goals": self.goals,
            "fears": self.fears,
            "charakter_typ": self.charakter_typ,
            "skills": self.skills,
            "rank": self.rank,
            "experience_points": self.experience_points,
            "learned_facts_count": len(self.learned_facts),
            "current_projects": self.current_projects
        }
    
    def __repr__(self) -> str:
        return f"Agent({self.name}, {self.role}, {self.charakter_typ}, {self.rank})"