# fc-auto-installer
### README для пользователей (русский и английский)

---

## **README (Русский)**

### Описание
`fc-auto-installer` — это простая программа для автоматического обновления клиентской сборки Minecraft. Она скачивает обновления, удаляет ненужные файлы и папки, а также обновляет сборку. Вам больше не нужно вручную разбираться с архивацией и заменой файлов!

---

### Установка
1. Зайдите на вкладку **Releases** на странице проекта.
2. Скачайте последнюю версию программы (файл `.exe`).
3. Переместите скачанный файл в любое удобное место на вашем компьютере.

---

### Использование
1. Запустите файл `fc-auto-installer.exe` двойным щелчком.
2. В программе:
   - Вставьте ссылку на архив сборки Minecraft (Google Drive).
   - Выберите папку, где находится ваша сборка Minecraft.
   - Нажмите **"Download and Extract"** (Скачать и распаковать).
3. Программа сама выполнит все действия:
   - Скачает архив.
   - Удалит ненужные файлы.
   - Обновит сборку.

---

### Предупреждение об антивирусах
Некоторые антивирусы могут отмечать `.exe` файл как подозрительный, так как он создан с помощью `PyInstaller`. Это стандартное поведение для кастомного софта. Вы можете:
1. Самостоятельно собрать программу (см. ниже).
2. Добавить файл в исключения антивируса, если уверены в его безопасности.

---

### Как создать сервисный ключ Google Drive
1. Зайдите в [Google Cloud Console](https://console.cloud.google.com/).
2. Создайте новый проект.
3. Перейдите в раздел **API & Services** → **Credentials**.
4. Нажмите **Create Credentials** → **Service Account**.
5. В настройках сервисного аккаунта скачайте JSON-файл с ключом.
6. Переместите этот файл в папку с программой.

---

### Сборка `.exe` самостоятельно
Если вы хотите самостоятельно собрать `.exe`, выполните следующие шаги:
1. **Установите Python и необходимые модули:**
   - Скачайте и установите [Python 3.10+](https://www.python.org/downloads/).
   - Установите зависимости командой:
     ```bash
     pip install -r requirements.txt
     ```
2. **Установите PyInstaller:**
   ```bash
   pip install pyinstaller
   ```
3. **Соберите `.exe`:**
   Выполните команду:
   ```bash
   pyinstaller --noconsole --onefile --icon=assets\minecraft_icon.ico --add-data "путь_к_ключу;." fc-auto-installer.py
   ```
   Убедитесь, что у вас есть сервисный ключ Google Drive (JSON) и добавьте его в команду.
4. Готовый `.exe` будет находиться в папке `dist`.

---

### Благодарности
Программа создана для удобства сообщества Minecraft. Если у вас есть предложения или вы нашли ошибку, напишите нам!

---

---

## **README (English)**

### Description
`fc-auto-installer` is a simple program for automatically updating Minecraft client builds. It downloads updates, removes unnecessary files and folders, and updates your build. No more manual archive handling or file replacements!

---

### Installation
1. Go to the **Releases** tab on the project page.
2. Download the latest version of the program (a `.exe` file).
3. Move the downloaded file to any convenient location on your computer.

---

### Usage
1. Run `fc-auto-installer.exe` by double-clicking it.
2. In the program:
   - Paste the link to the Minecraft build archive (Google Drive).
   - Select the folder where your Minecraft build is located.
   - Click **"Download and Extract"**.
3. The program will:
   - Download the archive.
   - Remove unnecessary files.
   - Update the build.

---

### Antivirus Warning
Some antivirus programs may flag the `.exe` file as suspicious since it is created using `PyInstaller`. This is normal for custom software. You can:
1. Build the program yourself (see below).
2. Add the file to your antivirus exceptions if you trust it.

---

### How to Create a Google Drive Service Key
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Navigate to **API & Services** → **Credentials**.
4. Click **Create Credentials** → **Service Account**.
5. In the service account settings, download the JSON key file.
6. Move this file to the program folder.

---

### Building `.exe` Yourself
If you'd like to build the `.exe` yourself, follow these steps:
1. **Install Python and required modules:**
   - Download and install [Python 3.10+](https://www.python.org/downloads/).
   - Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```
2. **Install PyInstaller:**
   ```bash
   pip install pyinstaller
   ```
3. **Build `.exe`:**
   Run the following command:
   ```bash
   pyinstaller --noconsole --onefile --icon=assets\minecraft_icon.ico --add-data "path_to_key;." fc-auto-installer.py
   ```
   Ensure you have the Google Drive service key (JSON) and include it in the command.
4. The ready `.exe` will be in the `dist` folder.

---

### Acknowledgments
This program was created for the Minecraft community. If you have suggestions or encounter a bug, feel free to reach out!
```