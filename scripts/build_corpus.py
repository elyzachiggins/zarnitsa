"""Build corpus entries from raw extracted source texts.

Run from the repo root:
    python scripts/build_corpus.py

Reads raw text files from data/corpus/raw/ and writes structured markdown
corpus entries to data/corpus/snapshots/2026-05/.

Each entry becomes a citable grounding document that the persona retriever
can inject into council prompts.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

RAW = Path("data/corpus/raw")
SNAPSHOT = Path("data/corpus/snapshots/2026-05")
SNAPSHOT.mkdir(parents=True, exist_ok=True)


def load_raw(filename: str) -> str:
    p = RAW / filename
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write_entry(
    filename: str,
    id: str,
    title: str,
    tier: str,
    source_date: str,
    keywords: list[str],
    topics: list[str],
    content: str,
    cited_by: list[str] | None = None,
) -> None:
    kw_str = ", ".join(f'"{k}"' for k in keywords)
    topic_str = ", ".join(f'"{t}"' for t in topics)
    cited_str = ""
    if cited_by:
        cited_str = "\ncited_by_personas: [" + ", ".join(f'"{c}"' for c in cited_by) + "]"
    header = f"""---
id: {id}
title: "{title}"
tier: {tier}
source_date: "{source_date}"
keywords: [{kw_str}]
topics: [{topic_str}]{cited_str}
---

