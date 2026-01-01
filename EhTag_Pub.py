import os
import time
import json
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
import matplotlib.pyplot as plt

# ==============================================================================
# 第一部分：普通用户配置区
# 请根据您的实际情况修改以下变量
# 普通用户只需要修改这一部分,其余代码不建议改动
# ==============================================================================

# 1. 浏览器身份标识 (User-Agent)
# 用于伪装成浏览器，避免被服务器拒绝。通常不需要修改，除非请求失败。
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# 2. 网站 Cookie (必须填写)
# 请登录 E-Hentai/ExHentai 后，按 F12 打开开发者工具，刷新页面，在“应用程序”中找到 Cookie 并复制，替换下文的xxx。
# 必须包含 'igneous', 'ipb_member_id', 'ipb_pass_hash' 等关键字段。
USER_COOKIE = "igneous=xxx; ipb_member_id=xxx; ipb_pass_hash=xxx;"


# 3. 收藏夹首页 URL
# 你想要抓取的收藏夹起始页面。
# 如果是 E-Hentai 表站，通常是 https://e-hentai.org/favorites.php
# 如果是 ExHentai 里站，通常是 https://exhentai.org/favorites.php
FAVORITES_URL = "https://exhentai.org/favorites.php"


# 页面权重计算方法：单个漫画的总权重 = 基础页面权重系数 + 页数 * 对应漫画类型页数权重
# （total = PAGE_BASIC_RATIO + page * CATEGORY_WEIGHTS）
# 4. 基础页面权重系数 (PAGE_BASIC_RATIO) 默认30.0
# 每一本漫画的基础得分。无论页数多少，都会先获得这个分数。
# 作用：防止页数极少的漫画权重过低。
PAGE_BASIC_RATIO = 30.0

# 5. 不同漫画类型的页数权重配置
# 此处定义不同类型的漫画，每一页相当于多少"分数"。
# 例如：同人志(Doujinshi)页数少但信息密度高，权重可以设高一点。
# 单行本(Manga)页数多，为了不让它统治统计结果，权重可以设低一点。
CATEGORY_WEIGHTS = {
    "Doujinshi": 1.0,  # 同人志 - 每一页贡献 1.0 分
    "Manga": 0.3,  # 漫画 - 每一页贡献 0.3 分
    "Artist CG": 0.1,  # 画师CG - 每一页贡献 0.1 分
    "Game CG": 0.1,  # 游戏CG - 每一页贡献 0.1 分
    "Western": 0.3,  # 西方
    "Non-H": 0.3,  # 非H
    "Image Set": 0.1,  # 图集
    "Cosplay": 0.2,
    "Asian Porn": 0.2,  # 亚洲
    "Misc": 0.2,  # 杂项
}

# 默认权重 (如果遇到了上面没写且未知的类型)
DEFAULT_PAGE_WEIGHT = 0.2


# 6. 缓存文件保存路径 (无必要可以不修改)
# 所有读写文件都放到程序所在目录下的 outputs 子目录
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")

# 抓取下来的数据会保存在这个文件中。只要这个文件存在，程序就不会再联网。
CACHE_FILE_PATH = os.path.join(OUTPUTS_DIR, "eh_favorites_cache.json")


# 7. 需要参与统计的收藏文件夹 ID 列表
# 只有在这个列表中的文件夹，其中的漫画才会被统计和分析
# 例如：[0, 1, 2] 表示只统计第 0、1、2 号收藏文件夹
# 如果留空 []，则统计所有文件夹
# 收藏文件夹 ID 从 0 开始编号（第一个文件夹是 0，第二个是 1，以此类推）
SELECTED_FAVORITE_FOLDERS = [0, 8, 9]  # 示例：[0, 2] 只统计第1个和第3个文件夹


