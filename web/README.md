# Wallpaper Converter Web

静态网页版（纯静态、零构建、文件不离开浏览器）。部署在 **GitHub Pages**：

- 线上地址：<https://sun-zihang.github.io/wallpaper-forge/>
- 自动部署：`.github/workflows/pages.yml`，`main` 上 `web/**`（或本 workflow 文件）变更时触发，也可手动 workflow_dispatch
- 部署成功后自动触发 `.github/workflows/smoke.yml` 对线上站点跑 Playwright 冒烟检查（26 项；另每周一定时执行）

本地预览：

```bash
python -m http.server 8765 -d web
```

测试（与 CI 一致；**勿给 glob 加引号**，bash 下带引号的 `**` 不会展开）：

```bash
node --test web/tests/*.test.mjs
```

CDN 钉版可达性另有 `node scripts/check_cdn.mjs`（读取 `web/lib/cdn.js` 里的镜像列表逐一 HEAD）。
