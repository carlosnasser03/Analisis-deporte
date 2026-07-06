"""
video_reader.py - Abstracción para lectura de video

Este módulo proporciona una interfaz abstracta para la lectura de videos,
permitiendo abstraer la dependencia de OpenCV y facilitar el testing con mocks.

Classes:
    VideoReader: Interfaz abstracta para lectura de video
    OpenCVVideoReader: Implementación usando OpenCV

Author: Scout AI Pipeline
Date: 2026-07-06
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np
import logging


class VideoReader(ABC):
    """
    Interfaz abstracta para lectura de video.

    Define los métodos que debe implementar cualquier lector de video,
    permitiendo abstraer la dependencia específica de OpenCV.
    """

    @abstractmethod
    def open(self, path: str) -> bool:
        """
        Abre un archivo de video.

        Args:
            path (str): Ruta al archivo de video

        Returns:
            bool: True si se abrió correctamente, False en caso contrario
        """
        pass

    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Lee el siguiente frame del video.

        Returns:
            Tuple[bool, Optional[np.ndarray]]: (éxito, frame en BGR)
                - bool: True si se leyó correctamente, False si llegó al final
                - np.ndarray: Frame de video (H, W, 3) en formato BGR, o None si falló
        """
        pass

    @abstractmethod
    def set_frame_position(self, frame_number: int) -> bool:
        """
        Establece la posición actual del video.

        Args:
            frame_number (int): Número de frame a posicionarse

        Returns:
            bool: True si se posicionó correctamente
        """
        pass

    @abstractmethod
    def get_fps(self) -> float:
        """
        Obtiene los frames por segundo (FPS) del video.

        Returns:
            float: FPS del video
        """
        pass

    @abstractmethod
    def get_frame_count(self) -> int:
        """
        Obtiene el número total de frames del video.

        Returns:
            int: Número total de frames
        """
        pass

    @abstractmethod
    def get_resolution(self) -> Tuple[int, int]:
        """
        Obtiene la resolución del video.

        Returns:
            Tuple[int, int]: (ancho, alto) en píxeles
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Cierra el video y libera recursos."""
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """
        Verifica si el video está abierto.

        Returns:
            bool: True si está abierto
        """
        pass


