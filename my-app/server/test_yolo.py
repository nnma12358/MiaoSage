#!/usr/bin/env python3
"""
苗绣·识裳 — YOLO 双模型系统端测试
====================================
在容器构建前验证 ONNX 模型加载和推理 Pipeline 正确性。

用法:
  python server/test_yolo.py                    # 自动查找模型 + 合成图测试
  python server/test_yolo.py --image test.jpg   # 指定测试图片
  python server/test_yolo.py --quick            # 仅加载测试（不推理）

通过标准: 所有断言通过 → exit 0  /  任一失败 → exit 1
"""

import os, sys, time, io, json, logging, argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------- 配置 ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("yolo-test")

SERVER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SERVER_DIR.parent

# 模型查找路径（优先级递减）
MODEL_SEARCH = [
    SERVER_DIR,                              # server/
    PROJECT_DIR,                             # my-app/
    PROJECT_DIR.parent / "CV",               # CV/
    Path("/app"),                            # Docker 容器内
    Path("/app/models"),                     # Docker 备选
]


# ============================================================
# 1. 模型查找
# ============================================================
def find_model(filename: str) -> str:
    """按优先级查找 ONNX 模型文件"""
    for base in MODEL_SEARCH:
        candidate = base / filename
        if candidate.exists():
            logger.info(f"  ✓ 找到: {candidate}")
            return str(candidate)
    return ""


# ============================================================
# 2. 合成测试图（模拟苗族服饰场景）
# ============================================================
def create_test_image(size: int = 640) -> Image.Image:
    """
    生成带几何图案的合成测试图，模拟检测场景。
    包含不同颜色区块，可被模型误检测或用于完整性测试。
    """
    img = Image.new("RGB", (size, size), color=(40, 40, 60))
    draw = ImageDraw.Draw(img)

    # 银饰模拟区（亮色块）
    draw.rectangle([100, 80, 300, 200], fill=(200, 210, 220), outline=(180, 190, 200), width=3)
    draw.ellipse([140, 100, 260, 180], fill=(220, 225, 235))
    draw.rectangle([120, 300, 280, 420], fill=(190, 200, 210), outline=(170, 180, 190), width=3)

    # 人物模拟区（暖色块）
    draw.rectangle([350, 100, 550, 450], fill=(180, 140, 120), outline=(160, 120, 100), width=4)
    draw.ellipse([400, 50, 500, 150], fill=(200, 160, 140))  # 头部

    # 装饰纹理
    for x in range(120, 280, 30):
        draw.line([(x, 310), (x + 15, 410)], fill=(150, 160, 170), width=2)

    # 标签
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    draw.text((10, 10), "MiaoSage Test Image", fill=(255, 255, 255), font=font)

    return img


