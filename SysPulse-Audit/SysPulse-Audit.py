"""
sysinfo.py — Outil de collecte d'informations système
Auteur  : [Ton nom]
GitHub  : [Ton repo]
Usage   : python sysinfo.py          → menu interactif
          python sysinfo.py --all    → rapport complet direct
          python sysinfo.py --json   → sortie JSON brute
          python sysinfo.py --save   → sauvegarde JSON + TXT
"""

import platform, socket, os, sys, json, argparse, datetime, subprocess, uuid, time, shutil, glob, re

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

# ─────────────────────────────────────────────────────────────────────────────
# COULEURS ANSI
# ─────────────────────────────────────────────────────────────────────────────

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    BLUE   = "\033[94m"
    MAGENTA= "\033[95m"
    DIM    = "\033[2m"

def c(color, text):
    return f"{color}{text}{C.RESET}"

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"

def _run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""

def _bar(percent, width=30):
    """Barre de progression ASCII colorée."""
    filled = int(width * percent / 100)
    bar    = "█" * filled + "░" * (width - filled)
    color  = C.GREEN if percent < 60 else (C.YELLOW if percent < 85 else C.RED)
    return f"{color}{bar}{C.RESET} {percent:.1f}%"

def _clear():
    os.system("cls" if os.name == "nt" else "clear")

def _sep(char="─", n=60, color=C.DIM):
    print(c(color, char * n))

def _title(text):
    _sep("═", 60, C.CYAN)
    print(c(C.BOLD + C.CYAN, f"  ◆ {text}"))
    _sep("═", 60, C.CYAN)

def _row(label, value, label_w=28):
    print(f"  {c(C.DIM, label.ljust(label_w))} {c(C.GREEN, str(value))}")

def _wait():
    input(c(C.DIM, "\n  [ Appuie sur Entrée pour revenir au menu ]"))

# ─────────────────────────────────────────────────────────────────────────────
# COLLECTEURS
# ─────────────────────────────────────────────────────────────────────────────

def get_os_info():
    return {
        "système"        : platform.system(),
        "version"        : platform.version(),
        "release"        : platform.release(),
        "architecture"   : platform.machine(),
        "plateforme"     : platform.platform(),
        "python_version" : sys.version.split()[0],
        "répertoire_cwd" : os.getcwd(),
        "executable_py"  : sys.executable,
    }

def get_cpu_info():
    info = {"processeur": platform.processor() or "N/A", "architecture": platform.machine()}
    if PSUTIL_OK:
        freq = psutil.cpu_freq()
        per_core = psutil.cpu_percent(interval=0.5, percpu=True)
        info.update({
            "coeurs_physiques"  : psutil.cpu_count(logical=False),
            "coeurs_logiques"   : psutil.cpu_count(logical=True),
            "fréquence_mhz"     : f"{freq.current:.0f}" if freq else "N/A",
            "fréquence_max_mhz" : f"{freq.max:.0f}" if freq else "N/A",
            "utilisation_%"     : psutil.cpu_percent(interval=1),
            "par_coeur_%"       : per_core,
        })
    return info

def get_ram_info():
    if not PSUTIL_OK:
        return {"erreur": "psutil requis"}
    mem  = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "totale"         : _bytes(mem.total),
        "disponible"     : _bytes(mem.available),
        "utilisée"       : _bytes(mem.used),
        "utilisation_%"  : mem.percent,
        "swap_totale"    : _bytes(swap.total),
        "swap_utilisée"  : _bytes(swap.used),
        "swap_%"         : swap.percent,
    }

def get_disk_info():
    if not PSUTIL_OK:
        return []
    disques = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            io    = psutil.disk_io_counters(perdisk=True) or {}
            name  = os.path.basename(part.device) or part.device
            disk_io = io.get(name, None)
            disques.append({
                "device"         : part.device,
                "point_montage"  : part.mountpoint,
                "système_fich."  : part.fstype,
                "total"          : _bytes(usage.total),
                "utilisé"        : _bytes(usage.used),
                "libre"          : _bytes(usage.free),
                "utilisation_%"  : usage.percent,
                "lectures_io"    : disk_io.read_count  if disk_io else "N/A",
                "écritures_io"   : disk_io.write_count if disk_io else "N/A",
            })
        except PermissionError:
            pass
    return disques