# tag权重分配逻辑：将该漫画的总权重平均分配给该 namespace 下的所有 tag
# 例如 某漫画有总权重100，其中有5个female标签，那么其中每个female标签获得权重 20 = 100 / 5
# 8. 需要统计的 Namespace (标签分类) 列表
# 你希望统计哪些类型的标签？
# 常见的有：female(女性标签), male(男性标签), parody(原作), character(角色), group(社团), artist(画师)
TARGET_NAMESPACES = [
    "female",
    "artist",
    "group",
    "other",
    "mixed",
    "character",
    "parody",
]


# 9. 每个 Namespace 对应的图表展示数量
# 例如 'female': 30 表示女性标签只统计并展示前 30 名。
TOP_N_CONFIG = {
    "female": 30,
    "male": 15,
    "mixed": 15,
    "parody": 15,
    "character": 20,
    "artist": 20,
    "group": 20,
    "other": 20,
}

# 默认TOP_N (如果遇到了上面没配置的 Namespace)
DEFAULT_TOP_N = 10


# 10. 请求延迟设置（秒）
# 为避免请求过快导致 404 或被封禁，建议设置一定延迟
DELAY_BETWEEN_PAGES = 1.0  # 收藏夹翻页之间的延迟（秒）
DELAY_BETWEEN_GALLERIES = 0.1  # 抓取每个漫画详情页之间的延迟（秒）


# 11. 遇到 404 时的重试设置
MAX_RETRIES = 3  # 遇到 404 时的最大重试次数
RETRY_DELAY = 10.0  # 重试前的等待时间（秒），遇到 404 时等待更长时间


# ==============================================================================
# 配置区结束，普通用户无需修改以下代码
# ==============================================================================


def get_headers():
    """
    生成请求头，包含 User-Agent 和 用户填写的 Cookie
    """
    return {"User-Agent": USER_AGENT, "Cookie": USER_COOKIE}


def ensure_outputs_dir():
    """
    确保 OUTPUTS_DIR 目录存在
    """
    try:
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
    except Exception:
        pass


def parse_page_count(text):
    """
    辅助函数：从文本中提取页数数字。
    例如输入 "61 页" 或 "61 pages"，返回整数 61。
    """
    try:
        # 分割字符串，寻找数字
        parts = text.split()
        for part in parts:
            # 去除可能的标点符号
            clean_part = part.strip().replace(",", "").replace(".", "")
            if clean_part.isdigit():
                return int(clean_part)
        return 0
    except:
        return 0


