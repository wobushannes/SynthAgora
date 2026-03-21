#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debatten-Controller für SynthAgora
- Timer (Runden-Zeitlimit)
- Rednerliste (wer darf wann sprechen)
- Unterbrechungen (Agenten können sich ins Wort fallen)
- Sanktionen (bei Wiederholungen, Ausweichen, Beleidigungen)
"""

import threading
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Any, Callable, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field


class SpeakerStatus(Enum):
    """Status eines Sprechers"""
    WAITING = "waiting"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    FINISHED = "finished"
    SANCTIONED = "sanctioned"
    SKIPPED = "skipped"


class SanctionType(Enum):
    """Arten von Sanktionen"""
    WARNING = "warning"
    MUTE = "mute"           # Für X Runden stumm
    POINT_DEDUCTION = "point_deduction"
    EXPULSION = "expulsion"  # Aus der Diskussion ausschließen


@dataclass
class Speaker:
    """Ein Sprecher in der Rednerliste"""
    name: str
    agent: Any
    status: SpeakerStatus = SpeakerStatus.WAITING
    position: int = 0
    speaking_time: float = 0.0
    contributions: int = 0
    warnings: int = 0
    sanction: Optional[SanctionType] = None
    sanction_until_round: int = 0


class DebateController:
    """Steuert den Ablauf einer Debatte"""
    
    def __init__(self, agents: List, config: Dict = None):
        """
        Args:
            agents: Liste der Agenten
            config: {
                "time_per_round": int,      # Sekunden pro Runde (0 = unbegrenzt)
                "thinking_time": int,       # Sekunden pro Agent
                "speaker_list": bool,       # Rednerliste aktivieren
                "interruptions": bool,      # Unterbrechungen erlauben
                "sanctions": bool,          # Sanktionen aktivieren
                "max_warnings": int,        # Max Verwarnungen vor Sanktion
                "mute_rounds": int,         # Runden die stummgeschaltet wird
                "repetition_threshold": int # Wiederholungen bis Verwarnung
            }
        """
        self.agents = agents
        self.config = {
            "time_per_round": 0,          # 0 = unbegrenzt
            "thinking_time": 10,          # Sekunden
            "speaker_list": False,
            "interruptions": False,
            "sanctions": False,
            "max_warnings": 3,
            "mute_rounds": 2,
            "repetition_threshold": 2,
            **(config or {})
        }
        
        # Rednerliste
        self.speakers: List[Speaker] = []
        self.current_speaker: Optional[Speaker] = None
        self.speaker_index = 0
        
        # Timing
        self.round_start_time: Optional[float] = None
        self.speaker_start_time: Optional[float] = None
        self.timer_thread: Optional[threading.Thread] = None
        self.stop_timer = threading.Event()
        
        # Verhaltenstracking
        self.agent_history: Dict[str, List[str]] = {}  # {name: [letzte Aussagen]}
        self.agent_repetitions: Dict[str, int] = {}
        
        # Events
        self.on_timeout: Optional[Callable] = None
        self.on_interruption: Optional[Callable] = None
        self.on_sanction: Optional[Callable] = None
        
        self._init_speakers()
    
    def _init_speakers(self):
        """Initialisiert die Rednerliste"""
        self.speakers = []
        for i, agent in enumerate(self.agents):
            self.speakers.append(Speaker(
                name=agent.name,
                agent=agent,
                position=i
            ))
            self.agent_history[agent.name] = []
            self.agent_repetitions[agent.name] = 0
    
    def reset(self):
        """Setzt den Controller zurück"""
        self.stop_timer.set()
        if self.timer_thread:
            self.timer_thread.join(timeout=1)
        
        self.speaker_index = 0
        self.current_speaker = None
        self.round_start_time = None
        self.speaker_start_time = None
        self.stop_timer.clear()
        
        for speaker in self.speakers:
            speaker.status = SpeakerStatus.WAITING
            speaker.speaking_time = 0
            speaker.warnings = 0
            speaker.sanction = None
            speaker.sanction_until_round = 0
        
        for name in self.agent_history:
            self.agent_history[name] = []
            self.agent_repetitions[name] = 0
    
    def start_round(self, round_num: int):
        """Startet eine neue Runde"""
        self.round_start_time = time.time()
        
        # Sanktionen aktualisieren
        for speaker in self.speakers:
            if speaker.sanction_until_round <= round_num:
                speaker.sanction = None
                speaker.sanction_until_round = 0
                if speaker.status == SpeakerStatus.SANCTIONED:
                    speaker.status = SpeakerStatus.WAITING
        
        # Rednerliste zurücksetzen
        if self.config["speaker_list"]:
            self.speaker_index = 0
            self._update_speaker_order()
    
    def _update_speaker_order(self):
        """Aktualisiert die Reihenfolge der Redner (basierend auf Status)"""
        # Aktive Sprecher zuerst
        active = [s for s in self.speakers if s.status not in [SpeakerStatus.SANCTIONED, SpeakerStatus.FINISHED]]
        sanctioned = [s for s in self.speakers if s.status == SpeakerStatus.SANCTIONED]
        
        # Sortiere nach Position
        active.sort(key=lambda s: s.position)
        sanctioned.sort(key=lambda s: s.position)
        
        self.speakers = active + sanctioned
        for i, s in enumerate(self.speakers):
            s.position = i
    
    def can_speak(self, agent_name: str, round_num: int) -> Tuple[bool, str]:
        """
        Prüft ob ein Agent sprechen darf.
        
        Returns:
            (darf_sprechen, grund)
        """
        speaker = self._get_speaker(agent_name)
        if not speaker:
            return False, "Agent nicht in Rednerliste"
        
        # Sanktioniert?
        if speaker.sanction:
            return False, f"Sanktioniert: {speaker.sanction.value}"
        
        # Schon gesprochen in dieser Runde?
        if speaker.status == SpeakerStatus.FINISHED:
            return False, "Bereits gesprochen in dieser Runde"
        
        # Rednerliste aktiv?
        if self.config["speaker_list"] and self.current_speaker:
            if agent_name != self.current_speaker.name:
                return False, f"Rednerliste: {self.current_speaker.name} ist an der Reihe"
        
        # Zeitüberschreitung?
        if self.config["time_per_round"] > 0:
            elapsed = time.time() - self.round_start_time
            if elapsed >= self.config["time_per_round"]:
                return False, "Rundenzeit abgelaufen"
        
        return True, ""
    
    def start_speaking(self, agent_name: str) -> bool:
        """Startet den Sprechvorgang"""
        speaker = self._get_speaker(agent_name)
        if not speaker:
            return False
        
        speaker.status = SpeakerStatus.SPEAKING
        speaker.speaking_time = time.time()
        self.current_speaker = speaker
        
        # Timer starten (falls Thinking-Time gesetzt)
        if self.config["thinking_time"] > 0:
            self._start_timer(self.config["thinking_time"], 
                              lambda: self._timeout_speaker(agent_name))
        
        return True
    
    def finish_speaking(self, agent_name: str, statement: str):
        """Beendet den Sprechvorgang"""
        speaker = self._get_speaker(agent_name)
        if not speaker:
            return
        
        # Zeit messen
        if speaker.speaking_time:
            duration = time.time() - speaker.speaking_time
            speaker.speaking_time = duration
        
        speaker.status = SpeakerStatus.FINISHED
        speaker.contributions += 1
        self.current_speaker = None
        self.stop_timer.set()
        
        # Wiederholungen prüfen
        self._check_repetition(agent_name, statement)
        
        # Nächsten Sprecher in der Rednerliste aktivieren
        if self.config["speaker_list"]:
            self._next_speaker()
    
    def _next_speaker(self):
        """Aktiviert den nächsten Sprecher in der Rednerliste"""
        self.speaker_index += 1
        if self.speaker_index < len(self.speakers):
            next_speaker = self.speakers[self.speaker_index]
            if next_speaker.status == SpeakerStatus.WAITING:
                # Callback für nächsten Sprecher
                if self.on_timeout:
                    self.on_timeout(next_speaker.name)
    
    def interrupt(self, interrupter: str, target: str) -> Tuple[bool, str]:
        """
        Unterbrechung eines Sprechers.
        
        Returns:
            (erfolgreich, nachricht)
        """
        if not self.config["interruptions"]:
            return False, "Unterbrechungen nicht erlaubt"
        
        target_speaker = self._get_speaker(target)
        if not target_speaker or target_speaker.status != SpeakerStatus.SPEAKING:
            return False, "Ziel spricht nicht"
        
        interrupter_speaker = self._get_speaker(interrupter)
        if not interrupter_speaker:
            return False, "Unterbrecher nicht in Rednerliste"
        
        # Unterbrechung durchführen
        target_speaker.status = SpeakerStatus.INTERRUPTED
        
        # Unterbrecher wird neuer Sprecher
        interrupter_speaker.status = SpeakerStatus.SPEAKING
        interrupter_speaker.speaking_time = time.time()
        self.current_speaker = interrupter_speaker
        
        if self.on_interruption:
            self.on_interruption(interrupter, target)
        
        return True, f"{interrupter} unterbricht {target}"
    
    def sanction(self, agent_name: str, reason: str, sanction_type: SanctionType = SanctionType.WARNING) -> bool:
        """
        Verhängt eine Sanktion.
        
        Returns:
            Erfolgreich
        """
        if not self.config["sanctions"]:
            return False
        
        speaker = self._get_speaker(agent_name)
        if not speaker:
            return False
        
        if sanction_type == SanctionType.WARNING:
            speaker.warnings += 1
            if speaker.warnings >= self.config["max_warnings"]:
                # Upgrade zu Mute
                return self.sanction(agent_name, f"Zu viele Verwarnungen ({speaker.warnings})", 
                                     SanctionType.MUTE)
        
        elif sanction_type == SanctionType.MUTE:
            speaker.sanction = SanctionType.MUTE
            speaker.sanction_until_round = self.config["mute_rounds"]
            speaker.status = SpeakerStatus.SANCTIONED
        
        elif sanction_type == SanctionType.POINT_DEDUCTION:
            # Punkteabzug (wird woanders implementiert)
            speaker.sanction = SanctionType.POINT_DEDUCTION
        
        elif sanction_type == SanctionType.EXPULSION:
            speaker.sanction = SanctionType.EXPULSION
            speaker.status = SpeakerStatus.SANCTIONED
            if speaker.agent:
                speaker.agent.ausgeschlossen = True
        
        if self.on_sanction:
            self.on_sanction(agent_name, sanction_type.value, reason)
        
        return True
    
    def _check_repetition(self, agent_name: str, statement: str):
        """Prüft auf Wiederholungen und verhängt ggf. Verwarnung"""
        history = self.agent_history[agent_name]
        
        # Prüfe auf exakte Wiederholung
        if statement in history:
            self.agent_repetitions[agent_name] += 1
            if self.agent_repetitions[agent_name] >= self.config["repetition_threshold"]:
                self.sanction(agent_name, f"Wiederholung ({self.agent_repetitions[agent_name]}x)", 
                             SanctionType.WARNING)
        else:
            self.agent_repetitions[agent_name] = 0
        
        # Prüfe auf Ähnlichkeit mit letzten Aussagen
        for past in history[-3:]:
            if self._text_similarity(statement, past) > 0.8:
                self.sanction(agent_name, "Zu ähnliche Aussage", SanctionType.WARNING)
                break
        
        # Historie aktualisieren
        history.append(statement)
        if len(history) > 20:
            history.pop(0)
        self.agent_history[agent_name] = history
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Einfache Ähnlichkeitsprüfung"""
        if not text1 or not text2:
            return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)
    
    def _get_speaker(self, name: str) -> Optional[Speaker]:
        for s in self.speakers:
            if s.name == name:
                return s
        return None
    
    def _start_timer(self, seconds: int, callback: Callable):
        """Startet einen Timer-Thread"""
        def timer_func():
            if self.stop_timer.wait(seconds):
                return
            callback()
        
        self.stop_timer.clear()
        self.timer_thread = threading.Thread(target=timer_func, daemon=True)
        self.timer_thread.start()
    
    def _timeout_speaker(self, agent_name: str):
        """Wird aufgerufen wenn ein Sprecher die Zeit überschreitet"""
        speaker = self._get_speaker(agent_name)
        if speaker and speaker.status == SpeakerStatus.SPEAKING:
            speaker.status = SpeakerStatus.SKIPPED
            self.current_speaker = None
            if self.on_timeout:
                self.on_timeout(agent_name)
    
    def get_status(self) -> Dict:
        """Gibt aktuellen Status zurück"""
        return {
            "speakers": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "warnings": s.warnings,
                    "sanction": s.sanction.value if s.sanction else None,
                    "contributions": s.contributions
                }
                for s in self.speakers
            ],
            "current_speaker": self.current_speaker.name if self.current_speaker else None,
            "round_elapsed": time.time() - self.round_start_time if self.round_start_time else 0,
            "speaker_list_active": self.config["speaker_list"],
            "interruptions_allowed": self.config["interruptions"],
            "sanctions_active": self.config["sanctions"]
        }
    
    def get_statistics(self) -> Dict:
        """Gibt Statistiken zurück"""
        total_speaking_time = sum(s.speaking_time for s in self.speakers if isinstance(s.speaking_time, (int, float)))
        return {
            "total_contributions": sum(s.contributions for s in self.speakers),
            "total_speaking_time": total_speaking_time,
            "total_warnings": sum(s.warnings for s in self.speakers),
            "sanctioned_agents": [s.name for s in self.speakers if s.sanction],
            "skipped_agents": [s.name for s in self.speakers if s.status == SpeakerStatus.SKIPPED]
        }


# ==================== HILFS-FUNKTIONEN ====================

def detect_repetition(history: List[str], new_statement: str, threshold: float = 0.85) -> bool:
    """Erkennt ob eine Aussage bereits ähnlich gesagt wurde"""
    if not history:
        return False
    
    def similarity(a, b):
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)
    
    for old in history[-5:]:  # Letzte 5 prüfen
        if similarity(new_statement, old) > threshold:
            return True
    return False


def check_offensive_language(text: str) -> Tuple[bool, List[str]]:
    """Prüft auf offensive Sprache"""
    offensive_words = [
        "idiot", "dumm", "blöd", "scheiße", "arsch", "hurensohn", 
        "schlampe", "fick", "behindert", "spast", "nazi", "opfer"
    ]
    found = [w for w in offensive_words if w in text.lower()]
    return len(found) > 0, found


if __name__ == "__main__":
    # Test
    print("Debatten-Controller initialisiert")
    print("Verfügbare Sanktionen:")
    for s in SanctionType:
        print(f"  • {s.value}")