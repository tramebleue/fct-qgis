import os

def model_filename(script_file):
    return os.path.join(
        os.path.dirname(script_file),
        os.path.basename(script_file).replace('.pyc','.py').replace('.py', '.model'))