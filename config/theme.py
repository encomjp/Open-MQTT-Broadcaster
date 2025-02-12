class ThemeColors:
    def __init__(self):
        # Base colors
        base = {
            'bg': '#1e1e1e',
            'fg': '#e0e0e0',
            'accent': '#0078d4'
        }

        # Derived colors
        self.colors = {
            **base,
            'bg_darker': '#181818',
            'bg_lighter': '#2d2d2d',
            'fg_dim': '#a0a0a0',
            'selection_bg': '#264f78',
            'selection_fg': '#ffffff',
            'input_bg': '#2d2d2d',
            'input_fg': base['fg'],
            'accent_hover': '#1b96ff',
            'error': '#f14c4c',
            'border': '#404040',
            'system_msg': '#00b7ff',
            'broadcast_msg': '#00ff9d',
            'error_msg': '#ff5555',
            'normal_msg': base['fg'],
            'timestamp': '#707070',
            'highlight': '#ffcb6b',
            'status_bg': '#264f78',
            'status_error': '#ff3333',
            'status_success': '#00cc66'
        }

    def __getitem__(self, key):
        return self.colors[key]

    def __contains__(self, key):
        return key in self.colors

    def get(self, key, default=None):
        return self.colors.get(key, default)