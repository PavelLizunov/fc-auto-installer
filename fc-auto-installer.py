import os
import shutil
import socket
import zipfile
import tarfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
from PyQt5 import QtWidgets, QtCore, QtGui
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

class MinecraftInstallerUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Minecraft Auto Installer")
        self.setStyleSheet("background-color: #2b2b2b; color: white;")
        self.setFixedSize(500, 400)

        layout = QtWidgets.QVBoxLayout()

        title_font = QtGui.QFont("Minecraft", 16, QtGui.QFont.Bold)
        title_label = QtWidgets.QLabel("Minecraft Auto Installer")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # URL input
        self.url_label = QtWidgets.QLabel("Enter download URL:")
        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setStyleSheet("background-color: #454545; color: white;")
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)

        # Save folder selection
        self.folder_label = QtWidgets.QLabel("Select save folder:")
        self.folder_input = QtWidgets.QLineEdit()
        self.folder_input.setStyleSheet("background-color: #454545; color: white;")
        self.folder_button = QtWidgets.QPushButton("Select")
        self.folder_button.clicked.connect(self.select_folder)
        self.folder_button.setStyleSheet("background-color: #606060; color: white;")

        folder_layout = QtWidgets.QHBoxLayout()
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_button)

        layout.addWidget(self.folder_label)
        layout.addLayout(folder_layout)

        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { border: 2px solid grey; text-align: center; } QProgressBar::chunk { background-color: #00ff00; }")
        layout.addWidget(self.progress_bar)

        # Buttons
        self.download_button = QtWidgets.QPushButton("Download")
        self.download_button.clicked.connect(self.download_file_ui)
        self.download_button.setStyleSheet("background-color: #606060; color: white;")

        self.extract_button = QtWidgets.QPushButton("Extract")
        self.extract_button.clicked.connect(self.toggle_extract_options)
        self.extract_button.setStyleSheet("background-color: #606060; color: white;")

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.extract_button)

        layout.addLayout(button_layout)

        # Extract options hidden initially
        self.extract_options_frame = QtWidgets.QFrame()
        self.extract_options_frame.setVisible(False)

        extract_layout = QtWidgets.QVBoxLayout()
        self.extract_path_button = QtWidgets.QPushButton("Select Archive for Extract")
        self.extract_path_button.clicked.connect(self.extract_file_ui)
        self.extract_path_button.setStyleSheet("background-color: #606060; color: white;")

        extract_layout.addWidget(self.extract_path_button)
        self.extract_options_frame.setLayout(extract_layout)
        layout.addWidget(self.extract_options_frame)

        self.setLayout(layout)

    def toggle_extract_options(self):
        self.extract_options_frame.setVisible(not self.extract_options_frame.isVisible())

    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select save folder")
        if folder:
            self.folder_input.setText(folder)

    def download_file_ui(self):
        url = self.url_input.text()
        save_folder = self.folder_input.text()

        if not url:
            QtWidgets.QMessageBox.critical(self, "Error", "Please enter a download URL!")
            return

        if not os.path.isdir(save_folder):
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a valid save folder!")
            return

        self.download_button.setEnabled(False)

        def run_download():
            try:
                service = get_drive_service()
                file_id = extract_file_id(url)
                file_path = download_file(service, file_id, save_folder, self.update_progress)
                QtWidgets.QMessageBox.information(self, "Success", f"File downloaded successfully: {file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
            finally:
                self.progress_bar.setValue(0)
                self.download_button.setEnabled(True)

        threading.Thread(target=run_download, daemon=True).start()

    def extract_file_ui(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select an archive to extract", filter="Archives (*.zip *.tar *.tar.gz *.tgz)")

        if not file_path:
            QtWidgets.QMessageBox.critical(self, "Error", "No file selected!")
            return

        save_folder = self.folder_input.text()
        if not os.path.isdir(save_folder):
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a valid save folder!")
            return

        def run_extraction():
            try:
                result = extract_archive(file_path, save_folder, progress_callback=self.update_progress)
                QtWidgets.QMessageBox.information(self, "Success", result)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
            finally:
                self.progress_bar.setValue(0)

        threading.Thread(target=run_extraction, daemon=True).start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MinecraftInstallerUI()
    window.show()
    sys.exit(app.exec_())
