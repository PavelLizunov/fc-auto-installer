import os
import socket
import zipfile
import tarfile
from googleapiclient.http import MediaIoBaseDownload
import io

stop_download = False

def check_internet_connection():
    """
    Проверяет подключение к интернету.
    Возвращает True, если интернет доступен, иначе False.
    """
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

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

def download_file_from_drive(service, file_id, save_folder, progress_callback):
    """
    Скачивает файл с Google Drive через API.
    :param service: объект службы Google Drive API.
    :param file_id: ID файла в Google Drive.
    :param save_folder: Папка для сохранения файла.
    :param progress_callback: Функция для обновления прогресса.
    """
    global stop_download

    # Получение метаданных файла
    file = service.files().get(fileId=file_id, fields="name, size").execute()
    file_name = file.get("name", "downloaded_file")
    file_size = int(file.get("size", 0))

    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join(save_folder, file_name)

    with open(file_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False

        while not done:
            if stop_download:
                raise Exception("Загрузка отменена пользователем.")

            status, done = downloader.next_chunk()
            progress = int(status.progress() * 100)
            progress_callback(progress)

    return file_path

def extract_archive(file_path, extract_to):
    """
    Распаковывает архив (ZIP или TAR) в указанную папку.
    :param file_path: Путь к архиву.
    :param extract_to: Папка для извлечения.
    """
    try:
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
                return "ZIP архив успешно извлечён."
        elif tarfile.is_tarfile(file_path):
            with tarfile.open(file_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
                return "TAR архив успешно извлечён."
        else:
            return "Файл не является архивом или формат не поддерживается."
    except Exception as e:
        raise Exception(f"Ошибка при извлечении архива: {e}")

def cancel_download():
    """Отменяет загрузку."""
    global stop_download
    stop_download = True
