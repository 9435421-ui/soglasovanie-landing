import os
import logging
from config import KNOWLEDGE_BASE_PATH

class ExpertArchive:
    def __init__(self):
        self.path = KNOWLEDGE_BASE_PATH
        os.makedirs(self.path, exist_ok=True)

    def get_all_documents(self):
        """Возвращает список всех экспертных документов."""
        try:
            return [f for f in os.listdir(self.path) if f.endswith('.md') or f.endswith('.pdf')]
        except Exception as e:
            logging.error(f"Error reading archive: {e}")
            return []

    def read_document(self, filename):
        """Чтение документа из архива (только MD для начала)."""
        file_path = os.path.join(self.path, filename)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logging.error(f"Error reading file {filename}: {e}")
            return None

archive = ExpertArchive()
