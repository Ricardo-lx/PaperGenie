import logging
from pathlib import Path
from typing import Optional

class Logger:
    _instance: Optional['Logger'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        self.logger = logging.getLogger('paper_writer')
        self.logger.setLevel(logging.INFO)
        
        # 文件处理器
        log_path = Path('logs/paper_writer.log')
        log_path.parent.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.INFO)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 格式化
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    @classmethod
    def get_logger(cls):
        if cls._instance is None:
            cls()
        return cls._instance.logger