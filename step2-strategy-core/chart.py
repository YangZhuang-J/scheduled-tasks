# -*- coding: utf-8 -*-
"""生成交互式 HTML 回测曲线图，直观对比 卖出逻辑 A / B / 旧(once)。

用法：
python chart.py --config config-3state.json --index 沪深300 --out chart.html
"""
import argparse
import json
import config_loader
import engine
from backtest import INDEX_SYMBOLS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--out", default="chart.html")
    args = ap.parse_args()

    symbol = args.symbol or INDEX_SYMBOLS[args.index]
    cfg = config_loader.load_config(args.config)

    print("加载数据并模拟三种卖出模式...")
    df = engine.get_data(args.index, symbol, args.window)

    res_once = engine.simulate(df, cfg, sell_mode="once")
    res_a = engine.simulate(df, cfg, sell_mode="A")
    res_b = engine.simulate(df, cfg, sell_mode="B")

    dates = [d.strftime("%Y-%m-%d") for d in df["date"]]
    close = [round(float(x), 2) for x in df["close"]]
    pct = [round(float(x), 2) for x in df["pct"]]
    pos_ret_b = [round(x, 2) if x is not None else None for x in res_b["daily"]["pos_return"]]

    def pts(res, action):
        return [[t["date"].strftime("%Y-%m-%d"), t["price"]] for t in res["trades"] if t["action"] == action]

    buy_pts = pts(res_b, "buy")
    sell_once = pts(res_once, "sell")
    sell_a = pts(res_a, "sell")
    sell_b = pts(res_b, "sell")
    sell_b_return = [[t["date"].strftime("%Y-%m-%d"), t["pos_return"]] for t in res_b["trades"] if t["action"] == "sell"]

    # 状态边界 / 闸门 / 阶梯线
    bounds = [s["range"][1] for s in cfg["buy_states"][:-1]]
    gate = cfg["sell"].get("min_valuation_pct", 70)
    ladder_profits = [r["profit"] for r in cfg["sell"].get("ladder", [])]

    for name, res in [("旧逻辑(once)", res_once), ("方案A", res_a), ("方案B", res_b)]:
        n_sell = sum(1 for t in res["trades"] if t["action"] == "sell")
        n_buy = sum(1 for t in res["trades"] if t["action"] == "buy")
        print(f"  {name}: 买入{n_buy}次, 卖出{n_sell}次, 总收益率{res['total_return']*100:.1f}%")

    data = {
        "index": args.index,
        "cfgName": cfg.get("name", args.config),
        "dates": dates,
        "close": close,
        "pct": pct,
        "posRetB": pos_ret_b,
        "buyPts": buy_pts,
        "sellOnce": sell_once,
        "sellA": sell_a,
        "sellB": sell_b,
        "sellBReturn": sell_b_return,
        "bounds": bounds,
        "gate": gate,
        "ladderProfits": ladder_profits,
    }

    html = render_html(data)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n已生成: {args.out}  （用浏览器打开）")


