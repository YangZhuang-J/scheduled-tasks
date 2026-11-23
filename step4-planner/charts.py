# -*- coding: utf-8 -*-
"""ECharts 图表生成（复用 step2 chart.html 的视觉风格）"""
import json

ECHARTS_CDN = "https://registry.npmmirror.com/echarts/5.5.0/files/dist/echarts.min.js"


_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="__CDN__"></script>
<style>html,body{margin:0;padding:0;height:__HEIGHT__px;overflow:hidden;background:transparent}</style>
</head><body><div id="c" style="width:100%;height:__HEIGHT__px"></div>
<script>
var chart = echarts.init(document.getElementById('c'));
var option = __OPTION__;
var FORCE_THEME = '__THEME__';

// ---------- 颜色工具 ----------
function parseColor(str) {
  str = (str || '').trim();
  if (!str) return null;
  if (str.charAt(0) === '#') {
    var h = str.slice(1);
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    if (h.length < 6) return null;
    var r = parseInt(h.substr(0, 2), 16), g = parseInt(h.substr(2, 2), 16), b = parseInt(h.substr(4, 2), 16);
    if (isNaN(r) || isNaN(g) || isNaN(b)) return null;
    return [r, g, b, 1];
  }
  var m = str.match(/[0-9.]+/g);
  if (m && m.length >= 3) {
    var a = (m.length >= 4) ? parseFloat(m[3]) : 1;
    return [+m[0], +m[1], +m[2], a];
  }
  return null;
}
function lumOf(c) { return (c[0] * 299 + c[1] * 587 + c[2] * 114) / 1000; }
function findBg(win, el) {
  var cur = el;
  while (cur) {
    var c = parseColor(win.getComputedStyle(cur).backgroundColor);
    if (c && c[3] > 0.05) return c;
    cur = cur.parentElement;
  }
  return null;
}
function detectDark() {
  if (FORCE_THEME === 'dark') return true;
  if (FORCE_THEME === 'light') return false;
  try {
    var win = window.parent, doc = win.document;
    var bg = findBg(win, doc.body) || findBg(win, doc.documentElement);
    if (bg) return lumOf(bg) < 128;
    var rs = win.getComputedStyle(doc.documentElement);
    var txt = parseColor(rs.getPropertyValue('--text-color').trim());
    if (txt) return lumOf(txt) > 128;
    return !!(win.matchMedia && win.matchMedia('(prefers-color-scheme: dark)').matches);
  } catch (e) {}
  return false;
}

// ---------- 记住原始系列颜色，便于来回切换 ----------
var origSeries = [].concat(option.series || []).map(function (s) {
  return {
    line: (s && s.lineStyle) ? s.lineStyle.color : null,
    item: (s && s.itemStyle) ? s.itemStyle.color : null
  };
});

var DARK_MAP = {
  '#34495e': '#a8bfd4', '#16a085': '#2ecc9b', '#2980b9': '#5dade2',
  '#27ae60': '#58d68d', '#8e44ad': '#bb8fce'
};

// ---------- 应用主题（幂等，可反复调用） ----------
function applyTheme(dark) {
  var FG = dark ? '#e8e8e8' : '#2b2b2b';
  var AXIS = dark ? '#7a7a7a' : '#b0b0b0';
  var SPLIT = dark ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.07)';

  option.backgroundColor = 'transparent';
  option.textStyle = Object.assign({}, option.textStyle, { color: FG });
  if (option.legend) option.legend.textStyle = Object.assign({}, option.legend.textStyle, { color: FG });
  if (option.title && !Array.isArray(option.title))
    option.title.textStyle = Object.assign({}, option.title.textStyle, { color: FG });

  function fixAxis(arr) {
    [].concat(arr || []).forEach(function (a) {
      if (!a) return;
      a.axisLabel = Object.assign({}, a.axisLabel, { color: FG });
      a.nameTextStyle = Object.assign({}, a.nameTextStyle, { color: FG });
      a.axisLine = Object.assign({}, a.axisLine, { lineStyle: Object.assign({}, (a.axisLine || {}).lineStyle, { color: AXIS }) });
      a.splitLine = Object.assign({}, a.splitLine, { lineStyle: Object.assign({}, (a.splitLine || {}).lineStyle, { color: SPLIT }) });
    });
  }
  fixAxis(option.xAxis);
  fixAxis(option.yAxis);

  // 恢复原始颜色后再按主题调整（避免反复切换时颜色被改坏）
  [].concat(option.series || []).forEach(function (s, i) {
    if (!s) return;
    var o = origSeries[i] || {};
    if (s.lineStyle && o.line) s.lineStyle.color = o.line;
    if (s.itemStyle && o.item) s.itemStyle.color = o.item;
    if (dark) {
      if (s.lineStyle && DARK_MAP[s.lineStyle.color]) s.lineStyle.color = DARK_MAP[s.lineStyle.color];
      if (s.itemStyle && DARK_MAP[s.itemStyle.color]) s.itemStyle.color = DARK_MAP[s.itemStyle.color];
    }
  });

  if (option.tooltip) {
    option.tooltip.backgroundColor = dark ? 'rgba(40,40,40,0.95)' : 'rgba(255,255,255,0.96)';
    option.tooltip.borderColor = dark ? '#555' : '#ccc';
    option.tooltip.textStyle = Object.assign({}, option.tooltip.textStyle, { color: FG });
    if (option.tooltip.axisPointer) option.tooltip.axisPointer.lineStyle = { color: dark ? '#888' : '#999' };
  }

  [].concat(option.dataZoom || []).forEach(function (d) {
    if (!d) return;
    d.textStyle = Object.assign({}, d.textStyle, { color: FG });
    d.borderColor = dark ? '#444' : '#ddd';
    if (d.type === 'slider') {
      d.backgroundColor = dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)';
      d.fillerColor = dark ? 'rgba(120,170,255,0.15)' : 'rgba(84,112,198,0.12)';
      d.handleStyle = { color: dark ? '#666' : '#d0d0d0' };
      d.moveHandleStyle = { color: dark ? '#888' : '#b0b0b0' };
    }
  });

  chart.setOption(option, true);
}

