## O2H

🌐 [English](README.md) | [中文](README_zh.md)

将 **O**bsidian .md 转换成 **H**ugo/Zola .md

## 功能

- 链接
  - 自动转换内部链接(笔记、附件、标题/锚)
  - 使用slug格式，自动从 front-matter 中获取或从文件名转换
  - 对无效的内部链接发出警告
  - 自动将视频附件（.mp4, .webm, .ogg）链接转换为HTML video tag

- 文件夹
  - 默认转换笔记库中的所有文件夹（自动排除模板文件夹）
  - 可指定一个或多个文件夹
  - 可选择是否清空目标文件夹（保留 "_index.*" 文件）

- 发布的日期/时间
  - 首先从 front-matter 中查找指定值，如果没有找到，
  - 使用笔记文件(.md)的创建时间和最后修改时间

- 语言支持
  - 如果前置元数据中包含 `lang` 字段，将在生成的文件名中添加语言后缀
  - 例如：具有 `lang: "zh"` 和 slug `abc-efg` 的文章将生成 `abc-efg.zh.md`

- 前置元数据（Frontmatter）
  - 支持 YAML 和 TOML 格式
  - YAML 格式（默认）- 兼容 Hugo SSG
  - TOML 格式 - 兼容 Zola SSG
  - 使用 `--frontmatter-format` 参数指定格式

- 静态站点生成器兼容性
  - **Hugo SSG**: 使用 YAML 前置元数据格式（默认）
  - **Zola SSG**: 使用 TOML 前置元数据格式

## 用法

```sh
git clone https://github.com/nodewee/o2h.git
cd o2h
pdm install
# 或者 pip install -r requirements.txt
python . --help
```

### 示例

```sh
# 转换笔记给 Hugo SSG 使用（YAML 格式的前置元数据 - 默认）
python . "Obsidian笔记库路径" "Hugo项目路径" --folders blogs

# 转换笔记给 Zola SSG 使用（TOML 格式的前置元数据）
python . "Obsidian笔记库路径" "Zola项目路径" --folders blogs --frontmatter-format toml

# 转换指定文件夹并自定义映射关系
python . "Obsidian笔记库路径" "Hugo项目路径" --folders "blogs>posts notes>articles"
```
