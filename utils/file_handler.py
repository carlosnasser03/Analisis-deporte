"""
Scout AI - File Handler Module

Manejo centralizado de archivos para Scout AI.
Soporta JSON, CSV y gestión de directorios.
"""

import json
import csv
import os
import shutil
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class FileHandler:
    """
    Manejador centralizado de archivos para Scout AI.

    Funcionalidades:
    - Lectura/escritura de JSON
    - Lectura/escritura de CSV
    - Creación y gestión de directorios
    - Validación de rutas
    - Backup automático
    """

    def __init__(self):
        """Inicializa el manejador de archivos."""
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        self.backup_enabled = True
        self.backup_dir = 'backups'

    def _setup_logging(self):
        """Configura el logging."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - FileHandler - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def save_json(
        self,
        data: Dict,
        path: str,
        pretty: bool = True,
        backup: bool = True
    ) -> bool:
        """
        Guarda datos en archivo JSON.

        Args:
            data: Diccionario a guardar
            path: Ruta del archivo
            pretty: Si se debe indentar el JSON
            backup: Si se debe hacer backup del archivo existente

        Returns:
            True si se guardó correctamente
        """
        try:
            # Crear directorio si no existe
            self.create_output_dir(path)

            # Hacer backup si el archivo existe
            if backup and os.path.exists(path) and self.backup_enabled:
                self._create_backup(path)

            # Guardar JSON
            indent = 2 if pretty else None
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)

            self.logger.info(f"JSON guardado: {path}")
            return True

        except Exception as e:
            self.logger.error(f"Error guardando JSON {path}: {str(e)}")
            return False

    def load_json(self, path: str) -> Optional[Dict]:
        """
        Carga datos desde un archivo JSON.

        Args:
            path: Ruta del archivo

        Returns:
            Diccionario cargado o None si hay error
        """
        try:
            if not os.path.exists(path):
                self.logger.warning(f"Archivo no existe: {path}")
                return None

            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.logger.info(f"JSON cargado: {path}")
            return data

        except Exception as e:
            self.logger.error(f"Error cargando JSON {path}: {str(e)}")
            return None

    def save_csv(
        self,
        data: List[Dict],
        path: str,
        fieldnames: Optional[List[str]] = None,
        backup: bool = True
    ) -> bool:
        """
        Guarda datos en archivo CSV.

        Args:
            data: Lista de diccionarios
            path: Ruta del archivo
            fieldnames: Nombres de columnas (se extraen de los datos si no se especifica)
            backup: Si se debe hacer backup del archivo existente

        Returns:
            True si se guardó correctamente
        """
        try:
            if not data:
                self.logger.warning("No hay datos para guardar en CSV")
                return False

            # Crear directorio si no existe
            self.create_output_dir(path)

            # Hacer backup si el archivo existe
            if backup and os.path.exists(path) and self.backup_enabled:
                self._create_backup(path)

            # Obtener fieldnames si no se especifican
            if not fieldnames:
                fieldnames = list(data[0].keys())

            # Guardar CSV
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            self.logger.info(f"CSV guardado: {path}")
            return True

        except Exception as e:
            self.logger.error(f"Error guardando CSV {path}: {str(e)}")
            return False

    def load_csv(self, path: str) -> Optional[List[Dict]]:
        """
        Carga datos desde un archivo CSV.

        Args:
            path: Ruta del archivo

        Returns:
            Lista de diccionarios o None si hay error
        """
        try:
            if not os.path.exists(path):
                self.logger.warning(f"Archivo no existe: {path}")
                return None

            data = []
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)

            self.logger.info(f"CSV cargado: {path}")
            return data

        except Exception as e:
            self.logger.error(f"Error cargando CSV {path}: {str(e)}")
            return None

    def create_output_dir(self, path: str) -> bool:
        """
        Crea el directorio para una ruta de archivo si no existe.

        Args:
            path: Ruta del archivo

        Returns:
            True si se creó o ya existe
        """
        try:
            dir_path = os.path.dirname(path)

            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                self.logger.info(f"Directorio creado: {dir_path}")
                return True

            return True

        except Exception as e:
            self.logger.error(f"Error creando directorio {path}: {str(e)}")
            return False

    def _create_backup(self, path: str) -> bool:
        """
        Crea un backup de un archivo existente.

        Args:
            path: Ruta del archivo

        Returns:
            True si se creó el backup
        """
        try:
            # Crear directorio de backups
            os.makedirs(self.backup_dir, exist_ok=True)

            # Generar nombre del backup
            filename = os.path.basename(path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{os.path.splitext(filename)[0]}_{timestamp}{os.path.splitext(filename)[1]}"
            backup_path = os.path.join(self.backup_dir, backup_name)

            # Copiar archivo
            shutil.copy2(path, backup_path)
            self.logger.info(f"Backup creado: {backup_path}")
            return True

        except Exception as e:
            self.logger.warning(f"Error creando backup: {str(e)}")
            return False

    def list_files(self, directory: str, extension: Optional[str] = None) -> List[str]:
        """
        Lista archivos en un directorio.

        Args:
            directory: Ruta del directorio
            extension: Extensión de archivo a filtrar (ej: '.json')

        Returns:
            Lista de rutas de archivos
        """
        try:
            if not os.path.exists(directory):
                self.logger.warning(f"Directorio no existe: {directory}")
                return []

            files = []
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    if extension is None or item.endswith(extension):
                        files.append(item_path)

            return sorted(files)

        except Exception as e:
            self.logger.error(f"Error listando archivos {directory}: {str(e)}")
            return []

    def delete_file(self, path: str, backup: bool = True) -> bool:
        """
        Elimina un archivo (opcionalmente con backup).

        Args:
            path: Ruta del archivo
            backup: Si se debe crear backup antes de eliminar

        Returns:
            True si se eliminó correctamente
        """
        try:
            if not os.path.exists(path):
                self.logger.warning(f"Archivo no existe: {path}")
                return False

            # Hacer backup si se solicita
            if backup:
                self._create_backup(path)

            os.remove(path)
            self.logger.info(f"Archivo eliminado: {path}")
            return True

        except Exception as e:
            self.logger.error(f"Error eliminando {path}: {str(e)}")
            return False

    def copy_file(self, source: str, destination: str) -> bool:
        """
        Copia un archivo.

        Args:
            source: Ruta del archivo fuente
            destination: Ruta del archivo destino

        Returns:
            True si se copió correctamente
        """
        try:
            if not os.path.exists(source):
                self.logger.error(f"Archivo fuente no existe: {source}")
                return False

            # Crear directorio destino si es necesario
            self.create_output_dir(destination)

            shutil.copy2(source, destination)
            self.logger.info(f"Archivo copiado de {source} a {destination}")
            return True

        except Exception as e:
            self.logger.error(f"Error copiando archivo: {str(e)}")
            return False

    def move_file(self, source: str, destination: str) -> bool:
        """
        Mueve un archivo.

        Args:
            source: Ruta del archivo fuente
            destination: Ruta del archivo destino

        Returns:
            True si se movió correctamente
        """
        try:
            if not os.path.exists(source):
                self.logger.error(f"Archivo fuente no existe: {source}")
                return False

            # Crear directorio destino si es necesario
            self.create_output_dir(destination)

            shutil.move(source, destination)
            self.logger.info(f"Archivo movido de {source} a {destination}")
            return True

        except Exception as e:
            self.logger.error(f"Error moviendo archivo: {str(e)}")
            return False

    def get_file_info(self, path: str) -> Optional[Dict]:
        """
        Obtiene información de un archivo.

        Args:
            path: Ruta del archivo

        Returns:
            Diccionario con información o None
        """
        try:
            if not os.path.exists(path):
                self.logger.warning(f"Archivo no existe: {path}")
                return None

            stat_info = os.stat(path)

            return {
                'path': path,
                'name': os.path.basename(path),
                'size_bytes': stat_info.st_size,
                'size_mb': round(stat_info.st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                'is_file': os.path.isfile(path),
                'is_dir': os.path.isdir(path)
            }

        except Exception as e:
            self.logger.error(f"Error obteniendo info de {path}: {str(e)}")
            return None

    def merge_json_files(self, file_list: List[str], output_path: str) -> bool:
        """
        Merge múltiples archivos JSON en uno solo.

        Args:
            file_list: Lista de rutas de archivos JSON
            output_path: Ruta del archivo de salida

        Returns:
            True si se mergearon correctamente
        """
        try:
            merged_data = {}

            for file_path in file_list:
                data = self.load_json(file_path)
                if data:
                    if isinstance(data, dict):
                        merged_data.update(data)
                    else:
                        self.logger.warning(
                            f"Archivo {file_path} no contiene un diccionario"
                        )

            # Guardar merged data
            return self.save_json(merged_data, output_path)

        except Exception as e:
            self.logger.error(f"Error mergeando archivos JSON: {str(e)}")
            return False

    def validate_path(self, path: str) -> bool:
        """
        Valida que una ruta sea válida.

        Args:
            path: Ruta a validar

        Returns:
            True si la ruta es válida
        """
        try:
            # Convertir a Path y acceder a algunas propiedades
            p = Path(path)
            # Si llegamos aquí, la ruta es válida
            return True
        except Exception:
            return False

    def get_directory_size(self, directory: str) -> int:
        """
        Obtiene el tamaño total de un directorio.

        Args:
            directory: Ruta del directorio

        Returns:
            Tamaño en bytes
        """
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)

            return total_size

        except Exception as e:
            self.logger.error(f"Error calculando tamaño: {str(e)}")
            return 0

    def cleanup_old_files(self, directory: str, days: int = 7) -> int:
        """
        Limpia archivos más antiguos que N días.

        Args:
            directory: Directorio a limpiar
            days: Días de antigüedad

        Returns:
            Número de archivos eliminados
        """
        try:
            import time
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            deleted_count = 0

            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    if os.path.getmtime(item_path) < cutoff_time:
                        os.remove(item_path)
                        deleted_count += 1
                        self.logger.info(f"Archivo antiguo eliminado: {item_path}")

            return deleted_count

        except Exception as e:
            self.logger.error(f"Error limpiando archivos antiguos: {str(e)}")
            return 0
