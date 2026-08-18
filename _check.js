const { createApp, ref, computed, onMounted, reactive, watch, nextTick } = Vue;

const app = createApp({
  setup() {
    const API_BASE = '';
    
    // Navigation
    const currentPage = ref('dashboard');
    const currentPageTitles = {
      soil: '🪣 土壤数据',
      phenology: '📅 物候期',
      emergence: '🌱 出苗调查',
      agronomic: '🌿 农艺性状',
      physiological: '🔬 生理指标',
      yield: '🌾 产量数据',
      quality: '🏆 品质数据'
    };
    const currentPageDescriptions = {
      soil: '土壤基础理化性质测定',
      phenology: '小麦生长发育期记录',
      emergence: '出苗情况调查',
      agronomic: '农艺性状测定',
      physiological: '生理生化指标测定',
      yield: '产量构成因素测定',
      quality: '籽粒品质测定'
    };
    
    // Data
    const bases = ref([]);
    const plots = ref([]);
    const dashboardData = ref(null);
    const operations = ref([]);

    // Map view
    const baseViewMode = ref('list');
    const viewBtnStyle = {
      padding: '8px 16px',
      border: '1px solid #ddd',
      background: 'white',
      color: '#666',
      cursor: 'pointer',
      borderRadius: '6px',
      marginRight: '8px'
    };
    const viewBtnActiveStyle = {
      padding: '8px 16px',
      border: '1px solid #3498db',
      background: '#3498db',
      color: 'white',
      cursor: 'pointer',
      borderRadius: '6px',
      marginRight: '8px'
    };
    const mapInstance = ref(null);
    const baseMarkers = ref([]);

    // Filters
      const selectedBaseFilter = ref('');
      const baseDetails = ref(null);
      const weatherData = ref(null);
      const selectedDataBase = ref('');
    const selectedPlotCode = ref('');
    const soilPhase = ref('播前');
    const operationBase = ref('');
    
    // Forms
    const baseForm = reactive({ base_code: '', base_name: '', admin_code: '', address: '', latitude: null, longitude: null, remarks: '' });
    const plotForm = reactive({ base_code: '', block: '', treatment: 'CK', plot_code: '', area_m2: 20, field_name: '' });
    const newOp = reactive({ date: '', op_type: '', plot_code: '', block: '', treatment: '', weather: '', temperature: null, operator: '', remarks: '' });
    const initForm = reactive({ base_code: '', blocks: 3, treatments: 6 });
    
    // Modals
    const modal = reactive({ show: false, type: '', title: '', editTarget: null });
    const qrCodeDataUrl = ref('');
    const qrPlot = ref(null);
    const qrUrl = ref('');
    
    // Export
    const exportBase = ref('');
    const exportTable = ref('soil_data');
    const exportData = ref([]);
    
    // Constants
    const treatmentCodes = [
      { code: 'CK', name: '空白对照', color: '#E8E8E8', fe_total: 0, fe_unit: 'g/亩' },
      { code: 'FS', name: '硫酸亚铁对照', color: '#DAE8FC', fe_total: 2000, fe_unit: 'g/亩' },
      { code: 'NF-0.5', name: '纳米铁半量', color: '#E1F5D5', fe_total: 0.5, fe_unit: 'g/亩' },
      { code: 'NF-1.0', name: '纳米铁标准量', color: '#D5E8D4', fe_total: 1.0, fe_unit: 'g/亩' },
      { code: 'NF-1.5', name: '纳米铁1.5倍量', color: '#C8E6C9', fe_total: 1.5, fe_unit: 'g/亩' },
      { code: 'NF-2.0', name: '纳米铁2倍量', color: '#A5D6A7', fe_total: 2.0, fe_unit: 'g/亩' }
    ];
    const blockNames = ['I', 'II', 'III'];
    const opTypes = ['拌种', '拔节期喷施', '灌浆期喷施', '播种', '灌溉', '施肥（基肥）', '除草', '病虫害防治', '取样', '调查/测定', '其他'];
    const weatherOptions = ['晴', '多云', '阴', '小雨', '中雨', '大雨', '雾', '雪', '大风'];
    const tableNames = {
        soil_data: '土壤数据',
        phenology: '物候期',
        emergence: '出苗调查',
        agronomic_traits: '农艺性状',
        physiological: '生理指标',
        yield_data: '产量数据',
        quality_data: '品质数据',
        operation_log: '操作日志',
        soil: '土壤数据',
        phenology_data: '物候期',
        emergence_data: '出苗调查',
        agronomic: '农艺性状',
        physiological_data: '生理指标'
      };
      
      function getTableName(tableName) {
        return tableNames[tableName] || tableName;
      }

      // 天气代码转图标 (Open-Meteo WMO weather interpretation codes)
      function getWeatherIcon(code) {
        const icons = {
          0: '☀️',  // 晴
          1: '🌤️', 2: '⛅', 3: '☁️',  // 多云/阴
          45: '🌫️', 48: '🌫️',  // 雾
          51: '🌦️', 53: '🌦️', 55: '🌧️',  // 毛毛雨
          56: '🌧️', 57: '🌧️',  // 冻毛毛雨
          61: '🌧️', 63: '🌧️', 65: '🌧️',  // 雨
          66: '🌧️', 67: '🌧️',  // 冻雨
          71: '🌨️', 73: '🌨️', 75: '🌨️',  // 雪
          77: '❄️',  // 雪粒
          80: '🌦️', 81: '🌧️', 82: '⛈️',  // 阵雨
          85: '🌨️', 86: '🌨️',  // 阵雪
          95: '⛈️',  // 雷暴
          96: '⛈️', 99: '⛈️'  // 雷暴伴冰雹
        };
        return icons[code] || '🌤️';
      }

      // 获取天气趋势数据 (前3天 + 今天 + 未来7天，共11天)
      function getWeatherTrendData(daily) {
        if (!daily || !daily.length) return [];
        
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const todayStr = formatLocalDate(today);
        
        // 确保按日期排序
        const sorted = [...daily].sort((a, b) => 
          new Date(a.record_date) - new Date(b.record_date)
        );
        
        // 找到今天的位置，截取前3天+未来7天
        let todayIdx = sorted.findIndex(d => d.record_date === todayStr);
        let startIdx, endIdx;
        if (todayIdx >= 0) {
          startIdx = Math.max(0, todayIdx - 3);
          endIdx = Math.min(sorted.length, todayIdx + 8);
        } else {
          // 如果找不到今天，就按日期顺序取前3天+未来7天或全部
          startIdx = 0;
          endIdx = Math.min(sorted.length, 11);
        }
        
        const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
        
        const result = sorted.slice(startIdx, endIdx).map(day => {
          const date = new Date(day.record_date + 'T00:00:00');
          const diffDays = Math.round((date.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
          const month = date.getMonth() + 1;
          const d = date.getDate();
          const weekday = weekdays[date.getDay()];
          
          // 日期标签：昨天/今天/明天/周一/周二...
          let dayLabel;
          if (diffDays === -1) dayLabel = '昨天';
          else if (diffDays === 0) dayLabel = '今天';
          else if (diffDays === 1) dayLabel = '明天';
          else if (diffDays === 2) dayLabel = '后天';
          else dayLabel = weekday;
          
          const precipProb = day.precipitation_probability != null ? day.precipitation_probability : null;
          
          return {
            date: day.record_date,
            dateMD: `${String(month).padStart(2,'0')}/${String(d).padStart(2,'0')}`,
            dayLabel: dayLabel,
            diffDays: diffDays,
            isToday: diffDays === 0,
            isPast: diffDays < 0,
            maxTemp: Math.round(day.temperature_max || 0),
            minTemp: Math.round(day.temperature_min || 0),
            code: day.weather_code,
            desc: day.weather_description || '',
            precipProb: precipProb,
            precipSum: day.precipitation_sum
          };
        });
        
        return result;
      }

      // 本地日期字符串 yyyy-mm-dd (避免UTC时区偏差)
      function formatLocalDate(dateObj) {
        const y = dateObj.getFullYear();
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const d = String(dateObj.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
      }

      // ========= 天气折线图辅助函数 (HTML圆点+SVG连线，完美对齐) =========
      // 容器固定高度130px，绘图区在 Y=30~115 之间 (85px高度)
      const PLOT_CONTAINER_H = 130;
      const PLOT_TOP_PX = 30;
      const PLOT_BOTTOM_PX = 115;
      const PLOT_H_PX = PLOT_BOTTOM_PX - PLOT_TOP_PX; // 85

      function _chartData(daily) {
        return getWeatherTrendData(daily);
      }

      function _chartTempRange(daily) {
        const data = _chartData(daily);
        if (!data.length) return { max: 30, min: 10 };
        let maxT = -Infinity, minT = Infinity;
        data.forEach(d => {
          if (d.maxTemp > maxT) maxT = d.maxTemp;
          if (d.minTemp < minT) minT = d.minTemp;
        });
        const pad = Math.max(3, Math.round((maxT - minT) * 0.2));
        return { max: maxT + pad, min: minT - pad };
      }

      // 温度 -> 130px容器内的绝对Y像素 (用于HTML圆点)
      function tempPixelY(temp, daily) {
        const range = _chartTempRange(daily);
        const span = range.max - range.min || 1;
        const tNorm = (temp - range.min) / span;
        return PLOT_BOTTOM_PX - PLOT_H_PX * tNorm;
      }

      // SVG连线点: X=0~100百分比(列中心), Y=0~130和容器像素对应
      function chartLinePoints(daily, type) {
        const data = _chartData(daily);
        if (!data.length) return '';
        const n = data.length;
        return data.map((d, idx) => {
          const x = ((idx + 0.5) / n) * 100;
          const temp = type === 'max' ? d.maxTemp : d.minTemp;
          const y = tempPixelY(temp, daily);
          return `${x.toFixed(2)},${y.toFixed(1)}`;
        }).join(' ');
      }

      function chartPastLinePoints(daily, type) {
        const data = _chartData(daily);
        if (!data.length) return '';
        const n = data.length;
        const hasPast = data.some(d => d.isPast);
        if (!hasPast) return '';
        return data.map((d, idx) => {
          if (!d.isPast) return null;
          const x = ((idx + 0.5) / n) * 100;
          const temp = type === 'max' ? d.maxTemp : d.minTemp;
          const y = tempPixelY(temp, daily);
          return `${x.toFixed(2)},${y.toFixed(1)}`;
        }).filter(Boolean).join(' ');
      }

      // 卡片颜色映射
      const cardColorMap = {
        soil_data: 'stat-card-green',
        soil: 'stat-card-green',
        phenology: 'stat-card-orange',
        phenology_data: 'stat-card-orange',
        emergence: 'stat-card-teal',
        emergence_data: 'stat-card-teal',
        agronomic_traits: 'stat-card-indigo',
        agronomic: 'stat-card-indigo',
        physiological: 'stat-card-purple',
        physiological_data: 'stat-card-purple',
        yield_data: 'stat-card-amber',
        quality_data: 'stat-card-rose',
        operation_log: 'stat-card-cyan'
      };
      
      // 图标映射
      const cardIconMap = {
        soil_data: '🪴',
        soil: '🪴',
        phenology: '🌸',
        phenology_data: '🌸',
        emergence: '🌱',
        emergence_data: '🌱',
        agronomic_traits: '📏',
        agronomic: '📏',
        physiological: '🧪',
        physiological_data: '🧪',
        yield_data: '🌾',
        quality_data: '🏆',
        operation_log: '📝'
      };
      
      function getStatCardClass(key) {
        return cardColorMap[key] || 'stat-card-blue';
      }
      
      function getStatIcon(key) {
        return cardIconMap[key] || '📊';
      }
    
    // Form field definitions
    const currentFormFields = computed(() => {
      const fields = {
        soil: [
          [{ key: 'ph', label: 'pH', type: 'number', step: '0.1' }, { key: 'fe_available', label: '有效铁(mg/kg)', type: 'number', step: '0.1' }, { key: 'fe_total', label: '全铁(g/kg)', type: 'number', step: '0.1' }],
          [{ key: 'organic_matter', label: '有机质(g/kg)', type: 'number', step: '0.1' }, { key: 'p_available', label: '有效磷(mg/kg)', type: 'number', step: '0.1' }, { key: 'k_available', label: '速效钾(mg/kg)', type: 'number', step: '0.1' }],
          [{ key: 'cec', label: 'CEC(cmol/kg)', type: 'number', step: '0.1' }, { key: 'bulk_density', label: '容重(g/cm³)', type: 'number', step: '0.01' }]
        ],
        phenology: [
          [{ key: 'sowing', label: '播种期', type: 'date' }, { key: 'emergence', label: '出苗期', type: 'date' }, { key: 'tillering', label: '分蘖期', type: 'date' }],
          [{ key: 'overwinter', label: '越冬期', type: 'date' }, { key: 'regreening', label: '返青期', type: 'date' }, { key: 'jointing', label: '拔节期', type: 'date' }],
          [{ key: 'heading', label: '抽穗期', type: 'date' }, { key: 'flowering', label: '开花期', type: 'date' }, { key: 'maturity', label: '成熟期', type: 'date' }]
        ],
        emergence: [
          [{ key: 'seeds_sown', label: '播种粒数', type: 'number' }, { key: 'emerged_7d', label: '7天出苗数', type: 'number' }, { key: 'rate_7d', label: '7天出苗率(%)', type: 'number', step: '0.1' }],
          [{ key: 'emerged_14d', label: '14天出苗数', type: 'number' }, { key: 'rate_14d', label: '14天出苗率(%)', type: 'number', step: '0.1' }, { key: 'basic_seedlings', label: '基本苗数', type: 'number', step: '0.1' }]
        ],
        agronomic: [
          [{ key: 'tillers_prewinter', label: '越冬前分蘖', type: 'number', step: '0.1' }, { key: 'tillers_postregreen', label: '返青后分蘖', type: 'number', step: '0.1' }, { key: 'tillers_jointing', label: '拔节期分蘖', type: 'number', step: '0.1' }],
          [{ key: 'plant_height', label: '株高(cm)', type: 'number', step: '0.1' }, { key: 'lai_jointing', label: '拔节期LAI', type: 'number', step: '0.1' }, { key: 'lai_heading', label: '抽穗期LAI', type: 'number', step: '0.1' }],
          [{ key: 'dry_weight_jointing', label: '拔节期干重(g/株)', type: 'number', step: '0.1' }, { key: 'dry_weight_heading', label: '抽穗期干重(g/株)', type: 'number', step: '0.1' }, { key: 'dry_weight_maturity', label: '成熟期干重(g/株)', type: 'number', step: '0.1' }]
        ],
        physiological: [
          [{ key: 'spad_jointing', label: '拔节期SPAD', type: 'number', step: '0.1' }, { key: 'spad_heading', label: '抽穗期SPAD', type: 'number', step: '0.1' }, { key: 'spad_filling', label: '灌浆期SPAD', type: 'number', step: '0.1' }],
          [{ key: 'photo_rate_heading', label: '抽穗期光合速率', type: 'number', step: '0.01' }, { key: 'photo_rate_filling', label: '灌浆期光合速率', type: 'number', step: '0.01' }, { key: 'active_fe_jointing', label: '拔节期活性铁', type: 'number', step: '0.1' }],
          [{ key: 'active_fe_filling', label: '灌浆期活性铁', type: 'number', step: '0.1' }, { key: 'cat', label: 'CAT活性', type: 'number', step: '0.01' }, { key: 'pod', label: 'POD活性', type: 'number', step: '0.01' }]
        ],
        yield: [
          [{ key: 'spikes_per_mu', label: '亩穗数(万穗/亩)', type: 'number', step: '0.1' }, { key: 'grains_per_spike', label: '穗粒数(粒/穗)', type: 'number', step: '0.1' }, { key: 'thousand_grain_wt_1', label: '千粒重第1组(g)', type: 'number', step: '0.01' }],
          [{ key: 'thousand_grain_wt_2', label: '千粒重第2组(g)', type: 'number', step: '0.01' }, { key: 'actual_yield', label: '实际产量(kg/亩)', type: 'number', step: '0.1' }, { key: 'harvest_index', label: '收获指数', type: 'number', step: '0.01' }]
        ],
        quality: [
          [{ key: 'grain_protein', label: '籽粒蛋白质(%)', type: 'number', step: '0.1' }, { key: 'wet_gluten', label: '湿面筋(%)', type: 'number', step: '0.1' }, { key: 'sds_sedimentation', label: 'SDS沉降值(mL)', type: 'number', step: '0.1' }],
          [{ key: 'grain_fe', label: '籽粒铁含量(mg/kg)', type: 'number', step: '0.1' }, { key: 'flour_fe', label: '面粉铁含量(mg/kg)', type: 'number', step: '0.1' }]
        ]
      };
      return fields[currentPage.value] || [];
    });
    
    const currentTableColumns = computed(() => {
      const fieldGroups = currentFormFields.value;
      const columns = [];
      fieldGroups.forEach(group => {
        group.forEach(field => {
          columns.push({ key: field.key, label: field.label });
        });
      });
      return columns;
    });
    
    const currentRecords = ref([]);
    const formData = reactive({});
    
    const filteredPlots = computed(() => {
      if (!selectedDataBase.value) return plots.value;
      return plots.value.filter(p => p.base_code === selectedDataBase.value);
    });
    
    // API methods
    async function api(method, url, data = null) {
      const opts = { method, headers: { 'Content-Type': 'application/json' } };
      if (data) opts.body = JSON.stringify(data);
      const res = await fetch(API_BASE + url, opts);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.message || '请求失败');
      }
      return res.json();
    }
    
    async function loadDashboard() {
      try {
        const res = await api('GET', '/api/v1/dashboard');
        dashboardData.value = res.data;
      } catch (e) { console.error('Dashboard error:', e); }
    }
    
    async function loadBases() {
      try {
        const res = await api('GET', '/api/v1/bases');
        bases.value = res.data || [];
      } catch (e) { console.error('Bases error:', e); }
    }
    
    function viewBaseDetail(base) {
      selectedBaseFilter.value = base.base_code;
      currentPage.value = 'plots';
      loadBaseDetails(base.base_code);
      loadPlots();
    }
    
    async function onBaseFilterChange() {
      if (selectedBaseFilter.value) {
        await loadBaseDetails(selectedBaseFilter.value);
      } else {
        baseDetails.value = null;
      }
      await loadPlots();
    }
    
    async function loadBaseDetails(baseCode) {
      try {
        const res = await api('GET', `/api/v1/bases/${baseCode}/details`);
        baseDetails.value = res.data;
      } catch (e) {
        console.error('Base details error:', e);
        baseDetails.value = null;
      }
      // 加载天气数据
      await loadWeather(baseCode);
    }
    
    async function loadWeather(baseCode) {
      try {
        const res = await api('GET', `/api/v1/bases/${baseCode}/weather?days=7`);
        weatherData.value = res.data;
      } catch (e) {
        console.error('Weather error:', e);
        weatherData.value = null;
      }
    }
    
    async function refreshWeather() {
      if (selectedBaseFilter.value) {
        await loadWeather(selectedBaseFilter.value);
      }
    }
    
    async function loadPlots() {
      try {
        const url = selectedBaseFilter.value ? `/api/v1/plots?base_code=${selectedBaseFilter.value}` : '/api/v1/plots';
        const res = await api('GET', url);
        plots.value = res.data || [];
      } catch (e) { console.error('Plots error:', e); }
    }
    
    async function loadOperations() {
      try {
        const url = operationBase.value ? `/api/v1/table/operation_log?base_code=${operationBase.value}` : '/api/v1/table/operation_log';
        const res = await api('GET', url);
        operations.value = res.data || [];
      } catch (e) { console.error('Operations error:', e); }
    }
    
    async function loadDataRecords() {
      if (!currentPage.value || currentPage.value === 'dashboard' || currentPage.value === 'bases' || 
          currentPage.value === 'plots' || currentPage.value === 'operations' || currentPage.value === 'export') return;
      try {
        const table = currentPage.value === 'soil' ? 'soil_data' : currentPage.value;
        const url = selectedDataBase.value ? `/api/v1/table/${table}?base_code=${selectedDataBase.value}` : `/api/v1/table/${table}`;
        const res = await api('GET', url);
        currentRecords.value = res.data || [];
      } catch (e) { console.error('Data error:', e); currentRecords.value = []; }
    }
    
    async function loadCurrentRecord() {
      if (!selectedPlotCode.value) {
        Object.keys(formData).forEach(k => delete formData[k]);
        return;
      }
      try {
        const plot = plots.value.find(p => p.plot_code === selectedPlotCode.value);
        if (!plot) return;
        const table = currentPage.value === 'soil' ? 'soil_data' : currentPage.value;
        const url = table === 'soil_data' 
          ? `/api/v1/table/${table}` 
          : `/api/v1/table/${table}`;
        const res = await api('GET', url);
        const records = res.data || [];
        let record;
        if (table === 'soil_data') {
          record = records.find(r => r.plot_code === selectedPlotCode.value && r.phase === soilPhase.value);
        } else {
          record = records.find(r => r.plot_code === selectedPlotCode.value);
        }
        Object.keys(formData).forEach(k => delete formData[k]);
        if (record) {
          currentFormFields.value.forEach(group => {
            group.forEach(field => {
              formData[field.key] = record[field.key] ?? null;
            });
          });
        } else {
          currentFormFields.value.forEach(group => {
            group.forEach(field => {
              formData[field.key] = null;
            });
          });
        }
      } catch (e) { console.error('Load record error:', e); }
    }
    
    async function saveRecord() {
      if (!selectedPlotCode.value) { alert('请先选择小区'); return; }
      try {
        const table = currentPage.value === 'soil' ? 'soil_data' : currentPage.value;
        const payload = {
          plot_code: selectedPlotCode.value,
          data: {},
          extra: {}
        };
        currentFormFields.value.forEach(group => {
          group.forEach(field => {
            if (formData[field.key] !== null && formData[field.key] !== undefined && formData[field.key] !== '') {
              payload.data[field.key] = formData[field.key];
            }
          });
        });
        if (table === 'soil_data') {
          payload.extra = { phase: soilPhase.value };
        }
        await api('POST', `/api/v1/table/${table}`, payload);
        alert('✅ 保存成功！');
        loadDataRecords();
      } catch (e) {
        alert('❌ 保存失败：' + e.message);
      }
    }
    
    // Base CRUD
    function showBaseModal(base = null) {
        modal.type = 'base';
        modal.title = base ? '编辑基地' : '新增基地';
        modal.editTarget = base;
        if (base) {
          Object.assign(baseForm, {
            base_code: base.base_code || '',
            base_name: base.base_name || '',
            admin_code: base.admin_code || '',
            address: base.address || '',
            latitude: base.latitude || null,
            longitude: base.longitude || null,
            remarks: base.remarks || ''
          });
        } else {
          Object.assign(baseForm, { base_code: '', base_name: '', admin_code: '', address: '', latitude: null, longitude: null, remarks: '' });
        }
      modal.show = true;
    }
    
    async function saveBase() {
      if (!baseForm.base_code || !baseForm.base_name) {
        alert('请填写基地编号和名称'); return;
      }
      try {
        if (modal.editTarget) {
          await api('PUT', `/api/v1/bases/${baseForm.base_code}`, baseForm);
        } else {
          await api('POST', '/api/v1/bases', baseForm);
        }
        modal.show = false;
        await loadBases();
      } catch (e) { alert('❌ ' + e.message); }
    }
    
    async function deleteBase(base) {
      if (!confirm(`确定删除基地 "${base.base_name}" 及其所有小区吗？`)) return;
      try {
        await api('DELETE', `/api/v1/bases/${base.base_code}`);
        await loadBases();
        await loadPlots();
      } catch (e) { alert('❌ ' + e.message); }
    }
    
    // Plot CRUD
    function showPlotModal() {
      modal.type = 'plot';
      modal.title = '新增小区';
      if (bases.value.length) {
        Object.assign(plotForm, { base_code: bases.value[0].base_code, block: '', treatment: 'CK', plot_code: '', area_m2: 20, field_name: '' });
      }
      modal.show = true;
    }
    
    async function savePlot() {
      if (!plotForm.block || !plotForm.treatment) {
        alert('请填写区组和处理'); return;
      }
      if (!plotForm.plot_code) {
        plotForm.plot_code = `${plotForm.block}-${plotForm.treatment}`;
      }
      try {
        await api('POST', '/api/v1/plots', plotForm);
        modal.show = false;
        await loadPlots();
      } catch (e) { alert('❌ ' + e.message); }
    }
    
    async function deletePlot(plot) {
      if (!confirm(`确定删除小区 "${plot.plot_code}" 吗？`)) return;
      // Note: API doesn't have DELETE for plots yet, need to add
      alert('小区删除功能暂未实现');
    }
    
    function showInitModal() {
      if (!bases.value.length) {
        alert('请先创建一个试验基地');
        return;
      }
      initForm.base_code = bases.value[0].base_code;
      initForm.blocks = 3;
      initForm.treatments = 6;
      modal.type = 'init';
      modal.title = '初始化小区';
      modal.show = true;
    }
    
    async function doInitPlots() {
      const total = initForm.blocks * initForm.treatments;
      if (!confirm(`确定要创建 ${total} 个小区吗？\n基地: ${initForm.base_code}\n区组数: ${initForm.blocks}\n每区组处理数: ${initForm.treatments}`)) return;
      try {
        const payload = {
          base_code: initForm.base_code,
          num_blocks: initForm.blocks,
          num_treatments: initForm.treatments
        };
        const res = await api('POST', '/api/v1/plots/init', payload);
        alert(`✅ 成功初始化 ${res.data?.created || total} 个小区！`);
        modal.show = false;
        await loadPlots();
      } catch (e) {
        alert('❌ 初始化失败：' + e.message);
      }
    }
    
    async function initDefaultPlots() {
      showInitModal();
    }
    
    // Operations
    async function saveOperation() {
      if (!newOp.date || !newOp.op_type) {
        alert('请填写日期和操作类型'); return;
      }
      try {
        const payload = {
          plot_code: newOp.plot_code || null,
          data: {
            date: newOp.date,
            op_type: newOp.op_type,
            treatment: newOp.treatment,
            block: newOp.block,
            weather: newOp.weather,
            temperature: newOp.temperature,
            operator: newOp.operator,
            remarks: newOp.remarks
          }
        };
        await api('POST', '/api/v1/table/operation_log', payload);
        alert('✅ 保存成功！');
        Object.assign(newOp, { date: '', op_type: '', plot_code: '', block: '', treatment: '', weather: '', temperature: null, operator: '', remarks: '' });
        await loadOperations();
      } catch (e) { alert('❌ ' + e.message); }
    }
    
    // QR Code
    async function showQRCode(plot) {
      qrPlot.value = plot;
      qrUrl.value = `${window.location.origin}/mobile_entry?plot=${plot.plot_code}`;
      
      // Generate QR code using external API
      const qrContent = `${window.location.origin}/mobile_entry?plot=${plot.plot_code}`;
      qrCodeDataUrl.value = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrContent)}`;
      modal.type = 'qr';
      modal.title = '扫码录入';
      modal.show = true;
    }
    
    // Export
    async function exportExcel() {
      try {
        const url = exportBase.value 
          ? `/api/v1/export/excel?base_code=${exportBase.value}` 
          : '/api/v1/export/excel';
        const res = await fetch(API_BASE + url);
        if (!res.ok) throw new Error('导出失败');
        const blob = await res.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `wheat_data_${new Date().toISOString().slice(0,10)}.xlsx`;
        a.click();
        URL.revokeObjectURL(downloadUrl);
      } catch (e) { alert('❌ ' + e.message); }
    }
    
    async function loadExportData() {
      try {
        const url = exportBase.value 
          ? `/api/v1/table/${exportTable.value}?base_code=${exportBase.value}` 
          : `/api/v1/table/${exportTable.value}`;
        const res = await api('GET', url);
        exportData.value = res.data || [];
      } catch (e) { console.error('Export error:', e); exportData.value = []; }
    }
    
    // Helpers
    function getTreatmentColor(code) {
      const t = treatmentCodes.find(c => c.code === code);
      return t ? t.color : '#f0f0f0';
    }
    
    function getTreatmentName(code) {
      const t = treatmentCodes.find(c => c.code === code);
      return t ? t.name : code;
    }
    
    function getTagClass(value) {
      if (!value || value === '—') return '';
      const num = parseInt(value);
      if (num >= 80) return 'tag tag-success';
      if (num >= 50) return 'tag tag-warning';
      return 'tag tag-info';
    }
    
    function formatDate(dateStr) {
      if (!dateStr) return '—';
      const d = new Date(dateStr);
      const year = d.getFullYear();
      const month = d.getMonth() + 1;
      const day = d.getDate();
      return `${year}/${month}/${day}`;
    }
    
    function getPlotCodeById(plotId) {
      const plot = plots.value.find(p => p.id === plotId);
      return plot ? plot.plot_code : null;
    }
    
    // Map computed
    const basesWithCoords = computed(() => {
      return bases.value.filter(b => b.latitude && b.longitude);
    });

    // Map functions
    function switchToMapView() {
      baseViewMode.value = 'map';
      // v-show 切换后，等 DOM 更新再初始化地图（nextTick 在 JS 作用域内可用）
      nextTick(() => { initBaseMap(); });
    }

    function initBaseMap() {
      const container = document.getElementById('baseMap');
      if (!container) {
        // 容器尚不存在，延迟重试
        setTimeout(() => initBaseMap(), 200);
        return;
      }

      // 如果地图已存在，验证容器是否仍然有效（bases 页面用 v-if，
      // 离开后 DOM 会被销毁，旧实例的 _container 会变成失效引用）
      if (mapInstance.value) {
        const oldContainer = mapInstance.value.getContainer();
        // 容器不在文档中或已被移除，销毁旧实例以便重建
        if (!oldContainer || !document.body.contains(oldContainer)) {
          try { mapInstance.value.remove(); } catch (e) {}
          mapInstance.value = null;
          baseMarkers.value = [];
        } else {
          // 容器仍然有效，只需刷新标记并重算尺寸
          updateBaseMarkers();
          setTimeout(() => mapInstance.value && mapInstance.value.invalidateSize(), 200);
          return;
        }
      }

      // 确保容器有尺寸（v-show 切换后容器可能尚未布局完成）
      if (container.offsetWidth === 0 || container.offsetHeight === 0) {
        setTimeout(() => initBaseMap(), 200);
        return;
      }

      // 默认使用第一个有坐标的基地或中国中心
      const bases = basesWithCoords.value;
      if (bases.length > 0) {
        const first = bases[0];
        mapInstance.value = L.map('baseMap').setView([first.latitude, first.longitude], 10);
      } else {
        mapInstance.value = L.map('baseMap').setView([34.1234, 113.4567], 5);
      }

      // 使用 OpenStreetMap 瓦片（多个国内可访问镜像，自动回退）
      const tileLayers = [
        {
          url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
          options: { subdomains: 'abc', maxZoom: 19 }
        },
        {
          url: 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
          options: { subdomains: '1234', maxZoom: 18 }
        }
      ];

      // 主瓦片层：高德地图（国内访问稳定，中文标注）
      const primary = tileLayers[1];
      const baseLayer = L.tileLayer(primary.url, {
        subdomains: primary.options.subdomains,
        maxZoom: primary.options.maxZoom,
        attribution: '&copy; 高德地图',
        crossOrigin: true
      }).addTo(mapInstance.value);

      // 主瓦片加载失败时回退到 OSM
      baseLayer.on('tileerror', function() {
        if (!mapInstance.value._fallbackAdded) {
          mapInstance.value._fallbackAdded = true;
          const fallback = tileLayers[0];
          L.tileLayer(fallback.url, {
            subdomains: fallback.options.subdomains,
            maxZoom: fallback.options.maxZoom,
            attribution: '&copy; OpenStreetMap'
          }).addTo(mapInstance.value);
        }
      });

      updateBaseMarkers();

      // 强制重新计算地图尺寸（多次以确保切换动画完成后正确显示）
      [200, 500, 1000].forEach(delay => {
        setTimeout(() => {
          if (mapInstance.value) mapInstance.value.invalidateSize();
        }, delay);
      });
    }

    function updateBaseMarkers() {
      if (!mapInstance.value) return;
      baseMarkers.value.forEach(m => mapInstance.value.removeLayer(m));
      baseMarkers.value = [];
      basesWithCoords.value.forEach(base => {
        const marker = L.marker([base.latitude, base.longitude]).addTo(mapInstance.value);
        marker.bindPopup(`<strong>${base.base_name}</strong><br/>${base.address || ''}`);
        baseMarkers.value.push(marker);
      });
      if (baseMarkers.value.length > 0) {
        const group = L.featureGroup(baseMarkers.value);
        mapInstance.value.fitBounds(group.getBounds().pad(0.2));
      }
    }

    function focusBaseOnMap(base) {
      if (!mapInstance.value || !base.latitude || !base.longitude) return;
      mapInstance.value.setView([base.latitude, base.longitude], 15);
      const marker = baseMarkers.value.find(m => {
        const latLng = m.getLatLng();
        return latLng.lat === base.latitude && latLng.lng === base.longitude;
      });
      if (marker) marker.openPopup();
    }

    // Watch for page changes to load data
    watch(currentPage, async (newPage, oldPage) => {
      // 离开 bases 页面时清理地图实例（bases 页面用 v-if，DOM 会被销毁，
      // 残留的 Leaflet 实例会导致返回时地图无法重新初始化）
      if (oldPage === 'bases' && newPage !== 'bases') {
        if (mapInstance.value) {
          mapInstance.value.remove();
          mapInstance.value = null;
        }
        baseMarkers.value = [];
      }
      if (newPage === 'dashboard') {
        loadDashboard();
        loadPlots();
      } else if (newPage === 'bases') {
        loadBases();
        // 仅在地图视图下初始化地图，避免在 list 视图下对 display:none 容器做无意义的重试
        if (baseViewMode.value === 'map') {
          nextTick(() => { initBaseMap(); });
        }
      } else if (newPage === 'plots') {
        loadPlots();
        loadBases();
      } else if (newPage === 'operations') {
        loadOperations();
        loadPlots();
      } else if (newPage === 'export') {
        loadExportData();
        loadBases();
      } else if (['soil', 'phenology', 'emergence', 'agronomic', 'physiological', 'yield', 'quality'].includes(newPage)) {
        loadDataRecords();
        loadPlots();
      }
      // Reset selections
      selectedPlotCode.value = '';
      Object.keys(formData).forEach(k => delete formData[k]);
      currentRecords.value = [];
    });
    
    // Initial load
    onMounted(async () => {
      await loadBases();
      await loadPlots();
      await loadDashboard();
    });
    
    return {
      // Navigation
      currentPage, currentPageTitles, currentPageDescriptions,
      // Data
      bases, plots, dashboardData, operations,
      // Map view
      baseViewMode, viewBtnStyle, viewBtnActiveStyle, mapInstance, baseMarkers,
      // Filters
      selectedBaseFilter, selectedDataBase, selectedPlotCode, soilPhase, operationBase,
      // Forms
      baseForm, plotForm, newOp, formData,
      // Modals
      modal, qrCodeDataUrl, qrPlot, qrUrl,
      // Export
      exportBase, exportTable, exportData,
      // Constants
      treatmentCodes, blockNames, opTypes, weatherOptions, tableNames, getTableName, getStatCardClass, getStatIcon,
      // Computed
      currentFormFields, currentTableColumns, currentRecords, filteredPlots, basesWithCoords,
      // Methods
      showBaseModal, editBase: showBaseModal, saveBase, deleteBase,
      showPlotModal, savePlot, deletePlot, initDefaultPlots, showInitModal, doInitPlots,
      viewBaseDetail, onBaseFilterChange, loadWeather, refreshWeather,
      saveRecord, loadDataRecords, loadCurrentRecord,
      saveOperation,
      showQRCode, exportExcel, loadExportData,
      // Map methods
      initBaseMap, updateBaseMarkers, focusBaseOnMap, switchToMapView, nextTick,
      // Helpers
      getTreatmentColor, getTreatmentName, getTagClass, formatDate, getPlotCodeById, getWeatherIcon, getWeatherTrendData, formatLocalDate,
      // Weather chart helpers
      tempPixelY, chartLinePoints, chartPastLinePoints,
      // Forms
      initForm,
      // Data
      baseDetails, weatherData
    };
  }
});

app.mount('#app');