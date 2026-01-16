import os
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from functools import lru_cache

logger = logging.getLogger("GameLibrary")

@lru_cache(maxsize=1)
def get_steam_command() -> str:
    """Detect and cache the Steam launch command (Native or Flatpak)"""
    if subprocess.run(["which", "steam"], capture_output=True).returncode == 0:
        return "steam"
    if subprocess.run(["which", "flatpak"], capture_output=True).returncode == 0:
        # Check if Steam Flatpak is installed
        result = subprocess.run(["flatpak", "info", "com.valvesoftware.Steam"], capture_output=True)
        if result.returncode == 0:
            return "flatpak run com.valvesoftware.Steam"
    return "steam" # Default fallback

class GameLibrary:
    """Detects and manages installed games from Steam and Epic Games"""
    
    def __init__(self):
        self.steam_games = []
        self.epic_games = []
        self.detect_games()
    
    def detect_steam_games(self) -> List[Dict]:
        """Detect installed Steam games"""
        games = []
        
        # Common Steam installation paths on Linux
        steam_paths = [
            Path.home() / ".steam/steam/steamapps",
            Path.home() / ".local/share/Steam/steamapps",
            # Flatpak Steam Path
            Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps",
        ]
        
        steam_cmd = get_steam_command()
        
        for steam_path in steam_paths:
            if not steam_path.exists():
                continue
                
            logger.info(f"Scanning Steam library at: {steam_path}")
            
            # Read library folders
            libraryfolders_file = steam_path / "libraryfolders.vdf"
            library_paths = [steam_path]
            
            if libraryfolders_file.exists():
                try:
                    with open(libraryfolders_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Parse VDF to find additional library paths
                        path_matches = re.findall(r'"path"\s+"([^"]+)"', content)
                        for path in path_matches:
                            lib_path = Path(path) / "steamapps"
                            if lib_path.exists() and lib_path not in library_paths:
                                library_paths.append(lib_path)
                except Exception as e:
                    logger.error(f"Error reading libraryfolders.vdf: {e}")
            
            # Scan all library paths for installed games
            for lib_path in library_paths:
                logger.info(f"Searching manifests in: {lib_path}")
                acf_files = list(lib_path.glob("appmanifest_*.acf"))
                
                for acf_file in acf_files:
                    try:
                        game_info = self._parse_steam_acf(acf_file, steam_cmd)
                        if game_info:
                            games.append(game_info)
                    except Exception as e:
                        logger.error(f"Error parsing {acf_file}: {e}")
        
        # Remove duplicates based on ID (if multiple library paths overlap)
        unique_games = {g['id']: g for g in games}.values()
        
        logger.info(f"Found {len(unique_games)} Steam games")
        return list(unique_games)
    
    def _parse_steam_acf(self, acf_file: Path, steam_cmd: str) -> Optional[Dict]:
        """Parse Steam ACF manifest file"""
        try:
            with open(acf_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract app ID
            appid_match = re.search(r'"appid"\s+"(\d+)"', content)
            if not appid_match:
                return None
            appid = appid_match.group(1)
            
            # Extract name
            name_match = re.search(r'"name"\s+"([^"]+)"', content)
            name = name_match.group(1) if name_match else f"Unknown Game ({appid})"
            
            # Extract install dir
            installdir_match = re.search(r'"installdir"\s+"([^"]+)"', content)
            installdir = installdir_match.group(1) if installdir_match else None

            return {
                "id": f"steam_{appid}",
                "appid": appid,
                "name": name,
                "platform": "Steam",
                "installdir": installdir,
                "launch_command": f"{steam_cmd} steam://rungameid/{appid}"
            }
        except Exception as e:
            logger.error(f"Error parsing ACF file: {e}")
            return None
    
    def detect_epic_games(self) -> List[Dict]:
        """Detect installed Epic Games"""
        games = []
        
        # Epic Games manifest directory on Linux (Heroic/Lutris paths)
        # 1. Heroic Games Launcher (Common)
        heroic_config = Path.home() / ".config/heroic/store_cache/legendary_installed_games.json"
        
        # 2. Legendary (Backend for Heroic)
        legendary_config = Path.home() / ".config/legendary/installed.json"
        
        # 3. Original path in code (maybe for some older wrappers)
        epic_manifests_path = Path.home() / ".config/Epic/UnrealEngineLauncher/LauncherInstalled.dat"
        
        # Check Heroic
        if heroic_config.exists():
            try:
                with open(heroic_config, 'r') as f:
                    data = json.load(f)
                    for item in data:
                        games.append({
                            "id": f"epic_{item['app_name']}",
                            "appid": item['app_name'],
                            "name": item.get('title', item['app_name']),
                            "platform": "Epic Games",
                            "installdir": item.get('install_path'),
                            "launch_command": f"heroic://launch/legendary/{item['app_name']}"
                        })
            except: pass

        # Check Epic Launcher Dat (Original Logic)
        if not games and epic_manifests_path.exists():
            try:
                logger.info(f"Reading Epic Games library from: {epic_manifests_path}")
                with open(epic_manifests_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if "InstallationList" in data:
                        for item in data["InstallationList"]:
                            if item.get("AppName"):
                                games.append({
                                    "id": f"epic_{item['AppName']}",
                                    "appid": item['AppName'],
                                    "name": item.get('InstallLocation', '').split('/')[-1] or item['AppName'],
                                    "platform": "Epic Games",
                                    "installdir": item.get('InstallLocation'),
                                    "launch_command": f"heroic://launch/{item['AppName']}"
                                })
            except Exception as e:
                logger.error(f"Error reading Epic Games library: {e}")
        
        return games
    
    def detect_games(self):
        """Detect all games from all platforms"""
        logger.info("Starting game detection...")
        self.steam_games = self.detect_steam_games()
        self.epic_games = self.detect_epic_games()
        logger.info(f"Total games detected: {len(self.steam_games) + len(self.epic_games)}")
    
    def get_all_games(self) -> List[Dict]:
        """Get all detected games"""
        all_games = []
        
        steam_cmd = get_steam_command()

        # Special Steam Entries
        all_games.append({
            "id": "steam_bigpicture",
            "appid": "bigpicture",
            "name": "Steam Big Picture",
            "platform": "Steam",
            "installdir": None,
            "launch_command": f"{steam_cmd} steam://open/bigpicture"
        })
        
        all_games.append({
            "id": "steam_desktop",
            "appid": "desktop",
            "name": "Steam Desktop",
            "platform": "Steam",
            "installdir": None,
            "launch_command": f"{steam_cmd}"
        })
        
        all_games.extend(self.steam_games)
        all_games.extend(self.epic_games)
        
        # Sort by name
        all_games.sort(key=lambda x: x['name'].lower())
        
        return all_games
    
    def get_game_by_id(self, game_id: str) -> Optional[Dict]:
        """Get game information by ID"""
        for game in self.get_all_games():
            if game['id'] == game_id:
                return game
        return None
    
    def launch_game(self, game_id: str) -> bool:
        """Launch a game by ID"""
        game = self.get_game_by_id(game_id)
        if not game:
            logger.error(f"Game not found: {game_id}")
            return False
        
        try:
            logger.info(f"Launching game: {game['name']} ({game['platform']})")
            # Using subprocess.Popen instead of os.system for better control and non-blocking
            subprocess.Popen(game['launch_command'].split() + ["&"], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return True
        except Exception as e:
            logger.error(f"Error launching game {game_id}: {e}")
            return False