def render_html(d):
    return """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>定投策略回测曲线 - """ + d["index"] + """</title>
<script src="https://registry.npmmirror.com/echarts/5.5.0/files/dist/echarts.min.js"></script>
<style>body{margin:0;font-family:sans-serif}#c{width:100vw;height:100vh}</style>
</head>
<body>
<div id="c"></div>
<script>
var D = """ + json.dumps(d, ensure_ascii=False) + """;
var chart = echarts.init(document.getElementById('c'));

function zoneColors(bounds){
  // 估值分位状态色带：绿→黄→红
  var stops = [];
  var colors = ['#2ecc71','#a8e063','#f1c40f','#e67e22','#e74c3c'];
  var pts = [0].concat(bounds, [100]);
  for(var i=0;i<pts.length-1;i++){
    var c = colors[Math.min(i, colors.length-1)];
    stops.push({xAxis: pts[i], color: c + '22'});
    stops.push({xAxis: pts[i+1], color: c + '22'});
  }
  return stops;
}

var option = {
  title: {text: D.index + '  估值定投回测  [' + D.cfgName + ']', left: 10, top: 2, textStyle:{fontSize:15}},
  tooltip: {trigger:'axis'},
  legend: {data:['收盘价','买入','卖出-旧逻辑','卖出-方案A','卖出-方案B','持仓收益率(B)','估值分位'], top: 24},
  axisPointer: {link: [{xAxisIndex:'all'}]},
  grid: [
    {left:70, right:30, top:60, height:'32%'},
    {left:70, right:30, top:'47%', height:'18%'},
    {left:70, right:30, top:'71%', height:'18%'}
  ],
  xAxis: [
    {type:'category', data:D.dates, gridIndex:0, axisLabel:{show:false}},
    {type:'category', data:D.dates, gridIndex:1, axisLabel:{show:false}},
    {type:'category', data:D.dates, gridIndex:2, axisLabel:{show:true}}
  ],
  yAxis: [
    {type:'log', gridIndex:0, name:'收盘价'},
    {type:'value', gridIndex:1, name:'持仓收益率%'},
    {type:'value', gridIndex:2, name:'估值分位%', min:0, max:100}
  ],
  dataZoom: [
    {type:'inside', xAxisIndex:[0,1,2]},
    {type:'slider', xAxisIndex:[0,1,2], bottom:5}
  ],
  series: [
    {name:'收盘价', type:'line', xAxisIndex:0, yAxisIndex:0, data:D.close, showSymbol:false, lineStyle:{width:1.2, color:'#34495e'}},
    {name:'买入', type:'scatter', xAxisIndex:0, yAxisIndex:0, data:D.buyPts, symbol:'triangle', symbolSize:5, itemStyle:{color:'#2ecc71'}},
    {name:'卖出-旧逻辑', type:'scatter', xAxisIndex:0, yAxisIndex:0, data:D.sellOnce, symbol:'pin', symbolSize:20, itemStyle:{color:'#95a5a6'}},
    {name:'卖出-方案A', type:'scatter', xAxisIndex:0, yAxisIndex:0, data:D.sellA, symbol:'pin', symbolSize:20, itemStyle:{color:'#e67e22'}},
    {name:'卖出-方案B', type:'scatter', xAxisIndex:0, yAxisIndex:0, data:D.sellB, symbol:'pin', symbolSize:20, itemStyle:{color:'#e74c3c'}},
    {name:'持仓收益率(B)', type:'line', xAxisIndex:1, yAxisIndex:1, data:D.posRetB, showSymbol:false, lineStyle:{width:1.2, color:'#8e44ad'}, markLine:{silent:true, symbol:'none', lineStyle:{type:'dashed'}, data:D.ladderProfits.map(function(v){return {yAxis:v};})}, label:{show:true, formatter:function(p){return p.data[1]!=null? p.data[1].toFixed(0)+'%':'';}}},
    {name:'估值分位', type:'line', xAxisIndex:2, yAxisIndex:2, data:D.pct, showSymbol:false, lineStyle:{width:1.2, color:'#16a085'}, markLine:{silent:true, symbol:'none', lineStyle:{type:'dashed', color:'#c0392b'}, data:[{yAxis:D.gate}]}, markArea:{silent:true, data:[[{xAxis:0},{xAxis:1}]]}, areaStyle:{}}
  ]
};

// 给估值分位面板加状态色带（背景）
var bounds = D.bounds;
var pts = [0].concat(bounds, [100]);
var colors = ['#2ecc71','#a8e063','#f1c40f','#e67e22','#e74c3c'];
var markAreas = [];
for(var i=0;i<pts.length-1;i++){
  var c = colors[Math.min(i, colors.length-1)];
  markAreas.push([{yAxis:pts[i], itemStyle:{color:c+'18'}}, {yAxis:pts[i+1]}]);
}
option.series[6].markArea = {silent:true, data: markAreas};

chart.setOption(option);
window.addEventListener('resize', function(){chart.resize();});
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
