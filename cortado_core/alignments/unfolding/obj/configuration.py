import functools

class Configuration(set):
    def __init__(self, events=None, total_cost=None, h=None):
        super().__init__()
        self._events = set() if events is None else events
        self._total_cost = 0 if total_cost is None else total_cost
        self._h = 0 if h is None else h # heuristic value

    @property
    def events(self):
        return self._events

    @events.setter
    def events(self, value):
        self._events = value

    @property
    def total_cost(self):
        return functools.reduce(
            lambda x1, x2: x1 + x2, map(lambda x: x.cost, self.events), 0
        )

    @total_cost.setter
    def total_cost(self, value):
        self._total_cost = value

    @property
    def h(self):
        return self._h

    @h.setter
    def h(self, value):
        self._h = value

    def compute_and_compare_parikh_vector(self, other):
        pv1 = sorted(list(map(lambda e: e.mapped_transition, self.events)))
        pv2 = sorted(list(map(lambda e: e.mapped_transition, other.events)))
        return pv1 < pv2

    def __lt__(self, other):

        self_f = self.total_cost + self.h
        other_f = other.total_cost + other.h

        if self_f != other_f:
            return self_f < other_f

        if self.total_cost != other.total_cost:
            return self.total_cost < other.total_cost

        if len(self.events) != len(other.events):
            return len(self.events) < len(other.events)

        return self.compute_and_compare_parikh_vector(other)

    def __str__(self):
        return f"move cost:{self.total_cost}"
