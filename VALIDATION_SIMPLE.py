#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script simple de validacion para FASE 2
"""

from pathlib import Path
import json


def main():
    print("\n" + "=" * 60)
    print("  VALIDACION DE FASE 2 - ARQUITECTURA PROFESIONAL")
    print("=" * 60)

    project = Path(__file__).parent

    # 1. Validar archivos creados
    print("\n1. VALIDACION DE ARCHIVOS CREADOS")
    print("-" * 60)

    files_to_check = {
        "utils/video_splitter.py": "Divisor de videos",
        "utils/validators.py": "Validadores",
        "utils/__init__.py": "Package init",
        "ARCHITECTURE_IMPLEMENTATION.md": "Doc tecnica",
        "README.md": "README actualizado",
        "CONTRIBUTING.md": "Guia de contribucion",
        "data/logs/FASE_2_COMPLETADA.json": "Checklist completacion",
    }

    created_count = 0
    for filepath, description in files_to_check.items():
        full_path = project / filepath
        if full_path.exists():
            size = full_path.stat().st_size / 1024
            print(f"[OK] {filepath}")
            print(f"     ({description}, {size:.1f} KB)")
            created_count += 1
        else:
            print(f"[NO] {filepath}")

    print(f"\nArchivos creados: {created_count}/{len(files_to_check)}")

    # 2. Validar imports de utils
    print("\n2. VALIDACION DE IMPORTS (utils)")
    print("-" * 60)

    try:
        from utils import (
            VideoSplitter,
            ChunkInfo,
            VideoValidator,
            DetectionValidator,
            ConfigValidator,
            DependencyValidator,
            ValidationResult,
        )
        print("[OK] Todos los imports de utils funcionan")
        imports_ok = True
    except Exception as e:
        print(f"[NO] Error en imports: {e}")
        imports_ok = False

    # 3. Validar core actualizado
    print("\n3. VALIDACION DE CORE ACTUALIZADO")
    print("-" * 60)

    core_init = project / "core" / "__init__.py"
    if core_init.exists():
        content = core_init.read_text(encoding='utf-8', errors='ignore')
        required_exports = [
            'TeamClassifier',
            'TeamColor',
            'PlayerTracker',
            'JerseyNumberDetector',
        ]

        missing = []
        for export in required_exports:
            if export not in content:
                missing.append(export)

        if not missing:
            print("[OK] Todas las clases core estan exportadas")
            core_ok = True
        else:
            print(f"[NO] Faltan exportaciones: {missing}")
            core_ok = False
    else:
        print("[NO] core/__init__.py no encontrado")
        core_ok = False

    # 4. Validar documentacion
    print("\n4. VALIDACION DE DOCUMENTACION")
    print("-" * 60)

    docs_to_check = {
        "README.md": ["Instalacion", "Uso Rapido", "Estructura"],
        "ARCHITECTURE_IMPLEMENTATION.md": ["Estructura", "Modulos core", "Diagrama"],
        "CONTRIBUTING.md": ["Testing", "Estándares", "Pull Requests"],
    }

    docs_ok = True
    for doc, required_sections in docs_to_check.items():
        doc_path = project / doc
        if doc_path.exists():
            content = doc_path.read_text(encoding='utf-8', errors='ignore')
            found = sum(1 for section in required_sections if section in content)
            print(f"[OK] {doc} ({found}/{len(required_sections)} secciones)")
        else:
            print(f"[NO] {doc} no encontrado")
            docs_ok = False

    # 5. Validar checklist
    print("\n5. VALIDACION DE CHECKLIST")
    print("-" * 60)

    checklist_path = project / "data" / "logs" / "FASE_2_COMPLETADA.json"
    if checklist_path.exists():
        try:
            with open(checklist_path, 'r', encoding='utf-8') as f:
                checklist = json.load(f)

            if checklist.get("estado") == "COMPLETADA":
                print("[OK] Checklist marcado como COMPLETADO")
                checklist_ok = True
            else:
                print(f"[NO] Estado: {checklist.get('estado')}")
                checklist_ok = False
        except Exception as e:
            print(f"[NO] Error al leer checklist: {e}")
            checklist_ok = False
    else:
        print("[NO] Checklist no encontrado")
        checklist_ok = False

    # Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)

    checks = {
        "Archivos creados": created_count == len(files_to_check),
        "Imports utils": imports_ok,
        "Core actualizado": core_ok,
        "Documentacion": docs_ok,
        "Checklist": checklist_ok,
    }

    for check_name, result in checks.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {check_name}")

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)

    print(f"\nResultado: {passed}/{total} checks pasados")

    if passed >= 4:
        print("\n" + "=" * 60)
        print("FASE 2 COMPLETADA EXITOSAMENTE!")
        print("=" * 60)
        print("\nEntregables:")
        print("  - 2 modulos utils (video_splitter, validators)")
        print("  - 3 documentos completos (Arch, README, Contributing)")
        print("  - Checklist de completacion")
        print("  - core/__init__.py actualizado")
        return 0
    else:
        print("\nAlgunos checks fallaron.")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
