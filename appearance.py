# -*- coding: utf-8 -*-
"""外观风格：经典单图 / 毛绒实拍精灵表 / 矢量扁平精灵表。"""

from PyQt5.QtCore import QSettings, QRect
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor

STYLE_CLASSIC = "classic"
STYLE_PLUSH = "plush"
STYLE_VECTOR = "vector"

STYLE_LABELS = {
    STYLE_CLASSIC: "经典毛绒",
    STYLE_PLUSH: "毛绒实拍",
    STYLE_VECTOR: "矢量扁平",
}

STYLE_SHEETS = {
    STYLE_PLUSH: "eggplant-spritesheet-plush-rgba.png",
    STYLE_VECTOR: "eggplant-spritesheet-vector-rgba.png",
}

# 旧紧凑表期望帧数；V1 等分表用 _V1_FRAME_COUNTS
_FALLBACK_FRAME_COUNTS = [6, 9, 9, 4, 5, 8, 6, 6, 6]
# Codex V1：1536×1872 / 8×9 / 192×208
_V1_ATLAS_W, _V1_ATLAS_H = 1536, 1872
_V1_CELL_W, _V1_CELL_H = 192, 208
_V1_COLS, _V1_ROWS = 8, 9
_V1_FRAME_COUNTS = [6, 8, 8, 6, 6, 6, 6, 8, 6]
IDLE_ROW = 0
_TARGET_ROWS = 9

_SETTINGS_KEY = "appearance/style"
_ALPHA_THR = 28


