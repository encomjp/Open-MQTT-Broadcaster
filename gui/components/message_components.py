import tkinter as tk
from tkinter import ttk, scrolledtext
from gui.components.base import BaseComponent, StyledFrame
from datetime import datetime

class MessageComponents(BaseComponent):
    HIGHLIGHT_PARTS = ("Broadcasting", "complete", "failed", "Success rate")
    CHANNEL_TIMEOUT = 40  # seconds before a channel is considered offline

    def __init__(self, parent, colors, on_channel_selection=None):
        super().__init__(parent, colors)
        self.on_channel_selection = on_channel_selection
        self.content_frame = ttk.Frame(parent, style='Dark.TFrame')
        self.channel_last_seen = {}
        self.root = parent
        self._selection_after_id = None
        self._last_selection_time = 0
        self._setup_components()
        
        # Start channel status checker
        self._status_check()

    def _setup_components(self):
        # Configure grid for 30/70 split between channels and messages
        self.content_frame.grid_columnconfigure(1, weight=7)
        self.content_frame.grid_columnconfigure(0, weight=3)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Create channel list
        self._setup_channel_list()
        # Create message display
        self._setup_message_display()

    def _setup_channel_list(self):
        # Left Panel - Channels
        left_frame = ttk.Frame(self.content_frame, style='Dark.TFrame')
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_frame.grid_rowconfigure(1, weight=1)  # Online channels get more space
        left_frame.grid_rowconfigure(2, weight=1)  # Offline channels get equal space
        left_frame.grid_columnconfigure(0, weight=1)

        # Online Channels Frame
        self.online_frame = StyledFrame(left_frame, self.colors, title="Online Channels (0)")
        self.online_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 5))
        
        self.online_list = tk.Listbox(
            self.online_frame.frame,
            selectmode=tk.EXTENDED,
            font=('Helvetica', 10),
            background=self.colors['input_bg'],
            foreground=self.colors['fg'],
            selectbackground=self.colors['selection_bg'],
            selectforeground=self.colors['selection_fg'],
            activestyle='none'
        )
        self.online_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.online_list.bind('<<ListboxSelect>>', self._on_selection_changed)

        # Offline Channels Frame
        self.offline_frame = StyledFrame(left_frame, self.colors, title="Offline Channels (0)")
        self.offline_frame.grid(row=2, column=0, sticky="nsew")
        
        self.offline_list = tk.Listbox(
            self.offline_frame.frame,
            selectmode=tk.EXTENDED,
            font=('Helvetica', 10),
            background=self.colors['input_bg'],
            foreground=self.colors['fg_dim'],  # Dimmed color for offline
            selectbackground=self.colors['selection_bg'],
            selectforeground=self.colors['selection_fg'],
            activestyle='none'
        )
        self.offline_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.offline_list.bind('<<ListboxSelect>>', self._on_selection_changed)

        # Initialize with All Channels in online
        self.online_list.insert(tk.END, "All Channels")
        self.update_channel_counts()

    def _on_selection_changed(self, event=None):
        """Handle selection changes in either listbox with rate limiting"""
        import time
        now = time.time()
        if hasattr(self, '_last_selection_time'):
            # Limit selection updates to once every 100ms
            if now - self._last_selection_time < 0.1:
                return
        self._last_selection_time = now

        # Clear selection in the other listbox
        if event and event.widget == self.online_list:
            self.offline_list.selection_clear(0, tk.END)
        elif event and event.widget == self.offline_list:
            self.online_list.selection_clear(0, tk.END)

        if self.on_channel_selection:
            self.on_channel_selection()

    def _status_check(self):
        """Periodically check channel status using Tkinter's event loop"""
        self.update_channel_status()
        # Schedule next check in 5 seconds
        self.root.after(5000, self._status_check)

    def update_channel_status(self):
        """Update channel online/offline status"""
        now_dt = datetime.now()
        online_channels = {ch for ch, last_seen in self.channel_last_seen.items() 
                         if (now_dt - last_seen).total_seconds() < self.CHANNEL_TIMEOUT}
        
        def move_channel(channel, from_list, to_list):
            try:
                idx = list(from_list.get(0, tk.END)).index(channel)
                channel_item = from_list.get(idx)
                from_list.delete(idx)
                to_list.insert(tk.END, channel_item)
            except (ValueError, tk.TclError):
                pass
        
        channels = list(self.get_channels())
        for channel in channels:
            if channel == "All Channels":
                continue
            
            is_in_online = channel in list(self.online_list.get(0, tk.END))
            is_in_offline = channel in list(self.offline_list.get(0, tk.END))
            
            if channel in online_channels:
                if is_in_offline:
                    move_channel(channel, self.offline_list, self.online_list)
            else:
                if is_in_online:
                    move_channel(channel, self.online_list, self.offline_list)
        
        self.update_channel_counts()

    def update_channel_counts(self):
        """Update the channel count displays"""
        online_count = self.online_list.size()
        offline_count = self.offline_list.size()
        self.online_frame.frame.configure(text=f"Online Channels ({online_count})")
        self.offline_frame.frame.configure(text=f"Offline Channels ({offline_count})")

    def add_channel(self, channel):
        """Add a new channel and mark it as recently seen"""
        if channel not in self.get_channels():
            self.channel_last_seen[channel] = datetime.now()
            self.online_list.insert(tk.END, channel)
            self.update_channel_counts()

    def mark_channel_seen(self, channel):
        """Update the last seen time for a channel"""
        self.channel_last_seen[channel] = datetime.now()
        try:
            idx = list(self.online_list.get(0, tk.END)).index(channel)
            self.online_list.itemconfig(idx, fg=self.colors['fg'])
        except ValueError:
            pass  # Channel might be in offline list
        self.update_channel_status()

    def get_channels(self):
        """Get all channels from both online and offline lists"""
        try:
            return (list(self.online_list.get(0, tk.END)) + 
                   list(self.offline_list.get(0, tk.END)))
        except tk.TclError:
            return []

    def get_selected_channels(self):
        """Get selected channels from either list"""
        try:
            online_sel = [self.online_list.get(i) for i in self.online_list.curselection()]
            offline_sel = [self.offline_list.get(i) for i in self.offline_list.curselection()]
            return online_sel + offline_sel
        except tk.TclError:
            return []

    def get_current_channel(self):
        """Get the currently selected channel from either list"""
        online_sel = self.online_list.curselection()
        if online_sel:
            return self.online_list.get(online_sel[0])
        
        offline_sel = self.offline_list.curselection()
        if offline_sel:
            return self.offline_list.get(offline_sel[0])
        
        return None

    def _setup_message_display(self):
        # Right Panel
        right_frame = ttk.Frame(self.content_frame, style='Dark.TFrame')
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # Messages area
        self.messages_frame = StyledFrame(right_frame, self.colors, title="Messages")
        self.messages_frame.frame.grid(row=0, column=0, sticky="nsew")
        
        self.text = scrolledtext.ScrolledText(
            self.messages_frame.frame,
            wrap=tk.WORD,
            font=('Consolas', 11),
            background=self.colors['input_bg'],
            foreground=self.colors['fg'],
            insertbackground=self.colors['fg'],
            selectbackground=self.colors['selection_bg'],
            selectforeground=self.colors['selection_fg'],
            padx=12, pady=12,
            borderwidth=1,
            relief=tk.SOLID,
            state='disabled',  # Make read-only
            cursor="arrow"     # Show normal cursor instead of text cursor
        )
        self.text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Only bind scrolling behavior, let tkinter handle selection naturally
        self.text.bind('<MouseWheel>', self._on_mouse_scroll)  # Windows/macOS
        self.text.bind('<Button-4>', self._on_mouse_scroll)    # Linux scroll up
        self.text.bind('<Button-5>', self._on_mouse_scroll)    # Linux scroll down
        
        self._auto_scroll = True
        self._last_scroll_time = 0
        self._setup_tags()

    def _copy_selection(self, event=None):
        """Handle copy operation"""
        try:
            selected_text = self.text.get("sel.first", "sel.last")
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass  # No selection
        return 'break'  # Prevent default copy behavior

    def _setup_tags(self):
        """Setup message display tags"""
        tags = {
            "timestamp": self.colors['timestamp'],
            "error": self.colors['error_msg'],
            "system": self.colors['system_msg'],
            "broadcast": self.colors['broadcast_msg'],
            "normal": self.colors['normal_msg'],
            "highlight": self.colors['highlight']
        }
        
        for tag, color in tags.items():
            self.text.tag_configure(tag, foreground=color)

    def display_message(self, channel, message, timestamp, message_type="normal"):
        """Display a message in the message area"""
        # Store current view position
        try:
            first, last = self.text.yview()
        except:
            first, last = 0, 1

        # Temporarily enable widget to insert text
        self.text.config(state='normal')
        
        self.text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.text.insert(tk.END, f"{channel}: {message}\n", message_type)
        
        # Return to disabled state and ensure cursor consistency
        self.text.config(state='disabled')
        self.text.configure(cursor="arrow")  # Always show arrow cursor
        
        # Only auto-scroll if we were already at the bottom
        if not self._auto_scroll:
            # Restore previous view position
            self.text.yview_moveto(first)
        else:
            self.text.see(tk.END)

        # Trim the text widget content if too many lines are present to improve performance
        max_lines = 500
        try:
            current_lines = int(self.text.index("end-1c").split('.')[0])
            if current_lines > max_lines:
                self.text.config(state='normal')
                # Delete the oldest lines so that only max_lines remain
                lines_to_delete = current_lines - max_lines
                self.text.delete("1.0", f"{lines_to_delete + 1}.0")
                self.text.config(state='disabled')
        except Exception as e:
            pass

    def _on_mouse_scroll(self, event):
        """Handle mouse scroll events"""
        import time
        self._last_scroll_time = time.time()
        # Check if we're at the bottom after scrolling
        self.root.after(50, self._check_scroll_position)

    def _check_scroll_position(self):
        """Check if we should re-enable auto-scroll"""
        import time
        if time.time() - self._last_scroll_time > 0.1:  # 100ms threshold
            try:
                first, last = self.text.yview()
                # Only auto-scroll if we're very close to the bottom
                self._auto_scroll = (last > 0.99)
            except:
                self._auto_scroll = True

    def _on_text_change(self, event=None):
        """Check if we should continue auto-scrolling based on user's scroll position"""
        try:
            first, last = self.text.yview()
            # Only auto-scroll if we're very close to the bottom
            self._auto_scroll = (last > 0.99)
        except:
            self._auto_scroll = True

    def clear_messages(self):
        """Clear all messages from the display"""
        self.text.config(state='normal')
        self.text.delete(1.0, tk.END)
        self.text.config(state='disabled')

    def grid(self, **kwargs):
        """Grid the main content frame"""
        self.content_frame.grid(**kwargs)