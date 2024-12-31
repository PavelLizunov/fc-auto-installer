import os
import shutil
import socket
import zipfile
import tarfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
from PyQt5 import QtWidgets, QtCore
import sys
import threading

# Configuration
IGNORED_FILES = ["options.txt", "servers.dat"]
IGNORED_FOLDERS = ["saves"]
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "fc-auto-installer-3b84891aacd2.json")

# Utility functions
def check_internet_connection():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

def extract_file_id(url):
    if "drive.google.com" in url and "/file/d/" in url:
        return url.split("/file/d/")[-1].split("/")[0]
    elif "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    else:
        raise ValueError("Invalid Google Drive URL format.")

def get_drive_service():
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        service = build('drive', 'v3', credentials=credentials)
        return service
    except FileNotFoundError:
        raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
    except Exception as e:
        raise Exception(f"Error creating Google Drive service: {e}")

def download_file(service, file_id, save_folder, progress_callback):
    file = service.files().get(fileId=file_id, fields="name, size").execute()
    file_name = file.get("name", "downloaded_file")
    file_size = int(file.get("size", 0))

    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join(save_folder, file_name)

    with open(file_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False

        while not done:
            status, done = downloader.next_chunk()
            progress = int(status.progress() * 100)
            progress_callback(progress)

    return file_path

def extract_archive(file_path, extract_to, overwrite=True, progress_callback=None):
    temp_extract_folder = os.path.join(extract_to, "temp_extract")
    os.makedirs(temp_extract_folder, exist_ok=True)

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

    minecraft_folder = os.path.join(temp_extract_folder, ".minecraft")
    if not os.path.exists(minecraft_folder):
        raise FileNotFoundError(".minecraft folder not found in the archive.")

    for item in os.listdir(minecraft_folder):
        src_path = os.path.join(minecraft_folder, item)
        dest_path = os.path.join(extract_to, item)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path, dirs_exist_ok=overwrite)
        else:
            shutil.copy2(src_path, dest_path)

    shutil.rmtree(temp_extract_folder)
    return "Archive extracted and .minecraft contents moved successfully."

class MinecraftInstallerUI(QtWidgets.QTabWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft Installer")
        self.setMinimumSize(500, 400)
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

        self.download_tab.setLayout(layout)

    def setup_logs_tab(self):
        layout = QtWidgets.QVBoxLayout()

        self.log_area = QtWidgets.QListWidget()
        layout.addWidget(self.log_area)

        self.logs_tab.setLayout(layout)

    def log_message(self, message):
        self.log_area.addItem(message)
        self.log_area.scrollToBottom()

    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select save folder")
        if folder:
            self.selected_folder = folder

    def start_download_and_extract(self):
        url = self.url_input.text()
        if not self.validate_url(url):
            self.log_message("Invalid URL")
            return
        if not hasattr(self, 'selected_folder') or not os.path.isdir(self.selected_folder):
            self.log_message("Invalid folder")
            return

        self.log_message("Starting download and extract process...")
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Downloading")
        self.toggle_buttons(False)
        self.worker = threading.Thread(target=self.run_download_and_extract, args=(url, self.selected_folder))
        self.worker.start()

    def start_extract_only(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select an archive to extract", filter="Archives (*.zip *.tar *.tar.gz *.tgz)")

        if not hasattr(self, 'selected_folder') or not os.path.isdir(self.selected_folder):
            self.log_message("Invalid folder")
            return
        if not file_path:
            self.log_message("Invalid archive")
            return

        self.log_message("Starting extraction process...")
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Extracting")
        self.toggle_buttons(False)
        self.worker = threading.Thread(target=self.run_extract_only, args=(file_path, self.selected_folder))
        self.worker.start()

    def toggle_buttons(self, enable):
        self.url_input.setEnabled(enable)
        self.select_folder_button.setEnabled(enable)
        self.download_button.setEnabled(enable)
        self.extract_button.setEnabled(enable)

    def validate_url(self, url):
        return url.startswith("https://") and "drive.google.com" in url

    def run_download_and_extract(self, url, save_folder):
        try:
            service = get_drive_service()
            file_id = extract_file_id(url)
            file_path = download_file(service, file_id, save_folder, self.update_progress_bar)
            self.log_message(f"Downloaded: {file_path}")
            self.progress_bar.setValue(0)
            self.status_label.setText("Status: Extracting")
            self.extract_archive(file_path, save_folder)
        except Exception as e:
            self.log_message(f"Error during download and extract: {str(e)}")
        finally:
            self.toggle_buttons(True)

    def run_extract_only(self, file_path, save_folder):
        try:
            self.extract_archive(file_path, save_folder)
        except Exception as e:
            self.log_message(f"Error during extraction: {str(e)}")
        finally:
            self.toggle_buttons(True)

    def extract_archive(self, file_path, save_folder):
        try:
            extract_archive(file_path, save_folder, progress_callback=self.update_progress_bar)
            self.log_message("Extraction completed successfully.")
        except Exception as e:
            self.log_message(f"Extraction error: {str(e)}")

    def update_progress_bar(self, value):
        self.progress_bar.setValue(value)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MinecraftInstallerUI()
    window.show()
    sys.exit(app.exec_())
