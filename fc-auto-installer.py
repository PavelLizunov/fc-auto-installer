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

# ==================== Конфигурация ====================

# Файлы, которые надо удалить из .minecraft перед копированием
IGNORED_FILES = ["options.txt", "servers.dat"]

# Папки, которые надо удалить из .minecraft перед копированием
IGNORED_FOLDERS = ["logs"]  # Можно дополнить своими

# Логика, какие элементы НЕ удаляем в корневой папке
def should_keep_in_main(item_name: str) -> bool:
    lower_name = item_name.lower()
    if lower_name == "saves":
        return True
    if "xaero" in lower_name:
        return True
    if "distant_horizons_server_data" in lower_name:
        return True
    return False

# Путь к JSON с учетными данными Google
SERVICE_ACCOUNT_FILE = os.path.join(
    os.path.dirname(__file__),
    "fc-auto-installer-3b84891aacd2.json"
)

# ==================== Логгирование ====================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class QtLogHandler(logging.Handler):
    """
    Перехватывает логи и отправляет их в QListWidget.
    """
    def __init__(self, list_widget: QtWidgets.QListWidget):
        super().__init__()
        self.list_widget = list_widget

    def emit(self, record):
        msg = self.format(record)
        # В PyQt обновления GUI должны выполняться в основном потоке,
        # поэтому используем сигнал через invokeMethod или прямое соединение.
        # Но в простом случае можно и напрямую добавлять:
        self.list_widget.addItem(msg)
        self.list_widget.scrollToBottom()

# ==================== Вспомогательные функции ====================

def check_internet_connection() -> bool:
    """
    Пример проверки сети. Если 8.8.8.8 недоступен, 
    у некоторых пользователей будет ложное срабатывание.
    """
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

def extract_file_id(url: str) -> str:
    """
    Извлекает file_id из Google Drive URL.
    """
    if "drive.google.com" in url and "/file/d/" in url:
        return url.split("/file/d/")[-1].split("/")[0]
    elif "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    else:
        raise ValueError("Invalid Google Drive URL format.")

def get_drive_service():
    """
    Создаём сервис для Google Drive API.
    """
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        service = build('drive', 'v3', credentials=credentials)
        return service
    except FileNotFoundError:
        raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
    except Exception as e:
        raise Exception(f"Error creating Google Drive service: {e}")

def remove_items_in_main_dir(folder_path: str) -> None:
    """
    Удаляет все элементы из корневой папки folder_path,
    кроме тех, что проходят проверку should_keep_in_main().
    """
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if not should_keep_in_main(item):
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

def clean_extracted_minecraft(minecraft_folder: str) -> None:
    """
    Удаляет нежелательные файлы/папки из распакованной .minecraft
    (IGNORED_FILES, IGNORED_FOLDERS).
    """
    for root, dirs, files in os.walk(minecraft_folder, topdown=True):
        # Удаляем файлы из IGNORED_FILES
        for fname in files:
            if fname in IGNORED_FILES:
                fpath = os.path.join(root, fname)
                os.remove(fpath)

        # Удаляем папки из IGNORED_FOLDERS
        dirs_to_remove = []
        for dname in dirs:
            if dname in IGNORED_FOLDERS:
                dirs_to_remove.append(dname)

        for dname in dirs_to_remove:
            dpath = os.path.join(root, dname)
            shutil.rmtree(dpath)
            dirs.remove(dname)

def extract_archive(file_path: str,
                    extract_to: str,
                    overwrite: bool = True,
                    progress_callback: Optional[Callable[[int], None]] = None) -> str:
    """
    Распаковывает архив во временную папку, чистит .minecraft,
    чистит корневую папку от всего, кроме исключений, затем
    копирует содержимое .minecraft в корневую папку extract_to.
    """
    # Создаём временную папку (настоящую system temp directory)
    temp_extract_folder = tempfile.mkdtemp(prefix="mc_installer_")

    try:
        # Определяем тип архива и распаковываем
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                files = zip_ref.namelist()
                total_files = len(files)
                for i, file in enumerate(files):
                    zip_ref.extract(file, temp_extract_folder)
                    if progress_callback:
                        progress_callback(int((i + 1) / total_files * 100))

        elif tarfile.is_tarfile(file_path):
            with tarfile.open(file_path, 'r:*') as tar_ref:
                members = tar_ref.getmembers()
                total_members = len(members)
                for i, member in enumerate(members):
                    tar_ref.extract(member, temp_extract_folder)
                    if progress_callback:
                        progress_callback(int((i + 1) / total_members * 100))
        else:
            raise ValueError("Unsupported archive format.")

        # Проверяем, что в архиве есть .minecraft
        minecraft_folder = os.path.join(temp_extract_folder, ".minecraft")
        if not os.path.exists(minecraft_folder):
            raise FileNotFoundError(".minecraft folder not found in the archive.")

        # Удаляем из распакованной .minecraft ненужные файлы/папки
        clean_extracted_minecraft(minecraft_folder)

        # Удаляем всё лишнее из корневой папки (extract_to), кроме исключений
        remove_items_in_main_dir(extract_to)

        # Копируем содержимое .minecraft в корневую папку
        for item in os.listdir(minecraft_folder):
            src_path = os.path.join(minecraft_folder, item)
            dest_path = os.path.join(extract_to, item)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path, dirs_exist_ok=overwrite)
            else:
                shutil.copy2(src_path, dest_path)

        return "Archive extracted and .minecraft contents moved successfully."

    except Exception as e:
        # Здесь можно реализовать логику отката (rollback), если нужно:
        #   - например, вернуть удалённые файлы обратно из корневой папки,
        #   - удалить уже скопированные файлы и т.д.
        raise e
    finally:
        # Удаляем временную папку
        shutil.rmtree(temp_extract_folder, ignore_errors=True)

