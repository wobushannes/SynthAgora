#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prognosis-Klasse für SynthAgora
- Ausgelagert aus main.py
- Vermeidet Zirkelimporte
"""

from datetime import datetime
from typing import Dict

class Prognosis:
    """Eine Vorhersage, die ein Agent gemacht hat"""
    
    def __init__(self, agent: str, topic: str, prediction: str, confidence: float):
        self.agent = agent
        self.topic = topic
        self.prediction = prediction
        self.confidence = confidence
        self.timestamp = datetime.now().isoformat()
        self.verified = False
        self.correct = None
        self.verification_time = None
    
    def verify(self, actual_outcome: str) -> bool:
        """Überprüft ob die Prognose richtig war"""
        self.verified = True
        self.verification_time = datetime.now().isoformat()
        
        # Einfache Prüfung: Schlüsselwörter
        self.correct = any(word in actual_outcome.lower() 
                          for word in self.prediction.lower().split()[:3])
        return self.correct
    
    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "topic": self.topic,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "verified": self.verified,
            "correct": self.correct,
            "verification_time": self.verification_time
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        prog = cls(data["agent"], data["topic"], data["prediction"], data["confidence"])
        prog.timestamp = data["timestamp"]
        prog.verified = data["verified"]
        prog.correct = data["correct"]
        prog.verification_time = data["verification_time"]
        return prog