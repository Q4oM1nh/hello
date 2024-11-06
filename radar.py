import win32process
import win32con
import pymem
import pymem.process
import time
import os
import ctypes
import logging
from requests import get
from colorama import init, Fore
from packaging import version
import json
# Initialize colorama for colored console output
init(autoreset=True)
class Logger:
    """Handles logging setup for the application."""

    LOG_DIRECTORY = os.path.expandvars(r'%LOCALAPPDATA%\Requests\ItsJesewe\crashes')
    LOG_FILE = os.path.join(LOG_DIRECTORY, 'combined_logs.log')

    @staticmethod
    def setup_logging():
        """Set up the logging configuration with the default log level INFO."""
        os.makedirs(Logger.LOG_DIRECTORY, exist_ok=True)
        with open(Logger.LOG_FILE, 'w') as f:
            pass

        logging.basicConfig(
            level=logging.INFO,  # Default to INFO level logging
            format='%(levelname)s: %(message)s',
            handlers=[logging.FileHandler(Logger.LOG_FILE), logging.StreamHandler()]
        )
    
class Utility:
    """Contains utility functions for the application."""

    CACHE_DIRECTORY = os.path.expandvars(r'%LOCALAPPDATA%\Requests\ItsJesewe')
    CACHE_FILE = os.path.join(CACHE_DIRECTORY, 'offsets_cache.json')

    @staticmethod
    def set_console_title(title):
        """Sets the console window title."""
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    @staticmethod
    def fetch_offsets():
        """Fetches offsets and client data from remote sources or local cache."""
        try:
            response_offset = get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json")
            response_client = get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json")

            if response_offset.status_code != 200 or response_client.status_code != 200:
                logging.error(f"{Fore.RED}Failed to fetch offsets from server.")
                return None, None

            offset = response_offset.json()
            client = response_client.json()

            if os.path.exists(Utility.CACHE_FILE):
                with open(Utility.CACHE_FILE, 'r') as f:
                    cached_data = json.load(f)

                if cached_data.get('offsets') != offset or cached_data.get('client') != client:
                    logging.info(f"{Fore.YELLOW}Offsets have changed, updating cache...")
                    with open(Utility.CACHE_FILE, 'w') as f:
                        json.dump({'offsets': offset, 'client': client}, f)
                else:
                    logging.info(f"{Fore.CYAN}Using cached offsets.")
                    return cached_data['offsets'], cached_data['client']
            else:
                os.makedirs(Utility.CACHE_DIRECTORY, exist_ok=True)
                with open(Utility.CACHE_FILE, 'w') as f:
                    json.dump({'offsets': offset, 'client': client}, f)

            return offset, client
        except Exception as e:
            logging.error(f"{Fore.RED}Failed to fetch offsets: {e}")
            logging.error(f"{Fore.RED}Please report this issue on the GitHub repository: https://github.com/Jesewe/cs2-noflash/issues")
            return None, None
        
class Entity:
    def __init__(self):
        self.b_valid = False
        self.base_address = 0

class PymemHandler:
    """Handles interaction with the game process using pymem."""

    def __init__(self, process_name="cs2.exe"):
        self.pm = None
        self.client_base = None
        self.process_name = process_name
        client_data = Utility.fetch_offsets()
        self.m_entitySpottedState = client_data["client.dll"]["classes"]["C_CSPlayerPawn"]["fields"]["m_entitySpottedState"]
        self.m_bSpotted = client_data["client.dll"]["classes"]["EntitySpottedState_t"]["fields"]["m_bSpotted"]
        
    def initialize_pymem(self):
        """Initializes Pymem and attaches to the game process."""
        try:
            self.pm = pymem.Pymem("cs2.exe")
            logging.info(f"{Fore.GREEN}Successfully attached to cs2.exe process.")
        except pymem.exception.ProcessNotFound:
            logging.error(f"{Fore.RED}Could not find cs2.exe process. Please make sure the game is running.")
        except pymem.exception.PymemError as e:
            logging.error(f"{Fore.RED}Pymem encountered an error: {e}")
        except Exception as e:
            logging.error(f"{Fore.RED}Unexpected error during Pymem initialization: {e}")
        return self.pm is not None

    def get_client_module(self):
        """Retrieves the client.dll module base address."""
        try:
            if self.client_base is None:
                client_module = pymem.process.module_from_name(self.pm.process_handle, "client.dll")
                if not client_module:
                    raise pymem.exception.ModuleNotFoundError("client.dll not found")
                self.client_base = client_module.lpBaseOfDll
                logging.info(f"{Fore.GREEN}client.dll module found at {hex(self.client_base)}.")
        except pymem.exception.ModuleNotFoundError as e:
            logging.error(f"{Fore.RED}Error: {e}. Ensure client.dll is loaded.")
        except Exception as e:
            logging.error(f"{Fore.RED}Unexpected error retrieving client module: {e}")
        return self.client_base is not None

    def read_entity_address(self, list_entry, player_pawn):
        """Read the base address of an entity."""
        return self.pm.read_uint(list_entry + 120 * (player_pawn & 0x1FF))

    def mark_entity_spotted(self, entity_base_address):
        """Mark the entity as spotted by writing to memory."""
        self.pm.write_bool(entity_base_address + self.m_entitySpottedState + self.m_bSpotted, True)

