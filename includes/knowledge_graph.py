#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Knowledge Graph mit SQLite-Backend für SynthAgora
"""

import json
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
import os

from .database import SynthAgoraDB
from .config import Config


class KnowledgeGraph:
    """Knowledge Graph mit SQLite-Backend"""
    
    def __init__(self):
        self.db = SynthAgoraDB()
        print(f"🔮 Knowledge Graph initialisiert")
    
    # ==================== KNOTEN ====================
    
    def add_node(self, node_id: str, node_type: str, properties: dict):
        self.db.add_node(node_id, node_type, properties)
    
    def get_node(self, node_id: str) -> Optional[dict]:
        return self.db.get_node(node_id)
    
    def get_node_count(self) -> int:
        return self.db.get_node_count()
    
    # ==================== KANTEN ====================
    
    def add_edge(self, from_node: str, to_node: str, relation: str, strength: float = 1.0):
        return self.db.add_edge(from_node, to_node, relation, strength)
    
    def get_edges(self, from_node: Optional[str] = None, to_node: Optional[str] = None,
                  relation: Optional[str] = None, limit: int = 1000) -> List[dict]:
        return self.db.get_edges(from_node, to_node, relation, 0.0, limit)
    
    def get_edge_count(self) -> int:
        return self.db.get_edge_count()
    
    def get_node_connections(self, node_id: str) -> Dict:
        return self.db.get_node_connections(node_id)
    
    # ==================== EINFLÜSSE ====================
    
    def add_influence(self, influencer: str, influenced: str, topic: str, strength: float):
        influencer_id = f"agent_{influencer.lower().replace(' ', '_')}"
        influenced_id = f"agent_{influenced.lower().replace(' ', '_')}"
        topic_id = f"topic_{topic.lower().replace(' ', '_')[:30]}"
        
        self.db.add_node(influencer_id, "agent", {"name": influencer})
        self.db.add_node(influenced_id, "agent", {"name": influenced})
        self.db.add_node(topic_id, "topic", {"name": topic})
        self.db.add_topic(topic_id, topic)
        self.db.add_node_to_topic(topic_id, influencer_id)
        self.db.add_node_to_topic(topic_id, influenced_id)
        self.db.add_edge(influencer_id, influenced_id, "beeinflusst", strength)
        self.db.add_influence(influencer_id, influenced_id, topic_id, strength)
    
    def get_influences(self, agent_name: str) -> dict:
        agent_id = f"agent_{agent_name.lower().replace(' ', '_')}"
        return self.db.get_influences(agent_id)
    
    def get_influence_network(self, min_strength: float = 0.3) -> Dict:
        return self.db.get_influence_network(min_strength)
    
    # ==================== THEMEN ====================
    
    def add_to_topic(self, topic: str, node_id: str):
        topic_id = f"topic_{topic.lower().replace(' ', '_')[:30]}"
        self.db.add_topic(topic_id, topic)
        self.db.add_node_to_topic(topic_id, node_id)
    
    def get_topic_nodes(self, topic: str) -> List[str]:
        topic_id = f"topic_{topic.lower().replace(' ', '_')[:30]}"
        return self.db.get_topic_nodes(topic_id)
    
    def get_all_topics(self) -> List[Dict]:
        topics = self.db.get_all_topics()
        for topic in topics:
            topic_id = topic.get('topic_id')
            if topic_id:
                nodes = self.db.get_topic_nodes(topic_id)
                topic['node_count'] = len(nodes)
        return topics
    
    def get_topic_count(self) -> int:
        return len(self.db.get_all_topics())
    
    # ==================== TEAMS ====================
    
    def add_team(self, team_name: str, agent_ids: List[str]):
        team_id = f"team_{team_name.lower().replace(' ', '_')}"
        self.db.add_team(team_id, team_name)
        self.add_node(team_id, "team", {"name": team_name})
        for agent_id in agent_ids:
            self.db.add_team_member(team_id, agent_id)
            self.add_edge(agent_id, team_id, "mitglied_in", 1.0)
    
    def get_team(self, team_name: str) -> Optional[Dict]:
        team_id = f"team_{team_name.lower().replace(' ', '_')}"
        return self.db.get_team(team_id)
    
    def get_all_teams(self) -> List[Dict]:
        return self.db.get_all_teams()
    
    # ==================== PUNKTE ====================
    
    def add_score(self, agent_name: str, points: int, reason: str):
        agent_id = f"agent_{agent_name.lower().replace(' ', '_')}"
        self.db.add_score(agent_id, points, reason)
    
    def get_leaderboard(self, limit: int = 10) -> List[Tuple[str, int]]:
        return self.db.get_leaderboard(limit)
    
    def get_agent_scores(self, agent_name: str) -> List[Dict]:
        agent_id = f"agent_{agent_name.lower().replace(' ', '_')}"
        return self.db.get_agent_score_history(agent_id)
    
    # ==================== PROGNOSEN ====================
    
    def add_prognosis(self, prognosis):
        agent_id = f"agent_{prognosis.agent.lower().replace(' ', '_')}"
        return self.db.add_prognosis(agent_id, prognosis.topic, prognosis.prediction, prognosis.confidence)
    
    def get_agent_prognoses(self, agent_name: str) -> List[dict]:
        agent_id = f"agent_{agent_name.lower().replace(' ', '_')}"
        return self.db.get_agent_prognoses(agent_id)
    
    def get_prognosis_stats(self, agent_name: Optional[str] = None) -> Dict:
        """Prognose-Statistiken - mit oder ohne Agent"""
        if agent_name:
            agent_id = f"agent_{agent_name.lower().replace(' ', '_')}"
            return self.db.get_prognosis_stats(agent_id)
        return self.db.get_prognosis_stats()  # Kein Agent → alle Statistiken
    
    # ==================== GEDÄCHTNIS ====================
    
    def add_memory_crystal(self, agent_id: str, fact: str, topic: str, importance: float = 0.5):
        crystal_id = f"crystal_{int(time.time())}_{random.randint(1000, 9999)}"
        room = self.db.get_memory_room(agent_id)
        if not room:
            room_id = f"room_{agent_id}"
            agent = self.db.get_agent(agent_id)
            agent_name = agent["name"] if agent else "Unbekannt"
            self.db.create_memory_room(room_id, agent_id, f"{agent_name}s Gedächtnis-Palast")
            room = self.db.get_memory_room(agent_id)
        
        if room:
            return self.db.add_memory_crystal(crystal_id, room['room_id'], fact, topic, importance)
        return False
    
    def get_agent_memories(self, agent_id: str) -> List[Dict]:
        return self.db.get_agent_memories(agent_id)
    
    def search_memories(self, agent_id: str, query: str) -> List[Dict]:
        return self.db.search_memories(agent_id, query)
    
    # ==================== STATISTIK ====================
    
    def get_stats(self) -> dict:
        stats = self.db.get_stats()
        stats['topics'] = self.get_topic_count()
        return stats
    
    # ==================== SUCHE ====================
    
    def search_nodes(self, query: str, node_type: Optional[str] = None, limit: int = 50) -> List[dict]:
        return self.db.search_nodes(query, node_type, limit)
    
    def find_related(self, node_id: str, relation: Optional[str] = None, max_depth: int = 2) -> List[dict]:
        return self.db.get_node_connections(node_id)
    
    # ==================== EXPORT / IMPORT ====================
    
    def export_to_json(self, filepath: str = None) -> str:
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(Config.EXPORTS_FOLDER, f"knowledge_graph_{timestamp}.json")
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        nodes = self.db.get_nodes_by_type("agent", 10000)
        edges = self.get_edges()
        topics = self.get_all_topics()
        teams = self.get_all_teams()
        stats = self.get_stats()
        
        export_data = {
            "nodes": {n['node_id']: n for n in nodes},
            "edges": edges,
            "topics": topics,
            "teams": teams,
            "stats": stats,
            "exported_at": datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Knowledge Graph exportiert: {filepath}")
        return filepath
    
    def import_from_json(self, filepath: str) -> bool:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for node_id, node_data in data.get("nodes", {}).items():
                props = node_data.get("properties", {})
                if isinstance(props, dict):
                    props = json.dumps(props)
                self.add_node(node_id, node_data.get("type", "unknown"), props)
            
            for edge_data in data.get("edges", []):
                self.add_edge(edge_data["from"], edge_data["to"], edge_data["relation"], edge_data.get("strength", 1.0))
            
            return True
        except Exception as e:
            print(f"❌ Import fehlgeschlagen: {e}")
            return False
    
    def __str__(self) -> str:
        stats = self.get_stats()
        return f"KnowledgeGraph(nodes={stats['kg_nodes']}, edges={stats['kg_edges']}, topics={stats['topics']})"