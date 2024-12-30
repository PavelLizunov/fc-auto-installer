import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
import io

stop_download = False

SERVICE_ACCOUNT_FILE = "C:\\Users\\slovn\\.json\\fc-auto-installer-3b84891aacd2.json"
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Аутентификация через сервисный ключ
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('drive', 'v3', credentials=credentials)

def extract_file_id(url):
    """
    Извлекает file_id из URL Google Drive.
    """
    if "drive.google.com" in url and "/file/d/" in url:
        return url.split("/file/d/")[-1].split("/")[0]
    elif "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    else:
        raise ValueError("Некорректный формат ссылки Google Drive")

def download_file_from_drive(file_id, save_folder):
    """
    Скачивает файл с Google Drive через API.
    :param file_id: ID файла в Google Drive.
    :param save_folder: Папка для сохранения файла.
    """
    global stop_download

    try:
        # Получение метаданных файла
        file = service.files().get(fileId=file_id, fields="name, size").execute()
        file_name = file.get("name", "downloaded_file")
        file_size = int(file.get("size", 0))

        request = service.files().get_media(fileId=file_id)
        file_path = os.path.join(save_folder, file_name)

        with open(file_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            progress_label.config(text="Загрузка: 0%")

            while not done:
                if stop_download:
                    raise Exception("Загрузка отменена пользователем.")

                status, done = downloader.next_chunk()
                progress = int(status.progress() * 100)
                progress_label.config(text=f"Загрузка: {progress}%")

        progress_label.config(text="Загрузка завершена")
        messagebox.showinfo("Успех", f"Файл '{file_name}' успешно скачан в папку: {save_folder}")
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        if stop_download:
            messagebox.showinfo("Отмена", "Загрузка была отменена.")
        else:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")

def download_file():
    """Запускает процесс скачивания файла в отдельном потоке."""
    global stop_download
    stop_download = False

    url = url_entry.get()
    save_folder = path_entry.get()

    if not url:
        messagebox.showerror("Ошибка", "Введите ссылку для скачивания!")
        return

    if not save_folder or not os.path.isdir(save_folder):
        messagebox.showerror("Ошибка", "Выберите корректную папку для сохранения!")
        return

    try:
        file_id = extract_file_id(url)
    except ValueError as e:
        messagebox.showerror("Ошибка", str(e))
        return

    # Деактивируем кнопки
    download_button.config(state=tk.DISABLED)
    cancel_button.config(state=tk.NORMAL)

    def run_download():
        try:
            download_file_from_drive(file_id, save_folder)
        finally:
            download_button.config(state=tk.NORMAL)
            cancel_button.config(state=tk.DISABLED)

    threading.Thread(target=run_download).start()

def cancel_download():
    """Отменяет загрузку."""
    global stop_download
    stop_download = True

def select_path():
    """Открывает диалоговое окно для выбора папки сохранения."""
    folder_selected = filedialog.askdirectory(title="Выберите папку для сохранения")
    if folder_selected:
        path_entry.delete(0, tk.END)
        path_entry.insert(0, folder_selected)

# Создание окна приложения
app = tk.Tk()
app.title("Скачивание файла с Google Диска")

# Интерфейс: метка и поле ввода для ссылки
tk.Label(app, text="Введите ссылку для скачивания:").pack(pady=5)
url_entry = tk.Entry(app, width=50)
url_entry.pack(pady=5)

# Интерфейс: метка, поле ввода и кнопка для выбора пути
tk.Label(app, text="Выберите папку для сохранения:").pack(pady=5)
path_frame = tk.Frame(app)
path_frame.pack(pady=5)

path_entry = tk.Entry(path_frame, width=40)
path_entry.pack(side=tk.LEFT, padx=5)
tk.Button(path_frame, text="Выбрать", command=select_path).pack(side=tk.LEFT)

# Метка прогресса
progress_label = tk.Label(app, text="Ожидание")
progress_label.pack(pady=5)

# Кнопки для скачивания и отмены
button_frame = tk.Frame(app)
button_frame.pack(pady=20)

download_button = tk.Button(button_frame, text="Скачать", command=download_file)
download_button.pack(side=tk.LEFT, padx=5)

cancel_button = tk.Button(button_frame, text="Отмена", command=cancel_download, state=tk.DISABLED)
cancel_button.pack(side=tk.LEFT, padx=5)

# Запуск приложения
app.mainloop()