class RadarScript:
    """Main script for managing entities and radar functionality."""
    
    def __init__(self):
        offsets, client_data = Utility.fetch_offsets()
        self.pymem_handler = PymemHandler()
        self.entity_list = []
        self.global_config = {'enable_radar': True}
        self.m_entitySpottedState = client_data["client.dll"]["classes"]["C_CSPlayerPawn"]["fields"]["m_entitySpottedState"]
        self.m_bSpotted = client_data["client.dll"]["classes"]["EntitySpottedState_t"]["fields"]["m_bSpotted"]
        self.dwEntityList = offsets["client.dll"]["dwEntityList"]
        self.dwLocalPlayerPawn = offsets["client.dll"]["dwLocalPlayerPawn"]
        self.dwLocalPlayerController = offsets["client.dll"]["dwLocalPlayerController"]
        self.m_hPlayerPawn = client_data["client.dll"]["classes"]["CCSPlayerController"]["fields"]["m_hPlayerPawn"]
        self.base_address = None

    def update_entity(self, entity, player_index, list_entry, player_pawn, player_base_address):
        """Update entity information."""
        
        player_index = 1  
        entity.bvalid = False

        # Calculate the first list entry
        list_entry_offset = (8 * (player_index & 0x7FFF) >> 9)
        list_entry_address = self.dwEntityList + list_entry_offset + 16
        list_entry1 = self.pymem_handler.pm.read_int(list_entry_address)
        if not list_entry1:
                entity.bvalid = False
                return

            # Calculate the player entity address
        player_ent_offset = 120 * (player_index & 0x1FF)
        player_ent_address = list_entry1 + player_ent_offset
        player_ent = self.pymem_handler.pm.read_int(player_ent_address)
        if not player_ent:
                entity.bvalid = False
                return

            # Read the player's pawn
        player_pawn = self.pymem_handler.pm.read_int(player_ent + self.m_hPlayerPawn)

            # Calculate the second list entry
        list_entry_offset2 = (8 * (player_pawn & 0x7FFF) >> 9)
        list_entry_address2 = self.dwEntityList + list_entry_offset2 + 16
        list_entry2 = self.pymem_handler.pm.read_int(list_entry_address2)
        if not list_entry2:
                entity.bvalid = False
                return

            # Read the base address of the entity
        entity_offset = 120 * (player_pawn & 0x1FF)
        entity_address = list_entry2 + entity_offset
        entity.base_address = entity_address
        if not entity_address or entity_address == player_base_address:
                entity.bvalid = False
        else:
                entity.bvalid = True
    def radar(self, entity):
        """Mark the entity as spotted on the radar."""
        if self.global_config['enable_radar'] and entity.bvalid:
            self.pymem_handler.pm.write_bool(entity.base_address + self.m_entitySpottedState + self.m_bSpotted , 1)

   def render_entities(self):
        """Process and render all entities on radar."""
        client_base = self.pymem_handler.client_base
        if client_base is None:
            logging.error("client_base is None. Cannot proceed with render_entities.")
            return

        try:
            # Calculate list_entry and validate
            list_entry = client_base + self.dwEntityList
            if list_entry <= 0:
                logging.error(f"Invalid list_entry: {list_entry}")
                return

            # Calculate local_player_controller and validate
            local_player_controller = self.pymem_handler.pm.read_int(client_base + self.dwLocalPlayerController)
            if local_player_controller <= 0:
                logging.error(f"Invalid local_player_controller: {local_player_controller}")
                return

            # Calculate player_base_address and validate
            player_base_address = self.pymem_handler.pm.read_int(local_player_controller + self.m_hPlayerPawn)
            if player_base_address <= 0:
                logging.error(f"Invalid player_base_address: {player_base_address}")
                return

            # Process each entity
            for i, enemy in enumerate(self.entity_list):
                self.update_entity(enemy, i, list_entry, player_base_address, player_base_address)

            # Only attempt radar update if the entity address is valid
            if enemy.base_address and enemy.base_address > 0:
                if enemy.bvalid:
                    self.radar(enemy)
                else:
                    logging.debug(f"Entity {i} is invalid, skipping radar update.")
            else:
                logging.warning(f"Invalid base_address for entity {i}: {enemy.base_address}")

        except pymem.exception.MemoryReadError as e:
            logging.error(f"Memory read error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error occurred while rendering entities: {e}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    script = RadarScript()
    if script.pymem_handler.initialize_pymem() and script.pymem_handler.get_client_module():
        while True:  # Thêm vòng lặp while True
            script.radar()
            time.sleep(0.1) 
