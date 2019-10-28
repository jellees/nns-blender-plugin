from mathutils import Vector


def float_to_fx32(value):
    return int(round(value * 4096))


def fx32_to_float(value):
    return float(value) / 4096


def float_to_fx10(value):
    return max(min(int(round(value * 512)), 511), -512)


def fx10_to_float(value):
    return float(value) / 512


def normal_to_vecfx10(vector):
    return Vecfx10([
        float_to_fx10(vector.y),
        float_to_fx10(vector.z),
        float_to_fx10(vector.x),
    ])


class Vecfx10():
    def __init__(self, vector=[0, 0, 0]):
        self.x = vector[0]
        self.y = vector[1]
        self.z = vector[2]

    def to_vector(self):
        return Vector([
            fx10_to_float(self.x),
            fx10_to_float(self.y),
            fx10_to_float(self.z),
        ])

    def __eq__(self, other):
        return (
            self.x == other.x
            and self.y == other.y
            and self.z == other.z
        )


class VecFx32(object):
    def __init__(self, vector=[0, 0, 0]):
        self.x = vector[0]
        self.y = vector[1]
        self.z = vector[2]

    def from_floats(self, floats):
        return VecFx32([
            float_to_fx32(floats[0]),
            float_to_fx32(floats[1]),
            float_to_fx32(floats[2])
        ])

    def from_vector(self, vector):
        return VecFx32([
            float_to_fx32(vector.x),
            float_to_fx32(vector.y),
            float_to_fx32(vector.z)
        ])

    def to_vector(self):
        return Vector([
            fx32_to_float(self.x),
            fx32_to_float(self.y),
            fx32_to_float(self.z),
        ])

    def __str__(self):
        return str(self.x), str(self.y), str(self.z)

    def __sub__(self, other):
        if isinstance(other, self.__class__):
            return VecFx32([
                self.x - other.x,
                self.y - other.y,
                self.z - other.z
            ])
        elif isinstance(other, int):
            return VecFx32([
                self.x - other,
                self.y - other,
                self.z - other
            ])
        else:
            raise TypeError(
                "unsupported operand type(s) for -: '{}' and '{}'"
            ).format(self.__class__, type(other))

    def __rshift__(self, other):
        if isinstance(other, self.__class__):
            return VecFx32([
                self.x >> other.x,
                self.y >> other.y,
                self.z >> other.z
            ])
        elif isinstance(other, int):
            return VecFx32([
                self.x >> other,
                self.y >> other,
                self.z >> other
            ])
        else:
            raise TypeError(
                "unsupported operand type(s) for >>: '{}' and '{}'"
            ).format(self.__class__, type(other))

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.x < other.x and
                self.y < other.y and
                self.z < other.z
            )
        elif isinstance(other, int):
            return (
                self.x < other and
                self.y < other and
                self.z < other
            )
        else:
            raise TypeError(
                "unsupported operand type(s) for <: '{}' and '{}'"
            ).format(self.__class__, type(other))

    def __eq__(self, other):
        return (
            self.x == other.x
            and self.y == other.y
            and self.z == other.z
        )