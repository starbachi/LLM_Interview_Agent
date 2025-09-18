"""
Configuration manager for Interview Agent.
Handles loading and managing YAML configuration files.
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration loading and directory setup."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.load_config()
        
    def load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file {self.config_path} not found, using defaults")
                self._load_default_config()
                return
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {self.config_path}")
                
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML config: {e}")
            self._load_default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._load_default_config()
    
    def _load_default_config(self) -> None:
        """Load default configuration when file is missing or invalid."""
        self.config = {
            "audio": {
                "debug": {
                    "enabled": True,
                    "base_directory": "debug_audio",
                    "subdirectories": {
                        "raw": "raw_input",
                        "normalized": "normalized", 
                        "failed": "failed_stt"
                    },
                    "file_formats": {
                        "raw_extension": ".raw",
                        "wav_extension": ".wav",
                        "mp3_extension": ".mp3"
                    },
                    "retention": {
                        "max_files": 100,
                        "cleanup_on_startup": False
                    }
                }
            },
            "logging": {
                "level": "DEBUG",
                "file": "interview_debug.log",
                "format": "%(asctime)s [%(levelname)s] %(message)s"
            },
            "stt": {
                "google": {
                    "language_code": "en-GB",
                    "model": "latest_long",
                    "enhanced": True,
                    "profanity_filter": False,
                    "enable_automatic_punctuation": True,
                    "enable_spoken_punctuation": True,
                    "enable_spoken_emojis": True
                }
            },
            "tts": {
                "google": {
                    "language_code": "en-GB",
                    "voice_name": "en-GB-Standard-A"
                }
            }
        }
        logger.info("Loaded default configuration")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path (e.g., "audio.debug.enabled")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def is_debug_enabled(self) -> bool:
        """Check if audio debug mode is enabled."""
        return self.get("audio.debug.enabled", False)
    
    def get_debug_directories(self) -> Dict[str, str]:
        """
        Get full paths for debug directories.
        
        Returns:
            Dictionary mapping directory types to full paths
        """
        if not self.is_debug_enabled():
            return {}
            
        base_dir = self.get("audio.debug.base_directory", "debug_audio")
        subdirs = self.get("audio.debug.subdirectories", {})
        
        return {
            name: os.path.join(base_dir, path) 
            for name, path in subdirs.items()
        }
    
    def setup_debug_directories(self) -> Dict[str, str]:
        """
        Create debug directories if they don't exist.
        
        Returns:
            Dictionary mapping directory types to created paths
        """
        if not self.is_debug_enabled():
            logger.info("Audio debug disabled, skipping directory creation")
            return {}
        
        directories = self.get_debug_directories()
        created_dirs = {}
        
        for dir_type, dir_path in directories.items():
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                created_dirs[dir_type] = dir_path
                logger.debug(f"Created debug directory: {dir_type} -> {dir_path}")
            except Exception as e:
                logger.error(f"Failed to create directory {dir_path}: {e}")
        
        if created_dirs:
            logger.info(f"Set up {len(created_dirs)} debug directories")
        
        return created_dirs
    
    def get_debug_file_path(self, dir_type: str, filename: str, file_format: str = "raw") -> Optional[str]:
        """
        Get full path for a debug file.
        
        Args:
            dir_type: Type of directory (raw, normalized, failed)
            filename: Base filename without extension
            file_format: File format (raw or wav)
            
        Returns:
            Full file path or None if debug disabled
        """
        if not self.is_debug_enabled():
            return None
            
        directories = self.get_debug_directories()
        if dir_type not in directories:
            logger.warning(f"Unknown debug directory type: {dir_type}")
            return None
        
        extension = self.get(f"audio.debug.file_formats.{file_format}_extension", f".{file_format}")
        return os.path.join(directories[dir_type], f"{filename}{extension}")


# Global configuration instance
config = ConfigManager()