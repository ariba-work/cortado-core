import functools


class Configuration(set):
    def __init__(self, events=None, total_cost=None):
        super().__init__()
        self._events = set() if events is None else events
        self._total_cost = 0 if total_cost is None else total_cost

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

    def __lt__(self, other):
        return self.total_cost < other.total_cost
        # TODO: breaking ties options - 1. ERV Foata Normal Forms, 2. Dijkstra's style parent search tuple

    def __str__(self):
        return f"move cost:{self.total_cost}"