class OpenCVVideoReader(VideoReader):
    """
    Implementación de VideoReader usando OpenCV.

    Proporciona acceso a los recursos de video a través de cv2.VideoCapture
    mientras mantiene una interfaz consistente y mockeable.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Inicializa el lector de video con OpenCV.

        Args:
            logger (Optional[logging.Logger]): Logger personalizado
        """
        import cv2
        self.cv2 = cv2
        self._cap = None
        self.logger = logger or logging.getLogger(__name__)
        self._fps = 0.0
        self._frame_count = 0
        self._width = 0
        self._height = 0

    def open(self, path: str) -> bool:
        """
        Abre un archivo de video con OpenCV.

        Args:
            path (str): Ruta al archivo de video

        Returns:
            bool: True si se abrió correctamente
        """
        try:
            self._cap = self.cv2.VideoCapture(str(path))

            if not self._cap.isOpened():
                self.logger.error(f"No se pudo abrir el video: {path}")
                return False

            # Obtener propiedades
            self._frame_count = int(self._cap.get(self.cv2.CAP_PROP_FRAME_COUNT))
            self._fps = self._cap.get(self.cv2.CAP_PROP_FPS)
            self._width = int(self._cap.get(self.cv2.CAP_PROP_FRAME_WIDTH))
            self._height = int(self._cap.get(self.cv2.CAP_PROP_FRAME_HEIGHT))

            self.logger.debug(
                f"Video abierto: {self._width}x{self._height} @ {self._fps:.1f}fps, "
                f"{self._frame_count} frames"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error abriendo video: {str(e)}")
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Lee el siguiente frame del video.

        Returns:
            Tuple[bool, Optional[np.ndarray]]: (éxito, frame)
        """
        if not self.is_opened():
            return False, None

        try:
            ret, frame = self._cap.read()
            if ret and frame is not None:
                return True, frame
            return False, None
        except Exception as e:
            self.logger.error(f"Error leyendo frame: {str(e)}")
            return False, None

    def set_frame_position(self, frame_number: int) -> bool:
        """
        Establece la posición actual del video.

        Args:
            frame_number (int): Número de frame

        Returns:
            bool: True si se posicionó correctamente
        """
        if not self.is_opened():
            return False

        try:
            self._cap.set(self.cv2.CAP_PROP_POS_FRAMES, frame_number)
            return True
        except Exception as e:
            self.logger.error(f"Error posicionando video: {str(e)}")
            return False

    def get_fps(self) -> float:
        """
        Obtiene los FPS del video.

        Returns:
            float: FPS
        """
        return self._fps

    def get_frame_count(self) -> int:
        """
        Obtiene el número total de frames.

        Returns:
            int: Número de frames
        """
        return self._frame_count

    def get_resolution(self) -> Tuple[int, int]:
        """
        Obtiene la resolución del video.

        Returns:
            Tuple[int, int]: (ancho, alto)
        """
        return self._width, self._height

    def close(self) -> None:
        """Cierra el video y libera recursos."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_opened(self) -> bool:
        """
        Verifica si el video está abierto.

        Returns:
            bool: True si está abierto
        """
        return self._cap is not None and self._cap.isOpened()

    def __del__(self):
        """Asegura que se cierren los recursos al destruir el objeto."""
        self.close()


class ColorSpaceConverter:
    """
    Abstracción para conversión de espacios de color.

    Permite convertir entre diferentes espacios de color manteniendo
    una interfaz consistente y facilitando el testing con mocks.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Inicializa el convertidor de espacios de color.

        Args:
            logger (Optional[logging.Logger]): Logger personalizado
        """
        import cv2
        self.cv2 = cv2
        self.logger = logger or logging.getLogger(__name__)

    def bgr_to_hsv(self, bgr_image: np.ndarray) -> np.ndarray:
        """
        Convierte una imagen de BGR a HSV.

        Args:
            bgr_image (np.ndarray): Imagen en formato BGR

        Returns:
            np.ndarray: Imagen en formato HSV
        """
        try:
            return self.cv2.cvtColor(bgr_image, self.cv2.COLOR_BGR2HSV)
        except Exception as e:
            self.logger.error(f"Error convirtiendo BGR a HSV: {str(e)}")
            raise

    def bgr_to_rgb(self, bgr_image: np.ndarray) -> np.ndarray:
        """
        Convierte una imagen de BGR a RGB.

        Args:
            bgr_image (np.ndarray): Imagen en formato BGR

        Returns:
            np.ndarray: Imagen en formato RGB
        """
        try:
            return self.cv2.cvtColor(bgr_image, self.cv2.COLOR_BGR2RGB)
        except Exception as e:
            self.logger.error(f"Error convirtiendo BGR a RGB: {str(e)}")
            raise

    def bgr_to_gray(self, bgr_image: np.ndarray) -> np.ndarray:
        """
        Convierte una imagen de BGR a escala de grises.

        Args:
            bgr_image (np.ndarray): Imagen en formato BGR

        Returns:
            np.ndarray: Imagen en escala de grises
        """
        try:
            return self.cv2.cvtColor(bgr_image, self.cv2.COLOR_BGR2GRAY)
        except Exception as e:
            self.logger.error(f"Error convirtiendo BGR a escala de grises: {str(e)}")
            raise


class VideoWriter(ABC):
    """
    Interfaz abstracta para escritura de video.

    Define los métodos que debe implementar cualquier escritor de video,
    permitiendo abstraer la dependencia específica de OpenCV.
    """

    @abstractmethod
    def open(self, path: str, fourcc: str, fps: float, frame_size: tuple) -> bool:
        """
        Abre un archivo de video para escritura.

        Args:
            path (str): Ruta al archivo de salida
            fourcc (str): Código de compresión (ej: 'mp4v')
            fps (float): Frames por segundo
            frame_size (tuple): Tamaño del frame (ancho, alto)

        Returns:
            bool: True si se abrió correctamente
        """
        pass

    @abstractmethod
    def write_frame(self, frame: np.ndarray) -> bool:
        """
        Escribe un frame en el video.

        Args:
            frame (np.ndarray): Frame en formato BGR (H, W, 3)

        Returns:
            bool: True si se escribió correctamente
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Cierra el video y libera recursos."""
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """
        Verifica si el video está abierto para escritura.

        Returns:
            bool: True si está abierto
        """
        pass


class OpenCVVideoWriter(VideoWriter):
    """
    Implementación de VideoWriter usando OpenCV.

    Proporciona acceso a la escritura de video a través de cv2.VideoWriter
    mientras mantiene una interfaz consistente.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Inicializa el escritor de video con OpenCV.

        Args:
            logger (Optional[logging.Logger]): Logger personalizado
        """
        import cv2
        self.cv2 = cv2
        self._writer = None
        self.logger = logger or logging.getLogger(__name__)

    def open(self, path: str, fourcc: str, fps: float, frame_size: tuple) -> bool:
        """
        Abre un archivo de video para escritura con OpenCV.

        Args:
            path (str): Ruta al archivo de salida
            fourcc (str): Código de compresión (ej: 'mp4v')
            fps (float): Frames por segundo
            frame_size (tuple): Tamaño del frame (ancho, alto)

        Returns:
            bool: True si se abrió correctamente
        """
        try:
            # Convertir fourcc string a código
            fourcc_code = self.cv2.VideoWriter_fourcc(*fourcc)
            self._writer = self.cv2.VideoWriter(
                str(path),
                fourcc_code,
                fps,
                frame_size
            )

            if not self._writer.isOpened():
                self.logger.error(f"No se pudo abrir video para escritura: {path}")
                return False

            self.logger.debug(f"Video abierto para escritura: {path}")
            return True

        except Exception as e:
            self.logger.error(f"Error abriendo video para escritura: {str(e)}")
            return False

    def write_frame(self, frame: np.ndarray) -> bool:
        """
        Escribe un frame en el video.

        Args:
            frame (np.ndarray): Frame en formato BGR

        Returns:
            bool: True si se escribió correctamente
        """
        if not self.is_opened():
            return False

        try:
            self._writer.write(frame)
            return True
        except Exception as e:
            self.logger.error(f"Error escribiendo frame: {str(e)}")
            return False

    def close(self) -> None:
        """Cierra el video y libera recursos."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def is_opened(self) -> bool:
        """
        Verifica si el video está abierto para escritura.

        Returns:
            bool: True si está abierto
        """
        return self._writer is not None and self._writer.isOpened()

    def __del__(self):
        """Asegura que se cierren los recursos al destruir el objeto."""
        self.close()
