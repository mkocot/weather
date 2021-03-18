import toml

def load_config(path:str) -> dict:
    with open(path) as f:
        return toml.load(f)