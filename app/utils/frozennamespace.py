class FrozenNamespaceMeta(type):
    def __setattr__(self, key, value):
        raise AttributeError("Cannot change attribute of FrozenNamespace.")

    def __delattr__(self, item):
        raise AttributeError("Cannot delete attribute of FrozenNamespace.")


class FrozenNamespace(metaclass=FrozenNamespaceMeta): ...