# ============================================================
# 3. ONNX 模型加载器（从 yolo_server.py 提取，无 FastAPI 依赖）
# ============================================================
class ONNXDetector:
    """独立 ONNX 推理器，不依赖 FastAPI"""

    def __init__(self, model_path: str, class_names: dict):
        import onnxruntime as ort
        self.model_path = model_path
        self.names = class_names
        self._session = ort.InferenceSession(model_path, providers=ort.get_available_providers())
        _, _, h, w = self._session.get_inputs()[0].shape
        self._input_shape = (w, h)
        self._in_name = self._session.get_inputs()[0].name
        logger.info(f"  ONNX 加载: {os.path.basename(model_path)} shape={self._input_shape}")

    def detect(self, img: Image.Image, conf_thresh: float = 0.25) -> list:
        w_in, h_in = self._input_shape
        img_w, img_h = img.size
        arr = np.array(img.resize((w_in, h_in), Image.BILINEAR), dtype=np.float32) / 255.0
        arr = np.expand_dims(arr.transpose(2, 0, 1), axis=0)
        preds = np.squeeze(self._session.run(None, {self._in_name: arr})[0])
        return self._postprocess(preds, img_w, img_h, w_in, h_in, conf_thresh)

    def _postprocess(self, preds, img_w, img_h, in_w, in_h, conf_thresh):
        bbox_raw, scores = preds[:4, :], preds[4:, :]
        class_ids = np.argmax(scores, axis=0)
        confs = np.max(scores, axis=0)
        mask = confs > conf_thresh
        if not mask.any():
            return []
        bbox_raw, class_ids, confs = bbox_raw[:, mask], class_ids[mask], confs[mask]
        cx, cy, w, h = bbox_raw[0], bbox_raw[1], bbox_raw[2], bbox_raw[3]
        x1 = (cx - w / 2) * img_w / in_w
        y1 = (cy - h / 2) * img_h / in_h
        x2 = (cx + w / 2) * img_w / in_w
        y2 = (cy + h / 2) * img_h / in_h
        areas = (x2 - x1) * (y2 - y1)
        order = np.argsort(confs)[::-1]
        keep = []
        while len(order) > 0:
            i = order[0]; keep.append(i)
            if len(order) == 1: break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            order = order[1:][inter / (areas[i] + areas[order[1:]] - inter + 1e-6) < 0.45]
        dets = []
        for i in keep:
            cls_id = int(class_ids[i])
            dets.append({
                "class": self.names.get(cls_id, f"cls_{cls_id}"),
                "cls_id": cls_id,
                "confidence": round(float(confs[i]), 4),
                "bbox": {"x1": round(float(x1[i]), 1), "y1": round(float(y1[i]), 1),
                         "x2": round(float(x2[i]), 1), "y2": round(float(y2[i]), 1)},
            })
        return sorted(dets, key=lambda d: d["confidence"], reverse=True)


_MIAO_SILVER_CLASSES = {
    0: "流苏帽 (tassel_hat)",
    1: "苗族牛角银头饰 (miao_ox_horn_silver_headwear)",
    2: "苗族银发簪 (miao_silver_hairpin)",
    3: "苗族银冠 (miao_silver_crown)",
    4: "苗族银胸饰 (miao_silver_chest_ornament)",
    5: "苗族银锁 (miao_silver_lock)",
    6: "苗族银项链 (miao_silver_necklace)",
    7: "银头饰 (silver_headdress)",
}

_MIAO_CLOTHES_CLASSES = {
    0: "苗族便装 (Miao casual wear)",
    1: "苗族盛装 (Miao ceremonial dress)",
}


class MiaoPipelineDetector:
    """与 yolo_server.py 逻辑完全一致的 Pipeline 检测器"""

    def __init__(self, silver_path: str, clothes_path: str):
        self.silver = ONNXDetector(silver_path, _MIAO_SILVER_CLASSES)
        self.clothes = ONNXDetector(clothes_path, _MIAO_CLOTHES_CLASSES)
        logger.info("  双模型 Pipeline 就绪 ✓")

    def detect(self, img: Image.Image, mode: str = "silver",
               use_person_filter: bool = True) -> dict:
        result = {"mode": mode, "clothes": [], "silver": [],
                  "silver_filtered": [], "triggered": False, "cost_ms": {}}

        if mode == "silver":
            t0 = time.perf_counter()
            result["silver"] = self.silver.detect(img)
            result["silver_filtered"] = result["silver"]
            result["cost_ms"]["silver"] = round((time.perf_counter() - t0) * 1000, 1)

        elif mode == "clothes":
            t0 = time.perf_counter()
            result["clothes"] = self.clothes.detect(img)
            result["cost_ms"]["clothes"] = round((time.perf_counter() - t0) * 1000, 1)

        elif mode == "pipeline":
            t0 = time.perf_counter()
            clothes_dets = self.clothes.detect(img)
            result["clothes"] = clothes_dets
            result["cost_ms"]["clothes"] = round((time.perf_counter() - t0) * 1000, 1)
            has_trigger = len(clothes_dets) > 0
            result["triggered"] = has_trigger

            if has_trigger or len(clothes_dets) == 0:
                t0 = time.perf_counter()
                silver_raw = self.silver.detect(img)
                result["silver"] = silver_raw
                result["cost_ms"]["silver"] = round((time.perf_counter() - t0) * 1000, 1)
                if use_person_filter and clothes_dets:
                    result["silver_filtered"] = self._filter_by_person(silver_raw, clothes_dets)
                else:
                    result["silver_filtered"] = silver_raw

        result["cost_ms"]["total"] = round(
            sum(v for v in result["cost_ms"].values() if isinstance(v, (int, float))), 1)
        return result

    @staticmethod
    def _filter_by_person(silver_dets, clothes_dets):
        filtered = []
        for s in silver_dets:
            scx = (s["bbox"]["x1"] + s["bbox"]["x2"]) / 2
            scy = (s["bbox"]["y1"] + s["bbox"]["y2"]) / 2
            for c in clothes_dets:
                if (c["bbox"]["x1"] <= scx <= c["bbox"]["x2"] and
                    c["bbox"]["y1"] <= scy <= c["bbox"]["y2"]):
                    filtered.append(s)
                    break
        return filtered


