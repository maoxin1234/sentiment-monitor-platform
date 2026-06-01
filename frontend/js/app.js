/* ══════════════════════════════════════════════════
   舆情监控大屏 - 前端主逻辑
   图表：ECharts 5  |  框架：Vue 3
   ══════════════════════════════════════════════════ */
const { createApp, ref, reactive, onMounted, onUnmounted } = Vue;

// ── ECharts 主题色 ────────────────────────────────────────────────────────────
const COLORS = {
  pos: '#10b981', neu: '#5a7299', neg: '#ef4444',
  blue: '#3b82f6', cyan: '#06b6d4', purple: '#8b5cf6',
  yellow: '#f59e0b', orange: '#f97316',
};
const PALETTE = [COLORS.cyan, COLORS.blue, COLORS.purple, COLORS.green,
                 COLORS.yellow, COLORS.orange, COLORS.pos, COLORS.neg];

const BASE_OPTS = {
  backgroundColor: 'transparent',
  textStyle: { color: '#c8d6f0', fontSize: 11 },
  tooltip: { backgroundColor: '#1a2744', borderColor: '#2d4070', textStyle: { color: '#c8d6f0', fontSize: 11 } },
};

function initChart(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  const chart = echarts.init(el, null, { renderer: 'canvas' });
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

// ── 地图坐标 ──────────────────────────────────────────────────────────────────
const REGION_COORDS = {
  '北京':[116.40,39.90],'上海':[121.47,31.23],'广州':[113.26,23.13],
  '深圳':[114.05,22.54],'成都':[104.06,30.57],'杭州':[120.15,30.25],
  '武汉':[114.30,30.59],'西安':[108.94,34.27],'重庆':[106.55,29.56],
  '南京':[118.77,32.05],'天津':[117.20,39.12],'郑州':[113.65,34.75],
  '长沙':[112.93,28.23],'沈阳':[123.43,41.80],'哈尔滨':[126.63,45.75],
};

// ══════════════════════════════════════════════════
const app = createApp({
  setup() {
    // ── 状态 ────────────────────────────────────────
    const wsConnected = ref(false);
    const currentTime = ref('');
    const stats = ref({});
    const recentPosts = ref([]);
    const activeAlerts = ref([]);

    // ── 图表实例 ────────────────────────────────────
    let charts = {};

    // ── 时序数据 ────────────────────────────────────
    const MAX_TS = 60;
    const tsData = {
      times: [], qps: [], baseline: [], sentiment: [],
      localRatio: [],
    };

    function pushTs(key, val) {
      tsData[key].push(val);
      if (tsData[key].length > MAX_TS) tsData[key].shift();
    }

    // ── 工具 ────────────────────────────────────────
    function sentimentClass(s) {
      return { '正面': 'pos', '负面': 'neg', '中性': 'neu' }[s] || 'neu';
    }

    function fmtTime() {
      return new Date().toLocaleTimeString('zh-CN', { hour12: false });
    }

    // ── 情感饼图 ────────────────────────────────────
    function updateSentimentChart(dist) {
      if (!charts.sentiment) return;
      const data = [
        { name: '正面', value: dist['正面'] || 0, itemStyle: { color: COLORS.pos } },
        { name: '中性', value: dist['中性'] || 0, itemStyle: { color: COLORS.neu } },
        { name: '负面', value: dist['负面'] || 0, itemStyle: { color: COLORS.neg } },
      ];
      charts.sentiment.setOption({
        ...BASE_OPTS,
        series: [{
          type: 'pie', radius: ['45%', '70%'], center: ['50%', '55%'],
          label: { show: true, formatter: '{b}\n{d}%', fontSize: 10, color: '#c8d6f0' },
          labelLine: { length: 6, length2: 4 },
          data,
        }],
        legend: { show: false },
      });
    }

    // ── 平台柱状图 ──────────────────────────────────
    function updatePlatformChart(dist) {
      if (!charts.platform) return;
      const entries = Object.entries(dist).sort((a, b) => b[1] - a[1]).slice(0, 7);
      charts.platform.setOption({
        ...BASE_OPTS,
        grid: { top: 5, bottom: 30, left: 55, right: 10 },
        xAxis: { type: 'value', axisLine: { show: false }, axisLabel: { fontSize: 9, color: '#5a7299' }, splitLine: { lineStyle: { color: '#1a2744' } } },
        yAxis: { type: 'category', data: entries.map(e => e[0]), axisLabel: { fontSize: 10, color: '#c8d6f0' }, axisLine: { lineStyle: { color: '#1a2744' } } },
        series: [{
          type: 'bar', barMaxWidth: 14,
          data: entries.map((e, i) => ({ value: e[1], itemStyle: { color: PALETTE[i % PALETTE.length] } })),
          label: { show: true, position: 'right', fontSize: 9, color: '#5a7299' },
        }],
      });
    }

    // ── QPS 趋势 ────────────────────────────────────
    function updateQpsChart() {
      if (!charts.qps) return;
      charts.qps.setOption({
        ...BASE_OPTS,
        grid: { top: 8, bottom: 20, left: 35, right: 10 },
        xAxis: { type: 'category', data: tsData.times, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#1a2744' } } },
        yAxis: { type: 'value', axisLabel: { fontSize: 9, color: '#5a7299' }, splitLine: { lineStyle: { color: '#1a2744' } }, minInterval: 1 },
        series: [
          {
            name: '当前QPS', type: 'line', data: tsData.qps, smooth: true,
            symbol: 'none', lineStyle: { color: COLORS.cyan, width: 2 },
            areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(6,182,212,.3)' }, { offset: 1, color: 'transparent' }] } },
          },
          {
            name: '基线', type: 'line', data: tsData.baseline, smooth: true,
            symbol: 'none', lineStyle: { color: COLORS.text_dim, width: 1, type: 'dashed' },
          },
        ],
        legend: { show: false },
        tooltip: { trigger: 'axis' },
      });
    }

    // ── 情感时序 ────────────────────────────────────
    function updateSentimentTs() {
      if (!charts.sentimentTs) return;
      charts.sentimentTs.setOption({
        ...BASE_OPTS,
        grid: { top: 8, bottom: 20, left: 38, right: 10 },
        xAxis: { type: 'category', data: tsData.times, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#1a2744' } } },
        yAxis: { type: 'value', min: -1, max: 1, axisLabel: { fontSize: 9, color: '#5a7299' }, splitLine: { lineStyle: { color: '#1a2744' } } },
        visualMap: {
          show: false, dimension: 1, pieces: [
            { lte: -0.1, color: COLORS.neg },
            { gt: -0.1, lte: 0.1, color: COLORS.neu },
            { gt: 0.1, color: COLORS.pos },
          ],
        },
        series: [{
          type: 'line', data: tsData.sentiment, smooth: true, symbol: 'none',
          lineStyle: { width: 2 },
          markLine: { silent: true, lineStyle: { color: '#1a2744', type: 'dashed' }, data: [{ yAxis: 0 }] },
        }],
      });
    }

    // ── 地图热力图 ──────────────────────────────────
    let mapReady = false;
    async function ensureMapRegistered() {
      if (mapReady) return true;
      try {
        const res = await fetch('https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json');
        const geoJson = await res.json();
        echarts.registerMap('china', geoJson);
        mapReady = true;
        return true;
      } catch (e) {
        return false;
      }
    }

    function updateMapFallback(regionHeat) {
      if (!charts.map) return;
      const sorted = [...regionHeat].sort((a,b) => b.heat - a.heat).slice(0, 12);
      charts.map.setOption({
        ...BASE_OPTS,
        title: { text: '地域热度分布（Top12）', textStyle: { color: '#5a7299', fontSize: 10 }, left: 5, top: 0 },
        grid: { top: 24, bottom: 30, left: 50, right: 60 },
        xAxis: { type: 'value', axisLabel: { fontSize: 9, color: '#5a7299' }, splitLine: { lineStyle: { color: '#1a2744' } } },
        yAxis: { type: 'category', data: sorted.map(r => r.region), axisLabel: { fontSize: 10, color: '#c8d6f0' }, axisLine: { lineStyle: { color: '#1a2744' } } },
        series: [
          {
            name: '热度', type: 'bar', barMaxWidth: 12,
            data: sorted.map(r => ({
              value: Math.log1p(r.heat),
              itemStyle: { color: r.negative_rate > 0.5 ? COLORS.neg : r.negative_rate > 0.3 ? COLORS.yellow : COLORS.cyan },
            })),
            label: { show: true, position: 'right', fontSize: 9, color: '#5a7299',
              formatter: p => sorted[p.dataIndex]?.negative_rate > 0.3 ? `⚠️${(sorted[p.dataIndex].negative_rate*100).toFixed(0)}%负` : '' },
          },
        ],
        tooltip: { formatter: p => `${p.name}<br/>热度: ${sorted.find(r=>r.region===p.name)?.heat?.toFixed(0)}<br/>负面率: ${(sorted.find(r=>r.region===p.name)?.negative_rate*100).toFixed(0)}%` },
      });
    }

    function updateMapChart(regionHeat) {
      if (!charts.map) return;
      if (!mapReady) {
        updateMapFallback(regionHeat);
        ensureMapRegistered().then(ok => ok && updateMapChart(regionHeat));
        return;
      }
      const points = regionHeat
        .filter(r => REGION_COORDS[r.region])
        .map(r => ({
          name: r.region,
          value: [...REGION_COORDS[r.region], Math.log1p(r.heat) * 10],
          negative_rate: r.negative_rate,
        }));

      const scatterData = regionHeat
        .filter(r => REGION_COORDS[r.region])
        .map(r => ({
          name: r.region,
          value: [...REGION_COORDS[r.region], r.count],
          negative_rate: r.negative_rate,
        }));

      charts.map.setOption({
        ...BASE_OPTS,
        geo: {
          map: 'china',
          roam: true,
          label: { show: false },
          itemStyle: { areaColor: '#0d1b3e', borderColor: '#1a3060', borderWidth: 0.8 },
          emphasis: { itemStyle: { areaColor: '#1a3060' }, label: { show: false } },
          zoom: 1.1,
        },
        visualMap: {
          min: 0, max: 100,
          show: true, orient: 'vertical',
          left: 5, bottom: 20,
          textStyle: { color: '#5a7299', fontSize: 10 },
          inRange: { color: ['#0d2b5e', '#1e5cba', '#06b6d4', '#f59e0b', '#ef4444'] },
          text: ['高', '低'],
        },
        series: [
          {
            type: 'heatmap', coordinateSystem: 'geo',
            data: points.map(p => ({ name: p.name, value: p.value })),
            pointSize: 30, blurSize: 25,
          },
          {
            type: 'effectScatter', coordinateSystem: 'geo',
            data: scatterData.filter(d => d.negative_rate > 0.5).map(d => ({
              name: d.name,
              value: d.value,
              itemStyle: { color: COLORS.neg },
            })),
            symbolSize: val => Math.max(6, Math.min(18, val[2] * 0.8)),
            rippleEffect: { brushType: 'fill', scale: 3 },
            label: { show: true, formatter: '{b}', fontSize: 9, color: COLORS.neg, position: 'right' },
          },
          {
            type: 'scatter', coordinateSystem: 'geo',
            data: scatterData.filter(d => d.negative_rate <= 0.5),
            symbolSize: val => Math.max(4, Math.min(14, val[2] * 0.6)),
            itemStyle: { color: COLORS.cyan, opacity: 0.8 },
            label: { show: true, formatter: '{b}', fontSize: 9, color: COLORS.cyan, position: 'right' },
          },
        ],
        tooltip: {
          formatter: p => {
            if (!p.data) return '';
            const d = scatterData.find(s => s.name === p.data.name);
            return `<b>${p.data.name}</b><br/>帖子数: ${p.data.value[2]}<br/>负面率: ${d ? (d.negative_rate * 100).toFixed(0) + '%' : '-'}`;
          },
        },
      });
    }

    // ── 话题图谱 ────────────────────────────────────
    function updateGraphChart(topics) {
      if (!charts.graph || !topics.length) return;

      const nodes = topics.slice(0, 15).map((t, i) => ({
        id: t.id,
        name: t.label,
        value: t.heat,
        symbolSize: Math.max(20, Math.min(55, Math.log1p(t.heat) * 5)),
        category: t.sentiment_avg > 0.1 ? 0 : t.sentiment_avg < -0.1 ? 1 : 2,
        label: { show: true, fontSize: 10 },
        itemStyle: {
          color: t.sentiment_avg > 0.1 ? COLORS.pos : t.sentiment_avg < -0.1 ? COLORS.neg : COLORS.cyan,
          opacity: 0.9,
        },
      }));

      const nodeIds = new Set(nodes.map(n => n.id));
      const edges = [];
      topics.slice(0, 15).forEach(t => {
        (t.related || []).forEach(rel => {
          if (nodeIds.has(rel) && t.id !== rel) {
            edges.push({ source: t.id, target: rel, lineStyle: { opacity: 0.3, width: 1 } });
          }
        });
      });

      charts.graph.setOption({
        ...BASE_OPTS,
        series: [{
          type: 'graph',
          layout: 'force',
          roam: true,
          nodes,
          edges,
          force: { repulsion: 120, gravity: 0.05, edgeLength: [60, 120], layoutAnimation: false },
          label: { color: '#c8d6f0', fontSize: 10 },
          lineStyle: { color: '#1a2744', curveness: 0.2 },
          emphasis: { focus: 'adjacency' },
        }],
        tooltip: {
          formatter: p => p.dataType === 'node'
            ? `<b>${p.data.name}</b><br/>热度: ${p.data.value?.toFixed(0)}<br/>帖子: ${topics.find(t => t.id === p.data.id)?.post_count || 0}`
            : '',
        },
      });
    }

    // ── LLM 仪表盘 ──────────────────────────────────
    function updateLlmChart(llmStats) {
      if (!charts.llm || !llmStats) return;
      const ratio = llmStats.local_ratio || 0;
      charts.llm.setOption({
        ...BASE_OPTS,
        series: [{
          type: 'gauge', radius: '90%', center: ['50%', '60%'],
          startAngle: 180, endAngle: 0,
          min: 0, max: 1,
          pointer: { show: false },
          progress: { show: true, width: 10, itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: COLORS.cyan }, { offset: 1, color: COLORS.blue }] } } },
          axisLine: { lineStyle: { width: 10, color: [[1, '#1a2744']] } },
          axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
          detail: {
            valueAnimation: true,
            formatter: v => `${(v * 100).toFixed(0)}%\n本地`,
            fontSize: 12, color: COLORS.cyan, offsetCenter: [0, '-10%'],
          },
          data: [{ value: ratio }],
        }],
      });
    }

    // ── 全量更新 ────────────────────────────────────
    function applyWindowData(data) {
      const t = new Date().toLocaleTimeString('zh-CN', { hour12: false, second: '2-digit' });
      pushTs('times', t);
      pushTs('qps', data.current_qps || 0);
      pushTs('baseline', data.baseline_qps || 0);
      pushTs('sentiment', data.sentiment_avg_60s || 0);

      updateSentimentChart(data.sentiment_distribution || {});
      updatePlatformChart(data.platform_distribution || {});
      updateQpsChart();
      updateSentimentTs();
      updateMapChart(data.region_heat || []);
      updateGraphChart(data.top_topics || []);
    }

    // ── WebSocket ────────────────────────────────────
    let ws = null;
    let reconnectTimer = null;

    function connectWs() {
      const wsUrl = `ws://${location.host}/ws`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => { wsConnected.value = true; };

      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === 'init' || msg.type === 'window') {
          applyWindowData(msg.data);
        } else if (msg.type === 'post') {
          recentPosts.value.unshift(msg.data);
          if (recentPosts.value.length > 30) recentPosts.value.pop();
        } else if (msg.type === 'alert') {
          activeAlerts.value.unshift(msg.data);
          if (activeAlerts.value.length > 10) activeAlerts.value.pop();
        }
      };

      ws.onclose = () => {
        wsConnected.value = false;
        reconnectTimer = setTimeout(connectWs, 3000);
      };

      ws.onerror = () => ws.close();
    }

    // ── HTTP 轮询（WebSocket 断开时的降级）────────────
    async function pollStats() {
      try {
        const [statsRes, postsRes, alertsRes] = await Promise.all([
          fetch('/api/stats').then(r => r.json()),
          fetch('/api/posts?limit=20').then(r => r.json()),
          fetch('/api/alerts').then(r => r.json()),
        ]);
        stats.value = statsRes;
        recentPosts.value = postsRes;
        activeAlerts.value = alertsRes.active || [];
        applyWindowData(statsRes);
        updateLlmChart(statsRes.llm_stats);
      } catch (_) {}
    }

    // ── 确认告警 ────────────────────────────────────
    async function ackAlert(id) {
      await fetch(`/api/alerts/${id}/ack`, { method: 'POST' });
      activeAlerts.value = activeAlerts.value.filter(a => a.id !== id);
    }

    // ── 生命周期 ────────────────────────────────────
    let clockTimer, pollTimer;

    onMounted(() => {
      // 初始化图表（延迟确保 DOM 尺寸已计算完成）
      setTimeout(() => {
        charts.sentiment   = initChart('chart-sentiment');
        charts.platform    = initChart('chart-platform');
        charts.qps         = initChart('chart-qps');
        charts.sentimentTs = initChart('chart-sentiment-ts');
        charts.map         = initChart('chart-map');
        charts.graph       = initChart('chart-graph');
        charts.llm         = initChart('chart-llm');
        // 预加载中国地图
        ensureMapRegistered();
      }, 100);

      connectWs();

      // 时钟
      currentTime.value = fmtTime();
      clockTimer = setInterval(() => { currentTime.value = fmtTime(); }, 1000);

      // HTTP 轮询（每5秒同步全量状态 + LLM仪表盘）
      pollStats();
      pollTimer = setInterval(() => {
        pollStats();
        if (stats.value.llm_stats) updateLlmChart(stats.value.llm_stats);
      }, 5000);
    });

    onUnmounted(() => {
      ws?.close();
      clearTimeout(reconnectTimer);
      clearInterval(clockTimer);
      clearInterval(pollTimer);
    });

    return { wsConnected, currentTime, stats, recentPosts, activeAlerts, sentimentClass, ackAlert };
  },
});

app.mount('#app');
