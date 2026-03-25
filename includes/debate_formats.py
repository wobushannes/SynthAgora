#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debatten-Formate für SynthAgora
- Pro/Contra (zwei Teams)
- Fishbowl (innere/äußere Kreise)
- World Café (wechselnde Gruppen)
- Delphi-Methode (mehrere Runden mit Feedback)
- Prämisse prüfen (These beweisen/widerlegen)
"""

import random
import threading
import time
import re
from typing import List, Dict, Optional, Any, Callable, Tuple, Generator
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class DebateFormat(Enum):
    """Verfügbare Debatten-Formate"""
    PRO_CONTRA = "pro_contra"
    FISHBOWL = "fishbowl"
    WORLD_CAFE = "world_cafe"
    DELPHI = "delphi"
    PREMISE_CHECK = "premise_check"
    CLASSIC = "classic"


@dataclass
class DebateConfig:
    """Konfiguration für eine Debatte"""
    format: str = "classic"
    rounds: int = 3
    time_per_round: int = 60
    thinking_time: int = 10
    enable_moderator: bool = False
    enable_voting: bool = False
    enable_sanctions: bool = False
    team_mode: bool = False
    
    # Pro/Contra spezifisch
    pro_team_name: str = "Pro"
    contra_team_name: str = "Contra"
    pro_agents: List[str] = field(default_factory=list)
    contra_agents: List[str] = field(default_factory=list)
    
    # Fishbowl spezifisch
    inner_circle_size: int = 5
    outer_circle_can_speak: bool = False
    
    # World Café spezifisch
    cafe_tables: int = 3
    rotation_rounds: int = 3
    
    # Delphi spezifisch
    delphi_rounds: int = 3
    anonymous_votes: bool = True
    show_statistics: bool = True
    
    # Prämisse spezifisch
    premise: str = ""
    prove_mode: bool = True


class DebateRound:
    """Eine einzelne Debatten-Runde"""
    
    def __init__(self, round_num: int, config: DebateConfig):
        self.round_num = round_num
        self.config = config
        self.contributions: List[Dict] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.votes: Dict[str, Dict] = {}
        self.summary: str = ""
    
    def add_contribution(self, agent_name: str, content: str, team: str = None):
        self.contributions.append({
            "agent": agent_name,
            "content": content,
            "team": team,
            "timestamp": datetime.now().isoformat(),
            "round": self.round_num
        })
    
    def add_vote(self, agent_name: str, vote: str, reason: str = ""):
        self.votes[agent_name] = {"vote": vote, "reason": reason, "timestamp": datetime.now().isoformat()}
    
    def get_vote_results(self) -> Dict:
        results = {"pro": 0, "contra": 0, "abstain": 0}
        for vote in self.votes.values():
            v = vote["vote"].lower()
            if v in results:
                results[v] += 1
            else:
                results["abstain"] += 1
        return results


class DebateSession:
    """Eine komplette Debatten-Session"""
    
    def __init__(self, topic: str, config: DebateConfig, agents: List, lm_client, db=None):
        self.topic = topic
        self.config = config
        self.agents = agents
        self.lm = lm_client
        self.db = db
        self.rounds: List[DebateRound] = []
        self.current_round = 0
        self.results = {}
        self.stop_event = threading.Event()
        self.is_running = False
        self.discussion_log = []
        
        # Team-Zuordnung für Pro/Contra
        self.teams = {}
        self._assign_teams()
    
    def _assign_teams(self):
        """Weist Agenten Teams zu"""
        # Nur für Formate mit Teams
        if self.config.format not in ["pro_contra", "premise_check"]:
            return
        
        # Erstelle Mapping von Namen zu Agent-Objekten
        agent_by_name = {a.name: a for a in self.agents}
        
        if self.config.pro_agents or self.config.contra_agents:
            # Manuelle Zuordnung
            for name in self.config.pro_agents:
                if name in agent_by_name:
                    self.teams[name] = "pro"
            for name in self.config.contra_agents:
                if name in agent_by_name:
                    self.teams[name] = "contra"
        else:
            # Automatische Zufallsverteilung
            shuffled = self.agents.copy()
            random.shuffle(shuffled)
            half = len(shuffled) // 2
            for agent in shuffled[:half]:
                self.teams[agent.name] = "pro"
            for agent in shuffled[half:]:
                self.teams[agent.name] = "contra"
    
    def get_team(self, agent_name: str) -> Optional[str]:
        return self.teams.get(agent_name)
    
    def add_to_log(self, text: str):
        self.discussion_log.append(text)
        if len(self.discussion_log) > 500:
            self.discussion_log = self.discussion_log[-500:]
    
    def start(self, callback: Callable = None) -> Generator:
        self.is_running = True
        self.stop_event.clear()
        
        format_str = self.config.format
        
        if format_str == "pro_contra":
            yield from self._run_pro_contra(callback)
        elif format_str == "fishbowl":
            yield from self._run_fishbowl(callback)
        elif format_str == "world_cafe":
            yield from self._run_world_cafe(callback)
        elif format_str == "delphi":
            yield from self._run_delphi(callback)
        elif format_str == "premise_check":
            yield from self._run_premise_check(callback)
        else:
            yield from self._run_classic(callback)
        
        self.is_running = False
    
    def _run_pro_contra(self, callback) -> Generator:
        """Pro/Contra-Debatte"""
        pro_agents = [a for a in self.agents if self.teams.get(a.name) == "pro"]
        contra_agents = [a for a in self.agents if self.teams.get(a.name) == "contra"]
        
        yield ("system", f"🏆 PRO/CONTRA DEBATTE: {self.topic}")
        yield ("system", f"👥 Pro-Team ({len(pro_agents)}): {', '.join([a.name for a in pro_agents[:10]])}")
        yield ("system", f"👥 Contra-Team ({len(contra_agents)}): {', '.join([a.name for a in contra_agents[:10]])}")
        
        for round_num in range(self.config.rounds):
            if self.stop_event.is_set():
                break
            
            round_data = DebateRound(round_num + 1, self.config)
            self.current_round = round_num + 1
            
            yield ("round_start", f"Runde {round_num+1}/{self.config.rounds}")
            
            # Pro spricht
            yield ("system", "🎤 Pro-Team spricht:")
            for agent in pro_agents:
                if self.stop_event.is_set():
                    break
                if agent.ausgeschlossen:
                    continue
                
                answer = self._get_agent_answer(agent, self.topic, None, round_num, team="pro")
                if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                    round_data.add_contribution(agent.name, answer, "pro")
                    yield ("agent", agent.name, answer, agent.color, "pro")
                    self.add_to_log(f"[PRO] {agent.name}: {answer}")
            
            # Contra spricht
            yield ("system", "🎤 Contra-Team spricht:")
            for agent in contra_agents:
                if self.stop_event.is_set():
                    break
                if agent.ausgeschlossen:
                    continue
                
                answer = self._get_agent_answer(agent, self.topic, None, round_num, team="contra")
                if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                    round_data.add_contribution(agent.name, answer, "contra")
                    yield ("agent", agent.name, answer, agent.color, "contra")
                    self.add_to_log(f"[CONTRA] {agent.name}: {answer}")
            
            if self.config.enable_voting:
                yield ("system", "🗳️ Abstimmung")
                votes = self._collect_votes(pro_agents + contra_agents, round_data)
                round_data.votes = votes
                results = round_data.get_vote_results()
                yield ("system", f"📊 Ergebnis: Pro={results['pro']}, Contra={results['contra']}, Enthaltung={results['abstain']}")
            
            self.rounds.append(round_data)
            yield ("round_end", f"Runde {round_num+1} beendet")
        
        yield ("system", self._generate_summary())
    
    def _run_premise_check(self, callback) -> Generator:
        """Prämisse prüfen"""
        premise = self.config.premise or self.topic
        mode_text = "beweisen" if self.config.prove_mode else "widerlegen"
        
        pro_agents = [a for a in self.agents if self.teams.get(a.name) == "pro"]
        contra_agents = [a for a in self.agents if self.teams.get(a.name) == "contra"]
        
        if not pro_agents and not contra_agents:
            shuffled = self.agents.copy()
            random.shuffle(shuffled)
            half = len(shuffled) // 2
            pro_agents = shuffled[:half]
            contra_agents = shuffled[half:]
            for a in pro_agents:
                self.teams[a.name] = "pro"
            for a in contra_agents:
                self.teams[a.name] = "contra"
        
        yield ("system", f"⚖️ PRÄMISSE PRÜFEN: {premise}")
        yield ("system", f"🎯 Aufgabe: Die These {mode_text}")
        yield ("system", f"👥 Pro-Team ({len(pro_agents)}): {', '.join([a.name for a in pro_agents[:10]])}")
        yield ("system", f"👥 Contra-Team ({len(contra_agents)}): {', '.join([a.name for a in contra_agents[:10]])}")
        
        arguments_for = []
        arguments_against = []
        
        for round_num in range(self.config.rounds):
            if self.stop_event.is_set():
                break
            
            round_data = DebateRound(round_num + 1, self.config)
            self.current_round = round_num + 1
            
            yield ("round_start", f"Runde {round_num+1}/{self.config.rounds}")
            
            if self.config.prove_mode:
                # Pro argumentiert FÜR die These
                yield ("system", "✅ Pro-Team (Argumente FÜR die These):")
                for agent in pro_agents:
                    if self.stop_event.is_set():
                        break
                    if agent.ausgeschlossen:
                        continue
                    
                    prompt = f"""These: {premise}
