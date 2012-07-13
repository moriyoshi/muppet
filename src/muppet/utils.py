from subprocess import Popen, PIPE
from muppet.exceptions import MuppetExternalCommandError
from distutils.spawn import find_executable as _find_executable
import re

def do_cmd(*args, **kwargs):
    p = Popen(args, stdin=None, stdout=PIPE, stderr=PIPE, **kwargs)
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        raise MuppetExternalCommandError(stderr, p.returncode)
    return stdout

def line_by_line(buf):
    for g in re.finditer(r'(?:(?:.*)(?:\r\n|\r|\n)|(?:.+)$)', buf):
        yield g.group(0)

def find_executable(executable):
    return _find_executable(executable)

def traverse_dict(dict, path, default=None):
    retval = dict
    try:
        for comp in path.split('.'):
            retval = retval[comp]
    except KeyError:
        return default
    return retval 

def getuidfor(name):
    from pwd import getpwnam
    pwent = getpwnam(name)
    return pwent.pw_uid

def getgidfor(name):
    from grp import getgrnam
    grent = getgrnam(name)
    return grent.gr_gid
