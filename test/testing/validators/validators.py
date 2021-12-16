from testing.shared.common import sorted_dict


def val1(d1):
    def f(key, d2):
        return f"1, {key}, {sorted_dict(d1)}, {sorted_dict(d2)}"

    return f


def val2(d1):
    def f(key, d2):
        return f"2, {key}, {sorted_dict(d1)}, {sorted_dict(d2)}"

    return f


def fail_val(d):
    raise ValueError("we've no functions 'ere")


def pval1(d1):
    def f(prefix, key, d2):
        return f"1, {prefix}, {key}, {sorted_dict(d1)}, {sorted_dict(d2)}"

    return f


def pval2(d1):
    def f(prefix, key, d2):
        return f"2, {prefix}, {key}, {sorted_dict(d1)}, {sorted_dict(d2)}"

    return f


def fail_prefix_val(d):
    raise ValueError("we've no prefix functions 'ere")
