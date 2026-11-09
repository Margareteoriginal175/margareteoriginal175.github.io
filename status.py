#!/usr/bin/env python3
"""Write engine marker + /api/status.json + /m/status.html (Chinese, dark).

env:
  ENGINE=A|B          which engine ran (marker data/engine_a.json / engine_b.json)
  ENGINE_MODE=...     scheduled / takeover / forced / dispatch
  RUN_RESULT=ok|rolled_back|failed
  RUN_URL=...         link to the run (Actions URL or box log)
  STATUS_MARK=0       only render page, don't update the marker
"""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import build as B

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TZ = ZoneInfo("Asia/Shanghai")
UTC = ZoneInfo("UTC")


def j(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def lbl(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%Y-%m-%d %H:%M Asia/Shanghai")


def next_engine_a(now: datetime) -> datetime:
    """cron '7 * * * *' + '37 */2 * * *' (UTC)."""
    u = now.astimezone(UTC).replace(second=0, microsecond=0)
    cands = []
    for h in range(0, 4):
        base = (u + timedelta(hours=h)).replace(minute=0)
        cands.append(base.replace(minute=7))
        if base.hour % 2 == 0:
            cands.append(base.replace(minute=37))
    return min(c for c in cands if c > u)


def next_minute(now: datetime, minutes: tuple[int, ...]) -> datetime:
    t = now.astimezone(TZ).replace(second=0, microsecond=0)
    for _ in range(0, 120):
        t += timedelta(minutes=1)
        if t.minute in minutes:
            return t
    return t


def write_marker(now: datetime) -> None:
    eng = (os.environ.get("ENGINE") or "").upper()
    if eng not in ("A", "B") or os.environ.get("STATUS_MARK", "1") == "0":
        return
    meta = j(ROOT / "api" / "meta.json")
    path = DATA / f"engine_{eng.lower()}.json"
    prev = j(path)
    result = os.environ.get("RUN_RESULT", "ok")
    marker = {
        "engine": eng,
        "name": "GitHub Actions 云端引擎" if eng == "A" else "Simular 云服务器引擎",
        "mode": os.environ.get("ENGINE_MODE", "scheduled"),
        "result": result,
        "last_run_at": now.isoformat(timespec="seconds"),
        "last_run_label": lbl(now),
        "last_success_label": lbl(now) if result in ("ok", "rolled_back") else prev.get("last_success_label"),
        "run_url": os.environ.get("RUN_URL", ""),
        "host": "github-actions" if eng == "A" else socket.gethostname(),
        "counts": (meta.get("counts") or {}),
        "runs_total": int(prev.get("runs_total") or 0) + 1,
    }
    if os.environ.get("ENGINE_SEEN_ONLY") == "1":
        marker = dict(prev or {}, engine=eng, name=marker["name"])
        marker["standby_seen_label"] = lbl(now)
        marker["standby_seen_at"] = now.isoformat(timespec="seconds")
    path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[status] marker {path.name}: {marker.get('mode')} {marker.get('result')}")


def age_min(iso: str | None, now: datetime) -> int | None:
    if not iso:
        return None
    try:
        return int((now - datetime.fromisoformat(iso)).total_seconds() // 60)
    except Exception:
        return None


def build_status(now: datetime) -> dict:
    a, b = j(DATA / "engine_a.json"), j(DATA / "engine_b.json")
    meta = j(ROOT / "api" / "meta.json")
    health = j(DATA / "sources_health.json")
    disc = j(DATA / "auto" / "discovered.json")
    dstate = j(DATA / "auto" / "discovery_state.json")
    links = j(DATA / "link_health.json")
    xs = j(DATA / "auto" / "x_fetch_status.json")
    hb = j(DATA / "heartbeat.json")
    b_seen = max(filter(None, [b.get("last_run_at"), b.get("standby_seen_at")]), default=None)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_at_label": lbl(now),
        "site": "https://aiym168.github.io/",
        "engines": {
            "A": {
                **a,
                "schedule": "每小时第 7 分钟 + 每 2 小时第 37 分钟（备用）",
                "next_run_label": lbl(next_engine_a(now)),
                "age_min": age_min(a.get("last_run_at"), now),
            },
            "B": {
                **b,
                "schedule": "服务器每小时第 25 分钟检查；GitHub 超过 90 分钟没更新就接管",
                "next_run_label": lbl(next_minute(now, (25,))),
                "last_seen_at": b_seen,
                "age_min": age_min(b_seen, now),
            },
            "watchdog": {
                "schedule": "每 30 分钟（第 23 / 53 分钟）",
                "next_run_label": lbl(next_minute(now, (23, 53))),
            },
        },
        "counts": meta.get("counts") or {},
        "data_updated_label": meta.get("updated_at_label"),
        "sources": health.get("sources") or {},
        "translators": health.get("translators") or {},
        "discovery": {
            "last_run_label": dstate.get("last_run_label"),
            "items": len(disc.get("items") or []),
            "new_this_run": disc.get("new_this_run"),
            "learned_topics": dstate.get("learned_topics") or [],
        },
        "links": {
            "checked_at_label": links.get("checked_at_label"),
            "checked": links.get("checked"),
            "dead_count": links.get("dead_count"),
        },
        "x": {
            "updated_at_label": xs.get("updated_at_label"),
            "primary_route": xs.get("primary_route"),
            "kept": xs.get("kept"),
        },
        "heartbeat_label": hb.get("updated_at_label"),
    }


STATE_ZH = {"healthy": "正常", "degraded": "波动", "skipped": "暂停中(自动重试)", "retrying": "重试中"}
NAME_ZH = {
    "HN": "Hacker News", "V2EX": "V2EX", "GitHub": "GitHub 搜索", "DEV.to": "DEV 社区", "Lobsters": "Lobsters",
    "GitHubHot": "GitHub 热门", "HotTopics": "最近热议", "X": "X 平台", "Discovery": "自动发现",
    "google": "谷歌翻译(免费)", "mymemory": "MyMemory 翻译", "libre": "LibreTranslate",
}
MODE_ZH = {"scheduled": "定时", "takeover": "接管", "forced": "手动强制", "dispatch": "手动触发", "workflow_dispatch": "手动/看门狗触发", "push": "代码更新", "standby": "待命"}
RES_ZH = {"ok": "成功", "rolled_back": "已自动回滚到上一版", "failed": "失败"}


def render(st: dict) -> str:
    esc = B.esc
    A, Bn, W = st["engines"]["A"], st["engines"]["B"], st["engines"]["watchdog"]

    def eng_card(e, title, extra=""):
        ok = e.get("result") in ("ok", "rolled_back")
        dot = "#5ef0c0" if ok and (e.get("age_min") or 9999) < 180 else "#ffd08a"
        link = f'<a href="{esc(e.get("run_url"))}" target="_blank" rel="noopener">查看运行记录 →</a>' if e.get("run_url", "").startswith("http") else ""
        return f"""<div class="card st-card">
  <div class="badge"><i class="live-dot" style="background:{dot}"></i> {esc(title)}</div>
  <h3>{esc(e.get("name") or title)}</h3>
  <table class="api-table">
   <tr><td>最近运行</td><td><b class="rel" data-iso="{esc(e.get('last_run_at') or '')}">{esc(e.get("last_run_label") or "暂无")}</b></td></tr>
   <tr><td>运行方式</td><td>{esc(MODE_ZH.get(e.get("mode"), e.get("mode") or "-"))}</td></tr>
   <tr><td>结果</td><td>{esc(RES_ZH.get(e.get("result"), e.get("result") or "-"))}</td></tr>
   {extra}
   <tr><td>计划</td><td>{esc(e.get("schedule"))}</td></tr>
   <tr><td>下次运行</td><td>{esc(e.get("next_run_label"))}</td></tr>
  </table>
  <p class="linkrow">{link}</p>
</div>"""

    b_extra = ""
    if Bn.get("standby_seen_label"):
        b_extra = f'<tr><td>最近在线</td><td><b class="rel" data-iso="{esc(Bn.get("standby_seen_at") or "")}">{esc(Bn.get("standby_seen_label"))}</b>（待命巡检）</td></tr>'

    rows = []
    for kind, data in (("数据源", st["sources"]), ("翻译", st["translators"])):
        for name, e in sorted(data.items()):
            rows.append(
                f"<tr><td>{esc(kind)}</td><td>{esc(NAME_ZH.get(name, name))}</td><td>{esc(STATE_ZH.get(e.get('state'), e.get('state') or '-'))}</td>"
                f"<td>{esc(e.get('score'))}</td><td>{esc(e.get('last_count', '-'))}</td><td>{esc(e.get('last_ok_label') or '-')}</td>"
                f"<td>{esc(e.get('skip_until_label') or '-')}</td></tr>"
            )
    c = st["counts"]
    mods = c.get("modules") or {}
    count_pills = "".join(
        f'<div class="pill">{esc(title)} <b data-count="{mods.get(mid, 0)}">{mods.get(mid, 0)}</b></div>'
        for mid, title, *_ in B.MODULES
    )
    d, lk, x = st["discovery"], st["links"], st["x"]
    topics = "、".join(d.get("learned_topics") or []) or "（积累中）"
    canonical = f"{B.CANONICAL}m/status.html"
    return f"""{B.head_block(f"运行状态 · {B.SITE_NAME}", f"{B.SITE_NAME} 双引擎自动更新运行状态：GitHub 云端引擎与服务器引擎互为备份，数据源健康度、条目数量与下次更新时间。", canonical)}
<body>
<div class="fx-aurora" aria-hidden="true"></div>
<div class="fx-grid" aria-hidden="true"></div>
<div class="fx-noise" aria-hidden="true"></div>
<div class="fx-scan" aria-hidden="true"></div>
<div class="fx-spot" aria-hidden="true"></div>
<canvas id="fx-particles" aria-hidden="true"></canvas>
<div class="wrap">
  {B.topnav("../")}
  <div class="crumbs"><a href="../">首页</a> › 运行状态</div>
  <header class="hero">
    <div class="eyebrow"><i class="live-dot"></i> SELF-ALIVE · DUAL ENGINE</div>
    <h1 class="hero-title">运行状态</h1>
    <p class="lead">本站由两套独立引擎自动维护：GitHub 云端引擎每小时更新；Simular 云服务器引擎每小时巡检，GitHub 停摆超过 90 分钟就自动接管。看门狗每 30 分钟检查一次，发现停用或失败会自动重新启用并补跑。全程无需人工。</p>
    <div class="stats">
      <div class="pill">数据更新 <b>{esc(st.get("data_updated_label") or "-")}</b></div>
      <div class="pill">状态生成 <b class="rel" data-iso="{esc(st["generated_at"])}">{esc(st["generated_at_label"])}</b></div>
      <div class="pill">免费资源 <b data-count="{c.get('deals', 0)}">{c.get('deals', 0)}</b></div>
    </div>
  </header>

  <section class="section"><h2>双引擎</h2>
    <div class="grid st-grid">
      {eng_card(A, "引擎 A · GitHub")}
      {eng_card(Bn, "引擎 B · 服务器", b_extra)}
      <div class="card st-card"><div class="badge"><i class="live-dot"></i> 看门狗</div><h3>互相守护</h3>
        <table class="api-table">
          <tr><td>计划</td><td>{esc(W["schedule"])}</td></tr>
          <tr><td>下次检查</td><td>{esc(W["next_run_label"])}</td></tr>
          <tr><td>职责</td><td>主流程被停用则自动启用；失败或超时则自动补跑并记录故障；服务器端同样会反向检查 GitHub。</td></tr>
          <tr><td>保活</td><td>每日心跳 {esc(st.get("heartbeat_label") or "-")}，防止 GitHub 因长期无活动停用定时任务。</td></tr>
        </table></div>
    </div>
  </section>

  <section class="section"><h2>条目数量</h2><div class="stats">{count_pills}</div></section>

  <section class="section"><h2>数据源健康度</h2>
    <p class="sec-desc">连续失败 3 次的数据源会自动暂停，并按 1→2→4…最长 24 小时的间隔自动重试；翻译服务按健康分自动轮换。</p>
    <div class="panel-box" style="overflow:auto"><table class="api-table">
      <tr><th>类型</th><th>名称</th><th>状态</th><th>健康分</th><th>最近条数</th><th>最近成功</th><th>暂停到</th></tr>
      {''.join(rows) or '<tr><td colspan="7">暂无记录</td></tr>'}
    </table></div>
  </section>

  <section class="section"><h2>自我进化</h2>
    <div class="panel-box"><table class="api-table">
      <tr><td>自动发现</td><td>最近 {esc(d.get("last_run_label") or "-")}，本次新发现 {esc(d.get("new_this_run") if d.get("new_this_run") is not None else "-")} 条，累计 {esc(d.get("items"))} 条</td></tr>
      <tr><td>自学关键词</td><td>{esc(topics)}</td></tr>
      <tr><td>死链清理</td><td>最近 {esc(lk.get("checked_at_label") or "-")}，检查 {esc(lk.get("checked") or 0)} 个链接，下线 {esc(lk.get("dead_count") or 0)} 个失效链接</td></tr>
      <tr><td>X 平台</td><td>最近 {esc(x.get("updated_at_label") or "-")}，保留 {esc(x.get("kept") or 0)} 条</td></tr>
    </table></div>
  </section>
  <p class="linkrow">机器可读：<a href="../api/status.json">api/status.json</a></p>
  <footer>{esc(B.SITE_NAME)}</footer>
</div>
<style>.st-grid{{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}}.st-card h3{{margin:10px 0}}.st-card td:first-child{{color:var(--muted);white-space:nowrap}}</style>
<script>{B.FX_JS}
(function(){{
  function rel(){{document.querySelectorAll('.rel').forEach(function(el){{
    var iso=el.getAttribute('data-iso'); if(!iso) return; var t=Date.parse(iso); if(isNaN(t)) return;
    var m=Math.round((Date.now()-t)/60000); var base=el.getAttribute('data-base')||el.textContent; el.setAttribute('data-base',base);
    el.textContent=base+'（'+(m<1?'刚刚':m<60?m+' 分钟前':Math.floor(m/60)+' 小时 '+(m%60)+' 分钟前')+'）';
  }});}}
  rel(); setInterval(rel,60000);
}})();
</script>
</body></html>"""


def main() -> int:
    now = datetime.now(TZ)
    write_marker(now)
    st = build_status(now)
    (ROOT / "api").mkdir(exist_ok=True)
    (ROOT / "m").mkdir(exist_ok=True)
    (ROOT / "api" / "status.json").write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "m" / "status.html").write_text(render(st), encoding="utf-8")
    print("[status] wrote api/status.json + m/status.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
