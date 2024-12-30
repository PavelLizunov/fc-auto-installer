import tkinter as tk
from tkinter import filedialog, messagebox
import requests
import os
import re


def download_large_file_from_google_drive(file_url, save_folder):
    """
    Скачивает файл с Google Диска, обрабатывая подтверждение для больших файлов.
    :param file_url: Прямая ссылка на файл Google Диска.
    :param save_folder: Папка для сохранения файла.
    """
    session = requests.Session()

    # Первоначальный запрос
    response = session.get(file_url, stream=True)
    confirm_token = get_confirm_token(response)
    if not confirm_token:
        confirm_token = extract_confirm_token_from_html(response.text)

    # Если требуется подтверждение, делаем повторный запрос
    if confirm_token:
        params = {'confirm': confirm_token}
        response = session.get(file_url, params=params, stream=True)

    # Извлечение имени файла
    content_disposition = response.headers.get('content-disposition')
    if content_disposition and 'filename=' in content_disposition:
        filename = content_disposition.split('filename=')[-1].strip('"')
    else:
        filename = "downloaded_file"

    # Полный путь для сохранения файла
    save_path = os.path.join(save_folder, filename)

    # Сохраняем файл
    save_response_content(response, save_path)

    return filename


def get_confirm_token(response):
    """
    Извлекает токен подтверждения из ответа Google.
    """
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None


def extract_confirm_token_from_html(html):
    """
    Извлекает токен подтверждения из HTML-страницы.
    """
    match = re.search(r'name="confirm" value="(.+?)"', html)
    if match:
        return match.group(1)
    return None


def save_response_content(response, save_path):
    """
    Сохраняет содержимое ответа в файл.
    """
    chunk_size = 32768  # 32 KB

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size):
            if chunk:  # фильтруем пустые блоки
                f.write(chunk)


def download_file():
    """Скачивание файла по ссылке с выбором папки для сохранения."""
    url = url_entry.get()
    save_folder = path_entry.get()

    if not url:
        messagebox.showerror("Ошибка", "Введите ссылку для скачивания!")
        return

    if not save_folder or not os.path.isdir(save_folder):
        messagebox.showerror("Ошибка", "Выберите корректную папку для сохранения!")
        return

    try:
        # Преобразование ссылки в корректный формат
        if "drive.google.com" in url and "id=" in url:
            file_id = url.split("id=")[-1].split("&")[0]
            url = f"https://drive.google.com/uc?id={file_id}&export=download"

        # Скачивание файла
        filename = download_large_file_from_google_drive(url, save_folder)
        messagebox.showinfo("Успех", f"Файл '{filename}' успешно скачан в папку {save_folder}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка при скачивании: {e}")


def select_path():
    """Открывает диалоговое окно для выбора папки сохранения."""
    folder_selected = filedialog.askdirectory(
        title="Выберите папку для сохранения"
    )
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

# Кнопка для скачивания
tk.Button(app, text="Скачать", command=download_file).pack(pady=20)

# Запуск приложения
app.mainloop()