def scrape_gallery_detail(session, gallery_url, folder_id):
    """
    抓取单本漫画的详情页信息，带有重试机制
    参数：
        session: requests.Session 对象
        gallery_url: 漫画详情页 URL
        folder_id: 该漫画所属的收藏文件夹 ID
    返回：
        包含漫画信息的字典，或 None（如果抓取失败）
    """
    print(f"  正在抓取详情: {gallery_url}")

    # 重试机制：遇到 404 时自动重试
    for attempt in range(MAX_RETRIES):
        try:
            # 发送请求获取详情页
            response = session.get(gallery_url, headers=get_headers(), timeout=20)

            # # 如果遇到 404，进行重试 (并入下方)
            # if response.status_code == 404:
            #     if attempt < MAX_RETRIES - 1:
            #         print(
            #             f"    请求返回 404，第 {attempt + 1} 次重试，等待 {RETRY_DELAY} 秒后重试..."
            #         )
            #         time.sleep(RETRY_DELAY)
            #         continue
            #     else:
            #         print(f"    请求失败，状态码: 404，已达最大重试次数，跳过该图库")
            #         return None

            # 如果状态码不是 200，也视为失败
            if response.status_code != 200:
                if attempt < MAX_RETRIES - 1:
                    print(
                        f"    请求返回 {response.status_code}，第 {attempt + 1} 次重试，等待 {RETRY_DELAY} 秒后重试..."
                    )
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    print(
                        f"    请求失败，状态码: {response.status_code}，已达最大重试次数，跳过该图库"
                    )
                    return None

            # 请求成功，开始解析页面
            soup = BeautifulSoup(response.text, "html.parser")

            # 1. 提取漫画类型 (Category)
            # 在详情页中，类别显示在 id="gdc" 的 div 下的第一个带有 class="cs ct*" 的 div 中
            category = "杂志"  # 默认值
            gdc_div = soup.find("div", id="gdc")
            if gdc_div:
                cat_div = gdc_div.find("div", class_=lambda x: x and "cs ct" in x)
                if cat_div:
                    category = cat_div.text.strip()

            # 2. 提取页数 (Page Count)
            # 页数在 id="gdd" 的表格中，寻找包含 '页数' 或 'Length' 的行
            page_count = 0
            gdd_div = soup.find("div", id="gdd")
            if gdd_div:
                # 查找所有表格行
                rows = gdd_div.find_all("tr")
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 2:
                        first_col = cols[0].text.strip()
                        if "Length" in first_col:
                            page_count = parse_page_count(cols[1].text)
                            break

            # 3. 提取标签 (Tags)
            # 标签位于 id="taglist" 的 div 中
            # 格式: {'female': ['tag1', 'tag2'], 'male': [...]}
            tags_data = {}

            taglist_div = soup.find("div", id="taglist")
            if taglist_div:
                # 遍历每一个标签行 (每一行是一个 namespace)
                tag_rows = taglist_div.find_all("tr")
                for row in tag_rows:
                    cols = row.find_all("td")
                    if len(cols) >= 2:
                        # 获取 namespace 名称
                        # 在ExHentai中，第一列可能是中文（如"女性:"）或英文（如"female:"）
                        namespace_td = cols[0]
                        namespace_text = namespace_td.text.strip().replace(":", "")

                        # 尝试从 class 属性获取更准确的 namespace
                        # 通过查看第二列中的标签链接来推断 namespace
                        tag_divs = cols[1].find_all("div", class_=["gt", "gtl", "gtw"])
                        if not tag_divs:
                            continue

                        # 从第一个标签的链接中提取 namespace
                        first_tag_link = tag_divs[0].find("a")
                        if not first_tag_link:
                            continue

                        href = first_tag_link.get("href", "")
                        # URL 格式: /tag/namespace:tagname
                        if "/tag/" in href:
                            tag_part = href.split("/tag/")[-1]
                            if ":" in tag_part:
                                namespace = tag_part.split(":")[0].strip()
                            else:
                                # 对于没有冒号的标签（如language, parody等）
                                # 需要特殊处理
                                namespace = "tag"
                        else:
                            namespace = "tag"

                        # 获取该 namespace 下的所有 tag
                        tags_in_row = []
                        for tag_div in tag_divs:
                            tag_link = tag_div.find("a")
                            if tag_link:
                                # 从 ehs-tag 属性获取英文标签名（更准确）
                                tag_name = tag_link.get("ehs-tag", "")
                                if not tag_name:
                                    # 如果没有 ehs-tag，从 href 中提取
                                    tag_href = tag_link.get("href", "")
                                    if "/tag/" in tag_href:
                                        tag_full = tag_href.split("/tag/")[-1]
                                        if ":" in tag_full:
                                            tag_name = tag_full.split(":", 1)[1]
                                        else:
                                            tag_name = tag_full
                                    else:
                                        # 最后的备选方案：使用显示文本
                                        tag_name = tag_link.text.strip()

                                # 清理标签名称：去除可能的前缀（如 "f:", "m:"）
                                if ":" in tag_name and len(tag_name.split(":")) == 2:
                                    tag_name = tag_name.split(":", 1)[1].strip()

                                if tag_name:
                                    tags_in_row.append(tag_name)

                        if tags_in_row:
                            tags_data[namespace] = tags_in_row

            # 返回包含所有信息的字典，包括所属文件夹 ID
            return {
                "url": gallery_url,
                "folder_id": folder_id,
                "category": category,
                "pages": page_count,
                "tags": tags_data,
            }

        except Exception as e:
            print(f"    抓取详情页出错: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"    第 {attempt + 1} 次重试，等待 {RETRY_DELAY} 秒...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"    已达最大重试次数，跳过该图库")
                return None

    return None


