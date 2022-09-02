import os
import aiofiles
import uuid

from config.app_config import settings


class LocalFile:
    def __init__(self, file_name, content_type):
        if not os.path.exists(settings.file_storage):
            os.makedirs(settings.file_storage)
        self.name = file_name
        self.type = content_type
        self.path = f'{settings.file_storage}/{uuid.uuid4()}'

    async def save(self, in_data):
        async with aiofiles.open(self.path, 'wb') as out_file:
            while content := await in_data.read():
                await out_file.write(content)

    def read(self):
        return open(self.path, 'rb')
