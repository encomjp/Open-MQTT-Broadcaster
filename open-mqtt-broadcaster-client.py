import tkinter as tk
import traceback
import sys
import logging
from gui.main_window import MQTTBroadcaster

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mqtt_broadcaster')

def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Handle keyboard interrupt specially
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))

def main():
    try:
        # Set exception hook
        sys.excepthook = handle_exception
        
        # Create and configure root window
        root = tk.Tk()
        root.configure(bg='#1e1e1e')
        
        # Report Python version and thread info
        logger.info(f"Python version: {sys.version}")
        logger.info("Initializing application...")
        
        try:
            root.tk.call('::tk::unsupported::MacWindowStyle', 'dark', root)
        except tk.TclError:
            pass
        
        # Initialize main application with error handling
        try:
            app = MQTTBroadcaster(root)
            logger.info("Application initialized successfully")
            root.mainloop()
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}", exc_info=True)
            raise
            
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        try:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Critical Error", 
                f"Application failed to start:\n{str(e)}\n\nCheck logs for details.")
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()