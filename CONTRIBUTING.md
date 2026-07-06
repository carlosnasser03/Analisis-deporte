# Guía de Contribución - Scout AI

**Versión:** 2.0  
**Última actualización:** 2026-07-06

¡Gracias por tu interés en contribuir a Scout AI! Esta guía describe el proceso de desarrollo, estándares de código y mejores prácticas.

---

## Tabla de Contenidos

1. [Configuración del Entorno](#configuración-del-entorno)
2. [Estándares de Código](#estándares-de-código)
3. [Proceso de Desarrollo](#proceso-de-desarrollo)
4. [Testing](#testing)
5. [Commits y Pull Requests](#commits-y-pull-requests)
6. [Documentación](#documentación)
7. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## Configuración del Entorno

### 1. Fork y Clone

```bash
# Fork el repositorio en GitHub
# Luego clonar tu fork
git clone https://github.com/tu-usuario/scout-ai.git
cd scout-ai

# Agregar upstream remoto
git remote add upstream https://github.com/scout-ai/scout-ai.git
```

### 2. Crear Rama de Desarrollo

```bash
# Actualizar main
git fetch upstream
git checkout main
git merge upstream/main

# Crear rama de feature
git checkout -b feature/nombre-descriptivo
# O para bugfix
git checkout -b fix/nombre-descriptivo
```

### 3. Configurar Entorno Virtual

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Instalar dependencias de desarrollo
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Pre-commit Hooks (Opcional pero Recomendado)

```bash
# Instalar pre-commit
pip install pre-commit

# Instalar hooks
pre-commit install

# Ejecutar manualmente
pre-commit run --all-files
```

---

## Estándares de Código

### Convenciones de Nombres

```python
# Módulos y archivos: snake_case
video_splitter.py
validators.py

# Clases: PascalCase
class VideoSplitter:
    pass

class ValidationResult:
    pass

# Funciones y métodos: snake_case
def validate_video_file(path):
    pass

def get_chunk_info(chunk_id):
    pass

# Constantes: UPPER_SNAKE_CASE
MIN_DURATION_SECONDS = 1
MAX_DURATION_SECONDS = 3600
SUPPORTED_FORMATS = {'.mp4', '.avi'}
```

### Estilo de Código

Seguimos **PEP 8** con algunas excepciones:

```python
# Máximo 100 caracteres por línea (preferible 80)
# Indentación: 4 espacios
# Dos líneas en blanco entre clases
# Una línea en blanco entre métodos

class MyClass:
    """Docstring de clase"""
    
    def __init__(self):
        """Docstring de método"""
        self.value = 0
    
    def method_one(self):
        """Primera método"""
        pass
    
    def method_two(self):
        """Segunda método"""
        pass


class AnotherClass:
    """Otra clase"""
    pass
```

### Type Hints

Usar type hints en todas las funciones nuevas:

```python
from typing import Dict, List, Optional, Tuple

def process_video(
    video_path: str,
    config: Dict[str, Any],
    output_dir: Optional[str] = None
) -> Dict[str, List]:
    """
    Procesa un video con configuración específica.
    
    Args:
        video_path: Ruta al archivo de video
        config: Diccionario de configuración
        output_dir: Directorio de salida (optional)
    
    Returns:
        Diccionario con resultados de procesamiento
    """
    pass
```

### Docstrings

Usar formato Google para docstrings:

```python
def validate_video_file(video_path: str) -> ValidationResult:
    """
    Valida un archivo de video.
    
    Verifica formato, duración, resolución y legibilidad.
    
    Args:
        video_path (str): Ruta al archivo de video.
    
    Returns:
        ValidationResult: Objeto con resultado de validación
        
    Raises:
        FileNotFoundError: Si el archivo no existe
        ValueError: Si el video es inválido
    
    Example:
        >>> result = validate_video_file("video.mp4")
        >>> if result.is_valid:
        ...     print("Video válido")
    """
    pass
```

### Imports

Organizar imports en este orden:

```python
# 1. Estándar library
import os
import json
from pathlib import Path
from typing import Dict, List

# 2. Third-party
import cv2
import numpy as np
from ultralytics import YOLO

# 3. Local
from utils import VideoValidator
from core import DetectionMetrics
```

### Logging

Usar logging en lugar de prints:

```python
import logging

logger = logging.getLogger(__name__)

# Malo
print("Procesando video...")

# Bueno
logger.info("Procesando video...")
logger.warning("Formato no soportado")
logger.error("No se puede abrir el archivo")
```

---

## Proceso de Desarrollo

### Workflow típico

```bash
# 1. Crear rama
git checkout -b feature/my-feature

# 2. Hacer cambios
# ... editar archivos ...

# 3. Agregar cambios
git add .

# 4. Hacer commit
git commit -m "feat: descripción clara del cambio"

# 5. Hacer push
git push origin feature/my-feature

# 6. Crear Pull Request en GitHub
```

### Estructura de Commit

```bash
# Formato: <tipo>(<scope>): <descripción>

# Ejemplos válidos:
git commit -m "feat(validators): agregar VideoValidator"
git commit -m "fix(detector): corregir detección de balón"
git commit -m "docs(readme): actualizar instrucciones"
git commit -m "refactor(core): simplificar UnifiedDetector"
git commit -m "test(validators): agregar tests para VideoValidator"
git commit -m "chore(deps): actualizar dependencias"

# Tipos comunes:
# - feat: Nueva funcionalidad
# - fix: Corregir bug
# - docs: Cambios de documentación
# - style: Formato de código
# - refactor: Refactorización sin cambiar comportamiento
# - test: Agregar o actualizar tests
# - chore: Cambios en build, deps, etc.
```

---

## Testing

### Escribir Tests

Crear tests en directorio `tests/`:

```python
# tests/test_validators.py
import pytest
from utils import VideoValidator, ValidationResult


class TestVideoValidator:
    """Tests para VideoValidator"""
    
    def test_validate_valid_video(self, sample_video_path):
        """Valida un video válido"""
        result = VideoValidator.validate_video_file(sample_video_path)
        assert result.is_valid
        assert result.errors == []
    
    def test_validate_missing_file(self):
        """Maneja archivo faltante"""
        result = VideoValidator.validate_video_file("no_existe.mp4")
        assert not result.is_valid
        assert "no encontrado" in result.message.lower()
    
    def test_validate_unsupported_format(self, tmp_path):
        """Rechaza formato no soportado"""
        # Crear archivo con extensión no soportada
        bad_file = tmp_path / "video.xyz"
        bad_file.write_text("fake content")
        
        result = VideoValidator.validate_video_file(str(bad_file))
        assert not result.is_valid
```

### Ejecutar Tests

```bash
# Instalar pytest
pip install pytest pytest-cov

# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=core --cov=utils

# Tests específicos
pytest tests/test_validators.py
pytest tests/test_validators.py::TestVideoValidator::test_validate_valid_video
```

### Fixtures Útiles

```python
# tests/conftest.py
import pytest
import cv2
import numpy as np


@pytest.fixture
def sample_video_path(tmp_path):
    """Crea un video de prueba"""
    video_path = tmp_path / "test_video.mp4"
    
    # Crear video 10 frames
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(
        str(video_path),
        fourcc,
        30.0,
        (640, 480)
    )
    
    for i in range(10):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        out.write(frame)
    
    out.release()
    return str(video_path)


@pytest.fixture
def sample_config():
    """Configuración de prueba"""
    return {
        'model_path': 'models/yolo.pt',
        'confidence': 0.5,
        'max_workers': 4,
    }
```

### Coverage

```bash
# Ver cobertura detallada
pytest --cov=core --cov=utils --cov-report=html

# Abre htmlcov/index.html
```

---

## Commits y Pull Requests

### Antes de hacer Commit

```bash
# 1. Verificar que el código cumple estándares
flake8 utils/ core/

# 2. Ejecutar tests
pytest

# 3. Verificar type hints
mypy utils/ core/

# 4. Actualizar imports
isort utils/ core/
```

### Plantilla de Pull Request

```markdown
## Descripción
Breve descripción de los cambios

## Tipo de Cambio
- [ ] Nueva funcionalidad
- [ ] Corrección de bug
- [ ] Breaking change
- [ ] Actualización de documentación

## Cambios
- Cambio 1
- Cambio 2
- Cambio 3

## Testing
- [ ] Tests unitarios agregados
- [ ] Tests existentes pasan
- [ ] Cobertura >= 80%

## Documentación
- [ ] Docstrings actualizados
- [ ] README actualizado (si aplica)
- [ ] ARCHITECTURE_IMPLEMENTATION.md actualizado (si aplica)

## Checklist
- [ ] Código sigue PEP 8
- [ ] No hay prints (usar logging)
- [ ] Type hints incluidos
- [ ] Docstrings actualizados
```

### Revisor

Los revisores verificarán:

- ✓ Código correcto y sin bugs
- ✓ Tests incluidos y pasando
- ✓ Documentación actualizada
- ✓ Estándares de código seguidos
- ✓ Sin conflictos de merge

---

## Documentación

### Agregar Documentación

Para cambios significativos, actualizar:

1. **Docstrings de código** - Docstrings Google format
2. **README.md** - Si añade nueva funcionalidad visible
3. **ARCHITECTURE_IMPLEMENTATION.md** - Si cambia arquitectura
4. **CONTRIBUTING.md** - Si cambia proceso de desarrollo

### Ejemplo: Nuevo Detector

Si agregas `core/my_detector.py`:

```python
"""
my_detector.py - Descripción breve

Propósito: Qué hace este módulo
Características principales
"""

class MyDetector:
    """
    Descripción larga de la clase
    
    Attributes:
        model: Modelo YOLO
        device: CPU o GPU
    """
    
    def __init__(self, model_path: str):
        """Inicialización"""
        pass
    
    def detect(self, frame: np.ndarray) -> Dict:
        """Detectar objetos"""
        pass
```

Luego actualizar:

1. `core/__init__.py` - Agregar import
2. `ARCHITECTURE_IMPLEMENTATION.md` - Documentar clase
3. `README.md` - Mencionarlo en módulos disponibles

---

## Preguntas Frecuentes

### P: ¿Cómo reportar un bug?

**R:** Crear un issue con:
- Título descriptivo
- Pasos para reproducir
- Comportamiento esperado
- Comportamiento actual
- Entorno (Python version, OS, etc.)

```markdown
**Título:** VideoSplitter falla con videos > 5GB

**Pasos para reproducir:**
1. Crear video de 6GB
2. Llamar VideoSplitter("video.mp4")
3. Ejecutar split_video()

**Error:**
MemoryError: Unable to allocate 2.50 GiB
```

### P: ¿Cómo proponer una nueva característica?

**R:** Crear un issue con etiqueta `enhancement`:
- Descripción del problema
- Solución propuesta
- Alternativas consideradas
- Contexto adicional

### P: ¿Cuánto tiempo toma un review?

**R:** Típicamente 48-72 horas en días hábiles.

### P: ¿Puedo cambiar el core/__init__.py?

**R:** Solo si:
- Es para agregar importaciones de nuevas clases
- La clase está documentada
- Hay tests
- Es consensuado

### P: ¿Qué pasa si mi PR tiene conflictos?

**R:** 
```bash
git fetch upstream
git rebase upstream/main
# Resolver conflictos
git add .
git rebase --continue
git push --force-with-lease origin feature/my-feature
```

### P: ¿Necesito agregar tests para todo?

**R:** Sí, excepto:
- Scripts de ejemplo
- Código de prueba/demo
- Cambios de documentación pura

Mínimo 70% de cobertura para core y utils.

---

## Recursos Útiles

### Documentación

- [PEP 8](https://pep8.org/) - Style Guide for Python
- [Google Docstring](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [Type Hints](https://docs.python.org/3/library/typing.html)
- [pytest Documentation](https://docs.pytest.org/)

### Herramientas

```bash
# Linting
pip install flake8 pylint black

# Type checking
pip install mypy

# Formatting
pip install black isort

# Testing
pip install pytest pytest-cov

# Pre-commit
pip install pre-commit
```

### Configuración recomendada (.editorconfig)

```ini
[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4

[*.{yaml,yml}]
indent_style = space
indent_size = 2
```

---

## Contacto

Para preguntas sobre contribución:

- 📧 Email: contribute@scout-ai.com
- 💬 Discussions: GitHub Discussions
- 🐛 Issues: GitHub Issues

---

**¡Gracias por contribuir a Scout AI!**

Scout AI Team | 2026
