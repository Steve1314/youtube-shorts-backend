import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import threading
import os
import webbrowser
from datetime import datetime

# Color Palette (YouTube Dark Theme)
BG_COLOR = "#0f0f0f"      # Pure Black/Dark Grey
SIDEBAR_COLOR = "#0f0f0f"  
CARD_COLOR = "#212121"     # Lighter Grey card
TEXT_COLOR = "#ffffff"     # White text
SUBTEXT_COLOR = "#aaaaaa"  # Muted grey text
YT_RED = "#ff0000"         # YouTube Red
ACCENT_GREEN = "#2ba640"   # YouTube success green

class YouTubeShortsGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Shorts Studio")
        self.root.geometry("900x700")
        self.root.configure(bg=BG_COLOR)
        
        self.BASE_URL = "http://localhost:8000"
        
        self.setup_styles()
        self.setup_ui()
        self.refresh_data()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure Frames
        self.style.configure("TFrame", background=BG_COLOR)
        self.style.configure("Card.TFrame", background=CARD_COLOR, relief="flat")
        
        # Configure Notebook
        self.style.configure("TNotebook", background=BG_COLOR, borderwidth=0)
        self.style.configure("TNotebook.Tab", 
                            background=BG_COLOR, 
                            foreground=SUBTEXT_COLOR, 
                            padding=[15, 5], 
                            font=("Helvetica", 10, "bold"))
        self.style.map("TNotebook.Tab", 
                      background=[("selected", CARD_COLOR)], 
                      foreground=[("selected", YT_RED)])
        
        # Configure Labels
        self.style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Helvetica", 10))
        self.style.configure("Header.TLabel", font=("Helvetica", 14, "bold"), foreground=TEXT_COLOR)
        self.style.configure("Sub.TLabel", font=("Helvetica", 9), foreground=SUBTEXT_COLOR)
        self.style.configure("CardHeader.TLabel", background=CARD_COLOR, font=("Helvetica", 11, "bold"), foreground=TEXT_COLOR)
        
        # Configure Buttons
        self.style.configure("TButton", 
                            font=("Helvetica", 10, "bold"), 
                            background=CARD_COLOR, 
                            foreground=TEXT_COLOR, 
                            borderwidth=0)
        self.style.map("TButton", 
                      background=[("active", "#333333")], 
                      foreground=[("active", YT_RED)])
        
        self.style.configure("Primary.TButton", background=YT_RED, foreground="white")
        self.style.map("Primary.TButton", background=[("active", "#cc0000")])
        
        # Configure Treeview
        self.style.configure("Treeview", 
                            background=CARD_COLOR, 
                            foreground=TEXT_COLOR, 
                            fieldbackground=CARD_COLOR, 
                            borderwidth=0, 
                            font=("Helvetica", 10))
        self.style.configure("Treeview.Heading", 
                            background=BG_COLOR, 
                            foreground=SUBTEXT_COLOR, 
                            font=("Helvetica", 10, "bold"))
        self.style.map("Treeview", background=[("selected", YT_RED)])

    def setup_ui(self):
        # Header Area
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill="x", padx=20, pady=20)
        
        ttk.Label(header_frame, text="YouTube", foreground=YT_RED, font=("Helvetica", 18, "bold")).pack(side="left")
        ttk.Label(header_frame, text=" Shorts Studio", font=("Helvetica", 18, "bold")).pack(side="left")
        
        # Main Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Tabs
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_videos = ttk.Frame(self.notebook)
        self.tab_schedule = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_dashboard, text="DASHBOARD")
        self.notebook.add(self.tab_videos, text="CONTENT")
        self.notebook.add(self.tab_schedule, text="ANALYTICS")
        
        self.setup_dashboard()
        self.setup_videos()
        self.setup_queue()

    def create_card(self, parent, title):
        card = ttk.Frame(parent, style="Card.TFrame")
        card.pack(fill="x", padx=10, pady=10)
        
        inner = tk.Frame(card, bg=CARD_COLOR, padx=15, pady=15)
        inner.pack(fill="both", expand=True)
        
        ttk.Label(inner, text=title, style="CardHeader.TLabel", background=CARD_COLOR).pack(anchor="w", pady=(0, 10))
        return inner

    def setup_dashboard(self):
        # Status Card
        status_inner = self.create_card(self.tab_dashboard, "Channel Status")
        
        self.lbl_backend_status = ttk.Label(status_inner, text="Server: Connecting...", background=CARD_COLOR)
        self.lbl_backend_status.pack(anchor="w", pady=5)
        
        self.lbl_auth_status = ttk.Label(status_inner, text="YouTube Identity: Verifying...", background=CARD_COLOR)
        self.lbl_auth_status.pack(anchor="w", pady=5)
        
        # Actions card
        actions_inner = self.create_card(self.tab_dashboard, "Quick Actions")
        
        btn_frame = ttk.Frame(actions_inner)
        btn_frame.configure(style="TFrame") # Match card BG
        btn_frame.pack(fill="x", pady=10)
        tk.Frame(btn_frame, bg=CARD_COLOR).pack() # Spacer trick
        
        btn_auth = tk.Button(actions_inner, text="CONNECT CHANNEL", bg=YT_RED, fg="white", font=("Helvetica", 9, "bold"), 
                           relief="flat", padx=15, pady=8, command=self.open_auth, cursor="hand2")
        btn_auth.pack(side="left", padx=5)
        
        btn_refresh = tk.Button(actions_inner, text="REFRESH DATA", bg="#333333", fg="white", font=("Helvetica", 9, "bold"), 
                             relief="flat", padx=15, pady=8, command=self.refresh_data, cursor="hand2")
        btn_refresh.pack(side="left", padx=5)
        
        btn_upload_next = tk.Button(actions_inner, text="UPLOAD NEXT NOW", bg="#333333", fg="white", font=("Helvetica", 9, "bold"), 
                                 relief="flat", padx=15, pady=8, command=self.upload_next, cursor="hand2")
        btn_upload_next.pack(side="left", padx=5)

        self.btn_instant = tk.Button(actions_inner, text="INSTANT PUBLISH", bg="#333333", fg=YT_RED, font=("Helvetica", 9, "bold"), 
                                 relief="flat", padx=15, pady=8, command=self.instant_publish, cursor="hand2", borderwidth=1, highlightbackground=YT_RED)
        self.btn_instant.pack(side="left", padx=5)

    def setup_videos(self):
        # Upload Card
        upload_inner = self.create_card(self.tab_videos, "Upload to Server")
        
        self.btn_select_file = tk.Button(upload_inner, text="SELECT VIDEOS", bg=YT_RED, fg="white", font=("Helvetica", 10, "bold"), 
                                       relief="flat", padx=20, pady=10, command=self.select_and_upload, cursor="hand2")
        self.btn_select_file.pack(pady=10)
        
        ttk.Label(upload_inner, text="Supported formats: MP4, MOV, MKV, WEBM", style="Sub.TLabel", background=CARD_COLOR).pack()
        
        # List Card
        list_inner = self.create_card(self.tab_videos, "Video Library")
        
        self.video_listbox = tk.Listbox(list_inner, bg="#1a1a1a", fg=TEXT_COLOR, borderwidth=0, 
                                      highlightthickness=0, font=("Helvetica", 10), selectbackground=YT_RED)
        self.video_listbox.pack(fill="both", expand=True, pady=5)
        
        # Schedule Card
        gen_inner = self.create_card(self.tab_videos, "Bulk Scheduler")
        
        input_frame = tk.Frame(gen_inner, bg=CARD_COLOR)
        input_frame.pack(fill="x", pady=5)
        
        ttk.Label(input_frame, text="Start Date:", background=CARD_COLOR).pack(side="left", padx=5)
        self.ent_start_date = tk.Entry(input_frame, bg="#333333", fg="white", borderwidth=0, insertbackground="white", font=("Helvetica", 10))
        self.ent_start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.ent_start_date.pack(side="left", padx=5, ipady=3)
        
        btn_gen = tk.Button(gen_inner, text="GENERATE AUTOMATIC SCHEDULE", bg=YT_RED, fg="white", font=("Helvetica", 9, "bold"), 
                           relief="flat", padx=15, pady=8, command=self.generate_schedule, cursor="hand2")
        btn_gen.pack(pady=10)

    def setup_queue(self):
        # Queue Table card
        queue_inner = self.create_card(self.tab_schedule, "Upcoming Uploads")
        
        cols = ("Filename", "Publish Time (IST)", "Status")
        self.queue_tree = ttk.Treeview(queue_inner, columns=cols, show="headings", height=15)
        
        for col in cols:
            self.queue_tree.heading(col, text=col.upper())
            self.queue_tree.column(col, width=200, anchor="center")
            
        self.queue_tree.pack(fill="both", expand=True)
        
        # Scrollbar for tree
        scb = ttk.Scrollbar(queue_inner, orient="vertical", command=self.queue_tree.yview)
        # Treeview doesn't support built-in scrollbar well with layouts but let's try
        self.queue_tree.configure(yscrollcommand=scb.set)

    def refresh_data(self):
        def task():
            try:
                # Backend status
                res = requests.get(f"{self.BASE_URL}/health")
                if res.status_code == 200:
                    self.lbl_backend_status.config(text="Server: Online ✅", foreground=ACCENT_GREEN)
                else:
                    self.lbl_backend_status.config(text="Server: Error ❌", foreground=YT_RED)
            except:
                self.lbl_backend_status.config(text="Server: Offline ❌", foreground=YT_RED)
                
            try:
                # Auth status
                res = requests.get(f"{self.BASE_URL}/auth/status")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("authenticated"):
                        self.lbl_auth_status.config(text="YouTube Identity: Connected ✅", foreground=ACCENT_GREEN)
                    else:
                        self.lbl_auth_status.config(text="YouTube Identity: Disconnected ❌", foreground=YT_RED)
                else:
                    self.lbl_auth_status.config(text="YouTube Identity: Status Error ❌", foreground=YT_RED)
            except:
                self.lbl_auth_status.config(text="YouTube Identity: Server Offline ❌", foreground=YT_RED)
                
            try:
                # Videos list
                res = requests.get(f"{self.BASE_URL}/videos")
                if res.status_code == 200:
                    videos = res.json().get("videos", [])
                    self.video_listbox.delete(0, tk.END)
                    for v in videos:
                        self.video_listbox.insert(tk.END, f"  🎥  {v}")
                
                # Schedule list
                res = requests.get(f"{self.BASE_URL}/schedule")
                if res.status_code == 200:
                    items = res.json().get("items", [])
                    for i in self.queue_tree.get_children():
                        self.queue_tree.delete(i)
                    for item in items:
                        status = item.get('status', 'pending')
                        display_status = f"✅ {status.upper()}" if status == "uploaded" else status.upper()
                        self.queue_tree.insert("", tk.END, values=(item.get('filename'), item.get('publish_time'), display_status))
            except Exception as e:
                print(f"Refresh error: {e}")

        threading.Thread(target=task).start()

    def open_auth(self):
        webbrowser.open(f"{self.BASE_URL}/auth/start")
        messagebox.showinfo("Studio Auth", "Redirecting to Google. Please finish authorization in your browser.")

    def select_and_upload(self):
        file_paths = filedialog.askopenfilenames(filetypes=[("Video files", "*.mp4 *.mov *.mkv *.webm")])
        if not file_paths:
            return
            
        def upload_task():
            try:
                self.btn_select_file.config(state="disabled", text="UPLOADING...")
                for file_path in file_paths:
                    filename = os.path.basename(file_path)
                    with open(file_path, "rb") as f:
                        res = requests.post(f"{self.BASE_URL}/videos/upload", files={"file": (filename, f)})
                
                messagebox.showinfo("Studio Status", f"Batch upload complete: {len(file_paths)} videos added.")
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Studio Error", str(e))
            finally:
                self.btn_select_file.config(state="normal", text="SELECT VIDEOS")
                
        threading.Thread(target=upload_task).start()

    def generate_schedule(self):
        start_date = self.ent_start_date.get()
        try:
            res = requests.post(f"{self.BASE_URL}/schedule/generate", params={"start_date": start_date})
            if res.status_code == 200:
                messagebox.showinfo("Studio Status", "Auto-Schedule generated for your library!")
                self.refresh_data()
            else:
                messagebox.showerror("Studio Error", res.json().get("detail", res.text))
        except Exception as e:
            messagebox.showerror("Studio Error", str(e))

    def upload_next(self):
        def task():
            try:
                res = requests.post(f"{self.BASE_URL}/upload/next")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success":
                        messagebox.showinfo("Studio Status", f"Manually Published: {data.get('filename')}")
                    else:
                        messagebox.showinfo("Studio Info", data.get("message"))
                    self.refresh_data()
                else:
                    messagebox.showerror("Studio Error", res.text)
            except Exception as e:
                messagebox.showerror("Studio Error", str(e))
        
        threading.Thread(target=task).start()

    def instant_publish(self):
        file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mov *.mkv *.webm")])
        if not file_path:
            return
            
        def upload_task():
            try:
                self.btn_instant.config(state="disabled", text="PUBLISHING...")
                filename = os.path.basename(file_path)
                with open(file_path, "rb") as f:
                    res = requests.post(f"{self.BASE_URL}/upload/instant", files={"file": (filename, f)})
                
                if res.status_code == 200:
                    messagebox.showinfo("Studio Status", "Success! Video is now LIVE on YouTube.")
                    self.refresh_data()
                else:
                    messagebox.showerror("Studio Error", f"Instant publish failed: {res.text}")
            except Exception as e:
                messagebox.showerror("Studio Error", str(e))
            finally:
                self.btn_instant.config(state="normal", text="INSTANT PUBLISH")
                
        threading.Thread(target=upload_task).start()

if __name__ == "__main__":
    root = tk.Tk()
    # Simple Roboto check or Helvetica default
    app = YouTubeShortsGUI(root)
    root.mainloop()
