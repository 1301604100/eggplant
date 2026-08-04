# 茄子桌宠：Gitee Releases 兜底 设计规格

**日期：** 2026-08-04  
**状态：** 已确认  
**范围：** GitHub 查更失败时回退 Gitee 发版仓；CI 同步 Release 附件  

---

## 1. 目标

- 客户端检查更新：先 GitHub，失败或无可用资产时再查 Gitee。
- Gitee 仓 `kary2/eggplant-releases` 仅托管公开 Release（无源码镜像）。
- tag 打包流程在发布 GitHub Release 后，尽力同步同名 Release + 两个 EXE 到 Gitee。
- Gitee 同步失败不阻断 GitHub 发版成功。

## 2. 常量

| 项 | 值 |
|----|-----|
| Gitee owner/repo | `kary2` / `eggplant-releases` |
| Gitee API | `https://gitee.com/api/v5/repos/kary2/eggplant-releases/releases` |
| Gitee 页面 | `https://gitee.com/kary2/eggplant-releases/releases` |
| Secret | `GITEE_TOKEN`（projects 权限） |

## 3. 客户端

- `fetch_latest_release`：GitHub →（失败或无可用包）Gitee。
- 选中结果带 `source`: `github` | `gitee`。
- 「打开下载页」按 `source` 打开对应站点。
- 资产名仍优先 `茄子桌宠.exe`，否则 `EggplantPet-Windows.exe`；兼容 `assets` / `attach_files` 与 `browser_download_url` / `download_url`。

## 4. CI

- 在 Publish GitHub Release 之后增加 Sync to Gitee 步骤（`continue-on-error: true`）。
- 无 `GITEE_TOKEN` 时跳过并打日志。
- 空仓时先推一个占位 commit 到 `master`，再创建 Release 并上传附件。