"""
    (SNAPSHOT / filename).write_text(header + content.strip() + "\n", encoding="utf-8")
    print(f"  wrote {filename}")


# ─── Load source texts ────────────────────────────────────────────────────────

grounding = load_raw("GROUNDING_for_RRTA.txt")
gerasimov = load_raw("Cennost_nauki_v_predvidenii_-K.txt")
svo_causes = load_raw("osnovnye-prichiny-i-tseli-spetsialnoy-voennoy-operatsii-rf-istoricheskiy-analiz-voennogo-konflikta.txt")
nato_cyber = load_raw("NATO_Russia_s_Strategy.txt")
nato_response = load_raw("NATO_Response.txt")
black_book = load_raw("black_book_2014-2023.txt")

# The Cyrillic-named files were saved with underscored names; try both patterns
fpv_manual = (
    load_raw("______________________________.txt")  # Эксплуатация и Применение БПЛА
    or load_raw("uav_fpv_manual.txt")
)
uav_theory = (
    load_raw("___________________________________.txt")  # Теория и практика применения дронов
    or load_raw("uav_theory.txt")
)

# Helper: extract lines n..m (1-indexed, inclusive)
def lines(text: str, start: int, end: int) -> str:
    ls = text.splitlines()
    return "\n".join(ls[start - 1 : end]).strip()


# ─── 2014 Military Doctrine ───────────────────────────────────────────────────

print("Writing 2014 Military Doctrine entries...")

write_entry(
    "02_doctrine_2014_general_provisions.md",
    id="doctrine_2014_general_provisions",
    title="2014 Military Doctrine — General Provisions and Key Definitions (Arts. 1–8)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["военная доктрина", "военная безопасность", "военная угроза", "военный конфликт",
               "локальная война", "региональная война", "крупномасштабная война", "мобилизация"],
    topics=["doctrine", "definitions", "conflict_spectrum", "military_policy"],
    cited_by=["chief_of_general_staff", "main_operations_directorate", "center_military_strategic"],
    content=lines(grounding, 2, 24),
)

write_entry(
    "03_doctrine_2014_external_threats.md",
    id="doctrine_2014_external_threats",
    title="2014 Military Doctrine — External Military Threats (Art. 12)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["НАТО", "расширение НАТО", "глобальный удар", "ПРО", "цветная революция",
               "информационные технологии", "смена режима", "военная инфраструктура"],
    topics=["threat_perception", "nato_expansion", "information_warfare", "bmd"],
    cited_by=["chief_of_general_staff", "main_intelligence_directorate", "center_military_strategic",
               "commander_in_chief"],
    content=lines(grounding, 25, 43),
)

write_entry(
    "04_doctrine_2014_internal_threats.md",
    id="doctrine_2014_internal_threats",
    title="2014 Military Doctrine — Internal Military Threats (Arts. 13–14)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["внутренние угрозы", "конституционный строй", "терроризм", "информационное воздействие",
               "межнациональная напряженность", "дестабилизация"],
    topics=["internal_security", "threat_perception", "information_warfare"],
    cited_by=["chief_of_general_staff", "main_intelligence_directorate"],
    content=lines(grounding, 44, 54),
)

write_entry(
    "05_doctrine_2014_modern_conflict.md",
    id="doctrine_2014_modern_conflict",
    title="2014 Military Doctrine — Characteristics of Modern Military Conflict (Art. 15)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["гибридная война", "высокоточное оружие", "гиперзвуковое оружие", "РЭБ",
               "беспилотные аппараты", "роботизированные системы", "информационное противоборство",
               "асимметричные действия", "частные военные компании", "ССО"],
    topics=["modern_warfare", "hybrid_warfare", "uav", "ew", "information_warfare"],
    cited_by=["chief_of_general_staff", "main_operations_directorate", "unmanned_systems_forces"],
    content=lines(grounding, 55, 65),
)

write_entry(
    "06_doctrine_2014_nuclear_policy.md",
    id="doctrine_2014_nuclear_policy",
    title="2014 Military Doctrine — Nuclear Weapons Policy and Employment Conditions (Arts. 16, 27)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["ядерное оружие", "ядерное сдерживание", "стратегическое сдерживание",
               "применение ядерного оружия", "существование государства", "WMD"],
    topics=["nuclear_deterrence", "escalation", "strategic_deterrence"],
    cited_by=["chief_of_general_staff", "commander_in_chief", "center_military_strategic"],
    content=lines(grounding, 66, 67) + "\n\n" + lines(grounding, 98, 100),
)

write_entry(
    "07_doctrine_2014_use_of_force.md",
    id="doctrine_2014_use_of_force",
    title="2014 Military Doctrine — Use of Armed Forces and CSTO Obligations (Arts. 22–26)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["применение ВС", "ОДКБ", "Союзное государство", "миротворческие операции",
               "высокоточное оружие", "стратегическое сдерживание"],
    topics=["force_employment", "csto", "deterrence", "allies"],
    cited_by=["chief_of_general_staff", "minister_of_defense", "commander_in_chief"],
    content=lines(grounding, 93, 103),
)

write_entry(
    "08_doctrine_2014_peacetime_tasks.md",
    id="doctrine_2014_peacetime_tasks",
    title="2014 Military Doctrine — Peacetime Tasks of the Armed Forces (Art. 32)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["суверенитет", "территориальная целостность", "ядерное сдерживание", "воздушно-космическая оборона",
               "Арктика", "морская безопасность", "борьба с терроризмом"],
    topics=["force_missions", "sovereignty", "arctic", "counterterrorism"],
    cited_by=["chief_of_general_staff", "main_operations_directorate"],
    content=lines(grounding, 104, 123),
)

write_entry(
    "09_doctrine_2014_mobilization.md",
    id="doctrine_2014_mobilization",
    title="2014 Military Doctrine — Mobilization Readiness (Arts. 40–42)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["мобилизационная готовность", "мобилизационный план", "экономика военного времени",
               "промышленность", "людские ресурсы"],
    topics=["mobilization", "wartime_economy", "industrial_base"],
    cited_by=["chief_of_general_staff", "main_org_mob_directorate", "economic_advisor"],
    content=lines(grounding, 184, 195),
)

write_entry(
    "10_doctrine_2014_armament_uav.md",
    id="doctrine_2014_armament_uav",
    title="2014 Military Doctrine — Armament Development: UAVs, Robotics, EW (Art. 46)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["беспилотные летательные аппараты", "роботизированные ударные комплексы",
               "РЭБ", "высокоточное оружие", "гиперзвуковое", "информационное противоборство",
               "воздушно-космическая оборона"],
    topics=["armament_development", "uav", "robotics", "ew", "hypersonics"],
    cited_by=["unmanned_systems_forces", "main_operations_directorate", "chief_of_general_staff"],
    content=lines(grounding, 203, 212),
)

write_entry(
    "11_doctrine_2014_defense_industry.md",
    id="doctrine_2014_defense_industry",
    title="2014 Military Doctrine — Defense-Industrial Complex Development (Art. 52–53)",
    tier="primary_doctrine",
    source_date="2014-12-26",
    keywords=["оборонно-промышленный комплекс", "технологическая независимость",
               "гособоронзаказ", "военно-техническое сотрудничество", "инновации"],
    topics=["defense_industry", "technological_sovereignty", "procurement"],
    cited_by=["economic_advisor", "minister_of_defense", "chief_of_general_staff"],
    content=lines(grounding, 221, 238),
)

# ─── Gerasimov 2013 ───────────────────────────────────────────────────────────

print("Writing Gerasimov 2013 entries...")

# The full Gerasimov text is short enough to split into 2 entries
gerasimov_lines = gerasimov.splitlines()
mid = len(gerasimov_lines) // 2

write_entry(
    "12_gerasimov_2013_new_type_warfare.md",
    id="gerasimov_2013_new_type_warfare",
    title="Gerasimov (2013) — The Value of Science in Foresight: New-Type Warfare and the Arab Spring",
    tier="academic_russian",
    source_date="2013-02-27",
    keywords=["война нового типа", "арабская весна", "невоенные меры", "цветные революции",
               "информационное противоборство", "Герасимов", "ценность науки"],
    topics=["new_generation_warfare", "information_warfare", "color_revolutions", "gerasimov_doctrine"],
    cited_by=["chief_of_general_staff", "center_military_strategic", "main_intelligence_directorate"],
    content="\n".join(gerasimov_lines[:mid]).strip(),
)

write_entry(
    "13_gerasimov_2013_military_science.md",
    id="gerasimov_2013_military_science",
    title="Gerasimov (2013) — Military Science Tasks: Robotics, Information Space, Science of Foresight",
    tier="academic_russian",
    source_date="2013-02-27",
    keywords=["военная наука", "робототехника", "беспилотники", "информационное пространство",
               "территориальная оборона", "оперативное использование ВС за рубежом"],
    topics=["military_science", "robotics", "uav", "information_warfare", "expeditionary_ops"],
    cited_by=["chief_of_general_staff", "unmanned_systems_forces"],
    content="\n".join(gerasimov_lines[mid:]).strip(),
)

# ─── SVO Causes ───────────────────────────────────────────────────────────────

print("Writing SVO Causes entries...")

svo_lines = svo_causes.splitlines()
# Find the actual article start (skip the journal header ~line 26)
article_start = next(
    (i for i, l in enumerate(svo_lines) if "ОСНОВНЫЕ ПРИЧИНЫ И ЦЕЛИ" in l.upper()), 0
)

write_entry(
    "14_svo_causes_nato_expansion.md",
    id="svo_causes_nato_expansion",
    title="SVO Causes — NATO Expansion and the Post-Cold War Security Order (Nadbitov 2025)",
    tier="academic_russian",
    source_date="2025-01-01",
    keywords=["НАТО", "расширение НАТО", "Бжезинский", "однополярный мир", "постсоветское пространство",
               "Украина", "Майдан", "Будапештский меморандум", "безопасность"],
    topics=["nato_expansion", "post_cold_war", "ukraine_crisis", "threat_perception"],
    cited_by=["commander_in_chief", "center_military_strategic", "chief_of_general_staff"],
    content="\n".join(svo_lines[article_start : article_start + 100]).strip(),
)

write_entry(
    "15_svo_causes_donbas_2014_2022.md",
    id="svo_causes_donbas_2014_2022",
    title="SVO Causes — Donbas Conflict 2014–2022: Minsk Agreements and the Road to SVO",
    tier="academic_russian",
    source_date="2025-01-01",
    keywords=["Донбасс", "Минские соглашения", "Минск-1", "Минск-2", "ВСУ", "АТО",
               "референдум", "Порошенко", "Зеленский", "геноцид"],
    topics=["ukraine_conflict", "donbas", "minsk_agreements", "escalation"],
    cited_by=["commander_in_chief", "chief_of_general_staff", "main_intelligence_directorate"],
    content="\n".join(svo_lines[article_start + 100 : article_start + 200]).strip(),
)

write_entry(
    "16_svo_justification_official.md",
    id="svo_justification_official",
    title="SVO — Official RF Justification: Denazification, Demilitarization, Protection of Donbas",
    tier="academic_russian",
    source_date="2025-01-01",
    keywords=["СВО", "денацификация", "демилитаризация", "Донбасс", "мирное население",
               "Устав ООН", "статья 51", "нацизм", "Бандера", "НАТО"],
    topics=["svo_justification", "denazification", "un_charter", "nato_threat"],
    cited_by=["commander_in_chief", "minister_of_defense"],
    content="\n".join(svo_lines[article_start + 200 :]).strip(),
)

# ─── Ukrainian Nationalism History ────────────────────────────────────────────

print("Writing Ukrainian nationalism history entries...")

# From GROUNDING file — lines 401-464 cover Ukrainian nationalism and post-Soviet collapse
write_entry(
    "17_ukraine_nationalism_historical.md",
    id="ukraine_nationalism_historical",
    title="Ukrainian Nationalism: Historical Roots 1917–1991 and the Bandеrist Legacy",
    tier="academic_russian",
    source_date="2024-01-01",
    keywords=["украинский национализм", "ОУН", "УПА", "Бандера", "нацизм",
               "Рух", "Свобода", "русофобия", "советская Украина"],
    topics=["ukraine_history", "nationalism", "banderism", "information_narrative"],
    cited_by=["commander_in_chief", "main_intelligence_directorate"],
    content=lines(grounding, 401, 440),
)

write_entry(
    "18_ukraine_post_soviet_collapse.md",
    id="ukraine_post_soviet_collapse",
    title="Post-Soviet Ukraine: Economic Collapse, Oligarchy, and the Roots of 2014",
    tier="academic_russian",
    source_date="2024-01-01",
    keywords=["постсоветская Украина", "экономический кризис", "олигархат", "Кравчук",
               "независимость 1991", "шоковая терапия", "МВФ", "обнищание"],
    topics=["ukraine_history", "economic_context", "post_soviet"],
    cited_by=["economic_advisor", "commander_in_chief"],
    content=lines(grounding, 452, 464),
)

# ─── Arab Spring / Color Revolution Framing ───────────────────────────────────

print("Writing Arab Spring / color revolution entries...")

write_entry(
    "19_arab_spring_color_revolution_framing.md",
    id="arab_spring_color_revolution_framing",
    title="Arab Spring as Western-Managed Color Revolution — Russian Analytical Frame",
    tier="academic_russian",
    source_date="2024-04-27",
    keywords=["арабская весна", "цветные революции", "западное вмешательство", "смена режима",
               "информационные технологии", "молодежь", "социальные сети", "исламизм"],
    topics=["color_revolutions", "western_interference", "information_warfare", "middle_east"],
    cited_by=["main_intelligence_directorate", "center_military_strategic"],
    content=lines(grounding, 465, 500),
)

# ─── Black Book — Atrocities Catalog ──────────────────────────────────────────

print("Writing Black Book atrocities entries...")

# Extract the numbered atrocities list from GROUNDING (lines 580-651)
write_entry(
    "20_black_book_donbas_atrocities_svo.md",
    id="black_book_donbas_atrocities_svo",
    title="Black Book 2022–2023: Documented Ukrainian Nationalist Atrocities Against Civilians (SVO Period)",
    tier="kremlin_statement",
    source_date="2023-01-01",
    keywords=["Азов", "военные преступления", "мирные жители", "Мариуполь", "Донецк",
               "ДНР", "ЛНР", "расстрел", "пытки", "денацификация"],
    topics=["war_crimes", "donbas", "denazification_narrative", "civilian_casualties"],
    cited_by=["commander_in_chief", "minister_of_defense"],
    content=lines(grounding, 605, 651),
)

# From the black_book PDF (the pre-SVO period, 2014-2022)
if black_book and len(black_book) > 5000:
    bb_lines = black_book.splitlines()
    # Find meaningful content start (skip title pages)
    bb_start = next((i for i, l in enumerate(bb_lines) if len(l.strip()) > 100), 50)
    write_entry(
        "21_black_book_donbas_atrocities_2014_2021.md",
        id="black_book_donbas_atrocities_2014_2021",
        title="Black Book 2014–2021: Documented Incidents of Violence Against Russian-Speaking Civilians in Donbas",
        tier="kremlin_statement",
        source_date="2023-01-01",
        keywords=["Донбасс", "2014", "2015", "2016", "военные преступления", "мирные жители",
                   "ВСУ", "Азов", "Правый сектор", "АТО"],
        topics=["war_crimes", "donbas", "denazification_narrative", "2014_conflict"],
        cited_by=["commander_in_chief", "main_intelligence_directorate"],
        content="\n".join(bb_lines[bb_start : bb_start + 150]).strip(),
    )

# ─── FPV Drone Manual ─────────────────────────────────────────────────────────

print("Writing FPV drone manual entries...")

if fpv_manual and len(fpv_manual) > 5000:
    fpv_lines = fpv_manual.splitlines()

    # Find table of contents / chapter starts
    def find_section(text_lines: list[str], keyword: str) -> int:
        kw_upper = keyword.upper()
        for i, l in enumerate(text_lines):
            if kw_upper in l.upper():
                return i
        return 0

    ch1_start = find_section(fpv_lines, "КЛАССИФИКАЦИЯ БпЛА") or find_section(fpv_lines, "1.1")
    ch2_start = find_section(fpv_lines, "АППАРАТУРА УПРАВЛЕНИЯ") or find_section(fpv_lines, "2.1")
    ch3_start = find_section(fpv_lines, "ПОРЯДОК ПОДГОТОВКИ") or find_section(fpv_lines, "3.1")
    ch5_start = find_section(fpv_lines, "ПИЛОТИРОВАНИЕ") or find_section(fpv_lines, "5.")

    write_entry(
        "22_fpv_drone_classification_specs.md",
        id="fpv_drone_classification_specs",
        title="FPV Drone Manual (VVA 2023) — UAV Classification, Types, and Technical Characteristics",
        tier="primary_doctrine",
        source_date="2023-01-01",
        keywords=["БпЛА", "FPV-дрон", "квадрокоптер", "классификация", "ТТХ",
                   "коммерческие БПЛА", "полет", "полезная нагрузка"],
        topics=["uav_doctrine", "uav_classification", "fpv_drones", "technical_specs"],
        cited_by=["unmanned_systems_forces"],
        content="\n".join(fpv_lines[ch1_start : ch1_start + 120]).strip(),
    )

    write_entry(
        "23_fpv_drone_control_rf_systems.md",
        id="fpv_drone_control_rf_systems",
        title="FPV Drone Manual (VVA 2023) — Control Systems, RF Frequencies, and Video Transmission",
        tier="primary_doctrine",
        source_date="2023-01-01",
        keywords=["аппаратура управления", "частоты", "2.4 ГГц", "5.8 ГГц", "FPV",
                   "видеосигнал", "антенны", "радиобезопасность"],
        topics=["uav_doctrine", "electronic_warfare", "rf_systems", "fpv_drones"],
        cited_by=["unmanned_systems_forces"],
        content="\n".join(fpv_lines[ch2_start : ch2_start + 120]).strip(),
    )

    write_entry(
        "24_fpv_drone_operator_training.md",
        id="fpv_drone_operator_training",
        title="FPV Drone Manual (VVA 2023) — Operator Training, Weather Effects, and Tactical Limitations",
        tier="primary_doctrine",
        source_date="2023-01-01",
        keywords=["оператор", "подготовка", "метеоусловия", "ограничения", "визуальная ориентировка",
                   "полетное задание", "тренажер"],
        topics=["uav_doctrine", "operator_training", "tactical_employment"],
        cited_by=["unmanned_systems_forces"],
        content="\n".join(fpv_lines[ch3_start : ch3_start + 120]).strip(),
    )

# ─── UAV Theory & Practice ────────────────────────────────────────────────────

print("Writing UAV Theory entries...")

if uav_theory and len(uav_theory) > 5000:
    uav_lines = uav_theory.splitlines()

    # Skip title/blank pages
    content_start = next((i for i, l in enumerate(uav_lines) if len(l.strip()) > 80), 80)

    write_entry(
        "25_uav_theory_tactical_concepts.md",
        id="uav_theory_tactical_concepts",
        title="UAV Theory and Practice — Tactical Employment Concepts and Reconnaissance-Strike Complexes",
        tier="academic_russian",
        source_date="2024-01-01",
        keywords=["разведывательно-ударный комплекс", "тактические БПЛА", "разведка",
                   "целеуказание", "барражирующий боеприпас", "Ланцет", "Герань", "Шахед"],
        topics=["uav_doctrine", "reconnaissance_strike", "loitering_munitions", "combined_arms"],
        cited_by=["unmanned_systems_forces", "main_operations_directorate"],
        content="\n".join(uav_lines[content_start : content_start + 150]).strip(),
    )

    ew_start = next(
        (i for i, l in enumerate(uav_lines) if "РЭБ" in l or "радиоэлектронн" in l.lower()), content_start + 150
    )
    write_entry(
        "26_uav_theory_ew_countermeasures.md",
        id="uav_theory_ew_countermeasures",
        title="UAV Theory and Practice — Electronic Warfare, Counter-UAV, and Survivability",
        tier="academic_russian",
        source_date="2024-01-01",
        keywords=["РЭБ", "противодействие БПЛА", "постановка помех", "глушение",
                   "подавление", "маскировка", "живучесть", "частотная война"],
        topics=["electronic_warfare", "counter_uav", "uav_survivability"],
        cited_by=["unmanned_systems_forces", "main_operations_directorate"],
        content="\n".join(uav_lines[ew_start : ew_start + 150]).strip(),
    )

# ─── NATO Analysis ────────────────────────────────────────────────────────────

print("Writing NATO analysis entries...")

if nato_cyber and len(nato_cyber) > 5000:
    nc_lines = nato_cyber.splitlines()

    # Introduction section
    intro_start = next((i for i, l in enumerate(nc_lines) if "INTRODUCTION" in l.upper()), 0)
    info_start = next((i for i, l in enumerate(nc_lines) if "information confrontation" in l.lower()), 0)
    cyber_start = next((i for i, l in enumerate(nc_lines) if "Activities in cyberspace" in l), 0)
    sovereign_start = next((i for i, l in enumerate(nc_lines) if "digital sovereignty" in l.lower()), 0)

    write_entry(
        "27_nato_analysis_russian_info_confrontation.md",
        id="nato_analysis_russian_info_confrontation",
        title="NATO StratCom Analysis: Russian 'Information Confrontation' Doctrine (2021)",
        tier="osint_analysis",
        source_date="2021-06-01",
        keywords=["information confrontation", "информационное противоборство", "cognitive warfare",
                   "cyber operations", "influence operations", "digital sovereignty"],
        topics=["information_warfare", "nato_perspective", "cyber", "adversary_analysis"],
        cited_by=["main_intelligence_directorate", "center_military_strategic"],
        content="\n".join(nc_lines[max(0, info_start - 5) : info_start + 100]).strip(),
    )

    write_entry(
        "28_nato_analysis_digital_sovereignty.md",
        id="nato_analysis_digital_sovereignty",
        title="NATO StratCom Analysis: Russian Digital Sovereignty and Runet Isolation",
        tier="osint_analysis",
        source_date="2021-06-01",
        keywords=["digital sovereignty", "Runet", "internet isolation", "SORM", "RuNet",
                   "censorship", "Sovereign Internet Law"],
        topics=["information_security", "digital_sovereignty", "nato_perspective"],
        cited_by=["main_intelligence_directorate"],
        content="\n".join(nc_lines[max(0, sovereign_start - 5) : sovereign_start + 80]).strip(),
    )

    if cyber_start > 0:
        write_entry(
            "29_nato_analysis_russian_cyber_operations.md",
            id="nato_analysis_russian_cyber_operations",
            title="NATO StratCom Analysis: Russia's Offensive Cyber Activities — Actors and Operations",
            tier="osint_analysis",
            source_date="2021-06-01",
            keywords=["GRU", "SVR", "FSB", "APT28", "APT29", "NotPetya", "election interference",
                       "cyber proxies", "hack and leak"],
            topics=["cyber_operations", "intelligence_services", "nato_perspective", "gru"],
            cited_by=["main_intelligence_directorate"],
            content="\n".join(nc_lines[cyber_start : cyber_start + 100]).strip(),
        )

if nato_response and len(nato_response) > 500:
    write_entry(
        "30_nato_response_russia_doctrine.md",
        id="nato_response_russia_doctrine",
        title="NATO Response to Russian Military Doctrine and Strategic Posture",
        tier="osint_analysis",
        source_date="2022-01-01",
        keywords=["NATO", "Russia", "deterrence", "defense posture", "Baltic", "Enhanced Forward Presence"],
        topics=["nato_perspective", "deterrence", "force_posture"],
        cited_by=["center_military_strategic", "sino_russian_liaison"],
        content=nato_response.strip(),
    )

print(f"\nDone. Check {SNAPSHOT}/")
