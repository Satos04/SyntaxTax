def simple():
    pass


def medium(x, items):
    if x > 0:
        for item in items:
            print(item)
    elif x == 0:
        return 0


def complex(x, items):
    result = 0
    for i in items:
        if i > 0:
            result += i
        elif i < 0:
            while result > 0:
                result -= 1
        else:
            try:
                result += 1
            except ValueError:
                pass
            except TypeError:
                pass
    return result