# ============================================================
# 4. 测试套件
# ============================================================
class TestSuite:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_true(self, condition, msg: str):
        if condition:
            self.passed += 1
            logger.info(f"  ✅ PASS: {msg}")
        else:
            self.failed += 1
            self.errors.append(msg)
            logger.error(f"  ❌ FAIL: {msg}")

    def assert_equal(self, actual, expected, msg: str):
        ok = actual == expected
        if ok:
            self.passed += 1
            logger.info(f"  ✅ PASS: {msg} (={actual})")
        else:
            self.failed += 1
            self.errors.append(f"{msg}: expected={expected}, got={actual}")
            logger.error(f"  ❌ FAIL: {msg} expected={expected} got={actual}")

    def assert_gt(self, actual, threshold, msg: str):
        ok = actual > threshold
        if ok:
            self.passed += 1
            logger.info(f"  ✅ PASS: {msg} (={actual} > {threshold})")
        else:
            self.failed += 1
            self.errors.append(f"{msg}: {actual} <= {threshold}")
            logger.error(f"  ❌ FAIL: {msg} {actual} <= {threshold}")

    def assert_lt(self, actual, threshold, msg: str):
        ok = actual < threshold
        if ok:
            self.passed += 1
            logger.info(f"  ✅ PASS: {msg} (={actual} < {threshold})")
        else:
            self.failed += 1
            self.errors.append(f"{msg}: {actual} >= {threshold}")
            logger.error(f"  ❌ FAIL: {msg} {actual} >= {threshold}")

    def summary(self) -> int:
        total = self.passed + self.failed
        logger.info("=" * 60)
        logger.info(f"  测试结果: {self.passed}/{total} 通过, {self.failed} 失败")
        if self.errors:
            logger.error("  失败项:")
            for e in self.errors:
                logger.error(f"    - {e}")
        logger.info("=" * 60)
        return 0 if self.failed == 0 else 1


