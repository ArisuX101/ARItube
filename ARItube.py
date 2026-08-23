import os
import re
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, filedialog
import yt_dlp

# --- COLOR THEMES PALETTES ---
THEMES = {
    "Dark Midnight": {
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "card_bg": "#181825",
        "accent": "#89b4fa",
        "btn_bg": "#313244",
        "entry_bg": "#11111b",
        "log_bg": "#11111b",
        "log_fg": "#a6e3a1",
    },
    "Cyberpunk": {
        "bg": "#0d0221",
        "fg": "#00f0ff",
        "card_bg": "#15052a",
        "accent": "#ff0055",
        "btn_bg": "#260941",
        "entry_bg": "#02010a",
        "log_bg": "#02010a",
        "log_fg": "#ff0055",
    },
    "Nord / Slate": {
        "bg": "#2e3440",
        "fg": "#eceff4",
        "card_bg": "#3b4252",
        "accent": "#88c0d0",
        "btn_bg": "#434c5e",
        "entry_bg": "#1d212a",
        "log_bg": "#1d212a",
        "log_fg": "#a3be8c",
    },
    "Clean Light": {
        "bg": "#f8f9fa",
        "fg": "#212529",
        "card_bg": "#ffffff",
        "accent": "#0d6efd",
        "btn_bg": "#e9ecef",
        "entry_bg": "#ffffff",
        "log_bg": "#ffffff",
        "log_fg": "#198754",
    },
    "Sakura": {
        "bg": "#ff66de",
        "fg": "#050105",
        "card_bg": "#ff41f2",
        "accent": "#9d00db",
        "btn_bg": "#ff41f2",
        "entry_bg": "#ff41f2",
        "log_bg": "#ff41f2",
        "log_fg": "#490000",
    },
    "Sakura2": {
        "bg": "#fdf0f5",        # Soft blush pink background
        "fg": "#4a2238",        # Dark plum text for high readability
        "card_bg": "#f8daf0",   # Muted pink card containers
        "accent": "#d63384",    # Deep magenta headers & accents
        "btn_bg": "#f3b0db",    # Soft pink button background
        "entry_bg": "#ffffff",  # Crisp white entry box
        "log_bg": "#ffffff",    # Crisp white log box
        "log_fg": "#85144b",    # Deep red/pink log text
    },
}


def find_vlc_path():
    paths = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]
    for path in paths:
        if os.path.exists(path): return path
    return None

def check_ffmpeg():
    return shutil.which("ffmpeg") is not None or os.path.exists("ffmpeg.exe")

class YTDLPLogger:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def debug(self, msg):
        if msg.startswith("[download]") and "ETA" not in msg:
            self.write(msg)
    def info(self, msg): self.write(msg)
    def warning(self, msg): self.write(f"WARNING: {msg}")
    def error(self, msg): self.write(f"ERROR: {msg}")
    
    def write(self, text):
        self.text_widget.after(0, self._append_text, str(text) + "\n")
    def _append_text(self, text):
        self.text_widget.insert(tk.END, text)
        self.text_widget.see(tk.END)

class ARItubeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ARItube - Stream & Downloader")
        self.root.geometry("750x650")
        self.root.minsize(650, 550)

        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.setup_ui()
        self.apply_theme("Dark Midnight")

    def setup_ui(self):
        padding = {"padx": 10, "pady": 5}

        # --- Top Bar ---
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", **padding)

        ttk.Label(top_frame, text="ARItube Media Downloader", font=("Segoe UI", 14, "bold")).pack(side="left", padx=5)

        theme_frame = ttk.Frame(top_frame)
        theme_frame.pack(side="right")
        ttk.Label(theme_frame, text="Theme:", font=("Segoe UI", 9)).pack(side="left", padx=3)
        
        self.theme_var = tk.StringVar(value="Dark Midnight")
        theme_box = ttk.Combobox(theme_frame, textvariable=self.theme_var, values=list(THEMES.keys()), state="readonly", width=14)
        theme_box.pack(side="right")
        theme_box.bind("<<ComboboxSelected>>", lambda e: self.apply_theme(self.theme_var.get()))

        # --- URL Input ---
        self.url_frame = ttk.LabelFrame(self.root, text=" YouTube URL or Playlist Link ")
        self.url_frame.pack(fill="x", **padding)

        self.url_entry = tk.Entry(self.url_frame, font=("Segoe UI", 10), relief="flat", bd=5)
        self.url_entry.pack(fill="x", padx=10, pady=10)

        # --- Download Location ---
        self.dir_frame = ttk.LabelFrame(self.root, text=" Save To ")
        self.dir_frame.pack(fill="x", **padding)

        default_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        self.dir_var = tk.StringVar(value=default_dir)
        
        self.dir_entry = tk.Entry(self.dir_frame, textvariable=self.dir_var, font=("Segoe UI", 10), relief="flat", bd=5)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)

        self.browse_btn = ttk.Button(self.dir_frame, text="📁 Browse", command=self.choose_directory)
        self.browse_btn.pack(side="right", padx=(5, 10), pady=10)

        # --- Actions ---
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", **padding)

        self.stream_btn = ttk.Button(btn_frame, text="🎬 Stream in VLC", command=lambda: self.start_action("stream"))
        self.stream_btn.pack(side="left", expand=True, fill="x", padx=3)

        self.video_btn = ttk.Button(btn_frame, text="📥 Download MP4", command=lambda: self.start_action("video"))
        self.video_btn.pack(side="left", expand=True, fill="x", padx=3)

        self.audio_btn = ttk.Button(btn_frame, text="🎵 Download MP3", command=lambda: self.start_action("audio"))
        self.audio_btn.pack(side="left", expand=True, fill="x", padx=3)

        # --- Progress Bar ---
        self.progress_frame = ttk.Frame(self.root)
        self.progress_frame.pack(fill="x", **padding)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.progress_label = ttk.Label(self.progress_frame, text="0.0% | Ready", font=("Consolas", 9), width=35, anchor="e")
        self.progress_label.pack(side="right")

        # --- Log ---
        self.log_frame = ttk.LabelFrame(self.root, text=" Status Log ")
        self.log_frame.pack(fill="both", expand=True, **padding)

        self.log_widget = scrolledtext.ScrolledText(self.log_frame, wrap="word", font=("Consolas", 9), bd=0)
        self.log_widget.pack(fill="both", expand=True, padx=5, pady=5)

    def apply_theme(self, theme_name):
        colors = THEMES[theme_name]
        self.root.configure(bg=colors["bg"])

        self.style.configure(".", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TLabelframe", background=colors["bg"], foreground=colors["accent"])
        self.style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["accent"])
        
        self.style.configure(
            "TButton", background=colors["btn_bg"], foreground=colors["fg"],
            bordercolor=colors["bg"], focusthickness=0, padding=6
        )
        self.style.map("TButton",
            background=[("active", colors["accent"]), ("disabled", colors["card_bg"])],
            foreground=[("active", "#ffffff"), ("disabled", "#888888")]
        )

        self.style.configure(
            "Horizontal.TProgressbar", background=colors["accent"], troughcolor=colors["entry_bg"],
            bordercolor=colors["bg"], lightcolor=colors["accent"], darkcolor=colors["accent"]
        )

        self.style.configure("TCombobox", fieldbackground=colors["entry_bg"], background=colors["btn_bg"], foreground=colors["fg"], arrowcolor=colors["fg"])
        self.root.option_add("*TCombobox*Listbox*background", colors["entry_bg"])
        self.root.option_add("*TCombobox*Listbox*foreground", colors["fg"])

        for entry in (self.url_entry, self.dir_entry):
            entry.configure(
                bg=colors["entry_bg"], fg=colors["fg"], insertbackground=colors["fg"],
                highlightbackground=colors["accent"], highlightcolor=colors["accent"]
            )
            
        self.log_widget.configure(bg=colors["log_bg"], fg=colors["log_fg"], insertbackground=colors["fg"])

    def choose_directory(self):
        folder = filedialog.askdirectory(title="Select Download Folder")
        if folder: self.dir_var.set(folder)

    def log(self, message):
        self.log_widget.insert(tk.END, message + "\n")
        self.log_widget.see(tk.END)

    def set_buttons_state(self, state):
        self.stream_btn.config(state=state)
        self.video_btn.config(state=state)
        self.audio_btn.config(state=state)

    def update_progress(self, val, text):
        self.progress_var.set(val)
        self.progress_label.config(text=text)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            percent = (downloaded / total * 100) if total > 0 else 0.0

            # Strip terminal color codes from yt-dlp strings cleanly
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            speed = ansi_escape.sub('', d.get('_speed_str', 'N/A')).strip()
            eta = ansi_escape.sub('', d.get('_eta_str', 'N/A')).strip()

            self.root.after(0, self.update_progress, percent, f"{percent:.1f}% | {speed} | ETA: {eta}")

        elif d['status'] == 'finished':
            self.root.after(0, self.update_progress, 100.0, "100.0% | Processing... | ETA: 00:00")

    def get_privacy_opts(self):
        return {
            "logger": YTDLPLogger(self.log_widget),
            "progress_hooks": [self.progress_hook],
            "nocolor": True,
            "extractor_args": {"youtube": {"player_client": ["ios", "android", "tv"]}},
        }

    def start_action(self, mode):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Input Error", "Please paste a YouTube URL first!")
            return

        self.set_buttons_state("disabled")
        threading.Thread(target=self.process_task, args=(url, mode), daemon=True).start()

    def process_task(self, url, mode):
        try:
            if mode == "stream": self.stream_logic(url)
            elif mode == "video": self.download_video_logic(url)
            elif mode == "audio": self.download_audio_logic(url)
        except Exception as e:
            self.log(f"\n[!] Error: {str(e)}")
            self.root.after(0, self.update_progress, 0.0, "Error occurred.")
        finally:
            self.set_buttons_state("normal")

    def stream_logic(self, url):
        self.root.after(0, self.update_progress, 0.0, "Fetching stream...")
        vlc_exe = find_vlc_path()
        if not vlc_exe:
            self.log("[!] Error: VLC Media Player executable not found.")
            return

        self.log("Fetching stream link(s)...")
        ydl_opts = self.get_privacy_opts()
        ydl_opts.update({"format": "bestvideo+bestaudio/best", "extract_flat": "in_playlist"})

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if "entries" in info:
            self.log(f"\nProcessing Playlist: {info.get('title', 'Playlist')}")
            m3u_content = ["#EXTM3U\n"]
            ydl_opts_single = self.get_privacy_opts()
            ydl_opts_single["format"] = "bestvideo+bestaudio/best"

            with yt_dlp.YoutubeDL(ydl_opts_single) as ydl_single:
                for idx, entry in enumerate(info["entries"], start=1):
                    item_url = entry.get("url") or entry.get("webpage_url")
                    if not item_url: continue
                    try:
                        item_info = ydl_single.extract_info(item_url, download=False)
                        title = item_info.get("title", f"Track {idx}")
                        if "requested_formats" in item_info:
                            v_url = item_info["requested_formats"][0]["url"]
                            a_url = item_info["requested_formats"][1]["url"]
                            m3u_content.extend([f"#EXTINF:-1,{title}\n", f"#EXTVLCOPT:input-slave={a_url}\n", f"{v_url}\n"])
                        else:
                            m3u_content.extend([f"#EXTINF:-1,{title}\n", f"{item_info['url']}\n"])
                    except Exception as e:
                        self.log(f"Skipping track {idx}: {e}")

            temp_playlist = os.path.join(tempfile.gettempdir(), "yt_playlist.m3u8")
            with open(temp_playlist, "w", encoding="utf-8") as f:
                f.writelines(m3u_content)

            self.log("Launching playlist in VLC...")
            subprocess.Popen([vlc_exe, temp_playlist])
            self.root.after(0, self.update_progress, 100.0, "Playing in VLC")
        else:
            title = info.get("title", "Video")
            self.log(f"Launching VLC HD Stream: {title}")
            if "requested_formats" in info:
                subprocess.Popen([vlc_exe, info["requested_formats"][0]["url"], f"--input-slave={info['requested_formats'][1]['url']}"])
            else:
                subprocess.Popen([vlc_exe, info["url"]])
            self.root.after(0, self.update_progress, 100.0, "Playing in VLC")

    def download_video_logic(self, url):
        self.root.after(0, self.update_progress, 0.0, "Initializing...")
        self.log("Starting high-quality MP4 download...")
        
        save_path = self.dir_var.get()
        ydl_opts = self.get_privacy_opts()
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "outtmpl": os.path.join(save_path, "%(playlist_title|.)s", "%(playlist_index&{} - |)s%(title)s.%(ext)s"),
            "merge_output_format": "mp4",
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        self.root.after(0, self.update_progress, 100.0, "Finished MP4 Download")
        self.log("\n✅ Video download complete!")

    def download_audio_logic(self, url):
        if not check_ffmpeg():
            self.log("\n[!] ERROR: FFmpeg is missing! Place ffmpeg.exe next to ARItube_gui.py.")
            return

        self.root.after(0, self.update_progress, 0.0, "Initializing...")
        self.log("Starting MP3 audio download...")
        
        save_path = self.dir_var.get()
        ydl_opts = self.get_privacy_opts()
        ydl_opts.update({
            "format": "bestaudio/best",
            "outtmpl": os.path.join(save_path, "%(playlist_title|.)s", "%(playlist_index&{} - |)s%(title)s.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        self.root.after(0, self.update_progress, 100.0, "Finished MP3 Download")
        self.log("\n✅ MP3 download complete!")

if __name__ == "__main__":
    root = tk.Tk()
    app = ARItubeApp(root)
    root.mainloop()