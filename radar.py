import pymem
import pymem.process
import time
import os
import ctypes
import logging
from requests import get
from colorama import init, Fore

# Initialize colorama for colored console output
init(autoreset=True)

class Logger:
    """Handles logging setup for the application."""
    LOG_DIRECTORY = os.path.expandvars(r'%LOCALAPPDATA%\Requests\ItsJesewe\crashes')
    LOG_FILE = os.path.join(LOG_DIRECTORY, 'radar_logs.log')

    @staticmethod
    def setup_logging():
        """Set up the logging configuration with the default log level INFO."""
        os.makedirs(Logger.LOG_DIRECTORY, exist_ok=True)
        with open(Logger.LOG_FILE, 'w') as f:
            pass

        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s: %(message)s',
            handlers=[logging.FileHandler(Logger.LOG_FILE), logging.StreamHandler()]
        )

class Utility:
    """Contains utility functions for the application."""
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

            return offset, client
        except Exception as e:
            logging.error(f"{Fore.RED}Failed to fetch offsets: {e}")
            return None, None

class Entity:
    def __init__(self):
        self.bvalid = False
        self.base_address = 0

class PymemHandler:
    """Handles interaction with the game process using pymem."""
    def __init__(self, process_name="cs2.exe"):
        self.pm = None
        self.client_base = None
        self.process_name = process_name
        client_data = Utility.fetch_offsets()
        if client_data:
            _, client_data = client_data
            self.m_entitySpottedState = client_data["client.dll"]["classes"]["C_CSPlayerPawn"]["fields"]["m_entitySpottedState"]
            self.m_bSpotted = client_data["client.dll"]["classes"]["EntitySpottedState_t"]["fields"]["m_bSpotted"]

    def initialize_pymem(self):
        """Initializes Pymem and attaches to the game process."""
        try:
            self.pm = pymem.Pymem(self.process_name)
            logging.info(f"{Fore.GREEN}Successfully attached to {self.process_name} process.")
        except pymem.exception.ProcessNotFound:
            logging.error(f"{Fore.RED}Could not find {self.process_name} process. Ensure the game is running.")
        except pymem.exception.PymemError as e:
            logging.error(f"{Fore.RED}Pymem error: {e}")
        return self.pm is not None

    def get_client_module(self):
        """Retrieves the client.dll module base address."""
        try:
            if self.client_base is None:
                client_module = pymem.process.module_from_name(self.pm.process_handle, "client.dll")
                if not client_module:
                    raise pymem.exception.ModuleNotFoundError("client.dll not found")
                self.client_base = client_module.lpBaseOfDll
                logging.info(f"{Fore.GREEN}client.dll found at {hex(self.client_base)}.")
        except pymem.exception.ModuleNotFoundError as e:
            logging.error(f"{Fore.RED}Error: {e}. Ensure client.dll is loaded.")
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
        self.entity_list = [Entity() for _ in range(32)]  # Create a list of entity slots
        self.global_config = {'enable_radar': True}
        if offsets and client_data:
            self.m_entitySpottedState = client_data["client.dll"]["classes"]["C_CSPlayerPawn"]["fields"]["m_entitySpottedState"]
            self.m_bSpotted = client_data["client.dll"]["classes"]["EntitySpottedState_t"]["fields"]["m_bSpotted"]
            self.dwEntityList = offsets["client.dll"]["dwEntityList"]
            self.dwLocalPlayerPawn = offsets["client.dll"]["dwLocalPlayerPawn"]
            self.dwLocalPlayerController = offsets["client.dll"]["dwLocalPlayerController"]
            self.m_hPlayerPawn = client_data["client.dll"]["classes"]["CCSPlayerController"]["fields"]["m_hPlayerPawn"]

    def update_entity(self, entity, player_index, list_entry, player_base_address):
        """Update entity information."""
        entity.bvalid = False
        list_entry_offset = (8 * (player_index & 0x7FFF) >> 9)
        list_entry_address = self.dwEntityList + list_entry_offset + 16
        list_entry1 = self.pymem_handler.pm.read_int(list_entry_address)
        if not list_entry1:
            return

        player_ent_address = list_entry1 + 120 * (player_index & 0x1FF)
        player_ent = self.pymem_handler.pm.read_int(player_ent_address)
        if not player_ent:
            return

        player_pawn = self.pymem_handler.pm.read_int(player_ent + self.m_hPlayerPawn)
        list_entry_offset2 = (8 * (player_pawn & 0x7FFF) >> 9)
        list_entry_address2 = self.dwEntityList + list_entry_offset2 + 16
        list_entry2 = self.pymem_handler.pm.read_int(list_entry_address2)
        if not list_entry2:
            return

        entity_address = list_entry2 + 120 * (player_pawn & 0x1FF)
        entity.base_address = entity_address
        entity.bvalid = bool(entity_address and entity_address != player_base_address)

    def radar(self, entity):
        """Mark the entity as spotted on the radar."""
        if self.global_config['enable_radar'] and entity.bvalid:
            self.pymem_handler.mark_entity_spotted(entity.base_address)

    def render_entities(self):
        """Process and render all entities on radar."""
        client_base = self.pymem_handler.client_base
        if client_base is None:
            logging.error("client_base is None. Cannot proceed with render_entities.")
            return

        try:
            list_entry = client_base + self.dwEntityList
            local_player_controller = self.pymem_handler.pm.read_int(client_base + self.dwLocalPlayerController)
            player_base_address = self.pymem_handler.pm.read_int(local_player_controller + self.m_hPlayerPawn)

            for i, enemy in enumerate(self.entity_list):
                self.update_entity(enemy, i, list_entry, player_base_address)
                if enemy.bvalid:
                    self.radar(enemy)
        except pymem.exception.MemoryReadError as e:
            logging.error(f"Memory read error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while rendering entities: {e}")

if __name__ == '__main__':
    Logger.setup_logging()
    script = RadarScript()
    if script.pymem_handler.initialize_pymem() and script.pymem_handler.get_client_module():
        while True:
            script.render_entities()
            time.sleep(0.1)