Aufgabe: Beweise diese These. Liefere ein Argument für deine Position (max 3 Sätze)."""
                    
                    answer = self._get_agent_answer(agent, prompt, None, round_num, team="pro")
                    if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        arguments_for.append({"agent": agent.name, "text": answer})
                        round_data.add_contribution(agent.name, answer, "pro")
                        yield ("agent", agent.name, f"✅ {answer}", agent.color, "pro")
                        self.add_to_log(f"[PRO] {agent.name}: {answer}")
                
                # Contra argumentiert GEGEN die These
                yield ("system", "❌ Contra-Team (Argumente GEGEN die These):")
                for agent in contra_agents:
                    if self.stop_event.is_set():
                        break
                    if agent.ausgeschlossen:
                        continue
                    
                    prompt = f"""These: {premise}
Aufgabe: Widerlege diese These. Liefere ein Argument gegen die These (max 3 Sätze)."""
                    
                    answer = self._get_agent_answer(agent, prompt, None, round_num, team="contra")
                    if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        arguments_against.append({"agent": agent.name, "text": answer})
                        round_data.add_contribution(agent.name, answer, "contra")
                        yield ("agent", agent.name, f"❌ {answer}", agent.color, "contra")
                        self.add_to_log(f"[CONTRA] {agent.name}: {answer}")
            
            else:
                # Widerlegungs-Modus: Contra beginnt
                yield ("system", "❌ Contra-Team (Argumente GEGEN die These):")
                for agent in contra_agents:
                    if self.stop_event.is_set():
                        break
                    if agent.ausgeschlossen:
                        continue
                    
                    prompt = f"""These: {premise}
