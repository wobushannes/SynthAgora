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
    MUTE = "mute"
    POINT_DEDUCTION = "point_deduction"
    EXPULSION = "expulsion"


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
        self.agents = agents
        self.config = {
            "time_per_round": 0,
            "thinking_time": 10,
            "speaker_list": False,
            "interruptions": False,
            "sanctions": False,
            "max_warnings": 3,
            "mute_rounds": 2,
            "repetition_threshold": 2,
            **(config or {})
        }
        
        self.speakers: List[Speaker] = []
        self.current_speaker: Optional[Speaker] = None
        self.speaker_index = 0
        
        self.round_start_time: Optional[float] = None
        self.speaker_start_time: Optional[float] = None
        self.timer_thread: Optional[threading.Thread] = None
        self.stop_timer = threading.Event()
        
        self.agent_history: Dict[str, List[str]] = {}
        self.agent_repetitions: Dict[str, int] = {}
        
        self.on_timeout: Optional[Callable] = None
        self.on_interruption: Optional[Callable] = None
        self.on_sanction: Optional[Callable] = None
        
        self._init_speakers()
    
    def _init_speakers(self):
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
        self.round_start_time = time.time()
        
        for speaker in self.speakers:
            if speaker.sanction_until_round <= round_num:
                speaker.sanction = None
                speaker.sanction_until_round = 0
                if speaker.status == SpeakerStatus.SANCTIONED:
                    speaker.status = SpeakerStatus.WAITING
        
        if self.config["speaker_list"]:
            self.speaker_index = 0
            self._update_speaker_order()
    
    def _update_speaker_order(self):
        active = [s for s in self.speakers if s.status not in [SpeakerStatus.SANCTIONED, SpeakerStatus.FINISHED]]
        sanctioned = [s for s in self.speakers if s.status == SpeakerStatus.SANCTIONED]
        
        active.sort(key=lambda s: s.position)
        sanctioned.sort(key=lambda s: s.position)
        
        self.speakers = active + sanctioned
        for i, s in enumerate(self.speakers):
            s.position = i
    
    def can_speak(self, agent_name: str, round_num: int) -> Tuple[bool, str]:
        speaker = self._get_speaker(agent_name)
        if not speaker:
            return False, "Agent nicht in Rednerliste"
        
        if speaker.sanction:
            return False, f"Sanktioniert: {speaker.sanction.value}"
        
        if speaker.status == SpeakerStatus.FINISHED:
            return False, "Bereits gesprochen in dieser Runde"
        
        if self.config["speaker_list"] and self.current_speaker:
            if agent_name != self.current_speaker.name:
                return False, f"Rednerliste: {self.current_speaker.name} ist an der Reihe"
        
        if self.config["time_per_round"] > 0:
            elapsed = time.time() - self.round_start_time
            if elapsed >= self.config["time_per_round"]:
                return False, "Rundenzeit abgelaufen"
        
        return True, ""
    
    def start_speaking(self, agent_name: str) -> bool:
        speaker = self._get_speaker(agent_name)
        if not speaker:
            return False
        
        speaker.status = SpeakerStatus.SPEAKING
        speaker.speaking_time = time.time()
        self.current_speaker = speaker
        
        if self.config["thinking_time"] > 0:
            self._start_timer(self.config["thinking_time"], 
                              lambda: self._timeout_speaker(agent_name))
        
        return True
    
    def finish_speaking(self, agent_name: str, statement: str):
        speaker = self._get_speaker(agent_name)
        if not speaker:
            return
        
        if speaker.speaking_time:
            duration = time.time() - speaker.speaking_time
            speaker.speaking_time = duration
        
        speaker.status = SpeakerStatus.FINISHED
        speaker.contributions += 1
        self.current_speaker = None
        self.stop_timer.set()
        
        self._check_repetition(agent_name, statement)
        
        if self.config["speaker_list"]:
            self._next_speaker()
    
    def _next_speaker(self):
        self.speaker_index += 1
        if self.speaker_index < len(self.speakers):
            next_speaker = self.speakers[self.speaker_index]
            if next_speaker.status == SpeakerStatus.WAITING:
                if self.on_timeout:
                    self.on_timeout(next_speaker.name)
    
    def interrupt(self, interrupter: str, target: str) -> Tuple[bool, str]:
        if not self.config["interruptions"]:
            return False, "Unterbrechungen nicht erlaubt"
        
        target_speaker = self._get_speaker(target)
        if not target_speaker or target_speaker.status != SpeakerStatus.SPEAKING:
            return False, "Ziel spricht nicht"
        
        interrupter_speaker = self._get_speaker(interrupter)
        if not interrupter_speaker:
            return False, "Unterbrecher nicht in Rednerliste"
        
        target_speaker.status = SpeakerStatus.INTERRUPTED
        
        interrupter_speaker.status = SpeakerStatus.SPEAKING
        interrupter_speaker.speaking_time = time.time()
        self.current_speaker = interrupter_speaker
        
        if self.on_interruption:
            self.on_interruption(interrupter, target)
        
        return True, f"{interrupter} unterbricht {target}"
    
    def sanction(self, agent_name: str, reason: str, sanction_type: SanctionType = SanctionType.WARNING) -> bool:
        if not self.config["sanctions"]:
            return False
        
        speaker = self._get_speaker(agent_name)
        if not speaker:
            return False
        
        if sanction_type == SanctionType.WARNING:
            speaker.warnings += 1
            if speaker.warnings >= self.config["max_warnings"]:
                return self.sanction(agent_name, f"Zu viele Verwarnungen ({speaker.warnings})", 
                                     SanctionType.MUTE)
        
        elif sanction_type == SanctionType.MUTE:
            speaker.sanction = SanctionType.MUTE
            speaker.sanction_until_round = self.config["mute_rounds"]
            speaker.status = SpeakerStatus.SANCTIONED
        
        elif sanction_type == SanctionType.POINT_DEDUCTION:
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
        history = self.agent_history[agent_name]
        
        if statement in history:
            self.agent_repetitions[agent_name] += 1
            if self.agent_repetitions[agent_name] >= self.config["repetition_threshold"]:
                self.sanction(agent_name, f"Wiederholung ({self.agent_repetitions[agent_name]}x)", 
                             SanctionType.WARNING)
        else:
            self.agent_repetitions[agent_name] = 0
        
        for past in history[-3:]:
            if self._text_similarity(statement, past) > 0.8:
                self.sanction(agent_name, "Zu ähnliche Aussage", SanctionType.WARNING)
                break
        
        history.append(statement)
        if len(history) > 20:
            history.pop(0)
        self.agent_history[agent_name] = history
    
    def _text_similarity(self, text1: str, text2: str) -> float:
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
        def timer_func():
            if self.stop_timer.wait(seconds):
                return
            callback()
        
        self.stop_timer.clear()
        self.timer_thread = threading.Thread(target=timer_func, daemon=True)
        self.timer_thread.start()
    
    def _timeout_speaker(self, agent_name: str):
        speaker = self._get_speaker(agent_name)
        if speaker and speaker.status == SpeakerStatus.SPEAKING:
            speaker.status = SpeakerStatus.SKIPPED
            self.current_speaker = None
            if self.on_timeout:
                self.on_timeout(agent_name)
    
    def get_status(self) -> Dict:
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
        total_speaking_time = sum(s.speaking_time for s in self.speakers if isinstance(s.speaking_time, (int, float)))
        return {
            "total_contributions": sum(s.contributions for s in self.speakers),
            "total_speaking_time": total_speaking_time,
            "total_warnings": sum(s.warnings for s in self.speakers),
            "sanctioned_agents": [s.name for s in self.speakers if s.sanction],
            "skipped_agents": [s.name for s in self.speakers if s.status == SpeakerStatus.SKIPPED]
        }


def detect_repetition(history: List[str], new_statement: str, threshold: float = 0.85) -> bool:
    if not history:
        return False
    
    def similarity(a, b):
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)
    
    for old in history[-5:]:
        if similarity(new_statement, old) > threshold:
            return True
    return False


def check_offensive_language(text: str) -> Tuple[bool, List[str]]:
    offensive_words = [
        "idiot", "dumm", "blöd", "scheiße", "arsch", "hurensohn", 
        "schlampe", "fick", "behindert", "spast", "nazi", "opfer"
    ]
    found = [w for w in offensive_words if w in text.lower()]
    return len(found) > 0, found


if __name__ == "__main__":
    print("Debatten-Controller initialisiert")
    print("Verfügbare Sanktionen:")
    for s in SanctionType:
        print(f"  • {s.value}")