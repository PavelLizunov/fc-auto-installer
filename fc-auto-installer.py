import os
import socket
import zipfile
import tarfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import queue

# Configuration
IGNORED_FILES = ["options.txt", "servers.dat"]
IGNORED_FOLDERS = ["saves"]
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "fc-auto-installer-3b84891aacd2.json")

# Utility functions
def check_internet_connection():
    """Check internet connection."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

def extract_file_id(url):
    """Extract file_id from a Google Drive URL."""
    if "drive.google.com" in url and "/file/d/" in url:
        return url.split("/file/d/")[-1].split("/")[0]
    elif "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    else:
        raise ValueError("Invalid Google Drive URL format.")

def get_drive_service():
    """Create and return a Google Drive API service."""
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        service = build('drive', 'v3', credentials=credentials)
        return service
    except FileNotFoundError:
        raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
    except Exception as e:
        raise Exception(f"Error creating Google Drive service: {e}")

def download_file(service, file_id, save_folder, progress_callback):
    """Download a file from Google Drive using its API."""
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

def extract_archive(file_path, extract_to, overwrite=True, ignore_list=None):
    """Extract a ZIP or TAR archive to a specified folder."""
    if ignore_list is None:
        ignore_list = IGNORED_FILES + IGNORED_FOLDERS

    if zipfile.is_zipfile(file_path):
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if any(file.startswith(ignored) for ignored in ignore_list):
                    continue
                zip_ref.extract(file, extract_to)
        return "ZIP archive extracted successfully."

    elif tarfile.is_tarfile(file_path):
        with tarfile.open(file_path, 'r:*') as tar_ref:
            for member in tar_ref.getmembers():
                if any(member.name.startswith(ignored) for ignored in ignore_list):
                    continue
                tar_ref.extract(member, extract_to)
        return "TAR archive extracted successfully."

    else:
        raise ValueError("Unsupported archive format.")

# UI Functions
def start_ui():
    """Start the Tkinter-based UI."""
    message_queue = queue.Queue()

    service = get_drive_service()

    def handle_queue():
        while not message_queue.empty():
            message_type, message_data = message_queue.get()
            if message_type == "progress":
                progress_bar["value"] = message_data
            elif message_type == "error":
                messagebox.showerror("Error", message_data)
            elif message_type == "info":
                messagebox.showinfo("Result", message_data)
        app.after(100, handle_queue)

    def download_file_ui():
        url = url_entry.get()
        save_folder = path_entry.get()

        if not url:
            messagebox.showerror("Error", "Please enter a download URL!")
            return

        if not save_folder or not os.path.isdir(save_folder):
            messagebox.showerror("Error", "Please select a valid save folder!")
            return

        download_button.config(state=tk.DISABLED)

        def run_download():
            try:
                file_id = extract_file_id(url)
                file_path = download_file(service, file_id, save_folder, lambda progress: message_queue.put(("progress", progress)))
                message_queue.put(("info", f"File downloaded successfully: {file_path}"))
            except Exception as e:
                message_queue.put(("error", str(e)))
            finally:
                message_queue.put(("progress", 0))
                download_button.config(state=tk.NORMAL)

        threading.Thread(target=run_download, daemon=True).start()

    def extract_file_ui():
        file_path = filedialog.askopenfilename(
            title="Select an archive to extract",
            filetypes=[("Archives", "*.zip *.tar *.tar.gz *.tgz")],
        )

        if not file_path:
            messagebox.showerror("Error", "No file selected!")
            return

        save_folder = path_entry.get()
        if not save_folder or not os.path.isdir(save_folder):
            messagebox.showerror("Error", "Please select a valid save folder!")
            return

        def run_extraction():
            try:
                result = extract_archive(file_path, save_folder)
                message_queue.put(("info", result))
            except Exception as e:
                message_queue.put(("error", str(e)))
            finally:
                message_queue.put(("progress", 0))

        threading.Thread(target=run_extraction, daemon=True).start()

    def select_path():
        folder_selected = filedialog.askdirectory(title="Select save folder")
        if folder_selected:
            path_entry.delete(0, tk.END)
            path_entry.insert(0, folder_selected)

    app = tk.Tk()
    app.title("Minecraft Auto Installer")

    tk.Label(app, text="Enter download URL:").pack(pady=5)
    url_entry = tk.Entry(app, width=50)
    url_entry.pack(pady=5)

    tk.Label(app, text="Select save folder:").pack(pady=5)
    path_frame = tk.Frame(app)
    path_frame.pack(pady=5)

    path_entry = tk.Entry(path_frame, width=40)
    path_entry.pack(side=tk.LEFT, padx=5)
    tk.Button(path_frame, text="Select", command=select_path).pack(side=tk.LEFT)

    progress_bar = ttk.Progressbar(app, orient="horizontal", length=300, mode="determinate")
    progress_bar.pack(pady=10)

    button_frame = tk.Frame(app)
    button_frame.pack(pady=20)

    download_button = tk.Button(button_frame, text="Download", command=download_file_ui)
    download_button.pack(side=tk.LEFT, padx=5)

    extract_button = tk.Button(button_frame, text="Extract", command=extract_file_ui)
    extract_button.pack(side=tk.LEFT, padx=5)

    app.after(100, handle_queue)
    app.mainloop()

if __name__ == "__main__":
    start_ui()