def run_spider_process():
    """
    执行完整的网页抓取流程
    会遍历所有收藏文件夹的所有分页，抓取每个漫画的详细信息
    """
    print(">>> 开始执行网页抓取流程...")
    print(
        f"请求延迟设置：翻页间隔 {DELAY_BETWEEN_PAGES} 秒，详情页间隔 {DELAY_BETWEEN_GALLERIES} 秒"
    )
    print(f"404 重试设置：最多重试 {MAX_RETRIES} 次，每次等待 {RETRY_DELAY} 秒\n")

    session = requests.Session()
    all_galleries = []

    # 第一步：获取所有收藏文件夹列表
    print("正在获取收藏文件夹列表...")
    try:
        res = session.get(FAVORITES_URL, headers=get_headers(), timeout=20)
        if res.status_code != 200:
            print(f"无法访问收藏夹首页，状态码: {res.status_code}")
            return

        soup = BeautifulSoup(res.text, "html.parser")

        # 查找所有收藏文件夹
        # 根据HTML，文件夹在 <div class="fp"> 元素中
        favorite_folders = []
        fp_divs = soup.find_all("div", class_="fp")

        for fp_div in fp_divs:
            # 从 onclick 属性中提取文件夹 ID
            onclick = fp_div.get("onclick", "")
            if "favcat=" in onclick:
                # 提取 favcat 参数值
                # 格式: document.location='https://exhentai.org/favorites.php?favcat=0'
                try:
                    favcat_part = onclick.split("favcat=")[1]
                    folder_id = int(favcat_part.split("'")[0])

                    # 提取文件夹名称（在最后一个子 div 的文本中）
                    text_divs = fp_div.find_all("div")
                    folder_name = "未命名"
                    if text_divs:
                        # 最后一个 div 通常包含文件夹名称
                        for div in reversed(text_divs):
                            text = div.text.strip()
                            # 跳过数字（收藏数量）
                            if text and not text.isdigit():
                                folder_name = text
                                break

                    favorite_folders.append({"id": folder_id, "name": folder_name})
                    print(f"  发现收藏文件夹 [{folder_id}]: {folder_name}")
                except:
                    continue

        if not favorite_folders:
            print("未找到任何收藏文件夹，可能是页面结构变化或 Cookie 失效")
            return

        # 按 ID 排序
        favorite_folders.sort(key=lambda x: x["id"])

    except Exception as e:
        print(f"获取收藏文件夹列表失败: {e}")
        return

    # 第二步：遍历每个收藏文件夹
    for folder in favorite_folders:
        folder_id = folder["id"]
        folder_name = folder["name"]

        print(f"\n{'=' * 60}")
        print(f"开始抓取收藏文件夹 [{folder_id}]: {folder_name}")
        print(f"{'=' * 60}")

        # 构造该文件夹的 URL（通过 favcat 参数指定文件夹）
        folder_url = f"{FAVORITES_URL}?favcat={folder_id}"
        current_url = folder_url
        has_next_page = True
        page_index = 1

        # 第三步：遍历该文件夹的所有分页
        while has_next_page:
            print(f"\n正在读取第 {page_index} 页...")

            try:
                res = session.get(current_url, headers=get_headers(), timeout=20)
                if res.status_code != 200:
                    print(f"  页面访问失败，状态码: {res.status_code}，跳过该页")
                    break

                soup = BeautifulSoup(res.text, "html.parser")

                # 查找漫画列表表格
                # 根据HTML，收藏列表在 <table class="itg gltc"> 或 <table class="itg glte"> 中
                table = soup.find("table", class_=lambda x: x and "itg" in x)
                if not table:
                    print("  未找到收藏列表表格，可能已到达末尾或出现错误")
                    break

                # 第四步：提取本页所有漫画链接
                rows = table.find_all("tr")
                page_gallery_links = []

                for row in rows:
                    # 跳过表头行
                    if row.find("th"):
                        continue

                    # 查找包含图库链接的单元格（class="gl3c glname"）
                    name_cell = row.find("td", class_="gl3c")
                    if name_cell:
                        link = name_cell.find("a")
                        if link:
                            href = link.get("href", "")
                            # 只提取漫画详情页链接（格式：/g/{id}/{token}/）
                            if "/g/" in href:
                                page_gallery_links.append(href)

                print(f"  本页发现 {len(page_gallery_links)} 个图库")

                # 第五步：逐个抓取漫画详情
                success_count = 0
                for idx, link in enumerate(page_gallery_links, 1):
                    print(f"  [{idx}/{len(page_gallery_links)}]", end=" ")

                    # 抓取详情页，传入文件夹 ID
                    gallery_data = scrape_gallery_detail(session, link, folder_id)
                    if gallery_data:
                        all_galleries.append(gallery_data)
                        success_count += 1
                        print(f"    ✓ 成功")

                    # 礼貌性延时，避免请求过快被封禁或返回 404
                    time.sleep(DELAY_BETWEEN_GALLERIES)

                print(f"  本页成功抓取: {success_count}/{len(page_gallery_links)}")

                # 第六步：查找"下一页"按钮
                # 根据HTML，下一页链接的 id 可能是 "dnext" 或 "unext"
                next_btn = soup.find("a", id="dnext")
                if not next_btn:
                    next_btn = soup.find("a", id="unext")

                # 如果存在下一页，继续循环；否则结束该文件夹的抓取
                if next_btn and next_btn.get("href"):
                    next_href = next_btn["href"]
                    # 检查是否是有效的下一页链接（不是 "#" 或 "javascript:"）
                    if next_href.startswith("http") or next_href.startswith("/"):
                        # 如果是相对路径，补全为完整URL
                        if next_href.startswith("/"):
                            base = FAVORITES_URL.rsplit("/", 1)[0]
                            current_url = base + next_href
                        else:
                            current_url = next_href
                        page_index += 1
                        # 翻页之间也要延时
                        print(f"  等待 {DELAY_BETWEEN_PAGES} 秒后继续下一页...")
                        time.sleep(DELAY_BETWEEN_PAGES)
                    else:
                        print("  未找到有效的下一页链接，该文件夹抓取完成")
                        has_next_page = False
                else:
                    print("  未找到下一页，该文件夹抓取完成")
                    has_next_page = False

            except KeyboardInterrupt:
                print("\n\n检测到用户中断（Ctrl+C）")
                print(f"已抓取 {len(all_galleries)} 本漫画数据")
                save_choice = input("是否保存已抓取的数据？(y/n): ")
                if save_choice.lower() == "y":
                    print(f"正在保存缓存文件: {CACHE_FILE_PATH}")
                    try:
                        os.makedirs(OUTPUTS_DIR, exist_ok=True)
                    except Exception:
                        pass
                    with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
                        json.dump(all_galleries, f, ensure_ascii=False, indent=2)
                    print("缓存保存成功。")
                return
            except Exception as e:
                print(f"  抓取过程发生错误: {e}")
                import traceback

                traceback.print_exc()
                break

    # 第七步：保存所有数据到缓存文件
    print(f"\n抓取结束。共获取 {len(all_galleries)} 本漫画数据。")
    print(f"正在保存缓存文件: {CACHE_FILE_PATH}")
    # 确保输出目录存在
    try:
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
    except Exception:
        pass

    with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(all_galleries, f, ensure_ascii=False, indent=2)
    print("缓存保存成功。")


