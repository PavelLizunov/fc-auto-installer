from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from config import SERVICE_ACCOUNT_FILE

def get_drive_service():
    """
    Создает и возвращает сервис для работы с Google Drive API.
    """
    try:
        # Загружаем учетные данные
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        # Создаем объект сервиса Google Drive API
        service = build('drive', 'v3', credentials=credentials)
        return service
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл ключа не найден: {SERVICE_ACCOUNT_FILE}")
    except Exception as e:
        raise Exception(f"Ошибка при создании сервиса Google Drive: {e}")
