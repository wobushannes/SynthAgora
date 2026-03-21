#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Result Analyzer für SynthAgora
- Thesen-Extraktion
- Konsens-Messung
- Argument-Karte (Baumdiagramm)
- Sentiment-Analyse
- Wortwolken-Daten
- Themen-Clustering
"""

import re
import json
import math
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple, Set
from collections import Counter, defaultdict
import threading


class ResultAnalyzer:
    """Analysiert Diskussions-Ergebnisse"""
    
    def __init__(self, lm_client=None):
        self.lm = lm_client
        self._lock = threading.Lock()
    
    def extract_theses(self, contributions: List[Dict], min_confidence: float = 0.6) -> List[Dict]:
        """
        Extrahiert Thesen aus Diskussionsbeiträgen.
        
        Returns:
            [
                {
                    "thesis": str,
                    "proponents": [agent_names],
                    "opponents": [agent_names],
                    "supporting_arguments": [str],
                    "opposing_arguments": [str],
                    "confidence": float,
                    "mentions": int
                }
            ]
        """
        # Alle Beiträge sammeln
        all_text = " ".join([c.get("content", "") for c in contributions])
        
        # Nach Thesen-Markern suchen
        thesis_markers = [
            r"meiner Meinung nach (?:ist|sind|muss|sollte) ([^.!?]+)",
            r"ich (?:glaube|denke|finde), dass ([^.!?]+)",
            r"(?:die These|das Argument), dass ([^.!?]+)",
            r"(?:mein|unser) (?:Standpunkt|Position) (?:ist|sind): ([^.!?]+)",
            r"dafür spricht, dass ([^.!?]+)",
            r"dagegen spricht, dass ([^.!?]+)"
        ]
        
        theses = []
        for marker in thesis_markers:
            matches = re.findall(marker, all_text, re.IGNORECASE)
            for match in matches:
                thesis = match.strip()
                if len(thesis) > 10 and len(thesis) < 200:
                    theses.append({
                        "thesis": thesis,
                        "confidence": 0.7,
                        "mentions": 1
                    })
        
        # Duplikate zusammenfassen
        unique_theses = {}
        for t in theses:
            key = t["thesis"].lower()
            if key in unique_theses:
                unique_theses[key]["mentions"] += 1
            else:
                unique_theses[key] = t
        
        # Nach Agenten gruppieren (wer hat was gesagt)
        for thesis in unique_theses.values():
            thesis_text = thesis["thesis"].lower()
            proponents = []
            opponents = []
            
            for c in contributions:
                content = c.get("content", "").lower()
                agent = c.get("agent", c.get("agent_name", "Unbekannt"))
                
                if thesis_text in content:
                    # Prüfe ob Zustimmung oder Ablehnung
                    if any(word in content for word in ["stimme zu", "ja", "richtig", "genau", "wahr"]):
                        proponents.append(agent)
                    elif any(word in content for word in ["widerspreche", "nein", "falsch", "stimme nicht"]):
                        opponents.append(agent)
            
            thesis["proponents"] = list(set(proponents))
            thesis["opponents"] = list(set(opponents))
        
        # Confidence berechnen basierend auf Mentions
        for thesis in unique_theses.values():
            thesis["confidence"] = min(1.0, thesis["mentions"] / 10 + 0.3)
        
        # Nach Confidence filtern
        return [t for t in unique_theses.values() if t["confidence"] >= min_confidence]
    
    def measure_consensus(self, contributions: List[Dict], theses: List[Dict] = None) -> Dict:
        """
        Misst den Konsensgrad in der Diskussion.
        
        Returns:
            {
                "overall_consensus": float,  # 0-1
                "per_thesis": {thesis: consensus},
                "polarization": float,       # Polarisierungsgrad
                "agent_agreement": {agent: agreement_score}
            }
        """
        if theses is None:
            theses = self.extract_theses(contributions, min_confidence=0.5)
        
        # Gesamtkonsens über alle Thesen
        thesis_consensus = {}
        for thesis in theses:
            total = len(thesis["proponents"]) + len(thesis["opponents"])
            if total > 0:
                # Konsens = max(pro, opp) / total
                consensus = max(len(thesis["proponents"]), len(thesis["opponents"])) / total
            else:
                consensus = 0.5
            thesis_consensus[thesis["thesis"]] = consensus
        
        overall_consensus = sum(thesis_consensus.values()) / len(thesis_consensus) if thesis_consensus else 0.5
        
        # Polarisierung (Standardabweichung der Meinungen)
        sentiments = []
        for c in contributions:
            sentiment = self._analyze_sentiment_simple(c.get("content", ""))
            sentiments.append(sentiment)
        
        if sentiments:
            mean = sum(sentiments) / len(sentiments)
            variance = sum((s - mean) ** 2 for s in sentiments) / len(sentiments)
            polarization = math.sqrt(variance)  # Höher = mehr Polarisierung
        else:
            polarization = 0
        
        # Agent Agreement (wie oft stimmt ein Agent mit dem Konsens überein)
        agent_agreement = defaultdict(float)
        agent_count = defaultdict(int)
        
        for thesis in theses:
            consensus_side = "pro" if len(thesis["proponents"]) > len(thesis["opponents"]) else "contra"
            for agent in thesis["proponents"]:
                agent_agreement[agent] += 1 if consensus_side == "pro" else 0
                agent_count[agent] += 1
            for agent in thesis["opponents"]:
                agent_agreement[agent] += 1 if consensus_side == "contra" else 0
                agent_count[agent] += 1
        
        for agent in agent_agreement:
            if agent_count[agent] > 0:
                agent_agreement[agent] /= agent_count[agent]
        
        return {
            "overall_consensus": overall_consensus,
            "per_thesis": thesis_consensus,
            "polarization": polarization,
            "agent_agreement": dict(agent_agreement)
        }
    
    def build_argument_map(self, contributions: List[Dict], max_depth: int = 3) -> Dict:
        """
        Baut eine Argument-Karte (Baumdiagramm).
        
        Returns:
            {
                "root": {
                    "argument": "Hauptthese",
                    "supporting": [...],
                    "opposing": [...],
                    "agent": "Agent"
                }
            }
        """
        # Verbindungen zwischen Argumenten erkennen (wer antwortet wem)
        connections = []
        agents_by_name = {}
        
        for i, c in enumerate(contributions):
            agent = c.get("agent", c.get("agent_name", "Unbekannt"))
            agents_by_name[agent] = c
        
        # Reaktions-Beziehungen erkennen
        for i, c in enumerate(contributions):
            content = c.get("content", "")
            # Prüft ob auf vorherigen Beitrag reagiert wird
            for j in range(max(0, i-5), i):
                prev = contributions[j]
                prev_content = prev.get("content", "")
                if self._text_similarity(content, prev_content) > 0.3:
                    connections.append({
                        "from": j,
                        "to": i,
                        "type": "reaction"
                    })
                    break
        
        # Baum aufbauen
        root = {"argument": "Diskussion", "supporting": [], "opposing": [], "children": []}
        nodes = {i: {"argument": c.get("content", "")[:100], "agent": c.get("agent", ""), "children": []} 
                 for i, c in enumerate(contributions)}
        
        for conn in connections:
            from_node = nodes.get(conn["from"])
            to_node = nodes.get(conn["to"])
            if from_node and to_node:
                from_node["children"].append(to_node)
        
        return {
            "nodes": nodes,
            "connections": connections,
            "root": root
        }
    
    def analyze_sentiment_timeline(self, contributions: List[Dict]) -> Dict:
        """
        Analysiert Sentiment über die Zeit.
        
        Returns:
            {
                "timeline": [
                    {"round": 1, "sentiment": 0.2, "count": 5},
                    ...
                ],
                "overall_sentiment": float,
                "sentiment_trend": "rising"|"falling"|"stable"
            }
        """
        timeline = []
        current_round = 1
        round_sentiments = []
        
        for c in contributions:
            round_num = c.get("round_number", c.get("round", 1))
            if round_num != current_round:
                if round_sentiments:
                    timeline.append({
                        "round": current_round,
                        "sentiment": sum(round_sentiments) / len(round_sentiments),
                        "count": len(round_sentiments)
                    })
                current_round = round_num
                round_sentiments = []
            
            sentiment = self._analyze_sentiment_simple(c.get("content", ""))
            round_sentiments.append(sentiment)
        
        # Letzte Runde
        if round_sentiments:
            timeline.append({
                "round": current_round,
                "sentiment": sum(round_sentiments) / len(round_sentiments),
                "count": len(round_sentiments)
            })
        
        # Gesamt-Sentiment
        all_sentiments = [s for t in timeline for s in [t["sentiment"]] * t["count"]]
        overall = sum(all_sentiments) / len(all_sentiments) if all_sentiments else 0
        
        # Trend
        if len(timeline) >= 2:
            first = timeline[0]["sentiment"]
            last = timeline[-1]["sentiment"]
            if last > first + 0.1:
                trend = "rising"
            elif last < first - 0.1:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "timeline": timeline,
            "overall_sentiment": overall,
            "sentiment_trend": trend
        }
    
    def generate_wordcloud_data(self, contributions: List[Dict], top_n: int = 50) -> Dict:
        """
        Generiert Daten für eine Wortwolke.
        
        Returns:
            {
                "words": [{"word": str, "count": int, "weight": float}],
                "total_words": int,
                "unique_words": int
            }
        """
        # Stoppwörter (deutsch)
        stopwords = {
            "der", "die", "das", "und", "oder", "aber", "denn", "dass", "ist", "sind",
            "war", "wurde", "werden", "wird", "ich", "du", "er", "sie", "es", "wir",
            "ihr", "sie", "ein", "eine", "einer", "eines", "dem", "den", "des",
            "auch", "nicht", "nur", "schon", "noch", "mal", "wie", "was", "wann",
            "wo", "warum", "wieso", "weshalb", "also", "so", "dann", "da", "doch"
        }
        
        word_counts = Counter()
        
        for c in contributions:
            content = c.get("content", "").lower()
            # Entferne Satzzeichen
            words = re.findall(r'\b[a-zäöüß]{3,}\b', content)
            for word in words:
                if word not in stopwords and len(word) > 2:
                    word_counts[word] += 1
        
        # Top N
        top_words = word_counts.most_common(top_n)
        
        # Max count für Gewichtung
        max_count = top_words[0][1] if top_words else 1
        
        words_data = []
        for word, count in top_words:
            words_data.append({
                "word": word,
                "count": count,
                "weight": count / max_count  # 0-1
            })
        
        return {
            "words": words_data,
            "total_words": sum(word_counts.values()),
            "unique_words": len(word_counts)
        }
    
    def cluster_topics(self, contributions: List[Dict], num_clusters: int = 5) -> Dict:
        """
        Clustert Themen aus Diskussionsbeiträgen.
        
        Returns:
            {
                "clusters": [
                    {
                        "name": str,
                        "keywords": [str],
                        "contributions": [int],
                        "agents": [str]
                    }
                ]
            }
        """
        # Extrahiere Schlüsselwörter aus allen Beiträgen
        all_keywords = []
        contribution_keywords = []
        
        for c in contributions:
            content = c.get("content", "").lower()
            # Extrahiere Nomen-ähnliche Wörter (einfach)
            words = re.findall(r'\b[a-zäöüß]{4,}\b', content)
            keywords = [w for w in words if w not in {"diese", "dieser", "dieses", "jenes", "solche"}]
            all_keywords.extend(keywords)
            contribution_keywords.append(keywords)
        
        # Häufigste Keywords
        keyword_counts = Counter(all_keywords)
        top_keywords = [k for k, _ in keyword_counts.most_common(20)]
        
        # Einfaches Clustering basierend auf Keyword-Überschneidungen
        clusters = []
        used = set()
        
        for i, keywords in enumerate(contribution_keywords):
            if i in used:
                continue
            
            # Finde verwandte Beiträge
            cluster_keywords = set(keywords)
            cluster_indices = [i]
            used.add(i)
            
            for j, other_keywords in enumerate(contribution_keywords):
                if j in used:
                    continue
                
                # Überschneidung berechnen
                overlap = len(set(keywords) & set(other_keywords))
                if overlap >= 2:
                    cluster_indices.append(j)
                    used.add(j)
                    cluster_keywords.update(other_keywords)
            
            if cluster_indices:
                # Cluster-Name aus häufigsten Keywords
                top_cluster_keywords = Counter(cluster_keywords).most_common(3)
                name = " / ".join([k for k, _ in top_cluster_keywords[:2]])
                
                # Agenten in diesem Cluster
                agents = list(set(c.get("agent", "") for idx in cluster_indices 
                                   for c in [contributions[idx]] if c.get("agent")))
                
                clusters.append({
                    "name": name or "Sonstiges",
                    "keywords": [k for k, _ in top_cluster_keywords[:5]],
                    "contribution_indices": cluster_indices,
                    "agents": agents[:5],
                    "size": len(cluster_indices)
                })
        
        # Nach Größe sortieren
        clusters.sort(key=lambda x: x["size"], reverse=True)
        
        return {
            "clusters": clusters[:num_clusters],
            "total_clusters": len(clusters)
        }
    
    def generate_heatmap_data(self, contributions: List[Dict], agents: List[str]) -> Dict:
        """
        Generiert Heatmap-Daten (Agent vs. Thema).
        
        Returns:
            {
                "agents": [agent_names],
                "topics": [topic_names],
                "matrix": [[intensity]]
            }
        """
        # Themen aus Beiträgen extrahieren
        topics = []
        for c in contributions:
            content = c.get("content", "")
            # Einfache Themen-Extraktion
            topic_matches = re.findall(r'\b([A-Z][a-zäöüß]+(?: [A-Z][a-zäöüß]+)?)\b', content)
            topics.extend(topic_matches[:2])
        
        topic_counts = Counter(topics)
        main_topics = [t for t, _ in topic_counts.most_common(10)]
        
        # Matrix aufbauen
        matrix = []
        for agent in agents:
            row = []
            for topic in main_topics:
                # Zähle wie oft dieser Agent dieses Thema erwähnt hat
                count = 0
                for c in contributions:
                    if c.get("agent") == agent and topic.lower() in c.get("content", "").lower():
                        count += 1
                row.append(min(1.0, count / 3))  # Cap bei 1.0
            matrix.append(row)
        
        return {
            "agents": agents,
            "topics": main_topics,
            "matrix": matrix
        }
    
    def extract_key_quotes(self, contributions: List[Dict], top_n: int = 10) -> List[Dict]:
        """
        Extrahiert die wichtigsten Zitate.
        
        Returns:
            [
                {
                    "text": str,
                    "agent": str,
                    "round": int,
                    "importance": float,
                    "type": str  # thesis, insight, counter, etc.
                }
            ]
        """
        quotes = []
        
        for c in contributions:
            content = c.get("content", "")
            agent = c.get("agent", c.get("agent_name", "Unbekannt"))
            round_num = c.get("round_number", c.get("round", 1))
            
            # Bewertungskriterien
            importance = 0.5
            
            # Länge (längere Beiträge sind oft wichtiger)
            importance += min(0.2, len(content) / 500)
            
            # Fragezeichen (Fragen sind oft relevant)
            if "?" in content:
                importance += 0.1
            
            # Ausrufezeichen (starke Aussagen)
            if "!" in content:
                importance += 0.05
            
            # Schlüsselwörter für wichtige Aussagen
            important_keywords = ["wichtig", "entscheidend", "wesentlich", "kern", "zentral", "These"]
            for kw in important_keywords:
                if kw in content.lower():
                    importance += 0.1
                    break
            
            # Typ bestimmen
            quote_type = "statement"
            if "?" in content:
                quote_type = "question"
            elif "widerspreche" in content.lower() or "stimme nicht" in content.lower():
                quote_type = "counter"
            elif "stimme zu" in content.lower() or "ja," in content.lower():
                quote_type = "agreement"
            elif any(kw in content.lower() for kw in ["these", "meiner meinung nach", "ich glaube"]):
                quote_type = "thesis"
            elif any(kw in content.lower() for kw in ["überraschend", "interessant", "bemerkenswert"]):
                quote_type = "insight"
            
            quotes.append({
                "text": content[:300] + "..." if len(content) > 300 else content,
                "agent": agent,
                "round": round_num,
                "importance": min(1.0, importance),
                "type": quote_type
            })
        
        # Nach Wichtigkeit sortieren
        quotes.sort(key=lambda x: x["importance"], reverse=True)
        
        return quotes[:top_n]
    
    def generate_full_report(self, contributions: List[Dict], agents: List, topic: str) -> Dict:
        """
        Generiert einen vollständigen Analyse-Bericht.
        """
        theses = self.extract_theses(contributions)
        consensus = self.measure_consensus(contributions, theses)
        sentiment = self.analyze_sentiment_timeline(contributions)
        wordcloud = self.generate_wordcloud_data(contributions)
        clusters = self.cluster_topics(contributions)
        quotes = self.extract_key_quotes(contributions)
        
        return {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_contributions": len(contributions),
                "unique_agents": len(set(c.get("agent", "") for c in contributions)),
                "total_rounds": max(c.get("round_number", c.get("round", 1)) for c in contributions) if contributions else 0
            },
            "theses": theses,
            "consensus": consensus,
            "sentiment": sentiment,
            "wordcloud": wordcloud,
            "clusters": clusters,
            "key_quotes": quotes
        }
    
    def _analyze_sentiment_simple(self, text: str) -> float:
        """Einfache Sentiment-Analyse basierend auf Wortlisten"""
        positive_words = {"gut", "toll", "super", "richtig", "wichtig", "positiv", "hilfreich", 
                         "einverstanden", "zustimmung", "ja", "stimme zu", "genau", "sehr gut"}
        negative_words = {"schlecht", "falsch", "doof", "negativ", "problematisch", "schwierig",
                         "widerspreche", "nein", "stimme nicht", "falsch", "ungünstig"}
        
        text_lower = text.lower()
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            return 0.5
        
        return pos_count / total
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Einfache Ähnlichkeitsprüfung"""
        if not text1 or not text2:
            return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)


if __name__ == "__main__":
    # Test
    analyzer = ResultAnalyzer()
    print("ResultAnalyzer initialisiert")
    
    test_contributions = [
        {"agent": "Anna", "content": "Ich finde, dass die Schule besser werden muss. Das ist wichtig!", "round": 1},
        {"agent": "Bernd", "content": "Da stimme ich zu, die Digitalisierung ist entscheidend.", "round": 1},
        {"agent": "Clara", "content": "Ich widerspreche, zuerst müssen die Lehrer besser ausgebildet werden.", "round": 2}
    ]
    
    theses = analyzer.extract_theses(test_contributions)
    print(f"Gefundene Thesen: {len(theses)}")
    
    sentiment = analyzer.analyze_sentiment_timeline(test_contributions)
    print(f"Sentiment-Trend: {sentiment['sentiment_trend']}")