## O2H

🌐 [English](README.md) | [中文](README_zh.md)

将 **O**bsidian .md 转换成 **H**ugo/Zola .md

## 功能

- 链接
  - 自动转换内部链接(笔记、附件、标题/锚)
  - **HTML链接支持**: 处理HTML属性中的链接（`src`, `href`, `data-src` 等）
    - 支持 `<iframe>`, `<img>`, `<a>`, `<video>`, `<audio>` 等HTML标签
    - 示例: `<iframe src="attachments/file.html">` → `<iframe src="/attachments/file.html">`
  - 使用slug格式，自动从 front-matter 中获取或从文件名转换
  - 对无效的内部链接发出警告
  - 自动将视频附件（.mp4, .webm, .ogg）链接转换为HTML video tag

- 文章内链功能 (新增!)
  - **自动交叉引用**: 在前置元数据中定义 `link_words` 字段，自动创建内部链接
  - **智能词匹配**: 支持英文单词边界和中文文本匹配
  - **冲突解决**: 处理重复的链接词，支持优先级系统
  - **避免自链**: 避免链接到当前文章定义的关键词
  - **可配置限制**: 控制每篇文章中每个词的最大链接数（默认：1）
  - **保护现有链接**: 跳过已经是链接的词语

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

# 禁用文章内链功能
python . "Obsidian笔记库路径" "Hugo项目路径" --folders blogs --disable-internal-linking

# 设置每个词的最大链接数
python . "Obsidian笔记库路径" "Hugo项目路径" --folders blogs --internal-link-max 2
```
