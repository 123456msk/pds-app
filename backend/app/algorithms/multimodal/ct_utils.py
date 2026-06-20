# ct_utils.py
import json
import os
import cv2
import numpy as np
import pydicom


def apply_windowing(image, window_center, window_width):
    """应用窗宽和窗位"""
    min_window = window_center - window_width / 2
    max_window = window_center + window_width / 2
    return np.clip(image, min_window, max_window)


def save_ct_results_to_json(dcm_path, detection_results, pixel_spacing,output_dir):
    """
    仅保存左右中心点坐标到 JSON；不再保存半径、能量。
    JSON 格式：
    {
        "left_femoral_head": {"x": int, "y": int},
        "right_femoral_head": {"x": int, "y": int}
    }
    """
    import os, json
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(dcm_path))[0]
    save_path = os.path.join(output_dir, f"radii_{base_name}.json")

    # 默认 0,0；按 x 坐标排序后取左/右
    left_center = {"x": 0, "y": 0}
    right_center = {"x": 0, "y": 0}

    # 为确保左右正确，按 x 从小到大
    detection_results = list(detection_results) or []
    detection_results.sort(key=lambda r: r['center'][0])

    if len(detection_results) >= 1:
        c = detection_results[0]['center']
        left_center = {"x": int(c[0]), "y": int(c[1])}
    if len(detection_results) >= 2:
        c = detection_results[1]['center']
        right_center = {"x": int(c[0]), "y": int(c[1])}

    data = {
        "left_femoral_head": left_center,
        "right_femoral_head": right_center
    }

    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"✅ 已保存中心点: {save_path}")



