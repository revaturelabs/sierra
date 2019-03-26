"""Utilities for Sierra

"""


class AttrDict(dict):

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(f"AttrDict object has no attribute '{attr}'")

    def __setattr__(self, attr, value):
        self[attr] = value
