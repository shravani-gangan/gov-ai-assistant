from src.core.config import get_config

config = get_config()

print("App:", config.app_name)
print("Model:", config.ollama.planner_model)
print("Data Dir:", config.data_dir)