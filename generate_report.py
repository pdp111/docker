import urllib.request
import json
import os
import datetime
import base64

def api_get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'github-top10-daily'})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            return {'error': f'Rate limited ({e.code})', 'status': e.code}
        return {'error': f'HTTP {e.code}', 'status': e.code}
    except Exception as e:
        return {'error': str(e), 'status': 0}

def fetch_repos():
    thresholds = ['>100000', '>50000', '>10000', '>1000', '>100', '']
    for t in thresholds:
        q = f'stars:{t}&sort=stars&order=desc&per_page=10' if t else 'sort=stars&order=desc&per_page=10'
        url = f'https://api.github.com/search/repositories?q={q}'
        data = api_get(url)
        items = data.get('items', [])
        if 'error' in data:
            print(f'Query stars:{t} failed: {data["error"]}')
            continue
        if len(items) >= 10:
            print(f'Query stars:{t} returned {len(items)} items')
            return items
    return []

def fetch_readme(full_name):
    url = f'https://api.github.com/repos/{full_name}/readme'
    data = api_get(url)
    if 'error' in data:
        return None, f'Error: {data["error"]}'
    content = data.get('content', '')
    if content:
        try:
            decoded = base64.b64decode(content).decode('utf-8', errors='ignore')
            lines = decoded.split('\n')
            # Take first 200 lines or first 8000 chars
            short = '\n'.join(lines[:200])
            if len(short) > 8000:
                short = short[:8000]
            return data, short
        except Exception as e:
            return data, f'Decode error: {e}'
    return data, None

def main():
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    print(f'Starting report generation for {today}')
    
    items = fetch_repos()
    if not items:
        print('Failed to fetch any repositories')
        return
    
    repos = []
    errors = []
    for idx, item in enumerate(items[:10]):
        full_name = item['full_name']
        print(f'[{idx+1}/10] Fetching README for {full_name}...')
        readme_meta, readme_content = fetch_readme(full_name)
        repos.append({
            'rank': idx + 1,
            'full_name': full_name,
            'description': item.get('description') or '',
            'language': item.get('language') or 'N/A',
            'stargazers_count': item.get('stargazers_count', 0),
            'forks_count': item.get('forks_count', 0),
            'open_issues_count': item.get('open_issues_count', 0),
            'created_at': item.get('created_at', ''),
            'pushed_at': item.get('pushed_at', ''),
            'license': item.get('license', {}).get('name', 'N/A') if item.get('license') else 'N/A',
            'homepage': item.get('homepage', ''),
            'topics': item.get('topics', []),
            'html_url': item.get('html_url', f'https://github.com/{full_name}'),
            'readme': readme_content or 'README 获取失败或为空',
        })
        if readme_meta and 'error' in readme_meta:
            errors.append(f'{full_name} README: {readme_meta["error"]}')
    
    # Generate markdown
    md = f"""# GitHub Top 10 仓库日报 - {today}

## 概览

- **数据来源**: GitHub Search API
- **采集时间**: {today}
- **口径说明**: GitHub 无官方"点击量"指标，本报告以 `stars` 总数作为综合热度的代理指标，按 stars 降序排列取前 10 名。

## 汇总表格

| 排名 | 仓库 | 主语言 | Stars | Forks | Open Issues | 简介 |
|:---:|:---|:---:|:---:|:---:|:---:|:---|
"""
    for r in repos:
        desc_short = r['description'][:60] + ('...' if len(r['description']) > 60 else '')
        md += f"| {r['rank']} | [{r['full_name']}]({r['html_url']}) | {r['language']} | {r['stargazers_count']:,} | {r['forks_count']:,} | {r['open_issues_count']:,} | {desc_short} |\n"
    
    for r in repos:
        md += f"""\n## {r['rank']}. {r['full_name']}

- **仓库链接**: {r['html_url']}
- **主语言**: {r['language']}
- **Stars**: {r['stargazers_count']:,}
- **Forks**: {r['forks_count']:,}
- **Open Issues**: {r['open_issues_count']:,}
- **Created At**: {r['created_at']}
- **Pushed At**: {r['pushed_at']}
- **License**: {r['license']}
- **Homepage**: {r['homepage'] or 'N/A'}
- **Topics**: {', '.join(r['topics']) if r['topics'] else 'N/A'}

### a) 仓库功能简介

{r['description'] or '暂无描述。'}

### b) 代码作用 / 技术架构要点

{r['readme'][:500] if r['readme'] else 'README 内容未能有效提取。'}

### c) 为何热度高

该仓库拥有 {r['stargazers_count']:,} stars，在 GitHub 生态中占据重要位置。其高热度可能源于：社区需求强烈、文档完善、长期维护活跃、在同类项目中具有先发优势或品牌效应，以及良好的传播性与实用性。

"""
    
    md += f"""## 附：数据来源与口径说明

- 本报告通过 GitHub Search API (`/search/repositories`) 获取数据，使用 `sort=stars&order=desc` 参数按 stars 总数降序排列。
- 若首次查询 `stars:>100000` 返回不足 10 条，会逐步降低阈值重新查询，直到满足 10 条。
- Stars 数是用户对仓库的"收藏"行为计数，可近似反映仓库的受欢迎程度，但不等同于访问量或实际使用量。

## 附：本次执行限制或异常

"""
    if errors:
        md += "\n".join(f"- {e}" for e in errors)
    else:
        md += "- 本次执行未遇到明显异常。"
    
    md += "\n"
    
    out_path = f'/workspace/github-top10-{today}.md'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'Report saved to {out_path}')

if __name__ == '__main__':
    main()
