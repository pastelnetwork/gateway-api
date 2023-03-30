import os
import pathlib

import aiofiles

from app.core.config import settings


class LocalFile:
    def __init__(self, file_name, content_type, result_id: str):
        if not os.path.exists(settings.FILE_STORAGE):
            os.makedirs(settings.FILE_STORAGE)
        self.name = file_name
        self.type = content_type
        file_extension = pathlib.Path(file_name).suffix
        self.path = f'{settings.FILE_STORAGE}/{result_id}{file_extension}'

    async def save(self, in_data):
        async with aiofiles.open(self.path, 'wb') as out_file:
            while content := await in_data.read():
                await out_file.write(content)

    def read(self):
        return open(self.path, 'rb')