def download_file(service,
                  file_id: str,
                  save_folder: str,
                  progress_callback: Callable[[int], None]) -> str:
    """
    Скачивает файл с Google Drive, обновляя прогресс через progress_callback.
    """
    file = service.files().get(fileId=file_id, fields="name, size").execute()
    file_name = file.get("name", "downloaded_file")
    file_size = int(file.get("size", 0)) if file.get("size") else 0

    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join(save_folder, file_name)

    with open(file_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        last_progress_sent = 0
        while not done:
            status, done = downloader.next_chunk()
            if status:
                # Порой Google не отдаёт точный размер, 
                # но если всё ок, можно использовать int(status.progress()*100).
                current_progress = int(status.progress() * 100)
                # Чтобы не слишком часто дёргать UI, можно слать обновление реже
                if current_progress - last_progress_sent >= 2:
                    progress_callback(current_progress)
                    last_progress_sent = current_progress

    return file_path

# ==================== QThread-классы (Workers) ====================

class DownloadWorker(QtCore.QThread):
    """
    Фоновый поток для скачивания архива.
    """
    progress = QtCore.pyqtSignal(int)
    message = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal(str)  # Вернём путь к файлу
    failed = QtCore.pyqtSignal(str)

    def __init__(self, url: str, save_folder: str):
        super().__init__()
        self.url = url
        self.save_folder = save_folder

    def run(self):
        try:
            service = get_drive_service()
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
    """
    Фоновый поток для распаковки архива и копирования.
    """
    progress = QtCore.pyqtSignal(int)
    message = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal(str)

    def __init__(self, file_path: str, extract_folder: str):
        super().__init__()
        self.file_path = file_path
        self.extract_folder = extract_folder

    def run(self):
        try:
            result = extract_archive(
                file_path=self.file_path,
                extract_to=self.extract_folder,
                progress_callback=self.on_progress
            )
            self.message.emit(result)
            self.finished_ok.emit()
        except Exception as e:
            self.failed.emit(str(e))

    def on_progress(self, value: int):
        self.progress.emit(value)

# ==================== Основной GUI-класс ====================

class MinecraftInstallerUI(QtWidgets.QTabWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft Installer (Refactored)")
        self.setMinimumSize(500, 400)

        # Лог-виджет
        self.log_area = QtWidgets.QListWidget()
        # Создаём и добавляем наш обработчик логов
        self.log_handler = QtLogHandler(self.log_area)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        logger.addHandler(self.log_handler)

        self.init_ui()

    def init_ui(self):
        self.download_tab = QtWidgets.QWidget()
        self.logs_tab = QtWidgets.QWidget()

        self.addTab(self.download_tab, "Download/Extract")
        self.addTab(self.logs_tab, "Logs")

        self.setup_download_tab()
        self.setup_logs_tab()

    def setup_download_tab(self):
        layout = QtWidgets.QVBoxLayout()

        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setPlaceholderText("Enter Google Drive URL")
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

    # =========================================
    #      Слот-методы для GUI
    # =========================================

    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder to install .minecraft")
        if folder:
            self.selected_folder = folder
            logger.info(f"Selected folder: {folder}")

    def start_download_and_extract(self):
        """
        Кнопка "Download and Extract"
        """
        url = self.url_input.text()
        if not self.validate_url(url):
            logger.error("Invalid Google Drive URL.")
            return

        if not hasattr(self, 'selected_folder') or not os.path.isdir(self.selected_folder):
            logger.error("Invalid folder selected.")
            return

        # Проверяем интернет (опционально)
        if not check_internet_connection():
            logger.error("No internet connection detected.")
            return

        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Downloading...")
        self.toggle_buttons(False)

        # 1. Скачиваем
        self.download_worker = DownloadWorker(url, self.selected_folder)
        self.download_worker.progress.connect(self.update_progress_bar)
        self.download_worker.message.connect(lambda msg: logger.info(msg))
        self.download_worker.finished_ok.connect(self.on_download_finished_ok)
        self.download_worker.failed.connect(self.on_download_failed)
        self.download_worker.start()

    def on_download_finished_ok(self, file_path: str):
        """
        Вызывается, когда загрузка успешно завершена.
        Делаем второй этап — распаковку.
        """
        logger.info(f"Downloaded file: {file_path}")
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Extracting...")

        self.extract_worker = ExtractWorker(file_path, self.selected_folder)
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
        """
        Кнопка "Extract Only"
        """
        if not hasattr(self, 'selected_folder') or not os.path.isdir(self.selected_folder):
            logger.error("Invalid folder selected.")
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select an archive to extract",
            filter="Archives (*.zip *.tar *.tar.gz *.tgz)"
        )
        if not file_path:
            logger.error("No archive selected.")
            return

        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Extracting...")
        self.toggle_buttons(False)

        self.extract_worker = ExtractWorker(file_path, self.selected_folder)
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

# ==================== Запуск приложения ====================

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MinecraftInstallerUI()
    window.show()
    sys.exit(app.exec_())
