import os
import sys

def resource_path(relative_path):
    """Получение пути ресурса для PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

SERVICE_ACCOUNT_FILE = resource_path("fc-auto-installer-3b84891aacd2.json")
