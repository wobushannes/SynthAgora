#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rollen-Pools für SynthAgora
- Zentrale Sammlung aller Rollen-Kategorien
- Einfach erweiterbar
- Kann später durch JSON ersetzt werden
"""
import random
from typing import List



# ==================== MEDIZIN & GESUNDHEIT ====================
MEDIZIN_ROLLEN = [
    "Arzt", "Ärztin", "Chirurg", "Orthopäde", "Kardiologe", "Neurologe", "Psychiater",
    "Anästhesist", "Radiologe", "Pathologe", "Dermatologe", "Urologe", "Gynäkologe",
    "Pädiater", "Geriatrie-Spezialist", "Notarzt", "Hausarzt", "Betriebsarzt",
    "Sportmediziner", "Rehabilitationsmediziner", "Palliativmediziner", "Intensivmediziner",
    "Krankenhausdirektor", "Chefarzt", "Oberarzt", "Assistenzarzt", "Praktikant",
    "Krankenschwester", "Gesundheits- und Krankenpfleger", "Altenpfleger", "Kinderkrankenschwester",
    "OP-Schwester", "Intensivpfleger", "Anästhesiepfleger", "Psychiatriepfleger",
    "Pflegedienstleiter", "Heilerziehungspfleger", "Hebamme", "Entbindungspfleger",
    "Physiotherapeut", "Ergotherapeut", "Logopäde", "Diätassistent", "Orthoptist",
    "Rettungssanitäter", "Notfallsanitäter", "Rettungsassistent", "Medizinischer Fachangestellter",
    "Arzthelfer", "Zahnarzt", "Zahnärztin", "Kieferorthopäde", "Zahntechniker",
    "Apotheker", "PTA", "Pharmazieingenieur", "Pharmakologe", "Medizintechniker",
    "Gesundheitsmanager", "Krankenhausmanager", "Qualitätsmanager im Gesundheitswesen",
    "Medizincontroller", "Case Manager", "Gesundheitscoach", "Präventionsberater",
    "Betrieblicher Gesundheitsmanager", "Gesundheitspsychologe", "Medizinjournalist"
]

# ==================== PSYCHOLOGIE & SOZIALES ====================
SOZIAL_ROLLEN = [
    "Psychologe", "Klinischer Psychologe", "Psychotherapeut", "Verhaltenstherapeut",
    "Tiefenpsychologe", "Kinder- und Jugendpsychotherapeut", "Familientherapeut",
    "Paartherapeut", "Traumatherapeut", "Suchttherapeut", "Rehabilitationstherapeut",
    "Neuropsychologe", "Gesundheitspsychologe", "Arbeitspsychologe", "Organisationspsychologe",
    "Marktpsychologe", "Medienpsychologe", "Verkehrspsychologe", "Rechtspsychologe",
    "Schulpsychologe", "Sozialarbeiter", "Sozialpädagoge", "Sozialassistent", "Erzieher",
    "Kindheitspädagoge", "Heilerziehungspfleger", "Jugendamt-Mitarbeiter", "Betreuer",
    "Integrationshelfer", "Streetworker", "Schuldnerberater", "Lebensberater", "Seelsorger",
    "Trauerbegleiter", "Mediator", "Konfliktberater", "Elternberater", "Erziehungsberater"
]

# ==================== BILDUNG & PÄDAGOGIK ====================
BILDUNG_ROLLEN = [
    "Lehrer", "Lehrerin", "Grundschullehrer", "Hauptschullehrer", "Realschullehrer",
    "Gymnasiallehrer", "Berufsschullehrer", "Förderschullehrer", "Schulleiter", "Konrektor",
    "Fachbereichsleiter", "Schulsozialarbeiter", "Schulpsychologe", "Vertretungslehrer",
    "Referendar", "Hochschulprofessor", "Universitätsdozent", "Fachhochschulprofessor",
    "Wissenschaftlicher Mitarbeiter", "Dekan", "Studiendekan", "Präsident einer Hochschule",
    "Erwachsenenbildner", "Volkshochschuldozent", "Trainer", "Ausbilder", "Berufsberater",
    "Nachhilfelehrer", "Sprachlehrer", "Musiklehrer", "Kunstlehrer", "Sportlehrer",
    "Förderpädagoge", "Sonderpädagoge", "Inklusionspädagoge", "Heilpädagoge"
]

# ==================== JURA & RECHT ====================
JURA_ROLLEN = [
    "Anwalt", "Anwältin", "Rechtsanwalt", "Fachanwalt für Arbeitsrecht", "Fachanwalt für Familienrecht",
    "Fachanwalt für Strafrecht", "Fachanwalt für Verkehrsrecht", "Fachanwalt für Medizinrecht",
    "Fachanwalt für IT-Recht", "Fachanwalt für Mietrecht", "Richter", "Richterin", "Staatsanwalt",
    "Staatsanwältin", "Rechtspfleger", "Notar", "Justiziar", "Syndikusrechtsanwalt", "Jurist",
    "Rechtswissenschaftler", "Rechtsreferendar", "Wirtschaftsjurist", "Compliance Officer",
    "Datenschutzbeauftragter", "Geschäftsführer Recht", "Rechtsabteilungsleiter", "Patentanwalt"
]

# ==================== WIRTSCHAFT & MANAGEMENT ====================
WIRTSCHAFT_ROLLEN = [
    "Unternehmer", "Geschäftsführer", "CEO", "Vorstandsvorsitzender", "CFO", "COO", "CTO",
    "Marketingmanager", "Vertriebsleiter", "Produktmanager", "Projektmanager", "Teamleiter",
    "Abteilungsleiter", "Bereichsleiter", "Betriebsleiter", "Filialleiter", "Gründer",
    "Startup-Gründer", "Serial Entrepreneur", "Investor", "Business Angel", "Venture Capitalist",
    "Fondsmanager", "Portfoliomanager", "Investmentbanker", "Financial Advisor", "Steuerberater",
    "Wirtschaftsprüfer", "Bilanzbuchhalter", "Controller", "Finanzanalyst", "Unternehmensberater",
    "Strategieberater", "Change Manager", "Organisationsentwickler", "Personalmanager", "HR Director"
]

# ==================== TECHNOLOGIE & IT ====================
TECH_ROLLEN = [
    "Softwareentwickler", "Programmierer", "Full-Stack-Entwickler", "Frontend-Entwickler", "Backend-Entwickler",
    "DevOps Engineer", "Systemadministrator", "Datenbankadministrator", "Cloud-Architekt", "Solution Architect",
    "IT-Sicherheitsexperte", "Ethical Hacker", "Penetrationstester", "Security Analyst", "CISO",
    "Data Scientist", "Machine Learning Engineer", "KI-Forscher", "AI-Spezialist", "Prompt Engineer",
    "Agile Coach", "Scrum Master", "Product Owner", "Tech Lead", "IT-Projektleiter", "IT-Consultant",
    "Webentwickler", "App-Entwickler", "Game Developer", "Embedded Systems Engineer", "Hardwareentwickler",
    "Netzwerkadministrator", "Support-Mitarbeiter", "Helpdesk", "IT-Trainer", "Digitalisierungsberater"
]

# ==================== KUNST & KULTUR ====================
KUNST_ROLLEN = [
    "Maler", "Bildhauer", "Fotograf", "Grafikdesigner", "Illustrator", "Kunsttherapeut", "Kunsthistoriker",
    "Kurator", "Galerist", "Kunstkritiker", "Museumsdirektor", "Restaurator", "Schauspieler", "Schauspielerin",
    "Theaterregisseur", "Bühnenbildner", "Dramaturg", "Intendant", "Musiker", "Sänger", "Gitarrist",
    "Pianist", "Dirigent", "Komponist", "Musikproduzent", "Tontechniker", "Tänzer", "Choreograf",
    "Autor", "Schriftsteller", "Dichter", "Journalist", "Redakteur", "Blogger", "Influencer", "Content Creator"
]

# ==================== HANDWERK & TECHNIK ====================
HANDWERK_ROLLEN = [
    "Elektriker", "Elektrotechnikermeister", "Installateur", "Heizungsbauer", "Klempner", "Maurer",
    "Zimmermann", "Dachdecker", "Maler", "Lackierer", "Stuckateur", "Fliesenleger", "Fensterbauer",
    "Schreiner", "Tischler", "Holzbildhauer", "Metallbauer", "Schweißer", "Schlosser", "Industriemechaniker",
    "Mechatroniker", "Kfz-Mechaniker", "Kfz-Elektriker", "Karosseriebauer", "Lackierer", "Bäcker",
    "Konditor", "Metzger", "Koch", "Küchenchef", "Gastronom", "Hotelier", "Hotelfachmann", "Reiseverkehrskaufmann"
]

# ==================== LANDWIRTSCHAFT & NATUR ====================
LANDWIRT_ROLLEN = [
    "Landwirt", "Bauer", "Biobauer", "Winzer", "Weinbauer", "Gärtner", "Landschaftsgärtner",
    "Friedhofsgärtner", "Forstwirt", "Förster", "Jäger", "Fischer", "Imker", "Tierarzt",
    "Tierärztin", "Veterinär", "Pferdewirt", "Hundetrainer", "Tierpfleger", "Zoodirektor",
    "Tierheimleiter", "Naturschützer", "Umweltaktivist", "Klimaforscher", "Meeresbiologe"
]

# ==================== POLITIK & ÖFFENTLICHER DIENST ====================
POLITIK_ROLLEN = [
    "Politiker", "Bundestagsabgeordneter", "Landtagsabgeordneter", "Stadtrat", "Bürgermeister",
    "Oberbürgermeister", "Landrat", "Minister", "Staatssekretär", "Bundeskanzler", "Präsident",
    "Botschafter", "Diplomat", "Beamter", "Verwaltungsangestellter", "Sachbearbeiter", "Amtsleiter",
    "Behördenleiter", "Polizist", "Kriminalpolizist", "Kommissar", "Ermittler", "Kriminaldirektor",
    "Zollbeamter", "Finanzbeamter", "Steuerfahnder", "Brandmeister", "Feuerwehrmann", "Katastrophenschützer"
]

# ==================== SPORT & BEWEGUNG ====================
SPORT_ROLLEN = [
    "Sportler", "Leistungssportler", "Profisportler", "Fußballspieler", "Trainer", "Fußballtrainer",
    "Athletiktrainer", "Konditionstrainer", "Physiotherapeut", "Sportmediziner", "Sportjournalist",
    "Sportkommentator", "Schiedsrichter", "Turnierleiter", "Vereinsmanager", "Sportdirektor",
    "Sportfunktionär", "Yogalehrer", "Fitnesscoach", "Personal Trainer", "Kampfsportler", "Boxer",
    "Schwimmer", "Leichtathlet", "Skifahrer", "Snowboarder", "Tennisspieler", "Golfer", "Reiter"
]

# ==================== MEDIEN & KOMMUNIKATION ====================
MEDIEN_ROLLEN = [
    "Journalist", "Redakteur", "Chefredakteur", "Reporter", "Korrespondent", "Nachrichtensprecher",
    "Moderator", "TV-Moderator", "Radio-Moderator", "Podcaster", "Medienmanager", "PR-Berater",
    "Pressesprecher", "Kommunikationsberater", "Social Media Manager", "Content-Manager", "Texter",
    "Werbetexter", "Kreativdirektor", "Art Director", "Medienwissenschaftler", "Filmregisseur",
    "Filmeditor", "Kameramann", "Lichttechniker", "Set-Designer", "Maskenbildner", "Stuntman"
]

# ==================== FORSCHUNG & WISSENSCHAFT ====================
FORSCHUNG_ROLLEN = [
    "Forscher", "Wissenschaftler", "Physiker", "Chemiker", "Biologe", "Mathematiker", "Informatiker",
    "Astronom", "Geologe", "Meteorologe", "Ozeanograph", "Paläontologe", "Archäologe", "Historiker",
    "Philosoph", "Soziologe", "Ethnologe", "Linguist", "Philologe", "Literaturwissenschaftler",
    "Kunsthistoriker", "Theologe", "Religionswissenschaftler", "Politologe", "Volkswirt", "Ökonom",
    "Statistiker", "Demograf", "Epidemiologe", "Genetiker", "Neurowissenschaftler", "Kognitionswissenschaftler"
]

# ==================== FAMILIE & ALLTAG ====================
FAMILIE_ROLLEN = [
    "Mutter", "Vater", "Großmutter", "Großvater", "Alleinerziehende Mutter", "Alleinerziehender Vater",
    "Hausfrau", "Hausmann", "Elternteil", "Patchwork-Mutter", "Patchwork-Vater", "Stiefmutter",
    "Stiefvater", "Pflegemutter", "Pflegevater", "Adoptivmutter", "Adoptivvater", "Tagesmutter",
    "Tagesvater", "Nachbar", "Nachbarin", "Hausmeister", "Vermieter", "Mieter", "Bürger", "Rentner"
]

# ==================== KREATIVE BERUFE ====================
KREATIVE_ROLLEN = [
    "Designer", "Modedesigner", "Innenarchitekt", "Architekt", "Stadtplaner", "Landschaftsarchitekt",
    "Spieleentwickler", "Game Designer", "UI Designer", "UX Designer", "Produktdesigner", "Industriedesigner",
    "Schmuckdesigner", "Keramiker", "Glaskünstler", "Textilkünstler", "Performancekünstler", "Tanzkünstler",
    "Zirkusartist", "Clown", "Magier", "Illusionist", "Feuerkünstler", "Streetart-Künstler", "Graffiti-Künstler"
]

# ==================== HANDEL & DIENSTLEISTUNG ====================
HANDEL_ROLLEN = [
    "Verkäufer", "Kaufmann", "Kauffrau", "Einzelhandelskaufmann", "Großhandelskaufmann", "Marktleiter",
    "Filialleiter", "Einkäufer", "Vertriebler", "Außendienstmitarbeiter", "Handelsvertreter", "Key Account Manager",
    "Kundenservice-Mitarbeiter", "Callcenter-Agent", "Rezeptionist", "Empfangschef", "Concierge", "Portier",
    "Friseur", "Kosmetiker", "Nageldesigner", "Make-up-Artist", "Wellnessberater", "Spa-Manager"
]

# ==================== ALLE ROLLEN KOMBINIERT ====================
ALL_ROLLEN = (
    MEDIZIN_ROLLEN + SOZIAL_ROLLEN + BILDUNG_ROLLEN + JURA_ROLLEN + 
    WIRTSCHAFT_ROLLEN + TECH_ROLLEN + KUNST_ROLLEN + HANDWERK_ROLLEN + 
    LANDWIRT_ROLLEN + POLITIK_ROLLEN + SPORT_ROLLEN + MEDIEN_ROLLEN + 
    FORSCHUNG_ROLLEN + FAMILIE_ROLLEN + KREATIVE_ROLLEN + HANDEL_ROLLEN
)

# ==================== ROLLEN-NACH-KATEGORIE (für gezielte Generierung) ====================
ROLE_CATEGORIES = {
    "medizin": MEDIZIN_ROLLEN,
    "sozial": SOZIAL_ROLLEN,
    "bildung": BILDUNG_ROLLEN,
    "justiz": JURA_ROLLEN,
    "wirtschaft": WIRTSCHAFT_ROLLEN,
    "technologie": TECH_ROLLEN,
    "kunst": KUNST_ROLLEN,
    "handwerk": HANDWERK_ROLLEN,
    "landwirtschaft": LANDWIRT_ROLLEN,
    "politik": POLITIK_ROLLEN,
    "sport": SPORT_ROLLEN,
    "medien": MEDIEN_ROLLEN,
    "forschung": FORSCHUNG_ROLLEN,
    "familie": FAMILIE_ROLLEN,
    "kreativ": KREATIVE_ROLLEN,
    "handel": HANDEL_ROLLEN
}

# ==================== HILFSFUNKTIONEN ====================
def get_random_role(category: str = None) -> str:
    """Gibt eine zufällige Rolle zurück"""
    if category and category in ROLE_CATEGORIES:
        return random.choice(ROLE_CATEGORIES[category])
    return random.choice(ALL_ROLLEN)

def get_roles_by_category(category: str) -> List[str]:
    """Gibt alle Rollen einer Kategorie zurück"""
    return ROLE_CATEGORIES.get(category, [])

def get_all_categories() -> List[str]:
    """Gibt alle Kategorien zurück"""
    return list(ROLE_CATEGORIES.keys())