# Issue 导入与里程碑设置指南

本文档说明如何将 `docs/issues_import.csv` 或 `docs/issues_import.json` 导入为 GitHub Issues，并按周设置里程碑与标签。

## 方式一：通过 GitHub 网页导入 CSV（推荐）

1. 打开仓库 Issues 页面 → New Issue 右侧的下拉菜单 → Import issues.
2. 选择文件：`docs/issues_import.csv`。
3. 确认列映射（Title/Body/Labels/Milestone）。
4. 开始导入，GitHub 会自动为不存在的 Labels/Milestone 创建条目。

注意：
- CSV 中 Body 的换行已使用 `\n`，导入后 GitHub 会自动渲染。
- 如需指派 Assignee，可在 CSV 中添加 `Assignee` 列（用户名）。

## 方式二：使用 GitHub CLI（gh）批量创建

前置：安装 `gh` 并执行 `gh auth login`。

### 创建里程碑（Week 1–Week 8）

```bash
for i in {1..8}; do
  gh api \
    --method POST \
    -H "Accept: application/vnd.github+json" \
    "/repos/:owner/:repo/milestones" \
    -f title="Week $i" >/dev/null
  echo "Milestone Week $i ensured"
done
```

> 将 `:owner/:repo` 替换为实际仓库（也可设置环境变量 `GH_REPO`）。

### 基于 JSON 创建 Issues

`docs/issues_import.json` 为数组格式，每个对象包含 `title`、`body`、`labels[]`、`milestone`（名称）。

示例脚本（bash + jq）：

```bash
FILE="docs/issues_import.json"

# 建立 milestone 名称到编号的映射
mapfile -t MS < <(gh api /repos/:owner/:repo/milestones | jq -r '.[] | "\(.number):\(.title)"')
get_ms_num() { # $1: title
  for kv in "${MS[@]}"; do
    num="${kv%%:*}"; title="${kv#*:}"
    [[ "$title" == "$1" ]] && { echo "$num"; return; }
  done
}

jq -c '.[]' "$FILE" | while read -r item; do
  title=$(echo "$item" | jq -r .title)
  body=$(echo "$item" | jq -r .body)
  labels=$(echo "$item" | jq -r '.labels | join(",")')
  ms_title=$(echo "$item" | jq -r .milestone)
  ms_num=$(get_ms_num "$ms_title")
  echo "Creating: $title (milestone: $ms_title)"
  gh issue create \
    --title "$title" \
    --body "$body" \
    --label "$labels" \
    --milestone "$ms_num" >/dev/null
done
```

> 需要 `jq`。Windows 用户可用 PowerShell/JQ 组合或改用 CSV 导入方式。

## 常见问题

- CSV 导入失败：确认第一行表头为 `Title,Body,Labels,Milestone`，Body 中逗号需被引号包裹。
- 里程碑未关联：网页导入会根据 `Milestone` 文本创建/关联；CLI 需传编号（上文脚本已处理）。
- 标签未创建：CSV/CLI 都会自动创建不存在的标签；如需颜色和描述，后续在仓库设置中统一调整。

---

如需我将导入流程做成一键脚本（支持 `GH_REPO` 环境变量与检查依赖），可以继续补充到 `scripts/` 目录。