Aufgabe: Widerlege diese These. Liefere ein Argument gegen die These (max 3 Sätze)."""
                    
                    answer = self._get_agent_answer(agent, prompt, None, round_num, team="contra")
                    if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        arguments_against.append({"agent": agent.name, "text": answer})
                        round_data.add_contribution(agent.name, answer, "contra")
                        yield ("agent", agent.name, f"❌ {answer}", agent.color, "contra")
                        self.add_to_log(f"[CONTRA] {agent.name}: {answer}")
                
                # Pro verteidigt
                yield ("system", "✅ Pro-Team (Verteidigung):")
                for agent in pro_agents:
                    if self.stop_event.is_set():
                        break
                    if agent.ausgeschlossen:
                        continue
                    
                    prompt = f"""These: {premise}
Aufgabe: Verteidige diese These. Liefere ein Argument für die These (max 3 Sätze)."""
                    
                    answer = self._get_agent_answer(agent, prompt, None, round_num, team="pro")
                    if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        arguments_for.append({"agent": agent.name, "text": answer})
                        round_data.add_contribution(agent.name, answer, "pro")
                        yield ("agent", agent.name, f"✅ {answer}", agent.color, "pro")
                        self.add_to_log(f"[PRO] {agent.name}: {answer}")
            
            self.rounds.append(round_data)
            yield ("round_end", f"Runde {round_num+1} beendet")
        
        yield ("system", self._generate_premise_summary(premise, arguments_for, arguments_against))
    
    def _run_fishbowl(self, callback) -> Generator:
        """Fishbowl-Debatte"""
        inner_agents = self.agents[:min(self.config.inner_circle_size, len(self.agents))]
        outer_agents = self.agents[len(inner_agents):]
        
        yield ("system", f"🐟 FISHBOWL DEBATTE: {self.topic}")
        yield ("system", f"🟢 Innerer Kreis ({len(inner_agents)}): {', '.join([a.name for a in inner_agents])}")
        yield ("system", f"⚪ Äußerer Kreis ({len(outer_agents)}): {', '.join([a.name for a in outer_agents[:10]])}")
        
        for round_num in range(self.config.rounds):
            if self.stop_event.is_set():
                break
            
            round_data = DebateRound(round_num + 1, self.config)
            self.current_round = round_num + 1
            
            yield ("round_start", f"Runde {round_num+1}/{self.config.rounds}")
            
            for agent in inner_agents:
                if self.stop_event.is_set():
                    break
                if agent.ausgeschlossen:
                    continue
                
                answer = self._get_agent_answer(agent, self.topic, None, round_num)
                if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                    round_data.add_contribution(agent.name, answer)
                    yield ("agent", agent.name, answer, agent.color)
                    self.add_to_log(f"{agent.name}: {answer}")
            
            self.rounds.append(round_data)
            yield ("round_end", f"Runde {round_num+1} beendet")
            
            # Rotation
            if round_num < self.config.rounds - 1 and outer_agents:
                new_inner = []
                for agent in inner_agents:
                    if random.random() < 0.5 and outer_agents:
                        outer_agents.append(agent)
                    else:
                        new_inner.append(agent)
                while len(new_inner) < self.config.inner_circle_size and outer_agents:
                    new_inner.append(outer_agents.pop(0))
                if new_inner:
                    inner_agents = new_inner
                    yield ("system", f"🔄 Rotation: Neuer innerer Kreis")
    
    def _run_world_cafe(self, callback) -> Generator:
        """World Café"""
        tables = [[] for _ in range(self.config.cafe_tables)]
        for i, agent in enumerate(self.agents):
            tables[i % self.config.cafe_tables].append(agent)
        
        yield ("system", f"☕ WORLD CAFÉ: {self.topic}")
        
        for round_num in range(self.config.rotation_rounds):
            if self.stop_event.is_set():
                break
            
            yield ("system", f"--- ROTATION {round_num+1}/{self.config.rotation_rounds} ---")
            
            for table_idx, table_agents in enumerate(tables):
                if not table_agents:
                    continue
                yield ("system", f"📌 Tisch {table_idx+1}")
                for agent in table_agents:
                    if self.stop_event.is_set():
                        break
                    if agent.ausgeschlossen:
                        continue
                    answer = self._get_agent_answer(agent, self.topic, None, round_num)
                    if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        yield ("agent", agent.name, f"[Tisch {table_idx+1}] {answer}", agent.color)
                        self.add_to_log(f"[Tisch {table_idx+1}] {agent.name}: {answer}")
            
            # Rotation
            if round_num < self.config.rotation_rounds - 1:
                rotating = []
                for table in tables:
                    if table:
                        rotating.append(table.pop(0))
                for i, agent in enumerate(rotating):
                    tables[i % len(tables)].append(agent)
        
        yield ("system", "☕ World Café beendet")
    
    def _run_delphi(self, callback) -> Generator:
        """Delphi-Methode mit Begründungen und Feedback"""
        yield ("system", f"🔮 DELPHI-METHODE: {self.topic}")
        
        all_responses = []
        
        for round_num in range(self.config.delphi_rounds):
            if self.stop_event.is_set():
                break
            
            round_data = DebateRound(round_num + 1, self.config)
            self.current_round = round_num + 1
            
            yield ("round_start", f"Delphi-Runde {round_num+1}/{self.config.delphi_rounds}")
            
            feedback = ""
            if round_num > 0 and self.config.show_statistics:
                feedback = self._generate_delphi_feedback(all_responses)
                yield ("system", f"📊 Feedback aus Runde {round_num}: {feedback}")
            
            responses = []
            for agent in self.agents:
                if self.stop_event.is_set():
                    break
                if agent.ausgeschlossen:
                    continue
                
                # Prompt mit Begründungsaufforderung
                if round_num == 0:
                    prompt = f"""Thema: {self.topic}

