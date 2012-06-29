from muppet.exceptions import MuppetException

class Reference(object):
    referenced = None
    id = None
    name = None

class Branch(Reference):
    pass

class Revision(object):
    id = None
    message = None
    parents = None

class VCSBase(object):
    branch = None
    branches = None
    repo_root = None

    def diff(self, rev1, rev2):
        pass

class NoSuchReference(MuppetException):
    pass

class NoSuchRevision(MuppetException):
    pass
