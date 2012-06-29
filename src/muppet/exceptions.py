class MuppetException(Exception):
    pass

class MuppetExternalCommandError(MuppetException):
    pass

class MuppetConfigurationError(MuppetException):
    pass

class MuppetPrerequisiteError(MuppetException):
    pass