# ============================================================
# 5. 主测试流程
# ============================================================
def run_tests(image_path: str = "", quick: bool = False):
    ts = TestSuite()

    # ---- 阶段 0: 环境检查 ----
    logger.info("\n" + "=" * 60)
    logger.info("  阶段 0: 环境检查")
    logger.info("=" * 60)

    # Python 版本
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    ts.assert_gt(sys.version_info.minor, 8, f"Python >= 3.9 (当前 {py_ver})")

    # onnxruntime
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        ts.assert_true(True, f"onnxruntime 可用 (providers={providers[:2]}...)")
    except ImportError:
        ts.assert_true(False, "onnxruntime 未安装")
        return ts.summary()

    # Pillow, numpy
    try:
        import numpy as np
        from PIL import Image
        ts.assert_true(True, "Pillow + numpy 可用")
    except ImportError:
        ts.assert_true(False, "Pillow/numpy 未安装")
        return ts.summary()

    # ---- 阶段 1: 模型发现 ----
    logger.info("\n" + "=" * 60)
    logger.info("  阶段 1: 模型文件发现")
    logger.info("=" * 60)

    silver_path = find_model("best_fp16.onnx")
    clothes_path = find_model("clothesfp16.onnx")

    ts.assert_true(bool(silver_path), f"银饰模型 best_fp16.onnx ({silver_path})")
    ts.assert_true(bool(clothes_path), f"服装模型 clothesfp16.onnx ({clothes_path})")

    if not silver_path or not clothes_path:
        logger.error("模型文件缺失，测试终止。请确保 best_fp16.onnx 和 clothesfp16.onnx 在上述路径之一。")
        return ts.summary()

    # 模型文件大小
    for label, path in [("银饰", silver_path), ("服装", clothes_path)]:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        ts.assert_gt(size_mb, 1, f"{label}模型文件 > 1MB ({size_mb:.1f} MB)")

    # ---- 阶段 2: 模型加载 ----
    logger.info("\n" + "=" * 60)
    logger.info("  阶段 2: ONNX 模型加载")
    logger.info("=" * 60)

    try:
        detector = MiaoPipelineDetector(silver_path, clothes_path)
        ts.assert_true(True, "双模型 Pipeline 实例化")
    except Exception as e:
        ts.assert_true(False, f"模型加载异常: {e}")
        return ts.summary()

    # 验证模型属性
    ts.assert_equal(len(detector.silver.names), 8, "银饰模型类别数 = 8")
    ts.assert_equal(len(detector.clothes.names), 2, "服装模型类别数 = 2")
    ts.assert_equal(detector.silver._input_shape[0], 640, "银饰模型输入宽度 = 640")
    ts.assert_equal(detector.clothes._input_shape[0], 640, "服装模型输入宽度 = 640")

    if quick:
        logger.info("\n⚡ --quick 模式：跳过推理测试")
        return ts.summary()

    # ---- 阶段 3: 推理测试 ----
    logger.info("\n" + "=" * 60)
    logger.info("  阶段 3: 推理功能测试")
    logger.info("=" * 60)

    # 准备测试图
    if image_path and os.path.exists(image_path):
        test_img = Image.open(image_path).convert("RGB")
        logger.info(f"  使用用户图片: {image_path} ({test_img.size})")
    else:
        test_img = create_test_image()
        logger.info(f"  使用合成测试图: {test_img.size[0]}x{test_img.size[1]}")

    # 3a. Silver 模式
    logger.info("\n  --- 3a. mode=silver ---")
    res = detector.detect(test_img, mode="silver")
    ts.assert_true("silver" in res, "返回结果含 'silver' 字段")
    ts.assert_true("cost_ms" in res, "返回结果含 'cost_ms' 字段")
    ts.assert_true("silver" in res["cost_ms"], "cost_ms 含 'silver'")
    ts.assert_lt(res["cost_ms"]["silver"], 5000, "银饰推理 < 5000ms")
    ts.assert_true(isinstance(res["silver"], list), "silver 检测结果为 list 类型")
    if res["silver"]:
        det = res["silver"][0]
        ts.assert_true("class" in det, "检测项含 'class'")
        ts.assert_true("confidence" in det, "检测项含 'confidence'")
        ts.assert_true("bbox" in det, "检测项含 'bbox'")
        ts.assert_gt(det["confidence"], 0, "置信度 > 0")
        ts.assert_lt(det["confidence"], 1.01, "置信度 <= 1")

    # 3b. Clothes 模式
    logger.info("\n  --- 3b. mode=clothes ---")
    res = detector.detect(test_img, mode="clothes")
    ts.assert_true("clothes" in res, "返回结果含 'clothes' 字段")
    ts.assert_lt(res["cost_ms"]["clothes"], 5000, "服装推理 < 5000ms")

    # 3c. Pipeline 模式（关闭过滤看原始输出）
    logger.info("\n  --- 3c. mode=pipeline (无过滤) ---")
    res = detector.detect(test_img, mode="pipeline", use_person_filter=False)
    ts.assert_true("clothes" in res, "pipeline 含 'clothes'")
    ts.assert_true("silver" in res, "pipeline 含 'silver'")
    ts.assert_true("triggered" in res, "pipeline 含 'triggered'")
    total = res["cost_ms"]["total"]
    ts.assert_lt(total, 10000, f"pipeline 总耗时 < 10000ms ({total}ms)")
    logger.info(f"  Pipeline 耗时: clothes={res['cost_ms']['clothes']}ms, "
                f"silver={res['cost_ms'].get('silver', 'N/A')}ms, total={total}ms")

    # 3d. Pipeline 模式（开启过滤）
    logger.info("\n  --- 3d. mode=pipeline (开启人物框过滤) ---")
    res = detector.detect(test_img, mode="pipeline", use_person_filter=True)
    ts.assert_true("silver_filtered" in res, "pipeline 含 'silver_filtered'")
    raw_count = len(res.get("silver", []))
    filtered_count = len(res.get("silver_filtered", []))
    ts.assert_true(filtered_count <= raw_count,
                   f"过滤后银饰 ≤ 原始银饰 ({filtered_count} <= {raw_count})")
    logger.info(f"  银饰: 原始 {raw_count} → 过滤后 {filtered_count}")

    # ---- 阶段 4: 输出格式一致性 ----
    logger.info("\n" + "=" * 60)
    logger.info("  阶段 4: 输出格式一致性")
    logger.info("=" * 60)

    # 对三种模式的返回格式做 schema 验证
    required_keys = {"mode", "clothes", "silver", "silver_filtered", "triggered", "cost_ms"}
    for mode_name in ["silver", "clothes", "pipeline"]:
        res = detector.detect(test_img, mode=mode_name)
        missing = required_keys - set(res.keys())
        ts.assert_true(len(missing) == 0, f"{mode_name} 模式返回包含所有必需字段 (缺失: {missing})")

    # 验证 cost_ms.total 一致性
    res = detector.detect(test_img, mode="pipeline")
    manual_sum = sum(v for k, v in res["cost_ms"].items()
                     if k != "total" and isinstance(v, (int, float)))
    ts.assert_true(abs(res["cost_ms"]["total"] - manual_sum) < 5,
                   f"total ({res['cost_ms']['total']}) ≈ 各阶段之和 ({manual_sum})")

    # ---- 阶段 5: 性能基准 ----
    logger.info("\n" + "=" * 60)
    logger.info("  阶段 5: 性能基准（预热后取平均）")
    logger.info("=" * 60)

    # 预热
    for _ in range(2):
        detector.detect(test_img, mode="silver")

    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        detector.detect(test_img, mode="silver")
        times.append((time.perf_counter() - t0) * 1000)

    avg_ms = round(sum(times) / len(times), 1)
    logger.info(f"  Silver 模式平均推理耗时: {avg_ms}ms (5次采样: {[round(t,1) for t in times]})")
    ts.assert_lt(avg_ms, 5000, f"平均推理 < 5000ms ({avg_ms}ms)")

    return ts.summary()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="苗绣·识裳 YOLO 双模型系统测试")
    parser.add_argument("--image", type=str, default="", help="测试图片路径 (可选)")
    parser.add_argument("--quick", action="store_true", help="仅加载模型，不跑推理")
    parser.add_argument("--output", type=str, default="", help="测试结果 JSON 输出路径")
    args = parser.parse_args()

    exit_code = run_tests(image_path=args.image, quick=args.quick)

    # 可选：输出 JSON 报告
    if args.output:
        report = {
            "exit_code": exit_code,
            "image": args.image or "synthetic",
            "quick": args.quick,
        }
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)

    sys.exit(exit_code)
