from importlib.metadata import version


try:
    __version__ = version('bazis-async-background')
except Exception:
    __version__ = 'dev'