def get_network_info():
    info = {
        "hostname"    : socket.gethostname(),
        "adresse_ip"  : socket.gethostbyname(socket.gethostname()),
        "mac"         : ":".join(["{:02x}".format((uuid.getnode() >> i) & 0xFF) for i in range(0, 48, 8)][::-1]),
    }
    if PSUTIL_OK:
        interfaces = {}
        for name, addrs in psutil.net_if_addrs().items():
            interfaces[name] = [{"famille": str(a.family), "adresse": a.address} for a in addrs]
        info["interfaces"] = interfaces
        stats = psutil.net_io_counters()
        info["octets_envoyés"] = _bytes(stats.bytes_sent)
        info["octets_reçus"]   = _bytes(stats.bytes_recv)
        info["paquets_envoyés"]= stats.packets_sent
        info["paquets_reçus"]  = stats.packets_recv
        # Connexions actives
        try:
            conns = psutil.net_connections(kind="inet")
            info["connexions_actives"] = len([c for c in conns if c.status == "ESTABLISHED"])
        except Exception:
            info["connexions_actives"] = "N/A"
    return info

def get_boot_info():
    if not PSUTIL_OK:
        return {"erreur": "psutil requis"}
    boot_dt = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime  = datetime.datetime.now() - boot_dt
    return {
        "démarrage" : boot_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime"    : str(uptime).split(".")[0],
    }

def get_users_info():
    if not PSUTIL_OK:
        return []
    return [{
        "nom"      : u.name,
        "terminal" : u.terminal or "N/A",
        "hôte"     : u.host or "local",
        "depuis"   : datetime.datetime.fromtimestamp(u.started).strftime("%Y-%m-%d %H:%M:%S"),
    } for u in psutil.users()]

def get_processes_info(top_n=15, sort_by="ram"):
    if not PSUTIL_OK:
        return []
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent", "status", "username"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    key = "memory_percent" if sort_by == "ram" else "cpu_percent"
    procs.sort(key=lambda x: x.get(key) or 0, reverse=True)
    return procs[:top_n]

def get_battery_info():
    if not PSUTIL_OK:
        return {"erreur": "psutil requis"}
    batt = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if not batt:
        return {"disponible": False}
    return {
        "disponible"    : True,
        "charge_%"      : batt.percent,
        "branché"       : batt.power_plugged,
        "temps_restant" : (str(datetime.timedelta(seconds=batt.secsleft))
                           if batt.secsleft > 0 else "Calcul..."),
    }

def get_temperatures():
    if not PSUTIL_OK or not hasattr(psutil, "sensors_temperatures"):
        return {"disponible": False}
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return {"disponible": False}
        result = {}
        for name, entries in temps.items():
            result[name] = [{"label": e.label or "core", "temp_°C": e.current} for e in entries]
        return result
    except Exception:
        return {"disponible": False}

def get_gpu_info():
    """Tente de récupérer les infos GPU via nvidia-smi ou wmic."""
    info = {}
    nv = _run("nvidia-smi --query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu --format=csv,noheader,nounits")
    if nv:
        parts = [p.strip() for p in nv.split(",")]
        if len(parts) >= 5:
            info = {
                "nom"             : parts[0],
                "mémoire_totale"  : f"{parts[1]} MB",
                "mémoire_utilisée": f"{parts[2]} MB",
                "température_°C"  : parts[3],
                "utilisation_%"   : parts[4],
            }
    elif os.name == "nt":
        wmic = _run("wmic path win32_VideoController get caption /value")
        if wmic:
            info["nom"] = wmic.split("=")[-1]
    if not info:
        info["note"] = "nvidia-smi non disponible ou aucun GPU NVIDIA détecté"
    return info

def get_installed_packages():
    """Liste les packages Python installés."""
    out = _run(f'"{sys.executable}" -m pip list --format=freeze')
    if not out:
        return []
    pkgs = []
    for line in out.splitlines():
        if "==" in line:
            name, ver = line.split("==", 1)
            pkgs.append({"package": name, "version": ver})
    return pkgs

def get_open_ports():
    """Retourne les ports en écoute."""
    if not PSUTIL_OK:
        return []
    ports = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == "LISTEN":
                ports.append({
                    "port"      : conn.laddr.port,
                    "adresse"   : conn.laddr.ip,
                    "pid"       : conn.pid,
                })
    except Exception:
        pass
    ports.sort(key=lambda x: x["port"])
    return ports

