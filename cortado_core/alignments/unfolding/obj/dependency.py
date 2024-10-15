class Dependency:
    def __init__(self, source, target, is_followed, connects_sync_moves):
        self.source = source
        self.target = target
        self.is_followed = is_followed
        self.connects_sync_moves = connects_sync_moves

    def __eq__(self, other):
        return self.source == other.source and self.target == other.target and self.is_followed == other.is_followed and self.connects_sync_moves == other.connects_sync_moves

    def __hash__(self):
        return hash((self.source, self.target, self.is_followed, self.connects_sync_moves))

    def serialize(self):
        return {
            "source": self.source,
            "target": self.target,
            "is_followed": self.is_followed,
            "connects_sync_moves": self.connects_sync_moves,
        }
