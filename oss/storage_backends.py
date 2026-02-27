from django.conf import settings
from django.core.files.storage import FileSystemStorage

class GoAppStorage(FileSystemStorage):
    def __init__(self, location=settings.GO_APP_UPLOAD_DIR, base_url=None):
        super().__init__(location=location, base_url=base_url)