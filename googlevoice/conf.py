try:
    from ConfigParser import ConfigParser as configparser, NoOptionError
except ImportError:
    from configparser import ConfigParser, NoOptionError 
import os
import settings


class Config(ConfigParser):
    """
    ``ConfigParser`` subclass that looks into your home folder for a file named
    ``.gvoice`` and parses configuration data from it.
    """
    def __init__(self):
        self.fname = os.path.expanduser('~/.gvoice')

        if not os.path.exists(self.fname):
            try:
                with open(self.fname, 'w') as f:
                    f.write(settings.DEFAULT_CONFIG)
            except IOError:
                return

        ConfigParser.__init__(self)

        try:
            self.read([self.fname])
        except IOError:
            return

    def _get(self, option, section='gvoice', **kwargs):
        try:
            #return ConfigParser.get(self, section, option).strip() or None
            return self.get(section, option).strip() or None
        except NoOptionError:
            return

    def set(self, option, value, section='gvoice', **kwargs):
        return ConfigParser.set(self, section, option, value)

    def phoneType(self):
        try:
            return int(self.get('phoneType'))
        except TypeError:
            return

    def save(self):
        with open(self.f, 'w') as f:
            f.write(f)

    phoneType = property(phoneType)
    forwardingNumber = property(lambda self: self._get('forwardingNumber'))
    email = property(lambda self: self._get('email', 'auth'))
    password = property(lambda self: self._get('password', 'auth'))
    MFAKey = property(lambda self: self._get('MFAKey', 'auth'))

config = Config()
