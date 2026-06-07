<script>
  import { fade, slide } from 'svelte/transition';
  import { onMount, onDestroy } from 'svelte';

  // --- 状态变量 ---
 let isListening = $state(false);           
let cameraStream = null;           // 流对象不需要响应式，保持普通变量
let videoElement = $state(undefined);  // 需要响应式，以便 $effect 追踪 DOM 绑定
let canvasElement;                 
let cameraActive = $state(false);          
let capturedImage = $state(null);          
let isIdentifying = $state(false);         
let identificationResult = $state(null);   
let recognitionFailed = $state(false);     
let recognitionDone = $state(false);       
let messages = $state([]);                 
let userInput = $state('');                
let chatContainer;                  // DOM 绑定，无需 $state
let detectedPatterns = $state([]);   // YOLO 实时检测结果
let isLoading = $state(false);       // AI 回复加载状态
let errorTip = $state('');           // 错误提示
let isStreaming = $state(false);     // 是否正在接收 LLM 流式输出
let streamingText = $state('');      // 当前流式输出中已累积的文本
let streamAbortController = null;    // 流式请求取消控制器
let isRecording = $state(false);     // 是否正在录音
let mediaRecorder = null;            // MediaRecorder 实例
let audioChunks = [];                // 录音数据块
let audioElement;                    // TTS 播放 <audio> 绑定
let ttsEnabled = $state(true);       // TTS 语音播报开关
let micStream = null;                // 录音媒体流

  // --- 语言切换 ---
  let lang = $state('zh');  // 'zh' | 'en'
  const t = {
    logo:          { zh: '苗绣·识裳', en: 'Miao Embroidery · Recognition' },
    camera:        { zh: '摄像头', en: 'Camera' },
    mic:           { zh: '麦克风', en: 'Mic' },
    aiModel:       { zh: 'AI模型', en: 'AI Model' },
    npu:           { zh: '算力加速', en: 'NPU Accel' },
    fpsLabel:      { zh: '帧率', en: 'FPS' },
    inferLabel:    { zh: '推理', en: 'Infer' },
    cpuLabel:      { zh: '算力', en: 'CPU' },
    preview:       { zh: '图像预览', en: 'Preview' },
    chatTitle:     { zh: '雅谈 · Qwen2.5-Instruct', en: 'Chat · Qwen2.5-Instruct' },
    quickTools:    { zh: '快捷功能', en: 'Quick Tools' },
    reference:     { zh: '参考图像', en: 'Reference' },
    captured:      { zh: '当前拍摄', en: 'Captured' },
    afterCapture:  { zh: '拍摄后显示', en: 'After capture' },
    culture:       { zh: '文化科普', en: 'Culture' },
    cultureTitle:  { zh: '苗族服饰文化', en: 'Miao Costume Culture' },
    cultureDesc:   { zh: '苗族银饰、刺绣、蜡染等传统技艺蕴藏着千年迁徙史诗与古老图腾信仰。', en: 'Miao silver, embroidery & batik embody a millennia-old migration epic and ancient totemic beliefs.' },
    quickAsk:      { zh: '快速提问', en: 'Quick Ask' },
    hornMeaning:   { zh: '银角寓意', en: 'Horn Meaning' },
    birdLegend:    { zh: '百鸟衣传说', en: 'Bird Coat Legend' },
    apronPatterns: { zh: '围腰花纹', en: 'Apron Patterns' },
    learnMore:     { zh: '了解更多苗绣类型', en: 'Learn More Types' },
    identifyBtn:   { zh: '识物（打开摄像头）', en: 'Identify (Open Camera)' },
    captureBtn:    { zh: '拍照', en: 'Capture' },
    closeBtn:      { zh: '关闭', en: 'Close' },
    yoloIdentify:  { zh: 'YOLOv8n 识别', en: 'YOLOv8n Identify' },
    identifying:   { zh: '识别中...', en: 'Identifying...' },
    retakeBtn:     { zh: '重新拍摄', en: 'Retake' },
    aimLens:       { zh: '请将苗绣服饰对准镜头', en: 'Aim Miao garment at lens' },
    liveDetecting: { zh: '实时检测中', en: 'Live' },
    patternsFound: { zh: '识别到', en: 'detected' },
    patternsUnit:  { zh: '个纹样', en: 'patterns' },
    capturedLabel: { zh: '已拍摄', en: 'Captured' },
    placeholderHint1: { zh: '点击下方按钮打开摄像头', en: 'Click button below to open camera' },
    placeholderHint2: { zh: '拍摄苗族服饰进行识别', en: 'Capture Miao garment to identify' },
    noObject:      { zh: '未识别到对象', en: 'No Object Detected' },
    noObjectDesc:  { zh: '请调整拍摄角度或光线后重新拍摄。', en: 'Adjust angle/lighting and retake.' },
    colorLabel:    { zh: '色彩', en: 'Color' },
    patternLabel:  { zh: '纹样', en: 'Pattern' },
    customLabel:   { zh: '习俗', en: 'Custom' },
    clearChat:     { zh: '清除', en: 'Clear' },
    girlName:      { zh: '苗族阿妹', en: 'Miao Girl AI' },
    girlDesc1:     { zh: '苗绣文化AI助手', en: 'Miao Embroidery AI' },
    girlDesc2:     { zh: '陪你识纹样、懂民俗、聊苗族文化', en: 'Identify patterns, learn folklore, chat culture' },
    startSession:  { zh: '开始会话', en: 'Start Session' },
    aiAssistant:   { zh: 'AI 助手', en: 'AI Assistant' },
    userLabel:     { zh: '用户', en: 'User' },
    inputPlaceholder: { zh: '输入苗绣相关问题...', en: 'Ask about Miao embroidery...' },
    sendBtn:       { zh: '发送', en: 'Send' },
    quickChat:     { zh: '快速会谈', en: 'Quick Chat' },
    meanings:      { zh: '纹样寓意', en: 'Meanings' },
    parts:         { zh: '服饰部件解析', en: 'Parts' },
    qa:            { zh: '苗绣提问', en: 'Q&A' },
    atlas:         { zh: '百苗图对照', en: 'Atlas' },
    listening:     { zh: '正在聆听...', en: 'Listening...' },
    voiceWake:     { zh: '语音唤醒助手', en: 'Voice Wake' },
    voiceInfo:     { zh: '全链路本地化 · ASR · TTS', en: 'All-local · ASR · LLM · TTS' },
    unknown:       { zh: '未知', en: 'Unknown' },
    errorEmpty:    { zh: '请输入提问内容', en: 'Please enter a question' },
    errorTimeout:  { zh: '模型响应超时，请重试', en: 'Model timeout, please retry' },
    welcomeZh:     { zh: '您好！我是"苗绣·识裳"助手。点击左下角"识物"按钮打开摄像头，调整角度后点击"拍照"按钮拍摄苗族服饰，我将使用 YOLOv8n 识别并调用 Qwen2.5-Instruct 为您解读其文化内涵。', en: '' },
    welcomeEn:     { zh: '', en: 'Hello! I am "Miao Embroidery · Recognition" assistant. Click "Identify" to open the camera, adjust the angle, then click "Capture" to photograph Miao garments. I will use YOLOv8n to identify and Qwen2.5-Instruct to explain the cultural significance.' },
    noDetectZh:    { zh: '⚠️ YOLOv8n 未检测到目标对象，请调整拍摄角度或光线后重新拍摄。', en: '' },
    noDetectEn:    { zh: '', en: '⚠️ No object detected by YOLOv8n. Please adjust the angle or lighting and retake.' },
    fallbackZh:    { zh: '我是您的苗族文化助手，熟悉银饰、刺绣、蜡染等传统服饰知识，您可以上传图片或直接提问。', en: '' },
    fallbackEn:    { zh: '', en: 'I am your Miao culture assistant, knowledgeable in silver ornaments, embroidery, batik and traditional costume. You may upload an image or ask a question directly.' },
    alertCameraZh: { zh: '无法访问摄像头，请检查权限或连接 USB 摄像头。', en: '' },
    alertCameraEn: { zh: '', en: 'Cannot access camera. Please check permissions or connect a USB camera.' },
    // 快捷提问话术（中/英分离）
    qHornZh:      { zh: '苗族银角有什么寓意？', en: '' },
    qHornEn:      { zh: '', en: 'What is the meaning of Miao silver horns?' },
    qBirdZh:      { zh: '百鸟衣的传说是什么？', en: '' },
    qBirdEn:      { zh: '', en: 'What is the legend of the Hundred-Bird Coat?' },
    qApronZh:     { zh: '围腰上的花纹代表什么？', en: '' },
    qApronEn:     { zh: '', en: 'What do the patterns on the apron represent?' },
    qTypesZh:     { zh: '请介绍一下苗族服饰的主要类型和特点', en: '' },
    qTypesEn:     { zh: '', en: 'Please introduce the main types and characteristics of Miao costumes' },
    qOutlineZh:   { zh: '请简要概述苗族服饰文化', en: '' },
    qOutlineEn:   { zh: '', en: 'Briefly outline Miao costume culture' },
    qSymbolZh:    { zh: '苗族服饰上的纹样有什么寓意？', en: '' },
    qSymbolEn:    { zh: '', en: 'What do the patterns on Miao costumes symbolize?' },
    qPartsZh:     { zh: '请详细解析苗族服饰的各个部件', en: '' },
    qPartsEn:     { zh: '', en: 'Please analyze each component of Miao costume in detail' },
    qLearnZh:     { zh: '我想了解苗绣的相关知识', en: '' },
    qLearnEn:     { zh: '', en: 'I want to learn about Miao embroidery' },
    qAtlasZh:     { zh: '请对照百苗图介绍苗族支系服饰', en: '' },
    qAtlasEn:     { zh: '', en: 'Please introduce Miao sub-group costumes with reference to the Bai Miao Atlas' },
    qButterflyZh: { zh: '讲解苗绣蝴蝶妈妈纹寓意', en: '' },
    qButterflyEn: { zh: '', en: 'Explain the Butterfly Mother motif in Miao embroidery' },
    qIntroZh:     { zh: '介绍苗族传统服饰特色', en: '' },
    qIntroEn:     { zh: '', en: 'Introduce the characteristics of Miao traditional costumes' },
    qPatternsZh:  { zh: '苗绣有哪些经典纹样', en: '' },
    qPatternsEn:  { zh: '', en: 'What are the classic patterns in Miao embroidery?' },
    qSilverZh:    { zh: '苗族银饰文化介绍', en: '' },
    qSilverEn:    { zh: '', en: 'Introduction to Miao silver ornament culture' },
    qVoice1Zh:    { zh: '苗族银角上的纹路代表什么？', en: '' },
    qVoice1En:    { zh: '', en: 'What do the patterns on Miao silver horns represent?' },
    qVoice2Zh:    { zh: '这件百鸟衣有什么来历？', en: '' },
    qVoice2En:    { zh: '', en: 'What is the origin of this Hundred-Bird Coat?' },
    qVoice3Zh:    { zh: '围腰上的涡旋有什么含义？', en: '' },
    qVoice3En:    { zh: '', en: 'What is the meaning of the spirals on the apron?' },
    qVoice4Zh:    { zh: '帮我介绍一下银项圈', en: '' },
    qVoice4En:    { zh: '', en: 'Tell me about Miao silver collars' },
  };
  function toggleLang() { lang = lang === 'zh' ? 'en' : 'zh'; }

  // --- 设备状态 ---
  let camOnline = $state(true);
  let micOnline = $state(true);
  let modelReady = $state(true);
  let npuReady = $state(true);

  // --- 实时监测指标 ---
  let fps = $state(28);              // 实时帧率
  let inferTime = $state(186);       // 最近一次推理耗时 (ms)
  let cpuUsage = $state(26);         // CPU / 算力占用率 (%)
  let memUsage = $state(0);          // 内存使用率 (%)
  let cpuTemp = $state(null);        // CPU 温度 (°C)
  let yoloAvgMs = $state(0);         // YOLO 平均推理延迟
  let yoloActive = $state(0);        // YOLO 当前处理数
  let llmActive = $state(0);         // LLM 当前处理数
  let backendLabel = $state('');     // 推理后端标签
  let fpsFrames = 0;
  let fpsLastTime = performance.now();
  let fpsAnimId = null;
  let monitorTimer = null;

  function startFpsMonitor() {
    fpsLastTime = performance.now();
    fpsFrames = 0;
    const tick = () => {
      fpsFrames++;
      const now = performance.now();
      const elapsed = now - fpsLastTime;
      if (elapsed >= 1000) {
        fps = Math.round(fpsFrames / (elapsed / 1000));
        fpsFrames = 0;
        fpsLastTime = now;
      }
      fpsAnimId = requestAnimationFrame(tick);
    };
    fpsAnimId = requestAnimationFrame(tick);
  }

  function startCpuMonitor() {
    // 实时拉取后端 /stats 接口获取多维性能指标
    const fetchStats = async () => {
      try {
        const resp = await fetch('/stats');
        if (resp.ok) {
          const data = await resp.json();
          cpuUsage = data.cpu_percent ?? cpuUsage;
          memUsage = data.mem_percent ?? memUsage;
          cpuTemp = data.cpu_temp ?? cpuTemp;
          yoloAvgMs = data.yolo_latency?.avg_ms ?? yoloAvgMs;
          yoloActive = data.yolo_queue?.active_requests ?? yoloActive;
          llmActive = data.llm_queue?.active_requests ?? llmActive;
          backendLabel = data.yolo_backend || data.backend || backendLabel;
        }
      } catch {
        // 网络异常时保持上一次有效值
      }
    };
    fetchStats(); // 立即拉取一次
    monitorTimer = setInterval(fetchStats, 2000);
  }

  function stopMonitors() {
    if (fpsAnimId) cancelAnimationFrame(fpsAnimId);
    if (monitorTimer) clearInterval(monitorTimer);
  }

  // --- YOLOv8n API 配置 ---
  // 一体化部署：前端与 YOLO API 同端口同域，始终使用相对路径
  const YOLO_API_URL = '/detect';
  const LLM_API_URL = '/chat';           // Qwen2.5-Instruct 对话 API
  const LLM_STREAM_URL = '/chat/stream';  // 流式对话（可选）
  
  // YOLO 通用类别名 → 苗族服饰知识库映射（用于 COCO 预训练模型的检测结果翻译）
  // 实际项目中应使用自定义训练的苗族服饰 YOLO 模型
  const yoloLabelMap = {
    'hat': '苗族银角头饰 Miao Silver Horn',
    'tie': '苗族银项圈 Miao Silver Collar',
    'backpack': '苗族百鸟衣 Miao Bird Coat',
    'apron': '苗族绣花围腰 Miao Embroidered Apron',
    // 可扩展更多映射 more mappings can be added
  };

  // 将 base64 Data URL 转为 Blob（用于 FormData 上传）
  function dataURLtoBlob(dataURL) {
    const parts = dataURL.split(',');
    const mime = parts[0].match(/:(.*?);/)?.[1] || 'image/jpeg';
    const bytes = atob(parts[1]);
    const buffer = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) {
      buffer[i] = bytes.charCodeAt(i);
    }
    return new Blob([buffer], { type: mime });
  }

  // --- 苗族服饰知识库（仅展示用，真实场景由 Qwen2.5-Instruct 生成） ---
  const miaoKnowledge = {
    '苗族银角头饰': {
      type: '苗族银角头饰 Miao Silver Horn Headdress',
      confidence: 98.2,
      color: '银白为主，间以靛蓝衬底 Silver-white with indigo blue base',
      pattern: '牛角纹、太阳芒纹、涡旋纹 Ox horn, sun ray, spiral patterns',
      meaning: '银角是苗族最重要的头饰之一，源于蚩尤部落的牛图腾崇拜。牛角象征力量与祖先庇护，银角上錾刻的太阳芒纹寓意生命轮回，涡旋纹则记录着苗族先民跨越江河的迁徙史诗。\n\nThe silver horn is a paramount Miao headdress, rooted in the ox totem worship of the Chiyou tribe. Horns symbolize strength and ancestral protection; sun-ray engravings signify the cycle of life; spiral motifs chronicle the epic migration of Miao ancestors across rivers.',
      custom: '每逢“鼓藏节”，苗族姑娘佩戴全套银角、银冠、银项圈，重达十余斤，行走时银铃作响，被认为可以驱邪纳福。\n\nDuring the Guzang Festival, Miao girls don full silver sets weighing 5+ kg — the tinkling of silver bells is believed to ward off evil and bring blessings.',
    },
    '苗族百鸟衣': {
      type: '苗族百鸟衣 Miao Hundred-Bird Coat',
      confidence: 96.8,
      color: '黑底彩绣，以红、绿、金为主 Black base with red, green, gold embroidery',
      pattern: '百鸟纹、蝶恋花纹、龙纹 Hundred-bird, butterfly-and-flower, dragon motifs',
      meaning: '百鸟衣是苗族“牯脏节”祭祖盛装，衣上绣满百鸟朝凤图。苗族传说中，百鸟曾帮助苗族始祖从洪水中逃生，因此鸟纹代表着救赎与吉祥。蝴蝶纹则指向“蝴蝶妈妈”创世神话。\n\nThe Hundred-Bird Coat is the ceremonial attire for the Miao Guzang Festival ancestor worship, embroidered with birds paying homage to the phoenix. In Miao legend, birds helped the first ancestor escape a great flood, so bird motifs symbolize salvation and auspiciousness. Butterfly patterns reference the Butterfly Mother creation myth.',
      custom: '一件百鸟衣需要数十位绣娘耗费数年手工绣制，绣法包含破线绣、打籽绣、马尾绣等十余种技法。\n\nA single Hundred-Bird Coat takes dozens of embroiderers several years to complete, using over ten techniques including split-thread stitch, seed stitch, and horsehair embroidery.',
    },
    '苗族绣花围腰': {
      type: '苗族绣花围腰 Miao Embroidered Apron',
      confidence: 94.5,
      color: '靛蓝底，五彩丝线绣 Indigo base with multicolor silk embroidery',
      pattern: '涡旋纹、铜鼓纹、石榴花纹 Spiral, bronze drum, pomegranate flower patterns',
      meaning: '围腰上的涡旋纹代表江河，记录苗族从黄河、长江到云贵高原的迁徙路线；铜鼓纹象征太阳与权威；石榴花则寄托多子多福的愿望。\n\nThe spiral patterns on the apron represent rivers, recording the Miao migration route from the Yellow River and Yangtze to the Yunnan-Guizhou Plateau; bronze drum motifs symbolize the sun and authority; pomegranate flowers embody wishes for fertility and blessings.',
      custom: '围腰是苗族女子日常必备，不同支系的围腰长度、纹样差异显著，是识别支系身份的“活族谱”。\n\nThe apron is a daily essential for Miao women; significant variations in length and pattern across different sub-groups make it a “living genealogy” for identifying branch affiliations.',
    },
    '苗族银项圈': {
      type: '苗族银项圈 Miao Silver Collar',
      confidence: 97.1,
      color: '纯银，偶有鎏金点缀 Pure silver, occasionally gilt-accented',
      pattern: '二龙抢宝、游鱼纹、乳钉纹 Two dragons contesting a pearl, swimming fish, nipple-stud patterns',
      meaning: '银项圈层层叠戴，象征女子家族的财富与地位。二龙抢宝图案寓意守护与尊贵，游鱼纹代表生育繁衍，乳钉纹则源于古代苗族对星辰的崇拜。\n\nSilver collars are worn in layers, symbolizing a woman’s family wealth and status. The two-dragons-contesting-a-pearl motif signifies protection and nobility; the swimming fish pattern represents fertility; the nipple-stud motif originates from ancient Miao star worship.',
      custom: '苗族银匠被誉为“月光下的艺术家”，一件精美的银项圈需经过熔炼、锻打、拉丝、錾刻等三十余道工序。\n\nMiao silversmiths are hailed as “artists under the moonlight” — a single exquisite silver collar undergoes over thirty processes including smelting, forging, wire-drawing, and engraving.',
    }
  };

  // --- 摄像头操作 ---
  let pendingStream = $state(null);  // 暂存待绑定的媒体流

  // 响应式副作用：当 cameraActive 变为 true 且 videoElement 就绪后，自动绑定流
  $effect(() => {
    if (cameraActive && videoElement && pendingStream) {
      videoElement.srcObject = pendingStream;
      pendingStream = null; // 消费后清空
    }
  });

  async function openCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { width: 640, height: 480, facingMode: 'environment' } 
      });
      cameraStream = stream;
      pendingStream = stream;
      cameraActive = true;
      detectedPatterns = [];
      startDrawLoop();
    } catch (err) {
      alert(lang === 'zh' ? t.alertCameraZh.zh : t.alertCameraEn.en);
      console.error('Camera error:', err);
      cameraActive = false;
      pendingStream = null;
    }
  }

  function closeCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      cameraStream = null;
      cameraActive = false;
      if (videoElement) videoElement.srcObject = null;
      stopDrawLoop();
    }
  }

  function captureFrame() {
    if (!videoElement || !canvasElement || !cameraActive) return;
    const context = canvasElement.getContext('2d');
    canvasElement.width = videoElement.videoWidth;
    canvasElement.height = videoElement.videoHeight;
    context.drawImage(videoElement, 0, 0);
    capturedImage = canvasElement.toDataURL('image/jpeg', 0.9);
    // 截取后自动关闭摄像头以节省资源（可选）
    closeCamera();
  }

  // --- Canvas 叠加层绘制 YOLO 识别框 ---
  let overlayCanvas = $state(null);

  function drawAnnotations() {
    if (!overlayCanvas) return;
    const ctx = overlayCanvas.getContext('2d');
    const w = overlayCanvas.width;
    const h = overlayCanvas.height;
    ctx.clearRect(0, 0, w, h);

    detectedPatterns.forEach(p => {
      // 青蓝色苗绣风格边框
      ctx.strokeStyle = '#5ecfd1';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = 'rgba(94, 207, 209, 0.6)';
      ctx.shadowBlur = 8;
      ctx.strokeRect(p.x, p.y, p.width, p.height);
      ctx.shadowBlur = 0;

      // 标签背景
      const label = `${p.label} ${Math.round(p.confidence * 100)}%`;
      ctx.font = 'bold 12px "PingFang SC", "Noto Serif SC", sans-serif';
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = '#5ecfd1';
      ctx.fillRect(p.x, p.y - 20, tw + 10, 18);

      // 标签文字
      ctx.fillStyle = '#0a1420';
      ctx.fillText(label, p.x + 5, p.y - 6);
    });

    // 未检测到时显示十字准星提示
    if (detectedPatterns.length === 0) {
      ctx.strokeStyle = 'rgba(94, 207, 209, 0.3)';
      ctx.lineWidth = 1;
      ctx.setLineDash([6, 8]);
      ctx.strokeRect(w * 0.15, h * 0.15, w * 0.7, h * 0.7);
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(w / 2, h * 0.2); ctx.lineTo(w / 2, h * 0.8);
      ctx.moveTo(w * 0.25, h / 2); ctx.lineTo(w * 0.75, h / 2);
      ctx.stroke();
    }
  }

  let drawAnimId = null;
  function drawLoop() {
    drawAnnotations();
    drawAnimId = requestAnimationFrame(drawLoop);
  }

  function startDrawLoop() {
    if (drawAnimId) return;
    drawLoop();
  }

  function stopDrawLoop() {
    if (drawAnimId) { cancelAnimationFrame(drawAnimId); drawAnimId = null; }
  }

  // --- 真实 YOLOv8n 检测（调用后端 API） ---
  async function runYoloDetection() {
    if (!capturedImage || isIdentifying) return;
    isIdentifying = true;
    identificationResult = null;
    recognitionFailed = false;
    recognitionDone = false;

    const t0 = performance.now();

    try {
      // 将 base64 图像转为 Blob，构造 FormData
      const blob = dataURLtoBlob(capturedImage);
      const formData = new FormData();
      formData.append('image', blob, 'captured.jpg');

      // 调用 YOLOv8n 后端 API
      const response = await fetch(YOLO_API_URL, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`API 返回错误状态: ${response.status}`);
      }

      const data = await response.json();
      
      // 记录实际推理耗时 (ms)
      inferTime = Math.round(performance.now() - t0);

      // 解析 YOLO 返回结果：预期格式 { detections: [{ class: "xxx", confidence: 0.98, bbox: [x,y,w,h] }] }
      const detections = data.detections || [];

      // 映射为可视化格式
      detectedPatterns = detections.map(d => ({
        x: d.bbox?.[0] ?? 60,
        y: d.bbox?.[1] ?? 40,
        width: d.bbox?.[2] ?? 160,
        height: d.bbox?.[3] ?? 120,
        label: yoloLabelMap[d.class?.toLowerCase()] || d.class || t.unknown[lang],
        confidence: d.confidence ?? 0.5
      }));

      if (detections.length === 0) {
        // 未检测到任何目标
        identificationResult = null;
        recognitionFailed = true;
        recognitionDone = true;
        isIdentifying = false;
        addBotMessage(lang === 'zh' ? t.noDetectZh.zh : t.noDetectEn.en);
        return;
      }

      // 取置信度最高的检测结果
      const topDetection = detections.reduce((best, cur) => 
        cur.confidence > best.confidence ? cur : best
      , detections[0]);

      // 尝试映射到苗族服饰知识库
      const mappedType = yoloLabelMap[topDetection.class?.toLowerCase()];
      let result;

      if (mappedType && miaoKnowledge[mappedType]) {
        // 成功映射到已知苗族服饰类型
        result = { 
          ...miaoKnowledge[mappedType],
          confidence: Math.round(topDetection.confidence * 100 * 10) / 10 // 转为百分比
        };
        addBotMessage(
          `YOLOv8n 识别到【${result.type}】，置信度 ${result.confidence}%。\n📐 原始标签: ${topDetection.class}\n\n` +
          `YOLOv8n identified [${result.type}], confidence ${result.confidence}%.\n📐 Raw label: ${topDetection.class}\n\n${result.meaning}`
        );
      } else {
        // 未映射到知识库，直接展示 YOLO 原始结果
        const confidencePct = Math.round(topDetection.confidence * 100 * 10) / 10;
        result = {
          type: `检测对象: ${topDetection.class} / Detected: ${topDetection.class}`,
          confidence: confidencePct,
          color: '—',
          pattern: '—',
          meaning: `YOLOv8n 检测到「${topDetection.class}」（置信度 ${confidencePct}%）。该类别暂未收录于苗族服饰知识库，助手将尽快扩充对应文化解说。\n\nYOLOv8n detected "${topDetection.class}" (confidence ${confidencePct}%). This category is not yet in the Miao costume knowledge base — the assistant will expand coverage soon.`,
          custom: '如您了解此物件的苗族文化背景，欢迎向助手描述，帮助完善知识库。\n\nIf you know the Miao cultural background of this item, please describe it to help improve the knowledge base.'
        };
        addBotMessage(
          `🔍 YOLOv8n 检测到【${topDetection.class}】，置信度 ${confidencePct}%。\n该类别暂未匹配苗族服饰知识库，已展示原始检测结果。\n\n` +
          `🔍 YOLOv8n detected [${topDetection.class}], confidence ${confidencePct}%.\nThis category is not matched in the Miao costume knowledge base — showing raw detection results.`
        );
      }

      identificationResult = result;
      recognitionFailed = false;
      recognitionDone = true;
      isIdentifying = false;
      drawAnnotations();

      // ---- YOLO 识别后自动调用 LLM 获取文化解说 ----
      callLLMForExplanation(topDetection, result);

    } catch (err) {
      inferTime = Math.round(performance.now() - t0);
      console.error('YOLO API 调用失败:', err);
      
      // API 调用失败时提示用户
      identificationResult = null;
      recognitionFailed = true;
      recognitionDone = true;
      isIdentifying = false;
      
      addBotMessage(
        `⚠️ YOLOv8n 服务连接失败：${err.message}\n请确保本地 YOLO 后端服务已启动（python server/yolo_server.py）。\n服务地址: ${YOLO_API_URL}\n\n` +
        `⚠️ YOLOv8n connection failed: ${err.message}\nPlease ensure the local YOLO backend is running (python server/yolo_server.py).\nAPI endpoint: ${YOLO_API_URL}`
      );
    }
  }

  // --- YOLO 检测后自动请求 LLM 文化解说（流式） ---
  async function callLLMForExplanation(detection, localResult) {
    const className = detection?.class || localResult?.type || '未知对象';
    const prompt = lang === 'zh'
      ? `我刚拍摄了一张苗族服饰图片，YOLO视觉模型检测到了「${className}」。请根据你的苗族文化知识，详细讲解这个物件的文化寓意、历史背景和传统习俗。`
      : `I just photographed a Miao costume item. YOLO detected "${className}". Please explain its cultural significance, historical background, and traditional customs based on your Miao culture knowledge.`;

    // 流式请求 LLM，首 token 即开始打印；失败时静默（本地知识库已在主流程展示）
    await streamLLMResponse(
      [{ role: 'user', content: prompt }],
      { silentError: true }
    );
  }

  // --- 重新拍摄 ---
  function retakePhoto() {
    capturedImage = null;
    identificationResult = null;
    recognitionFailed = false;
    recognitionDone = false;
    detectedPatterns = [];
    openCamera();
  }

  // --- 对话功能 ---
  function addBotMessage(text) {
    messages = [...messages, {
      id: Date.now(),
      role: 'assistant',
      content: text,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }];
    // 自动 TTS 语音播报（异步，不阻塞 UI）
    speakText(text);
  }

  function addUserMessage(text) {
    messages = [...messages, {
      id: Date.now(),
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }];
  }

  async function handleSendMessage() {
    errorTip = '';
    if (!userInput.trim()) {
      errorTip = t.errorEmpty[lang];
      return;
    }
    if (isLoading) return;
    const text = userInput.trim();
    cancelStream();  // 终止当前正在输出的流
    addUserMessage(text);
    userInput = '';

    // 构建对话历史（最近 10 条，避免上下文过长）
    const history = messages.slice(-10).map(m => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content
    }));
    history.push({ role: 'user', content: text });

    // 流式请求 LLM，首 token 即开始打印
    const ok = await streamLLMResponse(history, { silentError: true });
    if (!ok) {
      // LLM 不可用时使用本地知识库兜底
      let fallback = '';
      if (text.includes('银角') || text.includes('牛角')) {
        fallback = miaoKnowledge['苗族银角头饰'].meaning;
      } else if (text.includes('百鸟衣') || text.includes('鸟')) {
        fallback = miaoKnowledge['苗族百鸟衣'].meaning;
      } else if (text.includes('围腰') || text.includes('绣')) {
        fallback = miaoKnowledge['苗族绣花围腰'].meaning;
      } else if (text.includes('项圈') || text.includes('银')) {
        fallback = miaoKnowledge['苗族银项圈'].meaning;
      } else {
        fallback = lang === 'zh' ? t.fallbackZh.zh : t.fallbackEn.en;
      }
      // 如果 streamLLMResponse 没有添加错误消息，补充兜底内容
      if (!isStreaming && !isLoading) {
        addBotMessage(fallback);
      }
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleSendMessage();
    }
  }

  function clearMessages() {
    cancelStream();
    messages = [];
    isLoading = false;
    errorTip = '';
  }

  function startFreshSession() {
    clearMessages();
    addBotMessage(lang === 'zh' ? t.welcomeZh.zh : t.welcomeEn.en);
  }

  $effect(() => {
    if (messages.length || isLoading) {
      setTimeout(() => {
        if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
      }, 50);
    }
  });

  // --- LLM 流式响应：跟随服务端 token 实时输出 ---
  // 返回 true 表示成功收到内容，false 表示失败/中断
  async function streamLLMResponse(messages, { silentError = false } = {}) {
    // 取消已有的流
    cancelStream();

    streamAbortController = new AbortController();
    isStreaming = true;
    streamingText = '';
    isLoading = true;

    try {
      const response = await fetch(LLM_STREAM_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages }),
        signal: streamAbortController.signal
      });

      if (!response.ok) {
        throw new Error(`LLM 流式接口错误: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 按行解析 SSE（格式：data: {"content":"..."}\n\n）
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';  // 保留不完整的末行

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const payload = trimmed.slice(6);
          if (payload === '[DONE]') break;
          try {
            const parsed = JSON.parse(payload);
            if (parsed.content) {
              streamingText += parsed.content;
            }
            if (parsed.error) {
              throw new Error(parsed.error);
            }
          } catch (e) {
            // 非 JSON 时当作纯文本追加（兼容纯文本流）
            if (!payload.startsWith('{')) {
              streamingText += payload;
            }
          }
        }
      }

      // 流结束 — 将累积文本正式写入聊天记录
      const finalText = streamingText;
      streamingText = '';
      isStreaming = false;
      isLoading = false;
      streamAbortController = null;
      if (finalText.trim()) {
        addBotMessage(finalText);
        return true;
      }
      return false;  // 流完成但无内容
    } catch (err) {
      if (err.name === 'AbortError') {
        isStreaming = false;
        isLoading = false;
        streamAbortController = null;
        return false;
      }
      console.error('LLM 流式响应异常:', err);
      isStreaming = false;
      isLoading = false;
      streamAbortController = null;
      if (!silentError) {
        addBotMessage(
          lang === 'zh'
            ? `⚠️ 流式响应中断：${err.message}`
            : `⚠️ Stream interrupted: ${err.message}`
        );
      }
      return false;
    }
  }

  function cancelStream() {
    if (streamAbortController) {
      streamAbortController.abort();
      streamAbortController = null;
    }
    isStreaming = false;
    streamingText = '';
  }

  // 快捷提问话术
  // ================================================================
  // 真实麦克风录音 + ASR 语音识别
  // ================================================================
  function toggleListening() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 48000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
      micStream = stream;
      audioChunks = [];

      // 优先使用 audio/webm（浏览器通用），后端 SenseVoice 对常见格式兼容性好
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };
      mediaRecorder.onstop = async () => {
        // 释放麦克风
        stream.getTracks().forEach(t => t.stop());
        micStream = null;

        if (audioChunks.length === 0) return;

        const blob = new Blob(audioChunks, { type: mimeType });
        const formData = new FormData();
        formData.append('audio', blob, 'recording.webm');

        try {
          const resp = await fetch('/asr', { method: 'POST', body: formData });
          if (resp.ok) {
            const data = await resp.json();
            const text = (data.text || '').trim();
            if (text) {
              // 仅填入输入框，不自动发送——由用户确认后手动发送
              userInput = text;
            } else {
              // 仅显示短暂错误提示，不写入聊天记录
              errorTip = lang === 'zh' ? '🎤 未识别到语音内容，请重试。' : '🎤 No speech detected. Retry.';
              setTimeout(() => { if (errorTip === (lang === 'zh' ? '🎤 未识别到语音内容，请重试。' : '🎤 No speech detected. Retry.')) errorTip = ''; }, 3000);
            }
          } else {
            errorTip = lang === 'zh' ? '⚠️ ASR 服务异常' : '⚠️ ASR error';
            setTimeout(() => { if (errorTip === (lang === 'zh' ? '⚠️ ASR 服务异常' : '⚠️ ASR error')) errorTip = ''; }, 3000);
          }
        } catch (e) {
          console.error('ASR 请求失败:', e);
          errorTip = lang === 'zh' ? '⚠️ 无法连接语音识别服务' : '⚠️ Cannot connect ASR';
          setTimeout(() => { if (errorTip === (lang === 'zh' ? '⚠️ 无法连接语音识别服务' : '⚠️ Cannot connect ASR')) errorTip = ''; }, 3000);
        }
      };

      mediaRecorder.start();
      isRecording = true;
    } catch (err) {
      console.error('麦克风访问失败:', err);
      alert(lang === 'zh'
        ? '无法访问麦克风，请检查浏览器权限设置。'
        : 'Cannot access microphone. Please check browser permissions.');
      isRecording = false;
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    isRecording = false;
  }

  // ================================================================
  // TTS 语音播报：将 AI 回复文字送 /tts 合成并通过扬声器播放
  // ================================================================
  async function speakText(text) {
    if (!ttsEnabled || !text || !audioElement) return;
    // 提取纯文本（去除 HTML 标签等）
    const plain = text.replace(/<[^>]*>/g, '').replace(/&[^;]+;/g, '').trim();
    if (!plain) return;
    // 截断到 500 字，避免 TTS 模型超负载
    const short = plain.length > 500 ? plain.substring(0, 500) : plain;

    try {
      const resp = await fetch('/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: short })
      });
      if (resp.ok) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        // 释放旧 URL（避免内存泄漏）
        const oldSrc = audioElement.src;
        audioElement.src = url;
        audioElement.play().catch(e => console.warn('TTS 播放被阻止:', e.message));
        // 延迟清理旧 blob URL
        if (oldSrc && oldSrc.startsWith('blob:')) {
          setTimeout(() => URL.revokeObjectURL(oldSrc), 3000);
        }
      } else {
        console.warn('TTS 合成失败:', resp.status);
      }
    } catch (e) {
      console.warn('TTS 请求失败:', e.message);
    }
  }

  function toggleTTS() {
    ttsEnabled = !ttsEnabled;
    if (!ttsEnabled && audioElement) {
      audioElement.pause();
      audioElement.src = '';
    }
  }

  // --- 快捷提问话术（供 UI 按钮调用） ---
  const quickQuestions = [
    '讲解苗绣蝴蝶妈妈纹寓意\nExplain the Butterfly Mother motif in Miao embroidery',
    '介绍苗族传统服饰特色\nIntroduce the characteristics of Miao traditional costumes',
    '苗绣有哪些经典纹样\nWhat are the classic patterns in Miao embroidery?',
    '苗族银饰文化介绍\nIntroduction to Miao silver ornament culture'
  ];

  // --- 生命周期 ---
  onMount(() => {
    startFpsMonitor();
    startCpuMonitor();
    // 欢迎消息
    setTimeout(() => {
      addBotMessage(lang === 'zh' ? t.welcomeZh.zh : t.welcomeEn.en);
    }, 600);
  });

  onDestroy(() => {
    closeCamera();
    stopMonitors();
    stopDrawLoop();
    cancelStream();  // 终止正在进行的 LLM 流
    // 释放录音资源
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    if (micStream) {
      micStream.getTracks().forEach(t => t.stop());
    }
    // 清理 TTS blob URL
    if (audioElement && audioElement.src?.startsWith('blob:')) {
      URL.revokeObjectURL(audioElement.src);
    }
  });
</script>

<main class="app-container">
  <!-- 顶部导航栏 —— 设备状态 + 性能面板 -->
  <header class="app-header">
    <!-- 顶部蝴蝶+缠枝花纹装饰条 -->
    <div class="header-pattern-top">
      <div class="silver-beads-row">
        <span class="bead"></span><span class="bead"></span><span class="bead"></span>
        <span class="bead"></span><span class="bead"></span><span class="bead"></span>
        <span class="bead"></span><span class="bead"></span><span class="bead"></span>
        <span class="bead"></span><span class="bead"></span><span class="bead"></span>
        <span class="bead"></span><span class="bead"></span><span class="bead"></span>
      </div>
    </div>
    
    <div class="header-main">
      <!-- 左侧：Logo -->
      <div class="logo-section">
        <div class="ox-horn-icon" title="苗族牛角图腾">
          <svg viewBox="0 0 60 30" width="60" height="30">
            <path d="M10 28 C5 10 15 2 30 4 C45 2 55 10 50 28" fill="none" stroke="#5ecfd1" stroke-width="2.5" stroke-linecap="round"/>
            <circle cx="30" cy="15" r="6" fill="none" stroke="#5ecfd1" stroke-width="2"/>
            <circle cx="30" cy="15" r="2.5" fill="#5ecfd1"/>
          </svg>
        </div>
        <span class="top-logo-text">{t.logo[lang]}</span>
      </div>
      
      <!-- 中间：设备状态指示灯 -->
      <div class="status-group">
        <div class="status-item">
          <span class="status-dot {camOnline ? 'ok' : 'err'}"></span>
          <span class="status-text">{t.camera[lang]}</span>
        </div>
        <div class="status-item">
          <span class="status-dot {micOnline ? 'ok' : 'err'}"></span>
          <span class="status-text">{t.mic[lang]}</span>
        </div>
        <div class="status-item">
          <span class="status-dot {modelReady ? 'ok' : 'err'}"></span>
          <span class="status-text">{t.aiModel[lang]}</span>
        </div>
        <div class="status-item">
          <span class="status-dot {npuReady ? 'ok' : 'err'}"></span>
          <span class="status-text">{t.npu[lang]}</span>
        </div>
      </div>

      <!-- 右侧：性能面板 + 语言切换 -->
      <div class="perf-panel">
        <div class="perf-item" title="前端帧率">{t.fpsLabel[lang]}: {fps}</div>
        <div class="perf-item" title="YOLO 推理延迟">{t.inferLabel[lang]}: {inferTime} ms</div>
        <div class="perf-item" title="系统 CPU">{t.cpuLabel[lang]}: {cpuUsage}%</div>
        <div class="perf-item perf-mem" title="系统内存">RAM: {memUsage}%</div>
        {#if cpuTemp != null}
          <div class="perf-item perf-temp" title="CPU 温度">{cpuTemp}°C</div>
        {/if}
        {#if backendLabel}
          <div class="perf-item perf-backend" title="推理后端">{backendLabel}</div>
        {/if}
        <button class="btn-lang" onclick={toggleLang} title="Switch Language / 切换语言">
          {lang === 'zh' ? 'EN' : '中'}
        </button>
      </div>
    </div>
    
    <!-- 底部花蔓装饰行 -->
    <div class="header-pattern-bottom">
      <div class="silver-bubble-row">
        <span class="bubble"></span><span class="bubble"></span><span class="bubble"></span>
        <span class="bubble"></span><span class="bubble"></span><span class="bubble"></span>
        <span class="bubble"></span><span class="bubble"></span><span class="bubble"></span>
      </div>
      <div class="header-border-ornament">
        <span class="ornament-dot"></span>
        <span class="ornament-line"></span>
        <span class="ornament-diamond">◆</span>
        <span class="ornament-line"></span>
        <span class="ornament-dot"></span>
      </div>
    </div>
  </header>

  <!-- 主体内容区：三栏布局 -->
  <div class="main-layout">
    <!-- 左栏：识别预览区（华丽取景框） -->
    <aside class="panel panel-left">
      <div class="panel-title">
        <span class="title-icon">◇</span> {t.preview[lang]}
      </div>
      
      <!-- 主预览框（带装饰角花） -->
      <div class="ornate-frame">
        <!-- 装饰角花（回纹 + 四瓣小花） -->
        <div class="frame-corner corner-tl">
          <svg viewBox="0 0 40 40" width="36" height="36">
            <!-- 回纹几何 -->
            <path d="M2 38 L2 28 L12 28 L12 18 L22 18 L22 10" fill="none" stroke="#4a7a9a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M12 28 L22 28 L22 18" fill="none" stroke="#3a6a8a" stroke-width="0.7" stroke-linecap="round" opacity="0.5"/>
            <!-- 四瓣小花 -->
            <circle cx="30" cy="8" r="2.5" fill="none" stroke="#4a7a9a" stroke-width="0.8" opacity="0.7"/>
            <circle cx="30" cy="5" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="33" cy="8" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="27" cy="8" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="30" cy="11" r="1.2" fill="#4a7a9a" opacity="0.5"/>
          </svg>
        </div>
        <div class="frame-corner corner-tr">
          <svg viewBox="0 0 40 40" width="36" height="36">
            <path d="M38 38 L38 28 L28 28 L28 18 L18 18 L18 10" fill="none" stroke="#4a7a9a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M28 28 L18 28 L18 18" fill="none" stroke="#3a6a8a" stroke-width="0.7" stroke-linecap="round" opacity="0.5"/>
            <circle cx="10" cy="8" r="2.5" fill="none" stroke="#4a7a9a" stroke-width="0.8" opacity="0.7"/>
            <circle cx="10" cy="5" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="13" cy="8" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="7" cy="8" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="10" cy="11" r="1.2" fill="#4a7a9a" opacity="0.5"/>
          </svg>
        </div>
        <div class="frame-corner corner-bl">
          <svg viewBox="0 0 40 40" width="36" height="36">
            <path d="M2 2 L2 12 L12 12 L12 22 L22 22 L22 30" fill="none" stroke="#4a7a9a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M12 12 L22 12 L22 22" fill="none" stroke="#3a6a8a" stroke-width="0.7" stroke-linecap="round" opacity="0.5"/>
            <circle cx="30" cy="32" r="2.5" fill="none" stroke="#4a7a9a" stroke-width="0.8" opacity="0.7"/>
            <circle cx="30" cy="29" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="33" cy="32" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="27" cy="32" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="30" cy="35" r="1.2" fill="#4a7a9a" opacity="0.5"/>
          </svg>
        </div>
        <div class="frame-corner corner-br">
          <svg viewBox="0 0 40 40" width="36" height="36">
            <path d="M38 2 L38 12 L28 12 L28 22 L18 22 L18 30" fill="none" stroke="#4a7a9a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M28 12 L18 12 L18 22" fill="none" stroke="#3a6a8a" stroke-width="0.7" stroke-linecap="round" opacity="0.5"/>
            <circle cx="10" cy="32" r="2.5" fill="none" stroke="#4a7a9a" stroke-width="0.8" opacity="0.7"/>
            <circle cx="10" cy="29" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="13" cy="32" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="7" cy="32" r="1.2" fill="#4a7a9a" opacity="0.5"/>
            <circle cx="10" cy="35" r="1.2" fill="#4a7a9a" opacity="0.5"/>
          </svg>
        </div>

        <!-- 框内主内容 -->
        <div class="frame-content">
          {#if cameraActive}
            <div class="camera-popup-inner" transition:slide>
              <video bind:this={videoElement} autoplay playsinline muted></video>
              <canvas
                bind:this={overlayCanvas}
                class="overlay-canvas"
                width="640" height="480"
              ></canvas>
              <div class="viewfinder-grid">
                <div class="grid-h"></div>
                <div class="grid-v"></div>
              </div>
              {#if detectedPatterns.length > 0}
                <div class="camera-label live">● {t.liveDetecting[lang]} — {t.patternsFound[lang]} {detectedPatterns.length} {t.patternsUnit[lang]}</div>
              {:else}
                <div class="camera-label">{t.aimLens[lang]}</div>
              {/if}
            </div>
          {:else if capturedImage}
            <div class="preview-image-wrapper" transition:fade>
              <img src={capturedImage} alt="拍摄的服饰图片" />
              <canvas
                bind:this={overlayCanvas}
                class="overlay-canvas"
                width="640" height="480"
              ></canvas>
              <div class="preview-overlay-label">{t.capturedLabel[lang]}</div>
            </div>
          {:else}
            <div class="frame-placeholder">
              <div class="placeholder-illustration">
                <svg viewBox="0 0 160 120" width="140" height="105">
                  <!-- 远山 -->
                  <path d="M0 110 L0 80 Q30 55 60 72 Q90 50 120 68 Q150 48 160 60 L160 110 Z" fill="#111d2e" opacity="0.5"/>
                  <path d="M0 110 L0 90 Q40 65 80 82 Q120 60 160 78 L160 110 Z" fill="#0d1624" opacity="0.4"/>
                  <!-- 风雨桥廊 -->
                  <path d="M30 105 L30 72 L50 60 L70 72 L70 105" fill="none" stroke="#2a4a6a" stroke-width="1.2" opacity="0.6"/>
                  <path d="M70 105 L70 72 L90 60 L110 72 L110 105" fill="none" stroke="#2a4a6a" stroke-width="1.2" opacity="0.6"/>
                  <path d="M110 105 L110 72 L130 60 L150 72 L150 105" fill="none" stroke="#2a4a6a" stroke-width="1.2" opacity="0.5"/>
                  <!-- 桥廊顶部 -->
                  <path d="M30 72 L50 58 L70 72 L90 58 L110 72 L130 58 L150 72" fill="none" stroke="#2a4a6a" stroke-width="0.9" opacity="0.4"/>
                  <!-- 桥柱 -->
                  <rect x="42" y="80" width="2" height="25" fill="#1a3048" opacity="0.4"/>
                  <rect x="52" y="80" width="2" height="25" fill="#1a3048" opacity="0.4"/>
                  <rect x="82" y="80" width="2" height="25" fill="#1a3048" opacity="0.35"/>
                  <rect x="92" y="80" width="2" height="25" fill="#1a3048" opacity="0.35"/>
                  <!-- 蝴蝶装饰 -->
                  <path d="M78 42 Q74 34 72 38 Q70 42 78 42" fill="none" stroke="#3a6a8a" stroke-width="0.7" opacity="0.5"/>
                  <path d="M78 42 Q82 34 84 38 Q86 42 78 42" fill="none" stroke="#3a6a8a" stroke-width="0.7" opacity="0.5"/>
                  <!-- 飞鸟 -->
                  <path d="M120 35 Q124 30 128 35" fill="none" stroke="#2a4a6a" stroke-width="0.6" opacity="0.4"/>
                  <path d="M132 30 Q136 25 140 30" fill="none" stroke="#2a4a6a" stroke-width="0.5" opacity="0.3"/>
                </svg>
              </div>
              <p class="placeholder-hint">{t.placeholderHint1[lang]}<br/>{t.placeholderHint2[lang]}</p>
            </div>
          {/if}
        </div>
      </div>

      <!-- 操作按钮组 -->
      <div class="camera-actions">
        {#if !cameraActive && !capturedImage}
          <button class="btn-camera-main" onclick={openCamera}>
            <svg viewBox="0 0 24 24" width="20" height="20"><rect x="2" y="6" width="20" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M7 4 L8.5 2 L15.5 2 L17 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            {t.identifyBtn[lang]}
          </button>
        {:else if cameraActive}
          <button class="btn-capture" onclick={captureFrame}>
            <svg viewBox="0 0 24 24" width="20" height="20"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2.5"/><circle cx="12" cy="12" r="3.5" fill="currentColor"/></svg>
            {t.captureBtn[lang]}
          </button>
          <button class="btn-close-cam" onclick={closeCamera} title="关闭摄像头">
            <span>✕</span> {t.closeBtn[lang]}
          </button>
        {:else if capturedImage && !recognitionDone}
          <button class="btn-identify-main" onclick={runYoloDetection} disabled={isIdentifying}>
            {#if isIdentifying}
              <span class="spinner"></span> {t.identifying[lang]}
            {:else}
              <svg viewBox="0 0 24 24" width="18" height="18"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>
              {t.yoloIdentify[lang]}
            {/if}
          </button>
        {:else if recognitionDone}
          <button class="btn-retake-main" onclick={retakePhoto}>
            <svg viewBox="0 0 24 24" width="18" height="18"><path d="M1 4v6h6M23 20v-6h-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            {t.retakeBtn[lang]}
          </button>
        {/if}
      </div>

      <!-- 未识别提示 -->
      {#if recognitionFailed}
        <div class="unrecognized-card" transition:fade>
          <div class="unrecognized-icon">
            <svg viewBox="0 0 48 48" width="40" height="40"><circle cx="24" cy="24" r="20" fill="none" stroke="#c08040" stroke-width="1.5"/><line x1="24" y1="12" x2="24" y2="28" stroke="#c08040" stroke-width="2" stroke-linecap="round"/><circle cx="24" cy="34" r="2" fill="#c08040"/></svg>
          </div>
          <p class="unrecognized-title">{t.noObject[lang]}</p>
          <p class="unrecognized-desc">{t.noObjectDesc[lang]}</p>
          <button class="btn-retake" onclick={retakePhoto}>
            <span>↻</span> {t.retakeBtn[lang]}
          </button>
        </div>
      {/if}

      <!-- 识别结果卡片 -->
      {#if identificationResult}
        <div class="result-card" transition:fade>
          <div class="result-header">
            <span class="badge-type">{identificationResult.type}</span>
            <span class="badge-confidence">{identificationResult.confidence}%</span>
          </div>
          <div class="result-detail">
            <div class="detail-row"><span class="dl">{t.colorLabel[lang]}</span><span class="dv">{identificationResult.color}</span></div>
            <div class="detail-row"><span class="dl">{t.patternLabel[lang]}</span><span class="dv">{identificationResult.pattern}</span></div>
            <div class="detail-row"><span class="dl">{t.customLabel[lang]}</span><span class="dv">{identificationResult.custom}</span></div>
          </div>
        </div>
      {/if}
      
      <canvas bind:this={canvasElement} class="hidden-canvas"></canvas>
      <!-- 隐藏音频元素：TTS 语音播报 -->
      <audio bind:this={audioElement} class="hidden-audio" preload="none"></audio>
    </aside>

    <!-- 中栏：对话区 -->
    <section class="panel panel-chat">
      <div class="panel-title">
        <span class="title-icon">◇</span> {t.chatTitle[lang]}
        {#if messages.length > 0}
          <button class="btn-clear-chat" onclick={clearMessages} title="清除对话记录">
            <svg viewBox="0 0 24 24" width="14" height="14"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
            {t.clearChat[lang]}
          </button>
        {/if}
      </div>
      
      <!-- 错误提示 -->
      {#if errorTip}
        <div class="error-tip">{errorTip}</div>
      {/if}
      
      <!-- 聊天消息容器 -->
      <div class="chat-messages" bind:this={chatContainer} style="scroll-behavior: smooth;">
        {#if messages.length === 0 && !isLoading}
          <div class="empty-chat">
            <!-- 苗族阿妹 AI 助手卡片 -->
            <div class="miao-girl-card">
              <div class="avatar-box">
                <div class="girl-avatar">
                  <svg viewBox="0 0 80 80" width="80" height="80">
                    <circle cx="40" cy="40" r="38" fill="none" stroke="#5ecfd1" stroke-width="2"/>
                    <path d="M18 48 C12 20 28 8 40 8 C52 8 68 20 62 48" fill="none" stroke="#5ecfd1" stroke-width="2" stroke-linecap="round"/>
                    <circle cx="40" cy="38" r="14" fill="none" stroke="#7aaccc" stroke-width="1.2"/>
                    <circle cx="35" cy="35" r="2" fill="#7aaccc"/>
                    <circle cx="45" cy="35" r="2" fill="#7aaccc"/>
                    <path d="M35 44 Q40 48 45 44" fill="none" stroke="#7aaccc" stroke-width="1.2" stroke-linecap="round"/>
                  </svg>
                </div>
              </div>
              <div class="girl-info">
                <h2 class="girl-name">{t.girlName[lang]}</h2>
                <p class="girl-desc">{t.girlDesc1[lang]}<br/>{t.girlDesc2[lang]}</p>
              </div>
              <div class="quick-cards">
                {#each quickQuestions as q}
                  <button class="miao-btn quick-card-btn" onclick={() => { userInput = lang === 'zh' ? q.split('\n')[0] : q.split('\n')[1]; handleSendMessage(); }}>
                    {q}
                  </button>
                {/each}
              </div>
              <button class="btn-welcome-session" onclick={startFreshSession}>
                <span>▸</span> {t.startSession[lang]}
              </button>
            </div>
          </div>
        {:else}
          {#each messages as msg (msg.id)}
            <div class="chat-bubble {msg.role}">
              <div class="bubble-avatar">
                {#if msg.role === 'assistant'}
                  <div class="avatar ai">
                    <svg viewBox="0 0 24 24" width="14" height="14"><path d="M8 16 C4 8 10 2 12 2 C14 2 20 8 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
                  </div>
                {:else}
                  <div class="avatar user">
                    <svg viewBox="0 0 24 24" width="14" height="14"><circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 20 Q8 14 12 14 Q16 14 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
                  </div>
                {/if}
              </div>
              <div class="bubble-content">
                <div class="bubble-header">
                  <span class="bubble-role">{msg.role === 'assistant' ? t.aiAssistant[lang] : t.userLabel[lang]}</span>
                  <span class="bubble-time">{msg.time}</span>
                </div>
                <div class="bubble-text">
                  <p>{@html msg.content.replace(/\n/g, '<br/>')}</p>
                </div>
              </div>
            </div>
          {/each}

          {#if isStreaming}
            <div class="chat-bubble assistant streaming-bubble">
              <div class="bubble-avatar">
                <div class="avatar ai">
                  <svg viewBox="0 0 24 24" width="14" height="14"><path d="M8 16 C4 8 10 2 12 2 C14 2 20 8 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
                </div>
              </div>
              <div class="bubble-content">
                <div class="bubble-header">
                  <span class="bubble-role">{t.aiAssistant[lang]}</span>
                  <span class="bubble-time">● 输出中</span>
                </div>
                <div class="bubble-text">
                  <p>{@html streamingText.replace(/\n/g, '<br/>')}<span class="cursor-blink">|</span></p>
                </div>
              </div>
            </div>
          {/if}

          {#if isLoading && !isStreaming}
            <div class="chat-bubble assistant loading-bubble">
              <div class="bubble-avatar">
                <div class="avatar ai">
                  <svg viewBox="0 0 24 24" width="14" height="14"><path d="M8 16 C4 8 10 2 12 2 C14 2 20 8 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
                </div>
              </div>
              <div class="bubble-content">
                <div class="bubble-header">
                  <span class="bubble-role">{t.aiAssistant[lang]}</span>
                  <span class="bubble-time">...</span>
                </div>
                <div class="bubble-text loading">
                  <span class="dot">●</span>
                  <span class="dot">●</span>
                  <span class="dot">●</span>
                </div>
              </div>
            </div>
          {/if}
        {/if}
      </div>

      <!-- 文本输入框 -->
      <div class="chat-input">
        <input
          type="text"
          bind:value={userInput}
          placeholder={t.inputPlaceholder[lang]}
          disabled={isLoading}
          onkeydown={handleKeyDown}
          autocomplete="off"
        />
        <button class="btn-send" onclick={handleSendMessage} disabled={!userInput.trim() || isLoading}>
          {t.sendBtn[lang]}
        </button>
      </div>
    </section>

    <!-- 右栏：快捷功能与知识库入口 -->
    <aside class="panel panel-right">
      <div class="panel-title">
        <span class="title-icon">◇</span> {t.quickTools[lang]}
      </div>
      
      <!-- 参考图像小窗 -->
      <div class="right-section">
        <span class="section-mini-title">{t.reference[lang]}</span>
        {#if capturedImage}
          <div class="preview-mini">
            <img src={capturedImage} alt="拍摄预览" />
            <span class="preview-badge">{t.captured[lang]}</span>
          </div>
        {:else}
          <div class="preview-placeholder-mini">
            <div class="ph-icon">
              <svg viewBox="0 0 48 48" width="32" height="32"><rect x="6" y="10" width="36" height="28" rx="3" fill="none" stroke="#3a5a7a" stroke-width="1.5"/><circle cx="24" cy="24" r="7" fill="none" stroke="#3a5a7a" stroke-width="1"/><path d="M12 14 L14.5 11 L33.5 11 L36 14" fill="none" stroke="#3a5a7a" stroke-width="1.2"/></svg>
            </div>
            <span>{t.afterCapture[lang]}</span>
          </div>
        {/if}
      </div>

      <!-- 文化科普区块 -->
      <div class="right-section culture-section">
        <span class="section-mini-title">{t.culture[lang]}</span>
        <div class="culture-card">
          <div class="culture-icon">
            <svg viewBox="0 0 32 32" width="24" height="24"><path d="M8 28 C4 16 12 2 16 2 C20 2 28 16 24 28" fill="none" stroke="#7aaccc" stroke-width="1.5" stroke-linecap="round"/><circle cx="16" cy="15" r="5" fill="none" stroke="#7aaccc" stroke-width="1"/></svg>
          </div>
          <p class="culture-title">{t.cultureTitle[lang]}</p>
          <p class="culture-desc">{t.cultureDesc[lang]}</p>
        </div>
      </div>

      <!-- 快速提问 -->
      <div class="right-section">
        <span class="section-mini-title">{t.quickAsk[lang]}</span>
        <div class="quick-links">
          <button class="quick-btn" onclick={() => { userInput = lang === 'zh' ? t.qHornZh.zh : t.qHornEn.en; handleSendMessage(); }}>
            <span class="qb-icon">◈</span> {t.hornMeaning[lang]}
          </button>
          <button class="quick-btn" onclick={() => { userInput = lang === 'zh' ? t.qBirdZh.zh : t.qBirdEn.en; handleSendMessage(); }}>
            <span class="qb-icon">◈</span> {t.birdLegend[lang]}
          </button>
          <button class="quick-btn" onclick={() => { userInput = lang === 'zh' ? t.qApronZh.zh : t.qApronEn.en; handleSendMessage(); }}>
            <span class="qb-icon">◈</span> {t.apronPatterns[lang]}
          </button>
        </div>
      </div>

      <!-- 了解更多按钮 -->
      <button class="btn-learn-more" onclick={() => { userInput = lang === 'zh' ? t.qTypesZh.zh : t.qTypesEn.en; handleSendMessage(); }}>
        <span>▸</span> {t.learnMore[lang]}
      </button>
    </aside>
  </div>

  <!-- 底部导航标签栏 -->
  <nav class="bottom-nav">
    <button class="nav-tab active" onclick={() => { userInput = lang === 'zh' ? t.qOutlineZh.zh : t.qOutlineEn.en; handleSendMessage(); }}>
      <span class="nav-icon">◇</span>
      <span class="nav-label">{t.quickChat[lang]}</span>
    </button>
    <button class="nav-tab" onclick={() => { userInput = lang === 'zh' ? t.qSymbolZh.zh : t.qSymbolEn.en; handleSendMessage(); }}>
      <span class="nav-icon">❖</span>
      <span class="nav-label">{t.meanings[lang]}</span>
    </button>
    <button class="nav-tab" onclick={() => { userInput = lang === 'zh' ? t.qPartsZh.zh : t.qPartsEn.en; handleSendMessage(); }}>
      <span class="nav-icon">◈</span>
      <span class="nav-label">{t.parts[lang]}</span>
    </button>
    <button class="nav-tab" onclick={() => { userInput = lang === 'zh' ? t.qLearnZh.zh : t.qLearnEn.en; handleSendMessage(); }}>
      <span class="nav-icon">✧</span>
      <span class="nav-label">{t.qa[lang]}</span>
    </button>
    <button class="nav-tab" onclick={() => { userInput = lang === 'zh' ? t.qAtlasZh.zh : t.qAtlasEn.en; handleSendMessage(); }}>
      <span class="nav-icon">⬡</span>
      <span class="nav-label">{t.atlas[lang]}</span>
    </button>
  </nav>

  <!-- 底部语音交互栏 -->
  <footer class="voice-bar">
    <!-- TTS 语音播报开关 -->
    <button class="btn-tts-toggle" onclick={toggleTTS} title={ttsEnabled ? (lang === 'zh' ? '关闭语音播报' : 'Mute TTS') : (lang === 'zh' ? '开启语音播报' : 'Enable TTS')}>
      {ttsEnabled ? '🔊' : '🔇'}
    </button>

    <button 
      class="voice-btn" 
      class:recording={isRecording}
      onclick={toggleListening}
      disabled={isLoading}
    >
      <span class="voice-icon">
        {#if isRecording}
          <svg viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="8" fill="#ff6b6b"/></svg>
        {:else}
          <svg viewBox="0 0 24 24" width="16" height="16"><rect x="9" y="1" width="6" height="13" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M5 11a7 7 0 0 0 14 0" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M12 19v4M8 23h8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        {/if}
      </span>
      <span>{isRecording ? t.listening[lang] : t.voiceWake[lang]}</span>
      {#if isRecording}
        <div class="wave-bars live">
          <span></span><span></span><span></span><span></span><span></span>
        </div>
      {/if}
    </button>
    <span class="voice-info">{t.voiceInfo[lang]}</span>
  </footer>
</main>

<style>
  /* ========== CSS 变量 -- 苗绣色调 ========== */
  :root {
    --color-dark-bg: #1a3b70;
    --color-miao-cyan: #5ecfd1;
    --color-miao-blue: #3a6ea5;
    --color-miao-purple: #a882dd;
    --color-text-white: #f0f7ff;
  }

  /* ========== 全局重置 ========== */
  :global(*) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
  
  :global(body) {
    font-family: 'PingFang SC', 'Noto Serif SC', 'Microsoft YaHei', system-ui, sans-serif;
    background-color: #1a3b70;
    /* 菱形网格底纹 模拟苗绣经纬线 */
    background-image: 
      repeating-linear-gradient(45deg, 
        rgba(94, 207, 209, 0.06) 0px, 
        rgba(94, 207, 209, 0.06) 1px, 
        transparent 1px, 
        transparent 30px
      ),
      repeating-linear-gradient(-45deg, 
        rgba(94, 207, 209, 0.06) 0px, 
        rgba(94, 207, 209, 0.06) 1px, 
        transparent 1px, 
        transparent 30px
      );
    color: var(--color-text-white);
    overflow: hidden;
    height: 100vh;
  }

  /* 全局滚动条 — 苗绣青蓝风格 */
  :global(::-webkit-scrollbar) { width: 6px; height: 6px; }
  :global(::-webkit-scrollbar-thumb) {
    background: var(--color-miao-cyan);
    border-radius: 6px;
  }
  :global(::-webkit-scrollbar-track) {
    background: rgba(255,255,255,0.05);
  }
  
  /* 通用苗绣卡片 — 苗绣丝线光泽 + 渐变锯齿边框 */
  .miao-card {
    position: relative;
    border-radius: 16px;
    padding: 16px;
    background: rgba(15, 30, 60, 0.85);
    box-shadow: 
      inset 0 0 0 1px rgba(94, 207, 209, 0.2),
      0 0 20px rgba(94, 207, 209, 0.15);
  }
  .miao-card::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 16px;
    padding: 2px;
    background: linear-gradient(90deg, #5ecfd1, #a882dd, #5ecfd1);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    pointer-events: none;
  }

  /* 通用苗绣按钮 */
  .miao-btn {
    background: linear-gradient(135deg, #3a6ea5, #5ecfd1);
    color: #fff;
    border: none;
    border-radius: 20px;
    padding: 8px 20px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.3s ease;
  }
  .miao-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(94, 207, 209, 0.4);
  }
  .miao-btn:active {
    transform: translateY(0);
  }
  .miao-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }

  .app-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    max-width: 1440px;
    margin: 0 auto;
    background:
      /* 苗绣缠枝花卉暗纹 — 菱形织锦底纹 */
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'%3E%3Cpath d='M50 5 Q68 25 50 50 Q32 75 50 95' fill='none' stroke='%233a5570' stroke-width='0.5' opacity='0.25'/%3E%3Cpath d='M5 50 Q25 32 50 50 Q75 68 95 50' fill='none' stroke='%233a5570' stroke-width='0.5' opacity='0.25'/%3E%3Cpath d='M50 5 Q75 20 50 50 Q25 80 50 95' fill='none' stroke='%232a4058' stroke-width='0.4' opacity='0.15'/%3E%3Cpath d='M5 50 Q20 75 50 50 Q80 25 95 50' fill='none' stroke='%232a4058' stroke-width='0.4' opacity='0.15'/%3E%3Ccircle cx='50' cy='50' r='2' fill='%234a6a8a' opacity='0.3'/%3E%3Ccircle cx='50' cy='5' r='1.2' fill='%233a5570' opacity='0.2'/%3E%3Ccircle cx='50' cy='95' r='1.2' fill='%233a5570' opacity='0.2'/%3E%3Ccircle cx='5' cy='50' r='1.2' fill='%233a5570' opacity='0.2'/%3E%3Ccircle cx='95' cy='50' r='1.2' fill='%233a5570' opacity='0.2'/%3E%3C/svg%3E") repeat,
      /* 山水虚化剪影 — 底部远山 */
      linear-gradient(180deg, #0d1520 0%, #121d2e 40%, #162236 70%, #1a283a 100%);
    border-left: 1px solid #2a3a55;
    border-right: 1px solid #2a3a55;
    position: relative;
  }

  /* 风雨桥虚化剪影 — 底部装饰 */
  .app-container::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 160px;
    pointer-events: none;
    background:
      /* 远山轮廓 */
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1440' height='160' viewBox='0 0 1440 160' preserveAspectRatio='none'%3E%3Cpath d='M0 160 L0 120 Q80 85 150 100 Q220 70 320 90 Q380 60 480 80 Q560 45 680 65 Q760 35 860 55 Q940 25 1060 50 Q1140 20 1240 45 Q1320 30 1440 55 L1440 160 Z' fill='%23101e30' opacity='0.35'/%3E%3Cpath d='M0 160 L0 135 Q100 110 200 125 Q320 95 440 115 Q540 90 660 105 Q760 85 880 100 Q1000 75 1100 90 Q1200 78 1320 92 Q1380 85 1440 95 L1440 160 Z' fill='%230d1826' opacity='0.25'/%3E%3C/svg%3E") repeat-x bottom,
      /* 风雨桥柱廊剪影 */
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1440' height='90' viewBox='0 0 1440 90' preserveAspectRatio='none'%3E%3Crect x='200' y='10' width='4' height='80' fill='%23142338' opacity='0.4'/%3E%3Crect x='230' y='10' width='4' height='80' fill='%23142338' opacity='0.4'/%3E%3Crect x='260' y='10' width='4' height='80' fill='%23142338' opacity='0.4'/%3E%3Cpath d='M195 10 L270 10' stroke='%23142338' stroke-width='3' opacity='0.5'/%3E%3Cpath d='M195 55 L270 55 L275 35 L280 55' fill='none' stroke='%23142338' stroke-width='2.5' opacity='0.5'/%3E%3Crect x='520' y='10' width='4' height='80' fill='%23142338' opacity='0.3'/%3E%3Crect x='550' y='10' width='4' height='80' fill='%23142338' opacity='0.3'/%3E%3Crect x='580' y='10' width='4' height='80' fill='%23142338' opacity='0.3'/%3E%3Cpath d='M515 10 L590 10' stroke='%23142338' stroke-width='3' opacity='0.4'/%3E%3Cpath d='M515 55 L590 55 L595 35 L600 55' fill='none' stroke='%23142338' stroke-width='2.5' opacity='0.4'/%3E%3Crect x='880' y='10' width='4' height='80' fill='%23142338' opacity='0.3'/%3E%3Crect x='910' y='10' width='4' height='80' fill='%23142338' opacity='0.3'/%3E%3Crect x='940' y='10' width='4' height='80' fill='%23142338' opacity='0.3'/%3E%3Cpath d='M875 10 L950 10' stroke='%23142338' stroke-width='3' opacity='0.4'/%3E%3Cpath d='M875 55 L950 55 L955 35 L960 55' fill='none' stroke='%23142338' stroke-width='2.5' opacity='0.4'/%3E%3C/svg%3E") repeat-x bottom;
    z-index: 0;
  }
  
  /* ========== 顶部导航 ========== */
  .app-header {
    background: rgba(26, 59, 112, 0.9);
    border: 1px solid rgba(94, 207, 209, 0.3);
    border-radius: 14px;
    position: relative;
    z-index: 1;
    box-shadow: 0 2px 24px rgba(0, 0, 0, 0.4);
    margin: 8px 12px 6px;
  }

  /* -- 顶部蝴蝶+缠枝花纹装饰条 -- */
  .header-pattern-top {
    height: 24px;
    border-radius: 14px 14px 0 0;
    background:
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='24' viewBox='0 0 200 24'%3E%3C!-- 蝴蝶纹 --%3E%3Cpath d='M22 18 Q16 6 10 12 Q4 18 10 20 Q16 22 22 18 Z' fill='none' stroke='%234a7a9a' stroke-width='0.8' opacity='0.6'/%3E%3Cpath d='M10 20 Q14 16 16 12 Q18 8 22 8' fill='none' stroke='%233a6a8a' stroke-width='0.6' opacity='0.4'/%3E%3Cpath d='M10 12 Q6 8 2 10 Q0 12 4 14 Q8 14 10 12' fill='none' stroke='%233a6a8a' stroke-width='0.6' opacity='0.4'/%3E%3Ccircle cx='14' cy='14' r='1' fill='%233a6a8a' opacity='0.5'/%3E%3C!-- 缠枝花纹 --%3E%3Cpath d='M30 12 Q45 2 60 12 Q75 22 90 12' fill='none' stroke='%233a5570' stroke-width='0.7' opacity='0.5'/%3E%3Ccircle cx='45' cy='8' r='1.5' fill='%233a5570' opacity='0.4'/%3E%3Ccircle cx='75' cy='18' r='1.5' fill='%233a5570' opacity='0.4'/%3E%3Cpath d='M100 12 Q108 4 120 8 Q132 12 140 8' fill='none' stroke='%233a5570' stroke-width='0.7' opacity='0.5'/%3E%3Ccircle cx='120' cy='8' r='1.5' fill='%233a5570' opacity='0.4'/%3E%3C!-- 蝴蝶纹2 --%3E%3Cpath d='M152 18 Q146 6 140 12 Q134 18 140 20 Q146 22 152 18 Z' fill='none' stroke='%234a7a9a' stroke-width='0.8' opacity='0.6'/%3E%3Cpath d='M140 20 Q144 16 146 12 Q148 8 152 8' fill='none' stroke='%233a6a8a' stroke-width='0.6' opacity='0.4'/%3E%3Cpath d='M140 12 Q136 8 132 10 Q130 12 134 14 Q138 14 140 12' fill='none' stroke='%233a6a8a' stroke-width='0.6' opacity='0.4'/%3E%3Ccircle cx='144' cy='14' r='1' fill='%233a6a8a' opacity='0.5'/%3E%3C!-- 缠枝花卉2 --%3E%3Cpath d='M160 12 Q175 2 190 12' fill='none' stroke='%233a5570' stroke-width='0.7' opacity='0.5'/%3E%3Ccircle cx='175' cy='8' r='1.5' fill='%233a5570' opacity='0.4'/%3E%3C/svg%3E") repeat-x center,
      linear-gradient(180deg, #0a1420, #0f1d2e);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .silver-beads-row {
    display: none;
  }
  
  .bead {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #8ab4d0, #4a6a8a);
    box-shadow: 0 0 5px rgba(74, 106, 138, 0.5);
  }
  
  .header-main {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    gap: 12px;
  }
  
  .logo-section {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  
  .ox-horn-icon {
    filter: drop-shadow(0 0 8px rgba(94, 207, 209, 0.5));
  }
  
  .top-logo-text {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--color-miao-cyan);
    letter-spacing: 0.08em;
  }

  /* -- 设备状态指示灯 -- */
  .status-group {
    display: flex;
    gap: 16px;
  }
  .status-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    color: #e6f4ff;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }
  .status-dot.ok {
    background: #4cd9b2;
    box-shadow: 0 0 6px #4cd9b2;
  }
  .status-dot.err {
    background: #ff6b6b;
    box-shadow: 0 0 6px #ff6b6b;
  }
  .status-text {
    white-space: nowrap;
  }

  /* -- 性能面板 -- */
  .perf-panel {
    display: flex;
    gap: 14px;
    font-size: 0.78rem;
    color: #e6f4ff;
    flex-shrink: 0;
  }
  .perf-item {
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
    font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  }
  .perf-mem { color: #8ab8d0; }
  .perf-temp {
    color: #e0a060;
    font-weight: 600;
  }
  .perf-backend {
    color: #6a9a6a;
    font-size: 0.65rem;
    max-width: 110px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .btn-lang {
    width: 36px;
    height: 28px;
    border-radius: 14px;
    border: 1px solid var(--color-miao-cyan);
    background: rgba(94, 207, 209, 0.12);
    color: var(--color-miao-cyan);
    font-size: 0.7rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.25s;
    letter-spacing: 0.04em;
    flex-shrink: 0;
  }
  .btn-lang:hover {
    background: rgba(94, 207, 209, 0.28);
    box-shadow: 0 0 10px rgba(94, 207, 209, 0.3);
    transform: scale(1.05);
  }
  
  .header-pattern-bottom {
    height: 20px;
    background:
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='20' viewBox='0 0 160 20'%3E%3Cpath d='M0 10 Q20 0 40 10 Q60 20 80 10 Q100 0 120 10 Q140 20 160 10' fill='none' stroke='%233a5570' stroke-width='0.7' opacity='0.5'/%3E%3Ccircle cx='20' cy='10' r='2' fill='%233a5570' opacity='0.4'/%3E%3Ccircle cx='60' cy='10' r='2' fill='%233a5570' opacity='0.4'/%3E%3Ccircle cx='100' cy='10' r='2' fill='%233a5570' opacity='0.4'/%3E%3Ccircle cx='140' cy='10' r='2' fill='%233a5570' opacity='0.4'/%3E%3C!-- 四瓣小花 --%3E%3Ccircle cx='40' cy='10' r='1.2' fill='%233a5570' opacity='0.5'/%3E%3Ccircle cx='37' cy='8' r='1' fill='%233a5570' opacity='0.35'/%3E%3Ccircle cx='43' cy='8' r='1' fill='%233a5570' opacity='0.35'/%3E%3Ccircle cx='37' cy='12' r='1' fill='%233a5570' opacity='0.35'/%3E%3Ccircle cx='43' cy='12' r='1' fill='%233a5570' opacity='0.35'/%3E%3Ccircle cx='120' cy='10' r='1.2' fill='%233a5570' opacity='0.5'/%3E%3Ccircle cx='117' cy='8' r='1' fill='%233a5570' opacity='0.35'/%3E%3Ccircle cx='123' cy='8' r='1' fill='%233a5570' opacity='0.35'/%3E%3Ccircle cx='117' cy='12' r='1' fill='%233a5570' opacity='0.35'/%3E%3Ccircle cx='123' cy='12' r='1' fill='%233a5570' opacity='0.35'/%3E%3C/svg%3E") repeat-x center,
      #0b1522;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    border-top: 1px solid rgba(30, 58, 90, 0.3);
  }
  
  .silver-bubble-row {
    display: flex;
    gap: 14px;
  }
  
  .bubble {
    width: 9px;
    height: 9px;
    position: relative;
  }
  .bubble::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #7aacd0, #3a5a7a);
    box-shadow: 0 0 4px rgba(74, 106, 138, 0.6);
  }
  /* 四瓣小花 — 气泡外围 */
  .bubble::after {
    content: '';
    position: absolute;
    top: -3px; left: -3px; right: -3px; bottom: -3px;
    background:
      radial-gradient(circle at 50% 0%, rgba(74,106,138,0.35) 2px, transparent 2px),
      radial-gradient(circle at 100% 50%, rgba(74,106,138,0.35) 2px, transparent 2px),
      radial-gradient(circle at 50% 100%, rgba(74,106,138,0.35) 2px, transparent 2px),
      radial-gradient(circle at 0% 50%, rgba(74,106,138,0.35) 2px, transparent 2px);
    pointer-events: none;
  }
  
  .header-border-ornament {
    display: flex;
    align-items: center;
    gap: 8px;
    opacity: 0.5;
  }
  
  .ornament-dot {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: #5a8aaa;
  }
  
  .ornament-line {
    width: 24px;
    height: 1px;
    background: linear-gradient(90deg, transparent, #5a8aaa, transparent);
  }
  
  .ornament-diamond {
    color: #5a8aaa;
    font-size: 0.45rem;
    text-shadow: 0 0 4px rgba(90, 138, 170, 0.5);
  }
  
  /* ========== 三栏布局（靛蓝蜡染配色） ========== */
  .main-layout {
    flex: 1;
    display: flex;
    gap: 2px;
    background: #0b1420;
    overflow: hidden;
    position: relative;
    z-index: 1;
  }

  .panel {
    background: rgba(14, 22, 38, 0.85);
    padding: 14px;
    display: flex;
    flex-direction: column;
    position: relative;
  }
  
  .panel-left {
    width: 300px;
    flex-shrink: 0;
    overflow-y: auto;
  }
  
  .panel-chat {
    flex: 1;
    min-width: 0;
  }
  
  .panel-right {
    width: 230px;
    flex-shrink: 0;
    overflow-y: auto;
  }
  
  .panel-title {
    font-size: 0.88rem;
    font-weight: 600;
    color: #7aaccc;
    padding-bottom: 8px;
    margin-bottom: 10px;
    border-bottom: 1px solid rgba(60, 90, 120, 0.3);
    display: flex;
    align-items: center;
    gap: 6px;
    letter-spacing: 0.06em;
  }
  
  .title-icon {
    color: #7aaccc;
    font-size: 0.7rem;
    opacity: 0.7;
  }

  .btn-clear-chat {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    background: rgba(255, 107, 107, 0.12);
    border: 1px solid rgba(255, 107, 107, 0.25);
    border-radius: 12px;
    color: #e08080;
    font-size: 0.65rem;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
  }

  .btn-clear-chat:hover {
    background: rgba(255, 107, 107, 0.25);
    border-color: rgba(255, 107, 107, 0.5);
    color: #ff8a8a;
    box-shadow: 0 0 8px rgba(255, 107, 107, 0.2);
  }

  /* ========== 华丽取景框（回纹几何边框） ========== */
  .ornate-frame {
    position: relative;
    background:
      /* 风雨桥建筑暗纹 */
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='90' viewBox='0 0 120 90'%3E%3Cpath d='M0 85 L0 55 L20 40 L40 55 L40 85' fill='none' stroke='%23142032' stroke-width='0.8' opacity='0.35'/%3E%3Cpath d='M40 85 L40 55 L60 40 L80 55 L80 85' fill='none' stroke='%23142032' stroke-width='0.8' opacity='0.35'/%3E%3Cpath d='M80 85 L80 55 L100 40 L120 55 L120 85' fill='none' stroke='%23142032' stroke-width='0.8' opacity='0.35'/%3E%3Cpath d='M0 55 L20 38 L40 55 L60 38 L80 55 L100 38 L120 55' fill='none' stroke='%23142032' stroke-width='0.6' opacity='0.2'/%3E%3Crect x='16' y='65' width='2' height='20' fill='%23142032' opacity='0.2'/%3E%3Crect x='26' y='65' width='2' height='20' fill='%23142032' opacity='0.2'/%3E%3Crect x='56' y='65' width='2' height='20' fill='%23142032' opacity='0.2'/%3E%3Crect x='66' y='65' width='2' height='20' fill='%23142032' opacity='0.2'/%3E%3C/svg%3E") repeat,
      #070e18;
    border: 1px solid rgba(60, 90, 120, 0.35);
    border-radius: 2px;
    margin-bottom: 10px;
    box-shadow: inset 0 0 50px rgba(0, 0, 0, 0.6), 0 4px 24px rgba(0, 0, 0, 0.6);
  }

  .frame-corner {
    position: absolute;
    z-index: 2;
    pointer-events: none;
  }
  .corner-tl { top: -2px; left: -2px; }
  .corner-tr { top: -2px; right: -2px; }
  .corner-bl { bottom: -2px; left: -2px; }
  .corner-br { bottom: -2px; right: -2px; }

  .frame-content {
    position: relative;
    aspect-ratio: 4 / 3;
    background: #060c16;
    overflow: hidden;
  }

  .camera-popup-inner {
    width: 100%;
    height: 100%;
    position: relative;
  }

  .camera-popup-inner video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .overlay-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    pointer-events: none;
    z-index: 3;
  }

  .viewfinder-grid {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .grid-h {
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 1px;
    background: rgba(100, 150, 200, 0.2);
  }

  .grid-v {
    position: absolute;
    left: 50%;
    top: 0;
    bottom: 0;
    width: 1px;
    background: rgba(100, 150, 200, 0.2);
  }

  .camera-label {
    position: absolute;
    bottom: 8px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.7);
    color: #7aaccc;
    font-size: 0.65rem;
    padding: 2px 10px;
    border-radius: 10px;
    letter-spacing: 0.06em;
    z-index: 5;
  }

  .camera-label.live {
    color: #5ecfd1;
    background: rgba(10, 20, 30, 0.85);
    border: 1px solid rgba(94, 207, 209, 0.4);
    animation: livePulse 2s ease-in-out infinite;
  }

  @keyframes livePulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }

  .preview-image-wrapper {
    width: 100%;
    height: 100%;
    position: relative;
  }

  .preview-image-wrapper img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .preview-overlay-label {
    position: absolute;
    bottom: 8px;
    right: 8px;
    background: rgba(0,0,0,0.65);
    color: #7aaccc;
    font-size: 0.65rem;
    padding: 3px 10px;
    border-radius: 10px;
    border: 1px solid rgba(100, 150, 200, 0.3);
  }

  .frame-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }

  .placeholder-illustration {
    opacity: 0.35;
    filter: drop-shadow(0 0 8px rgba(100, 140, 180, 0.2));
  }

  .placeholder-hint {
    font-size: 0.72rem;
    color: #4a6a8a;
    text-align: center;
    line-height: 1.6;
    letter-spacing: 0.04em;
  }

  /* ========== 左栏操作按钮组 ========== */
  .camera-actions {
    display: flex;
    gap: 8px;
    margin-bottom: 10px;
  }

  .btn-camera-main,
  .btn-capture,
  .btn-identify-main,
  .btn-retake-main {
    flex: 1;
    padding: 10px 12px;
    font-size: 0.8rem;
    font-weight: 600;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: all 0.25s;
    letter-spacing: 0.04em;
  }

  .btn-camera-main {
    background: linear-gradient(145deg, #1e3a5a, #142840);
    border: 1px solid #3a6a9a;
    color: #7ab8e0;
  }

  .btn-camera-main:hover {
    border-color: #5a9aca;
    box-shadow: 0 0 16px rgba(90, 154, 202, 0.3);
    background: linear-gradient(145deg, #244a6a, #1a3050);
  }

  .btn-capture {
    background: linear-gradient(145deg, #c0a86a, #8a7040);
    border: none;
    color: #0a1220;
    font-weight: 700;
    box-shadow: 0 4px 14px rgba(192, 168, 106, 0.35);
  }

  .btn-capture:hover {
    box-shadow: 0 6px 20px rgba(192, 168, 106, 0.55);
    transform: translateY(-1px);
  }

  .btn-close-cam {
    padding: 10px 14px;
    background: rgba(60, 40, 40, 0.6);
    border: 1px solid #5a3a3a;
    color: #c09090;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.2s;
  }

  .btn-close-cam:hover {
    background: rgba(80, 40, 40, 0.7);
    border-color: #8a4040;
  }

  .btn-identify-main {
    background: linear-gradient(145deg, #1a3a2a, #0f2a1a);
    border: 1px solid #3a6a4a;
    color: #70c090;
  }

  .btn-identify-main:hover:not(:disabled) {
    border-color: #5a9a6a;
    box-shadow: 0 0 16px rgba(90, 154, 106, 0.3);
  }

  .btn-identify-main:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-retake-main {
    background: linear-gradient(145deg, #2a3040, #1a2030);
    border: 1px solid #4a5a6a;
    color: #b0c0d0;
  }

  .btn-retake-main:hover {
    border-color: #6a7a8a;
    box-shadow: 0 0 12px rgba(100, 120, 140, 0.2);
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .hidden-canvas {
    display: none;
  }

  .hidden-audio {
    display: none;
  }

  /* ========== 未识别提示卡片 ========== */
  .unrecognized-card {
    background: linear-gradient(135deg, #1a1a2a, #151525);
    border: 1px solid #3a2a2a;
    border-radius: 10px;
    padding: 14px;
    text-align: center;
    margin-top: 10px;
  }

  .unrecognized-icon {
    margin-bottom: 6px;
    opacity: 0.8;
  }

  .unrecognized-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: #c09050;
    margin-bottom: 4px;
  }

  .unrecognized-desc {
    font-size: 0.7rem;
    color: #7a6a5a;
    line-height: 1.5;
    margin-bottom: 10px;
  }

  .btn-retake {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 20px;
    background: linear-gradient(135deg, #3a2a2a, #2a1a1a);
    border: 1px solid #6a4a4a;
    border-radius: 20px;
    color: #d0a080;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-retake:hover {
    background: linear-gradient(135deg, #4a3a3a, #3a2a2a);
    border-color: #8a6a6a;
    box-shadow: 0 4px 12px rgba(120, 80, 80, 0.3);
  }

  /* ========== 识别结果卡片 ========== */
  .result-card {
    background: linear-gradient(135deg, #1a2a35, #15202a);
    border: 1px solid rgba(74, 110, 140, 0.3);
    border-radius: 8px;
    padding: 12px;
    margin-top: 10px;
  }

  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .badge-type {
    font-weight: 600;
    color: #7aaccc;
    font-size: 0.85rem;
  }

  .badge-confidence {
    font-size: 0.68rem;
    background: rgba(40, 90, 60, 0.4);
    color: #60c090;
    padding: 2px 10px;
    border-radius: 12px;
    border: 1px solid rgba(90, 154, 106, 0.3);
  }

  .detail-row {
    display: flex;
    gap: 8px;
    font-size: 0.75rem;
    margin-bottom: 3px;
  }

  .detail-row .dl {
    color: #5a7a9a;
    min-width: 36px;
    font-weight: 500;
  }

  .detail-row .dv {
    color: #bcc8d8;
  }
  
  /* ========== 聊天区域 ========== */
  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 4px 2px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  /* 自定义滚动条 */
  .chat-messages::-webkit-scrollbar { width: 4px; }
  .chat-messages::-webkit-scrollbar-thumb {
    background: rgba(94, 207, 209, 0.4);
    border-radius: 4px;
  }
  .chat-messages::-webkit-scrollbar-track { background: transparent; }

  /* 错误提示 */
  .error-tip {
    color: #ff6b6b;
    font-size: 0.75rem;
    text-align: center;
    padding: 4px 0;
    margin-bottom: 2px;
  }

  /* -- 空状态欢迎区 -- */
  .empty-chat {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 10px;
  }

  /* 苗族阿妹 AI 助手卡片 */
  .miao-girl-card {
    width: 100%;
    max-width: 340px;
    box-sizing: border-box;
    padding: 24px 20px 20px;
    background: rgba(26, 59, 112, 0.85);
    border-radius: 16px;
    border: 1px solid rgba(94, 207, 209, 0.3);
    box-shadow: 0 0 20px rgba(94, 207, 209, 0.15);
    text-align: center;
  }

  .avatar-box {
    margin-bottom: 10px;
  }
  .girl-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 90px;
    height: 90px;
    border-radius: 50%;
    background: radial-gradient(circle at 40% 35%, #1e3048, #0d1828);
    border: 2px solid #5ecfd1;
    box-shadow: 0 0 14px rgba(94, 207, 209, 0.4);
  }

  .girl-name {
    font-size: 1.05rem;
    color: #5ecfd1;
    margin: 0 0 4px;
    font-weight: 600;
    letter-spacing: 0.06em;
  }

  .girl-desc {
    font-size: 0.78rem;
    color: #c0d8f0;
    margin: 0 0 14px;
    line-height: 1.5;
    letter-spacing: 0.04em;
  }

  .quick-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 12px;
  }

  .quick-card-btn {
    padding: 8px 6px;
    font-size: 0.7rem;
    border-radius: 20px;
  }

  .btn-welcome-session {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 24px;
    background: linear-gradient(135deg, #5ecfd1, #a882dd);
    border: none;
    border-radius: 20px;
    color: #fff;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.25s;
    box-shadow: 0 4px 14px rgba(94, 207, 209, 0.3);
    letter-spacing: 0.06em;
  }

  .btn-welcome-session:hover {
    box-shadow: 0 6px 22px rgba(94, 207, 209, 0.5);
    transform: translateY(-2px);
  }

  /* -- 聊天气泡 -- */
  .chat-bubble {
    display: flex;
    gap: 8px;
    animation: bubbleIn 0.35s ease-out both;
  }

  .chat-bubble.assistant {
    flex-direction: row;
    animation-delay: 0.1s;
  }

  .chat-bubble.user {
    flex-direction: row-reverse;
    animation-delay: 0s;
  }

  .loading-bubble {
    animation: loadingIn 0.3s ease-out both;
  }

  @keyframes bubbleIn {
    0%   { opacity: 0; transform: translateY(16px) scale(0.96); }
    100% { opacity: 1; transform: translateY(0) scale(1); }
  }

  @keyframes loadingIn {
    0%   { opacity: 0; transform: translateY(8px); }
    100% { opacity: 1; transform: translateY(0); }
  }

  .bubble-avatar .avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .avatar.ai {
    background: linear-gradient(135deg, #1a4a3a, #0a2a1a);
    border: 1px solid rgba(90, 154, 106, 0.4);
    color: #80d0a0;
  }

  .avatar.user {
    background: linear-gradient(135deg, #3a3a5a, #2a2a4a);
    border: 1px solid rgba(120, 120, 180, 0.4);
    color: #a0a0d0;
  }

  .bubble-content {
    max-width: 72%;
  }

  .bubble-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 3px;
  }

  .bubble-role {
    font-size: 0.65rem;
    font-weight: 600;
    color: #5a7a9a;
  }

  .bubble-time {
    font-size: 0.6rem;
    color: #3a5a6a;
  }

  .bubble-text {
    padding: 10px 14px;
    border-radius: 14px;
    font-size: 0.8rem;
    line-height: 1.55;
    color: #e8f0f8;
  }

  .assistant .bubble-text {
    background: linear-gradient(135deg, #3a6ea5, #5ecfd1);
    background-image: 
      radial-gradient(circle at 10% 10%, rgba(255,255,255,0.1) 0%, transparent 50%),
      linear-gradient(135deg, #3a6ea5, #5ecfd1);
    border-radius: 18px 18px 18px 4px;
    box-shadow: 0 2px 8px rgba(58, 110, 165, 0.3);
  }

  .user .bubble-text {
    background: linear-gradient(135deg, #a882dd, #c9b4f0);
    background-image: 
      radial-gradient(circle at 90% 90%, rgba(255,255,255,0.1) 0%, transparent 50%),
      linear-gradient(135deg, #a882dd, #c9b4f0);
    border-radius: 18px 18px 4px 18px;
    box-shadow: 0 2px 8px rgba(168, 130, 221, 0.3);
  }

  /* 加载动画气泡 */
  .bubble-text.loading {
    display: flex;
    gap: 5px;
    align-items: center;
    justify-content: center;
    min-width: 56px;
    padding: 10px 20px;
  }
  .dot {
    font-size: 0.5rem;
    animation: dotBounce 1.4s infinite ease-in-out;
  }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }

  @keyframes dotBounce {
    0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
    40% { transform: translateY(-5px); opacity: 1; }
  }

  /* 打字机光标闪烁 */
  .cursor-blink {
    animation: cursorFlash 0.8s step-end infinite;
    color: #5ecfd1;
    font-weight: 300;
  }
  @keyframes cursorFlash {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }

  /* -- 输入框 -- */
  .chat-input {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 8px;
  }

  .chat-input input {
    flex: 1;
    height: 36px;
    padding: 0 14px;
    border-radius: 20px;
    border: 1px solid rgba(94, 207, 209, 0.5);
    background: rgba(255,255,255,0.08);
    color: #e0e8f0;
    font-size: 0.8rem;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s;
  }

  .chat-input input:focus {
    border-color: rgba(94, 207, 209, 0.8);
    box-shadow: 0 0 8px rgba(94, 207, 209, 0.2);
  }

  .chat-input input::placeholder {
    color: rgba(255,255,255,0.35);
  }

  .chat-input input:disabled {
    opacity: 0.5;
  }

  .btn-send {
    padding: 0 18px;
    height: 36px;
    border-radius: 20px;
    border: none;
    background: linear-gradient(135deg, #5ecfd1, #a882dd);
    color: #fff;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
    letter-spacing: 0.04em;
  }

  .btn-send:hover:not(:disabled) {
    box-shadow: 0 0 14px rgba(94, 207, 209, 0.4);
    transform: translateY(-1px);
  }

  .btn-send:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  
  /* ========== 右侧面板 ========== */
  .right-section {
    margin-bottom: 14px;
  }

  .section-mini-title {
    display: block;
    font-size: 0.66rem;
    color: #4a7a9a;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
    text-transform: uppercase;
    font-weight: 500;
  }

  /* 参考图像小窗 */
  .preview-mini {
    background: #0a1220;
    border: 1px solid rgba(74, 110, 140, 0.3);
    border-radius: 6px;
    overflow: hidden;
    position: relative;
  }

  .preview-mini img {
    width: 100%;
    display: block;
    aspect-ratio: 4/3;
    object-fit: cover;
  }

  .preview-badge {
    position: absolute;
    bottom: 5px;
    right: 5px;
    background: rgba(0,0,0,0.7);
    color: #7aaccc;
    font-size: 0.58rem;
    padding: 1px 8px;
    border-radius: 8px;
  }

  .preview-placeholder-mini {
    background: #0a1220;
    border: 1px solid rgba(74, 110, 140, 0.2);
    border-radius: 6px;
    aspect-ratio: 4/3;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    color: #3a5a7a;
    font-size: 0.68rem;
  }

  /* 文化科普卡片 */
  .culture-section {
    margin-bottom: 14px;
  }

  .culture-card {
    background: linear-gradient(135deg, rgba(20, 40, 60, 0.5), rgba(10, 25, 40, 0.7));
    border: 1px solid rgba(74, 110, 140, 0.2);
    border-radius: 8px;
    padding: 12px;
    text-align: center;
  }

  .culture-icon {
    margin-bottom: 6px;
    opacity: 0.7;
  }

  .culture-title {
    font-size: 0.75rem;
    font-weight: 600;
    color: #7aaccc;
    margin-bottom: 4px;
  }

  .culture-desc {
    font-size: 0.65rem;
    color: #5a7a9a;
    line-height: 1.6;
    letter-spacing: 0.03em;
  }

  /* 快速提问 */
  .quick-links {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .quick-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 8px 10px;
    background: rgba(12, 20, 32, 0.7);
    border: 1px solid rgba(60, 90, 120, 0.3);
    border-radius: 8px;
    color: #6a9ab0;
    font-size: 0.72rem;
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
    letter-spacing: 0.04em;
  }

  .quick-btn:hover {
    border-color: rgba(100, 150, 200, 0.4);
    background: rgba(16, 28, 44, 0.9);
    color: #8ab8d0;
    box-shadow: 0 0 10px rgba(74, 106, 138, 0.2);
  }

  .qb-icon {
    font-size: 0.5rem;
    color: #5a8aaa;
    opacity: 0.7;
  }

  .btn-learn-more {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 10px;
    margin-top: 4px;
    background: linear-gradient(135deg, rgba(74, 130, 180, 0.15), rgba(60, 100, 150, 0.05));
    border: 1px solid rgba(74, 130, 180, 0.35);
    border-radius: 8px;
    color: #7ab4d0;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s;
    letter-spacing: 0.06em;
  }

  .btn-learn-more:hover {
    background: linear-gradient(135deg, rgba(74, 130, 180, 0.25), rgba(60, 100, 150, 0.1));
    border-color: rgba(100, 160, 210, 0.6);
    box-shadow: 0 0 18px rgba(74, 106, 138, 0.2);
    transform: translateY(-1px);
  }

  /* ========== 底部导航标签栏 ========== */
  .bottom-nav {
    display: flex;
    background: #0a1420;
    border-top: 1px solid rgba(74, 110, 140, 0.25);
    border-bottom: 1px solid rgba(74, 110, 140, 0.15);
    padding: 4px 16px;
    gap: 2px;
  }

  .nav-tab {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    padding: 8px 4px 6px;
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #4a6a8a;
    cursor: pointer;
    transition: all 0.2s;
  }

  .nav-tab:hover {
    background: rgba(74, 110, 140, 0.1);
    color: #6a9ab0;
  }

  .nav-tab.active {
    background: rgba(74, 130, 180, 0.15);
    color: #7aaccc;
  }

  .nav-tab.active .nav-icon {
    text-shadow: 0 0 8px rgba(74, 130, 180, 0.5);
  }

  .nav-icon {
    font-size: 0.9rem;
    line-height: 1;
  }

  .nav-label {
    font-size: 0.62rem;
    letter-spacing: 0.06em;
    font-weight: 500;
  }

  /* ========== 底部语音栏 ========== */
  .voice-bar {
    background: #0a1420;
    border-top: 1px solid rgba(74, 110, 140, 0.2);
    padding: 8px 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }

  /* TTS 语音播报开关 */
  .btn-tts-toggle {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 1px solid rgba(94, 207, 209, 0.35);
    background: rgba(94, 207, 209, 0.1);
    font-size: 1.1rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    flex-shrink: 0;
    line-height: 1;
  }
  .btn-tts-toggle:hover {
    background: rgba(94, 207, 209, 0.25);
    border-color: rgba(94, 207, 209, 0.6);
  }
  
  .voice-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #0f1d2e;
    border: 1px solid rgba(74, 110, 140, 0.35);
    border-radius: 24px;
    padding: 7px 18px;
    color: #b0c8d8;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 0.78rem;
  }

  .voice-btn:hover:not(:disabled) {
    border-color: rgba(192, 168, 106, 0.4);
  }
  
  .voice-btn.recording {
    background: #2a1a1a;
    border-color: rgba(255, 107, 107, 0.6);
    color: #ffaaaa;
    box-shadow: 0 0 20px rgba(255, 80, 80, 0.35);
    animation: recordPulse 1.5s ease-in-out infinite;
  }

  @keyframes recordPulse {
    0%, 100% { box-shadow: 0 0 20px rgba(255, 80, 80, 0.35); }
    50% { box-shadow: 0 0 40px rgba(255, 80, 80, 0.55); }
  }

  .voice-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  
  .voice-btn.recording .voice-icon {
    color: #ff8080;
  }
  
  .wave-bars {
    display: flex;
    gap: 3px;
    align-items: flex-end;
    height: 20px;
  }
  
  .wave-bars span {
    width: 4px;
    background: #e0a0a0;
    border-radius: 2px;
    animation: wave 0.8s infinite ease-in-out;
  }

  .wave-bars.live span {
    background: #ff6b6b;
    animation-duration: 0.6s;
  }
  
  .wave-bars span:nth-child(1) { height: 8px; animation-delay: 0s; }
  .wave-bars span:nth-child(2) { height: 15px; animation-delay: 0.1s; }
  .wave-bars span:nth-child(3) { height: 20px; animation-delay: 0.2s; }
  .wave-bars span:nth-child(4) { height: 12px; animation-delay: 0.3s; }
  .wave-bars span:nth-child(5) { height: 10px; animation-delay: 0.4s; }
  
  @keyframes wave {
    0%, 100% { transform: scaleY(0.6); opacity: 0.6; }
    50% { transform: scaleY(1); opacity: 1; }
  }
  
  .voice-info {
    font-size: 0.66rem;
    color: #3a5a7a;
    letter-spacing: 0.04em;
  }
  
  /* 响应式调整 */
  @media (max-width: 900px) {
    .main-layout {
      flex-direction: column;
    }
    .panel-left, .panel-right {
      width: 100%;
      flex-shrink: 1;
    }
    .panel-left {
      order: 1;
      max-height: 45vh;
    }
    .panel-chat {
      order: 2;
      flex: 1;
    }
    .panel-right {
      order: 3;
    }
    .bottom-nav {
      flex-wrap: wrap;
      gap: 4px;
    }
    .nav-tab {
      flex: 1 0 auto;
      min-width: 60px;
    }
    .status-group {
      display: none;
    }
  }
</style>