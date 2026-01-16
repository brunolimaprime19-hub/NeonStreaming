import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import sys
import os
import signal
import json

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self, bg="#0d0f14", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas, style="Card.TFrame")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mousewheel
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas = canvas

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

class ServerGUI:
    CONFIG_FILE = "server_config.json"
    
    def __init__(self, root):
        self.root = root
        self.root.title("Neon Stream - Server Manager Ultimate")
        self.root.geometry("900x700")
        self.root.configure(bg="#0f172a") # Slate-900
        
        self.server_process = None
        self.is_running = False
        
        self.vars = {} # Dictionary to store all Tk vars
        
        self.setup_styles()
        self.create_widgets()
        self.default_config() # Set defaults first
        self.load_config()    # Overwrite with saved
        
        # Initial updates
        self.update_bitrate_label(self.vars["bitrate"].get())

        # Auto-save support
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.save_config()
        if self.is_running:
            self.stop_server()
        self.root.destroy()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Colors
        BG_DARK = "#0f172a"
        BG_CARD = "#1e293b"
        TEXT_MAIN = "#f8fafc"
        TEXT_MUTED = "#94a3b8"
        ACCENT = "#6366f1" # Indigo-500
        SUCCESS = "#10b981"
        DANGER = "#ef4444"
        
        # Base
        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=BG_DARK)
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_MAIN, font=("Inter", 10))
        style.configure("Header.TLabel", background=BG_DARK, foreground=ACCENT, font=("Inter", 18, "bold"))
        style.configure("Section.TLabel", background=BG_DARK, foreground="#cbd5e1", font=("Inter", 12, "bold"))
        style.configure("Status.TLabel", background=BG_DARK, foreground=TEXT_MUTED, font=("Monospace", 10))

        # Notebook
        style.configure("TNotebook", background=BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_CARD, foreground=TEXT_MUTED, padding=[15, 8], font=("Inter", 10))
        style.map("TNotebook.Tab", 
                  background=[("selected", ACCENT)], 
                  foreground=[("selected", "white")])

        # Buttons
        style.configure("TButton", padding=8, font=("Inter", 10, "bold"), borderwidth=0)
        style.map("TButton",
                  background=[('active', '#4f46e5'), ('!disabled', ACCENT)],
                  foreground=[('active', 'white'), ('!disabled', 'white')])
        
        style.configure("Start.TButton", background=SUCCESS)
        style.map("Start.TButton", background=[('active', '#059669'), ('!disabled', SUCCESS)])
        
        style.configure("Stop.TButton", background=DANGER)
        style.map("Stop.TButton", background=[('active', '#dc2626'), ('!disabled', DANGER)])
        
        # Labelframes
        style.configure("TLabelframe", background=BG_DARK, relief="solid", bordercolor="#334155", borderwidth=1)
        style.configure("TLabelframe.Label", background=BG_DARK, foreground=ACCENT, font=("Inter", 10, "bold"))
        
        # Combobox
        style.configure("TCombobox", 
                        fieldbackground=BG_CARD, 
                        background=BG_DARK, 
                        foreground=TEXT_MAIN, 
                        arrowcolor=ACCENT,
                        padding=5)
        style.map("TCombobox",
                  fieldbackground=[('readonly', BG_CARD)],
                  foreground=[('readonly', TEXT_MAIN)])
        
        # Global Option for Combobox listbox
        self.root.option_add('*TCombobox*Listbox.background', BG_CARD)
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT_MAIN)
        self.root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
        self.root.option_add('*TCombobox*Listbox.selectForeground', "white")
        self.root.option_add('*TCombobox*Listbox.font', ("Inter", 10))
        self.root.option_add('*TCombobox*Listbox.borderWidth', 0)

        # Checkbutton
        style.configure("TCheckbutton", 
                        background=BG_DARK, 
                        foreground=TEXT_MAIN, 
                        font=("Inter", 10))
        style.map("TCheckbutton",
                  background=[('active', BG_DARK)],
                  foreground=[('active', TEXT_MAIN)])
        
        # Scale (TK standard, not TTK, so we style it in add_scale usually, 
        # but let's ensure the label is okay or add a style if needed)

    def create_widgets(self):
        # Header Area
        header_frame = ttk.Frame(self.root, padding="20 20 20 10")
        header_frame.pack(fill=tk.X)
        
        title = ttk.Label(header_frame, text="NEON STREAM SERVER", style="Header.TLabel")
        title.pack(side=tk.LEFT)
        
        self.status_var = tk.StringVar(value="OFFLINE")
        status_lbl = ttk.Label(header_frame, textvariable=self.status_var, style="Status.TLabel", foreground="#ef4444")
        status_lbl.pack(side=tk.RIGHT)

        # Main Content - Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create Tabs
        self.tab_video = self.create_tab("Vídeo & Áudio")
        self.tab_latency = self.create_tab("Latência & Perf.")
        self.tab_input = self.create_tab("Input & Captura")
        self.tab_session = self.create_tab("Sessão & Seg.")
        self.tab_advanced = self.create_tab("Avançado & Logs")
        
        # --- TAB 1: VIDEO (STREAMING) & AUDIO ---
        self.build_video_section(self.tab_video)
        self.build_audio_section(self.tab_video)

        # --- TAB 2: LATENCY & PERFORMANCE ---
        self.build_latency_section(self.tab_latency)
        self.build_adaptive_section(self.tab_latency)
        self.build_gpu_section(self.tab_latency)

        # --- TAB 3: INPUT & CAPTURE ---
        self.build_capture_section(self.tab_input)
        self.build_input_section(self.tab_input)

        # --- TAB 4: SESSION, USERS & SECURITY ---
        self.build_session_section(self.tab_session)
        self.build_security_section(self.tab_session)

        # --- TAB 5: ADVANCED & LOGS ---
        self.build_advanced_section(self.tab_advanced)
        self.build_windows_setup_section(self.tab_advanced) # New section
        self.build_log_section(self.tab_advanced)

        # Footer Actions
        footer = ttk.Frame(self.root, padding="20")
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_toggle = ttk.Button(footer, text="INICIAR SERVIDOR", style="Start.TButton", command=self.toggle_server)
        self.btn_toggle.pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(footer, text="Salvar Config", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(footer, text="Restaurar Padrões", command=self.default_config).pack(side=tk.LEFT, padx=5)

    def create_tab(self, title):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)
        # Add scroll capability
        scroll = ScrollableFrame(frame)
        scroll.pack(fill=tk.BOTH, expand=True)
        return scroll.scrollable_frame

    def add_section(self, parent, title):
        lf = ttk.LabelFrame(parent, text=title, padding="15")
        lf.pack(fill=tk.X, padx=10, pady=10, expand=False)
        return lf

    def add_combo(self, parent, label, var_name, values, default, row, col, width=15):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=5, pady=5)
        if var_name not in self.vars: self.vars[var_name] = tk.StringVar(value=default)
        cb = ttk.Combobox(parent, textvariable=self.vars[var_name], values=values, state="readonly", width=width)
        cb.grid(row=row, column=col+1, sticky="w", padx=5, pady=5)
        return cb

    def add_entry(self, parent, label, var_name, default, row, col, width=15):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=5, pady=5)
        if var_name not in self.vars: self.vars[var_name] = tk.StringVar(value=default)
        e = ttk.Entry(parent, textvariable=self.vars[var_name], width=width)
        e.grid(row=row, column=col+1, sticky="w", padx=5, pady=5)
        return e
    
    def add_check(self, parent, label, var_name, default, row, col):
        if var_name not in self.vars: self.vars[var_name] = tk.BooleanVar(value=default)
        cb = ttk.Checkbutton(parent, text=label, variable=self.vars[var_name])
        cb.grid(row=row, column=col, columnspan=2, sticky="w", padx=5, pady=5)
        return cb

    def add_scale(self, parent, label, var_name, from_, to, default, row, col, command=None):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=5, pady=5)
        if var_name not in self.vars: self.vars[var_name] = tk.IntVar(value=default)
        scale = tk.Scale(parent, from_=from_, to=to, orient=tk.HORIZONTAL, 
                         variable=self.vars[var_name], bg="#1e293b", fg="white", 
                         highlightthickness=0, length=200, showvalue=1, command=command)
        scale.grid(row=row, column=col+1, sticky="w", padx=5, pady=5)
        return scale

    # --- SECTION BUILDERS ---

    def build_video_section(self, parent):
        sec = self.add_section(parent, "VÍDEO (Streaming)")
        
        # Row 0
        self.add_combo(sec, "Resolução", "resolution", [
            "1280x720 (60 FPS)",
            "1280x720 (720p)", 
            "1920x1080 (1080p)", 
            "2560x1440 (2K)", 
            "3840x2160 (4K)",
            "848x480 (480p)"
        ], "1280x720 (60 FPS)", 0, 0)
        self.add_combo(sec, "FPS", "fps", ["30", "60", "120", "144"], "60", 0, 2)
        
        # Row 1
        self.add_combo(sec, "Codec", "codec", ["H.264 (padrão)", "VP9", "AV1 (experimental)"], "H.264 (padrão)", 1, 0)
        self.add_combo(sec, "Perfil H.264", "h264_profile", ["baseline", "main", "high"], "baseline", 1, 2)
        
        # Row 2
        self.add_combo(sec, "Preset de Latência", "latency_preset", ["Ultra Baixa", "Baixa", "Balanceada"], "Ultra Baixa", 2, 0)
        self.add_combo(sec, "GOP (Keyframe)", "gop", ["15", "30", "60"], "60", 2, 2)
        
        # Row 3 (Bitrate)
        # Bitrate Logic
        def update_lbl(val):
            kbps = int(float(val))
            self.bitrate_label_var.set(f"{kbps} Kbps ({kbps/1000:.1f} Mbps)")
            
        self.bitrate_label_var = tk.StringVar(value="3000 Kbps")
        ttk.Label(sec, text="Bitrate Fixo:").grid(row=3, column=0, pady=10, padx=5, sticky="w")
        
        # We need a custom container for bitrate to show label next to it nicely
        b_frame = tk.Frame(sec, bg="#1e293b")
        b_frame.grid(row=3, column=1, columnspan=3, sticky="w")
        
        self.vars["bitrate"] = tk.IntVar(value=10000)
        s = tk.Scale(b_frame, from_=2000, to=60000, orient=tk.HORIZONTAL, variable=self.vars["bitrate"], 
                 bg="#1e293b", fg="white", highlightthickness=0, length=250, showvalue=0, command=update_lbl)
        s.bind("<ButtonRelease-1>", self.update_live_bitrate)
        s.pack(side=tk.LEFT)
        ttk.Label(b_frame, textvariable=self.bitrate_label_var, foreground="#6366f1").pack(side=tk.LEFT, padx=10)
        
        self.add_check(sec, "Bitrate Automático", "bitrate_auto", False, 4, 0)
        self.add_combo(sec, "B-Frames", "bframes", ["0", "1", "2"], "0", 4, 2)

    def build_audio_section(self, parent):
        sec = self.add_section(parent, "ÁUDIO")
        self.add_combo(sec, "Codec", "audio_codec", ["Opus"], "Opus", 0, 0)
        self.add_combo(sec, "Bitrate", "audio_bitrate", ["64", "96", "128", "192"], "128", 0, 2)
        self.add_combo(sec, "Latência", "audio_latency", ["Baixa", "Normal"], "Baixa", 1, 0)
        self.add_check(sec, "Microfone", "mic_enabled", False, 1, 2)
        self.add_check(sec, "Cancelamento de Eco", "echo_cancel", True, 2, 0)
        self.add_check(sec, "Aceleração GPU (Áudio)", "audio_gpu", False, 2, 2)
        
        btn_frame = ttk.Frame(sec, style="Card.TFrame")
        btn_frame.grid(row=3, column=0, columnspan=4, pady=15, sticky="w")
        
        ttk.Button(btn_frame, text="Mudar Áudio para HDMI", command=self.set_audio_to_hdmi).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Áudio Analógico (Fone/Caixa)", command=self.set_audio_to_analog).pack(side=tk.LEFT, padx=5)

    def build_latency_section(self, parent):
        sec = self.add_section(parent, "LATÊNCIA & BUFFER")
        self.add_check(sec, "Modo Ultra Baixa Latência", "ultra_low_latency", True, 0, 0)
        self.add_check(sec, "Frame Drop (se atraso)", "frame_drop", True, 0, 2)
        
        self.add_combo(sec, "Buffer Vídeo (frames)", "buffer_video", ["0", "1", "2"], "0", 1, 0)
        self.add_entry(sec, "Buffer Áudio (ms)", "buffer_audio", "0", 1, 2)
        
        self.add_combo(sec, "Controle Jitter", "jitter", ["Baixo", "Médio", "Alto"], "Baixo", 2, 0)

    def build_adaptive_section(self, parent):
        sec = self.add_section(parent, "ADAPTATIVO (INTELIGENTE)")
        self.add_check(sec, "Escala Dinâmica (Ping)", "dynamic_scale", False, 0, 0)
        self.add_check(sec, "FPS Adaptativo (60->30)", "adaptive_fps", False, 0, 2)
        self.add_check(sec, "Bitrate Adaptativo (RTT)", "adaptive_bitrate", False, 1, 0)
        self.add_check(sec, "Modo Conexão Ruim (Auto)", "bad_connection_mode", True, 1, 2)

    def build_gpu_section(self, parent):
        sec = self.add_section(parent, "GOP & PERFORMANCE")
        
        if os.name == "nt":
            encoders = ["Automático", "NVENC (Nvidia)", "AMF (AMD)", "QSV (Intel)", "Software (CPU)"]
        else:
            encoders = ["Automático", "NVENC (Nvidia)", "VAAPI (AMD/Intel)", "Software (CPU)"]
            
        self.add_combo(sec, "Encoder", "encoder", encoders, "Software (CPU)", 0, 0)
        self.add_combo(sec, "Prioridade Processo", "process_priority", ["Normal", "Alta", "Tempo Real"], "Normal", 0, 2)
        
        self.add_entry(sec, "FPS Max por Sessão", "max_fps_session", "60", 1, 0)
        self.add_entry(sec, "Afinidade CPU (Cores)", "cpu_affinity", "All", 1, 2)
        
        self.add_scale(sec, "GPU Limit (%)", "gpu_limit", 10, 100, 100, 2, 0)
        self.add_scale(sec, "CPU Limit (%)", "cpu_limit", 10, 100, 100, 2, 2)

    def build_capture_section(self, parent):
        sec = self.add_section(parent, "CAPTURA")
        
        if os.name == "nt":
            backends = ["DDA (Alta Perf.)", "GDI (Compatível)"]
            default_backend = "DDA (Alta Perf.)"
        else:
            backends = ["X11 (Padrão)", "PipeWire"]
            default_backend = "X11 (Padrão)"
            
        self.add_combo(sec, "Backend", "backend", backends, default_backend, 0, 0)
        self.add_check(sec, "Captura de Cursor", "capture_cursor", True, 0, 2)
        
        self.add_combo(sec, "Multi-Monitor", "monitor_mode", ["Monitor 1", "Monitor 2", "Espelhar Todos"], "Monitor 1", 1, 0)
        self.add_entry(sec, "Região (x,y,w,h)", "capture_region", "0,0,1280,720", 1, 2)

    def build_input_section(self, parent):
        sec = self.add_section(parent, "INPUT (Controles)")
        self.add_combo(sec, "Teclado", "kbd_layout", ["ABNT2", "US Int"], "ABNT2", 0, 0)
        self.add_combo(sec, "Gamepad Emulation", "gamepad_emu", ["XInput (Xbox)", "DualShock 4"], "XInput (Xbox)", 0, 2)
        
        self.add_scale(sec, "Sensibilidade Mouse", "mouse_sens", 1, 20, 10, 1, 0)
        self.add_check(sec, "Vibração", "vibration", True, 1, 2)
        
        self.add_check(sec, "Overlay Customizável", "overlay_enabled", True, 2, 0)
        self.add_check(sec, "Anti-ghosting", "anti_ghosting", True, 2, 2)

    def build_session_section(self, parent):
        sec = self.add_section(parent, "SESSÕES")
        self.add_entry(sec, "Porta Servidor", "port", "8080", 0, 0)
        self.add_entry(sec, "Max Sessões", "max_sessions", "1", 0, 2)
        
        self.add_check(sec, "Fila de Espera", "queue_enabled", False, 1, 0)
        self.add_check(sec, "Auto-Disconnect (Inativo)", "auto_disconnect", True, 1, 2)

    def build_security_section(self, parent):
        sec = self.add_section(parent, "SEGURANÇA")
        self.add_combo(sec, "Isolamento", "isolation", ["Usuário Linux", "Container (Docker)", "Nada"], "Usuário Linux", 0, 0)
        self.add_entry(sec, "Limite Rede (Mbps)", "net_limit", "50", 0, 2)
        
        self.add_entry(sec, "Limite RAM (MB)", "mem_limit", "2000", 1, 0)
        self.add_check(sec, "Firewall por sessão", "session_firewall", False, 1, 2)
        self.add_check(sec, "Proteção Anti-Flood", "flood_protect", True, 1, 2)

    def build_advanced_section(self, parent):
        sec = self.add_section(parent, "DEBUG & EXPERIMENTAL")
        self.add_check(sec, "Modo Debug", "debug_mode", False, 0, 0)
        self.add_check(sec, "Dump de Frames", "frame_dump", False, 0, 2)
        self.add_check(sec, "Simular Lag", "sim_lag", False, 1, 0)
        self.add_check(sec, "Gravação Automática", "auto_record", False, 1, 2)

        note_text = ("Nota: Algumas opções \"Adaptativas\" (como Escala Dinâmica) e de \"Segurança\" "
                     "(como Container Docker) foram adicionadas à interface para configuração, mas a "
                     "implementação lógica profunda (feedback loop de rede ou criação de containers) "
                     "depende de desenvolvimentos futuros no backend, embora o servidor já esteja "
                     "preparado para receber esses parâmetros.")
        
        ttk.Label(sec, text=note_text, foreground="#64748b", font=("Inter", 8, "italic"), 
                  wraplength=800, justify="left").grid(row=2, column=0, columnspan=4, pady=(15, 5), padx=5, sticky="w")
        
    def build_windows_setup_section(self, parent):
        if os.name != "nt": return
        
        sec = self.add_section(parent, "WINDOWS SETUP")
        ttk.Label(sec, text="Dependências necessárias: vgamepad, psutil", foreground="#94a3b8").grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        
        ttk.Button(sec, text="Instalar Dependências Windows", command=self.install_dependencies).grid(row=1, column=0, padx=5, pady=10)
        ttk.Button(sec, text="Executar Teste de Captura (Windows)", command=self.run_capture_test).grid(row=1, column=1, padx=5, pady=10)

    def install_dependencies(self):
        self.log("Instalando dependências (vgamepad, psutil)...")
        def run():
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "vgamepad", "psutil"])
                self.log("Dependências instaladas com sucesso!")
                messagebox.showinfo("Sucesso", "Dependências instaladas com sucesso!")
            except Exception as e:
                self.log(f"Erro ao instalar: {e}")
                messagebox.showerror("Erro", f"Falha ao instalar dependências: {e}")
        threading.Thread(target=run, daemon=True).start()

    def run_capture_test(self):
        self.log("Iniciando teste de captura Windows...")
        def run():
            try:
                result = subprocess.run([sys.executable, "test_windows_capture.py"], capture_output=True, text=True)
                self.log(result.stdout)
                if result.stderr: self.log(f"Erros no teste: {result.stderr}")
                if result.returncode == 0:
                    messagebox.showinfo("Teste Concluído", "O teste de captura passou!")
                else:
                    messagebox.showwarning("Teste Falhou", "O teste de captura falhou. Verifique os logs.")
            except Exception as e:
                self.log(f"Erro ao executar teste: {e}")
        threading.Thread(target=run, daemon=True).start()

    def build_log_section(self, parent):
        sec = self.add_section(parent, "LOGS DO SISTEMA")
        self.log_area = scrolledtext.ScrolledText(sec, height=12, bg="#0d0f14", fg="#94a3b8", font=("Monospace", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(sec)
        btn_frame.pack(fill=tk.X, pady=5)
        self.btn_copy_logs = ttk.Button(btn_frame, text="Copiar Logs", command=self.copy_logs)
        self.btn_copy_logs.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Limpar", command=lambda: self.log_area.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=5)

    # --- LOGIC ---
    
    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        # Ensure log area doesn't grow indefinitely (Limit to ~1000 lines)
        if int(self.log_area.index('end-1c').split('.')[0]) > 1000:
            self.log_area.delete("1.0", "2.0")
        self.log_area.see(tk.END)

    def copy_logs(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_area.get("1.0", tk.END))
        
        # Animação de Sucesso
        old_text = self.btn_copy_logs.cget("text")
        self.btn_copy_logs.configure(text="✨ COPIADO COM SUCESSO! ✨")
        
        # Piscar o botão (opcional, mas charmoso)
        self.root.after(1500, lambda: self.btn_copy_logs.configure(text=old_text))

    def update_bitrate_label(self, val):
        kbps = int(float(val))
        if hasattr(self, 'bitrate_label_var'):
            self.bitrate_label_var.set(f"{kbps} Kbps ({kbps/1000:.1f} Mbps)")

    def default_config(self):
        defaults = {
            "resolution": "1280x720", "fps": "60", "bitrate": 5000, "codec": "H.264 (default)",
            "encoder": "Auto", "backend": "X11 (Padrão)", "port": "8080", "audio_bitrate": "128",
            "gop": "60", "latency_preset": "Ultra Baixa"
        }
        for k, v in defaults.items():
            if k in self.vars:
                self.vars[k].set(v)
        self.update_bitrate_label(5000)

    def load_config(self):
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                for k, v in config.items():
                    if k in self.vars:
                        self.vars[k].set(v)
                self.update_bitrate_label(self.vars["bitrate"].get())
                self.log("Configurações carregadas.")
        except Exception as e:
            self.log(f"Erro ao carregar configurações: {e}")

    def save_config(self):
        config = {k: v.get() for k, v in self.vars.items()}
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(config, f)
            self.log("Configurações salvas.")
        except Exception as e:
            self.log(f"Erro salvando: {e}")

    def toggle_server(self):
        if not self.is_running:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        self.save_config()
        
        # Prepare arguments
        v = self.vars
        
        # Mapping UI values to CLI args
        codec_map = {"H.264 (padrão)": "h264", "VP9": "vp9", "AV1 (experimental)": "av1"}
        encoder_map = {
            "Automático": "auto", 
            "NVENC (Nvidia)": "nvenc", 
            "VAAPI (AMD/Intel)": "vaapi", 
            "AMF (AMD)": "amf",
            "QSV (Intel)": "qsv",
            "Software (CPU)": "x264"
        }
        backend_map = {
            "X11 (Padrão)": "x11", 
            "PipeWire": "pipewire",
            "DDA (Alta Perf.)": "dda",
            "GDI (Compatível)": "gdi"
        }
        
        # Base command
        if getattr(sys, 'frozen', False):
            # Bundled mode: use the executable itself and a flag
            cmd = [sys.executable, "--server"]
        else:
            # Development mode
            cmd = [sys.executable, "server.py"]
            
        cmd += [
            "--port", v["port"].get(),
            "--resolution", v["resolution"].get().split()[0],
            "--bitrate", str(v["bitrate"].get()),
            "--fps", v["fps"].get(),
            "--encoder", encoder_map.get(v["encoder"].get(), "auto"),
            "--codec", codec_map.get(v["codec"].get(), "h264"),
            "--audio-bitrate", v["audio_bitrate"].get(),
            "--gop", v["gop"].get(),
            "--capture-backend", backend_map.get(v["backend"].get(), "x11"),
            
            # Advanced Video
            "--h264-profile", v["h264_profile"].get(),
            "--bframes", v["bframes"].get(),
            "--latency-preset", v["latency_preset"].get().lower().replace(" ", "_"),
            "--buffer-video", v["buffer_video"].get(),
            
            # Audio
            "--audio-latency", v["audio_latency"].get().lower(),
            "--buffer-audio", str(v["buffer_audio"].get()),
            
            # Capture
            "--region", v["capture_region"].get(),
            "--monitor", v["monitor_mode"].get().replace(" ", ""),
            
            # Performance/System
            "--process-priority", v["process_priority"].get().lower(),
            "--net-limit", v["net_limit"].get(),
            "--mem-limit", v["mem_limit"].get()
        ]

        # CPU Affinity
        affinity = v["cpu_affinity"].get()
        if affinity.lower() != "all":
            cmd += ["--cpu-affinity", affinity]

        # Boolean Flags
        if v["bitrate_auto"].get(): cmd.append("--bitrate-auto")
        if v["mic_enabled"].get(): cmd.append("--mic-enabled")
        if v["echo_cancel"].get(): cmd.append("--echo-cancel")
        if v["ultra_low_latency"].get(): cmd.append("--ultra-low-latency")
        if v["frame_drop"].get(): cmd.append("--frame-drop")
        if v["capture_cursor"].get(): cmd.append("--capture-cursor")
        if v["dynamic_scale"].get(): cmd.append("--dynamic-scale")
        if v["adaptive_fps"].get(): cmd.append("--adaptive-fps")
        if v["adaptive_bitrate"].get(): cmd.append("--adaptive-bitrate")
        if v["audio_gpu"].get(): cmd.append("--audio-gpu")
        
        if v["debug_mode"].get(): cmd.append("--debug")
        
        self.log(f"Iniciando: {' '.join(cmd)}")
        
        try:
            if os.name != "nt":
                self.server_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, preexec_fn=os.setsid
                )
            else:
                self.server_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            self.is_running = True
            self.btn_toggle.configure(text="PARAR SERVIDOR", style="Stop.TButton")
            self.status_var.set(f"ONLINE (: {v['port'].get()})")
            
            # Ativar áudio GPU após servidor iniciar
            if v["audio_gpu"].get():
                self.set_audio_to_hdmi()
            
            threading.Thread(target=self.read_logs, daemon=True).start()
        except Exception as e:
            self.log(f"Erro crítico ao iniciar: {e}")

    def read_logs(self):
        while self.is_running and self.server_process:
            line = self.server_process.stdout.readline()
            if not line: break
            self.root.after(0, self.log, line.strip())
        
        if self.is_running:
            self.root.after(0, self.server_stopped_unexpectedly)

    def server_stopped_unexpectedly(self):
        if self.is_running:
            self.stop_server()
            self.log("Servidor parou inesperadamente.")

    def stop_server(self):
        if self.server_process:
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                else:
                    self.server_process.send_signal(signal.CTRL_BREAK_EVENT)
                self.server_process.wait(timeout=1)
            except:
                try:
                    self.server_process.kill()
                except: pass
            self.server_process = None
        
        # Restaurar áudio se estava em modo GPU
        if self.vars["audio_gpu"].get():
            self.set_audio_to_analog()
        
        self.is_running = False
        self.btn_toggle.configure(text="INICIAR SERVIDOR", style="Start.TButton")
        self.status_var.set("OFFLINE")
        self.log("Servidor finalizado.")

    def set_audio_to_hdmi(self):
        self._switch_audio("hdmi")

    def set_audio_to_analog(self):
        self._switch_audio("analog")

    def _switch_audio(self, type_target):
        if os.name == "nt":
            self.log("Troca de áudio via interface não suportada no Windows. Use o Painel de Controle.")
            return
        try:
            # 1. Encontrar o sink alvo
            sinks = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
            target_sink = None
            for line in sinks.splitlines():
                parts = line.split()
                if len(parts) >= 2 and type_target in parts[1].lower():
                    target_sink = parts[1]
                    break
            
            if not target_sink:
                messagebox.showerror("Erro", f"Saída {type_target.upper()} não encontrada!")
                return
            
            # 2. Definir como padrão
            subprocess.run(["pactl", "set-default-sink", target_sink], check=True)
            
            # 3. Mover todos os inputs ativos para o novo sink
            try:
                inputs = subprocess.check_output(["pactl", "list", "short", "sink-inputs"], text=True)
                for line in inputs.splitlines():
                    if line.strip():
                        input_id = line.split()[0]
                        subprocess.run(["pactl", "move-sink-input", input_id, target_sink], check=False)
            except:
                pass # Pode não haver inputs ativos
            
            self.log(f"Áudio do sistema redirecionado para: {target_sink}")
            messagebox.showinfo("Sucesso", f"Áudio redirecionado para:\n{target_sink}")
            
        except Exception as e:
            self.log(f"Erro ao mudar áudio: {e}")
            messagebox.showerror("Erro", f"Falha ao mudar áudio: {e}")

    # DYNAMIC BITRATE UPDATE
    def update_live_bitrate(self, event=None):
        if not self.is_running: return
        
        try:
            import urllib.request
            import json
            
            port = self.vars["port"].get()
            bitrate_kbps = self.vars["bitrate"].get()
            
            url = f"http://127.0.0.1:{port}/api/settings"
            data = json.dumps({"bitrate": bitrate_kbps}).encode("utf-8")
            
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    self.log(f"Bitrate atualizado ao vivo: {bitrate_kbps} Kbps")
                    self.save_config()
        except Exception as e:
            self.log(f"Falha ao atualizar bitrate: {e}")

if __name__ == "__main__":
    if "--server" in sys.argv:
        # Launch server logic directly
        import server
        # Remove the --server flag from sys.argv so argparse doesn't complain
        sys.argv.remove("--server")
        server.main()
    else:
        root = tk.Tk()
        app = ServerGUI(root)
        root.mainloop()

