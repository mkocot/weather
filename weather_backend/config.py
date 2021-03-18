import toml

def load_config(path:str):
    with open(path) as f:
        return toml.load(f)