def find_femoral_heads_adaptive(dcm_file_path, config):
    """
    股骨头定位 (去除可视化显示)
    返回: (final_results, pixel_spacing) 或 (None, None)
    """
    try:
        ds = pydicom.dcmread(dcm_file_path)
        hu_image = ds.pixel_array.astype(np.float64) * ds.RescaleSlope + ds.RescaleIntercept
        height, width = hu_image.shape
        try:
            pixel_spacing = ds.PixelSpacing[0]
        except (AttributeError, IndexError):
            pixel_spacing = config['DEFAULT_PIXEL_SPACING']

        # --- 骨骼分割 ---
        bone_mask = np.where(hu_image > config['BONE_THRESHOLD_HU'], 255, 0).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, tuple(config['MORPH_KERNEL_SIZE']))
        cleaned_bone_mask = cv2.morphologyEx(bone_mask, cv2.MORPH_CLOSE, kernel, iterations=config['MORPH_ITERATIONS'])
        contours, _ = cv2.findContours(cleaned_bone_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bone_fragments = [c for c in contours if cv2.contourArea(c) > config['MIN_BONE_AREA_PIXELS']]
        if len(bone_fragments) < 2:
            return None, None

        mid_x = width // 2
        def cx(c):
            m = cv2.moments(c)
            return m['m10'] / m['m00'] if m['m00'] != 0 else None

        left_fragments = [c for c in bone_fragments if (cx(c) and cx(c) < mid_x)]
        right_fragments = [c for c in bone_fragments if (cx(c) and cx(c) >= mid_x)]
        if not left_fragments or not right_fragments:
            return None, None

        initial_contours = [max(left_fragments, key=cv2.contourArea), max(right_fragments, key=cv2.contourArea)]
        initial_contours.sort(key=lambda c: cx(c))

        grad_x = cv2.Sobel(hu_image, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(hu_image, cv2.CV_64F, 0, 1, ksize=3)

        # --- 霍夫圆检测 ---
        min_radius_mm, max_radius_mm = config['FEMORAL_HEAD_DIAMETER_MM_RANGE']
        min_radius_px = int((min_radius_mm/2)/pixel_spacing)
        max_radius_px = int((max_radius_mm/2)/pixel_spacing)
        hough_params = dict(config['HOUGH_CIRCLES_PARAMS'])
        hough_params.update({'minRadius': min_radius_px, 'maxRadius': max_radius_px})
        hough_input_img = cv2.normalize(apply_windowing(hu_image, *config['BONE_WINDOW_HOUGH']),
                                        None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        final_results = []
        for i, contour in enumerate(initial_contours):
            roi_mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(roi_mask, [contour], -1, 255, thickness=cv2.FILLED)
            hough_roi_img = cv2.bitwise_and(hough_input_img, hough_input_img, mask=roi_mask)
            circles = cv2.HoughCircles(hough_roi_img, cv2.HOUGH_GRADIENT, **hough_params)
            if circles is None:
                continue

            best_circle_info, max_final_energy = None, -np.inf
            for c in circles[0, :]:
                center, radius = (int(c[0]), int(c[1])), int(c[2])

                # 圆周能量计算
                num_points = max(int(2 * np.pi * radius), 8)
                angles = np.linspace(0, 2 * np.pi, num_points)
                px = (center[0] + radius * np.cos(angles)).astype(int)
                py = (center[1] + radius * np.sin(angles)).astype(int)
                valid_idx = (py >= 0) & (py < height) & (px >= 0) & (px < width)
                py, px = py[valid_idx], px[valid_idx]
                if len(px) == 0:
                    continue

                vrx, vry = px - center[0], py - center[1]
                nr = np.sqrt(vrx**2 + vry**2)
                vgx, vgy = grad_x[py, px], grad_y[py, px]
                ng = np.sqrt(vgx**2 + vgy**2)
                valid_grad = ng > 1e-6
                dp = np.zeros_like(vrx, dtype=float)
                if np.any(valid_grad):
                    dp[valid_grad] = (vrx[valid_grad] * vgx[valid_grad] +
                                      vry[valid_grad] * vgy[valid_grad]) / (nr[valid_grad] * ng[valid_grad])
                rad_sq = np.mean(np.abs(dp)) ** 3

                mags = ng
                std_dev_mags = np.std(mags)
                mean_mags = np.mean(mags)
                coeff_of_variation = std_dev_mags / (mean_mags + 1e-6)
                energy_consistency = 1.0 / (1.0 + coeff_of_variation)

                final_energy = rad_sq * energy_consistency

                if final_energy > max_final_energy:
                    max_final_energy = final_energy
                    best_circle_info = {'center': center, 'radius': radius, 'contour': contour,
                                        'side': "左侧" if i == 0 else "右侧", 'energy': final_energy}
            
            if best_circle_info:
                final_results.append(best_circle_info)

        if len(final_results) >= 2:
            return final_results, pixel_spacing
        else:
            return None, None
    except Exception:
        import traceback
        traceback.print_exc()
        return None, None












def visualize_femoral_heads_cv(
    dcm_file_path,
    detection_results,
    pixel_spacing,
    output_dir,
    config
):
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(dcm_file_path))[0]

    ds = pydicom.dcmread(dcm_file_path)
    hu_image = (
        ds.pixel_array.astype(np.float64)
        * ds.RescaleSlope
        + ds.RescaleIntercept
    )

    h, w = hu_image.shape

    # ---------- 骨窗 ----------
    bone_window = apply_windowing(hu_image, *config['BONE_WINDOW_HOUGH'])
    bone_img = cv2.normalize(bone_window, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    bone_color = cv2.applyColorMap(bone_img, cv2.COLORMAP_BONE)

    # ---------- 软组织窗（✅ 修复点） ----------
    soft_window = apply_windowing(hu_image, 40, 400)
    soft_img = cv2.normalize(soft_window, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    soft_color = cv2.cvtColor(soft_img, cv2.COLOR_GRAY2BGR)  # ✅ 不会报错

    # ---------- 骨骼分割 ----------
    bone_mask = np.where(hu_image > config['BONE_THRESHOLD_HU'], 255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        tuple(config['MORPH_KERNEL_SIZE'])
    )
    bone_mask = cv2.morphologyEx(
        bone_mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=config['MORPH_ITERATIONS']
    )
    bone_mask_color = cv2.applyColorMap(bone_mask, cv2.COLORMAP_HOT)

    # ---------- 梯度 ----------
    grad_x = cv2.Sobel(hu_image, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(hu_image, cv2.CV_64F, 0, 1, ksize=3)
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)
    grad_img = cv2.normalize(grad_mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    grad_color = cv2.applyColorMap(grad_img, cv2.COLORMAP_JET)

    # ---------- 检测结果 ----------
    detected = detection_results is not None and len(detection_results) > 0

    if detected:
        colors = [(0, 255, 0), (0, 0, 255), (255, 0, 0), (0, 255, 255)]
        for i, res in enumerate(detection_results):
            center = tuple(map(int, res['center']))
            radius = int(res.get('radius', 40))
            color = colors[i % len(colors)]

            cv2.circle(bone_color, center, radius, color, 2, cv2.LINE_AA)
            cv2.circle(bone_color, center, 4, color, -1, cv2.LINE_AA)

            label = f"{res.get('side','')} ({center[0]},{center[1]})"
            cv2.putText(
                bone_color,
                label,
                (center[0] - 90, center[1] - radius - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA
            )
    else:
        cv2.putText(
            bone_color,
            "NO FEMORAL HEAD DETECTED",
            (w // 4, h // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 0, 255),
            3,
            cv2.LINE_AA
        )

    # ---------- 拼接 ----------
    top = np.hstack([bone_color, bone_mask_color])
    bottom = np.hstack([grad_color, soft_color])
    canvas = np.vstack([top, bottom])

    save_path = os.path.join(output_dir, f"vis_{base_name}.png")
    cv2.imwrite(save_path, canvas)

    print(f"✅ 可视化完成（detected={detected}）: {save_path}")
    return save_path


# 更新 __all__ 列表
__all__ = [
    "apply_windowing",
    "save_ct_results_to_json",
    "find_femoral_heads_adaptive",
    "visualize_femoral_heads",  # 新增
]
# __all__ = [
#     "apply_windowing",
#     "save_ct_results_to_json",
#     "find_femoral_heads_adaptive",
# ]
