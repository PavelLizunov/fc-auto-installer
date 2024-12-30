import tkinter as tk
from tkinter import filedialog, messagebox
import threading
from auth import get_drive_service
from downloader import extract_file_id, download_file_from_drive, cancel_download
import os

def start_ui():
    service = get_drive_service()
    stop_download = False

    def download_file():
        """Запускает процесс скачивания файла в отдельном потоке."""
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
                def update_progress(progress):
                    progress_label.config(text=f"Загрузка: {progress}%")
                
                file_name = download_file_from_drive(service, file_id, save_folder, update_progress)
                messagebox.showinfo("Успех", f"Файл '{file_name}' успешно скачан в папку: {save_folder}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
            finally:
                download_button.config(state=tk.NORMAL)
                cancel_button.config(state=tk.DISABLED)

        threading.Thread(target=run_download).start()

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
