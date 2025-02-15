class ThemeColors:
    def __init__(self):
        # Base colors
        base = {
            'bg': '#2e2e2e',
            'fg': '#ffffff',
            'accent': '#0a84ff'
        }

        # Derived colors
        self.colors = {
            **base,
            'bg_darker': '#262626',
            'bg_lighter': '#3a3a3a',
            'fg_dim': '#b0b0b0',
            'selection_bg': '#005fcb',
            'selection_fg': '#ffffff',
            'input_bg': '#3a3a3a',
            'input_fg': base['fg'],
            'accent_hover': '#409cff',
            'error': '#ff3b30',
            'border': '#525252',
            'system_msg': '#0a84ff',
            'broadcast_msg': '#30d158',
            'error_msg': '#ff453a',
            'normal_msg': base['fg'],
            'timestamp': '#8e8e93',
            'highlight': '#ffcc00',
            'status_bg': '#1c1c1e',
            'status_error': '#ff453a',
            'status_success': '#32d74b'
        }

    def __getitem__(self, key):
        return self.colors[key]

    def __contains__(self, key):
        return key in self.colors

    def get(self, key, default=None):
        return self.colors.get(key, default)