def load_cache():
    """
    从本地加载缓存文件
    返回：漫画数据列表
    """
    print(f"正在加载本地缓存: {CACHE_FILE_PATH}")
    try:
        with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"成功加载 {len(data)} 本漫画数据")
        return data
    except Exception as e:
        print(f"读取缓存失败: {e}")
        return []


def filter_by_folders(galleries):
    """
    根据配置的收藏文件夹 ID 列表筛选数据
    只保留属于指定文件夹的漫画
    如果 SELECTED_FAVORITE_FOLDERS 为空，则不筛选（保留所有数据）
    """
    # 如果用户没有指定文件夹，返回全部数据
    if not SELECTED_FAVORITE_FOLDERS:
        print("未指定收藏文件夹筛选，将统计所有文件夹的数据")
        return galleries

    print(f"\n>>> 开始按收藏文件夹筛选数据...")
    print(f"只保留文件夹 ID 为 {SELECTED_FAVORITE_FOLDERS} 的漫画")

    # 筛选：只保留 folder_id 在指定列表中的漫画
    filtered = []
    for gallery in galleries:
        folder_id = gallery.get("folder_id")
        if folder_id in SELECTED_FAVORITE_FOLDERS:
            filtered.append(gallery)

    print(f"筛选前: {len(galleries)} 本漫画")
    print(f"筛选后: {len(filtered)} 本漫画")

    return filtered