def get_env_vars():
    keys = {"PATH", "HOME", "USER", "SHELL", "TERM", "LANG", "PWD",
            "LOGNAME", "HOSTNAME", "USERPROFILE", "COMPUTERNAME", "OS",
            "PROCESSOR_IDENTIFIER", "NUMBER_OF_PROCESSORS"}
    return {k: v for k, v in os.environ.items() if k in keys}

def get_ping(host="8.8.8.8"):
    """Ping simple vers l'extérieur."""
    param = "-n" if os.name == "nt" else "-c"
    result = _run(f"ping {param} 3 {host}")
    if not result:
        return {"hôte": host, "statut": "Échec"}
    # Cherche le temps moyen
    for keyword in ("Average", "avg", "moy"):
        if keyword.lower() in result.lower():
            lines = result.splitlines()
            last  = lines[-1] if lines else result
            return {"hôte": host, "statut": "OK", "résultat": last}
    return {"hôte": host, "statut": "OK"}

def get_public_ip():
    """Récupère l'IP publique via curl/wget."""
    ip = _run("curl -s --max-time 4 https://api.ipify.org") or \
         _run("wget -qO- --timeout=4 https://api.ipify.org")
    return ip or "Non disponible (pas de connexion ou curl/wget absent)"

# ─────────────────────────────────────────────────────────────────────────────
# NOUVEAUX COLLECTEURS
# ─────────────────────────────────────────────────────────────────────────────

def get_installed_software():
    """Liste les logiciels installés (Windows: registre, Linux/Mac: gestionnaire de paquets)."""
    software = []
    if os.name == "nt":
        keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        try:
            import winreg
            for key_path in keys:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            sub_key_name = winreg.EnumKey(key, i)
                            sub_key = winreg.OpenKey(key, sub_key_name)
                            name    = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                            try:
                                version = winreg.QueryValueEx(sub_key, "DisplayVersion")[0]
                            except Exception:
                                version = "N/A"
                            try:
                                publisher = winreg.QueryValueEx(sub_key, "Publisher")[0]
                            except Exception:
                                publisher = "N/A"
                            if name:
                                software.append({"nom": name, "version": version, "éditeur": publisher})
                        except Exception:
                            pass
                except Exception:
                    pass
        except ImportError:
            software.append({"note": "winreg non disponible"})
    elif platform.system() == "Darwin":
        out = _run("system_profiler SPApplicationsDataType -json")
        if out:
            try:
                data = json.loads(out)
                apps = data.get("SPApplicationsDataType", [])
                for app in apps[:100]:
                    software.append({
                        "nom"     : app.get("_name", "?"),
                        "version" : app.get("version", "N/A"),
                        "éditeur" : "N/A",
                    })
            except Exception:
                pass
    else:
        # Linux — dpkg ou rpm
        out = _run("dpkg-query -W -f='${Package}\t${Version}\n'") or \
              _run("rpm -qa --queryformat '%{NAME}\t%{VERSION}\n'")
        for line in out.splitlines()[:100]:
            parts = line.split("\t")
            if len(parts) == 2:
                software.append({"nom": parts[0], "version": parts[1], "éditeur": "N/A"})
    software.sort(key=lambda x: x.get("nom", "").lower())
    return software


def get_wifi_profiles():
    """Liste les réseaux Wi-Fi mémorisés (sans mot de passe)."""
    profiles = []
    if os.name == "nt":
        out = _run("netsh wlan show profiles")
        for line in out.splitlines():
            if "Profil utilisateur" in line or "User profiles" in line or "All User Profile" in line:
                name = line.split(":")[-1].strip()
                if name:
                    profiles.append({"ssid": name})
    elif platform.system() == "Darwin":
        out = _run("networksetup -listpreferredwirelessnetworks en0")
        for line in out.splitlines()[1:]:
            ssid = line.strip()
            if ssid:
                profiles.append({"ssid": ssid})
    else:
        # Linux NetworkManager
        paths = glob.glob("/etc/NetworkManager/system-connections/*.nmconnection") + \
                glob.glob("/etc/NetworkManager/system-connections/*")
        for p in paths:
            try:
                with open(p, "r") as f:
                    content = f.read()
                for line in content.splitlines():
                    if line.startswith("ssid="):
                        profiles.append({"ssid": line.split("=", 1)[1]})
            except Exception:
                pass
    return profiles


