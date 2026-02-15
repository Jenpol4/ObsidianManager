import customtkinter as ctk
import requests
import threading
import os
import subprocess
import time
import json
import re
import zipfile
import sys
import socket
import shutil
from tkinter import Toplevel, Label, filedialog, messagebox
from PIL import Image
from io import BytesIO
from mcstatus import JavaServer, BedrockServer

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- CHEMINS ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DEFAULT_SERVERS_DIR = os.path.join(BASE_DIR, "Serveurs_List")

if not os.path.exists(DEFAULT_SERVERS_DIR): os.makedirs(DEFAULT_SERVERS_DIR)

# --- LIENS ---
URLS_JAVA = {
    "1.20.4": "https://piston-data.mojang.com/v1/objects/8dd1a28015f51b1803213892b50b7b4fc76e594d/server.jar",
    "1.19.4": "https://piston-data.mojang.com/v1/objects/8f3112a1049751cc472ec13e390eade507436aeff/server.jar",
    "1.18.2": "https://piston-data.mojang.com/v1/objects/c8f83c5655308435b3dcf03c06d9fe8740a77469/server.jar"
}
URLS_BEDROCK = {
    "1.21.132.3 (Dernière)": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.132.3.zip"
}

STYLE_CARD = {"fg_color": "#212121", "border_width": 1, "border_color": "#404040", "corner_radius": 6}

# --- CONFIG ---
DEFAULT_PROPERTIES_JAVA = """spawn-protection=16
max-tick-time=60000
query.port=25565
generator-settings=
force-gamemode=false
allow-nether=true
enforce-whitelist=false
gamemode=survival
broadcast-console-to-ops=true
enable-query=false
player-idle-timeout=0
difficulty=easy
spawn-monsters=true
op-permission-level=4
pvp=true
snooper-enabled=true
level-type=default
hardcore=false
enable-command-block=false
max-players=20
network-compression-threshold=256
resource-pack-sha1=
max-world-size=29999984
server-port=25565
server-ip=
spawn-npcs=true
allow-flight=false
level-name=world
view-distance=10
resource-pack=
spawn-animals=true
white-list=false
generate-structures=true
online-mode=true
max-build-height=256
level-seed=
prevent-proxy-connections=false
use-native-transport=true
motd=Un serveur Minecraft
enable-rcon=false
"""

DROPDOWN_OPTIONS = {
    "gamemode": ["survival", "creative", "adventure", "spectator"],
    "difficulty": ["peaceful", "easy", "normal", "hard"],
    "level-type": ["default", "flat", "largebiomes", "amplified"],
    "allow-flight": ["true", "false"], "white-list": ["true", "false"],
    "pvp": ["true", "false"], "online-mode": ["true", "false"],
    "hardcore": ["true", "false"], "enable-command-block": ["true", "false"]
}

TRADUCTION_TITRES = {
    "gamemode": "Mode de jeu", "difficulty": "Difficulté", "max-players": "Joueurs Max",
    "server-port": "Port", "level-seed": "Graine (Seed)", "motd": "MOTD (Accueil)", "server-name": "Nom Serveur",
    "white-list": "Whitelist", "pvp": "PVP", "enable-command-block": "Command Blocks",
    "allow-flight": "Voler", "view-distance": "Distance Vue", "online-mode": "Mode Online",
    "level-name": "Nom Monde", "hardcore": "Hardcore", "spawn-protection": "Protect. Spawn",
    "generate-structures": "Structures", "allow-cheats": "Autoriser Cheats", "level-type": "Type de Monde"
}

INFOS_PROPRIETES = {
    "gamemode": "Mode de jeu (survival, creative).\n(gamemode)",
    "difficulty": "Difficulté (easy, normal, hard).\n(difficulty)",
    "white-list": "Si activé, liste fermée.\n(white-list)",
    "online-mode": "True = Premium. False = Crack.\n(online-mode)",
    "server-port": "Port (Java=25565, Bedrock=19132).\n(server-port)"
}

COLONNE_GAUCHE = ["Général", "Gameplay & Difficulté", "Avancé"]
COLONNE_DROITE = ["Monde & Génération", "Réseau & Sécurité", "Performance"]
CATEGORIES_MAPPING = {
    "motd": "Général", "server-name": "Général", "gamemode": "Gameplay & Difficulté", "difficulty": "Gameplay & Difficulté",
    "pvp": "Gameplay & Difficulté", "hardcore": "Gameplay & Difficulté", "allow-flight": "Gameplay & Difficulté", "allow-cheats": "Gameplay & Difficulté",
    "level-name": "Monde & Génération", "level-seed": "Monde & Génération", "generate-structures": "Monde & Génération", "level-type": "Monde & Génération",
    "server-port": "Réseau & Sécurité", "max-players": "Réseau & Sécurité", "white-list": "Réseau & Sécurité",
    "online-mode": "Réseau & Sécurité", "view-distance": "Performance", "enable-command-block": "Avancé"
}