def analyze_data(galleries):
    """
    核心逻辑：对筛选后的数据进行加权统计
    注意：此函数接收的 galleries 已经过文件夹筛选
    """
    print("\n>>> 开始进行数据加权分析...")

    # 统计容器： { 'female': {'tag_name': score, ...}, 'parody': {...} }
    stats_result = defaultdict(lambda: defaultdict(float))

    for gallery in galleries:
        category = gallery.get("category", "杂志")
        pages = gallery.get("pages", 0)
        tags_map = gallery.get("tags", {})

        # 1. 确定该漫画类型对应的页数权重系数
        # 如果类型在配置中，取配置值；否则取默认值
        page_weight_ratio = CATEGORY_WEIGHTS.get(category, DEFAULT_PAGE_WEIGHT)

        # 2. 计算这本漫画的总页面权重
        # 公式：基础分 + (页数 × 该类型的页数权重系数)
        total_weight = PAGE_BASIC_RATIO + (pages * page_weight_ratio)

        # 3. 遍历这本漫画的所有 namespace
        for namespace in tags_map:
            # 只统计我们在配置中关心的 namespace
            if namespace not in TARGET_NAMESPACES:
                continue

            tag_list = tags_map[namespace]
            if not tag_list:
                continue

            # 4. 权重分配逻辑（Normalize）
            # 将该漫画的总权重平均分配给该 namespace 下的所有 tag
            # 避免标签堆砌导致统计失真
            weight_per_tag = total_weight / len(tag_list)

            # 5. 累加每个标签的权重分数
            for tag in tag_list:
                stats_result[namespace][tag] += weight_per_tag

    print("数据分析完成")
    return stats_result


