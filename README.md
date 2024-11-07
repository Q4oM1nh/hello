# CS2 RadarHack

This project is a radar enhancement tool for the game CS2, designed to highlight enemy entities in real-time by marking them as "spotted" in the game memory. The script reads and updates memory values in `cs2.exe` using `pymem`, allowing for a radar hack that displays enemies on the player's radar.

## Features

- **Real-Time Radar**: Marks entities (enemies) as spotted, allowing for visibility on the radar.
- **Logging**: Logs important events and errors to a file for easy debugging and analysis.
- **Cache Management**: Stores offsets and client data in a local cache to optimize future runs.
- **Console Display**: Displays important status messages in the console with color-coded output using `colorama`.

## Requirements

- Python 3.8+
- Windows OS (due to dependencies on Windows APIs)
- **Python Libraries**:
  - `pymem`: For reading and writing game memory.
  - `colorama`: For colored console output.
  - `requests`: For fetching data from GitHub.
  - `packaging`: For version management.
  - `pywin32`: For handling Windows processes and console features.

## Usage

- **Run the script** while `cs2.exe` is open. The script will automatically attach to the game process and load necessary offsets from a GitHub repository.
- **Configuration**:
  - To enable or disable radar functionality, modify `self.global_config['enable_radar']` within the `RadarScript` class.
  - Log files are saved to `%LOCALAPPDATA%\Requests\ItsJesewe\crashes`.

## Troubleshooting

- **Error: Could not find cs2.exe process**:
  - Make sure the game is running before executing the script.

- **Error fetching offsets**:
  - Check internet connectivity, as offsets are fetched from GitHub.

- **Game Crashes or Unstable Performance**:
  - Use this script at your own risk, as modifying game memory may lead to unintended behavior.

## Disclaimer

This script is for educational purposes only. Using cheats or hacks in online games is against the terms of service of most games and can result in bans or other penalties. Use this script at your own risk.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.