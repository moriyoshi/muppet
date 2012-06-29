from ConfigParser import RawConfigParser, NoSectionError, NoOptionError
import re

class ConfigWrapper(object):
    def __init__(self, raw_config):
        self.raw_config = raw_config

    def __getitem__(self, key):
        section, option = key.split('.', 1)
        try:
            return self.raw_config.get(section, option)
        except NoSectionError:
            raise KeyError(key)
        except NoOptionError:
            raise KeyError(key)

def config_wrapper_from_file(filenames):
    raw_config = RawConfigParser()
    raw_config.read(filenames)
    return ConfigWrapper(raw_config)

class Settings(object):
    def __init__(self, encoding='utf-8'):
        self.dicts = []
        self.encoding = encoding

    def add(self, dict):
        self.dicts.insert(0, dict)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def _fetch(self, dict, key):
        encoding = self.encoding
        try:
            encoding = dict['muppetrc.encoding']
        except KeyError:
            pass
        return unicode(dict[key], encoding)

    def interpolate(self, value):
        return re.sub(r'\$\{([^}+])\}', lambda g: self.get(g.group(1), ''), value)

    def __getitem__(self, key):
        for dict in self.dicts:
            try:
                return self.interpolate(self._fetch(dict, key))
            except KeyError:
                pass
        raise KeyError(key)
