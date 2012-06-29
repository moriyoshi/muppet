from muppet.vcs.git import Git
from muppet.exceptions import MuppetConfigurationError

__all__ = [
    'query_backends'
    ]

available_backends = [
    Git
    ]

def query_backends(settings, variables):
    retval = []
    for backend in available_backends:
        try:
            retval.append(
                backend.from_settings_and_variables(
                    settings, variables))
        except MuppetConfigurationError: 
            pass
    return retval
