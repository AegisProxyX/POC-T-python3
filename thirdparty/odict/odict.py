"""Python 3 compatibility interface for the old bundled ordered dictionary."""
from collections import OrderedDict as _OrderedDict
class OrderedDict(_OrderedDict):
    def iterkeys(self): return iter(self.keys())
    def itervalues(self): return iter(self.values())
    def iteritems(self): return iter(self.items())
    def has_key(self, key): return key in self