// 字符串 formatter 转函数（只需做一次）
if (option.tooltip && typeof option.tooltip.valueFormatter === 'string') {
  try { option.tooltip.valueFormatter = eval('(' + option.tooltip.valueFormatter + ')'); }
  catch (e) { delete option.tooltip.valueFormatter; }
}

// ---------- 首次渲染 + 自动跟随主题变化 ----------
var _lastDark = null;
function refresh() {
  var d = detectDark();
  if (d !== _lastDark) {
    _lastDark = d;
    applyTheme(d);
  }
}
refresh();

// auto 模式下轮询（Streamlit 主题切换不会重载 iframe）
if (FORCE_THEME === 'auto') {
  setInterval(refresh, 800);
  try {
    var win = window.parent;
    new win.MutationObserver(refresh).observe(win.document.documentElement,
      { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] });
    new win.MutationObserver(refresh).observe(win.document.body,
      { attributes: true, attributeFilter: ['class', 'style'] });
  } catch (e) {}
}

window.addEventListener('resize', function () { chart.resize(); });
</script></body></html>"""


def _base_html(height, option_js, theme="auto"):
    return (_HTML_TEMPLATE
            .replace("__CDN__", ECHARTS_CDN)
            .replace("__HEIGHT__", str(height))
            .replace("__THEME__", theme)
            .replace("__OPTION__", option_js))


def _zone_areas(bounds):
    """估值分位的状态色带：绿 → 黄 → 红"""
    pts = [0] + list(bounds) + [100]
    colors = ["#2ecc71", "#a8e063", "#f1c40f", "#e67e22", "#e74c3c"]
    areas = []
    for i in range(len(pts) - 1):
        c = colors[min(i, len(colors) - 1)]
        areas.append([
            {"yAxis": pts[i], "itemStyle": {"color": c + "18"}},
            {"yAxis": pts[i + 1]},
        ])
    return areas




def long_term_price_chart(dates, close, crisis_events, height=320, theme="auto"):
    """全历史价格参考图（2002~今，标注重大危机）"""
    # 标注危机事件（竖线 + 标签）
    marklines = []
    for ev in crisis_events:
        marklines.append({
            "xAxis": ev["date"],
            "label": {"formatter": ev["label"], "position": "insideEndTop",
                      "color": "#c0392b", "fontSize": 10},
            "lineStyle": {"color": "#c0392b", "type": "dashed", "width": 1},
        })

    opt = {
        "animation": False,
        "title": {"text": "全历史价格参考（2002~今）· 未覆盖 2008 金融危机", "left": 8, "top": 4,
                  "textStyle": {"fontSize": 13}},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["收盘价"], "top": 22},
        "grid": {"left": 58, "right": 30, "top": 56, "bottom": 44},
        "xAxis": {"type": "category", "data": dates},
        "yAxis": {"type": "log", "name": "价格", "scale": True},
        "dataZoom": [{"type": "inside"}, {"type": "slider", "height": 16, "bottom": 8}],
        "series": [{
            "name": "收盘价", "type": "line", "data": close, "showSymbol": False,
            "lineStyle": {"width": 1.2, "color": "#7f8c8d"},
            "markLine": {"silent": True, "symbol": "none", "data": marklines},
        }],
    }
    return _base_html(height, json.dumps(opt, ensure_ascii=False), theme)


def price_chart(dates, close, pct, buys, sells, bounds, gate, height=380, theme="auto"):
    """图1：价格 + 买卖点 + 估值分位色带（主图）"""
    opt = {
        "animation": False,
        "title": {"text": "价格走势 · 买卖点 · 估值分位", "left": 8, "top": 4,
                  "textStyle": {"fontSize": 13}},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["收盘价", "买入", "卖出"], "top": 22},
        "axisPointer": {"link": [{"xAxisIndex": "all"}]},
        "grid": [
            {"left": 58, "right": 50, "top": 56, "height": "46%"},
            {"left": 58, "right": 50, "top": "66%", "height": "24%"},
        ],
        "xAxis": [
            {"type": "category", "data": dates, "gridIndex": 0, "axisLabel": {"show": False}},
            {"type": "category", "data": dates, "gridIndex": 1},
        ],
        "yAxis": [
            {"type": "log", "gridIndex": 0, "name": "价格", "scale": True},
            {"type": "value", "gridIndex": 1, "name": "分位%", "min": 0, "max": 100},
        ],
        "dataZoom": [{"type": "inside", "xAxisIndex": [0, 1]}],
        "series": [
            {"name": "收盘价", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0,
             "data": close, "showSymbol": False,
             "lineStyle": {"width": 1.1, "color": "#34495e"}},
            {"name": "买入", "type": "scatter", "xAxisIndex": 0, "yAxisIndex": 0,
             "data": buys, "symbol": "triangle", "symbolSize": 6,
             "itemStyle": {"color": "#27ae60"}},
            {"name": "卖出", "type": "scatter", "xAxisIndex": 0, "yAxisIndex": 0,
             "data": sells, "symbol": "pin", "symbolSize": 18,
             "itemStyle": {"color": "#e74c3c"}},
            {"name": "估值分位", "type": "line", "xAxisIndex": 1, "yAxisIndex": 1,
             "data": pct, "showSymbol": False,
             "lineStyle": {"width": 1, "color": "#16a085"},
             "markLine": {"silent": True, "symbol": "none",
                          "lineStyle": {"type": "dashed", "color": "#c0392b"},
                          "data": [{"yAxis": gate}]},
             "markArea": {"silent": True, "data": _zone_areas(bounds)}},
        ],
    }
    return _base_html(height, json.dumps(opt, ensure_ascii=False), theme)


def value_chart(dates, invested_series, value_series, labels=None, height=340, theme="auto"):
    """图2：持仓市值 vs 累计投入（可多配置对比）

    invested_series / value_series: list[list]，每项一条曲线
    labels: 每条曲线对应的配置名
    """
    labels = labels or [""] * len(invested_series)
    series = []
    colors = ["#2980b9", "#27ae60", "#e67e22", "#8e44ad"]
    for i, (inv, val) in enumerate(zip(invested_series, value_series)):
        c = colors[i % len(colors)]
        name = labels[i] or f"配置{i+1}"
        series.append({
            "name": f"{name}·投入", "type": "line", "data": inv,
            "showSymbol": False, "lineStyle": {"width": 1.2, "type": "dashed", "color": c},
        })
        series.append({
            "name": f"{name}·市值", "type": "line", "data": val,
            "showSymbol": False, "lineStyle": {"width": 1.8, "color": c},
            "areaStyle": {"opacity": 0.08},
        })

    opt = {
        "animation": False,
        "title": {"text": "持仓市值 vs 累计投入", "left": 8, "top": 4,
                  "textStyle": {"fontSize": 13}},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 24, "type": "scroll"},
        "grid": {"left": 66, "right": 30, "top": 60, "bottom": 60},
        "xAxis": {"type": "category", "data": dates},
        "yAxis": {"type": "value", "name": "元", "scale": True},
        "dataZoom": [{"type": "inside"}, {"type": "slider", "height": 16, "bottom": 8}],
        "series": series,
    }
    return _base_html(height, json.dumps(opt, ensure_ascii=False), theme)


def return_chart(dates, return_series, labels=None, ladder=None, height=300, theme="auto"):
    """图3：持仓收益率曲线 + 止盈阶梯线（可多配置对比）"""
    labels = labels or [""] * len(return_series)
    colors = ["#2980b9", "#27ae60", "#e67e22", "#8e44ad"]
    series = []
    for i, r in enumerate(return_series):
        series.append({
            "name": labels[i] or f"配置{i+1}", "type": "line", "data": r,
            "showSymbol": False, "lineStyle": {"width": 1.6, "color": colors[i % len(colors)]},
        })
    markline_data = [{"yAxis": v} for v in (ladder or [])]
    if markline_data:
        series[0]["markLine"] = {
            "silent": True, "symbol": "none",
            "lineStyle": {"type": "dashed", "color": "#c0392b", "opacity": 0.6},
            "data": markline_data,
        }

    opt = {
        "animation": False,
        "title": {"text": "持仓收益率（虚线=止盈阶梯）", "left": 8, "top": 4,
                  "textStyle": {"fontSize": 13}},
        "tooltip": {"trigger": "axis", "valueFormatter": "function(v){return v==null?'-':v.toFixed(1)+'%';}"},
        "legend": {"top": 22, "type": "scroll"},
        "grid": {"left": 58, "right": 30, "top": 56, "bottom": 44},
        "xAxis": {"type": "category", "data": dates},
        "yAxis": {"type": "value", "name": "%", "axisLabel": {"formatter": "{value}%"}},
        "dataZoom": [{"type": "inside"}],
        "series": series,
    }
    return _base_html(height, json.dumps(opt, ensure_ascii=False), theme)
