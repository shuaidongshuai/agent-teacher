"""工具函数模块。"""


def format_number(value, decimals=2):
    """格式化数字为指定小数位。"""
    return round(value, decimals)


def is_numeric(value):
    """检查值是否为数字类型。"""
    return isinstance(value, (int, float))


def safe_divide(a, b, default=0):
    """安全除法，除零时返回默认值。"""
    if b == 0:
        return default
    return a / b
