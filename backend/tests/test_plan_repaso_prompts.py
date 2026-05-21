"""Tests del parser y fallbacks del plan de repaso."""

from __future__ import annotations

from src.utils.plan_repaso_prompts import (
    SESSION_ORDER,
    _generic_fallback,
    build_plan_prompt,
    merge_parsed_with_fallback,
    parse_plan_response,
)

_SAMPLE_LLM_OUTPUT = """\
[D+1]
Elabora un mapa conceptual de algoritmos de ordenamiento con complejidad O(n).
Define con tus palabras qué es estabilidad en un algoritmo de ordenamiento.
Explica en voz alta la diferencia entre burbuja y selección sin consultar apuntes.

[D+7]
Implementa quicksort en Python y mide tiempos con listas de 100 y 10_000 elementos.
Analiza tres errores típicos al elegir el pivote en quicksort y cómo evitarlos.
Completa cinco preguntas tipo examen sobre complejidad de ordenamiento O(n log n).

[D+14]
Resuelve un caso integrador: ordenar registros de estudiantes por dos criterios.
Establece cuándo usar merge sort frente a quicksort según memoria y estabilidad.
Relaciona el ordenamiento con estructuras de datos tipo montículo (heap).

[D+30]
Autoevalúate con 12 preguntas cerradas sobre ordenamiento sin mirar material.
Simula un examen de 45 minutos implementando dos algoritmos y comparando resultados.
Enseña el tema a un compañero imaginario en 5 minutos y anota lagunas detectadas.
"""


def test_parse_plan_response_extrae_cuatro_bloques():
    parsed = parse_plan_response(_SAMPLE_LLM_OUTPUT)
    assert set(parsed.keys()) == set(SESSION_ORDER)
    for tipo in SESSION_ORDER:
        assert len(parsed[tipo]) == 3


def test_parse_plan_response_vacio_si_no_hay_etiquetas():
    assert parse_plan_response("solo texto sin bloques") == {}


def test_actividades_parseadas_no_son_identicas_entre_sesiones():
    parsed = parse_plan_response(_SAMPLE_LLM_OUTPUT)
    all_acts = [a for acts in parsed.values() for a in acts]
    assert len(all_acts) == len(set(all_acts))


def test_generic_fallback_diferencia_por_tipo():
    d1 = _generic_fallback("Algoritmos", "D+1")
    d30 = _generic_fallback("Algoritmos", "D+30")
    assert d1 != d30
    assert "mapa conceptual" in d1[0].lower() or "conceptos" in d1[0].lower()
    assert "autoeval" in d30[0].lower() or "simulacro" in " ".join(d30).lower()


def test_build_plan_prompt_incluye_roles_pedagogicos():
    prompt = build_plan_prompt("Ordenamiento", "contexto de prueba")
    assert "D+1" in prompt and "D+30" in prompt
    assert "Prohibido repetir" in prompt
    assert "contexto de prueba" in prompt


def test_merge_parsed_completa_sesiones_faltantes():
    partial = {"D+1": ["a" * 20, "b" * 20, "c" * 20]}
    merged = merge_parsed_with_fallback(partial, "Tema X")
    assert len(merged) == 4
    assert len(merged["D+7"]) == 3
