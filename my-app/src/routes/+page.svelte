<script>
  import { fade, slide, fly, scale } from 'svelte/transition';
  import { quintOut, elasticOut } from 'svelte/easing';
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
let audioUnlocked = false;           // 浏览器音频策略解锁标记
let ttsEnabled = $state(true);       // TTS 语音播报开关
let micStream = null;                // 录音媒体流
let showQRCode = $state(false);      // 二维码弹窗
let qrCodeDataUrl = $state('');      // 二维码 DataURL
let isMobile = $state(typeof navigator !== 'undefined' && (
    /Android|iPhone|iPad|iPod|webOS/i.test(navigator.userAgent) ||
    ('ontouchstart' in window && window.innerWidth < 1024)
  ));
let fileInputElement;                // 移动端隐藏文件输入（调用原生相机）
let showPreviewPopup = $state(false);// 移动端图像预览弹窗
let mobileRecogActive = $state(false); // 移动端识别进行中（覆盖层）

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

  // --- 二维码生成与切换 ---
  function toggleQRCode() {
    showQRCode = !showQRCode;
    if (showQRCode && !qrCodeDataUrl) {
      generateQRCode();
    }
  }
  function generateQRCode() {
    // 使用免费 QR 码 API 生成，无需外部依赖
    const currentUrl = window.location.origin + window.location.pathname;
    const apiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(currentUrl)}&bgcolor=0f1d2e&color=5ecfd1&margin=10`;
    // 直接设置 API URL（浏览器自动加载图片）
    qrCodeDataUrl = apiUrl;
  }
  function closeQRModal(e) {
    // 点击遮罩关闭
    if (e.target === e.currentTarget) {
      showQRCode = false;
    }
  }

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
  
  // YOLO 新模型类别（Clothes 10类 + Sliver 6类）共 16 类
  const yoloLabelMap = {
    // ===== Clothes.onnx：苗族服装 10 类 =====
    '几何挑花麻质上衣': '几何挑花麻质上衣',
    '刺绣围腰': '苗族刺绣围腰',
    '单边彩绣百褶裙': '单边彩绣百褶裙',
    '多层条纹布包头': '多层条纹布包头',
    '小型浮雕银胸吊牌': '浮雕银胸吊牌',
    '彩绣直筒绣花长裙': '彩绣直筒绣花长裙',
    '白色头帕': '白色头帕',
    '米白麻质短上衣': '米白麻质短上衣',
    '袖口破线绣纹样': '袖口破线绣纹样',
    '彩色十字挑花包头头巾': '十字挑花包头头巾',
    // ===== Sliver.onnx：苗族银饰 6 类 =====
    '全包式银花帽': '全包式银花帽',
    '平顶花丝银头冠': '平顶花丝银头冠',
    '立柱花丝银头冠': '立柱花丝银头冠',
    '银压领': '银压领',
    '雕花弯形银牛角冠': '雕花弯形银牛角冠',
    '黑苗银锁': '黑苗银锁',
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

  // --- 苗族服饰知识库（新模型 服装10类 + 银饰6类 + 3类兜底） ---
  const miaoKnowledge = {
    // ==================== Clothes.onnx 服装 10 类 ====================
    '几何挑花麻质上衣': {
      type: '几何挑花麻质上衣', confidence: 95,
      color: '麻质本色，几何挑花绣',
      pattern: '菱形纹、回纹、八角花纹',
      meaning: '苗族传统麻质上衣，以几何挑花工艺在领口、袖口、衣襟绣制菱形纹与回纹。这些抽象几何图案并非简单装饰——菱形代表田野与丰收，回纹象征生命轮回不息，八角花则对应苗族古历法中的八个节气，体现了苗族人民"观天象、顺四时"的农耕智慧。',
      custom: '挑花是苗族最古老的刺绣技法之一，不需画稿，全凭心中构图在麻布经纬上数纱挑绣。一位熟练绣娘每天可挑数百针，一件上衣需耗时数月完成。黔东南雷山、台江一带的几何挑花最为精美。',
    },
    '苗族刺绣围腰': {
      type: '苗族刺绣围腰', confidence: 94,
      color: '靛蓝底，五彩丝线绣',
      pattern: '涡旋纹、铜鼓纹、石榴花纹',
      meaning: '围腰是苗族女子日常劳作与盛装必备之物。围腰上最具标志性的纹样是涡旋纹——它并非普通装饰，而是苗族千年迁徙史诗的"活地图"：每一道螺旋代表一条跨越的江河（黄河、长江、沅水、清水江），铜鼓纹居中象征太阳与祖先权威，石榴花则寄托多子多福的美好祈愿。',
      custom: '苗族不同支系的围腰长度差异显著：黔东南西江苗寨围腰过膝，以红绿色绣为主；黔西北威宁一带则短至腰际，以素雅黑白为主。围腰长度和纹样是识别苗族支系身份的"活族谱"，苗家女子从小学习绣围腰，出嫁时需备数条作为嫁妆。',
    },
    '单边彩绣百褶裙': {
      type: '单边彩绣百褶裙', confidence: 93,
      color: '靛蓝黑底，单边彩绣',
      pattern: '几何条纹、菱形纹、花卉纹',
      meaning: '百褶裙是苗族女性盛装中最具视觉冲击力的服饰。裙身由数十乃至上百道细密褶裥组成，层叠如山峦起伏，寓意苗家先祖居住的崇山峻岭。单边彩绣的设计体现了苗族"不对称之美"的审美哲学——绣花只在一侧绽放，另一侧留白，恰似山水画中"疏可走马、密不透风"的构图智慧。',
      custom: '一条精美的百褶裙制作周期极长：首先将土布反复浸染靛蓝数十次直至深黑，再用指甲或骨片一道一道掐出褶裥，最后绣花。部分支系（如台江施洞）的百褶裙上绣有完整的苗族古歌图案，被称为"穿在身上的史书"。',
    },
    '多层条纹布包头': {
      type: '多层条纹布包头', confidence: 92,
      color: '黑白条纹交织',
      pattern: '横纹与竖纹交替排列',
      meaning: '多层条纹布包头是苗族识别支系和婚姻状况的重要标志。黑白相间的条纹并非随意设计——横纹代表大地与人间的秩序，竖纹象征通天之柱，横竖交织寓意天地交融、阴阳和谐。层数越多代表佩戴者家族地位越高，未婚女子通常包裹层次较少，已婚妇女则层叠厚重。',
      custom: '包头的包裹方式因支系而异：黔东南黄平一带以"牛角包"著称，将头帕盘绕成牛角状高耸于头顶；安顺地区则流行"圆盘包"，扁平如满月。在苗年、鼓藏节等盛大节日，女子还会在头帕上缀银花、银蝶作为点缀。',
    },
    '浮雕银胸吊牌': {
      type: '小型浮雕银胸吊牌', confidence: 91,
      color: '纯银浮雕，中心凸起',
      pattern: '太阳纹、乳钉纹、莲花纹',
      meaning: '小型浮雕银胸吊牌佩戴于胸前正心位置，是苗族盛装中的"护心镜"。中央太阳纹象征光明正气驱散邪祟，周围乳钉纹代表满天繁星寓意天地护佑，部分吊牌刻有莲花纹体现苗族与佛教文化的交融。浮雕工艺使纹样凸起于银面之上，立体感极强，在阳光下银光流转。',
      custom: '银胸吊牌通常由母亲传给女儿，是苗族女性嫁妆中的重要组成部分。苗族银匠制作胸牌时，先熔银铸板，再用錾刀一刀一刀雕出浮雕纹样——整个过程全凭心手相应，不借图纸。一枚精美胸牌从熔银到成品需经历熔炼、锻打、錾刻、镂空等三十余道工序。',
    },
    '彩绣直筒绣花长裙': {
      type: '彩绣直筒绣花长裙', confidence: 90,
      color: '深色底，彩绣花纹遍布',
      pattern: '花鸟纹、几何纹、缠枝花卉',
      meaning: '彩绣直筒长裙是苗族女子日常与礼仪皆宜的服饰。直筒剪裁简洁大方，精髓全在裙身遍布的彩绣——花鸟纹象征自然和谐，几何纹代表天地秩序，缠枝花卉寓意生命绵延不绝。走起路来裙摆微动，绣花若隐若现，体现了苗族"动静皆美"的穿衣哲学。',
      custom: '直筒绣花长裙多见于贵州台江、剑河一带的苗族支系。绣制一条长裙需先将整块布料绷在绣架上，绣娘俯身刺绣数月至半年。苗族绣娘有"绣花不绣夜"的传统——只在白天自然光下绣制，认为月光下绣出的花"没有魂"，体现了对刺绣艺术的敬畏之心。',
    },
    '白色头帕': {
      type: '白色头帕', confidence: 89,
      color: '纯白棉布，素净无染',
      pattern: '素白为主，间有淡色暗纹刺绣',
      meaning: '白色头帕是部分苗族支系最具辨识度的标志性头饰。在苗族色彩体系中，白色象征纯洁、庄重与对祖先的敬仰。白色头帕不仅具有实用功能——遮阳避尘、固定发髻——更承载着深厚的文化寓意：苗族古歌传唱，先祖从东方迁徙而来，白色代表东方日出之地，佩戴白色头帕即是铭记祖源、不忘来路。',
      custom: '白色头帕主要流行于黔西北威宁、赫章一带的苗族支系（俗称"白苗"）。头帕通常极长——展开可达数米，盘绕于头顶形成层叠如云朵的造型。盘帕是苗族女子清晨必做的功课，手法娴熟者仅需数分钟即可盘出整齐美观的头帕。',
    },
    '米白麻质短上衣': {
      type: '米白麻质短上衣', confidence: 88,
      color: '米白麻质原色，天然质朴',
      pattern: '简约几何纹样、暗纹织花',
      meaning: '米白麻质短上衣是苗族人民适应湿热山地气候的智慧结晶。麻质面料透气吸汗、凉爽舒适，短款剪裁便于田间劳作和山路行走。衣身虽以素色为主，但苗族女子会在袖口、领口织入暗纹几何花——这些含蓄的纹样是苗族"外简内繁"审美观的体现：日常不张扬，但细节绝不敷衍。',
      custom: '麻质上衣的制作从种麻开始——苗族至今保留着古老的种麻、沤麻、绩麻、纺线、织布全套工艺。一件麻质上衣从麻秆到成衣需经历十余道工序，耗时数月。苗族有"麻衣传家"的传统，母亲亲手为女儿织造的麻质上衣是出嫁时最珍贵的嫁妆之一。',
    },
    '袖口破线绣纹样': {
      type: '袖口破线绣纹样', confidence: 87,
      color: '彩色破线绣，丝线光泽闪烁',
      pattern: '花鸟纹、蝶纹、龙凤纹',
      meaning: '破线绣是苗族独有的超高难度刺绣技法——将一根丝线劈开分成8至12股细如发丝的丝线后再绣制。袖口是苗族服饰中绣工最集中的部位之一，因为苗族女子行走、劳作时袖口最引人注目。袖口上的蝴蝶纹直接指向苗族最核心的创世神话"蝴蝶妈妈"——传说蝴蝶妈妈生下十二个蛋，孵出人类始祖姜央及天地万物。',
      custom: '破线绣技法极其考验绣娘的眼力和耐心：一根标准丝线需用指尖反复揉搓使其松散，再用针尖一缕一缕劈开——劈得越细绣面越平滑光泽。一位绣娘一天劈出的丝线往往只够绣指甲盖大小的面积。台江施洞的破线绣袖口技艺被列为国家级非物质文化遗产。',
    },
    '十字挑花包头头巾': {
      type: '彩色十字挑花包头头巾', confidence: 86,
      color: '彩色棉线，十字挑花满绣',
      pattern: '十字纹、菱形纹、八角花',
      meaning: '十字挑花是苗族最具代表性的绣法之一，以布帛经纬纱交叉点为基础绣出一个个"十"字形单元，再由无数个"十"字组成精美图案。包头头巾上的十字挑花纹样并非随意之作——每一个十字都是一个"文字符号"，记录着苗族的历史事件、迁徙路线和祖训家规。苗族古歌中所唱的"十字绣花绣古理，千针万线记祖言"即源于此。',
      custom: '十字挑花包头头巾主要流行于贵州黄平、施秉一带。苗族女子从小随母亲学习十字挑花，至出嫁时需绣出数条精美头巾。头巾不仅用于包头，在苗族社交中更有"以巾传情"的传统——姑娘将亲手绣制的头巾赠予心上人，头巾绣工的精细程度直接体现女子的聪慧与家教。',
    },
    // ==================== Sliver.onnx 银饰 6 类 ====================
    '全包式银花帽': {
      type: '全包式银花帽', confidence: 96,
      color: '纯银银白，全包裹式造型',
      pattern: '银花簇拥、龙凤纹、缠枝纹',
      meaning: '全包式银花帽是苗族银饰中最为隆重的头饰类型，将佩戴者的头部完全包裹在银花之中。帽体由数十朵手工打制的银花层层堆叠而成，每朵银花由银匠一锤一錾手工成形——花瓣薄如蝉翼，花蕊细如针尖。银花簇拥如繁花盛开，象征苗族女性如花般绽放的生命力与家族的繁荣昌盛。龙凤纹则代表尊贵与吉祥。',
      custom: '一顶全包式银花帽的制作需耗时数月乃至一年。银匠先将银锭反复锻打成薄片，再剪出花瓣形状，用錾刀刻出花瓣纹理，最后将数十朵银花焊接组合于帽架之上。由于制作难度极高，全包式银花帽通常只在鼓藏节、苗年等最盛大的节日和婚礼上佩戴，是苗族女性一生中最珍贵的"高光配饰"。',
    },
    '平顶花丝银头冠': {
      type: '平顶花丝银头冠', confidence: 95,
      color: '纯银花丝，银光如织',
      pattern: '花丝编织纹、如意纹、蝴蝶纹',
      meaning: '平顶花丝银头冠是苗族花丝工艺的巅峰之作。花丝工艺将银料拉成直径不足一毫米的银丝，再以银丝为"线"编织出精美的几何与花卉图案。平顶设计庄重大气，象征天圆地方的宇宙观；花丝编织纹如蛛网般精细繁密，寓意家族人丁兴旺、血脉相连；如意纹寄托生活顺遂、万事如意的美好祝愿。',
      custom: '花丝工艺是苗族银匠最具代表性的绝技之一。拉丝时银匠需将粗银条反复穿过大小递减的钢模孔洞，从直径5毫米拉至0.2毫米的银丝——一根银丝往往需要数十次拉拔，稍有不慎就会断裂前功尽弃。一位技艺精湛的银匠一年只能制作一到两顶花丝银头冠，因此被誉为"月光下的艺术家"。',
    },
    '立柱花丝银头冠': {
      type: '立柱花丝银头冠', confidence: 94,
      color: '纯银立柱，花丝缠绕其上',
      pattern: '立柱造型、花丝缠绕纹、龙凤纹',
      meaning: '立柱花丝银头冠是苗族银角中最具视觉冲击力的类型——高高的银质立柱从冠顶冲天而起，花丝缠绕其上如藤蔓攀柱，象征苗族先祖"通天达地"的信仰。立柱本身代表连接天地的神树或天梯，花丝缠绕寓意吉祥与祝福绵延不绝。龙凤纹盘绕柱身，代表尊贵守护与阴阳和谐。',
      custom: '立柱花丝银头冠主要流行于贵州台江施洞一带，是当地苗族女子盛装中最醒目的标志。立柱的高低和花丝的精细程度直接体现佩戴者家族的经济实力与银匠技艺水平。节庆时苗族姑娘佩戴立柱银冠，行走间银柱微颤、银铃轻响，苗族认为这种声音能驱邪纳福、引来好运。',
    },
    '银压领': {
      type: '银压领', confidence: 93,
      color: '纯银银白，镂空工艺',
      pattern: '龙凤纹、缠枝纹、如意云头',
      meaning: '银压领是苗族女子佩戴于衣领之上的银饰，兼具实用与装饰双重功能。压领的主体为一弯如月牙的银片，佩戴时恰好压住衣领边缘使其挺括平整——这是"压领"之名的由来。银面上镂空雕刻龙凤纹和缠枝花卉，龙凤象征尊贵吉祥，缠枝寓意生命连绵。银压领在苗族盛装中起到"画龙点睛"的作用——将视线自然引向佩戴者的面容。',
      custom: '银压领的制作需银匠先将银板錾刻出纹样轮廓，再用细如针尖的镂刀将纹样周围掏空形成镂空效果——这一步极需耐心，稍有不慎便会戳破纹样主体前功尽弃。一件精美的银压领从熔银到成品需经历熔炼、锻打、錾刻、镂空、打磨等三十余道工序，耗时数日至数周。',
    },
    '雕花弯形银牛角冠': {
      type: '雕花弯形银牛角冠', confidence: 97,
      color: '纯银银白，弯角造型',
      pattern: '牛角纹、龙纹、花鸟纹、水波纹',
      meaning: '雕花弯形银牛角冠是苗族银角中最具辨识度的经典造型——形似水牛弯角🐂，高高扬起于头顶。牛角图腾源于苗族先祖蚩尤部落的牛崇拜，在苗族信仰中牛角象征祖先的勇猛力量与民族的顽强坚韧。牛角上錾刻龙纹代表权威守护、花鸟寓意吉祥、水波纹记录苗族历代跨越的江河，是真正的"戴在头上的民族史诗"。',
      custom: '苗族银角分为"平角"和"弯角"两种——平角多流行于清水江流域，弯角则以台江施洞为代表，角尖向内优雅弯曲形如新月。银牛角冠的制作从熔银铸板开始，银匠用铁锤反复锻打银板使其均匀平整，再以数十把大小形状各异的錾刀一刀一刀刻出精美纹饰。一顶银牛角冠重达一到两公斤，是苗族银匠技艺与家族财富的双重象征。',
    },
    '黑苗银锁': {
      type: '黑苗银锁', confidence: 92,
      color: '纯银银白，黑苗风格',
      pattern: '如意锁形、缠枝纹、长命富贵铭文',
      meaning: '黑苗银锁是黔东南黑苗支系特有的银饰类型，以如意锁为基本造型。锁面正中錾刻"长命富贵"等吉祥铭文直抒祝福，两侧镶嵌缠枝纹寓意福气绵长。在苗族传统中，银锁不仅是装饰品更是护身符——母亲将银锁赠予女儿时寄托了"锁住生命、锁住平安、锁住福气"的深深祝福，是苗族母女之间情感传递的重要信物。',
      custom: '黑苗银锁通常在外婆为外孙女举办的满月礼或周岁礼上赠送，是苗族"姥姥银"传统中最具代表性的物件。女孩从小佩戴银锁，至十二岁后由父母收起珍藏作为传家宝代代相传。银锁正面浮雕精美，背面往往刻有赠送日期和祝福语——一把银锁就是一部微型家族史。',
    },
    // ==================== 兜底（LLM 离线时本地应答） ====================
    '苗族百鸟衣': {
      type: '苗族百鸟衣', confidence: 96,
      color: '黑底彩绣，点缀真实鸟羽',
      pattern: '百鸟纹、蝶恋花纹、龙纹',
      meaning: '百鸟衣是苗族最古老最珍贵的祭祀礼服，源于苗族创世神话。相传蝴蝶妈妈生下十二个蛋请吉宇鸟孵化出人类始祖姜央——百鸟衣上的鸟羽和鸟纹便是纪念吉宇鸟的孵化之恩。衣上缀满上百根真实鸟羽与精美绣片，穿着时羽翼轻摇如百鸟朝凤，是苗族刺绣与服饰艺术的巅峰之作。',
      custom: '一件百鸟衣需采集数百根鸟羽，绣片上以蚕丝线绣出百鸟形态——绣法涵盖破线绣、打籽绣、马尾绣等十余种苗族独有技法。制作周期长达数年，只在鼓藏节祭祖大典由寨中德高望重的长者穿着。百鸟衣已被列为国家级非物质文化遗产。',
    },
    '苗族绣花围腰': {
      type: '苗族绣花围腰', confidence: 94,
      color: '靛蓝底，五彩丝线满绣',
      pattern: '涡旋纹、铜鼓纹、石榴花纹、蝴蝶纹',
      meaning: '苗族绣花围腰上的涡旋纹被称为"苗族迁徙地图"——每一道螺旋代表一条跨越的江河，从黄河、长江到沅水、清水江，铭刻着苗族先民数千公里的迁徙历程。铜鼓纹居中象征太阳与祖先的权威，石榴花寄托多子多福的祈愿，蝴蝶纹则指向创世神话中的蝴蝶妈妈。一方围腰，就是一部浓缩的苗族文化史。',
      custom: '围腰是苗族女子日常必备之物，不同支系样式差异显著——是识别支系身份的"活族谱"。女子从小学习绣围腰，到出嫁时需备数条精绣围腰作为嫁妆，围腰的绣工精细程度直接体现女方的聪慧与家教。',
    },
    '苗族银项圈': {
      type: '苗族银项圈', confidence: 97,
      color: '纯银银白，层层叠戴',
      pattern: '二龙抢宝、游鱼纹、乳钉纹、连环纹',
      meaning: '苗族银项圈以多层叠戴为特色——层数越多代表家族越富裕、地位越高。项圈上的二龙抢宝图案寓意守护与尊贵，游鱼纹代表生育繁衍与年年有余，乳钉纹则源于苗族古人对星辰的崇拜。银项圈不仅是财富的象征，更是连接苗族女性与祖先、自然、宇宙的精神纽带。',
      custom: '苗族银匠被誉为"月光下的艺术家"——一件银项圈需经历熔炼、锻打、拉丝、錾刻等三十余道工序。银项圈按重量分为三两三、六两六、九两九等吉利数字规格，最重的九两九银项圈通常只在鼓藏节祭祖大典上佩戴，是苗家世代相传的珍宝。',
    },
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
    // 移动端：调用原生照相机应用（无需实时预览）
    if (isMobile) {
      if (fileInputElement) {
        fileInputElement.value = '';  // 清空上次选择，确保 change 事件触发
        fileInputElement.click();
      }
      return;
    }
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

  // 移动端原生相机拍照回调
  function handleMobilePhoto(event) {
    const file = event.target?.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      capturedImage = e.target.result;
      detectedPatterns = [];
      recognitionFailed = false;
      recognitionDone = false;
      identificationResult = null;
      // 移动端拍照后自动触发 YOLO 识别
      mobileRecogActive = true;
      runYoloDetection();
    };
    reader.readAsDataURL(file);
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
    mobileRecogActive = false;  // 关闭移动端识别覆盖层
    // 移动端重新调用原生相机，桌面端重新打开摄像头
    if (isMobile) {
      fileInputElement?.click();
    } else {
      openCamera();
    }
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
    streamingText = '';
    // 先显示加载气泡（思考动画），等网络响应到达后再切换到流式气泡
    isLoading = true;
    // isStreaming 在拿到响应后再置 true

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

      // 响应到达，切换为流式气泡
      isStreaming = true;

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
            if (parsed.replace) {
              // 幻觉检测触发替换 → 清空已流式输出的文本，替换为安全回退语
              streamingText = parsed.content;
            } else if (parsed.content) {
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

  // --- 轻量 Markdown → HTML（处理 AI 输出的 **粗体** / 标题 / 列表）---
  function renderMarkdown(text) {
    let html = text;
    // 1. 粗体 **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // 2. 标题 ### Heading
    html = html.replace(/^### (.+)$/gm, '<h4 class="md-heading">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 class="md-heading">$1</h3>');
    // 3. 有序列表 1. item
    html = html.replace(/^(\d+)\. (.+)$/gm, '<li class="md-li"><span class="md-num">$1.</span> $2</li>');
    // 4. 无序列表 - item 或 * item
    html = html.replace(/^[-*] (.+)$/gm, '<li class="md-li md-bullet">$1</li>');
    // 5. 连续列表项包裹 <ul>
    html = html.replace(/(<li class="md-li.*?<\/li>\n?)+/g, '<ul class="md-list">$&</ul>');
    // 6. 段落：双换行
    html = html.replace(/\n\n/g, '</p><p>');
    // 7. 单换行 → <br>
    html = html.replace(/\n/g, '<br/>');
    // 8. 包裹顶层
    html = '<p>' + html + '</p>';
    // 9. 清理空段落
    html = html.replace(/<p>\s*<\/p>/g, '');
    // 10. 清理嵌套问题：列表内不应有 <p>
    html = html.replace(/<ul class="md-list"><p>/g, '<ul class="md-list">');
    html = html.replace(/<\/p><\/ul>/g, '</ul>');
    return html;
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
    // 清洗 Markdown/HTML，提取纯中文口语文本
    let plain = text
      .replace(/<[^>]*>/g, '')           // HTML 标签
      .replace(/&[^;]+;/g, '')           // HTML 实体
      .replace(/[""]/g, '"')             // 智能引号 → 直引号（MeloTTS 兼容）
      .replace(/['']/g, "'")             // 智能单引号
      .replace(/[《》〈〉「」『』【】〖〗«»]/g, '')  // 书名号/括号类（保留内部文字）
      .replace(/[;；:：]/g, '，')          // 分号/冒号 → 逗号（MeloTTS 兼容）
      .replace(/[…‥]/g, '。')            // 省略号 → 句号
      .replace(/[—–～〜]/g, '，')        // 破折号/波浪线 → 逗号
      .replace(/\*\*(.+?)\*\*/g, '$1')   // **粗体**
      .replace(/^#{1,4}\s+/gm, '')       // ### 标题
      .replace(/^[-*]\s+/gm, '')         // - 无序列表
      .replace(/^\d+\.\s+/gm, '')        // 1. 有序列表
      .replace(/[*_~`]/g, '')            // 残余标记符号
      .replace(/\n{2,}/g, '。')          // 双换行→句号
      .replace(/\n/g, '，')              // 单换行→逗号
      .replace(/\s+/g, '')               // 多余空白
      .trim();
    if (!plain) return;
    // 截断到 800 字，避免 TTS 模型超负载
    const short = plain.length > 800 ? plain.substring(0, 800) : plain;

    try {
      // 10s 超时保护：防止远程 TTS 不可达时阻塞 UI
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 10000);
      const resp = await fetch('/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: short }),
        signal: ctrl.signal
      });
      clearTimeout(timer);
      if (resp.ok) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const oldSrc = audioElement.src;

        // 等待音频完全加载后再播放，防止中途截断
        await new Promise((resolve, reject) => {
          audioElement.src = url;
          audioElement.load();
          let resolved = false;
          const done = (err) => {
            if (resolved) return;
            resolved = true;
            audioElement.removeEventListener('canplaythrough', onReady);
            audioElement.removeEventListener('error', onError);
            audioElement.removeEventListener('loadeddata', onReady);
            if (err) reject(err); else resolve();
          };
          const onReady = () => {
            // canplaythrough 可能过早触发，确认 readyState >= 3 再放行
            if (audioElement.readyState >= 3) done();
          };
          const onError = (e) => done(e);
          audioElement.addEventListener('canplaythrough', onReady);
          audioElement.addEventListener('loadeddata', onReady);
          audioElement.addEventListener('error', onError);
          // 超时保护：3s 后强制播放
          setTimeout(() => done(), 3000);
        });

        if (!audioUnlocked) {
          try { await audioElement.play(); audioUnlocked = true; } catch { /* 等用户交互 */ }
        }
        if (audioUnlocked) {
          audioElement.play().catch(e => console.warn('TTS 播放被阻止:', e.message));
        }
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
        <button class="btn-qr" onclick={toggleQRCode} title="手机扫码访问 / Scan to visit">
          <svg viewBox="0 0 24 24" width="15" height="15"><rect x="3" y="3" width="7" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="14" y="3" width="7" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="3" y="14" width="7" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M14 14h4v4M18 14v4h-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        </button>
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
          <!-- ── 移动端 UI：CSS @media 控制显示，完全独立于桌面端 ── -->
          <div class="mobile-frame-ui">
            {#if capturedImage}
              <div class="mobile-capture-done">
                <img src={capturedImage} alt="拍摄的图片" class="mobile-capture-thumb" />
                <span class="mobile-capture-text">{lang === 'zh' ? '已拍摄，点击下方按钮识别' : 'Photo taken, tap below to identify'}</span>
              </div>
            {:else}
              <div class="mobile-camera-placeholder">
                <button class="btn-mobile-capture-main" onclick={openCamera}>
                  <svg viewBox="0 0 24 24" width="28" height="28"><rect x="2" y="6" width="20" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>
                  <span>{lang === 'zh' ? '拍照识别' : 'Take Photo'}</span>
                </button>
              </div>
            {/if}
          </div>

          <!-- ── 桌面端 UI：CSS @media 控制显示 ── -->
          <div class="desktop-frame-ui">
            {#if cameraActive}
              <div class="camera-popup-inner" transition:scale={{ duration: 350, easing: elasticOut }}>
                <video bind:this={videoElement} autoplay playsinline muted></video>
                <canvas bind:this={overlayCanvas} class="overlay-canvas" width="640" height="480"></canvas>
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
              <div class="preview-image-wrapper" transition:scale={{ duration: 380, easing: quintOut }}>
                <img src={capturedImage} alt="拍摄的服饰图片" />
                <canvas bind:this={overlayCanvas} class="overlay-canvas" width="640" height="480"></canvas>
                <div class="preview-overlay-label">{t.capturedLabel[lang]}</div>
              </div>
            {:else}
              <div class="frame-placeholder">
                <div class="placeholder-illustration">
                  <svg viewBox="0 0 160 120" width="140" height="105">
                    <path d="M0 110 L0 80 Q30 55 60 72 Q90 50 120 68 Q150 48 160 60 L160 110 Z" fill="#111d2e" opacity="0.5"/>
                    <path d="M0 110 L0 90 Q40 65 80 82 Q120 60 160 78 L160 110 Z" fill="#0d1624" opacity="0.4"/>
                    <path d="M30 105 L30 72 L50 60 L70 72 L70 105" fill="none" stroke="#2a4a6a" stroke-width="1.2" opacity="0.6"/>
                    <path d="M70 105 L70 72 L90 60 L110 72 L110 105" fill="none" stroke="#2a4a6a" stroke-width="1.2" opacity="0.6"/>
                    <path d="M110 105 L110 72 L130 60 L150 72 L150 105" fill="none" stroke="#2a4a6a" stroke-width="1.2" opacity="0.5"/>
                    <path d="M30 72 L50 58 L70 72 L90 58 L110 72 L130 58 L150 72" fill="none" stroke="#2a4a6a" stroke-width="0.9" opacity="0.4"/>
                    <rect x="42" y="80" width="2" height="25" fill="#1a3048" opacity="0.4"/>
                    <rect x="52" y="80" width="2" height="25" fill="#1a3048" opacity="0.4"/>
                    <rect x="82" y="80" width="2" height="25" fill="#1a3048" opacity="0.35"/>
                    <rect x="92" y="80" width="2" height="25" fill="#1a3048" opacity="0.35"/>
                    <path d="M78 42 Q74 34 72 38 Q70 42 78 42" fill="none" stroke="#3a6a8a" stroke-width="0.7" opacity="0.5"/>
                    <path d="M78 42 Q82 34 84 38 Q86 42 78 42" fill="none" stroke="#3a6a8a" stroke-width="0.7" opacity="0.5"/>
                    <path d="M120 35 Q124 30 128 35" fill="none" stroke="#2a4a6a" stroke-width="0.6" opacity="0.4"/>
                    <path d="M132 30 Q136 25 140 30" fill="none" stroke="#2a4a6a" stroke-width="0.5" opacity="0.3"/>
                  </svg>
                </div>
                <p class="placeholder-hint">{t.placeholderHint1[lang]}<br/>{t.placeholderHint2[lang]}</p>
              </div>
            {/if}
          </div>
        </div>
      </div>

      <!-- 操作按钮组 -->
      <div class="camera-actions">
        {#if !cameraActive && !capturedImage}
          <button class="btn-camera-main" onclick={openCamera}>
            <svg viewBox="0 0 24 24" width="20" height="20"><rect x="2" y="6" width="20" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M7 4 L8.5 2 L15.5 2 L17 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            {isMobile ? (lang === 'zh' ? '拍照' : 'Photo') : t.identifyBtn[lang]}
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
        <div class="unrecognized-card" transition:scale={{ duration: 380, easing: elasticOut }}>
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
        <div class="result-card" transition:slide={{ duration: 400, easing: quintOut }}>
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
      <!-- 移动端原生相机：隐藏文件输入 -->
      <input type="file" bind:this={fileInputElement} accept="image/*" class="hidden-input" onchange={handleMobilePhoto} />
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
            <div class="chat-bubble {msg.role}" in:fly={{ y: 24, duration: 450, easing: quintOut }} out:scale={{ duration: 200, opacity: 0 }}>
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
                  <p>{@html renderMarkdown(msg.content)}</p>
                </div>
              </div>
            </div>
          {/each}

          {#if isStreaming}
            <div class="chat-bubble assistant streaming-bubble" in:fly={{ y: 20, duration: 400, easing: quintOut }}>
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
                  <p>{@html renderMarkdown(streamingText)}<span class="cursor-blink">|</span></p>
                </div>
              </div>
            </div>
          {/if}

          {#if isLoading && !isStreaming}
            <div class="chat-bubble assistant loading-bubble" in:fly={{ y: 20, duration: 400, easing: quintOut }}>
              <div class="bubble-avatar">
                <div class="avatar ai thinking">
                  <svg viewBox="0 0 24 24" width="14" height="14"><path d="M8 16 C4 8 10 2 12 2 C14 2 20 8 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
                </div>
              </div>
              <div class="bubble-content">
                <div class="bubble-header">
                  <span class="bubble-role">{t.aiAssistant[lang]}</span>
                  <span class="bubble-time">{lang === 'zh' ? '思考中…' : 'Thinking…'}</span>
                </div>
                <div class="bubble-text loading">
                  <span class="loading-dots">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                  </span>
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

  <!-- 底部语音交互栏（移动端：精简3按钮） -->
  <footer class="voice-bar mobile-only">
    <button class="mobbar-btn" onclick={openCamera} title="拍照">📷</button>
    <button class="mobbar-btn mic-btn" onclick={toggleListening} class:recording={isRecording} title={isRecording ? '录音中…' : '语音'}>
      <span class="mic-inner">{isRecording ? '🔴' : '🎤'}</span>
      {#if isRecording}
        <span class="mic-ripple"></span>
        <span class="mic-ripple delay"></span>
      {/if}
    </button>
    <button class="mobbar-btn" onclick={toggleTTS} title="播报">{ttsEnabled ? '🔊' : '🔇'}</button>
  </footer>

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

  <!-- ── 移动端识别反馈覆盖层 ── -->
  {#if isMobile && mobileRecogActive && capturedImage}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_interactive_supports_focus -->
    <div class="mobile-recog-overlay" onclick={() => mobileRecogActive = false} role="dialog" aria-modal="true" tabindex="-1" transition:fade={{ duration: 250 }}>
      <div class="mobile-recog-card" onclick={(e) => e.stopPropagation()} transition:scale={{ duration: 350, easing: elasticOut }}>
        <!-- 关闭按钮 -->
        <button class="recog-close" onclick={() => mobileRecogActive = false} aria-label="关闭">✕</button>

        <!-- 预览图 -->
        <div class="recog-image-box">
          <img src={capturedImage} alt="拍摄图片" class="recog-preview-img" />
          {#if isIdentifying}
            <div class="recog-scanning-overlay">
              <div class="recog-spinner-box">
                <span class="recog-spinner"></span>
                <span class="recog-scan-label">{lang === 'zh' ? 'YOLO 识别中…' : 'YOLO Identifying…'}</span>
              </div>
              <!-- 扫描线动画 -->
              <div class="scan-line"></div>
            </div>
          {/if}
        </div>

        <!-- 状态文字 -->
        <div class="recog-status">
          {#if isIdentifying}
            <div class="recog-status-identifying">
              <span class="recog-dot-pulse"></span>
              {lang === 'zh' ? '正在分析苗族服饰特征…' : 'Analyzing Miao costume features…'}
            </div>
          {:else if recognitionDone && identificationResult}
            <div class="recog-status-success">
              <span class="recog-check">✓</span>
              <span class="recog-type-label">{identificationResult.type}</span>
              <span class="recog-conf-badge">{identificationResult.confidence}%</span>
            </div>
            <p class="recog-meaning-preview">{identificationResult.meaning?.slice(0, 80)}…</p>
          {:else if recognitionDone && recognitionFailed}
            <div class="recog-status-fail">
              <span class="recog-fail-icon">⚠️</span>
              {lang === 'zh' ? '未识别到苗族服饰，请调整角度重试' : 'No Miao garment detected, try again'}
            </div>
          {/if}
        </div>

        <!-- 操作按钮 -->
        <div class="recog-actions">
          {#if recognitionDone}
            <button class="recog-btn recog-retake" onclick={retakePhoto}>
              <span>📷</span> {lang === 'zh' ? '重新拍摄' : 'Retake'}
            </button>
          {/if}
          <button class="recog-btn recog-dismiss" onclick={() => mobileRecogActive = false}>
            {lang === 'zh' ? '关闭' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- 二维码弹窗 -->
  {#if showQRCode}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_interactive_supports_focus -->
    <div class="qr-overlay" onclick={closeQRModal} onkeydown={(e) => e.key === 'Escape' && (showQRCode = false)} role="dialog" aria-modal="true" tabindex="-1" aria-label={lang === 'zh' ? '二维码弹窗' : 'QR Code Dialog'} transition:fade={{ duration: 250 }}>
      <div class="qr-modal" transition:scale={{ duration: 380, easing: elasticOut }}>
        <button class="qr-close" onclick={() => showQRCode = false} aria-label={lang === 'zh' ? '关闭二维码' : 'Close QR code'}>
          <svg viewBox="0 0 24 24" width="18" height="18"><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
        <div class="qr-icon-header">
          <span class="qr-diamond">◆</span>
          <span class="qr-title">{lang === 'zh' ? '手机扫码访问' : 'Scan to Visit'}</span>
          <span class="qr-diamond">◆</span>
        </div>
        <div class="qr-image-box">
          {#if qrCodeDataUrl}
            <img src={qrCodeDataUrl} alt="QR Code" class="qr-image" />
          {:else}
            <div class="qr-loading">
              <span class="spinner"></span>
              <span>{lang === 'zh' ? '生成中…' : 'Generating…'}</span>
            </div>
          {/if}
        </div>
        <p class="qr-hint">{lang === 'zh' ? '使用微信、支付宝或浏览器扫一扫，在手机上打开苗绣·识裳' : 'Scan with WeChat, Alipay or browser to open on your phone'}</p>
        <div class="qr-url">{typeof window !== 'undefined' ? window.location.origin + window.location.pathname : ''}</div>
      </div>
    </div>
  {/if}
</main>

<style>
  /* ========== 全局动画关键帧（必须在 :global 块内定义，否则 Svelte 作用域哈希会导致引用失败）========== */
  :global {
    @keyframes dotBounce {
      0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
      40% { transform: translateY(-5px); opacity: 1; }
    }
    @keyframes cursorFlash {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }
    @keyframes livePulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.7; }
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes wave {
      0%, 100% { transform: scaleY(0.6); opacity: 0.6; }
      50% { transform: scaleY(1); opacity: 1; }
    }
    @keyframes recordPulse {
      0%, 100% { box-shadow: 0 0 20px rgba(255, 80, 80, 0.35); }
      50% { box-shadow: 0 0 40px rgba(255, 80, 80, 0.55); }
    }
    @keyframes streamGlow {
      0%, 100% { box-shadow: 0 2px 8px rgba(58, 110, 165, 0.3); }
      50% { box-shadow: 0 2px 18px rgba(94, 207, 209, 0.5); }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to   { opacity: 1; }
    }
    @keyframes avatarGlow {
      0%, 100% { box-shadow: 0 0 6px rgba(94, 207, 209, 0.3); }
      50% { box-shadow: 0 0 16px rgba(94, 207, 209, 0.7); }
    }
  }

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
    transform: translateY(-2px) scale(1.02);
    box-shadow: 0 4px 18px rgba(94, 207, 209, 0.45);
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .miao-btn:active {
    transform: translateY(0) scale(0.97);
    transition: all 0.1s ease;
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
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    letter-spacing: 0.04em;
    flex-shrink: 0;
  }
  .btn-lang:hover {
    background: rgba(94, 207, 209, 0.28);
    box-shadow: 0 0 14px rgba(94, 207, 209, 0.4);
    transform: scale(1.08);
  }
  .btn-lang:active {
    transform: scale(0.95);
  }

  /* 二维码按钮 */
  .btn-qr {
    width: 36px;
    height: 28px;
    border-radius: 14px;
    border: 1px solid rgba(168, 130, 221, 0.45);
    background: rgba(168, 130, 221, 0.12);
    color: #c0a8e8;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    flex-shrink: 0;
  }
  .btn-qr:hover {
    background: rgba(168, 130, 221, 0.28);
    box-shadow: 0 0 16px rgba(168, 130, 221, 0.35);
    transform: scale(1.08);
  }
  .btn-qr:active {
    transform: scale(0.95);
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

  /* ── 移动/桌面 UI 隔离基类 ── */
  .mobile-frame-ui { display: none !important; }
  .desktop-frame-ui { display: contents !important; }

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
    box-shadow: 0 0 20px rgba(90, 154, 202, 0.4);
    background: linear-gradient(145deg, #244a6a, #1a3050);
    transform: translateY(-2px);
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .btn-camera-main:active {
    transform: translateY(0) scale(0.97);
    transition: all 0.1s ease;
  }

  .btn-capture {
    background: linear-gradient(145deg, #c0a86a, #8a7040);
    border: none;
    color: #0a1220;
    font-weight: 700;
    box-shadow: 0 4px 14px rgba(192, 168, 106, 0.35);
  }

  .btn-capture:hover {
    box-shadow: 0 6px 24px rgba(192, 168, 106, 0.6);
    transform: translateY(-2px) scale(1.03);
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .btn-capture:active {
    transform: translateY(0) scale(0.96);
    transition: all 0.1s ease;
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

  .hidden-canvas {
    display: none;
  }

  .hidden-input {
    position: absolute;
    left: -9999px;
    width: 1px;
    height: 1px;
    opacity: 0;
  }

  .hidden-audio {
    position: absolute;
    left: -9999px;
    width: 1px;
    height: 1px;
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
    box-shadow: 0 6px 26px rgba(94, 207, 209, 0.55);
    transform: translateY(-3px) scale(1.04);
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .btn-welcome-session:active {
    transform: translateY(0) scale(0.96);
    transition: all 0.1s ease;
  }

  /* -- 聊天气泡 -- */
  .chat-bubble {
    display: flex;
    gap: 8px;
    will-change: transform, opacity;
  }

  .chat-bubble.assistant {
    flex-direction: row;
  }

  .chat-bubble.user {
    flex-direction: row-reverse;
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

  /* Markdown 渲染样式 */
  .bubble-text :global(.md-heading) {
    margin: 6px 0 3px;
    font-size: 0.95rem;
    font-weight: 700;
    color: #d0e8ff;
  }
  .bubble-text :global(.md-list) {
    margin: 4px 0;
    padding-left: 16px;
    list-style: none;
  }
  .bubble-text :global(.md-li) {
    margin-bottom: 2px;
  }
  .bubble-text :global(.md-num) {
    color: #a0c8e0;
    font-weight: 600;
    margin-right: 4px;
  }
  .bubble-text :global(.md-bullet)::before {
    content: '•';
    color: #5ecfd1;
    margin-right: 6px;
  }

  .assistant .bubble-text {
    background: linear-gradient(135deg, #3a6ea5, #5ecfd1);
    background-image: 
      radial-gradient(circle at 10% 10%, rgba(255,255,255,0.1) 0%, transparent 50%),
      linear-gradient(135deg, #3a6ea5, #5ecfd1);
    border-radius: 18px 18px 18px 4px;
    box-shadow: 0 2px 8px rgba(58, 110, 165, 0.3);
    transition: box-shadow 0.4s ease;
  }
  /* 流式气泡：光晕呼吸动画 */
  .streaming-bubble .bubble-text {
    animation: streamGlow 2.5s ease-in-out infinite;
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
  .loading-dots {
    display: flex;
    gap: 6px;
  }
  .loading-dots .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.7);
    animation: dotBounce 1.4s infinite ease-in-out;
  }
  .loading-dots .dot:nth-child(2) { animation-delay: 0.2s; }
  .loading-dots .dot:nth-child(3) { animation-delay: 0.4s; }

  /* 思考中头像呼吸光晕 */
  .avatar.ai.thinking {
    animation: avatarGlow 1.5s ease-in-out infinite;
  }
  @keyframes avatarGlow {
    0%, 100% { box-shadow: 0 0 6px rgba(94, 207, 209, 0.3); }
    50% { box-shadow: 0 0 16px rgba(94, 207, 209, 0.7); }
  }

  /* 打字机光标闪烁 */
  .cursor-blink {
    animation: cursorFlash 0.7s ease-in-out infinite;
    color: #5ecfd1;
    font-weight: 300;
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
    box-shadow: 0 0 18px rgba(94, 207, 209, 0.5);
    transform: translateY(-2px) scale(1.04);
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .btn-send:active:not(:disabled) {
    transform: translateY(0) scale(0.96);
    transition: all 0.1s ease;
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
    border-color: rgba(100, 150, 200, 0.5);
    background: rgba(16, 28, 44, 0.92);
    color: #8ab8d0;
    box-shadow: 0 0 14px rgba(74, 106, 138, 0.3);
    transform: translateX(3px);
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .quick-btn:active {
    transform: translateX(1px) scale(0.97);
    transition: all 0.1s ease;
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
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .nav-tab:hover {
    background: rgba(74, 110, 140, 0.1);
    color: #6a9ab0;
    transform: translateY(-2px);
  }
  .nav-tab:active {
    transform: translateY(0) scale(0.96);
    transition: all 0.1s ease;
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

  /* 移动端工具栏：桌面端隐藏，手机端显示 */
  .mobile-only { display: none !important; }
  @media (max-width: 768px) {
    .mobile-only { display: flex !important; }
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
  
  .voice-info {
    font-size: 0.66rem;
    color: #3a5a7a;
    letter-spacing: 0.04em;
  }
  
  /* ========== 二维码弹窗 ========== */
  .qr-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(6, 12, 22, 0.82);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.25s ease-out;
  }

  .qr-modal {
    position: relative;
    background: linear-gradient(160deg, #101e32, #0c1828, #0f1d30);
    border: 1px solid rgba(94, 207, 209, 0.35);
    border-radius: 20px;
    padding: 32px 28px 24px;
    text-align: center;
    max-width: 360px;
    width: 90%;
    box-shadow:
      0 0 40px rgba(94, 207, 209, 0.18),
      0 0 80px rgba(0, 0, 0, 0.5),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .qr-modal::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 20px;
    padding: 1.5px;
    background: linear-gradient(135deg, #5ecfd1, #a882dd, #5ecfd1);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    pointer-events: none;
  }

  .qr-close {
    position: absolute;
    top: 12px;
    right: 14px;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(255, 255, 255, 0.06);
    color: #7aaccc;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .qr-close:hover {
    background: rgba(255, 107, 107, 0.2);
    border-color: rgba(255, 107, 107, 0.45);
    color: #ff8a8a;
    transform: rotate(90deg) scale(1.1);
  }

  .qr-icon-header {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 18px;
  }
  .qr-diamond {
    color: #5ecfd1;
    font-size: 0.55rem;
    opacity: 0.7;
    text-shadow: 0 0 6px rgba(94, 207, 209, 0.4);
  }
  .qr-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #d0e8ff;
    letter-spacing: 0.08em;
  }

  .qr-image-box {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 220px;
    height: 220px;
    margin: 0 auto 14px;
    background: #0f1d2e;
    border-radius: 14px;
    border: 1px solid rgba(94, 207, 209, 0.25);
    overflow: hidden;
    box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.4), 0 0 16px rgba(94, 207, 209, 0.1);
  }
  .qr-image {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }
  .qr-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    color: #4a7a9a;
    font-size: 0.78rem;
    letter-spacing: 0.04em;
  }

  .qr-hint {
    font-size: 0.7rem;
    color: #5a7a9a;
    line-height: 1.55;
    margin-bottom: 10px;
    letter-spacing: 0.03em;
  }
  .qr-url {
    font-size: 0.65rem;
    font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
    color: #3a6a8a;
    background: rgba(0, 0, 0, 0.3);
    padding: 6px 14px;
    border-radius: 10px;
    word-break: break-all;
    letter-spacing: 0.03em;
  }

  /* ==========================================
     响应式设计 — 手机端 / 平板 / 桌面三分立
     ========================================== */

  /* ── 平板竖屏 (≤1024px)：双栏 + 底栏导航 ── */
  @media (max-width: 1024px) {
    .main-layout {
      flex-direction: column;
    }
    .panel-left {
      width: 100%;
      max-height: 42vh;
      flex-shrink: 1;
      order: 1;
    }
    .panel-chat {
      order: 2;
      flex: 1;
      min-height: 280px;
    }
    .panel-right {
      width: 100%;
      order: 3;
      max-height: 30vh;
      overflow-y: auto;
    }
    .status-group {
      display: none;
    }
    .perf-panel {
      gap: 8px;
      font-size: 0.68rem;
    }
    .perf-panel .perf-mem,
    .perf-panel .perf-temp {
      display: none;
    }
    .ornate-frame {
      margin-bottom: 6px;
    }
    .frame-corner svg {
      width: 24px;
      height: 24px;
    }
  }

  /* ── 手机端 (≤768px)：单栏交互，触控优化 ── */
  @media (max-width: 768px) {
    .app-container {
      border-left: none;
      border-right: none;
      border-radius: 0;
    }
    .app-container::after {
      display: none;
    }

    /* 顶部导航压缩 */
    .app-header {
      margin: 0;
      border-radius: 0;
      border-left: none;
      border-right: none;
    }
    .header-pattern-top,
    .header-pattern-bottom {
      height: 12px;
    }
    .header-pattern-top {
      background-size: 120px 12px;
    }
    .header-main {
      padding: 6px 10px;
      gap: 6px;
    }
    .top-logo-text {
      font-size: 0.9rem;
      letter-spacing: 0.04em;
    }
    .ox-horn-icon svg {
      width: 40px;
      height: 20px;
    }
    .perf-panel {
      gap: 6px;
      font-size: 0.62rem;
    }
    .perf-item {
      display: none;
    }
    .perf-item:first-child {
      display: inline;  /* 仅保留 FPS */
    }
    .btn-qr { display: none; }
    .btn-lang {
      width: 28px;
      height: 24px;
      font-size: 0.6rem;
    }

    /* 单栏布局 — 聊天优先，相机压缩 */
    .main-layout {
      flex-direction: column;
      gap: 0;
      overflow-y: auto;
    }
    .panel-left {
      display: none !important;  /* 手机端完全隐藏图像预览区 */
    }
    .panel-chat {
      order: 2;
      flex: 1;
      padding: 6px 8px;
    }
    .panel-right {
      display: none;
    }
    .panel-title {
      font-size: 0.78rem;
      padding-bottom: 5px;
      margin-bottom: 6px;
    }

    /* 移动端：隐藏华丽取景框，改为紧凑相机区 */
    .ornate-frame {
      background: none;
      border: none;
      border-radius: 0;
      box-shadow: none;
      margin-bottom: 4px;
      padding: 0;
    }
    .frame-corner {
      display: none;
    }
    .frame-content {
      aspect-ratio: auto;
      background: transparent;
      min-height: 0;
    }

    /* CSS 驱动移动/桌面 UI 隔离（!important 确保绝对生效） */
    .mobile-frame-ui { display: block !important; }
    .desktop-frame-ui { display: none !important; }

    /* 移动端相机占位 */
    .mobile-camera-placeholder {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      padding: 8px 0;
    }
    .btn-mobile-capture-main {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 28px;
      background: linear-gradient(145deg, #c0a86a, #8a7040);
      border: none;
      border-radius: 24px;
      color: #0a1220;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(192, 168, 106, 0.35);
      transition: all 0.25s;
      min-height: 48px;
    }
    .btn-mobile-capture-main:active {
      transform: scale(0.96);
    }
    .mobile-camera-hint {
      font-size: 0.68rem;
      color: #4a6a8a;
      margin: 0;
    }

    /* 移动端拍摄完成提示 */
    .mobile-capture-done {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      padding: 8px 0;
    }
    .mobile-capture-thumb {
      width: 100%;
      max-width: 200px;
      max-height: 120px;
      object-fit: cover;
      border-radius: 10px;
      border: 1px solid rgba(94,207,209,0.3);
      display: block;
    }
    .mobile-capture-text {
      font-size: 0.72rem;
      color: #7aaccc;
    }

    /* 聊天面板 — 移动端输入框 fixed，与语音栏同层 */
    .chat-input {
      position: fixed;
      bottom: 66px;
      left: 0;
      right: 0;
      z-index: 99;
      background: #0e1626;  /* 不透明白底，防止文字穿透 */
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      padding: 8px 10px 8px;
      margin-top: 0;
      border-top: 1px solid rgba(94,207,209,0.2);
      box-shadow: 0 -4px 16px rgba(0,0,0,0.5);
    }
    .chat-messages {
      padding-bottom: 130px;  /* 输入框 ~60px + 按钮行 ~70px */
    }

    /* 隐藏桌面端实时取景元素 */
    .camera-popup-inner,
    .viewfinder-grid,
    .preview-image-wrapper,
    .preview-overlay-label,
    .frame-placeholder {
      display: none;
    }

    .camera-label {
      font-size: 0.6rem;
      padding: 2px 8px;
    }

    /* 按钮触控优化 — 最小 44px 点击区域 */
    .camera-actions {
      gap: 6px;
      margin-bottom: 4px;
    }
    .btn-camera-main,
    .btn-capture,
    .btn-identify-main,
    .btn-retake-main,
    .btn-close-cam {
      padding: 12px 14px;
      font-size: 0.85rem;
      min-height: 44px;
      border-radius: 10px;
    }

    /* 聊天气泡 */
    .bubble-content {
      max-width: 88%;
    }
    .bubble-text {
      font-size: 0.85rem;
      padding: 10px 14px;
    }
    .chat-input input {
      height: 44px;
      font-size: 0.9rem;
      border-radius: 22px;
    }
    .btn-send {
      height: 44px;
      padding: 0 20px;
      font-size: 0.85rem;
      border-radius: 22px;
    }

    /* 识别结果卡片 */
    .result-card {
      padding: 10px;
    }
    .badge-type {
      font-size: 0.78rem;
    }
    .detail-row {
      font-size: 0.7rem;
    }

    /* 底部导航 — 手机端隐藏 */
    .bottom-nav {
      display: none;
    }

    /* 语音栏 — 移动端：紧贴输入框下方，无背景 */
    .voice-bar {
      padding: 6px 8px;
      gap: 6px;
    }
    .voice-bar:not(.mobile-only) {
      display: none;
    }
    .voice-bar.mobile-only {
      display: flex;
      justify-content: space-evenly;
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      z-index: 100;
      background: #0e1626;
      border-top: 1px solid rgba(94,207,209,0.15);
      padding: 12px 8px max(16px, env(safe-area-inset-bottom));
    }
    .voice-btn, .voice-info {
      display: none;
    }
    .mobbar-btn {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 1px solid rgba(94,207,209,0.3);
      background: rgba(94,207,209,0.08);
      font-size: 1.2rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
      color: #5ecfd1;
      position: relative;
    }
    .mobbar-btn:active {
      background: rgba(94,207,209,0.3);
      transform: scale(0.92);
    }

    /* ── 麦克风录音特效 ── */
    .mobbar-btn.mic-btn {
      transition: all 0.35s ease;
    }
    .mobbar-btn.mic-btn.recording {
      background: rgba(255, 70, 70, 0.18);
      border-color: rgba(255, 90, 90, 0.6);
      color: #ff6b6b;
      box-shadow: 0 0 20px rgba(255, 70, 70, 0.45);
      animation: micPulse 1.2s ease-in-out infinite;
    }
    .mic-inner {
      position: relative;
      z-index: 2;
    }
    /* 扩散波纹 */
    .mic-ripple {
      position: absolute;
      inset: -6px;
      border-radius: 50%;
      border: 2px solid rgba(255, 90, 90, 0.5);
      animation: rippleOut 1.5s ease-out infinite;
      pointer-events: none;
    }
    .mic-ripple.delay {
      animation-delay: 0.75s;
    }

    @keyframes micPulse {
      0%, 100% { box-shadow: 0 0 12px rgba(255, 70, 70, 0.35); }
      50%      { box-shadow: 0 0 28px rgba(255, 70, 70, 0.65); }
    }
    @keyframes rippleOut {
      0%   { transform: scale(0.8); opacity: 0.9; }
      100% { transform: scale(1.6); opacity: 0; }
    }
    .btn-tts-toggle { display: none; }

    /* ── 移动端识别反馈覆盖层 ── */
    .mobile-recog-overlay {
      position: fixed;
      inset: 0;
      z-index: 1000;
      background: rgba(6, 12, 22, 0.88);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .mobile-recog-card {
      position: relative;
      background: linear-gradient(160deg, #101e32, #0c1828);
      border: 1px solid rgba(94, 207, 209, 0.3);
      border-radius: 18px;
      padding: 20px 16px 16px;
      width: 100%;
      max-width: 340px;
      box-shadow: 0 0 40px rgba(94, 207, 209, 0.12), 0 8px 32px rgba(0,0,0,0.5);
    }
    .recog-close {
      position: absolute;
      top: 10px;
      right: 12px;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.05);
      color: #7aaccc;
      font-size: 0.85rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 5;
    }
    .recog-image-box {
      position: relative;
      width: 100%;
      aspect-ratio: 4/3;
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid rgba(94,207,209,0.2);
      margin-bottom: 12px;
      background: #060c16;
    }
    .recog-preview-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    /* 扫描中覆盖层 */
    .recog-scanning-overlay {
      position: absolute;
      inset: 0;
      background: rgba(6, 12, 22, 0.55);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    .recog-spinner-box {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      z-index: 2;
    }
    .recog-spinner {
      width: 40px;
      height: 40px;
      border: 3px solid rgba(94,207,209,0.2);
      border-top-color: #5ecfd1;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    .recog-scan-label {
      font-size: 0.82rem;
      color: #5ecfd1;
      font-weight: 600;
      letter-spacing: 0.04em;
    }
    /* 扫描线 */
    .scan-line {
      position: absolute;
      left: 0;
      right: 0;
      height: 2px;
      background: linear-gradient(90deg, transparent, #5ecfd1, transparent);
      box-shadow: 0 0 12px rgba(94,207,209,0.6);
      animation: scanMove 1.8s ease-in-out infinite;
      z-index: 1;
    }
    @keyframes scanMove {
      0%   { top: 0%; }
      50%  { top: 95%; }
      100% { top: 0%; }
    }

    /* 状态区 */
    .recog-status {
      margin-bottom: 12px;
      text-align: center;
    }
    .recog-status-identifying {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-size: 0.8rem;
      color: #8ab8d0;
    }
    .recog-dot-pulse {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #5ecfd1;
      animation: livePulse 1.2s ease-in-out infinite;
      display: inline-block;
    }
    .recog-status-success {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .recog-check {
      color: #4cd9b2;
      font-weight: 700;
      font-size: 1.1rem;
    }
    .recog-type-label {
      font-size: 0.9rem;
      font-weight: 700;
      color: #d0e8ff;
    }
    .recog-conf-badge {
      font-size: 0.7rem;
      background: rgba(40, 90, 60, 0.5);
      color: #60c090;
      padding: 2px 10px;
      border-radius: 12px;
      border: 1px solid rgba(90, 154, 106, 0.3);
    }
    .recog-meaning-preview {
      font-size: 0.7rem;
      color: #6a9ab0;
      line-height: 1.5;
      margin: 8px 0 0;
      text-align: left;
      padding: 0 4px;
    }
    .recog-status-fail {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      font-size: 0.82rem;
      color: #e0a060;
      font-weight: 600;
    }
    .recog-fail-icon { font-size: 1.1rem; }

    /* 操作按钮 */
    .recog-actions {
      display: flex;
      gap: 10px;
    }
    .recog-btn {
      flex: 1;
      padding: 10px 14px;
      border-radius: 22px;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s;
      letter-spacing: 0.04em;
    }
    .recog-retake {
      background: linear-gradient(145deg, #c0a86a, #8a7040);
      border: none;
      color: #0a1220;
      box-shadow: 0 3px 12px rgba(192, 168, 106, 0.3);
    }
    .recog-retake:active { transform: scale(0.96); }
    .recog-dismiss {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.15);
      color: #7aaccc;
    }
    .recog-dismiss:active { background: rgba(255,255,255,0.12); }

    /* 欢迎卡片 */
    .miao-girl-card {
      padding: 16px 14px;
      max-width: 100%;
    }
    .girl-avatar {
      width: 64px;
      height: 64px;
    }
    .girl-name {
      font-size: 0.95rem;
    }
    .quick-cards {
      grid-template-columns: 1fr;
    }

    /* 未识别提示 */
    .unrecognized-card {
      padding: 10px;
    }
    .unrecognized-title {
      font-size: 0.8rem;
    }

    /* 二维码弹窗 */
    .qr-modal {
      padding: 20px 14px 16px;
      max-width: 300px;
    }
    .qr-image-box {
      width: 180px;
      height: 180px;
    }
    .qr-title {
      font-size: 0.85rem;
    }
  }

  /* ── 极小屏 (≤400px) ── */
  @media (max-width: 400px) {
    .top-logo-text {
      font-size: 0.78rem;
    }
    .panel-left {
      max-height: 35vh;
    }
    .frame-content {
      aspect-ratio: 1/1;
    }
    .chat-input input {
      font-size: 0.8rem;
    }
    .btn-send {
      font-size: 0.75rem;
      padding: 0 14px;
    }
  }

  /* ── 桌面宽屏 (≥1400px)：三栏宽松间距 ── */
  @media (min-width: 1400px) {
    .app-container {
      max-width: 1600px;
    }
    .panel-left {
      width: 360px;
    }
    .panel-right {
      width: 280px;
    }
    .main-layout {
      gap: 12px;
    }
    .ornate-frame {
      border-width: 2px;
    }
  }
</style>