def get_startup_programs():
    """Liste les programmes au démarrage."""
    items = []
    if os.name == "nt":
        try:
            import winreg
            for hive, path in [
                (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
            ]:
                try:
                    key = winreg.OpenKey(hive, path)
                    for i in range(winreg.QueryInfoKey(key)[1]):
                        name, val, _ = winreg.EnumValue(key, i)
                        items.append({"nom": name, "commande": val})
                except Exception:
                    pass
        except ImportError:
            pass
        # Dossier Démarrage
        startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        if os.path.isdir(startup_dir):
            for f in os.listdir(startup_dir):
                items.append({"nom": f, "commande": os.path.join(startup_dir, f)})
    elif platform.system() == "Darwin":
        out = _run("osascript -e 'tell application \"System Events\" to get the name of every login item'")
        for name in out.split(", "):
            if name.strip():
                items.append({"nom": name.strip(), "commande": "N/A"})
    else:
        # Linux systemd user services
        out = _run("systemctl list-units --user --type=service --state=enabled --no-pager --plain")
        for line in out.splitlines():
            parts = line.split()
            if parts:
                items.append({"nom": parts[0], "commande": "systemd user service"})
        # crontab
        cron = _run("crontab -l")
        for line in cron.splitlines():
            if line and not line.startswith("#"):
                items.append({"nom": "cron", "commande": line.strip()})
    return items


def get_scheduled_tasks():
    """Tâches planifiées (Windows: schtasks, Linux: cron system, Mac: launchd)."""
    tasks = []
    if os.name == "nt":
        out = _run('schtasks /query /fo CSV /nh')
        for line in out.splitlines()[:40]:
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 3:
                tasks.append({
                    "nom"   : parts[0],
                    "statut": parts[2] if len(parts) > 2 else "N/A",
                })
    elif platform.system() == "Darwin":
        out = _run("launchctl list")
        for line in out.splitlines()[1:30]:
            parts = line.split()
            if len(parts) >= 3:
                tasks.append({"nom": parts[2], "statut": parts[1]})
    else:
        for cron_file in ["/etc/crontab"] + glob.glob("/etc/cron.d/*"):
            try:
                with open(cron_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            tasks.append({"nom": cron_file, "commande": line[:80]})
            except Exception:
                pass
    return tasks[:40]


def get_user_accounts():
    """Comptes utilisateurs locaux + groupes."""
    accounts = []
    if os.name == "nt":
        out = _run("net user")
        # On nettoie la sortie
        lines = out.splitlines()
        in_users = False
        for line in lines:
            if "---" in line:
                in_users = True
                continue
            if in_users and line.strip() and "La commande" not in line and "The command" not in line:
                for name in line.split():
                    if name:
                        accounts.append({"nom": name, "groupe": "N/A"})
    else:
        try:
            with open("/etc/passwd") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) >= 7 and parts[6] not in ("/sbin/nologin", "/bin/false", "/usr/sbin/nologin"):
                        accounts.append({
                            "nom"        : parts[0],
                            "uid"        : parts[2],
                            "gid"        : parts[3],
                            "home"       : parts[5],
                            "shell"      : parts[6],
                        })
        except Exception:
            pass
    return accounts


def get_antivirus_firewall():
    """État antivirus et pare-feu."""
    info = {}
    if os.name == "nt":
        # Pare-feu Windows
        fw = _run("netsh advfirewall show allprofiles state")
        info["pare_feu_windows"] = "Actif" if "ON" in fw.upper() else ("Inactif" if "OFF" in fw.upper() else "N/A")
        # Antivirus via WMI
        av = _run('wmic /namespace:\\\\root\\SecurityCenter2 path AntiVirusProduct get displayName /value')
        avs = [l.split("=")[-1] for l in av.splitlines() if "displayName=" in l]
        info["antivirus"] = avs if avs else ["Non détecté"]
        # Windows Defender
        wd = _run("powershell -command \"Get-MpComputerStatus | Select-Object -ExpandProperty RealTimeProtectionEnabled\"")
        info["defender_temps_réel"] = "Actif" if "True" in wd else ("Inactif" if "False" in wd else "N/A")
    elif platform.system() == "Darwin":
        fw_out = _run("defaults read /Library/Preferences/com.apple.alf globalstate")
        info["pare_feu_macos"] = "Actif" if fw_out in ("1", "2") else "Inactif"
    else:
        # Linux
        ufw = _run("ufw status")
        iptables = _run("iptables -L -n --line-numbers 2>/dev/null | head -5")
        info["ufw"]      = ufw.splitlines()[0] if ufw else "Non installé"
        info["iptables"] = "Actif" if iptables else "Non disponible"
    return info


# ─────────────────────────────────────────────────────────────────────────────
# RAPPORT COMPLET
# ─────────────────────────────────────────────────────────────────────────────

def collect_all():
    return {
        "horodatage"     : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "système"        : get_os_info(),
        "cpu"            : get_cpu_info(),
        "ram"            : get_ram_info(),
        "disques"        : get_disk_info(),
        "réseau"         : get_network_info(),
        "démarrage"      : get_boot_info(),
        "utilisateurs"   : get_users_info(),
        "top_processus"  : get_processes_info(),
        "batterie"       : get_battery_info(),
        "températures"   : get_temperatures(),
        "gpu"            : get_gpu_info(),
        "ports_ouverts"  : get_open_ports(),
        "env_vars"       : get_env_vars(),
        "logiciels"      : get_installed_software(),
        "wifi_profiles"  : get_wifi_profiles(),
        "démarrage_auto" : get_startup_programs(),
        "tâches_planif." : get_scheduled_tasks(),
        "comptes_users"  : get_user_accounts(),
        "sécurité"       : get_antivirus_firewall(),
    }

# ─────────────────────────────────────────────────────────────────────────────
# AFFICHAGE PAR SECTION
# ─────────────────────────────────────────────────────────────────────────────

def show_os():
    _clear(); _title("Système d'exploitation")
    d = get_os_info()
    for k, v in d.items():
        _row(k, v)
    _wait()

def show_cpu():
    _clear(); _title("Processeur (CPU)")
    d = get_cpu_info()
    for k, v in d.items():
        if k == "par_coeur_%":
            print(f"\n  {c(C.DIM,'Utilisation par cœur :')}")
            for i, pct in enumerate(v):
                print(f"    Cœur {i:<3}  {_bar(pct, 25)}")
        elif k == "utilisation_%":
            print(f"\n  {'Utilisation globale'.ljust(28)} {_bar(v)}")
        else:
            _row(k, v)
    _wait()

def show_ram():
    _clear(); _title("Mémoire RAM & Swap")
    d = get_ram_info()
    for k, v in d.items():
        if k in ("utilisation_%", "swap_%"):
            print(f"\n  {k.ljust(28)} {_bar(v)}")
        else:
            _row(k, v)
    _wait()

def show_disks():
    _clear(); _title("Disques")
    for i, disk in enumerate(get_disk_info()):
        device = disk["device"]
        print(f"\n  {c(C.YELLOW + C.BOLD, f'Disque {i+1} — {device}')}")
        _sep()
        for k, v in disk.items():
            if k == "utilisation_%":
                print(f"  {'utilisation'.ljust(28)} {_bar(v)}")
            else:
                _row(k, v)
    _wait()

def show_network():
    _clear(); _title("Réseau")
    d = get_network_info()
    skip = {"interfaces"}
    for k, v in d.items():
        if k not in skip:
            _row(k, v)
    if "interfaces" in d:
        print(f"\n  {c(C.DIM,'Interfaces :')}")
        for iface, addrs in d["interfaces"].items():
            print(f"    {c(C.YELLOW, iface)}")
            for a in addrs:
                print(f"      {a['famille']:<20} {a['adresse']}")
    _wait()

def show_processes():
    _clear()
    print(c(C.DIM, "\n  Trier par : ") + c(C.CYAN, "[1]") + " RAM  " + c(C.CYAN, "[2]") + " CPU")
    ch = input("  Choix : ").strip()
    sort_by = "cpu" if ch == "2" else "ram"
    _clear(); _title(f"Top 15 processus (tri : {'CPU' if sort_by=='cpu' else 'RAM'})")
    print(f"  {'PID':<7}{'Nom':<30}{'RAM %':<10}{'CPU %':<10}{'Statut'}")
    _sep()
    for p in get_processes_info(sort_by=sort_by):
        pid   = p.get("pid", "?")
        name  = (p.get("name") or "?")[:29]
        ram   = f"{p.get('memory_percent') or 0:.2f}"
        cpu   = f"{p.get('cpu_percent') or 0:.2f}"
        stat  = p.get("status", "?")
        print(f"  {c(C.DIM,str(pid)):<14}{c(C.CYAN,name):<39}{c(C.YELLOW,ram):<18}{c(C.RED,cpu):<18}{c(C.DIM,stat)}")
    _wait()

def show_battery():
    _clear(); _title("Batterie")
    d = get_battery_info()
    if not d.get("disponible"):
        print(c(C.YELLOW, "  Aucune batterie détectée (machine de bureau ou erreur)"))
    else:
        for k, v in d.items():
            if k == "charge_%":
                print(f"\n  {'charge'.ljust(28)} {_bar(v)}")
            else:
                _row(k, v)
    _wait()

def show_temperatures():
    _clear(); _title("Températures")
    d = get_temperatures()
    if not d.get("disponible", True) or d == {"disponible": False}:
        print(c(C.YELLOW, "  Capteurs de température non disponibles sur ce système"))
    else:
        for sensor, entries in d.items():
            print(f"\n  {c(C.YELLOW, sensor)}")
            for e in entries:
                temp  = e["temp_°C"]
                color = C.GREEN if temp < 60 else (C.YELLOW if temp < 80 else C.RED)
                print(f"    {e['label']:<25} {c(color, f'{temp} °C')}")
    _wait()

def show_gpu():
    _clear(); _title("GPU")
    d = get_gpu_info()
    for k, v in d.items():
        _row(k, v)
    _wait()

def show_ports():
    _clear(); _title("Ports en écoute")
    ports = get_open_ports()
    if not ports:
        print(c(C.YELLOW, "  Aucun port trouvé (droits insuffisants ?)"))
    else:
        print(f"  {'Port':<8}{'Adresse':<25}{'PID'}")
        _sep()
        for p in ports:
            print(f"  {c(C.CYAN,str(p['port'])):<16}{c(C.DIM,p['adresse']):<33}{c(C.DIM,str(p['pid']))}")
    _wait()

def show_ping():
    _clear(); _title("Test de connectivité")
    host = input(c(C.DIM, "  Hôte à pinger [8.8.8.8] : ")).strip() or "8.8.8.8"
    print(c(C.DIM, f"\n  Ping de {host} en cours..."))
    d = get_ping(host)
    for k, v in d.items():
        _row(k, v)
    print(c(C.DIM, "\n  Récupération de l'IP publique..."))
    _row("IP publique", get_public_ip())
    _wait()

def show_packages():
    _clear(); _title("Packages Python installés")
    pkgs = get_installed_packages()
    if not pkgs:
        print(c(C.YELLOW, "  Impossible de lister les packages"))
    else:
        print(f"  {c(C.DIM, f'{len(pkgs)} packages trouvés')}\n")
        print(f"  {'Package':<35}{'Version'}")
        _sep()
        for p in pkgs[:50]:
            print(f"  {c(C.CYAN, p['package']):<43}{c(C.DIM, p['version'])}")
        if len(pkgs) > 50:
            print(c(C.DIM, f"\n  ... et {len(pkgs)-50} autres (utilise --save pour tout voir)"))
    _wait()

def show_env():
    _clear(); _title("Variables d'environnement")
    for k, v in get_env_vars().items():
        _row(k, v[:80] + ("…" if len(v) > 80 else ""))
    _wait()

def show_full_report():
    _clear(); _title("Rapport complet")
    data = collect_all()
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    _wait()

def save_report():
    _clear(); _title("Sauvegarde du rapport")
    print(c(C.DIM, "  Collecte des données..."))
    data = collect_all()
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON
    fjson = f"sysinfo_{ts}.json"
    with open(fjson, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(c(C.GREEN, f"  [✓] JSON sauvegardé  : {fjson}"))

    # TXT
    ftxt = f"sysinfo_{ts}.txt"
    with open(ftxt, "w", encoding="utf-8") as f:
        f.write(f"RAPPORT SYSTÈME — {data['horodatage']}\n")
        f.write("=" * 60 + "\n\n")
        def dump(obj, indent=0):
            pad = "  " * indent
            if isinstance(obj, dict):
                for k, v in obj.items():
                    f.write(f"{pad}{k}:\n")
                    dump(v, indent + 1)
            elif isinstance(obj, list):
                for item in obj:
                    dump(item, indent)
                    f.write(f"{pad}---\n")
            else:
                f.write(f"{pad}{obj}\n")
        dump(data)
    print(c(C.GREEN, f"  [✓] TXT sauvegardé   : {ftxt}"))
    _wait()

def show_software():
    _clear(); _title("Logiciels installés")
    sw = get_installed_software()
    if not sw:
        print(c(C.YELLOW, "  Aucun logiciel trouvé"))
    else:
        print(f"  {c(C.DIM, str(len(sw)) + ' logiciels trouvés')}\n")
        print(f"  {'Nom':<45}{'Version':<20}{'Éditeur'}")
        _sep()
        for s in sw[:60]:
            nom  = s.get("nom", "?")[:44]
            ver  = s.get("version", "N/A")[:19]
            pub  = s.get("éditeur", "N/A")[:30]
            print(f"  {c(C.CYAN, nom):<53}{c(C.DIM, ver):<28}{c(C.DIM, pub)}")
        if len(sw) > 60:
            print(c(C.DIM, f"\n  ... et {len(sw)-60} autres (utilise --save pour tout voir)"))
    _wait()

def show_wifi():
    _clear(); _title("Réseaux Wi-Fi mémorisés")
    profiles = get_wifi_profiles()
    if not profiles:
        print(c(C.YELLOW, "  Aucun profil Wi-Fi trouvé (droits insuffisants ?)"))
    else:
        print(f"  {c(C.DIM, str(len(profiles)) + ' réseaux mémorisés')}\n")
        for i, p in enumerate(profiles):
            print(f"  {c(C.DIM, str(i+1).rjust(3) + '.'):<12} {c(C.CYAN, p['ssid'])}")
    _wait()

def show_startup():
    _clear(); _title("Programmes au démarrage")
    items = get_startup_programs()
    if not items:
        print(c(C.YELLOW, "  Aucun programme trouvé au démarrage"))
    else:
        print(f"  {'Nom':<35}{'Commande / Chemin'}")
        _sep()
        for it in items:
            nom = it.get("nom", "?")[:34]
            cmd = it.get("commande", "N/A")[:60]
            print(f"  {c(C.CYAN, nom):<43}{c(C.DIM, cmd)}")
    _wait()

def show_tasks():
    _clear(); _title("Tâches planifiées")
    tasks = get_scheduled_tasks()
    if not tasks:
        print(c(C.YELLOW, "  Aucune tâche planifiée trouvée"))
    else:
        print(f"  {'Nom / Source':<45}{'Statut / Commande'}")
        _sep()
        for t in tasks:
            nom = t.get("nom", "?")[:44]
            val = t.get("statut", t.get("commande", "N/A"))[:50]
            print(f"  {c(C.CYAN, nom):<53}{c(C.DIM, val)}")
    _wait()

def show_accounts():
    _clear(); _title("Comptes utilisateurs locaux")
    accounts = get_user_accounts()
    if not accounts:
        print(c(C.YELLOW, "  Aucun compte trouvé"))
    else:
        if "uid" in (accounts[0] if accounts else {}):
            print(f"  {'Nom':<20}{'UID':<8}{'GID':<8}{'Shell':<25}{'Home'}")
            _sep()
            for a in accounts:
                print(f"  {c(C.CYAN, a.get('nom','?')):<28}{c(C.DIM,a.get('uid','?')):<16}{c(C.DIM,a.get('gid','?')):<16}{c(C.DIM,a.get('shell','?')):<33}{c(C.DIM,a.get('home','?'))}")
        else:
            print(f"  {'Nom':<30}{'Groupe'}")
            _sep()
            for a in accounts:
                print(f"  {c(C.CYAN, a.get('nom','?')):<38}{c(C.DIM, a.get('groupe','N/A'))}")
    _wait()

def show_security():
    _clear(); _title("Sécurité — Antivirus & Pare-feu")
    d = get_antivirus_firewall()
    for k, v in d.items():
        if isinstance(v, list):
            print(f"\n  {c(C.DIM, k)} :")
            for item in v:
                color = C.GREEN if "actif" not in str(item).lower() else C.GREEN
                print(f"    {c(C.CYAN, str(item))}")
        else:
            color = C.GREEN if str(v).lower() in ("actif", "true", "1") else (C.RED if str(v).lower() in ("inactif", "false", "0") else C.DIM)
            print(f"  {c(C.DIM, k.ljust(28))} {c(color, str(v))}")
    _wait()

# ─────────────────────────────────────────────────────────────────────────────
# MENU INTERACTIF
# ─────────────────────────────────────────────────────────────────────────────

MENU = [
    ("1",  "Système d'exploitation",      show_os),
    ("2",  "Processeur (CPU)",            show_cpu),
    ("3",  "Mémoire RAM & Swap",          show_ram),
    ("4",  "Disques",                     show_disks),
    ("5",  "Réseau & Interfaces",         show_network),
    ("6",  "Processus actifs (Top 15)",   show_processes),
    ("7",  "Batterie",                    show_battery),
    ("8",  "Températures",                show_temperatures),
    ("9",  "GPU",                         show_gpu),
    ("10", "Ports en écoute",             show_ports),
    ("11", "Test ping / IP publique",     show_ping),
    ("12", "Packages Python",             show_packages),
    ("13", "Variables d'environnement",   show_env),
    ("14", "Logiciels installés",         show_software),
    ("15", "Réseaux Wi-Fi mémorisés",     show_wifi),
    ("16", "Programmes au démarrage",     show_startup),
    ("17", "Tâches planifiées",           show_tasks),
    ("18", "Comptes utilisateurs",        show_accounts),
    ("19", "Antivirus & Pare-feu",        show_security),
    ("20", "Rapport complet (JSON)",      show_full_report),
    ("21", "💾  Sauvegarder le rapport",  save_report),
    ("0",  "Quitter",                     None),
]

def print_menu():
    _clear()
    w = shutil.get_terminal_size((70, 24)).columns
    print()
    print(c(C.CYAN + C.BOLD, "  ███████╗██╗   ██╗███████╗██╗███╗   ██╗███████╗ ██████╗ "))
    print(c(C.CYAN,           "  ██╔════╝╚██╗ ██╔╝██╔════╝██║████╗  ██║██╔════╝██╔═══██╗"))
    print(c(C.CYAN,           "  ███████╗ ╚████╔╝ ███████╗██║██╔██╗ ██║█████╗  ██║   ██║"))
    print(c(C.CYAN,           "  ╚════██║  ╚██╔╝  ╚════██║██║██║╚██╗██║██╔══╝  ██║   ██║"))
    print(c(C.CYAN + C.BOLD,  "  ███████║   ██║   ███████║██║██║ ╚████║██║     ╚██████╔╝"))
    print(c(C.DIM,             "  ╚══════╝   ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝╚═╝      ╚═════╝ "))
    print(c(C.DIM, f"\n  {'Outil de collecte d informations système':^56}"))
    _sep("─", 60, C.DIM)
    print()
    # 2 colonnes — 11 items à gauche, reste à droite
    left  = MENU[:11]
    right = MENU[11:]
    for i in range(max(len(left), len(right))):
        l = left[i]  if i < len(left)  else None
        r = right[i] if i < len(right) else None
        lstr = f"  {c(C.CYAN,'['+l[0]+']'):<20} {c(C.BOLD,l[1]):<30}" if l else " " * 52
        rstr = f"  {c(C.CYAN,'['+r[0]+']'):<20} {c(C.BOLD,r[1])}" if r else ""
        print(lstr + rstr)
    print()
    _sep("─", 60, C.DIM)

def interactive_menu():
    if not PSUTIL_OK:
        print(c(C.YELLOW, "\n  [!] psutil non installé : pip install psutil\n"))
    actions = {item[0]: item[2] for item in MENU}
    while True:
        print_menu()
        choice = input(c(C.CYAN, "\n  → Ton choix : ")).strip()
        if choice == "0":
            _clear()
            print(c(C.GREEN, "\n  À bientôt !\n"))
            break
        fn = actions.get(choice)
        if fn:
            fn()
        else:
            print(c(C.RED, "  Choix invalide."))
            time.sleep(0.8)

# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="sysinfo — collecte d'infos système")
    parser.add_argument("--all",  action="store_true", help="Rapport complet (texte)")
    parser.add_argument("--json", action="store_true", help="Sortie JSON brute")
    parser.add_argument("--save", action="store_true", help="Sauvegarde JSON + TXT")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(collect_all(), indent=2, ensure_ascii=False, default=str))
    elif args.all:
        data = collect_all()
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        if args.save:
            save_report()
    elif args.save:
        save_report()
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