class AppearanceManager:
    """加载精灵表：相对谷值分行 + 峰值中点切帧。"""

    def __init__(self, resource_path_fn):
        self._resource_path = resource_path_fn
        self._settings = QSettings("EggplantPet", "EggplantPet")
        saved = self._settings.value(_SETTINGS_KEY, STYLE_CLASSIC)
        self.style = saved if saved in STYLE_LABELS else STYLE_CLASSIC
        self._sheets = {}
        self._row_frames = {}
        self._frame_cache = {}

    def set_style(self, style_id):
        if style_id not in STYLE_LABELS:
            return False
        if style_id == self.style:
            return True
        self.style = style_id
        self._settings.setValue(_SETTINGS_KEY, style_id)
        self._frame_cache.clear()
        return True

    def is_sprite_style(self):
        return self.style in STYLE_SHEETS

    def style_label(self):
        return STYLE_LABELS.get(self.style, STYLE_LABELS[STYLE_CLASSIC])

    def _load_sheet(self, style_id):
        if style_id in self._sheets:
            return self._sheets[style_id]
        path = self._resource_path(STYLE_SHEETS[style_id])
        pix = QPixmap(path)
        self._sheets[style_id] = None if pix.isNull() else pix
        if not pix.isNull():
            self._row_frames[style_id] = self._detect_frames(pix)
        return self._sheets[style_id]

    def _detect_frames(self, sheet):
        image = sheet.toImage().convertToFormat(QImage.Format_ARGB32)
        sw, sh = image.width(), image.height()

        # Codex V1 标准图集：等分网格，无需谷值检测
        if sw == _V1_ATLAS_W and sh == _V1_ATLAS_H:
            return self._detect_frames_v1_grid(image)

        row_dense = [0.0] * sh
        for y in range(sh):
            hit = 0
            for x in range(0, sw, 2):
                if image.pixelColor(x, y).alpha() > _ALPHA_THR:
                    hit += 1
            row_dense[y] = hit / max(1, sw // 2)

        row_bounds = _detect_row_bounds(row_dense, target_rows=_TARGET_ROWS)
        rows = []

        for row_idx, (y0, y1) in enumerate(row_bounds):
            h = max(1, y1 - y0)
            expected = _FALLBACK_FRAME_COUNTS[min(row_idx, len(_FALLBACK_FRAME_COUNTS) - 1)]

            col_dense = [0.0] * sw
            for x in range(sw):
                hit = 0
                step = max(1, h // 40)
                for y in range(y0, y1, step):
                    if image.pixelColor(x, y).alpha() > _ALPHA_THR:
                        hit += 1
                col_dense[x] = hit / max(1, (h + step - 1) // step)

            segments = _peak_segments(col_dense, expected)
            if len(segments) < max(2, expected // 2):
                segments = _equal_segments_in_content(col_dense, expected)

            frames = []
            for x0, x1 in segments:
                # 略向内收，减少行间渗色
                iy0 = y0 + 1
                iy1 = y1 - 1
                if iy1 <= iy0:
                    iy0, iy1 = y0, y1
                bx0, by0, bx1, by1 = _content_bbox(
                    image, x0, iy0, x1 - x0, iy1 - iy0, _ALPHA_THR
                )
                if bx1 - bx0 < 20 or by1 - by0 < 20:
                    continue
                if (bx1 - bx0) * (by1 - by0) < 900:
                    continue
                pad = 4
                frames.append(QRect(
                    max(0, bx0 - pad),
                    max(y0, by0 - pad),
                    min(sw, bx1 + pad) - max(0, bx0 - pad),
                    min(y1, by1 + pad) - max(y0, by0 - pad),
                ))

            if len(frames) < max(2, expected // 2):
                frames = []
                for x0, x1 in _equal_segments_in_content(col_dense, expected):
                    frames.append(QRect(x0, y0, max(1, x1 - x0), h))

            rows.append(frames)
        return rows

    def _detect_frames_v1_grid(self, image):
        """1536×1872 / 192×208 等分；跳过全透明格。"""
        rows = []
        for row_idx in range(_V1_ROWS):
            expected = _V1_FRAME_COUNTS[row_idx]
            frames = []
            for col in range(min(expected, _V1_COLS)):
                x = col * _V1_CELL_W
                y = row_idx * _V1_CELL_H
                # 快速采样：格内是否有不透明像素
                hit = False
                for yy in range(y + 8, y + _V1_CELL_H - 8, 6):
                    for xx in range(x + 8, x + _V1_CELL_W - 8, 6):
                        if image.pixelColor(xx, yy).alpha() > _ALPHA_THR:
                            hit = True
                            break
                    if hit:
                        break
                if not hit:
                    continue
                frames.append(QRect(x, y, _V1_CELL_W, _V1_CELL_H))
            rows.append(frames)
        return rows

    def _frames_for_row(self, row):
        sheet = self._load_sheet(self.style)
        if sheet is None:
            return []
        rows = self._row_frames.get(self.style) or []
        if not rows:
            return []
        row = max(0, min(int(row), len(rows) - 1))
        return rows[row]

    def get_frame(self, row, col):
        if not self.is_sprite_style():
            return QPixmap()
        key = (self.style, int(row), int(col))
        if key in self._frame_cache:
            return self._frame_cache[key]

        sheet = self._load_sheet(self.style)
        if sheet is None or sheet.isNull():
            return QPixmap()

        frames = self._frames_for_row(row)
        if not frames:
            return QPixmap()
        col = max(0, min(int(col), len(frames) - 1))
        cropped = sheet.copy(frames[col])
        # V1 等分格已含安全边，不再做激进裁切
        is_v1 = (
            not sheet.isNull()
            and sheet.width() == _V1_ATLAS_W
            and sheet.height() == _V1_ATLAS_H
        )
        if not is_v1:
            cropped = _keep_main_sprite(cropped)
            cropped = _trim_vertical_bleed(cropped)
            cropped = _trim_stacked_sprite(cropped)
            cropped = _trim_wide_duplicate(cropped)
        framed = _pad_to_square(cropped)
        self._frame_cache[key] = framed
        return framed

    def idle_frame_count(self):
        return max(1, len(self._frames_for_row(IDLE_ROW)))

    def action_row_count(self):
        self._load_sheet(self.style)
        rows = self._row_frames.get(self.style) or []
        return max(1, len(rows))

    def action_frame_count(self, row):
        return max(1, len(self._frames_for_row(row)))


def _smooth(values, radius=15):
    n = len(values)
    if n == 0:
        return values
    out = [0.0] * n
    for i in range(n):
        a = max(0, i - radius)
        b = min(n, i + radius + 1)
        out[i] = sum(values[a:b]) / (b - a)
    return out


def _detect_row_bounds(row_dense, target_rows=9):
    """用相对深度谷值分行（行与行几乎贴边时，绝对阈值会失效）。"""
    h = len(row_dense)
    if h < 80:
        return [(0, h)]

    smooth = _smooth(row_dense, radius=12)
    margin = max(36, h // 28)
    candidates = []
    for y in range(margin, h - margin):
        if smooth[y] > smooth[y - 1] or smooth[y] > smooth[y + 1]:
            continue
        win0, win1 = max(0, y - 45), min(h, y + 46)
        local_max = max(smooth[win0:win1])
        depth = local_max - smooth[y]
        if depth < 0.10:
            continue
        if smooth[y] > local_max * 0.62:
            continue
        # 抑制过密候选：同窗只留更深的
        # 把切点挪到空隙带中心，减少吃进邻行
        g0 = y
        while g0 > margin and smooth[g0] <= smooth[y] + 0.03:
            g0 -= 1
        g1 = y
        while g1 < h - margin and smooth[g1] <= smooth[y] + 0.03:
            g1 += 1
        cut_y = (g0 + g1) // 2

        if candidates and cut_y - candidates[-1][0] < 48:
            if depth > candidates[-1][1]:
                candidates[-1] = (cut_y, depth, smooth[cut_y])
            continue
        candidates.append((cut_y, depth, smooth[cut_y]))

    need = target_rows - 1
    # 优先更深的谷，再按 y 排序；同时尝试 8 行（毛绒表常见）
    ranked = sorted(candidates, key=lambda t: (-t[1], t[2]))

    def build(n_cuts):
        chosen = []
        for y, depth, val in ranked:
            if len(chosen) >= n_cuts:
                break
            if all(abs(y - c) >= 55 for c in chosen):
                # 保证每段不太矮
                trial = sorted(chosen + [y])
                bounds = [0] + trial + [h]
                if all(bounds[i + 1] - bounds[i] >= 70 for i in range(len(bounds) - 1)):
                    chosen.append(y)
        return sorted(chosen)

    # 选得分更好的切分数（切点处密度更低）
    best_cuts = None
    best_score = None
    for n_cuts in (need, need - 1, need - 2):
        if n_cuts < 5:
            continue
        cuts = build(n_cuts)
        if len(cuts) < max(5, n_cuts - 1):
            continue
        score = sum(smooth[c] for c in cuts) / len(cuts)
        # 偏好接近目标行数，且切点更“空”
        score += abs(len(cuts) + 1 - target_rows) * 0.02
        if best_score is None or score < best_score:
            best_score = score
            best_cuts = cuts

    if not best_cuts:
        # 回退等分
        best_cuts = [int(round((i + 1) * h / target_rows)) for i in range(need)]

    bounds = [0] + sorted(best_cuts) + [h]
    # 精灵表已含真实行间距时，只需极小内收避开抗锯齿渗色
    rows = []
    for i in range(len(bounds) - 1):
        y0, y1 = bounds[i], bounds[i + 1]
        inset = 2
        if i > 0:
            y0 += inset
        if i < len(bounds) - 2:
            y1 -= inset
        if y1 - y0 < 50:
            y0, y1 = bounds[i], bounds[i + 1]
        rows.append((y0, y1))
    return rows


def _local_peaks(values, min_distance, height):
    peaks = []
    n = len(values)
    for i in range(1, n - 1):
        if values[i] < height:
            continue
        if values[i] >= values[i - 1] and values[i] >= values[i + 1]:
            if not peaks or i - peaks[-1] >= min_distance:
                peaks.append(i)
            elif values[i] > values[peaks[-1]]:
                peaks[-1] = i
    return peaks


def _peak_segments(col_dense, expected):
    """以峰值为中心，用相邻峰中点作为左右边界，避免固定半宽切到邻居。"""
    smooth = _smooth(col_dense, radius=10)
    mx = max(smooth) if smooth else 0
    if mx <= 0:
        return []

    n = len(col_dense)
    dist = max(28, int(n / max(expected, 1) * 0.35))
    peaks = _local_peaks(smooth, dist, mx * 0.22)
    if len(peaks) < 2:
        return []

    # 若峰太多，保留最高的 expected 个（按位置排序）
    if len(peaks) > expected + 2:
        keep = sorted(peaks, key=lambda i: -smooth[i])[:expected]
        peaks = sorted(keep)
    elif len(peaks) > expected:
        # 去掉最弱的多余峰
        while len(peaks) > expected:
            weakest = min(range(len(peaks)), key=lambda k: smooth[peaks[k]])
            peaks.pop(weakest)

    if len(peaks) < 2:
        return []

    # 内容左右边界，避免首尾段吞进空白
    xs = [i for i, v in enumerate(col_dense) if v > 0.04]
    left_edge = xs[0] if xs else 0
    right_edge = (xs[-1] + 1) if xs else n

    segs = []
    for i, cx in enumerate(peaks):
        if i == 0:
            x0 = left_edge
        else:
            x0 = (peaks[i - 1] + cx) // 2
        if i == len(peaks) - 1:
            x1 = right_edge
        else:
            x1 = (cx + peaks[i + 1]) // 2
        # 略收边，减少帧间渗色
        pad = 2
        x0 = max(left_edge, x0 + pad)
        x1 = min(right_edge, x1 - pad)
        if x1 - x0 >= 24:
            segs.append((x0, x1))
    return segs


def _equal_segments_in_content(col_dense, count):
    xs = [i for i, v in enumerate(col_dense) if v > 0.05]
    n = len(col_dense)
    if not xs:
        step = max(1, n // count)
        return [(i * step, n if i == count - 1 else (i + 1) * step) for i in range(count)]
    left, right = xs[0], xs[-1] + 1
    for x in range(right - 1, left, -1):
        if col_dense[x] > 0.12:
            right = x + 1
            break
    width = max(1, right - left)
    step = width / float(count)
    segs = []
    for i in range(count):
        a = left + int(i * step)
        b = right if i == count - 1 else left + int((i + 1) * step)
        segs.append((a, max(a + 1, b)))
    return segs


def _content_bbox(image, x, y, w, h, thr):
    x1, y1 = x + w, y + h
    min_x, min_y = x1, y1
    max_x, max_y = x, y
    found = False
    for yy in range(y, y1):
        for xx in range(x, x1):
            if image.pixelColor(xx, yy).alpha() > thr:
                found = True
                min_x = min(min_x, xx)
                min_y = min(min_y, yy)
                max_x = max(max_x, xx)
                max_y = max(max_y, yy)
    if not found:
        return x, y, x, y
    return min_x, min_y, max_x + 1, max_y + 1


def _keep_main_sprite(pixmap):
    """连通域清洗：保留最大主体及其邻近小道具，去掉行间渗入的残片。"""
    if pixmap.isNull():
        return pixmap
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = image.width(), image.height()
    if w * h > 400_000:
        return pixmap

    visited = [[False] * w for _ in range(h)]
    components = []

    for sy in range(h):
        for sx in range(w):
            if visited[sy][sx] or image.pixelColor(sx, sy).alpha() <= _ALPHA_THR:
                continue
            stack = [(sx, sy)]
            visited[sy][sx] = True
            pixels = []
            min_x = min_y = 10**9
            max_x = max_y = -1
            while stack:
                x, y = stack.pop()
                pixels.append((x, y))
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                        if image.pixelColor(nx, ny).alpha() > _ALPHA_THR:
                            visited[ny][nx] = True
                            stack.append((nx, ny))
            area = len(pixels)
            if area < 12:
                continue
            components.append({
                "pixels": pixels,
                "area": area,
                "bbox": (min_x, min_y, max_x + 1, max_y + 1),
            })

    if not components:
        return pixmap

    components.sort(key=lambda c: -c["area"])
    main = components[0]
    mx0, my0, mx1, my1 = main["bbox"]
    keep = {main["area"]: True}
    kept_pixels = set(main["pixels"])

    def bbox_dist(a, b):
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        dx = 0 if ax1 >= bx0 and bx1 >= ax0 else min(abs(ax0 - bx1), abs(bx0 - ax1))
        dy = 0 if ay1 >= by0 and by1 >= ay0 else min(abs(ay0 - by1), abs(by0 - ay1))
        return (dx * dx + dy * dy) ** 0.5

    proximity = max(14, int(min(w, h) * 0.10))
    for comp in components[1:]:
        cx0, cy0, cx1, cy1 = comp["bbox"]
        cy = (cy0 + cy1) / 2
        overlaps_x = (cx1 >= mx0 - 10) and (cx0 <= mx1 + 10)
        dist = bbox_dist(comp["bbox"], main["bbox"])

        # 气球/绳子断开：主体正上方
        above_main = cy1 <= my0 + 6 and overlaps_x and comp["area"] < main["area"] * 0.75

        # 贴底小残片几乎都是下一行渗色（绿蒂/气球顶），一律丢弃
        if cy1 >= h - 2 and cy0 > int(h * 0.55) and comp["area"] < main["area"] * 0.4:
            continue
        # 贴顶且偏小：邻行底部渗色（不是气球）
        if cy0 <= 1 and cy1 < int(h * 0.28) and not above_main and comp["area"] < main["area"] * 0.22:
            continue

        near_prop = dist <= proximity or (
            overlaps_x
            and comp["area"] < main["area"] * 0.35
            and abs(cy - (my0 + my1) / 2) < h * 0.55
            and cy0 > 2
            and cy1 < h - 2
        )

        if above_main or near_prop:
            kept_pixels.update(comp["pixels"])

    out = QImage(w, h, QImage.Format_ARGB32)
    out.fill(QColor(0, 0, 0, 0))
    for x, y in kept_pixels:
        out.setPixelColor(x, y, image.pixelColor(x, y))

    # 再收紧到保留像素的 bbox
    bx0, by0, bx1, by1 = _content_bbox(out, 0, 0, w, h, _ALPHA_THR)
    if bx1 - bx0 < 8 or by1 - by0 < 8:
        return pixmap
    return QPixmap.fromImage(out.copy(bx0, by0, bx1 - bx0, by1 - by0))


def _row_hits(image):
    w, h = image.width(), image.height()
    hits = []
    for y in range(h):
        hit = 0
        for x in range(0, w, 2):
            if image.pixelColor(x, y).alpha() > _ALPHA_THR:
                hit += 1
        hits.append(hit)
    return hits


def _trim_vertical_bleed(pixmap):
    """去掉上下边缘渗入的邻行残片（即使有少量像素桥接）。

    - 底部：下 40% 内若出现低谷且下方内容远小于上方，砍掉下方
    - 顶部：仅当顶上是很小一坨（邻行脚/桌），不砍气球
    """
    if pixmap.isNull():
        return pixmap
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = image.width(), image.height()
    if h < 40:
        return pixmap

    row_hit = _row_hits(image)
    mx = max(row_hit) if row_hit else 0
    if mx <= 0:
        return pixmap
    smooth = _smooth([float(v) for v in row_hit], radius=3)

    # --- 底部渗色 ---
    search0, search1 = int(h * 0.55), h - 3
    best_cut = None
    best_score = -1.0
    for y in range(search0, search1):
        if smooth[y] > mx * 0.14:
            continue
        # 空隙带
        g0 = y
        while g0 > search0 and smooth[g0] <= mx * 0.14:
            g0 -= 1
        g1 = y
        while g1 < h - 1 and smooth[g1] <= mx * 0.14:
            g1 += 1
        if g1 - g0 < 2:
            continue
        up = sum(row_hit[:g0])
        down = sum(row_hit[g1:])
        if down < 8:
            continue
        if up < down * 3:
            continue
        # 下方应是矮残片
        if (h - g1) > int(h * 0.28):
            continue
        score = (up / max(1, down)) * (g1 - g0)
        if score > best_score:
            best_score = score
            best_cut = (g0 + g1) // 2

    if best_cut is not None:
        pixmap = pixmap.copy(QRect(0, 0, w, best_cut))
        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        w, h = image.width(), image.height()
        row_hit = _row_hits(image)
        mx = max(row_hit) if row_hit else 0
        if mx <= 0:
            return pixmap
        smooth = _smooth([float(v) for v in row_hit], radius=3)

    # --- 顶部渗色（小残片，不是气球）---
    search1 = max(4, int(h * 0.22))
    best_cut = None
    best_score = -1.0
    for y in range(3, search1):
        if smooth[y] > mx * 0.14:
            continue
        g0 = y
        while g0 > 0 and smooth[g0] <= mx * 0.14:
            g0 -= 1
        g1 = y
        while g1 < search1 and smooth[g1] <= mx * 0.14:
            g1 += 1
        if g1 - g0 < 2:
            continue
        up = sum(row_hit[:g0 + 1])
        down = sum(row_hit[g1:])
        if up < 8 or down < up * 4:
            continue
        # 上方太高/太大 → 可能是气球，不砍
        if g0 > int(h * 0.18) or up > down * 0.35:
            continue
        score = (down / max(1, up)) * (g1 - g0)
        if score > best_score:
            best_score = score
            best_cut = (g0 + g1) // 2

    if best_cut is not None:
        pixmap = pixmap.copy(QRect(0, best_cut, w, h - best_cut))
    return pixmap


def _trim_stacked_sprite(pixmap):
    """中部大空隙且上下两团时，保留上方（双角色叠帧）。"""
    if pixmap.isNull():
        return pixmap

    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = image.width(), image.height()
    if h < 50:
        return pixmap

    row_hit = _row_hits(image)
    mx = max(row_hit) if row_hit else 0
    if mx <= 0:
        return pixmap

    mid0, mid1 = h // 5, (h * 4) // 5
    best_gap = None
    best_score = None
    y = mid0
    while y < mid1:
        if row_hit[y] > mx * 0.08:
            y += 1
            continue
        g0 = y
        while y < mid1 and row_hit[y] <= mx * 0.08:
            y += 1
        g1 = y
        gap_h = g1 - g0
        if gap_h < 8:
            continue
        mid = (g0 + g1) // 2
        up = sum(row_hit[:g0])
        down = sum(row_hit[g1:])
        up_span = 0
        for i in range(g0 - 1, -1, -1):
            if row_hit[i] > mx * 0.15:
                up_span += 1
            elif up_span > 0:
                break
        # 气球细线空隙 narrow；真正叠角色空隙更宽，且上下质量接近
        if gap_h >= 10 and up > 0 and down > 0 and up_span >= int(h * 0.35):
            if down > up * 0.35 and gap_h >= 12:
                score = gap_h
                if best_score is None or score > best_score:
                    best_score = score
                    best_gap = mid
    if best_gap is None:
        return pixmap
    return pixmap.copy(QRect(0, 0, w, best_gap))


def _trim_wide_duplicate(pixmap):
    """过宽且左右各有一团内容时，只留左侧主体。"""
    if pixmap.isNull():
        return pixmap
    if pixmap.width() <= int(pixmap.height() * 1.35):
        return pixmap
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = image.width(), image.height()
    col_hit = []
    for x in range(w):
        hit = 0
        for y in range(0, h, 2):
            if image.pixelColor(x, y).alpha() > _ALPHA_THR:
                hit += 1
        col_hit.append(hit)
    mx = max(col_hit) if col_hit else 0
    if mx <= 0:
        return pixmap
    mid0, mid1 = w // 3, (w * 2) // 3
    gap = None
    for x in range(mid0, mid1):
        if col_hit[x] <= mx * 0.1:
            left = any(col_hit[i] > mx * 0.25 for i in range(0, x))
            right = any(col_hit[i] > mx * 0.25 for i in range(x + 1, w))
            if left and right:
                gap = x
                break
    if gap is None:
        return pixmap.copy(QRect(0, 0, min(w, int(h * 1.15)), h))
    return pixmap.copy(QRect(0, 0, gap, h))


def _pad_to_square(pixmap):
    if pixmap.isNull():
        return pixmap
    side = max(pixmap.width(), pixmap.height(), 1)
    out = QPixmap(side, side)
    out.fill(QColor(0, 0, 0, 0))
    painter = QPainter(out)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.drawPixmap((side - pixmap.width()) // 2, (side - pixmap.height()) // 2, pixmap)
    painter.end()
    return out
