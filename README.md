# SysPulse

A comprehensive Python-based system profiler for hardware, network, and process monitoring. Designed for efficient system health assessment and real-time performance tracking.

## 🇫🇷 Description en français
SysPulse est un outil complet de profilage système développé en Python. Il permet d'effectuer un bilan de santé instantané de votre machine en collectant des données sur le matériel, le réseau, les processus actifs et la configuration logicielle.

## 🚀 Key Features / Fonctionnalités
- **System Profiling:** Detailed recovery of OS and hardware configuration.
- **Resource Telemetry:** Real-time CPU, RAM, and GPU analysis.
- **Network Intelligence:** Scan of interfaces, active connections, and listening ports.
- **Software Inventory:** List of installed applications, Python packages, and startup programs.
- **Security Posture:** Quick view of firewall state, antivirus, and scheduled tasks.
- **Data Export:** Automatic report generation in JSON and TXT formats.

## 🛠 Prerequisites / Prérequis
- Python 3.x
- `psutil` library: `pip install psutil`
  
## 💻 Installation
1. Clone this repository:
   
   git clone https://github.com/evanrcl/SysPulse-Audit.git

2.  cd .\SysPulse-Audit\

3.  cd .\SysPulse-Audit\

4.  pip install psutil

5.  python SysPulse-Audit.py

# Generate a full report and save it (JSON + TXT)
python SysPulse-Audit.py --save

# Get raw JSON output
python SysPulse-Audit.py --json

  
