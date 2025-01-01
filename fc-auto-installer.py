import os
import sys
import shutil
import socket
import zipfile
import tarfile
import tempfile
import logging

from typing import Optional, Callable, List
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QFontDatabase, QIcon, QFont, QPixmap, QPainter
from PyQt5.QtCore import Qt, QRect

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class QtLogHandler(logging.Handler):
    """
    Логгирование в QListWidget (Logs).
    """
    def __init__(self, list_widget: QtWidgets.QListWidget):
        super().__init__()
        self.list_widget = list_widget

    def emit(self, record):
        msg = self.format(record)
        # Добавляем сообщение в QListWidget
        self.list_widget.addItem(msg)
        self.list_widget.scrollToBottom()

# ==================== Константы / Настройки ====================

ARCHIVE_EXTENSIONS = (".zip", ".tar", ".tar.gz", ".tgz", ".rar")
MODS_FOLDERS = ["mods", "configs"]  # Папки, которые удаляем из main
MC_FILES_TO_REMOVE = ["options.txt", "server.dat"]  # Файлы, удаляемые в tmp/.minecraft, ЕСЛИ есть такие же в main

# ==================== Вспомогательные функции ====================

def check_internet_connection() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

def extract_file_id(url: str) -> str:
    if "drive.google.com" in url and "/file/d/" in url:
        return url.split("/file/d/")[-1].split("/")[0]
    elif "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    else:
        raise ValueError("Invalid Google Drive URL format.")

def get_drive_service(service_account_file: str):
    try:
        credentials = Credentials.from_service_account_file(service_account_file)
        service = build('drive', 'v3', credentials=credentials)
        return service
    except FileNotFoundError:
        raise FileNotFoundError(f"Service account file not found: {service_account_file}")
    except Exception as e:
        raise Exception(f"Error creating Google Drive service: {e}")

def download_file(service,
                  file_id: str,
                  save_folder: str,
                  progress_callback: Callable[[int], None]) -> str:
    file_info = service.files().get(fileId=file_id, fields="name, size").execute()
    file_name = file_info.get("name", "downloaded_file")
    file_size = int(file_info.get("size", 0)) if file_info.get("size") else 0

    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join(save_folder, file_name)

    with open(file_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        last_progress_sent = 0
        while not done:
            status, done = downloader.next_chunk()
            if status:
                current_progress = int(status.progress() * 100)
                if current_progress - last_progress_sent >= 2:
                    progress_callback(current_progress)
                    last_progress_sent = current_progress

    return file_path

# ==================== QThread-классы (Workers) ====================

class DownloadWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    message = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, url: str, save_folder: str, service_account_file: str):
        super().__init__()
        self.url = url
        self.save_folder = save_folder
        self.service_account_file = service_account_file

    def run(self):
        try:
            service = get_drive_service(self.service_account_file)
            file_id = extract_file_id(self.url)
            file_path = download_file(
                service=service,
                file_id=file_id,
                save_folder=self.save_folder,
                progress_callback=self.on_progress
            )
            self.finished_ok.emit(file_path)
        except Exception as e:
            self.failed.emit(str(e))

    def on_progress(self, value: int):
        self.progress.emit(value)

class ExtractWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    message = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal(str)

    def __init__(self,
                 file_path: str,
                 extract_folder: str,
                 ignored_files: List[str],
                 ignored_folders: List[str],
                 keep_in_main: List[str]):
        super().__init__()
        self.file_path = file_path
        self.extract_folder = extract_folder
        self.ignored_files = ignored_files
        self.ignored_folders = ignored_folders
        self.keep_in_main = keep_in_main

    def run(self):
        try:
            self.custom_install_process()
            self.message.emit("Installation steps completed successfully.")
            self.finished_ok.emit()
        except Exception as e:
            self.failed.emit(str(e))

    def on_progress(self, value: int):
        self.progress.emit(value)

    def custom_install_process(self):
        """
        1) Создаём папку tmp
        2) Распаковываем архив => tmp
        3) Удаляем mods/, configs/ в main
        4) Удаляем options.txt/server.dat в tmp/.minecraft, но только если они есть в main
        5) Копируем tmp/.minecraft => main (overwrite)
        6) Удаляем tmp (и при желании — сам архив)
        """
        main_dir = self.extract_folder
        archive_path = self.file_path

        # 1. Папка tmp
        tmp_dir = os.path.join(main_dir, "tmp")
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        # 2. Распаковать архива => tmp
        self.extract_to_tmp(archive_path, tmp_dir)

        # 3. Удаляем mods/, configs/ из main
        self.remove_mods_folders_in_main(main_dir, MODS_FOLDERS)

        # 4. Удаляем options.txt/server.dat в tmp/.minecraft, если они есть в main
        self.remove_files_in_minecraft_if_in_main(tmp_dir, main_dir, MC_FILES_TO_REMOVE)

        # 5. Копируем tmp/.minecraft => main
        self.copy_minecraft_to_main(tmp_dir, main_dir)

        # 6. Удаляем tmp
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # (Если хотите удалять архив — раскомментируйте)
        # os.remove(archive_path)

    def extract_to_tmp(self, archive_path: str, tmp_dir: str):
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                all_files = zip_ref.namelist()
                total = len(all_files)
                for i, member in enumerate(all_files):
                    zip_ref.extract(member, tmp_dir)
                    percent = int((i + 1) / total * 100)
                    self.on_progress(percent)
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, "r:*") as tar_ref:
                all_members = tar_ref.getmembers()
                total = len(all_members)
                for i, member in enumerate(all_members):
                    tar_ref.extract(member, tmp_dir)
                    percent = int((i + 1) / total * 100)
                    self.on_progress(percent)
        else:
            raise ValueError("Unsupported archive format.")

        # Проверка на наличие .minecraft
        mc_path = os.path.join(tmp_dir, ".minecraft")
        if not os.path.exists(mc_path):
            raise FileNotFoundError("No .minecraft folder found inside the archive.")

    def remove_mods_folders_in_main(self, main_dir: str, folders: List[str]):
        for folder_name in folders:
            path_ = os.path.join(main_dir, folder_name)
            if os.path.isdir(path_):
                shutil.rmtree(path_, ignore_errors=True)
                logger.info(f"Removed folder: {path_}")

    def remove_files_in_minecraft_if_in_main(self, tmp_dir: str, main_dir: str, files_to_remove: List[str]):
        """
        Удаляем указанные файлы из tmp/.minecraft ТОЛЬКО ЕСЛИ аналогичные есть в main_dir.
        """
        mc_path = os.path.join(tmp_dir, ".minecraft")
        if not os.path.exists(mc_path):
            return

        for fname in files_to_remove:
            main_path = os.path.join(main_dir, fname)
            # Проверяем, есть ли такой файл в main_dir:
            if not os.path.exists(main_path):
                # значит не удаляем его в tmp
                continue

            # Если в main есть, то удаляем во всём tmp/.minecraft
            for root, dirs, files in os.walk(mc_path, topdown=True):
                if fname in files:
                    f_path = os.path.join(root, fname)
                    os.remove(f_path)
                    logger.info(f"Removed file in tmp: {f_path}")

    def copy_minecraft_to_main(self, tmp_dir: str, main_dir: str):
        mc_path = os.path.join(tmp_dir, ".minecraft")
        if not os.path.exists(mc_path):
            return
        for item in os.listdir(mc_path):
            src = os.path.join(mc_path, item)
            dst = os.path.join(main_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        logger.info(f"Copied .minecraft contents from {mc_path} to {main_dir}")

# ===================== Класс бескаркасного окна =====================
class FramelessMainWindow(QtWidgets.QMainWindow):
    """
    Модель «бескаркасного» окна с кастомным заголовком, который можно перетаскивать.
    """
    def __init__(self, parent=None):
        super().__init__(parent, flags=Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self._old_pos = None

        # Устанавливаем тёмный фон самого окна
        self.setStyleSheet("background-color: #2F2F2F;")
        self.setWindowTitle("Minecraft Installer (MC-Style) [Frameless]")
        self.setWindowIcon(QIcon("assets/minecraft_icon.png"))

        # Кнопки заголовка
        self.title_bar = QtWidgets.QWidget(self)
        self.title_bar.setObjectName("title_bar")
        self.title_bar.setStyleSheet("background-color: #2F2F2F; color: #FFFFFF;")
        self.title_bar.setFixedHeight(40)

        self.title_layout = QtWidgets.QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(5, 0, 5, 0)
        self.title_layout.setSpacing(5)

        # Кнопка "Закрыть"
        self.close_button = QtWidgets.QPushButton("X", self.title_bar)
        self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(self.close)

        # Кнопка "Свернуть"
        self.min_button = QtWidgets.QPushButton("-", self.title_bar)
        self.min_button.setFixedSize(30, 30)
        self.min_button.clicked.connect(self.showMinimized)

        # Заголовок (текст)
        self.title_label = QtWidgets.QLabel("Minecraft Installer (Frameless)", self.title_bar)
        self.title_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")

        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch(1)
        self.title_layout.addWidget(self.min_button)
        self.title_layout.addWidget(self.close_button)

        # Основной layout
        self.main_widget = QtWidgets.QWidget(self)
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Добавляем title_bar + содержимое
        self.main_layout.addWidget(self.title_bar)

        # Далее создаём QTabWidget (с «MC-Style» UI)
        self.tab_widget = MinecraftInstallerUI()
        # Добавляем QTabWidget
        self.main_layout.addWidget(self.tab_widget)

        self.setCentralWidget(self.main_widget)
        self.setMinimumSize(600, 500)

    def mousePressEvent(self, event):
        """
        Для перетаскивания окна — если нажали в title_bar (не на кнопки).
        """
        if event.button() == Qt.LeftButton:
            # Проверяем, где нажали
            if event.pos().y() <= self.title_bar.height():
                self._old_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._old_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._old_pos is not None:
            delta = QtCore.QPoint(event.globalPos() - self._old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._old_pos = event.globalPos()
        super().mouseMoveEvent(event)

# ==================== Основной класс (QTabWidget) ====================
class MinecraftInstallerUI(QtWidgets.QTabWidget):
    def __init__(self):
        super().__init__()
        # Ниже вся логика вкладок, стилизации и т. п.
        # (Практически та же, что была в предыдущих примерах.)

        self.setStyleSheet("""
            QTabWidget::pane {
                background-color: #3B3B3B;
                border: 2px solid #000;
            }
            QTabBar::tab {
                background: #4F4F4F;
                color: #FFFFFF;
                padding: 8px;
                border: 1px solid #222;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #7F7F7F;
            }
            QWidget {
                background-color: #2F2F2F;
                color: #FFFFFF;
            }
            QLineEdit {
                background-color: #444444;
                border: 1px solid #888;
                padding: 4px;
            }
            QPlainTextEdit {
                background-color: #444444;
                border: 1px solid #888;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #666666;
                border: 1px solid #888;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #999999;
            }
            QProgressBar {
                background-color: #444444;
                border: 1px solid #888;
                text-align: center;
                color: #fff;
            }
            QProgressBar::chunk {
                background-color: #06B025; 
            }
            QMessageBox {
                background-color: #2F2F2F;
            }
        """)

        # Параметры по умолчанию
        self.ignored_files: List[str] = ["options.txt", "servers.dat"]
        self.ignored_folders: List[str] = ["logs"]
        self.keep_in_main:  List[str] = ["saves", "xaero", "distant_horizons_server_data"]

        self.service_account_file = os.path.join(
            os.path.dirname(__file__),
            "fc-auto-installer-3b84891aacd2.json"
        )

        # Лог-виджет
        self.log_area = QtWidgets.QListWidget()
        self.log_handler = QtLogHandler(self.log_area)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        logger.addHandler(self.log_handler)

        self.selected_folder = ""

        self.init_ui()

    def init_ui(self):
        self.download_tab = QtWidgets.QWidget()
        self.logs_tab = QtWidgets.QWidget()
        self.exclusions_tab = QtWidgets.QWidget()

        self.addTab(self.download_tab, "Download/Extract")
        self.addTab(self.logs_tab, "Logs")
        self.addTab(self.exclusions_tab, "Exclusions")

        self.setup_download_tab()
        self.setup_logs_tab()
        self.setup_exclusions_tab()

    def setup_download_tab(self):
        layout = QtWidgets.QVBoxLayout()

        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.url_input.setPlaceholderText("Enter Google Drive URL (hidden)")
        layout.addWidget(self.url_input)

        self.select_folder_button = QtWidgets.QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.select_folder)
        layout.addWidget(self.select_folder_button)

        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)

        self.status_label = QtWidgets.QLabel("Status: Idle")
        layout.addWidget(self.status_label)

        self.download_button = QtWidgets.QPushButton("Download and Extract")
        self.download_button.clicked.connect(self.start_download_and_extract)
        layout.addWidget(self.download_button)

        self.extract_button = QtWidgets.QPushButton("Extract Only")
        self.extract_button.clicked.connect(self.start_extract_only)
        layout.addWidget(self.extract_button)

        layout.addStretch()
        self.download_tab.setLayout(layout)

    def setup_logs_tab(self):
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.log_area)
        self.logs_tab.setLayout(layout)

    def setup_exclusions_tab(self):
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(QtWidgets.QLabel("Ignored Files (one per line):"))
        self.ignored_files_edit = QtWidgets.QPlainTextEdit("\n".join(self.ignored_files))
        layout.addWidget(self.ignored_files_edit)

        layout.addWidget(QtWidgets.QLabel("Ignored Folders (one per line):"))
        self.ignored_folders_edit = QtWidgets.QPlainTextEdit("\n".join(self.ignored_folders))
        layout.addWidget(self.ignored_folders_edit)

        layout.addWidget(QtWidgets.QLabel("Keep in Main (substrings, one per line):"))
        self.keep_in_main_edit = QtWidgets.QPlainTextEdit("\n".join(self.keep_in_main))
        layout.addWidget(self.keep_in_main_edit)

        save_button = QtWidgets.QPushButton("Save Exclusions")
        save_button.clicked.connect(self.save_exclusions)
        layout.addWidget(save_button)

        layout.addStretch()
        self.exclusions_tab.setLayout(layout)

    # ----------------- СЛОТЫ/ОБРАБОТЧИКИ -----------------

    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder (main)")
        if folder:
            self.selected_folder = folder
            logger.info(f"Selected folder: {folder}")

    def start_download_and_extract(self):
        url = self.url_input.text()
        if not self.validate_url(url):
            logger.error("Invalid Google Drive URL.")
            return

        if not os.path.isdir(self.selected_folder):
            logger.error("Invalid folder selected.")
            return

        if not check_internet_connection():
            logger.error("No internet connection detected.")
            return

        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Downloading...")
        self.toggle_buttons(False)

        self.download_worker = DownloadWorker(url, self.selected_folder, self.service_account_file)
        self.download_worker.progress.connect(self.update_progress_bar)
        self.download_worker.message.connect(lambda msg: logger.info(msg))
        self.download_worker.finished_ok.connect(self.on_download_finished_ok)
        self.download_worker.failed.connect(self.on_download_failed)
        self.download_worker.start()

    def on_download_finished_ok(self, file_path: str):
        logger.info(f"Downloaded file: {file_path}")
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Extracting...")

        self.extract_worker = ExtractWorker(
            file_path=file_path,
            extract_folder=self.selected_folder,
            ignored_files=self.ignored_files,
            ignored_folders=self.ignored_folders,
            keep_in_main=self.keep_in_main
        )
        self.extract_worker.progress.connect(self.update_progress_bar)
        self.extract_worker.message.connect(lambda msg: logger.info(msg))
        self.extract_worker.finished_ok.connect(self.on_extract_finished_ok)
        self.extract_worker.failed.connect(self.on_extract_failed)
        self.extract_worker.start()

    def on_download_failed(self, error_str: str):
        logger.error(f"Download failed: {error_str}")
        self.status_label.setText("Status: Download failed.")
        self.toggle_buttons(True)

    def on_extract_finished_ok(self):
        logger.info("Extraction completed successfully.")
        self.status_label.setText("Status: Done")
        self.toggle_buttons(True)

    def on_extract_failed(self, error_str: str):
        logger.error(f"Extraction failed: {error_str}")
        self.status_label.setText("Status: Extraction failed.")
        self.toggle_buttons(True)

    def start_extract_only(self):
        if not os.path.isdir(self.selected_folder):
            logger.error("Invalid folder selected.")
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select an archive to extract",
            filter="Archives (*.zip *.tar *.tar.gz *.tgz *.rar)"
        )
        if not file_path:
            logger.error("No archive selected.")
            return

        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Extracting...")
        self.toggle_buttons(False)

        self.extract_worker = ExtractWorker(
            file_path=file_path,
            extract_folder=self.selected_folder,
            ignored_files=self.ignored_files,
            ignored_folders=self.ignored_folders,
            keep_in_main=self.keep_in_main
        )
        self.extract_worker.progress.connect(self.update_progress_bar)
        self.extract_worker.message.connect(lambda msg: logger.info(msg))
        self.extract_worker.finished_ok.connect(self.on_extract_finished_ok)
        self.extract_worker.failed.connect(self.on_extract_failed)
        self.extract_worker.start()

    def toggle_buttons(self, enable: bool):
        self.url_input.setEnabled(enable)
        self.select_folder_button.setEnabled(enable)
        self.download_button.setEnabled(enable)
        self.extract_button.setEnabled(enable)

    def update_progress_bar(self, value: int):
        self.progress_bar.setValue(value)

    def validate_url(self, url: str) -> bool:
        return url.startswith("https://") and "drive.google.com" in url

    def save_exclusions(self):
        files_text = self.ignored_files_edit.toPlainText().strip()
        folders_text = self.ignored_folders_edit.toPlainText().strip()
        keep_text = self.keep_in_main_edit.toPlainText().strip()

        self.ignored_files = [line.strip() for line in files_text.splitlines() if line.strip()]
        self.ignored_folders = [line.strip() for line in folders_text.splitlines() if line.strip()]
        self.keep_in_main = [line.strip() for line in keep_text.splitlines() if line.strip()]

        logger.info("Exclusions updated:")
        logger.info(f"  Ignored files: {self.ignored_files}")
        logger.info(f"  Ignored folders: {self.ignored_folders}")
        logger.info(f"  Keep in main:  {self.keep_in_main}")

        QtWidgets.QMessageBox.information(self, "Exclusions", "Exclusions have been saved successfully.")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    # Запускаем бескаркасное окно
    window = FramelessMainWindow()
    window.show()

    sys.exit(app.exec_())