Bewerte auf einer Skala von 1-10 (1 = stimme überhaupt nicht zu, 10 = stimme voll zu), wie sehr du der folgenden Aussage zustimmst:
"{self.config.premise or self.topic}"

Gib deine Bewertung als Zahl und dann eine kurze Begründung (2-3 Sätze)."""
                else:
                    prompt = f"""Thema: {self.topic}

Feedback aus der letzten Runde: {feedback}

Bewerte auf einer Skala von 1-10 (1 = stimme überhaupt nicht zu, 10 = stimme voll zu), wie sehr du der folgenden Aussage zustimmst:
"{self.config.premise or self.topic}"

Gib deine Bewertung als Zahl und dann eine kurze Begründung (2-3 Sätze). Berücksichtige dabei das Feedback."""
                
                answer = self._get_agent_answer(agent, prompt, None, round_num)
                if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                    score = self._extract_score(answer)
                    responses.append({
                        "agent": agent.name,
                        "score": score,
                        "reasoning": answer
                    })
                    if not self.config.anonymous_votes:
                        yield ("agent", agent.name, f"📊 {answer}", agent.color)
                    round_data.add_contribution(agent.name, answer)
                    self.add_to_log(f"{agent.name}: {answer}")
            
            all_responses.append(responses)
            self.rounds.append(round_data)
            
            if responses and self._check_consensus(responses):
                yield ("system", f"✅ Konsens erreicht in Runde {round_num+1}!")
                break
        
        final_stats = self._generate_delphi_final(all_responses)
        yield ("system", f"📊 DELPHI-ERGEBNISSE:\n{final_stats}")
    
    def _run_classic(self, callback) -> Generator:
        """Klassische Debatte"""
        for round_num in range(self.config.rounds):
            if self.stop_event.is_set():
                break
            
            round_data = DebateRound(round_num + 1, self.config)
            self.current_round = round_num + 1
            
            yield ("round_start", f"Runde {round_num+1}/{self.config.rounds}")
            
            for agent in self.agents:
                if self.stop_event.is_set():
                    break
                if agent.ausgeschlossen:
                    continue
                
                answer = self._get_agent_answer(agent, self.topic, None, round_num)
                if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                    round_data.add_contribution(agent.name, answer)
                    yield ("agent", agent.name, answer, agent.color)
                    self.add_to_log(f"{agent.name}: {answer}")
            
            self.rounds.append(round_data)
            yield ("round_end", f"Runde {round_num+1} beendet")
        
        yield ("system", self._generate_summary())
    
    def _get_agent_answer(self, agent, topic, document, round_num, context="", team=None) -> str:
        try:
            # Team-Information in Topic einbauen
            if team:
                topic_with_team = f"[TEAM {team.upper()}] {topic}"
            else:
                topic_with_team = topic
            
            answer = agent.answer(topic_with_team, document, self.lm, self.stop_event, round_num)
            return answer
        except Exception as e:
            print(f"❌ Fehler bei Agent {agent.name}: {e}")
            return "[FEHLER]"
    
    def _get_context(self, recent_contributions: List[Dict]) -> str:
        if not recent_contributions:
            return ""
        return "\n".join([f"{c['agent']}: {c['content'][:200]}" for c in recent_contributions])
    
    def _collect_votes(self, agents, round_data: DebateRound) -> Dict:
        votes = {}
        for agent in agents:
            if agent.ausgeschlossen:
                continue
            prompt = f"""Thema: {self.topic}
