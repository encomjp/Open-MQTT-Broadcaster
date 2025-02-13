import os
import importlib
import logging

logger = logging.getLogger("module_loader")


def load_all_modules():
    """
    Dynamically load all modules in the modules directory (excluding __init__.py and module_loader.py).
    Returns:
        dict: A dictionary where keys are module names (filename without extension) and values are the imported module.
    """
    modules = {}
    module_dir = os.path.dirname(__file__)
    for filename in os.listdir(module_dir):
        if filename.endswith(".py") and filename not in ("__init__.py", "module_loader.py"):
            module_name = filename[:-3]
            try:
                module = importlib.import_module(f"modules.{module_name}")
                modules[module_name] = module
                logger.info(f"Loaded module: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load module {module_name}: {e}")
    return modules 