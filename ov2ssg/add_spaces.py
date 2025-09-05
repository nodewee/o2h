"""
The code of this module copied from https://github.com/robot527/add-spaces
The copyright belongs to the original author.
"""

"""Add Spaces
Usage:
    add_pass.py <content>
Options:
    -h --help     add blocks between english and chinese
    --version     2.0.
"""
from re import sub

# from docopt import docopt


def is_chinese(uni_ch):
    """判断一个 unicode 是否是汉字。"""
    if (uni_ch >= "\u4e00") and (uni_ch <= "\u9fa5"):
        return True
    else:
        return False


def isdigit(uni_ch):
    """判断一个 unicode 是否是十进制数字。"""
    if (uni_ch >= "\u0030") and (uni_ch <= "\u0039"):
        return True
    else:
        return False


def isalpha(uni_ch):
    """判断一个 unicode 是否是字母。"""
    if (
        (uni_ch >= "\u0041")
        and (uni_ch <= "\u005a")
        or (uni_ch >= "\u0061")
        and (uni_ch <= "\u007a")
    ):
        return True
    else:
        return False


def is_en_symbol(uni_ch):
    """判断一个 unicode 是否是英文符号。"""
    if uni_ch in [
        ":",
        ";",
        "%",
        "!",
        "?",
        "`",
        "°",
        "<",
        "=",
        ">",
        '"',
        "$",
        "&",
        "'",
        ",",
        ".",
        "/",
        "@",
        "\\",
        "^",
        "|",
    ]:
        return True
    else:
        return False


def is_en_l_bracket(uni_ch):
    """判断一个 unicode 是否是英文左括号。"""
    if uni_ch == "(" or uni_ch == "[":
        return True
    else:
        return False


def is_en_r_bracket(uni_ch):
    """判断一个 unicode 是否是英文右括号。"""
    if uni_ch == ")" or uni_ch == "]":
        return True
    else:
        return False


def is_zh_l_bracket(uni_ch):
    """判断一个 unicode 是否是中文左括号。"""
    if uni_ch == "\uff08":
        return True
    else:
        return False


def is_zh_r_bracket(uni_ch):
    """判断一个 unicode 是否是中文右括号。"""
    if uni_ch == "\uff09":
        return True
    else:
        return False


def add_spaces_to_string(string):
    """给字符串添加合理的空格。"""
    newustr = ""
    flag = 0
    ch_lst = list(string)
    length = len(ch_lst)
    for i in range(0, length):
        if i < length - 1:
            # 中文(括号)与英文(括号)之间需要增加空格
            if (is_chinese(string[i]) and isalpha(ch_lst[i + 1])) or (
                isalpha(ch_lst[i]) and is_chinese(ch_lst[i + 1])
            ):
                ch_lst[i] += " "
            elif (isalpha(ch_lst[i]) and is_zh_l_bracket(ch_lst[i + 1])) or (
                is_zh_r_bracket(ch_lst[i]) and isalpha(ch_lst[i + 1])
            ):
                ch_lst[i] += " "
            elif (is_chinese(ch_lst[i]) and is_en_l_bracket(ch_lst[i + 1])) or (
                is_en_r_bracket(ch_lst[i]) and is_chinese(ch_lst[i + 1])
            ):
                ch_lst[i] += " "
            # 中文与英文符号之间需要增加空格
            elif (is_chinese(ch_lst[i]) and is_en_symbol(ch_lst[i + 1])) or (
                is_en_symbol(ch_lst[i]) and is_chinese(ch_lst[i + 1])
            ):
                ch_lst[i] += " "
                flag = 1
            # 中文(括号)与数字之间需要增加空格
            elif (is_chinese(ch_lst[i]) and isdigit(ch_lst[i + 1])) or (
                isdigit(ch_lst[i]) and is_chinese(ch_lst[i + 1])
            ):
                ch_lst[i] += " "
            elif (isdigit(ch_lst[i]) and is_zh_l_bracket(ch_lst[i + 1])) or (
                is_zh_r_bracket(ch_lst[i]) and isdigit(ch_lst[i + 1])
            ):
                ch_lst[i] += " "

        newustr += ch_lst[i]
    newstring = newustr
    # 处理中文里的粗体字和斜体字
    if flag == 1:
        newstring = sub(r"\*", "*", newstring)
        newstring = sub(r" \*\* ", "**", newstring)
        newstring = sub(r"\*\* ", "**", newstring)
        newstring = sub(r" \*\*", "**", newstring)
        newstring = sub("_ ", "_", newstring)
        newstring = sub(" _", "_", newstring)
        newstring = sub("__ ", "__", newstring)
        newstring = sub(" __", "__", newstring)

    return add_space_betw_digit_and_unit(newstring)


def add_space_betw_digit_and_unit(string):
    # todo markdown image url user hash uuid like units in it. will create blanck newline in. makes wrong
    #    """给数字与单位之间增加空格。"""
    #    from re import sub
    #    # 常用单位，不齐全
    #    units = ['bps', 'Kbps', 'Mbps', 'Gbps',
    #             'B', 'KB', 'MB', 'GB', 'TB', 'PB',
    #             'g', 'Kg', 't',
    #             'h', 'm', 's']
    #    for unit in units:
    #        pattern = r'(?<=\d)' + unit  # positive lookbehind assertion,
    #        # 如果前面是括号中 '=' 后面的字符串，则匹配成功
    #        repl = ' ' + unit
    #        string = sub(pattern, repl, string)
    return string


def add_spaces_to_content(content):
    return add_spaces_to_string(content)


# def main():
#     args = docopt(__doc__, version="add-spaces 2.0")
#     kwargs = {
#         "content": args["<content>"],
#     }
#     result = add_spaces_to_content(**kwargs)
#     return result


# if __name__ == "__main__":
#     r = main()
#     print(r)