Bisherige Diskussion: {self._get_context(round_data.contributions[-5:])}

Gib deine Stimme ab: Pro, Contra oder Enthaltung.
Begründe kurz (1 Satz)."""
            response = self._get_agent_answer(agent, prompt, None, self.current_round)
            if response:
                vote = "pro" if "pro" in response.lower() else "contra" if "contra" in response.lower() else "abstain"
                votes[agent.name] = {"vote": vote, "reason": response}
        return votes
    
    def _extract_score(self, text: str) -> int:
        """Extrahiert eine Zahl 1-10 aus Text"""
        patterns = [
            r'\b([1-9]|10)\b',
            r'(\d+)/10',
            r'Bewertung:?\s*(\d+)',
            r'Punktzahl:?\s*(\d+)',
            r'(\d+)\s*Punkte',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 10:
                    return val
        return 5
    
    def _check_consensus(self, responses: List[Dict]) -> bool:
        """Prüft ob Konsens erreicht wurde (80% innerhalb 2 Punkte)"""
        scores = [r["score"] for r in responses]
        if not scores:
            return False
        avg = sum(scores) / len(scores)
        within_range = sum(1 for s in scores if abs(s - avg) <= 2)
        return within_range / len(scores) >= 0.8
    
    def _generate_delphi_feedback(self, all_responses: List[List[Dict]]) -> str:
        """Generiert Feedback für Delphi-Runde"""
        if not all_responses:
            return ""
        last_round = all_responses[-1]
        scores = [r["score"] for r in last_round]
        avg = sum(scores) / len(scores) if scores else 0
        std = (sum((s - avg) ** 2 for s in scores) / len(scores)) ** 0.5 if scores else 0
        
        reasons = []
        for r in last_round[:3]:
            reasons.append(f"{r['agent']}: {r['reasoning'][:100]}...")
        
        feedback = f"Durchschnitt: {avg:.1f}/10, Streuung: {std:.1f}\n"
        feedback += f"Beispiel-Argumente:\n" + "\n".join(reasons)
        return feedback
    
    def _generate_delphi_final(self, all_responses: List[List[Dict]]) -> str:
        """Generiert finale Delphi-Ergebnisse"""
        if not all_responses:
            return "Keine Ergebnisse"
        
        final_round = all_responses[-1]
        scores = [r["score"] for r in final_round]
        avg = sum(scores) / len(scores) if scores else 0
        
        text = f"Endgültiger Konsens: {avg:.1f}/10\n\n"
        text += "Detaillierte Begründungen:\n"
        for r in final_round:
            text += f"\n{r['agent']}: {r['score']}/10\n"
            text += f"  • {r['reasoning'][:200]}...\n"
        return text
    
    def _generate_premise_summary(self, premise: str, pro_args: List, contra_args: List) -> str:
        text = f"📋 PRÄMISSEN-PRÜFUNG: {premise}\n\n"
        text += f"✅ ARGUMENTE FÜR ({len(pro_args)}):\n"
        for arg in pro_args[:5]:
            text += f"  • {arg['agent']}: {arg['text'][:100]}...\n"
        text += f"\n❌ ARGUMENTE DAGEGEN ({len(contra_args)}):\n"
        for arg in contra_args[:5]:
            text += f"  • {arg['agent']}: {arg['text'][:100]}...\n"
        
        if len(pro_args) > len(contra_args):
            text += f"\n📊 Fazit: Mehr Argumente FÜR die These ({len(pro_args)} vs {len(contra_args)})"
        elif len(contra_args) > len(pro_args):
            text += f"\n📊 Fazit: Mehr Argumente GEGEN die These ({len(contra_args)} vs {len(pro_args)})"
        else:
            text += f"\n📊 Fazit: Ausgeglichen ({len(pro_args)} vs {len(contra_args)})"
        
        return text
    
    def _generate_summary(self) -> str:
        total_contributions = sum(len(r.contributions) for r in self.rounds)
        return f"📊 DEBATTE BEENDET\n• {len(self.rounds)} Runden\n• {total_contributions} Beiträge\n• Format: {self.config.format}"
    
    def stop(self):
        self.stop_event.set()
        self.is_running = False
    
    def get_results(self) -> Dict:
        return {
            "topic": self.topic,
            "format": self.config.format,
            "rounds": len(self.rounds),
            "total_contributions": sum(len(r.contributions) for r in self.rounds),
            "rounds_data": [
                {
                    "round": r.round_num,
                    "contributions": r.contributions,
                    "votes": r.votes
                }
                for r in self.rounds
            ]
        }


def get_available_formats() -> List[Dict]:
    return [
        {"id": "classic", "name": "Klassisch", "description": "Standard-Diskussion mit allen Agenten"},
        {"id": "pro_contra", "name": "Pro/Contra", "description": "Zwei Teams debattieren gegeneinander"},
        {"id": "fishbowl", "name": "Fishbowl", "description": "Innerer Kreis diskutiert, äußerer hört zu"},
        {"id": "world_cafe", "name": "World Café", "description": "Wechselnde Kleingruppen diskutieren"},
        {"id": "delphi", "name": "Delphi", "description": "Mehrere Runden mit Feedback bis Konsens"},
        {"id": "premise_check", "name": "Prämisse prüfen", "description": "These beweisen oder widerlegen"}
    ]


if __name__ == "__main__":
    print("Verfügbare Formate:")
    for f in get_available_formats():
        print(f"  • {f['name']}: {f['description']}")