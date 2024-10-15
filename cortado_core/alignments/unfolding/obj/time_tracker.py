class TimeTracker:
    def __init__(self):
        self.total_time = 0

    def add_time(self, duration):
        self.total_time += duration

    def get_total_time(self):
        return self.total_time
