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

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "fc-auto-installer-3b84891aacd2.json")

IGNORED_FILES = ["options.txt", "servers.dat"]
IGNORED_FOLDERS = ["saves"]

class MinecraftInstallerUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Minecraft Installer")
        self.setFixedSize(400, 400)

        layout = QtWidgets.QVBoxLayout()

        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setPlaceholderText("Enter download URL (Optional for Extract)")
        layout.addWidget(self.url_input)

        self.folder_input = QtWidgets.QLineEdit()
        self.folder_input.setPlaceholderText("Select save folder")
        layout.addWidget(self.folder_input)

        folder_button = QtWidgets.QPushButton("Select Folder")
        folder_button.clicked.connect(self.select_folder)
        layout.addWidget(folder_button)

        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)

        download_button = QtWidgets.QPushButton("Download and Extract")
        download_button.clicked.connect(self.download_and_extract)
        layout.addWidget(download_button)

        extract_button = QtWidgets.QPushButton("Extract Only")
        extract_button.clicked.connect(self.extract_only)
        layout.addWidget(extract_button)

        self.log_area = QtWidgets.QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        self.setLayout(layout)

    def log_message(self, message):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select save folder")
        if folder:
            self.folder_input.setText(folder)

    def download_and_extract(self):
        url = self.url_input.text()
        save_folder = self.folder_input.text()

        if not url or not os.path.isdir(save_folder):
            self.log_message("Invalid URL or folder")
            return

        self.log_message("Starting download and extract process...")
        self.progress_bar.setValue(0)
        threading.Thread(target=self.run_process, args=(url, save_folder), daemon=True).start()

    def extract_only(self):
        save_folder = self.folder_input.text()
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select an archive to extract", filter="Archives (*.zip *.tar *.tar.gz *.tgz)")

        if not os.path.isdir(save_folder) or not file_path:
            self.log_message("Invalid folder or archive")
            return

        self.log_message("Starting extraction process...")
        self.progress_bar.setValue(0)
        threading.Thread(target=self.run_extract_only, args=(file_path, save_folder), daemon=True).start()

    def run_process(self, url, save_folder):
        try:
            service = self.get_drive_service()
            file_id = self.extract_file_id(url)
            file_path = self.download_file(service, file_id, save_folder)
            self.log_message(f"Downloaded: {file_path}")
            self.extract_archive(file_path, save_folder)
            self.log_message("Process completed successfully.")
        except Exception as e:
            self.log_message(f"Error: {e}")

    def run_extract_only(self, file_path, save_folder):
        try:
            self.extract_archive(file_path, save_folder)
            self.log_message("Extraction completed successfully.")
        except Exception as e:
            self.log_message(f"Error: {e}")

    def extract_file_id(self, url):
        if "drive.google.com" in url and "/file/d/" in url:
            return url.split("/file/d/")[-1].split("/")[0]
        elif "id=" in url:
            return url.split("id=")[-1].split("&")[0]
        else:
            raise ValueError("Invalid URL format.")

    def get_drive_service(self):
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        return build('drive', 'v3', credentials=credentials)

    def download_file(self, service, file_id, save_folder):
        file = service.files().get(fileId=file_id, fields="name, size").execute()
        file_name = file.get("name", "downloaded_file")

        request = service.files().get_media(fileId=file_id)
        file_path = os.path.join(save_folder, file_name)

        with open(file_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False

            while not done:
                status, done = downloader.next_chunk()
                self.progress_bar.setValue(int(status.progress() * 100))

        return file_path

    def extract_archive(self, file_path, save_folder):
        temp_extract_folder = os.path.join(save_folder, "temp_extract")
        os.makedirs(temp_extract_folder, exist_ok=True)

        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_folder)
        elif tarfile.is_tarfile(file_path):
            with tarfile.open(file_path, 'r:*') as tar_ref:
                tar_ref.extractall(temp_extract_folder)
        else:
            raise ValueError("Unsupported archive format.")

        minecraft_folder = os.path.join(temp_extract_folder, ".minecraft")
        if not os.path.exists(minecraft_folder):
            raise FileNotFoundError(".minecraft folder not found.")

        for root, dirs, files in os.walk(minecraft_folder):
            for file in files:
                if file in IGNORED_FILES:
                    os.remove(os.path.join(root, file))
            for folder in dirs:
                if folder in IGNORED_FOLDERS:
                    shutil.rmtree(os.path.join(root, folder))

        for item in os.listdir(minecraft_folder):
            src_path = os.path.join(minecraft_folder, item)
            dest_path = os.path.join(save_folder, item)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dest_path)

        shutil.rmtree(temp_extract_folder)
        self.log_message("Extraction completed and temporary files cleaned up.")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MinecraftInstallerUI()
    window.show()
    app.exec_()
