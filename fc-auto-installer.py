import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import gdown
import os

# Глобальная переменная для остановки загрузки
stop_download = False

def download_file_with_gdown(url, save_folder):
    """
    Скачивает файл с помощью библиотеки gdown.

    :param url: Ссылка на файл Google Drive.
    :param save_folder: Путь к папке для сохранения файла.
    """
    global stop_download

    try:
        # Получаем ID файла из ссылки
        if "drive.google.com" in url and "/file/d/" in url:
            file_id = url.split("/file/d/")[-1].split("/")[0]
            url = f"https://drive.google.com/uc?id={file_id}&export=download"

        # Имя файла из URL (если не предоставлено)
        output = os.path.join(save_folder, "downloaded_file")

        # Скачивание файла с использованием gdown
        gdown.download(url, output, quiet=False)

        if stop_download:
            os.remove(output)
            messagebox.showinfo("Отмена", "Загрузка была отменена.")
        else:
            messagebox.showinfo("Успех", f"Файл успешно скачан в папку: {save_folder}")
    except Exception as e:
        if stop_download:
            messagebox.showinfo("Отмена", "Загрузка была отменена.")
        else:
            messagebox.showerror("Ошибка", f"Произошла ошибка при скачивании: {e}")

def download_file():
    """Запускает процесс скачивания файла в отдельном потоке."""
    global stop_download
    stop_download = False  # Сбрасываем флаг отмены

    url = url_entry.get()
    save_folder = path_entry.get()

    if not url:
        messagebox.showerror("Ошибка", "Введите ссылку для скачивания!")
        return

    if not save_folder or not os.path.isdir(save_folder):
        messagebox.showerror("Ошибка", "Выберите корректную папку для сохранения!")
        return

    # Деактивируем кнопки
    download_button.config(state=tk.DISABLED)
    cancel_button.config(state=tk.NORMAL)

    def run_download():
        try:
            download_file_with_gdown(url, save_folder)
        finally:
            # Активируем кнопку скачивания после завершения
            download_button.config(state=tk.NORMAL)
            cancel_button.config(state=tk.DISABLED)

    threading.Thread(target=run_download).start()

def cancel_download():
    """Отменяет загрузку файла."""
    global stop_download
    stop_download = True
    cancel_button.config(state=tk.DISABLED)

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

# Кнопка для скачивания
download_button = tk.Button(app, text="Скачать", command=download_file)
download_button.pack(pady=5)

# Кнопка для отмены загрузки
cancel_button = tk.Button(app, text="Отмена", command=cancel_download, state=tk.DISABLED)
cancel_button.pack(pady=5)

# Запуск приложения
app.mainloop()
