## O2H

🌐 [English](README.md) | [中文](README_zh.md)

将 **O**bsidian .md 转换成 **H**ugo .md

## 功能

- 链接
  - 自动转换内部链接为网站相对链接(笔记，附件)
  - 使用slug格式，从笔记的 front-matter 中获取slug或从标题中自动生成
  - 对无效的内部链接发出警告
  - 自动转换视频附件（.mp4, .webm, .ogg）链接为HTML video tag

- 文件夹
  - 默认情况下，转换笔记库中的所有文件夹（不包括模板文件夹）
  - 或指定一个或多个文件夹

- 发布的日期/时间
  - 先使用前面指定的日期/时间
  - 或者使用笔记文件(.md)的创建时间和最后修改时间

## 用法

```sh
git clone https://github.com/nodewee/o2h.git
cd o2h
pdm install
# 或者 pip install -r requirements.txt
python . --help
```
