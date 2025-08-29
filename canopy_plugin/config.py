"""
Configuration management for Canopy Plugin Python implementation.

This module provides type-safe configuration handling with validation.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ConfigOptions:
    """Configuration options for creating a Config instance."""
    chain_id: Optional[int] = None
    data_dir_path: Optional[str] = None


@dataclass 
class ConfigData:
    """Serializable configuration data for JSON persistence."""
    chain_id: int
    data_dir_path: str


class Config:
    """
    Configuration management for Canopy plugin.
    Provides type-safe configuration handling with validation.
    """
    
    DEFAULT_CHAIN_ID = 1
    DEFAULT_DATA_DIR = "/tmp/plugin/"
    
    def __init__(self, options: Optional[ConfigOptions] = None):
        """Initialize configuration with optional parameters."""
        if options is None:
            options = ConfigOptions()
            
        self.chain_id = options.chain_id if options.chain_id is not None else self.DEFAULT_CHAIN_ID
        self.data_dir_path = options.data_dir_path if options.data_dir_path is not None else self.DEFAULT_DATA_DIR
        
        # Validate configuration
        self._validate()
    
    def _validate(self) -> None:
        """
        Validate configuration parameters.
        
        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(self.chain_id, int) or self.chain_id < 1:
            raise ValueError(f"Invalid chain_id: {self.chain_id}. Must be a positive integer.")
        
        if not isinstance(self.data_dir_path, str) or not self.data_dir_path.strip():
            raise ValueError(f"Invalid data_dir_path: {self.data_dir_path}. Must be a non-empty string.")
    
    @classmethod
    def default_config(cls) -> 'Config':
        """
        Create default configuration.
        """
        return cls(ConfigOptions(
            chain_id=cls.DEFAULT_CHAIN_ID,
            data_dir_path=os.path.join(cls.DEFAULT_DATA_DIR)
        ))
    
    @classmethod
    async def from_file(cls, filepath: str) -> 'Config':
        """
        Load configuration from JSON file.
        
        Args:
            filepath: Path to the configuration file
            
        Returns:
            Config instance
            
        Raises:
            ValueError: If file cannot be read or parsed
        """
        if not isinstance(filepath, str) or not filepath.strip():
            raise ValueError("Filepath must be a non-empty string")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                file_content = file.read()
                config_data = json.loads(file_content)
            
            # Start with default config and override with file data
            default_config = cls.default_config()
            
            return cls(ConfigOptions(
                chain_id=config_data.get('chainId', default_config.chain_id),
                data_dir_path=config_data.get('dataDirPath', default_config.data_dir_path)
            ))
        except (OSError, json.JSONDecodeError, KeyError) as err:
            raise ValueError(f"Failed to load config from {filepath}: {err}")
    
    @classmethod
    def from_file_sync(cls, filepath: str) -> 'Config':
        """
        Load configuration from JSON file synchronously.
        
        Args:
            filepath: Path to the configuration file
            
        Returns:
            Config instance
            
        Raises:
            ValueError: If file cannot be read or parsed
        """
        if not isinstance(filepath, str) or not filepath.strip():
            raise ValueError("Filepath must be a non-empty string")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                file_content = file.read()
                config_data = json.loads(file_content)
            
            # Start with default config and override with file data
            default_config = cls.default_config()
            
            return cls(ConfigOptions(
                chain_id=config_data.get('chainId', default_config.chain_id),
                data_dir_path=config_data.get('dataDirPath', default_config.data_dir_path)
            ))
        except (OSError, json.JSONDecodeError, KeyError) as err:
            raise ValueError(f"Failed to load config from {filepath}: {err}")
    
    async def save_to_file(self, filepath: str) -> None:
        """
        Save configuration to JSON file.
        
        Args:
            filepath: Path where to save the configuration
            
        Raises:
            ValueError: If file cannot be written
        """
        if not isinstance(filepath, str) or not filepath.strip():
            raise ValueError("Filepath must be a non-empty string")
        
        config_data = {
            'chainId': self.chain_id,
            'dataDirPath': self.data_dir_path
        }
        
        try:
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as file:
                json.dump(config_data, file, indent=2, ensure_ascii=False)
        except OSError as err:
            raise ValueError(f"Failed to save config to {filepath}: {err}")
    
    def save_to_file_sync(self, filepath: str) -> None:
        """
        Save configuration to JSON file synchronously.
        
        Args:
            filepath: Path where to save the configuration
            
        Raises:
            ValueError: If file cannot be written
        """
        if not isinstance(filepath, str) or not filepath.strip():
            raise ValueError("Filepath must be a non-empty string")
        
        config_data = {
            'chainId': self.chain_id,
            'dataDirPath': self.data_dir_path
        }
        
        try:
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as file:
                json.dump(config_data, file, indent=2, ensure_ascii=False)
        except OSError as err:
            raise ValueError(f"Failed to save config to {filepath}: {err}")
    
    def update(self, **kwargs) -> 'Config':
        """
        Create a copy of this configuration with updated values.
        
        Args:
            **kwargs: Configuration parameters to update
            
        Returns:
            New Config instance with updated values
        """
        options = ConfigOptions(
            chain_id=kwargs.get('chain_id', self.chain_id),
            data_dir_path=kwargs.get('data_dir_path', self.data_dir_path)
        )
        return Config(options)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to plain dict for serialization."""
        return {
            'chainId': self.chain_id,
            'dataDirPath': self.data_dir_path
        }
    
    def __str__(self) -> str:
        """Create a string representation of the configuration."""
        return f"Config(chain_id={self.chain_id}, data_dir_path=\"{self.data_dir_path}\")"
    
    def __repr__(self) -> str:
        """Create a detailed string representation."""
        return self.__str__()
    
    def __eq__(self, other) -> bool:
        """Check if this configuration equals another."""
        if not isinstance(other, Config):
            return False
        return (
            self.chain_id == other.chain_id and
            self.data_dir_path == other.data_dir_path
        )