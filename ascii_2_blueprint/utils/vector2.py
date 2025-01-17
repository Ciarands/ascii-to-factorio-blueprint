class Vector2:
    x: float
    y: float

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
    
    def __mul__(self, vector):
        return Vector2(self.x * vector.x, self.y * vector.y)

    def __add__(self, vector):
        return Vector2(self.x + vector.x, self.y + vector.y)

    def __repr__(self):
        return f"Vector2({self.x},{self.y})"

    @property
    def as_dict(self):
        return {"x": self.x, "y": self.y}