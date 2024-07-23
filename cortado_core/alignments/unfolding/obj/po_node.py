class PONode:
    def __init__(self, label, eid, is_synchronous=False):
        self.eid = eid
        self.label = label
        self.is_synchronous = is_synchronous

    def __str__(self):
        return self.label

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return self.eid == other.eid

    def __hash__(self):
        return hash(self.eid)
