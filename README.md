# EhTag统计工具

## 项目简介

EhTag统计工具是一个用于统计和分析E-Hentai/ExHentai收藏夹中标签（Tag）使用情况的Python脚本。通过抓取用户的收藏夹数据，计算不同标签的加权权重，并生成可视化图表和CSV统计文件，帮助用户深入了解自己的收藏偏好。

## 功能特性

- **自动抓取数据**：从E-Hentai/ExHentai收藏夹自动抓取漫画信息，包括类型、页数和标签。
- **智能权重计算**：根据漫画类型和页数计算权重，避免页数少的漫画权重过低。
- **多文件夹支持**：支持选择特定收藏文件夹进行统计。
- **标签分类统计**：按Namespace（如female、artist、group等）分别统计标签权重。
- **可视化输出**：生成水平柱状图表，直观展示前N个标签。
- **缓存机制**：支持数据缓存，避免重复抓取。
- **重试机制**：自动处理网络请求失败，支持404重试。

## 安装要求

- **Python版本**：Python 3.6+
- **依赖库**：
  - requests
  - beautifulsoup4
  - matplotlib

### 安装步骤

1. 克隆或下载项目文件到本地。
2. 安装依赖库：
   ```bash
   pip install requests beautifulsoup4 matplotlib
   ```
3. 确保Python环境配置正确。

## 使用方法

### 1. 配置脚本

下载并打开 `EhTag_Pub.py` 文件，修改配置区中的变量：

#### 必需配置

- **USER_AGENT**：浏览器User-Agent字符串，通常无需修改。
- **USER_COOKIE**：E-Hentai/ExHentai的登录Cookie。必须包含 `igneous`、`ipb_member_id`、`ipb_pass_hash` 等字段。
  - 获取方法：登录网站后，按F12打开开发者工具，刷新页面，在"应用程序" > "Cookie"中复制相关值。

#### 可选配置

- **PAGE_BASIC_RATIO**：基础页面权重系数（默认30.0）。
- **CATEGORY_WEIGHTS**：不同漫画类型的页数权重配置。
- **SELECTED_FAVORITE_FOLDERS**：需要统计的收藏文件夹ID列表（留空统计所有）。
- **TARGET_NAMESPACES**：需要统计的标签分类列表。
- **TOP_N_CONFIG**：每个Namespace展示的Top标签数量。
- **DELAY_BETWEEN_PAGES** / **DELAY_BETWEEN_GALLERIES**：请求延迟设置。
- **MAX_RETRIES** / **RETRY_DELAY**：重试设置。

### 2. 运行脚本

在命令行中运行：
```bash
python EhTag_Pub.py
```

脚本会自动检查缓存文件，如果不存在则开始抓取数据，否则直接使用缓存。

### 3. 查看结果

运行完成后，在 `outputs/` 目录下查看：
- `eh_favorites_cache.json`：抓取的原始数据缓存。
- `stats_*.csv`：各Namespace的标签统计CSV文件。
- `chart_*.png`：可视化图表文件。

## 输出文件说明

- **缓存文件**：`eh_favorites_cache.json` - 包含所有抓取的漫画详细信息。
- **统计CSV**：`stats_{namespace}.csv` - 各标签的加权分数，按分数降序排列。
- **图表文件**：`chart_{namespace}.png` - Top标签的水平柱状图。

## 注意事项

1. **Cookie安全**：请妥善保管Cookie信息，不要在公共场合分享。
2. **网络请求**：脚本会发送大量请求，请遵守网站使用条款，避免过度频繁访问。
3. **延迟设置**：适当调整请求延迟，避免被服务器封禁。
4. **数据隐私**：所有数据仅本地处理，不上传到任何服务器。
5. **兼容性**：主要针对E-Hentai/ExHentai的页面结构，如网站改版不保证可用性。
6. **错误处理**：遇到网络问题时，脚本会自动重试，请耐心等待。

## 权重计算逻辑

- **漫画总权重** = 基础权重 + (页数 × 类型权重系数)
- **标签权重分配**：总权重平均分配给该Namespace下的所有标签

## 故障排除

- **无法访问网站**：检查Cookie是否正确、网络连接是否正常。
- **404**：该画廊可能已下架，或请求速度过快。
- **图表显示异常**：确保matplotlib和中文字体正确安装。

## 许可证

本项目仅供学习和个人使用，请遵守相关法律法规。