def export_csv_and_plot(stats_data):
    """
    导出统计结果为 CSV 文件，并生成可视化图表
    每个 namespace 生成一个独立的 CSV 和一张图表
    """
    print("\n>>> 开始生成统计报表和图表...")

    # 设置绘图字体，解决中文显示问题
    plt.rcParams["font.sans-serif"] = [
        "SimHei",
        "Microsoft YaHei",
        "Arial",
        "sans-serif",
    ]
    plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

    # 遍历每个需要统计的 namespace
    for namespace in TARGET_NAMESPACES:
        if namespace not in stats_data:
            print(f"警告: 数据中没有找到分类 {namespace}，跳过。")
            continue

        # 获取该 namespace 下的所有标签及其权重分数
        tag_scores = stats_data[namespace]

        # 排序：按分数从高到低排序
        sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)

        # 截取前 N 名（根据配置）- 仅用于图表显示
        limit = TOP_N_CONFIG.get(namespace, DEFAULT_TOP_N)
        top_tags = sorted_tags[:limit]

        if not sorted_tags:
            print(f"分类 {namespace} 数据为空，跳过。")
            continue

        # --- 第一步：导出 CSV 文件（输出所有数据，不受top_n限制）---
        # 确保输出目录存在
        try:
            os.makedirs(OUTPUTS_DIR, exist_ok=True)
        except Exception:
            pass

        csv_filename = os.path.join(OUTPUTS_DIR, f"stats_{namespace}.csv")
        print(f"正在导出 {csv_filename} ...")
        with open(csv_filename, "w", encoding="utf-8-sig") as f:
            f.write("Tag,Weighted_Score\n")  # 表头：标签, 加权分数
            for tag, score in sorted_tags:  # 使用 sorted_tags 而不是 top_tags
                f.write(f"{tag},{score:.2f}\n")

        # --- 第二步：绘制可视化图表 ---
        # 准备绘图数据
        labels = [item[0] for item in top_tags]
        values = [item[1] for item in top_tags]

        # 反转列表，让第一名显示在图表最上方
        labels.reverse()
        values.reverse()

        # 创建图表
        plt.figure(figsize=(10, 6))  # 设置图片大小

        # 绘制水平柱状图
        plt.barh(labels, values, color="skyblue")

        # 设置图表标题和轴标签
        plt.xlabel("Weighted Score (Based on Pages & Type)")  # X轴说明
        plt.title(f"Top {limit} Tags in Namespace: [{namespace}]")  # 标题
        plt.grid(axis="x", linestyle="--", alpha=0.7)  # 添加网格线

        # 调整布局，防止标签被切掉
        plt.tight_layout()

        # 保存图表为 PNG 文件
        img_filename = os.path.join(OUTPUTS_DIR, f"chart_{namespace}.png")
        plt.savefig(img_filename)
        print(f"图表已保存: {img_filename}")

        # 关闭当前图表，释放内存
        plt.close()


def main():
    """
    主函数：程序入口
    """
    # 确保 outputs 目录存在（后续读写都使用该目录）
    ensure_outputs_dir()
    # ---------------------------------------------------------
    # 步骤 1: 缓存检查逻辑
    # 如果缓存文件存在，直接加载；否则开始网页抓取
    # ---------------------------------------------------------
    if os.path.exists(CACHE_FILE_PATH):
        print(f"检测到缓存文件 [{CACHE_FILE_PATH}] 存在。")
        print("跳过网页抓取，直接使用本地数据。")
        print("如果想重新抓取，请手动删除该 JSON 文件。\n")

        # 从本地加载缓存数据
        galleries = load_cache()
    else:
        print(f"未检测到缓存文件。准备开始抓取网页...\n")

        # 检查 Cookie 是否填写完整
        if not USER_COOKIE or "igneous" not in USER_COOKIE:
            print("警告: 你似乎没有填写 Cookie，或者 Cookie 格式不完整。")
            print("如果没有正确填写 Cookie，可能无法抓取到完整数据。")
            confirm = input("是否继续？(y/n): ")
            if confirm.lower() != "y":
                return

        # 执行网页抓取流程
        run_spider_process()

        # 抓取完成后加载缓存
        galleries = load_cache()

    # 检查是否成功加载数据
    if not galleries:
        print("错误: 没有加载到任何数据，程序退出。")
        return

    # ---------------------------------------------------------
    # 步骤 2: 收藏文件夹筛选逻辑（统计前置条件）
    # 只保留用户指定文件夹中的漫画数据
    # ---------------------------------------------------------
    filtered_galleries = filter_by_folders(galleries)

    if not filtered_galleries:
        print("错误: 筛选后没有任何数据，请检查收藏文件夹配置。")
        return

    # ---------------------------------------------------------
    # 步骤 3: 数据加权分析逻辑
    # 对筛选后的数据进行统计，计算每个标签的加权分数
    # ---------------------------------------------------------
    stats = analyze_data(filtered_galleries)

    # ---------------------------------------------------------
    # 步骤 4: 导出与可视化逻辑
    # 将统计结果输出为 CSV 文件和图表
    # ---------------------------------------------------------
    export_csv_and_plot(stats)

    print("\n=============================================")
    print("所有任务已完成！请查看目录下的 .csv 和 .png 文件。")
    print("=============================================")


# 程序入口
if __name__ == "__main__":
    main()
