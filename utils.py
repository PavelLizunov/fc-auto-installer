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