# --- OUTILS ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip); self.widget.bind("<Leave>", self.hide_tip)
    def show_tip(self, event=None):
        if self.tip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert"); x += self.widget.winfo_rootx() + 25; y += self.widget.winfo_rooty() + 25
        self.tip_window = Toplevel(self.widget); self.tip_window.wm_overrideredirect(True); self.tip_window.wm_geometry(f"+{x}+{y}")
        Label(self.tip_window, text=self.text, background="#ffffe0", relief="solid", borderwidth=1).pack()
    def hide_tip(self, event=None):
        if self.tip_window: self.tip_window.destroy(); self.tip_window = None

def nettoyer_nom_dossier(nom):
    return re.sub(r'[^\w\s-]', '', nom).strip().replace(' ', '_') or "Serveur_Sans_Nom"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "127.0.0.1"

# --- CLASSE GESTION DU SERVEUR ---
class ServerControlPanel(ctk.CTkToplevel):
    def __init__(self, parent, server_path, server_name, server_version, server_type, icon_image):
        super().__init__(parent)
        self.server_path = server_path
        self.server_type = server_type 
        self.icon_image = icon_image
        self.server_process = None
        self.running = False
        self.port_serveur = 19132 if self.server_type == "bedrock" else 25565
        self.ram_allocated = 2 
        
        self.load_extra_config()
        self.lire_port()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.title(f"Gestion : {server_name}")
        self.geometry("1150x750")
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)

        # HEADER
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        if self.icon_image: ctk.CTkLabel(self.top_bar, text="", image=self.icon_image).pack(side="left", padx=10)
        else:
            t_col = "orange" if server_type == "java" else "cyan"
            ctk.CTkLabel(self.top_bar, text=f"[{server_type.upper()}]", text_color=t_col, font=("Arial", 16, "bold")).pack(side="left", padx=10)

        ctk.CTkLabel(self.top_bar, text=f"{server_name} ({server_version})", font=("Arial", 20, "bold")).pack(side="left")
        
        # BOUTONS
        self.btn_power = ctk.CTkButton(self.top_bar, text="▶ DÉMARRER", fg_color="green", font=("Arial", 14, "bold"), command=self.toggle_server_state)
        self.btn_power.pack(side="right", padx=10)

        if self.server_type == "bedrock":
            self.btn_port = ctk.CTkButton(self.top_bar, text=f"Port: {self.port_serveur} ❐", fg_color="#2B2B2B", hover_color="#404040", width=120, command=self.copy_port_to_clipboard)
            self.btn_port.pack(side="right", padx=5)

        self.local_ip = get_local_ip()
        self.btn_ip = ctk.CTkButton(self.top_bar, text=f"IP: {self.local_ip} ❐", fg_color="#2B2B2B", hover_color="#404040", width=160, command=self.copy_ip_to_clipboard)
        self.btn_ip.pack(side="right", padx=5)

        # ONGLETS
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.tab_console = self.tabs.add("Console")
        self.tab_players = self.tabs.add("Joueurs & Modération")
        self.tab_config = self.tabs.add("Configuration")

        self.setup_console_tab()
        self.setup_players_tab()
        self.setup_config_tab()

    def on_close(self):
        if self.running:
            if messagebox.askokcancel("Quitter", "Le serveur est encore allumé. Voulez-vous l'arrêter et fermer la fenêtre ?"):
                self.stop_server()
                self.after(2000, self.destroy)
        else:
            self.destroy()

    def load_extra_config(self):
        try:
            with open(os.path.join(self.server_path, "info.json"), "r") as f:
                data = json.load(f)
                self.ram_allocated = data.get("ram", 2)
        except: pass

    def lire_port(self):
        try:
            with open(os.path.join(self.server_path, "server.properties"), "r") as f:
                for line in f:
                    if line.startswith("server-port="): self.port_serveur = int(line.split("=")[1].strip())
        except: pass

    def copy_ip_to_clipboard(self):
        self.clipboard_clear(); self.clipboard_append(self.local_ip)
        orig = f"IP: {self.local_ip} ❐"; self.btn_ip.configure(text="✅ Copié !", fg_color="green")
        self.after(2000, lambda: self.btn_ip.configure(text=orig, fg_color="#2B2B2B"))

    def copy_port_to_clipboard(self):
        self.clipboard_clear(); self.clipboard_append(str(self.port_serveur))
        orig = f"Port: {self.port_serveur} ❐"; self.btn_port.configure(text="✅ Copié !", fg_color="green")
        self.after(2000, lambda: self.btn_port.configure(text=orig, fg_color="#2B2B2B"))

    # --- CONFIGURATION (SANS BACKUP) ---
    def setup_config_tab(self):
        self.scroll_config = ctk.CTkScrollableFrame(self.tab_config)
        self.scroll_config.pack(fill="both", expand=True, padx=5, pady=5)
        self.scroll_config.grid_columnconfigure(0, weight=1); self.scroll_config.grid_columnconfigure(1, weight=1)
        self.props_path = os.path.join(self.server_path, "server.properties"); self.widgets_config = {}
        if not os.path.exists(self.props_path): ctk.CTkLabel(self.scroll_config, text="Fichier introuvable.").pack(); return
        data_props = {}
        with open(self.props_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"): k, v = line.strip().split("=", 1); data_props[k] = v
        
        def dessiner_colonne(liste_cats, col_idx):
            r = 0
            for cat in liste_cats:
                keys = [k for k, c in CATEGORIES_MAPPING.items() if c == cat and k in data_props]
                
                is_perf = (cat == "Performance")
                if keys or (is_perf and self.server_type == "java"):
                    frame = ctk.CTkFrame(self.scroll_config, **STYLE_CARD)
                    frame.grid(row=r, column=col_idx, sticky="nsew", padx=10, pady=10)
                    ctk.CTkLabel(frame, text=cat, font=("Arial", 15, "bold"), text_color="#3B8ED0").pack(pady=(10, 5), padx=10, anchor="w")
                    
                    if is_perf and self.server_type == "java":
                        self.create_ram_widget(frame)
                        ctk.CTkFrame(frame, height=2, fg_color="#404040").pack(fill="x", padx=10, pady=5)

                    for k in keys: self.create_config_row(frame, k, data_props[k])
                    r += 1
            return r
        
        last_l = dessiner_colonne(COLONNE_GAUCHE, 0)
        dessiner_colonne(COLONNE_DROITE, 1)
        
        # --- AUTRES ALIGNÉ ---
        displayed = [k for k in data_props if k in CATEGORIES_MAPPING]
        others = [k for k in data_props if k not in displayed]
        if others:
            f = ctk.CTkFrame(self.scroll_config, **STYLE_CARD)
            # On colle au dernier élément de gauche
            f.grid(row=last_l, column=0, sticky="nsew", padx=10, pady=10)
            ctk.CTkLabel(f, text="Autres", font=("Arial", 15, "bold"), text_color="gray").pack(pady=10, padx=10, anchor="w")
            for k in others: self.create_config_row(f, k, data_props[k])
        
        ctk.CTkButton(self.tab_config, text="💾 ENREGISTRER CONFIGURATION", command=self.save_properties, fg_color="orange", height=40).pack(pady=10, padx=20, fill="x")

    def create_ram_widget(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent"); row.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(row, text="Mémoire Vive (RAM)", font=("Arial", 12, "bold")).pack(anchor="w", padx=5)
        self.lbl_ram_val = ctk.CTkLabel(row, text=f"{self.ram_allocated} Go", text_color="#3B8ED0"); self.lbl_ram_val.pack(anchor="e", padx=5)
        self.slider_ram = ctk.CTkSlider(row, from_=1, to=16, number_of_steps=15, command=self.update_ram_visuals); self.slider_ram.set(self.ram_allocated); self.slider_ram.pack(fill="x", padx=5, pady=(0, 5))
        self.progress_ram = ctk.CTkProgressBar(row, height=10); self.progress_ram.pack(fill="x", padx=5, pady=(0, 10))
        self.update_ram_visuals(self.ram_allocated)

    def update_ram_visuals(self, value):
        val = int(value)
        self.ram_allocated = val
        self.lbl_ram_val.configure(text=f"{val} Go")
        percent = val / 16
        self.progress_ram.set(percent)
        if val <= 4: self.progress_ram.configure(progress_color="#2CC985")
        elif val <= 8: self.progress_ram.configure(progress_color="#FFA500")
        else: self.progress_ram.configure(progress_color="#FF474C")

    def create_config_row(self, parent, key, value):
        row = ctk.CTkFrame(parent, fg_color="transparent"); row.pack(fill="x", pady=2, padx=5)
        info = ctk.CTkLabel(row, text="ⓘ", text_color="#3B8ED0", cursor="hand2", font=("Arial", 12)); info.pack(side="left", padx=5)
        ToolTip(info, INFOS_PROPRIETES.get(key, f"Param: {key}"))
        ctk.CTkLabel(row, text=TRADUCTION_TITRES.get(key, key), anchor="w").pack(side="left")
        if key in DROPDOWN_OPTIONS:
            var = ctk.StringVar(value=value.lower())
            ctk.CTkOptionMenu(row, variable=var, values=DROPDOWN_OPTIONS[key], width=140, height=25).pack(side="right", padx=5)
            self.widgets_config[key] = {"type": "dropdown", "widget": var}
        elif value.lower() in ['true', 'false']:
            v = ctk.BooleanVar(value=(value.lower() == 'true'))
            ctk.CTkSwitch(row, text="", variable=v).pack(side="right", padx=5)
            self.widgets_config[key] = {"type": "bool", "widget": v}
        else:
            e = ctk.CTkEntry(row, width=140); e.insert(0, value); e.pack(side="right", padx=5)
            self.widgets_config[key] = {"type": "text", "widget": e}

    def save_properties(self):
        new_c = ""
        with open(self.props_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k = line.split("=", 1)[0]
                    if k in self.widgets_config:
                        d = self.widgets_config[k]
                        if d["type"] == "bool": v = "true" if d["widget"].get() else "false"
                        else: v = d["widget"].get()
                        new_c += f"{k}={v}\n"
                    else: new_c += line
                else: new_c += line
        with open(self.props_path, "w") as f: f.write(new_c)
        if self.server_type == "java":
            try:
                json_path = os.path.join(self.server_path, "info.json")
                with open(json_path, "r") as f: data = json.load(f)
                data["ram"] = self.ram_allocated
                with open(json_path, "w") as f: json.dump(data, f)
            except: pass
        self.log("Configuration (et RAM) Sauvegardée !")

    def setup_players_tab(self):
        if self.server_type == "bedrock":
            ctk.CTkLabel(self.tab_players, text="La gestion visuelle des joueurs\nn'est pas disponible sur Bedrock.\n\nUtilisez la console pour les commandes\n(kick, ban, op...).", font=("Arial", 16), text_color="gray").pack(expand=True)
            return
        self.toolbar_players = ctk.CTkFrame(self.tab_players, fg_color="transparent"); self.toolbar_players.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(self.toolbar_players, text="Gestion Joueurs", font=("Arial", 16, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(self.toolbar_players, text="🔄 Actualiser", width=120, command=self.refresh_all_players_tab).pack(side="right", padx=10)
        self.tab_players.grid_columnconfigure(0, weight=1); self.tab_players.grid_columnconfigure(1, weight=1); self.tab_players.grid_rowconfigure(1, weight=1)
        self.toolbar_players.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.frame_list_players = ctk.CTkFrame(self.tab_players); self.frame_list_players.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        ctk.CTkLabel(self.frame_list_players, text="En Ligne", font=("Arial", 14, "bold")).pack(pady=5)
        self.scroll_players = ctk.CTkScrollableFrame(self.frame_list_players); self.scroll_players.pack(fill="both", expand=True, padx=5, pady=5)
        self.frame_mod = ctk.CTkFrame(self.tab_players); self.frame_mod.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.mod_tabs = ctk.CTkTabview(self.frame_mod); self.mod_tabs.pack(fill="both", expand=True, padx=5, pady=5)
        self.tab_whitelist = self.mod_tabs.add("Whitelist"); self.tab_bans = self.mod_tabs.add("Bannis"); self.tab_ops = self.mod_tabs.add("OP")
        self.setup_list_manager(self.tab_whitelist, "whitelist.json", "whitelist add", "whitelist remove")
        self.setup_list_manager(self.tab_bans, "banned-players.json", "ban", "pardon")
        self.setup_list_manager(self.tab_ops, "ops.json", "op", "deop")

    def refresh_all_players_tab(self):
        if self.server_type == "bedrock": return
        self.refresh_online_players()
        for tab in [self.tab_whitelist, self.tab_bans, self.tab_ops]:
            if hasattr(tab, 'refresh_func'): tab.refresh_func()

    def setup_list_manager(self, parent, json_file, cmd_add, cmd_rem):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", pady=5)
        e = ctk.CTkEntry(f, placeholder_text="Pseudo..."); e.pack(side="left", fill="x", expand=True, padx=5)
        sf = ctk.CTkScrollableFrame(parent); sf.pack(fill="both", expand=True, padx=5, pady=5)
        def add():
            if e.get(): self.send_command_text(f"{cmd_add} {e.get()}"); e.delete(0, "end"); self.after(1000, lambda: self.refresh_json_list(sf, json_file, cmd_rem))
        ctk.CTkButton(f, text="+", width=40, fg_color="green", command=add).pack(side="right", padx=5)
        parent.refresh_func = lambda: self.refresh_json_list(sf, json_file, cmd_rem)
        self.refresh_json_list(sf, json_file, cmd_rem)

    def refresh_json_list(self, sf, json_file, cmd_rem):
        for w in sf.winfo_children(): w.destroy()
        path = os.path.join(self.server_path, json_file)
        if not os.path.exists(path): ctk.CTkLabel(sf, text="(Vide)").pack(); return
        try:
            with open(path, "r") as f: d = json.load(f)
            for i in d:
                n = i.get("name", "Inconnu"); r = ctk.CTkFrame(sf, **STYLE_CARD); r.pack(fill="x", pady=4, padx=2)
                ctk.CTkLabel(r, text=n, font=("Arial", 12, "bold")).pack(side="left", padx=10)
                def rem(t=n): self.send_command_text(f"{cmd_rem} {t}"); self.after(1000, lambda: self.refresh_json_list(sf, json_file, cmd_rem))
                ctk.CTkButton(r, text="✖", width=30, height=25, fg_color="darkred", command=lambda: rem()).pack(side="right", padx=10)
        except: ctk.CTkLabel(sf, text="Erreur Lecture").pack()

    def refresh_online_players(self):
        if self.server_type == "bedrock": return
        for w in self.scroll_players.winfo_children(): w.destroy()
        if not self.running: ctk.CTkLabel(self.scroll_players, text="Serveur éteint.").pack(pady=20); return
        threading.Thread(target=self._fetch_players_thread).start()

    def _fetch_players_thread(self):
        try:
            server = JavaServer.lookup(f"localhost:{self.port_serveur}")
            status = server.status()
            if status.players.sample: self.after(0, lambda: [self.add_player_card_java(p.name) for p in status.players.sample])
            else: self.after(0, lambda: ctk.CTkLabel(self.scroll_players, text="Aucun joueur.").pack(pady=20))
        except: pass

    def add_player_card_java(self, username):
        c = ctk.CTkFrame(self.scroll_players, **STYLE_CARD); c.pack(fill="x", pady=4, padx=2)
        try:
            u = f"https://minotar.net/avatar/{username}/32"
            i = ctk.CTkImage(light_image=Image.open(BytesIO(requests.get(u).content)), size=(32, 32))
            ctk.CTkLabel(c, text="", image=i).pack(side="left", padx=10)
        except: pass
        ctk.CTkLabel(c, text=username, font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkButton(c, text="KICK", width=50, height=25, fg_color="red", command=lambda: self.send_command_text(f"kick {username}")).pack(side="right", padx=5)

    def start_server(self):
        self.running = True; self.update_button_ui("LOADING"); threading.Thread(target=self._run_process).start()

    def _run_process(self):
        if self.server_type == "bedrock":
            exe_path = os.path.join(self.server_path, "bedrock_server.exe")
            if not os.path.exists(exe_path): self.log(f"ERREUR: Fichier introuvable !\n{exe_path}"); self.running=False; self.update_button_ui("OFF"); return
            cmd = [exe_path]
            try:
                props_path = os.path.join(self.server_path, "server.properties")
                with open(props_path, "r") as f: content = f.read()
                if "enable-query=true" not in content:
                    with open(props_path, "a") as f: f.write("\nenable-query=true\n")
            except: pass
        else:
            cmd = ["java", f"-Xmx{self.ram_allocated}G", f"-Xms{self.ram_allocated}G", "-jar", "server.jar", "nogui"]
        try:
            self.server_process = subprocess.Popen(cmd, cwd=self.server_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace')
            self.update_button_ui("ON"); self.after(5000, self.refresh_all_players_tab)
            while True:
                line = self.server_process.stdout.readline()
                if not line and self.server_process.poll() is not None: break
                if line: self.log(line.strip())
        except Exception as e: self.log(f"ERREUR: {e}")
        finally: self.running = False; self.server_process = None; self.update_button_ui("OFF")

    def log(self, m): self.console_output.configure(state="normal"); self.console_output.insert("end", m+"\n"); self.console_output.see("end"); self.console_output.configure(state="disabled")
    def toggle_server_state(self): self.start_server() if not self.running else self.stop_server()
    def update_button_ui(self, s): 
        t, c = ("⏹ ARRÊTER", "red") if s=="ON" else ("▶ DÉMARRER", "green") if s=="OFF" else ("⏳ ...", "gray")
        self.btn_power.configure(text=t, fg_color=c)
    def stop_server(self): self.send_command_text("stop")
    def send_command(self, e=None): self.send_command_text(self.console_input.get()); self.console_input.delete(0, "end")
    def send_command_text(self, c): 
        if self.running and self.server_process: self.server_process.stdin.write(c+"\n"); self.server_process.stdin.flush(); self.log(f"> {c}")
    def setup_console_tab(self):
        self.tab_console.grid_columnconfigure(0, weight=1); self.tab_console.grid_rowconfigure(0, weight=1)
        self.console_output = ctk.CTkTextbox(self.tab_console, state="disabled", font=("Consolas", 12), fg_color="#1e1e1e", text_color="#00ff00"); self.console_output.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        f = ctk.CTkFrame(self.tab_console); f.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.console_input = ctk.CTkEntry(f); self.console_input.pack(side="left", fill="x", expand=True, padx=5); self.console_input.bind("<Return>", self.send_command)
        ctk.CTkButton(f, text="Envoyer", width=80, command=self.send_command).pack(side="right")

# --- APP PRINCIPALE ---
class MinecraftManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Manager Serveur Minecraft - PROJET BAC")
        self.geometry("800x600")
        self.dossier_racine = DEFAULT_SERVERS_DIR
        self.top_frame = ctk.CTkFrame(self); self.top_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(self.top_frame, text="Dossier :").pack(side="left", padx=10)
        self.lbl_directory = ctk.CTkLabel(self.top_frame, text=self.dossier_racine, text_color="gray"); self.lbl_directory.pack(side="left", padx=5)
        ctk.CTkButton(self.top_frame, text="📁 Changer", width=100, command=self.choisir_dossier).pack(side="right", padx=10)
        self.main_tabs = ctk.CTkTabview(self); self.main_tabs.pack(fill="both", expand=True, padx=20, pady=20)
        self.tab_create = self.main_tabs.add("Créer un Serveur"); self.tab_list = self.main_tabs.add("Mes Serveurs")
        
        self.img_java = None; self.img_bedrock = None
        try:
            pj = os.path.join(ASSETS_DIR, "java.png"); pb = os.path.join(ASSETS_DIR, "bedrock.png")
            if os.path.exists(pj): self.img_java = ctk.CTkImage(light_image=Image.open(pj), dark_image=Image.open(pj), size=(24, 24))
            if os.path.exists(pb): self.img_bedrock = ctk.CTkImage(light_image=Image.open(pb), dark_image=Image.open(pb), size=(24, 24))
        except: pass

        self.setup_create_tab(); self.setup_list_tab()

    def choisir_dossier(self):
        d = filedialog.askdirectory()
        if d: self.dossier_racine = d; self.lbl_directory.configure(text=d); self.refresh_server_list()

    def setup_list_tab(self):
        ctk.CTkButton(self.tab_list, text="Actualiser", command=self.refresh_server_list).pack(pady=10)
        self.servers_frame = ctk.CTkScrollableFrame(self.tab_list, width=700, height=400); self.servers_frame.pack(pady=10)
        self.refresh_server_list()

    def refresh_server_list(self):
        for w in self.servers_frame.winfo_children(): w.destroy()
        if not os.path.exists(self.dossier_racine): return
        found = False; dossiers = [d for d in os.listdir(self.dossier_racine) if os.path.isdir(os.path.join(self.dossier_racine, d))]
        for folder in dossiers:
            full_path = os.path.join(self.dossier_racine, folder)
            is_java = os.path.exists(os.path.join(full_path, "server.jar"))
            is_bedrock = os.path.exists(os.path.join(full_path, "bedrock_server.exe"))
            if is_java or is_bedrock: found = True; self.creer_carte_serveur(folder)

    def creer_carte_serveur(self, folder):
        try: 
            with open(os.path.join(self.dossier_racine, folder, "info.json")) as f: 
                d = json.load(f); n, v, t = d.get("nom", folder), d.get("version", "?"), d.get("type", "java")
        except: 
            n, v = folder, "?"
            t = "bedrock" if os.path.exists(os.path.join(self.dossier_racine, folder, "bedrock_server.exe")) else "java"
        r = ctk.CTkFrame(self.servers_frame, **STYLE_CARD); r.pack(fill="x", pady=5, padx=5)
        
        icon_img = self.img_java if t == "java" else self.img_bedrock
        if icon_img: ctk.CTkLabel(r, text="", image=icon_img).pack(side="left", padx=10)
        else:
            col = "orange" if t=="java" else "cyan"
            ctk.CTkLabel(r, text=f"[{t.upper()}]", text_color=col, font=("Arial", 12, "bold")).pack(side="left", padx=10)
            
        ctk.CTkLabel(r, text=f"{n} ({v})", font=("Arial", 14, "bold")).pack(side="left", padx=5)
        ctk.CTkButton(r, text="GÉRER", command=lambda: ServerControlPanel(self, os.path.join(self.dossier_racine, folder), n, v, t, icon_img)).pack(side="right", padx=10, pady=10)

    def setup_create_tab(self):
        self.tab_create.grid_columnconfigure(0, weight=1); self.tab_create.grid_columnconfigure(1, weight=1)
        form_frame = ctk.CTkFrame(self.tab_create, fg_color="transparent"); form_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        ctk.CTkLabel(form_frame, text="Type de Serveur :", anchor="w").pack(fill="x")
        self.type_var = ctk.StringVar(value="Java Edition")
        self.seg_button = ctk.CTkSegmentedButton(form_frame, values=["Java Edition", "Bedrock Edition"], variable=self.type_var, command=self.update_version_list)
        self.seg_button.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(form_frame, text="Nom du Serveur :", anchor="w").pack(fill="x")
        self.var_name = ctk.StringVar(); self.var_name.trace_add("write", self.check_create_button)
        self.entry_name = ctk.CTkEntry(form_frame, textvariable=self.var_name); self.entry_name.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(form_frame, text="Version :", anchor="w").pack(fill="x")
        self.version_var = ctk.StringVar(value="1.20.4")
        self.menu_version = ctk.CTkOptionMenu(form_frame, values=list(URLS_JAVA.keys()), variable=self.version_var); self.menu_version.pack(fill="x", pady=(0, 15))
        
        world_frame = ctk.CTkFrame(form_frame, border_width=1, border_color="gray"); world_frame.pack(fill="x", pady=10, padx=0)
        self.world_mode = ctk.StringVar(value="Générer un Monde")
        self.seg_world = ctk.CTkSegmentedButton(world_frame, values=["Générer un Monde", "Importer ma Map"], variable=self.world_mode, command=self.toggle_world_ui); self.seg_world.pack(fill="x", padx=5, pady=5)
        
        self.frame_gen = ctk.CTkFrame(world_frame, fg_color="transparent"); self.frame_gen.pack(fill="x", padx=5, pady=5)
        self.lbl_gen_type = ctk.CTkLabel(self.frame_gen, text="Type :")
        self.lbl_gen_type.pack(side="left")
        self.type_world_var = ctk.StringVar(value="Normal")
        self.menu_type = ctk.CTkOptionMenu(self.frame_gen, values=["Normal", "Plat", "Amplifié", "Biome Unique", "Biomes Larges"], variable=self.type_world_var, width=120)
        self.menu_type.pack(side="left", padx=5)
        self.entry_seed = ctk.CTkEntry(self.frame_gen, placeholder_text="Graine (Seed)...", width=120); self.entry_seed.pack(side="left", padx=5, fill="x", expand=True)
        
        self.frame_import = ctk.CTkFrame(world_frame, fg_color="transparent")
        self.lbl_import_file = ctk.CTkLabel(self.frame_import, text="Aucun fichier", text_color="gray", width=150); self.lbl_import_file.pack(side="left", padx=5)
        ctk.CTkButton(self.frame_import, text="Choisir...", width=80, command=self.choose_map_file).pack(side="right", padx=5)
        self.map_file_path = None

        self.btn_install = ctk.CTkButton(form_frame, text="CRÉER LE SERVEUR", fg_color="green", height=50, font=("Arial", 16, "bold"), state="disabled", command=self.lancer_installation); self.btn_install.pack(fill="x", pady=20)
        self.logs_create = ctk.CTkTextbox(self.tab_create, height=400); self.logs_create.grid(row=0, column=1, sticky="nsew", padx=20, pady=20); self.logs_create.insert("end", "Prêt.\n")

    def check_create_button(self, *args):
        if self.var_name.get().strip(): self.btn_install.configure(state="normal")
        else: self.btn_install.configure(state="disabled")

    def toggle_world_ui(self, value):
        if value == "Générer un Monde": self.frame_import.pack_forget(); self.frame_gen.pack(fill="x", padx=5, pady=5)
        else: self.frame_gen.pack_forget(); self.frame_import.pack(fill="x", padx=5, pady=5)

    def choose_map_file(self):
        t = self.type_var.get()
        filetypes = [("Zip", "*.zip")] if t == "Java Edition" else [("MCWorld", "*.mcworld"), ("Zip", "*.zip")]
        f = filedialog.askopenfilename(filetypes=filetypes)
        if f: self.map_file_path = f; self.lbl_import_file.configure(text=os.path.basename(f), text_color="white")

    def update_version_list(self, value):
        if value == "Java Edition":
            self.menu_version.configure(values=list(URLS_JAVA.keys())); self.version_var.set(list(URLS_JAVA.keys())[0])
            self.lbl_gen_type.pack(side="left")
            self.menu_type.pack(side="left", padx=5)
        else:
            self.menu_version.configure(values=list(URLS_BEDROCK.keys())); self.version_var.set(list(URLS_BEDROCK.keys())[0])
            self.lbl_gen_type.pack_forget()
            self.menu_type.pack_forget()
        self.map_file_path = None; self.lbl_import_file.configure(text="Aucun fichier", text_color="gray")

    def lancer_installation(self):
        n = self.entry_name.get()
        if not n: return
        self.btn_install.configure(state="disabled")
        t = "java" if self.type_var.get() == "Java Edition" else "bedrock"
        urls = URLS_JAVA if t == "java" else URLS_BEDROCK
        url = urls.get(self.version_var.get())
        world_data = {"mode": self.world_mode.get(), "type": self.type_world_var.get(), "seed": self.entry_seed.get(), "import_path": self.map_file_path}
        threading.Thread(target=self.download_thread, args=(url, self.version_var.get(), n, t, world_data)).start()

    def download_thread(self, url, v, n, t, w_data):
        try:
            clean_name = nettoyer_nom_dossier(n); full_path = os.path.join(self.dossier_racine, clean_name)
            if os.path.exists(full_path): self.logs_create.insert("end", "Erreur: Ce nom existe déjà.\n"); return
            os.makedirs(full_path); self.logs_create.insert("end", f"Création ({t}) dans {full_path}...\n")
            with open(os.path.join(full_path, "info.json"), "w") as j: json.dump({"nom": n, "version": v, "type": t}, j)
            
            self.logs_create.insert("end", "Téléchargement du serveur...\n")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            r = requests.get(url, headers=headers, stream=True)
            if t == "java":
                with open(os.path.join(full_path, "server.jar"), 'wb') as j: j.write(r.content)
                with open(os.path.join(full_path, "eula.txt"), "w") as j: j.write("eula=true")
            else:
                zip_path = os.path.join(full_path, "bedrock.zip")
                with open(zip_path, 'wb') as j: j.write(r.content)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(full_path)
                os.remove(zip_path)

            props_to_add = ""
            if w_data["mode"] == "Importer ma Map" and w_data["import_path"]:
                self.logs_create.insert("end", f"Importation de la map : {os.path.basename(w_data['import_path'])}...\n")
                if t == "java":
                    world_dest = os.path.join(full_path, "world")
                    with zipfile.ZipFile(w_data["import_path"], 'r') as z:
                        z.extractall(world_dest)
                        items = os.listdir(world_dest)
                        if len(items) == 1 and os.path.isdir(os.path.join(world_dest, items[0])):
                            subdir = os.path.join(world_dest, items[0])
                            for item in os.listdir(subdir): shutil.move(os.path.join(subdir, item), world_dest)
                            os.rmdir(subdir)
                else:
                    world_dest = os.path.join(full_path, "worlds", "imported_map")
                    with zipfile.ZipFile(w_data["import_path"], 'r') as z: z.extractall(world_dest)
                    props_to_add += "level-name=imported_map\n"
            
            elif w_data["mode"] == "Générer un Monde":
                if t == "java":
                    lvl_type_map = {"Normal": "default", "Plat": "flat", "Amplifié": "amplified", "Biome Unique": "single_biome_surface", "Biomes Larges": "largebiomes"}
                    props_to_add += f"level-type={lvl_type_map.get(w_data['type'], 'default')}\n"
                    if w_data["seed"]: props_to_add += f"level-seed={w_data['seed']}\n"
                else:
                    if w_data["seed"]: props_to_add += f"level-seed={w_data['seed']}\n"

            if t == "bedrock": props_to_add += "enable-query=true\n"
            
            final_props = DEFAULT_PROPERTIES_JAVA + f"\nmotd={n} - Projet BAC\n" + props_to_add
            with open(os.path.join(full_path, "server.properties"), "w") as j: j.write(final_props)
            
            self.logs_create.insert("end", "Terminé avec succès !\n")
            self.after(0, self.refresh_server_list)
            
        except Exception as e: self.logs_create.insert("end", f"Erreur: {str(e)}\n")
        finally: self.btn_install.configure(state="normal")

if __name__ == "__main__":
    app = MinecraftManagerApp()
    app.mainloop()